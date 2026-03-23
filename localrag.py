import gradio as gr
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import PromptTemplate

# ── Global state ───────────────────────────────────────────────────────────────
combined_store   = None
per_file_stores  = {}
active_retriever = None
current_mode     = "combined"

# ── Models — CPU optimized ─────────────────────────────────────────────────────
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    num_thread=4,
)
llm = OllamaLLM(
    model="mistral",
    keep_alive=-1,
    num_predict=512,
    temperature=0.1,
    num_ctx=3072,
    num_thread=4,
)

# ── Prompt ─────────────────────────────────────────────────────────────────────
RAG_PROMPT = PromptTemplate.from_template("""You are a precise document assistant. Using ONLY the context below, answer the question directly.

Rules:
- Answer only what is asked — nothing more
- Do not mention unrelated names, dates, or details
- If multiple sections are relevant, combine into one clear answer
- If not found, say: "Not found in documents."
- Keep the answer concise but complete

Context:
{context}

Question: {question}

Answer:""")

# ── Splitter ───────────────────────────────────────────────────────────────────
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
)


# ── File loader router ─────────────────────────────────────────────────────────
def load_file(path: str):
    ext = path.lower().split(".")[-1]

    if ext == "pdf":
        return PyPDFLoader(path).load()

    elif ext in ("doc", "docx"):
        docs = Docx2txtLoader(path).load()
        # Tag each doc chunk with page number manually
        for i, doc in enumerate(docs):
            if "page" not in doc.metadata:
                doc.metadata["page"] = i
        return docs

    elif ext in ("xls", "xlsx"):
        docs = UnstructuredExcelLoader(path, mode="elements").load()
        for i, doc in enumerate(docs):
            # Excel uses sheet name — keep it if available
            if "page_number" in doc.metadata:
                doc.metadata["page"] = doc.metadata["page_number"]
            elif "page" not in doc.metadata:
                doc.metadata["page"] = i
        return docs

    elif ext in ("ppt", "pptx"):
        docs = UnstructuredPowerPointLoader(path, mode="elements").load()
        for doc in docs:
            # Unstructured provides page_number for slides
            if "page_number" in doc.metadata:
                doc.metadata["page"] = doc.metadata["page_number"] - 1  # make 0-indexed like PDF
            elif "page" not in doc.metadata:
                doc.metadata["page"] = 0
        return docs

    return []

# ── Process all uploaded files ─────────────────────────────────────────────────
def process_files(files):
    global combined_store, per_file_stores, active_retriever, current_mode

    if not files:
        yield "⚠️ Please upload at least one file.", gr.update(choices=[], value=None)
        return

    per_file_stores = {}
    all_chunks      = []
    file_summary    = []
    per_file_chunks = {}

    yield "⏳ Loading files...", gr.update(choices=[], value=None)

    for file in files:
        path     = file.name
        filename = path.replace("\\", "/").split("/")[-1]
        try:
            docs = load_file(path)
            if not docs:
                file_summary.append(f"  ⚠️ {filename} — unsupported or empty")
                continue
            for doc in docs:
                doc.metadata["source_file"] = filename
            chunks = SPLITTER.split_documents(docs)
            per_file_chunks[filename] = chunks
            all_chunks.extend(chunks)
            file_summary.append(f"  ✅ {filename} ({len(chunks)} chunks)")
        except Exception as e:
            file_summary.append(f"  ❌ {filename} — {str(e)}")

    if not all_chunks:
        yield "❌ No content extracted. Check file formats.", gr.update(choices=[], value=None)
        return

    yield f"⏳ Embedding {len(all_chunks)} chunks...", gr.update(choices=[], value=None)

    # Build combined store
    combined_store   = FAISS.from_documents(all_chunks, embeddings)
    active_retriever = combined_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3},
    )
    current_mode = "combined"

    # Build per-file stores
    for filename, chunks in per_file_chunks.items():
        per_file_stores[filename] = FAISS.from_documents(chunks, embeddings)

    dropdown_choices = ["🗂 All files (combined)"] + list(per_file_stores.keys())
    summary          = "\n".join(file_summary)

    yield (
        f"✅ Done! Indexed {len(all_chunks)} chunks from {len(per_file_stores)} file(s):\n{summary}\n\nAsk away!",
        gr.update(choices=dropdown_choices, value="🗂 All files (combined)")
    )


# ── Switch active knowledge base ───────────────────────────────────────────────
def switch_source(choice):
    global active_retriever, current_mode

    if not choice:
        return "No source selected."

    if choice == "🗂 All files (combined)":
        if combined_store is None:
            return "⚠️ No files processed yet."
        active_retriever = combined_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3},
        )
        current_mode = "combined"
        return "🗂 Now querying: ALL files combined"
    else:
        if choice not in per_file_stores:
            return f"⚠️ '{choice}' not found."
        active_retriever = per_file_stores[choice].as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3},
        )
        current_mode = choice
        return f"📄 Now querying: {choice} only"


# ── Ask question ───────────────────────────────────────────────────────────────
def ask_question(question):
    if not question.strip():
        return "Please type a question."
    if active_retriever is None:
        return "⚠️ Please upload and process files first."

    try:
        docs = active_retriever.invoke(question)

        # Filter to current file only in single-file mode
        if current_mode != "combined":
            docs = [doc for doc in docs if doc.metadata.get("source_file") == current_mode]
            if not docs:
                return "❌ No relevant content found in this file for your question."

        context     = "\n\n".join(doc.page_content for doc in docs)
        prompt_text = RAG_PROMPT.format(context=context, question=question)
        result      = llm.invoke(prompt_text)

        # Build sources
        seen    = set()
        sources = []
        for doc in docs:
            filename = doc.metadata.get("source_file", "Unknown")
            page     = doc.metadata.get("page")
            page_num = (page + 1) if isinstance(page, int) else None
            key      = (filename, page_num)
            if key not in seen:
                seen.add(key)
                # Show correct label per file type
                ext = filename.lower().split(".")[-1]
                if ext in ("ppt", "pptx") and page_num:
                    label = f"{filename} — Slide {page_num}"
                elif ext in ("xls", "xlsx") and page_num:
                    label = f"{filename} — Sheet/Row {page_num}"
                elif page_num:
                    label = f"{filename} — Page {page_num}"
                else:
                    label = filename
                preview = doc.page_content[:100].replace("\n", " ")
                sources.append(f"  • {label}: {preview}...")

        return result + "\n\n---\n📄 Sources:\n" + "\n".join(sources)

    except Exception as e:
        return f"❌ Error: {str(e)}"



# ── Gradio UI ──────────────────────────────────────────────────────────────────
with gr.Blocks(title="Offline RAG Chatbot") as app:
    gr.Markdown("# 📄 Offline RAG Chatbot — FAISS + Ollama + Mistral")
    gr.Markdown(
        "**Fully offline.** Upload PDF, DOCX, XLSX, PPTX. "
        "Query all at once or switch to a single file."
    )

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(
                label="📂 Upload Files (PDF / DOCX / XLSX / PPTX)",
                file_types=[".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"],
                file_count="multiple",
            )
            process_btn = gr.Button("⚙️ Process Files", variant="primary")
            status_box  = gr.Textbox(label="Status", lines=7, interactive=False)

            gr.Markdown("### 🔍 Query Source")
            source_dropdown = gr.Dropdown(
                label="Select which file(s) to query",
                choices=[],
                value=None,
                interactive=True,
            )
            switch_status = gr.Textbox(label="Active source", lines=1, interactive=False)

        with gr.Column(scale=2):
            question   = gr.Textbox(
                label="Your question",
                placeholder="Ask anything across your documents...",
                lines=2,
            )
            with gr.Row():
                submit_btn = gr.Button("Ask", variant="primary")
                clear_btn  = gr.Button("Clear")
            answer_box = gr.Textbox(label="Answer", lines=15, interactive=False)

    process_btn.click(fn=process_files,      inputs=file_input,      outputs=[status_box, source_dropdown])
    source_dropdown.change(fn=switch_source, inputs=source_dropdown, outputs=switch_status)
    submit_btn.click(fn=ask_question,        inputs=question,        outputs=answer_box)
    question.submit(fn=ask_question,         inputs=question,        outputs=answer_box)
    clear_btn.click(lambda: ("", ""),                                outputs=[question, answer_box])


if __name__ == "__main__":
    app.launch()