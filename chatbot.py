# chatbot.py (core logic)
from flask import Blueprint, request, jsonify
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM
from document_processor import vector_store

chat_bp = Blueprint('chat', __name__)

# Initialize components once
model = OllamaLLM(model="llama3.2")

PROMPT_TEMPLATE = """
Use the following context to answer the question:
{context}

Conversation History:
{history}

Question: {question}
Answer:"""

prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
chain = prompt | model

@chat_bp.route('/chat', methods=['POST'])
def handle_chat():
    """Main chat endpoint with RAG integration"""
    data = request.json
    user_input = data.get('question', '')
    context = data.get('context', '')
    
    # Retrieve relevant documents
    docs = vector_store.similarity_search(user_input, k=3) if vector_store else []
    rag_context = "\n".join([d.page_content for d in docs])
    
    # Generate response
    response = chain.invoke({
        "context": rag_context,
        "history": context,
        "question": user_input
    })
    
    # Update conversation context
    new_context = f"{context}\nUser: {user_input}\nAI: {response}"
    return jsonify({"response": str(response), "context": new_context})