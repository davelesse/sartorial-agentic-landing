/**
 * ═══════════════════════════════════════════════════════════
 * SARTORIAL AGENTIC — Chatbot Widget
 * Vanilla JS · Zero dependencies · ~15kb
 *
 * Integration (une ligne sur le site client) :
 *   <script src="https://sartorial-agentic.ai/widget.js"
 *           data-sa-key="TENANT_PUBLIC_KEY"
 *           data-sa-theme="dark"
 *           data-sa-position="right"
 *           async></script>
 * ═══════════════════════════════════════════════════════════
 */
(function () {
  'use strict';

  // ══════════════════════════════════════
  // CONFIG
  // ══════════════════════════════════════
  const script = document.currentScript || [...document.scripts].find(s => s.src.includes('widget.js'));
  if (!script) return;

  const API_BASE = (script.dataset.saApi || 'https://sartorial-agentic.ai') + '/api/v1/chatbot';
  const PUBLIC_KEY = script.dataset.saKey;
  const THEME = script.dataset.saTheme || 'dark';       // dark | light
  const POSITION = script.dataset.saPosition || 'right'; // right | left
  const PRIMARY = script.dataset.saPrimary || '#C9A84C'; // accent color override
  const STORAGE_KEY = `sa_visitor_${PUBLIC_KEY}`;

  if (!PUBLIC_KEY) {
    console.error('[Sartorial Agentic] Missing data-sa-key attribute on script tag.');
    return;
  }

  // ══════════════════════════════════════
  // TRANSLATIONS
  // ══════════════════════════════════════
  const I18N = {
    fr: {
      placeholder: 'Écrivez votre message…',
      send: 'Envoyer',
      restart: 'Nouvelle conversation',
      poweredBy: 'Propulsé par Sartorial Agentic',
      typing: 'écrit…',
      ariaOpen: 'Ouvrir le chat',
      ariaClose: 'Fermer',
      errorGeneric: 'Une erreur est survenue. Merci de réessayer.',
    },
    en: {
      placeholder: 'Type your message…',
      send: 'Send',
      restart: 'New conversation',
      poweredBy: 'Powered by Sartorial Agentic',
      typing: 'is typing…',
      ariaOpen: 'Open chat',
      ariaClose: 'Close',
      errorGeneric: 'An error occurred. Please try again.',
    },
    de: {
      placeholder: 'Nachricht eingeben…',
      send: 'Senden',
      restart: 'Neues Gespräch',
      poweredBy: 'Bereitgestellt von Sartorial Agentic',
      typing: 'schreibt…',
      ariaOpen: 'Chat öffnen',
      ariaClose: 'Schließen',
      errorGeneric: 'Ein Fehler ist aufgetreten. Bitte erneut versuchen.',
    },
    nl: {
      placeholder: 'Typ uw bericht…',
      send: 'Verzenden',
      restart: 'Nieuw gesprek',
      poweredBy: 'Mogelijk gemaakt door Sartorial Agentic',
      typing: 'aan het typen…',
      ariaOpen: 'Chat openen',
      ariaClose: 'Sluiten',
      errorGeneric: 'Er is een fout opgetreden. Probeer het opnieuw.',
    },
    es: {
      placeholder: 'Escriba su mensaje…',
      send: 'Enviar',
      restart: 'Nueva conversación',
      poweredBy: 'Desarrollado por Sartorial Agentic',
      typing: 'está escribiendo…',
      ariaOpen: 'Abrir chat',
      ariaClose: 'Cerrar',
      errorGeneric: 'Ocurrió un error. Intente de nuevo.',
    },
  };

  // ══════════════════════════════════════
  // STATE
  // ══════════════════════════════════════
  let visitorId = localStorage.getItem(STORAGE_KEY) || null;
  let language = 'fr';
  let tenantName = '';
  let isOpen = false;
  let isStreaming = false;

  // ══════════════════════════════════════
  // DOM BUILDER
  // ══════════════════════════════════════

  function injectStyles() {
    const css = `
      .sa-widget-root {
        --sa-primary: ${PRIMARY};
        --sa-abyss: #030810;
        --sa-midnight: #060E1A;
        --sa-deep: #0A1628;
        --sa-gold: ${PRIMARY};
        --sa-gold-bright: #E2C46A;
        --sa-ivory: #F5F0EB;
        --sa-ivory-dim: #C8C0B5;
        --sa-border: rgba(201, 168, 76, 0.15);
        position: fixed; ${POSITION}: 24px; bottom: 24px;
        z-index: 2147483646;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 14px;
        line-height: 1.5;
        color: var(--sa-ivory);
      }

      /* Launcher button */
      .sa-launcher {
        width: 60px; height: 60px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--sa-gold), #A68A3E);
        border: none;
        cursor: pointer;
        box-shadow: 0 8px 30px rgba(0,0,0,0.35), 0 0 0 0 rgba(201,168,76,0.6);
        display: flex; align-items: center; justify-content: center;
        transition: transform .3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow .3s;
        animation: sa-pulse 2.5s ease-out infinite;
      }
      .sa-launcher:hover { transform: translateY(-3px) scale(1.05); }
      .sa-launcher svg { width: 26px; height: 26px; stroke: var(--sa-abyss); stroke-width: 2; fill: none; }
      @keyframes sa-pulse {
        0%   { box-shadow: 0 8px 30px rgba(0,0,0,0.35), 0 0 0 0 rgba(201,168,76,0.4); }
        70%  { box-shadow: 0 8px 30px rgba(0,0,0,0.35), 0 0 0 15px rgba(201,168,76,0); }
        100% { box-shadow: 0 8px 30px rgba(0,0,0,0.35), 0 0 0 0 rgba(201,168,76,0); }
      }

      /* Panel */
      .sa-panel {
        position: absolute; bottom: 80px; ${POSITION}: 0;
        width: 380px; height: 560px; max-height: 80vh;
        background: var(--sa-midnight);
        border: 1px solid var(--sa-border);
        border-radius: 16px;
        overflow: hidden;
        display: flex; flex-direction: column;
        box-shadow: 0 25px 60px rgba(0,0,0,0.5);
        transform: translateY(10px) scale(0.96);
        opacity: 0;
        pointer-events: none;
        transition: all .4s cubic-bezier(0.16, 1, 0.3, 1);
      }
      .sa-panel.open {
        transform: translateY(0) scale(1);
        opacity: 1;
        pointer-events: auto;
      }

      /* Header */
      .sa-header {
        padding: 18px 20px;
        background: linear-gradient(170deg, #4A0E2E 0%, var(--sa-midnight) 100%);
        border-bottom: 1px solid var(--sa-border);
        display: flex; justify-content: space-between; align-items: center;
      }
      .sa-title {
        font-family: "Cormorant Garamond", Georgia, serif;
        font-size: 18px;
        font-weight: 500;
        color: var(--sa-ivory);
        letter-spacing: 0.02em;
      }
      .sa-header-actions { display: flex; gap: 8px; }
      .sa-header-btn {
        background: transparent;
        border: 1px solid var(--sa-border);
        color: var(--sa-ivory-dim);
        padding: 6px 10px;
        font-size: 11px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        cursor: pointer;
        border-radius: 4px;
        transition: all .25s;
      }
      .sa-header-btn:hover { color: var(--sa-gold); border-color: var(--sa-gold); }
      .sa-header-close {
        background: transparent; border: none; color: var(--sa-ivory-dim);
        font-size: 22px; line-height: 1; cursor: pointer; padding: 4px;
      }
      .sa-header-close:hover { color: var(--sa-gold); }

      /* Messages */
      .sa-messages {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        display: flex; flex-direction: column; gap: 12px;
        scrollbar-width: thin;
        scrollbar-color: rgba(201,168,76,0.3) transparent;
      }
      .sa-messages::-webkit-scrollbar { width: 4px; }
      .sa-messages::-webkit-scrollbar-thumb { background: rgba(201,168,76,0.3); }

      .sa-msg {
        max-width: 85%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 14px;
        line-height: 1.55;
        animation: sa-msg-in .4s cubic-bezier(0.16, 1, 0.3, 1);
        word-wrap: break-word;
        white-space: pre-wrap;
      }
      .sa-msg-assistant {
        background: var(--sa-deep);
        border: 1px solid var(--sa-border);
        align-self: flex-start;
        border-bottom-left-radius: 4px;
      }
      .sa-msg-user {
        background: linear-gradient(135deg, var(--sa-gold), #A68A3E);
        color: var(--sa-abyss);
        align-self: flex-end;
        border-bottom-right-radius: 4px;
        font-weight: 500;
      }
      @keyframes sa-msg-in {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
      }

      /* Typing indicator */
      .sa-typing {
        display: flex; gap: 4px; padding: 14px;
        background: var(--sa-deep);
        border: 1px solid var(--sa-border);
        border-radius: 12px;
        align-self: flex-start;
        width: fit-content;
      }
      .sa-typing span {
        width: 6px; height: 6px; border-radius: 50%;
        background: var(--sa-gold);
        animation: sa-typing-dot 1.4s infinite;
      }
      .sa-typing span:nth-child(2) { animation-delay: 0.2s; }
      .sa-typing span:nth-child(3) { animation-delay: 0.4s; }
      @keyframes sa-typing-dot {
        0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
        30% { opacity: 1; transform: translateY(-4px); }
      }

      /* Input */
      .sa-input-row {
        padding: 12px;
        border-top: 1px solid var(--sa-border);
        display: flex; gap: 8px; align-items: flex-end;
      }
      .sa-input {
        flex: 1;
        background: var(--sa-deep);
        border: 1px solid var(--sa-border);
        color: var(--sa-ivory);
        padding: 10px 12px;
        font-family: inherit;
        font-size: 14px;
        border-radius: 8px;
        resize: none;
        max-height: 100px;
        min-height: 40px;
        outline: none;
        transition: border-color .25s;
      }
      .sa-input:focus { border-color: var(--sa-gold); }
      .sa-input::placeholder { color: rgba(200,192,181,0.4); }

      .sa-send-btn {
        background: var(--sa-gold);
        border: none;
        color: var(--sa-abyss);
        width: 40px; height: 40px;
        border-radius: 8px;
        cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        transition: all .25s;
        flex-shrink: 0;
      }
      .sa-send-btn:hover:not(:disabled) {
        background: var(--sa-gold-bright);
        transform: translateY(-1px);
      }
      .sa-send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .sa-send-btn svg { width: 18px; height: 18px; fill: currentColor; }

      /* Footer */
      .sa-footer {
        padding: 8px 14px;
        text-align: center;
        font-size: 10px;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: rgba(200,192,181,0.4);
        border-top: 1px solid rgba(201,168,76,0.05);
      }
      .sa-footer a { color: var(--sa-gold); text-decoration: none; }

      /* Mobile */
      @media (max-width: 480px) {
        .sa-widget-root { ${POSITION}: 0; bottom: 0; }
        .sa-panel {
          width: 100vw; height: 100vh; max-height: 100vh;
          bottom: 0; ${POSITION}: 0;
          border-radius: 0;
        }
        .sa-launcher { margin: 0 16px 16px 0; }
      }
    `;

    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ══════════════════════════════════════
  // BUILD UI
  // ══════════════════════════════════════

  const root = document.createElement('div');
  root.className = 'sa-widget-root';
  document.body.appendChild(root);

  injectStyles();

  // Launcher
  const launcher = document.createElement('button');
  launcher.className = 'sa-launcher';
  launcher.setAttribute('aria-label', I18N[language].ariaOpen);
  launcher.innerHTML = `
    <svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  `;
  root.appendChild(launcher);

  // Panel
  const panel = document.createElement('div');
  panel.className = 'sa-panel';
  panel.innerHTML = `
    <div class="sa-header">
      <div class="sa-title"></div>
      <div class="sa-header-actions">
        <button class="sa-header-btn sa-restart-btn" type="button"></button>
        <button class="sa-header-close" aria-label="Close">×</button>
      </div>
    </div>
    <div class="sa-messages" aria-live="polite"></div>
    <div class="sa-input-row">
      <textarea class="sa-input" rows="1"></textarea>
      <button class="sa-send-btn" aria-label="Send">
        <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
      </button>
    </div>
    <div class="sa-footer">
      <a href="https://sartorial-agentic.ai" target="_blank" rel="noopener"></a>
    </div>
  `;
  root.appendChild(panel);

  // Refs
  const titleEl = panel.querySelector('.sa-title');
  const messagesEl = panel.querySelector('.sa-messages');
  const inputEl = panel.querySelector('.sa-input');
  const sendBtn = panel.querySelector('.sa-send-btn');
  const restartBtn = panel.querySelector('.sa-restart-btn');
  const closeBtn = panel.querySelector('.sa-header-close');
  const footerLink = panel.querySelector('.sa-footer a');

  // ══════════════════════════════════════
  // I18N UPDATE
  // ══════════════════════════════════════
  function applyTranslations() {
    const t = I18N[language] || I18N.fr;
    inputEl.placeholder = t.placeholder;
    sendBtn.setAttribute('aria-label', t.send);
    restartBtn.textContent = t.restart;
    footerLink.textContent = t.poweredBy;
    launcher.setAttribute('aria-label', t.ariaOpen);
    closeBtn.setAttribute('aria-label', t.ariaClose);
  }

  // ══════════════════════════════════════
  // UI HELPERS
  // ══════════════════════════════════════

  function renderMessage(role, text) {
    const div = document.createElement('div');
    div.className = `sa-msg sa-msg-${role}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function showTyping() {
    const typing = document.createElement('div');
    typing.className = 'sa-typing';
    typing.innerHTML = '<span></span><span></span><span></span>';
    typing.dataset.saTyping = '1';
    messagesEl.appendChild(typing);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return typing;
  }

  function removeTyping() {
    const el = messagesEl.querySelector('[data-sa-typing]');
    if (el) el.remove();
  }

  // ══════════════════════════════════════
  // API
  // ══════════════════════════════════════

  async function apiInit() {
    const lang = (navigator.language || 'fr').split('-')[0].toLowerCase();
    const langHint = ['fr', 'en', 'de', 'nl', 'es'].includes(lang) ? lang : 'fr';

    try {
      const res = await fetch(`${API_BASE}/init`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Public-Key': PUBLIC_KEY,
        },
        body: JSON.stringify({
          visitor_id: visitorId,
          language_hint: langHint,
        }),
      });
      if (!res.ok) throw new Error('Init failed');
      const data = await res.json();

      visitorId = data.visitor_id;
      language = data.language;
      tenantName = data.tenant_name;
      localStorage.setItem(STORAGE_KEY, visitorId);

      titleEl.textContent = tenantName;
      applyTranslations();

      // Si pas d'historique, on affiche le greeting
      if (messagesEl.children.length === 0) {
        renderMessage('assistant', data.greeting);
      }
    } catch (e) {
      console.error('[Sartorial Agentic] init failed', e);
    }
  }

  async function loadHistory() {
    if (!visitorId) return;
    try {
      const res = await fetch(`${API_BASE}/history/${visitorId}`, {
        headers: { 'X-Public-Key': PUBLIC_KEY },
      });
      if (!res.ok) return;
      const data = await res.json();

      if (data.messages && data.messages.length > 0) {
        messagesEl.innerHTML = '';
        for (const msg of data.messages) {
          renderMessage(msg.role, msg.content);
        }
      }
      if (data.language) language = data.language;
    } catch (e) {
      console.warn('[Sartorial Agentic] history load failed', e);
    }
  }

  async function sendMessage(message) {
    if (isStreaming || !message.trim()) return;
    isStreaming = true;
    sendBtn.disabled = true;

    renderMessage('user', message);
    const typingEl = showTyping();

    let assistantBubble = null;
    let accumulated = '';

    try {
      const res = await fetch(`${API_BASE}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Public-Key': PUBLIC_KEY,
        },
        body: JSON.stringify({
          visitor_id: visitorId,
          message: message,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') continue;

          try {
            const event = JSON.parse(payload);

            if (event.type === 'text_delta') {
              if (!assistantBubble) {
                removeTyping();
                assistantBubble = renderMessage('assistant', '');
              }
              accumulated += event.delta;
              assistantBubble.textContent = accumulated;
              messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (event.type === 'tool_use') {
              // Tools agissent côté serveur — on ne les affiche pas au visiteur
              // sauf peut-être un indicateur "je recherche…"
            } else if (event.type === 'done') {
              // End of stream
            } else if (event.type === 'error') {
              removeTyping();
              renderMessage('assistant', event.message || I18N[language].errorGeneric);
            }
          } catch (e) {
            console.warn('[Sartorial Agentic] parse error', e);
          }
        }
      }
    } catch (e) {
      console.error('[Sartorial Agentic] stream error', e);
      removeTyping();
      if (!assistantBubble) renderMessage('assistant', I18N[language].errorGeneric);
    } finally {
      isStreaming = false;
      sendBtn.disabled = false;
      removeTyping();
    }
  }

  async function clearConversation() {
    if (!visitorId) return;
    try {
      await fetch(`${API_BASE}/history/${visitorId}`, {
        method: 'DELETE',
        headers: { 'X-Public-Key': PUBLIC_KEY },
      });
    } catch {}
    messagesEl.innerHTML = '';
    await apiInit();
  }

  // ══════════════════════════════════════
  // EVENTS
  // ══════════════════════════════════════

  launcher.addEventListener('click', async () => {
    isOpen = !isOpen;
    panel.classList.toggle('open', isOpen);
    if (isOpen) {
      if (!visitorId) {
        await apiInit();
      } else {
        await loadHistory();
        if (messagesEl.children.length === 0) {
          await apiInit();
        } else {
          titleEl.textContent = tenantName || '';
          applyTranslations();
        }
      }
      setTimeout(() => inputEl.focus(), 400);
    }
  });

  closeBtn.addEventListener('click', () => {
    isOpen = false;
    panel.classList.remove('open');
  });

  restartBtn.addEventListener('click', clearConversation);

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = inputEl.value.trim();
      if (text) {
        sendMessage(text);
        inputEl.value = '';
        inputEl.style.height = 'auto';
      }
    }
  });

  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
  });

  sendBtn.addEventListener('click', () => {
    const text = inputEl.value.trim();
    if (text) {
      sendMessage(text);
      inputEl.value = '';
      inputEl.style.height = 'auto';
    }
  });

  // Set initial translations (fallback to FR before init)
  applyTranslations();
})();
