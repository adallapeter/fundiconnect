(function () {
  const widget = document.getElementById('assistant-widget');
  if (!widget) return;

  const panel = document.getElementById('assistant-panel');
  const toggle = document.getElementById('assistant-toggle');
  const close = document.getElementById('assistant-close');
  const form = document.getElementById('assistant-form');
  const input = document.getElementById('assistant-input');
  const messages = document.getElementById('assistant-messages');
  const assistantTyping = document.getElementById('assistant-typing');
  const userTyping = document.getElementById('assistant-user-typing');
  const statusNode = document.getElementById('assistant-status');
  const submitButton = form?.querySelector('button[type="submit"]');
  const storageKey = 'fundiconnect-assistant-open';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  let socket = null;
  let assistantWaiting = false;
  let fallbackMode = false;
  let userTypingTimer = null;
  let initialStateLoaded = false;
  let reconnectTimer = null;
  let typingSent = false;
  const conversationContext = [];

  const defaultSuggestions = [
    { label: 'Post a job', url: '/post_job/' },
    { label: 'Browse jobs', url: '/jobs/' },
    { label: 'Open dashboard', url: '/accounts/dashboard/' }
  ];

  const escapeHtml = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const scrollToBottom = () => {
    if (!messages) return;
    messages.scrollTop = messages.scrollHeight;
  };

  const setAssistantTyping = (visible, text) => {
    if (!assistantTyping) return;
    assistantTyping.textContent = text || 'FundiConnect AI Assistant is typing...';
    assistantTyping.classList.toggle('hidden', !visible);
  };

  const setUserTyping = (visible) => {
    if (!userTyping) return;
    userTyping.classList.toggle('hidden', !visible);
  };

  const setStatus = (text, tone = 'text-slate-500') => {
    if (!statusNode) return;
    statusNode.textContent = text || '';
    statusNode.className = `mb-2 text-xs font-medium ${tone}${text ? '' : ' hidden'}`;
  };

  const bubbleExists = (role, text) => Array.from(messages?.children || []).some((node) => {
    return node.dataset.role === role && node.dataset.text === text;
  });

  const appendBubble = (role, text) => {
    if (!messages || !text || bubbleExists(role, text)) return;
    const own = role === 'user';
    const bubble = document.createElement('div');
    bubble.dataset.role = role;
    bubble.dataset.text = text;
    bubble.className = `flex ${own ? 'justify-end' : 'justify-start'} animate-rise`;
    bubble.innerHTML = `
      <div class="max-w-[85%] rounded-[1.5rem] px-4 py-3 text-sm leading-6 ${own ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-800 shadow-sm'}">
        ${escapeHtml(text)}
      </div>
    `;
    messages.appendChild(bubble);
    scrollToBottom();
    conversationContext.push({ role, content: text });
    while (conversationContext.length > 10) conversationContext.shift();
  };

  const appendAssistantMeta = (data) => {
    if (!messages) return;
    const suggestions = (data.suggestions && data.suggestions.length ? data.suggestions : defaultSuggestions).slice(0, 5);
    const highlights = (data.highlights || []).filter(Boolean).slice(0, 4);
    const platformItems = (data.platform_items || []).filter(Boolean).slice(0, 3);
    if (!suggestions.length && !highlights.length && !platformItems.length) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'flex justify-start animate-rise';
    const cards = document.createElement('div');
    cards.className = 'max-w-[92%] space-y-3 rounded-[1.5rem] border border-slate-200 bg-white/90 px-4 py-4 shadow-sm';

    if (highlights.length) {
      const highlightRow = document.createElement('div');
      highlightRow.className = 'flex flex-wrap gap-2';
      highlights.forEach((item) => {
        const pill = document.createElement('div');
        pill.className = 'inline-flex items-center gap-2 rounded-full bg-sky-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700';
        pill.innerHTML = `<i class="bi bi-lightning-charge"></i><span>${escapeHtml(item)}</span>`;
        highlightRow.appendChild(pill);
      });
      cards.appendChild(highlightRow);
    }

    if (platformItems.length) {
      const itemsWrap = document.createElement('div');
      itemsWrap.className = 'space-y-2';
      platformItems.forEach((item) => {
        const node = document.createElement(item.url ? 'a' : 'div');
        node.className = 'flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700 transition hover:border-slate-300 hover:bg-white';
        if (item.url) {
          node.href = item.url;
          node.dataset.loadingLabel = 'Opening...';
          node.addEventListener('click', () => {
            if (window.setLinkLoading) window.setLinkLoading(node, true);
          });
        }
        node.innerHTML = `
          <div class="flex items-start gap-3">
            <div class="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-white text-slate-700 shadow-sm">
              <i class="bi bi-${escapeHtml(item.icon || 'sparkles')}"></i>
            </div>
            <div>
              <div class="font-semibold text-slate-900">${escapeHtml(item.title || 'Platform item')}</div>
              <div class="text-xs text-slate-500">${escapeHtml(item.subtitle || '')}</div>
            </div>
          </div>
          ${item.url ? '<i class="bi bi-arrow-up-right-circle text-slate-400"></i>' : ''}
        `;
        itemsWrap.appendChild(node);
      });
      cards.appendChild(itemsWrap);
    }

    if (suggestions.length) {
      const suggestionWrap = document.createElement('div');
      suggestionWrap.className = 'flex flex-wrap gap-2';
      suggestions.forEach((item) => {
        const action = document.createElement(item.url ? 'a' : 'button');
        action.className = 'inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-white';
        const icon = item.icon ? `<i class="bi bi-${escapeHtml(item.icon)}"></i>` : '';
        action.innerHTML = `${icon}<span>${escapeHtml(item.label || 'Open')}</span>`;
        if (item.url) {
          action.href = item.url;
          action.dataset.loadingLabel = 'Opening...';
          action.addEventListener('click', () => {
            if (window.setLinkLoading) window.setLinkLoading(action, true);
          });
        } else {
          action.type = 'button';
        }
        if (item.reason) action.title = item.reason;
        suggestionWrap.appendChild(action);
      });
      cards.appendChild(suggestionWrap);
    }

    wrapper.appendChild(cards);
    messages.appendChild(wrapper);
    scrollToBottom();
  };

  const setOpen = (open) => {
    panel?.classList.toggle('hidden', !open);
    toggle?.classList.toggle('hidden', open);
    if (open) {
      setTimeout(() => input?.focus(), 60);
      scrollToBottom();
    }
    try {
      window.localStorage.setItem(storageKey, open ? 'true' : 'false');
    } catch (error) {}
  };

  const setLoading = (loading) => {
    assistantWaiting = loading;
    if (!submitButton || !window.setButtonLoading) return;
    if (loading) {
      window.setButtonLoading(submitButton, true);
    } else {
      window.setButtonLoading(submitButton, false);
    }
  };

  const requestFallback = async (prompt) => {
    const response = await fetch('/accounts/assistant/respond/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.getCsrfToken ? window.getCsrfToken() : ''
      },
      body: JSON.stringify({ prompt, path: window.location.pathname, context: conversationContext })
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.error || 'Assistant request failed.');
    }
    return payload.data;
  };

  const handleResponse = (data) => {
    appendBubble('assistant', data.text || 'I am here to help.');
    appendAssistantMeta(data);
    setAssistantTyping(false);
    setLoading(false);
    setStatus(fallbackMode ? 'Reply delivered through the backup assistant channel.' : 'Live assistant connected.', fallbackMode ? 'text-amber-600' : 'text-emerald-600');
  };

  const handleFailure = (message) => {
    appendBubble('assistant', message || 'I am having trouble right now, but please try again in a moment.');
    appendAssistantMeta({ suggestions: defaultSuggestions });
    setAssistantTyping(false);
    setLoading(false);
    setStatus('The live assistant is reconnecting. You can still keep chatting.', 'text-amber-600');
  };

  const sendPrompt = async (prompt) => {
    if (!prompt || assistantWaiting) return;
    appendBubble('user', prompt);
    setUserTyping(false);
    input.value = '';
    setAssistantTyping(true);
    setLoading(true);

    try {
      if (!fallbackMode && socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'generate', prompt, path: window.location.pathname, context: conversationContext }));
        return;
      }
      const data = await requestFallback(prompt);
      handleResponse(data);
    } catch (error) {
      handleFailure('I had trouble sending that. Please try again in a moment.');
    }
  };

  const connect = () => {
    if (socket && socket.readyState === WebSocket.OPEN) return;
    clearTimeout(reconnectTimer);
    try {
      socket = new WebSocket(`${proto}://${window.location.host}/ws/assistant/`);
      setStatus('Connecting to the live assistant...', 'text-sky-700');
      socket.addEventListener('open', () => {
        fallbackMode = false;
        setStatus('Live assistant connected.', 'text-emerald-600');
      });
      socket.addEventListener('message', (event) => {
        const payload = JSON.parse(event.data || '{}');
        if (payload.type === 'assistant_state') {
          if (!initialStateLoaded) {
            if (payload.data.greeting) appendBubble('assistant', payload.data.greeting);
            (payload.data.history || []).forEach((item) => appendBubble(item.role, item.content));
            initialStateLoaded = true;
          }
          return;
        }
        if (payload.type === 'assistant_typing') {
          if (payload.actor === 'assistant') {
            setAssistantTyping(Boolean(payload.is_typing));
            if (payload.is_typing) {
              setStatus('FundiConnect AI is thinking through your workspace...', 'text-sky-700');
            }
          } else if (payload.actor === 'user') {
            setUserTyping(Boolean(payload.is_typing));
          }
          return;
        }
        if (payload.type === 'assistant_response' && payload.ok && payload.data) {
          handleResponse(payload.data);
        } else if (payload.type === 'assistant_response' && !payload.ok) {
          handleFailure(payload.error || 'I am having trouble right now, but I can still guide you around the platform.');
        }
      });
      socket.addEventListener('close', () => {
        fallbackMode = true;
        setStatus('Live assistant unavailable. Reconnecting in the background...', 'text-amber-600');
        reconnectTimer = window.setTimeout(connect, 2500);
      });
      socket.addEventListener('error', () => {
        fallbackMode = true;
        setStatus('Live assistant unavailable. Using the backup channel for now.', 'text-amber-600');
      });
    } catch (error) {
      fallbackMode = true;
      setStatus('Live assistant unavailable. Using the backup channel for now.', 'text-amber-600');
      renderSuggestions(defaultSuggestions);
    }
  };

  toggle?.addEventListener('click', () => setOpen(true));
  close?.addEventListener('click', () => setOpen(false));

  input?.addEventListener('input', () => {
    const hasValue = Boolean(input.value.trim());
    setUserTyping(hasValue);
    if (!fallbackMode && socket && socket.readyState === WebSocket.OPEN) {
      if (hasValue && !typingSent) {
        socket.send(JSON.stringify({ type: 'typing', is_typing: true }));
        typingSent = true;
      } else if (!hasValue && typingSent) {
        socket.send(JSON.stringify({ type: 'typing', is_typing: false }));
        typingSent = false;
      }
    }
    window.clearTimeout(userTypingTimer);
    userTypingTimer = window.setTimeout(() => {
      setUserTyping(false);
      if (!fallbackMode && socket && socket.readyState === WebSocket.OPEN && typingSent) {
        socket.send(JSON.stringify({ type: 'typing', is_typing: false }));
        typingSent = false;
      }
    }, 900);
  });

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const prompt = input.value.trim();
    await sendPrompt(prompt);
  });

  try {
    setOpen(window.localStorage.getItem(storageKey) === 'true');
  } catch (error) {
    setOpen(false);
  }

  connect();
})();
