// scripts.js
let context = "";
let controller = null;

document.getElementById('userInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

window.onload = () => addMessage("Hello! How can I help you?", 'bot');

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message) return;
    
    input.value = '';
    addMessage(message, 'user');
    
    controller = new AbortController();
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ context, question: message }),
            signal: controller.signal
        });
        
        const data = await response.json();
        context = data.context;
        addMessage(data.response, 'bot');
    } catch (error) {
        handleError(error);
    }
}

function handleError(error) {
    const message = error.name === 'AbortError' 
        ? 'Chat stopped' 
        : 'Error processing request';
    addMessage(message, 'system');
}

function stopChat() {
    if (controller) controller.abort();
    context = "";
    document.getElementById('conversation').innerHTML = '';
    addMessage('Chat reset. Start new conversation.', 'system');
}

function addMessage(text, sender) {
    const conversation = document.getElementById('conversation');
    const messageDiv = document.createElement('div');
    messageDiv.className = `${sender}-message`;
    messageDiv.innerHTML = `<strong>${sender}:</strong> ${text}`;
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}