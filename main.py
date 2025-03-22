# main.py (entry point)
from flask import Flask, render_template, jsonify
from chatbot import chat_bp
from document_processor import initialize_rag
import os

app = Flask(__name__)

# Initialize RAG system with sample document
initialize_rag('data/document.txt')

# Register blueprint for chat routes
app.register_blueprint(chat_bp)

@app.route('/data-files')
def list_data_files():
    """List all files in the data folder"""
    data_folder = 'data'
    files = os.listdir(data_folder)
    return jsonify(files)

@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)