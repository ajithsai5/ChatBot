# document_processor.py (RAG operations)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

vector_store = None

def initialize_rag(file_path: str):
    """Initialize RAG system with a document file"""
    global vector_store
    
    # Read the document from the file
    with open(file_path, 'r') as f:
        document = f.read()
    
    # Process document into chunks
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    ).split_text(document)
    
    # Initialize vector store with document chunks
    embeddings = OllamaEmbeddings(model="llama3.2")
    vector_store = Chroma.from_texts(
        texts=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )