/* ─────────────────────────────────────────────────────────────
   Frontend logic — preserves backend contract.
   Endpoints (no changes):
     POST /uhccp-internal-chatbot/chat?msg=<text>
     POST /uhccp-internal-chatbot/chat/stream
   Demo mode is enabled for the preview (window.__DEMO__ = true)
   so the page works without the Flask backend.
   ───────────────────────────────────────────────────────────── */

const CHAT_ROUTE        = '/uhccp-internal-chatbot/chat';
const CHAT_STREAM_ROUTE = '/uhccp-internal-chatbot/chat/stream';
const PROGRESS_ICONS    = ['⚙️','🧠','📊','🧩','📄','✅'];

window.__DEMO__ = false; // production: real Flask backend

let conversationHistory = [];
let progressIconIndex = 0;
let controller = null;

const $ = (id) => document.getElementById(id);
const conv   = $('conversation');
const input  = $('userInput');
const sendBtn= $('sendBtn');
const form   = $('chat-form');
const empty  = $('emptyState');

/* ── Theme ─────────────────────────────────────── */
const storedTheme = localStorage.getItem('isaac-theme');
if (storedTheme) document.documentElement.setAttribute('data-theme', storedTheme);
$('themeToggle').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = (cur === 'dark') ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('isaac-theme', next);
});

/* ── Sidebar toggle (mobile) ───────────────────── */
$('sidebarToggle').addEventListener('click', () => $('app').classList.toggle('sidebar-open'));

/* ── Composer ──────────────────────────────────── */
function autosize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 220) + 'px';
}
input.addEventListener('input', () => {
  autosize();
  sendBtn.disabled = !input.value.trim();
});
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (input.value.trim()) sendMessage();
  }
});
form.addEventListener('submit', (e) => { e.preventDefault(); if (input.value.trim()) sendMessage(); });

/* Prompt cards + quick chips + tool buttons ───── */
document.querySelectorAll('[data-prompt]').forEach(el => {
  el.addEventListener('click', () => {
    input.value = el.dataset.prompt;
    autosize();
    sendBtn.disabled = false;
    input.focus();
  });
});

$('newChatBtn').addEventListener('click', () => {
  conversationHistory = [];
  conv.innerHTML = '';
  if (empty.parentNode) {
    conv.appendChild(empty);
  } else {
    conv.appendChild(empty);
  }
  empty.style.display = 'flex';
  input.focus();
});

/* ── Message rendering ─────────────────────────── */
function nowTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function escapeHtml(s) {
  return (s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function renderMarkdown(text) {
  try {
    if (window.marked && window.DOMPurify) {
      const html = window.marked.parse(text || '');
      return window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
    }
  } catch (e) { console.error(e); }
  return `<p>${escapeHtml(text)}</p>`;
}

function hideEmpty() { if (empty) empty.style.display = 'none'; }

function addMessage(text, sender, options = {}) {
  hideEmpty();
  const normalizedSender = (sender || '').toLowerCase();
  const isUser = normalizedSender === 'user';
  const isSystem = normalizedSender === 'system';

  const wrap = document.createElement('div');
  wrap.className = `msg ${isUser ? 'user' : isSystem ? 'system' : 'bot'}`;

  const avatarLabel = isUser ? 'A' : 'i';
  wrap.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">${avatarLabel}</div>
    <div class="msg-body">
      ${isSystem ? '' : `<div class="msg-meta">${isUser ? 'You' : 'Isaac'} · ${nowTime()}</div>`}
      <div class="bubble"></div>
    </div>
  `;
  const bubble = wrap.querySelector('.bubble');
  if (isUser) {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdown(text);
  }
  conv.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addThinking() {
  hideEmpty();
  const wrap = document.createElement('div');
  wrap.className = 'msg bot thinking-msg';
  wrap.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">i</div>
    <div class="msg-body">
      <div class="msg-meta">Isaac · thinking…</div>
      <div class="thinking" aria-label="Thinking"><span></span><span></span><span></span></div>
    </div>
  `;
  conv.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addProgressStep(text) {
  hideEmpty();
  const wrap = document.createElement('div');
  wrap.className = 'msg bot progress-row';
  wrap.style.gap = '14px';
  const icon = PROGRESS_ICONS[progressIconIndex++ % PROGRESS_ICONS.length];
  wrap.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">i</div>
    <div class="msg-body">
      <div class="progress-step"><span class="icon">${icon}</span><span>${escapeHtml(text)}</span></div>
    </div>
  `;
  conv.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addLinkStatus(title, items) {
  // appends a link-status card to the last bot bubble
  hideEmpty();
  const lastBot = [...conv.querySelectorAll('.msg.bot .bubble')].pop();
  if (!lastBot) return;
  const card = document.createElement('div');
  card.className = 'link-status';
  card.innerHTML = `
    <div class="link-status-head">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 1 0-7.07-7.07L11 5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 1 0 7.07 7.07L13 19"/></svg>
      ${escapeHtml(title)}
    </div>
    <ul class="link-status-list">
      ${items.map(it => `
        <li>
          <a href="${escapeHtml(it.url)}" target="_blank" rel="noopener">${escapeHtml(it.url)}</a>
          <span class="link-pill ${it.kind}">${it.label}</span>
        </li>
      `).join('')}
    </ul>
  `;
  lastBot.appendChild(card);
  scrollToBottom();
}

function scrollToBottom() {
  const wrap = $('convWrap');
  wrap.scrollTop = wrap.scrollHeight;
}

/* ── PPT intent detection ──────────────────────── */
function isPptGenerationIntent(message) {
  const t = (message || '').toLowerCase();
  const wantsPpt = /(ppt|pptx|power\s?point|slides|deck)/i.test(t);
  const wantsAction = /(generate|create|build|make|prepare|produce|share)/i.test(t);
  const weeklyHint = /(weekly|week)/i.test(t);
  return wantsPpt && (wantsAction || weeklyHint);
}

/* ── Network ───────────────────────────────────── */
async function sendMessage() {
  const message = input.value.trim();
  if (!message) return;

  input.value = '';
  autosize();
  sendBtn.disabled = true;

  addMessage(message, 'user');
  const thinking = addThinking();
  controller = new AbortController();

  try {
    if (window.__DEMO__) {
      await demoRespond(message, thinking);
      return;
    }

    if (isPptGenerationIntent(message)) {
      await sendStreamingMessage(message, thinking);
      return;
    }

    const qp = new URLSearchParams({ msg: message });
    const res = await fetch(`${CHAT_ROUTE}?${qp.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history: conversationHistory }),
      signal: controller.signal
    });
    const data = await res.json();
    thinking.remove();
    addMessage(data.response || '(no response)', 'Chatbot');
    if (data.urlInfo && Array.isArray(data.urlInfo) && data.urlInfo.length) {
      addLinkStatus('Link status', data.urlInfo);
    }
    conversationHistory.push({ role: 'user', content: message });
    conversationHistory.push({ role: 'assistant', content: data.response || '' });
  } catch (err) {
    console.error(err);
    if (thinking.parentNode) thinking.remove();
    addMessage(err.name === 'AbortError' ? 'Chat stopped.' : 'Error processing request.', 'system');
  }
}

async function sendStreamingMessage(message, thinkingMessage) {
  const res = await fetch(CHAT_STREAM_ROUTE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history: conversationHistory }),
    signal: controller.signal
  });
  if (!res.ok || !res.body) throw new Error('Stream request failed');

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const handle = (eventText) => {
    const lines = eventText.split('\n').map(l => l.trim()).filter(l => l.startsWith('data:'));
    if (!lines.length) return;
    const raw = lines.map(l => l.replace(/^data:\s*/, '')).join('');
    let payload; try { payload = JSON.parse(raw); } catch { return; }
    if (thinkingMessage && thinkingMessage.parentNode) thinkingMessage.remove();
    if (payload.type === 'progress') addProgressStep(payload.message || 'Working…');
    else if (payload.type === 'final') addMessage(payload.message || 'Done.', 'Chatbot');
    else if (payload.type === 'error') addMessage(payload.message || 'Error', 'system');
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const p of parts) handle(p);
  }
  if (buffer.trim()) handle(buffer);
}

/* ── Demo mode: realistic mocked responses ─────── */
async function demoRespond(message, thinking) {
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  if (isPptGenerationIntent(message)) {
    if (thinking.parentNode) thinking.remove();
    const steps = [
      'Gathering Rally sprint data for the current week',
      'Pulling ServiceNow incident counts (P1/P2/P3)',
      'Fetching Dynatrace problem signals and SLO drift',
      'Summarizing Splunk error patterns by service',
      'Composing executive summary and risk register',
      'Rendering PowerPoint slides',
      'Status deck ready'
    ];
    for (let i = 0; i < steps.length; i++) {
      await sleep(700 + Math.random()*350);
      addProgressStep(steps[i]);
    }
    await sleep(500);
    addMessage(
`**Weekly status deck generated.**

The deck (\`UHCCP-DevOps-Status-${new Date().toISOString().slice(0,10)}.pptx\`) is ready for download in the shared drive.

| Section | Highlights |
| --- | --- |
| Sprint progress | 41 stories completed · 7 carried over |
| Incidents | 0 P1 · 3 P2 (all mitigated) |
| Reliability | 99.94% availability · 2 SLO burn alerts |
| Performance | CrUX LCP 2.1s (p75), trending down |

Anything you'd like me to revise before sharing?`, 'Chatbot');
    return;
  }

  await sleep(700);
  if (thinking.parentNode) thinking.remove();

  const lower = message.toLowerCase();
  if (/dynatrace/.test(lower)) {
    addMessage(
`**Open Dynatrace problems** — 3 active, ordered by impact.

1. **High response time** — *Member Portal · /eligibility* — opened 14m ago
   - Affected: ~6.2% of sessions in US-East
   - Root cause candidate: \`eligibility-svc\` DB pool exhaustion
2. **Failure rate increase** — *Claims API · /v2/submit* — opened 1h 22m ago
   - Failure rate 3.4% (baseline 0.6%)
3. **Slow disk write** — *batch-worker-04* — opened 3h ago (degraded only)

> Recommend acknowledging #1 — pattern matches incident **INC0094112** from last Tuesday.`, 'Chatbot');
    return;
  }

  if (/rally|eagle|user stor/.test(lower)) {
    addMessage(
`**Team Eagle — current sprint (Sprint 142, ends Fri).**

- **US-23104** — Provider directory v3 search ranking — *In Progress*
- **US-23117** — Member SSO token rotation — *In Review*
- **US-23122** — CrUX integration for nightly perf job — *Defined*
- **US-23130** — Splunk dashboard for claims throughput — *In Progress*
- **DE-1879** — Fix duplicate event emission on resubmit — *Blocked* (waiting on platform team)

3 of 5 items are at risk if the SSO change slips past Wednesday.`, 'Chatbot');
    return;
  }

  if (/link.*valid|web link|url.*check/.test(lower)) {
    addMessage(
`Ran the **web link validator** against the **provider directory** sitemap (84 URLs).

- 76 healthy · 4 redirects · 2 broken · 2 require auth

The broken links are below — both look like stale CMS references.`, 'Chatbot');
    addLinkStatus('Link status — 84 URLs scanned', [
      { url: 'https://uhccp.example.com/providers/find-a-doctor', kind: 'ok',   label: '✅ 200 OK' },
      { url: 'https://uhccp.example.com/providers/specialists',  kind: 'ok',   label: '✅ 200 OK' },
      { url: 'https://uhccp.example.com/legacy/dr-search',       kind: 'warn', label: '⚠️ 301 redirect' },
      { url: 'https://uhccp.example.com/providers/coverage-old', kind: 'bad',  label: '❌ 404 not found' },
      { url: 'https://uhccp.example.com/admin/directory-export', kind: 'lock', label: '🔒 401 auth required' },
    ]);
    return;
  }

  if (/servicenow|incident|p1|p2/.test(lower)) {
    addMessage(
`**Open ServiceNow priority incidents.**

| Number | Priority | Title | Assigned | Age |
| --- | --- | --- | --- | --- |
| INC0094112 | P2 | Eligibility lookup latency spike | Eagle | 4h |
| INC0094098 | P2 | Claims submit 5xx | Falcon | 1d |
| INC0094051 | P3 | Pharmacy formulary cache miss | Heron | 2d |

No active P1s. The two P2s have linked Dynatrace problems — want me to pull those signals?`, 'Chatbot');
    return;
  }

  addMessage(
`I can help with that. I have access to:

- **Rally** — user stories, defects, sprint progress
- **ServiceNow** — incidents, problems, changes
- **Splunk** & **Dynatrace** — logs, problems, SLOs
- **CrUX** — real-user performance metrics
- **PPT generation** — weekly status decks

Could you tell me a bit more about what you'd like to see?`, 'Chatbot');
}
