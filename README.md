# 📄 Offline RAG Chatbot — FAISS + Ollama + Mistral

A fully offline Retrieval-Augmented Generation (RAG) chatbot that lets you upload multiple documents and ask questions across all of them. Supports PDF, DOCX, XLSX, and PPTX files. No internet connection or API keys required after setup.

---

## 🧠 How It Works

1. Upload one or more documents → they get split into chunks and embedded using `nomic-embed-text`
2. Chunks are stored in a **FAISS** vector store (in-memory, fast lookup)
3. When you ask a question, the most relevant chunks are retrieved
4. **Mistral** (via Ollama) generates an answer using only those chunks
5. The answer includes **page / slide / sheet references** from the source document

---

## 🖥️ Requirements

- Python 3.9+
- [Ollama](https://ollama.com/) installed and running
- The following Ollama models pulled (one-time setup):

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

---

## ⚙️ Installation

### 1. Clone or download the project

```bash
git clone https://github.com/your-username/local-rag-chatbot.git
cd local-rag-chatbot
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv rag_env
rag_env\Scripts\activate

# macOS / Linux
python -m venv rag_env
source rag_env/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Pull Ollama models (one-time)

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

---

## 🚀 Running the App

Make sure Ollama is running first:

```bash
ollama serve
```

> If you see `"address already in use"` — Ollama is already running. That's fine.

Then start the app:

```bash
python localrag.py
```

Open your browser and go to:

```
http://127.0.0.1:7860
```

---

## 🧪 Usage

1. **Upload files** using the file picker — supports PDF, DOCX, XLSX, PPTX (multiple at once)
2. Click **⚙️ Process Files** and wait for the ✅ status message
3. Use the **Query Source dropdown** to select:
   - `🗂 All files (combined)` — search across everything
   - A specific file — search only that document
4. **Type your question** and press Enter or click **Ask**
5. The answer appears with **📄 source references** showing exact page, slide, or sheet

---

## 📁 Project Structure

```
local-rag-chatbot/
│
├── localrag.py          # Main application file
├── requirements.txt     # Python dependencies
├── README.md            # This file
└── rag_env/             # Virtual environment (not committed to git)
```

---

## ⚡ Performance Notes (CPU)

| Step | Expected Time |
|---|---|
| First model load | 10–30s (one-time per session) |
| PDF processing (10 pages) | 5–15s |
| PPTX processing (50 slides) | 15–30s |
| Question answering | 30–90s on CPU |

> Performance depends on your CPU and available RAM. A machine with 16GB RAM and a modern CPU will perform best.

---

## 📄 Supported File Types

| Format | Extension | Source Reference |
|---|---|---|
| PDF | `.pdf` | Page number |
| Word Document | `.doc`, `.docx` | Page number |
| Excel Spreadsheet | `.xls`, `.xlsx` | Sheet/Row number |
| PowerPoint | `.ppt`, `.pptx` | Slide number |

---

## 🔧 Tech Stack

| Component | Tool |
|---|---|
| LLM | Mistral 7B via Ollama |
| Embeddings | nomic-embed-text via Ollama |
| Vector Store | FAISS (in-memory) |
| Document Loaders | LangChain (PyPDF, Docx2txt, Unstructured) |
| Web UI | Gradio |
| Orchestration | LangChain |

---

## 🔒 Privacy

Everything runs **100% locally** on your machine. No data is sent to any external server or API. Your documents stay private.

---

## 🛠️ Troubleshooting

**App crashes on startup**
- Make sure Ollama is installed and running: `ollama serve`
- Confirm both models are pulled: `ollama list`

**"Not found in documents" for answers you expect**
- Try rephrasing your question more specifically
- Switch to the specific file in the dropdown instead of combined mode

**PPTX or DOCX not loading**
- Make sure you installed all dependencies: `pip install -r requirements.txt`
- Try re-saving the file in its native format

**Processing is slow**
- Normal on CPU — Mistral 7B is a large model
- Larger files with more chunks take longer to embed on first upload

**Port already in use**
- Another Gradio instance is running. Stop it or change the port:
  ```python
  app.launch(server_port=7861)
  ```

---

## 📦 Freeing Up Space

To remove unused Ollama models:

```bash
ollama list              # see all downloaded models
ollama rm <model-name>   # delete a model
```

Only `mistral` and `nomic-embed-text` are required for this app.