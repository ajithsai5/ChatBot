# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python main.py
```

Flask dev server starts at `http://localhost:5000`. Requires Ollama running locally with the `llama3.2` model pulled (`ollama pull llama3.2`).

## Installing Dependencies

No `requirements.txt` exists. Install manually:

```bash
pip install flask langchain langchain-community langchain-ollama chromadb
```

## Known Issue

`main.py:10` calls `initialize_rag('data/document.md')` but the `data/` directory was removed — documents now live in `Knowledge/`. The path must be updated to `Knowledge/document.md` (or a new document path) before the app will start without error.

## Architecture

This is a **RAG-powered Flask chatbot** using local LLM inference.

**Request flow:**
1. User submits a question via the browser chat UI (`static/scripts.js` → `POST /chat`)
2. `chatbot.py` retrieves the 3 most semantically similar document chunks from the Chroma vector store
3. Retrieved chunks + conversation history + the question are combined into a LangChain prompt
4. The prompt is sent to the local Ollama `llama3.2` model via `OllamaLLM`
5. The Markdown-formatted response and updated history context are returned as JSON
6. `scripts.js` renders the response using `marked` (loaded from CDN in `templates/index.html`)

**Key files:**

| File | Role |
|------|------|
| `main.py` | Flask app entry point; registers blueprint; calls `initialize_rag` on startup |
| `chatbot.py` | `/chat` POST endpoint; LangChain chain (`prompt | model`); RAG retrieval |
| `document_processor.py` | Chunks a document, creates Ollama embeddings, persists Chroma vector store to `./chroma_db/` |
| `static/scripts.js` | Chat UI — sends messages, manages `context` string across turns, renders Markdown, handles abort |
| `templates/index.html` | Single-page chat UI; loads `marked` from CDN |

**State management:** Conversation history is maintained entirely on the client as a plain string (`context`) passed back and forth in every `/chat` request body. There is no server-side session state.

**Vector store:** Chroma persists to `./chroma_db/` on first run. Re-running `initialize_rag` with the same document rebuilds and overwrites it.

**Knowledge base:** Source documents for RAG live in `Knowledge/` (PDFs and `document.md`). Only the file passed to `initialize_rag` is indexed — currently one document at a time.

## Design Artifacts

`design-artifacts/` contains product and UX planning documents (Product Brief, Trigger Map, UX Scenarios, Design System, Development spec) generated during the project's design phase. These are reference material, not executed by code.
