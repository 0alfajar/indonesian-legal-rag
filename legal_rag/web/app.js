// Elements
const form = document.querySelector('#query-form');
const questionInput = document.querySelector('#question');
const submitBtn = document.querySelector('#submit-btn');
const documentSelect = document.querySelector('#document');
const modeSelect = document.querySelector('#mode');
const chatScroller = document.querySelector('#chat-scroller');
const welcomeView = document.querySelector('#welcome-view');
const messagesContainer = document.querySelector('#messages-container');
const thinkingIndicator = document.querySelector('#thinking-indicator');
const thinkingLabel = document.querySelector('#thinking-label');
const headerScopeLabel = document.querySelector('#header-scope-label');
const corpusStatusText = document.querySelector('#corpus-status-text');
const sidebar = document.querySelector('#sidebar');
const sidebarToggle = document.querySelector('#sidebar-toggle');
const sidebarCloseBtn = document.querySelector('#sidebar-close-btn');
const sidebarBackdrop = document.querySelector('#sidebar-backdrop');
const newChatBtn = document.querySelector('#new-chat-btn');
const newChatPill = document.querySelector('#new-chat-pill');

function createElement(tag, className, textContent) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (textContent !== undefined) el.textContent = textContent;
  return el;
}

// Auto-expand Textarea & Handle Input State
function updateInputState() {
  questionInput.style.height = 'auto';
  questionInput.style.height = Math.min(questionInput.scrollHeight, 180) + 'px';
  submitBtn.disabled = !questionInput.value.trim();
}

questionInput.addEventListener('input', updateInputState);

questionInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!submitBtn.disabled) {
      form.requestSubmit();
    }
  }
});

// Sidebar Toggle Handlers
function toggleSidebar(open) {
  if (!sidebar) return;
  if (open === undefined) {
    sidebar.classList.toggle('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.toggle('active');
  } else if (open) {
    sidebar.classList.add('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('active');
  } else {
    sidebar.classList.remove('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
  }
}

if (sidebarToggle) sidebarToggle.addEventListener('click', () => toggleSidebar(true));
if (sidebarCloseBtn) sidebarCloseBtn.addEventListener('click', () => toggleSidebar(false));
if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', () => toggleSidebar(false));

// Document Scope Selector Change
documentSelect.addEventListener('change', () => {
  const selectedText = documentSelect.options[documentSelect.selectedIndex].text;
  if (headerScopeLabel) headerScopeLabel.textContent = selectedText;
});

// Load System Health & Corpus Status
async function loadHealth() {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) throw new Error('Corpus API offline');
    const health = await response.json();
    if (corpusStatusText) {
      corpusStatusText.textContent = `${health.chunks.toLocaleString()} passages`;
    }

    // Populate document selector
    for (const doc of health.documents) {
      const option = createElement('option', '', doc);
      option.value = doc;
      documentSelect.append(option);
    }
  } catch (error) {
    console.error('Failed to load health data:', error);
    if (corpusStatusText) {
      corpusStatusText.textContent = 'Corpus offline';
      corpusStatusText.style.color = '#f87171';
    }
    // Show error banner in UI
    const errorBanner = createElement('div', 'error-banner');
    errorBanner.textContent = 'Failed to load document corpus. Some features may not work correctly.';
    errorBanner.style.margin = '10px';
    errorBanner.style.position = 'fixed';
    errorBanner.style.top = '10px';
    errorBanner.style.left = '50%';
    errorBanner.style.transform = 'translateX(-50%)';
    errorBanner.style.zIndex = '9999';
    document.body.prepend(errorBanner);
    setTimeout(() => errorBanner.remove(), 5000);
  }
}

// Reset Conversation (New Chat)
function resetChat() {
  messagesContainer.innerHTML = '';
  messagesContainer.hidden = true;
  welcomeView.hidden = false;
  thinkingIndicator.hidden = true;
  questionInput.value = '';
  documentSelect.value = ''; // Reset to "All Regulations"
  if (headerScopeLabel) headerScopeLabel.textContent = 'All Regulations';
  updateInputState();
  questionInput.focus();
  toggleSidebar(false);
}

if (newChatBtn) newChatBtn.addEventListener('click', resetChat);
if (newChatPill) newChatPill.addEventListener('click', resetChat);

// Handle Preset Question Clicks
document.querySelectorAll('[data-question]').forEach(btn => {
  btn.addEventListener('click', () => {
    questionInput.value = btn.dataset.question;
    updateInputState();
    form.requestSubmit();
    toggleSidebar(false);
  });
});

// Scroll Smoothly to Bottom
function scrollToBottom() {
  chatScroller.scrollTo({
    top: chatScroller.scrollHeight,
    behavior: 'smooth'
  });
}

// Append User Bubble
function appendUserMessage(text) {
  welcomeView.hidden = true;
  messagesContainer.hidden = false;

  const row = createElement('div', 'message-row user');
  const bubble = createElement('div', 'user-bubble', text);
  row.append(bubble);
  messagesContainer.append(row);
  scrollToBottom();
}

// Parse Text with Citation Pills
function formatStatementWithCitations(statement, onCitationClick) {
  const container = createElement('p', 'statement-paragraph');
  const text = statement.text;
  const citationRegex = /\[(S\d+)\]/g;

  let lastIndex = 0;
  let match;

  while ((match = citationRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      container.append(document.createTextNode(text.substring(lastIndex, match.index)));
    }

    const sourceId = match[1];
    const badge = createElement('button', 'citation-chip', `[${sourceId}]`);
    badge.type = 'button';
    badge.title = `View source ${sourceId}`;
    badge.addEventListener('click', (e) => {
      e.preventDefault();
      onCitationClick(sourceId);
    });
    container.append(badge);

    lastIndex = citationRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    container.append(document.createTextNode(text.substring(lastIndex)));
  }

  if (statement.source_ids && statement.source_ids.length > 0) {
    const inlineCitations = new Set(Array.from(text.matchAll(citationRegex), m => m[1]));
    const addedCitations = new Set();
    for (const sid of statement.source_ids) {
      if (!inlineCitations.has(sid) && !addedCitations.has(sid)) {
        const badge = createElement('button', 'citation-chip', `[${sid}]`);
        badge.type = 'button';
        badge.title = `View source ${sid}`;
        badge.addEventListener('click', (e) => {
          e.preventDefault();
          onCitationClick(sid);
        });
        container.append(document.createTextNode(' '));
        container.append(badge);
        addedCitations.add(sid);
      }
    }
  }

  return container;
}

// Create Source Card
function createSourceCard(source, label) {
  const card = createElement('div', 'source-card');
  const sid = source.source_id || label;
  card.id = `source-${sid}`;

  const header = createElement('div', 'source-card-header');
  const badge = createElement('span', 'source-id-badge', `[${sid}]`);
  header.append(badge);

  const page = source.page_start || 1;
  const pdfLink = createElement('a', 'source-pdf-link');
  pdfLink.href = `/sources/${encodeURIComponent(source.doc_id)}#page=${page}`;
  pdfLink.target = '_blank';
  pdfLink.rel = 'noopener noreferrer';
  pdfLink.innerHTML = `PDF page ${page} ↗`;
  header.append(pdfLink);
  card.append(header);

  const title = createElement('div', 'source-provision-title',
    `${source.doc_id} · Pasal ${source.pasal}${source.ayat ? ` ayat (${source.ayat})` : ''}`
  );
  card.append(title);

  const textEl = createElement('div', 'source-text', source.text);
  card.append(textEl);

  return card;
}

// Append Assistant Message
function appendAssistantMessage(data) {
  const row = createElement('div', 'message-row assistant');
  const body = createElement('div', 'assistant-body');

  const sources = data.answer ? data.sources : data.results.map(r => r.chunk);

  // Evidence Accordion
  let evidenceSection = null;
  if (sources && sources.length > 0) {
    evidenceSection = createElement('div', 'evidence-section');
    const evHeader = createElement('div', 'evidence-header');
    evHeader.innerHTML = `
      <div class="evidence-title">
        <span>Sources</span>
        <span class="evidence-count-badge">${sources.length}</span>
      </div>
      <div class="evidence-chevron">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
    `;

    const evList = createElement('div', 'evidence-list');
    sources.forEach((s, idx) => {
      evList.append(createSourceCard(s, s.source_id || `S${idx + 1}`));
    });

    evHeader.addEventListener('click', () => {
      evidenceSection.classList.toggle('open');
    });

    evidenceSection.append(evHeader);
    evidenceSection.append(evList);
  }

  const handleCitationClick = (sourceId) => {
    if (evidenceSection) {
      evidenceSection.classList.add('open');
      const targetCard = evidenceSection.querySelector(`#source-${sourceId}`);
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        targetCard.classList.remove('highlight');
        void targetCard.offsetWidth;
        targetCard.classList.add('highlight');
        setTimeout(() => targetCard.classList.remove('highlight'), 2000);
      }
    }
  };

  // Render Answer Statements
  if (data.answer && data.answer.statements && data.answer.statements.length > 0) {
    data.answer.statements.forEach(stmt => {
      body.append(formatStatementWithCitations(stmt, handleCitationClick));
    });

    if (data.answer.limitations) {
      const limBox = createElement('div', 'limitations-box');
      limBox.textContent = data.answer.limitations;
      body.append(limBox);
    }
  } else if (data.answer && data.answer.status === 'insufficient_evidence') {
    const p = createElement('p', '', data.answer.limitations || 'No relevant provisions found in the current corpus to answer this question.');
    body.append(p);
  } else if (!data.answer && data.results && data.results.length > 0) {
    const p = createElement('p', '', `Retrieved ${data.results.length} relevant provisions from the selected collection:`);
    body.append(p);
    if (evidenceSection) {
      evidenceSection.classList.add('open');
    }
  }

  if (data.generation_error) {
    const errBox = createElement('div', 'error-banner', data.generation_error);
    body.append(errBox);
  }

  row.append(body);
  if (evidenceSection) {
    row.append(evidenceSection);
  }
  messagesContainer.append(row);
  scrollToBottom();
}

// Handle Form Submission
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  const documentScope = documentSelect.value || null;
  const mode = modeSelect.value || 'answer';

  appendUserMessage(question);
  questionInput.value = '';
  updateInputState();
  questionInput.disabled = true;
  submitBtn.disabled = true;

  if (thinkingLabel) {
    thinkingLabel.textContent = mode === 'answer' ? 'Searching regulations & reasoning...' : 'Searching regulations...';
  }
  thinkingIndicator.hidden = false;
  scrollToBottom();

  try {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, document: documentScope, mode }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Query failed');
    }

    thinkingIndicator.hidden = true;
    appendAssistantMessage(data);
  } catch (err) {
    thinkingIndicator.hidden = true;
    appendAssistantMessage({
      generation_error: err.message || 'Error communicating with Legal Atlas'
    });
  } finally {
    questionInput.disabled = false;
    updateInputState();
    questionInput.focus();
  }
});

// Init
loadHealth();
updateInputState();

