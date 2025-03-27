// scripts.js
let context = "";
let controller = null;

document.getElementById('userInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

window.onload = () => addMessage("Hello! How can I help you?", 'ChatBot');

async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    if (!message) return;
    
    input.value = '';
    addMessage(message, 'User');
    
    // Add loading indicator
    const loading = document.createElement('div');
    loading.className = 'loading-message';
    loading.innerHTML = `
        <img class="avatar" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzJlN2QzMiI+PHBhdGggZD0iTTEyLDJBMTAsMTAgMCAwLDAgMiwxMkExMCwxMCAwIDAsMCAxMiwyMiAxMCwxMCAwIDAsMCAyMiwxMiAxMCwxMCAwIDAsMCAxMiwyTTEyLDRBOCw4IDAgMCwxIDIwLDEyQTgsOCAwIDAsMSAxMiwyMCA4LDggMCAwLDEgNCwxMiA4LDggMCAwLDEgMTIsNE0xNiwxNkExLDEgMCAwLDAgMTUsMTdBMSwxIDAgMCwwIDE2LDE4IDEgMSAwIDAsMCAxNywxNyAxLDEgMCAwLDAgMTYsMTZNMTMsMTFWN0gxMVYxMkgxM1YxNUgxMVYxN0gxM1YxNkgxNVYxNEgxM1YxMU0xMCwxMUEyLDIgMCAwLDAgOCw5QTIsMiAwIDAsMCA2LDExQTIsMiAwIDAsMCA4LDEzIDIsMiAwIDAsMCAxMCwxMSIvPjwvc3ZnPg==">
        <div class="loading-dots">
            <div></div><div></div><div></div>
        </div>
    `;
    const loadingIndicator = document.getElementById('loading-indicator');
    loadingIndicator.style.display = 'block';
    loadingIndicator.appendChild(loading);
    
    controller = new AbortController();
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ context, question: message }),
            signal: controller.signal
        });
        
        loadingIndicator.style.display = 'none';
        loadingIndicator.innerHTML = '';
        const data = await response.json();
        context = data.context;
        addMessage(data.response, 'ChatBot');
    } catch (error) {
        loadingIndicator.style.display = 'none';
        loadingIndicator.innerHTML = '';
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
    addMessage('Chat reset. Start new conversation.', 'system'); // Moved this line above clearing the conversation
    context = "";
    document.getElementById('conversation').innerHTML = '';
    
    fetch('/exit', { method: 'POST' })
        .then(() => window.location.href = '/exit')
        .catch(error => handleError(error));
}

function addMessage(text, sender) {
    const conversation = document.getElementById('conversation');
    const messageDiv = document.createElement('div');
    messageDiv.className = sender === 'ChatBot' ? 'bot-message' : 'user-message';
    
    const avatar = sender === 'ChatBot' 
    ? 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzJlN2QzMiI+PHBhdGggZD0iTTIwIDRoLTRWMy41QzE2IDEyLjQzIDEyLjQzIDE2IDMuNSAxNkg0djRoNC4yNWwtLjg4IDRoMTMuNWwtLjg3LTRIMjB2LTRoLS41QzE5LjMzIDggMTYgNC42NyAxMiA0VjBIOHY0QzQgNC42Ny43IDggMCAxMnY0aDR2NGg0LjI1bC0uODggNEg0djJoMTZ2LTJoLTQuMzhsLS44Ny00SDI0di00aC00VjE2aDR2LTR6Ii8+PC9zdmc+' 
    : 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzM0OThkYiI+PHBhdGggZD0iTTEyIDRhNCA0IDAgMSAxIDAgOCA0IDQgMCAwIDEgMC04em0wIDEwYzQuNDIgMCA4IDEuNzkgOCA0djJINHYtMmMwLTIuMjEgMy41OC00IDgtNHoiLz48L3N2Zz4=';
    
    messageDiv.innerHTML = `
        <img class="avatar" src="${avatar}">
        <div class="message-content">${marked(text)}</div>
    `;
    
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
}