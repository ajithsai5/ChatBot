/**
 * UHCCP Internal Chatbot — frontend interaction layer.
 *
 * Responsibilities:
 *  - Submit user messages to the streaming chat API.
 *  - Render markdown responses via marked.js + DOMPurify.
 *  - Animate progress indicators during response streaming.
 *  - Handle PPT generation, quick-links, and link-validator sidebar buttons.
 *
 * Not handled here:
 *  - Backend routing, AI inference, or data retrieval.
 *  - Authentication or session management.
 */

const CHAT_INPUT_ID = 'userInput';
const CHAT_FORM_ID = 'chat-form';
const CHAT_ROUTE = '/uhccp-internal-chatbot/chat';
const CHAT_STREAM_ROUTE = '/uhccp-internal-chatbot/chat/stream';

let context = "";
let controller = null;
const progressIcons = ['⚙️', '🧠', '📊', '🧩', '📄', '✅'];
let progressIconIndex = 0;

document.getElementById(CHAT_INPUT_ID).addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        sendMessage();
    }
});

document.getElementById(CHAT_FORM_ID).addEventListener('submit', function(event) {
    event.preventDefault();
    sendMessage();
});

window.onload = () => addMessage("Hello! How can I help you?", 'Chatbot');

function isPptGenerationIntent(message) {
    const text = (message || '').toLowerCase();
    const wantsPpt = /(ppt|pptx|power\s?point|slides|deck)/i.test(text);
    const wantsAction = /(generate|create|build|make|prepare|produce|share|gerate|gererate)/i.test(text);
    const weeklyHint = /(weekly|week|wekly|weeklt|wekli)/i.test(text);
    return wantsPpt && (wantsAction || weeklyHint);
}

function nextProgressIcon() {
    const icon = progressIcons[progressIconIndex % progressIcons.length];
    progressIconIndex += 1;
    return icon;
}

function addProgressMessage(text) {
    const messageDiv = addMessage(`${nextProgressIcon()} ${text}`, 'Chatbot');
    messageDiv.classList.add('progress-message');
    return messageDiv;
}

async function sendMessage() {
    const input = document.getElementById(CHAT_INPUT_ID);
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    addMessage(message, 'user');

    controller = new AbortController();

    const thinkingMessage = addMessage('', 'Chatbot');
    thinkingMessage.classList.add('thinking-message');
    ['.', '.', '.'].forEach((dot, index) => {
        const span = document.createElement('span');
        span.textContent = dot;
        span.style.animationDelay = `${index * 0.2}s`;
        thinkingMessage.appendChild(span);
    });

    try {
        if (isPptGenerationIntent(message)) {
            await sendStreamingMessage(message, thinkingMessage);
            return;
        }

        const queryParams = new URLSearchParams({
            context: context,
            msg: message
        });

        const requestBody = {
            history: []
        };

        const response = await fetch(`${CHAT_ROUTE}?${queryParams.toString()}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: controller.signal
        });

        const data = await response.json();
        context = data.context;

        thinkingMessage.remove();
        addMessage(data.response, 'Chatbot');
    } catch (error) {
        console.error('Error occurred:', error);
        handleError(error);
        thinkingMessage.remove();
    }
}

async function sendStreamingMessage(message, thinkingMessage) {
    const response = await fetch(CHAT_STREAM_ROUTE, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message,
            context,
            history: []
        }),
        signal: controller.signal
    });

    if (!response.ok || !response.body) {
        throw new Error('Streaming request failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    const processEvent = (eventText) => {
        const lines = eventText
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.startsWith('data:'));

        if (!lines.length) return;

        const raw = lines.map(line => line.replace(/^data:\s*/, '')).join('');
        let payload;
        try {
            payload = JSON.parse(raw);
        } catch (e) {
            console.error('Invalid stream payload:', raw, e);
            return;
        }

        if (payload.type === 'progress') {
            if (thinkingMessage && thinkingMessage.parentNode) thinkingMessage.remove();
            addProgressMessage(payload.message || 'Working on your PPT request...');
        } else if (payload.type === 'final') {
            if (thinkingMessage && thinkingMessage.parentNode) thinkingMessage.remove();
            addMessage(payload.message || 'Done.', 'Chatbot');
        } else if (payload.type === 'error') {
            if (thinkingMessage && thinkingMessage.parentNode) thinkingMessage.remove();
            addMessage(payload.message || 'Error processing request', 'system');
        }
    };

    while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
            processEvent(part);
        }
    }

    if (buffer.trim()) {
        processEvent(buffer);
    }
}

function handleError(error) {
    const message = error.name === 'AbortError' 
        ? 'Chat stopped' 
        : 'Error processing request';
    addMessage(message, 'system');
}

// Stop chat functionality removed

function addMessage(text, sender) {
    const conversation = document.getElementById('conversation');
    const messageDiv = document.createElement('div');
    const normalizedSender = (sender || '').toLowerCase();
    messageDiv.className = normalizedSender === 'chatbot' ? 'chatbot-message' : `${normalizedSender}-message`;
    messageDiv.classList.add('message-bubble');
    try {
        if (window.marked && typeof window.marked.parse === 'function' && window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
            const html = window.marked.parse(text);
            messageDiv.innerHTML = window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
        } else {
            messageDiv.textContent = text;
        }
    } catch (e) {
        messageDiv.textContent = text;
        console.error('Render error:', e);
    }
    conversation.appendChild(messageDiv);
    conversation.scrollTop = conversation.scrollHeight;
    return messageDiv; // Return the created message element
}