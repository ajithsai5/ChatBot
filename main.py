# main.py (entry point)
from flask import Flask, render_template
from chatbot import chat_bp
from document_processor import initialize_rag

app = Flask(__name__)

# Initialize RAG system with sample document
initialize_rag('data/document.txt')

# Register blueprint for chat routes
app.register_blueprint(chat_bp)

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)