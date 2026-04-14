# ChatBot

A RAG-powered AI chatbot that runs entirely locally using Ollama. Ask questions and get context-aware answers based on your own knowledge documents — no cloud API keys required.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| AI/LLM | LangChain, Ollama (llama3.2) |
| Vector DB | ChromaDB |
| Frontend | HTML, CSS, JavaScript, marked.js |

## Prerequisites

- Python 3.x
- [Ollama](https://ollama.com) installed and running
- llama3.2 model pulled:
  ```bash
  ollama pull llama3.2
  ```

## Setup

```bash
pip install flask langchain langchain-community langchain-ollama chromadb
```

## Run

```bash
python main.py
```

Open http://localhost:5000 in your browser.

## How It Works

1. On startup, the app reads a knowledge document from `Knowledge/`, splits it into chunks, and stores embeddings in a local Chroma vector store
2. When you send a message, the app retrieves the 3 most relevant chunks via semantic search
3. The chunks + conversation history + your question are sent to the local Ollama llama3.2 model
4. The response is rendered as Markdown in the chat UI

## Project Structure

```
main.py                 # Flask app entry point, route registration, RAG init
chatbot.py              # /chat endpoint, LangChain prompt chain
document_processor.py   # Document chunking, embeddings, Chroma vector store
static/scripts.js       # Chat UI logic, message handling, Markdown rendering
static/styles.css       # Chat styling
templates/index.html    # Main chat page
templates/exit.html     # Server shutdown page
Knowledge/              # Source documents for RAG (markdown + PDFs)
```
