function getCsrfToken() {
  const name = 'csrftoken=';
  const decodedCookie = decodeURIComponent(document.cookie || '');
  const parts = decodedCookie.split(';');
  for (let part of parts) {
    part = part.trim();
    if (part.startsWith(name)) {
      return part.substring(name.length);
    }
  }
  return '';
}

const toastStyles = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  error: 'border-rose-200 bg-rose-50 text-rose-900',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  info: 'border-slate-200 bg-white text-slate-900'
};

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container || !message) return;

  const toast = document.createElement('div');
  toast.className = `pointer-events-auto rounded-2xl border px-4 py-3 shadow-soft transition ${toastStyles[type] || toastStyles.info}`;
  toast.innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="text-sm font-semibold capitalize">${type}</div>
        <div class="mt-1 text-sm opacity-90">${message}</div>
      </div>
      <button type="button" class="text-lg leading-none opacity-60 hover:opacity-100" aria-label="Dismiss toast">×</button>
    </div>
  `;

  const dismiss = () => {
    toast.classList.add('opacity-0', 'translate-x-6');
    setTimeout(() => toast.remove(), 220);
  };

  toast.querySelector('button')?.addEventListener('click', dismiss);
  container.appendChild(toast);
  setTimeout(dismiss, 4200);
}

function inferBootstrapIcon(text, fallback = 'sparkles') {
  const value = String(text || '').toLowerCase();
  if (/job|brief|project/.test(value)) return 'briefcase';
  if (/bid|proposal|quote/.test(value)) return 'send-check';
  if (/message|chat|inbox|conversation/.test(value)) return 'chat-dots';
  if (/profile|account/.test(value)) return 'person-circle';
  if (/setting|security|2fa|verify|password/.test(value)) return 'shield-lock';
  if (/review|rating|testimonial|credibility/.test(value)) return 'star';
  if (/artisan|fundi|provider/.test(value)) return 'person-badge';
  if (/payment|wallet|payout/.test(value)) return 'credit-card';
  if (/delete|remove|danger|cancel/.test(value)) return 'trash3';
  if (/edit|update/.test(value)) return 'pencil-square';
  if (/save|submit|continue|next|confirm/.test(value)) return 'check2-circle';
  if (/search|browse|explore|discover/.test(value)) return 'search';
  if (/home|overview|dashboard/.test(value)) return 'speedometer2';
  if (/phone/.test(value)) return 'phone';
  if (/email/.test(value)) return 'envelope';
  return fallback;
}

function prependIcon(node, icon, wrapperClass = 'mr-2') {
  if (!node || node.querySelector('.bi')) return;
  const iconNode = document.createElement('i');
  iconNode.className = `bi bi-${icon} ${wrapperClass}`.trim();
  node.prepend(iconNode);
}

function isLikelyEmptyStateText(text) {
  const value = String(text || '').trim().toLowerCase();
  return (
    value.startsWith('no ') ||
    value.includes(' will appear here') ||
    value.includes('yet.') ||
    value.includes('right now.') ||
    value.includes('available yet.')
  );
}

window.showToast = showToast;
window.getCsrfToken = getCsrfToken;
window.setButtonLoading = (button, loading, label) => {
  if (!button) return;
  const textHolder = button.querySelector('.button-label');
  if (!button.dataset.originalHtml) {
    button.dataset.originalHtml = button.innerHTML;
  }
  if (!button.dataset.originalLabel) {
    button.dataset.originalLabel = textHolder ? textHolder.textContent : button.textContent.trim();
  }
  if (loading) {
    button.disabled = true;
    const nextLabel = label || button.dataset.loadingLabel || 'Working...';
    button.innerHTML = `<span class="inline-flex items-center gap-2"><span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"></span><span class="button-label">${nextLabel}</span></span>`;
  } else {
    button.disabled = false;
    button.innerHTML = button.dataset.originalHtml || button.innerHTML;
  }
};
window.setLinkLoading = (link, loading, label) => {
  if (!link) return;
  if (!link.dataset.originalHtml) {
    link.dataset.originalHtml = link.innerHTML;
  }
  if (loading) {
    const nextLabel = label || link.dataset.loadingLabel || link.textContent.trim() || 'Opening...';
    link.setAttribute('aria-disabled', 'true');
    link.classList.add('pointer-events-none', 'opacity-90');
    link.innerHTML = `<span class="inline-flex items-center gap-2"><span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current/30 border-t-current"></span><span>${nextLabel}</span></span>`;
  } else {
    link.removeAttribute('aria-disabled');
    link.classList.remove('pointer-events-none', 'opacity-90');
    link.innerHTML = link.dataset.originalHtml || link.innerHTML;
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-mobile-overlay');
  const openButton = document.getElementById('sidebar-toggle-button');
  const closeButton = document.getElementById('sidebar-close-button');
  const collapseButton = document.getElementById('sidebar-collapse-button');
  const collapseStorageKey = 'fundiconnect-sidebar-collapsed';
  const isDesktop = () => window.matchMedia('(min-width: 768px)').matches;

  const toggleSidebar = (isOpen) => {
    if (!sidebar || !overlay) return;
    const open = typeof isOpen === 'boolean' ? isOpen : sidebar.classList.contains('-translate-x-full');
    sidebar.classList.toggle('-translate-x-full', !open);
    overlay.classList.toggle('hidden', !open);
    body.classList.toggle('overflow-hidden', open && !isDesktop());
  };

  // Ensure desktop starts with sidebar visible (untoggled) unless explicitly collapsed in storage
  if (isDesktop()) {
    sidebar?.classList.remove('-translate-x-full');
    overlay?.classList.add('hidden');
  }

  const setCollapsed = (collapsed) => {
    if (!isDesktop()) {
      body.classList.remove('sidebar-collapsed');
      body.classList.remove('sidebar-text-hidden');
      return;
    }
    // Toggle collapsed class immediately
    body.classList.toggle('sidebar-collapsed', collapsed);
    if (collapseButton) {
      collapseButton.innerHTML = collapsed ? '<i class="bi bi-layout-sidebar"></i>' : '<i class="bi bi-layout-sidebar-inset"></i>';
    }

    // When collapsing: hide text immediately to avoid hanging labels.
    // When expanding: keep text hidden until the sidebar finished its CSS transition.
    if (collapsed) {
      // If collapsing, remove any existing expand spinner and hide text immediately
      const existingSpinner = document.getElementById('sidebar-expand-spinner');
      if (existingSpinner) existingSpinner.remove();
      body.classList.add('sidebar-text-hidden');
    } else {
      // While expanding, hide text and show a small spinner in the sidebar brand area
      body.classList.add('sidebar-text-hidden');
      if (sidebar && !document.getElementById('sidebar-expand-spinner')) {
        const spinner = document.createElement('div');
        spinner.id = 'sidebar-expand-spinner';
        spinner.className = 'absolute left-1/2 top-3 -translate-x-1/2 z-40';
        spinner.innerHTML = '<span class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden="true"></span>';
        sidebar.appendChild(spinner);
      }

      // Wait for the sidebar transition to finish before showing text and removing spinner.
      const onTransitionEnd = (ev) => {
        if (ev.target !== sidebar) return;
        window.setTimeout(() => body.classList.remove('sidebar-text-hidden'), 20);
        const existingSpinner = document.getElementById('sidebar-expand-spinner');
        if (existingSpinner) existingSpinner.remove();
        sidebar.removeEventListener('transitionend', onTransitionEnd);
      };
      sidebar.addEventListener('transitionend', onTransitionEnd);

      // Safety fallback: ensure text is shown and spinner removed after a max delay.
      window.setTimeout(() => {
        if (!body.classList.contains('sidebar-collapsed')) body.classList.remove('sidebar-text-hidden');
        const existingSpinner = document.getElementById('sidebar-expand-spinner');
        if (existingSpinner) existingSpinner.remove();
        sidebar.removeEventListener('transitionend', onTransitionEnd);
      }, 900);
    }
    try {
      localStorage.setItem(collapseStorageKey, collapsed ? 'true' : 'false');
    } catch (error) {}
  };

  openButton?.addEventListener('click', () => toggleSidebar(true));
  closeButton?.addEventListener('click', () => toggleSidebar(false));
  overlay?.addEventListener('click', () => toggleSidebar(false));
  collapseButton?.addEventListener('click', () => setCollapsed(!body.classList.contains('sidebar-collapsed')));
  sidebar?.addEventListener('mouseenter', () => {
    if (isDesktop() && body.classList.contains('sidebar-collapsed')) {
      body.classList.add('sidebar-peek');
    }
  });
  sidebar?.addEventListener('mouseleave', () => body.classList.remove('sidebar-peek'));

  try {
    setCollapsed(localStorage.getItem(collapseStorageKey) === 'true');
  } catch (error) {
    setCollapsed(false);
  }

  window.addEventListener('resize', () => {
    if (!isDesktop()) {
      body.classList.remove('sidebar-collapsed');
      body.classList.remove('sidebar-peek');
      body.classList.remove('overflow-hidden');
      overlay?.classList.add('hidden');
      sidebar?.classList.add('-translate-x-full');
    } else {
      sidebar?.classList.remove('-translate-x-full');
      overlay?.classList.add('hidden');
      try {
        setCollapsed(localStorage.getItem(collapseStorageKey) === 'true');
      } catch (error) {
        setCollapsed(false);
      }
    }
  });

  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
      if (!submitter || submitter.dataset.skipLoading === 'true') return;
      window.setButtonLoading(submitter, true);
    });
  });

  window.addEventListener('pageshow', () => {
    document.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((button) => {
      if (button.dataset.originalHtml) {
        window.setButtonLoading(button, false);
      }
    });
    document.querySelectorAll('a[data-loading-label]').forEach((link) => {
      if (link.dataset.originalHtml) {
        window.setLinkLoading(link, false);
      }
    });
  });

  document.querySelectorAll('a[data-loading-label]').forEach((link) => {
    link.addEventListener('click', () => window.setLinkLoading(link, true));
  });

  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link[data-path]').forEach((link) => {
    const target = link.getAttribute('data-path');
    if (!target) return;
    if (currentPath === target || (target !== '/' && currentPath.startsWith(target))) {
      link.classList.add('bg-slate-900', 'text-white', 'shadow-soft');
      link.classList.remove('text-slate-600');
    }
  });

  document.querySelectorAll('[data-toast-message]').forEach((node) => {
    showToast(node.dataset.toastMessage, node.dataset.toastType || 'info');
  });

  document
    .querySelectorAll('button, a, h1, h2, h3, h4, .empty-state-title, .empty-state-action')
    .forEach((node) => {
      if (node.dataset.autoIconApplied === 'true') return;
      const text = node.textContent.trim();
      if (!text || node.querySelector('.bi') || node.closest('#assistant-widget')) return;
      if (node.dataset.skipAutoIcon === 'true' || node.closest('[data-skip-auto-icon="true"]')) return;
      const isAction = node.matches('button, a');
      const isHeading = /^H[1-4]$/.test(node.tagName);
      if (!isAction && !isHeading && !node.classList.contains('empty-state-title') && !node.classList.contains('empty-state-action')) return;
      prependIcon(node, inferBootstrapIcon(text, isHeading ? 'stars' : 'arrow-right-circle'));
      node.dataset.autoIconApplied = 'true';
    });

  document.querySelectorAll('div, p').forEach((node) => {
    if (node.dataset.emptyStateEnhanced === 'true') return;
    if (node.querySelector('*')) return;
    const text = node.textContent.trim();
    if (!isLikelyEmptyStateText(text)) return;
    if (text.length > 160) return;
    node.className = 'rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500';
    node.innerHTML = `
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-sky-700 shadow-sm">
        <i class="bi bi-inbox text-xl"></i>
      </div>
      <div class="empty-state-title mt-3 font-semibold text-slate-900">${text}</div>
    `;
    node.dataset.emptyStateEnhanced = 'true';
  });

  document.querySelectorAll('.text-3xl.font-extrabold, .text-4xl.font-extrabold').forEach((valueNode) => {
    const card = valueNode.closest('div.rounded-3xl, div.rounded-\\[2rem\\]');
    if (!card || card.dataset.statEnhanced === 'true') return;
    const labelNode = Array.from(card.children).find((child) => child !== valueNode && /text-slate-500/.test(child.className || ''));
    if (!labelNode) return;
    const label = labelNode.textContent.trim();
    if (!label || labelNode.querySelector('.bi')) return;
    labelNode.classList.add('flex', 'items-center', 'gap-2');
    prependIcon(labelNode, inferBootstrapIcon(label, 'bar-chart'));
    card.dataset.statEnhanced = 'true';
  });

  const debounce = (fn, delay = 250) => {
    let timer = null;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), delay);
    };
  };

  const ensureLeafletAssets = async () => {
    if (window.L) return;
    if (!document.querySelector('link[data-leaflet]')) {
      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      stylesheet.dataset.leaflet = '1';
      document.head.appendChild(stylesheet);
    }
    await new Promise((resolve, reject) => {
      const existing = document.querySelector('script[data-leaflet]');
      if (existing && window.L) {
        resolve();
        return;
      }
      if (existing) {
        existing.addEventListener('load', resolve, { once: true });
        existing.addEventListener('error', reject, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.dataset.leaflet = '1';
      script.onload = resolve;
      script.onerror = reject;
      document.body.appendChild(script);
    });
  };

  document.querySelectorAll('[data-location-picker]').forEach((field) => {
    if (field.dataset.locationEnhanced === '1') return;

    const wrapper = document.createElement('div');
    wrapper.className = 'location-picker-shell';
    if (field.dataset.locationHideMap === '1') wrapper.classList.add('location-picker-hidden-map');

    const toolbar = document.createElement('div');
    toolbar.className = 'location-picker-toolbar';

    const search = document.createElement('input');
    search.type = 'search';
    search.className = 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-500';
    search.placeholder = `Search ${field.dataset.locationLabel || 'location'} with map support`;

    const useCurrent = document.createElement('button');
    useCurrent.type = 'button';
    useCurrent.className = 'inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50';
    useCurrent.innerHTML = '<i class="bi bi-crosshair"></i><span>Use current location</span>';

    const suggestions = document.createElement('div');
    suggestions.className = 'location-suggestion-list hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-soft';

    const mapNode = document.createElement('div');
    mapNode.className = 'location-picker-map';

    field.parentNode.insertBefore(wrapper, field);
    wrapper.appendChild(toolbar);
    toolbar.appendChild(search);
    toolbar.appendChild(useCurrent);
    wrapper.appendChild(suggestions);
    wrapper.appendChild(field);
    wrapper.appendChild(mapNode);

    field.classList.add('w-full', 'rounded-2xl', 'border', 'border-slate-300', 'px-4', 'py-3', 'text-sm', 'text-slate-900', 'outline-none', 'transition', 'focus:border-slate-500');

    const defaultLocation = {
      latitude: -1.286389,
      longitude: 36.817223,
      label: field.dataset.locationDefault || 'Nairobi, Kenya'
    };
    let map = null;
    let marker = null;

    const closeSuggestions = () => suggestions.classList.add('hidden');

    const renderMap = async (latitude, longitude, label) => {
      if (field.dataset.locationHideMap === '1') {
        mapNode.classList.add('hidden');
        return;
      }
      try {
        await ensureLeafletAssets();
        if (!map) {
          map = window.L.map(mapNode, { zoomControl: true }).setView([latitude, longitude], 14);
          window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
          }).addTo(map);
        } else {
          map.setView([latitude, longitude], 14);
        }
        if (!marker) {
          marker = window.L.marker([latitude, longitude]).addTo(map);
        } else {
          marker.setLatLng([latitude, longitude]);
        }
        if (label) marker.bindPopup(label).openPopup();
        window.setTimeout(() => map.invalidateSize(), 120);
      } catch (error) {
        mapNode.classList.add('hidden');
      }
    };

    const renderSuggestions = (results) => {
      suggestions.innerHTML = '';
      if (!results.length) {
        closeSuggestions();
        return;
      }
      results.forEach((item) => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'flex w-full items-start justify-between gap-3 rounded-2xl px-3 py-3 text-left text-sm transition hover:bg-slate-50';
        row.innerHTML = `<span class="font-semibold text-slate-800">${item.display_name}</span><span class="text-slate-500">${item.type || 'Location'}</span>`;
        row.addEventListener('click', () => {
          field.value = item.display_name;
          search.value = item.display_name;
          closeSuggestions();
          renderMap(Number(item.lat), Number(item.lon), item.display_name);
        });
        suggestions.appendChild(row);
      });
      suggestions.classList.remove('hidden');
    };

    const searchLocations = debounce(async () => {
      const term = search.value.trim();
      if (term.length < 3) {
        closeSuggestions();
        return;
      }
      try {
        const response = await fetch(`/accounts/location/search/?q=${encodeURIComponent(term)}`);
        if (!response.ok) {
          closeSuggestions();
          return;
        }
        const payload = await response.json();
        renderSuggestions(payload.results || []);
      } catch (error) {
        closeSuggestions();
      }
    }, 320);

    search.addEventListener('input', searchLocations);
    search.addEventListener('focus', searchLocations);
    document.addEventListener('click', (event) => {
      if (!wrapper.contains(event.target)) closeSuggestions();
    });

    useCurrent.addEventListener('click', () => {
      if (!navigator.geolocation) {
        showToast('This browser cannot access device location right now.', 'warning');
        return;
      }
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const latitude = position.coords.latitude;
          const longitude = position.coords.longitude;
          try {
            const response = await fetch(`/accounts/location/reverse/?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`);
            const data = await response.json();
            const label = data.display_name || `${latitude}, ${longitude}`;
            field.value = label;
            search.value = label;
            renderMap(latitude, longitude, label);
          } catch (error) {
            field.value = `${latitude}, ${longitude}`;
            search.value = field.value;
            renderMap(latitude, longitude, field.value);
          }
        },
        () => showToast('Device location could not be retrieved right now.', 'warning'),
        { enableHighAccuracy: true, timeout: 12000 }
      );
    });

    if (field.value.trim()) {
      search.value = field.value.trim();
    } else {
      search.value = defaultLocation.label;
    }
    renderMap(defaultLocation.latitude, defaultLocation.longitude, search.value);
    field.dataset.locationEnhanced = '1';
  });

  const collectAssistantFormPreview = (form) => {
    const preview = {};
    if (!form) return preview;
    form.querySelectorAll('input, textarea, select').forEach((field) => {
      const name = field.name || field.id;
      if (!name || /csrfmiddlewaretoken/i.test(name) || field.type === 'password' || field.type === 'hidden') return;
      const value = String(field.value || '').trim();
      if (!value) return;
      preview[name] = value.length > 240 ? `${value.slice(0, 240)}...` : value;
    });
    return preview;
  };

  const buildAssistantSurfacePrompt = (page, form, preview) => {
    const lowerPage = String(page || '').toLowerCase();
    if (lowerPage === 'home') {
      return 'Give me a live FundiConnect home-page briefing with the best next actions, recommended areas to explore, and quick platform insights for this user.';
    }
    if (lowerPage === 'client_dashboard') {
      return 'Give me a short client dashboard briefing with the most important next actions, hiring recommendations, and any delivery follow-ups worth doing now.';
    }
    if (lowerPage === 'post_job') {
      return `I am drafting a FundiConnect job post. Review this draft and tell me how to improve the brief, pricing clarity, scope, urgency, and trust signals. Draft snapshot: ${JSON.stringify(preview)}`;
    }
    if (lowerPage === 'place_bid') {
      return `I am preparing a FundiConnect bid. Review this bid draft and tell me how to make it more competitive, believable, and conversion-friendly. Draft snapshot: ${JSON.stringify(preview)}`;
    }
    return `Give me page-aware FundiConnect guidance for ${page || 'this screen'} using this visible draft data: ${JSON.stringify(preview)}`;
  };

  const renderAssistantSurface = (slot, data) => {
    if (!slot || !data) return;
    const suggestions = Array.isArray(data.suggestions) ? data.suggestions.slice(0, 4) : [];
    const highlights = Array.isArray(data.highlights) ? data.highlights.slice(0, 4) : [];
    const platformItems = Array.isArray(data.platform_items) ? data.platform_items.slice(0, 3) : [];

    slot.innerHTML = `
      <div class="rounded-[1.75rem] border border-slate-200 bg-gradient-to-br from-white via-slate-50 to-sky-50/70 p-6 shadow-soft animate-rise">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div class="max-w-3xl">
            <div class="inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.22em] text-white">
              <i class="bi bi-stars text-sky-300"></i>FundiConnect AI
            </div>
            <p class="mt-4 text-sm leading-7 text-slate-700">${data.text || 'AI suggestions will appear here.'}</p>
            ${highlights.length ? `
              <div class="mt-4 flex flex-wrap gap-2">
                ${highlights.map((item) => `<span class="inline-flex items-center gap-2 rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-600 ring-1 ring-slate-200"><i class="bi bi-lightning-charge-fill text-amber-500"></i>${item}</span>`).join('')}
              </div>
            ` : ''}
          </div>
          ${platformItems.length ? `
            <div class="grid min-w-[280px] gap-3 lg:max-w-sm">
              ${platformItems.map((item) => `
                <a href="${item.url || '#'}" class="rounded-2xl bg-white px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-md ${item.url ? '' : 'pointer-events-none'}">
                  <div class="flex items-center gap-2 font-semibold text-slate-900"><i class="bi bi-${item.icon || inferBootstrapIcon(item.title || item.type || 'item', 'sparkles')} text-sky-600"></i>${item.title || 'Insight'}</div>
                  <div class="mt-1 text-xs text-slate-500">${item.subtitle || ''}</div>
                </a>
              `).join('')}
            </div>
          ` : ''}
        </div>
        ${suggestions.length ? `
          <div class="mt-5 flex flex-wrap gap-3">
            ${suggestions.map((item) => `
              <a href="${item.url || '#'}" class="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-sky-300 hover:text-sky-700 hover:shadow-sm ${item.url ? '' : 'pointer-events-none opacity-70'}">
                <i class="bi bi-${item.icon || inferBootstrapIcon(item.label || 'action', 'arrow-right-circle')}"></i>
                <span>${item.label || 'Open'}</span>
              </a>
            `).join('')}
          </div>
        ` : ''}
      </div>
    `;
  };

  const renderAssistantSurfaceLoading = (slot) => {
    if (!slot) return;
    slot.innerHTML = `
      <div class="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-soft">
        <div class="flex items-center gap-3 text-sm font-semibold text-slate-600">
          <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-sky-200 border-t-sky-600"></span>
          Preparing tailored AI guidance...
        </div>
      </div>
    `;
  };

  document.querySelectorAll('form[data-assistant-endpoint]').forEach((form) => {
    const context = (() => {
      try {
        return JSON.parse(form.dataset.assistantContext || '{}');
      } catch (error) {
        return {};
      }
    })();
    const page = context.page || form.id || 'page';
    const slot = document.getElementById(form.dataset.assistantSlot || `ai-suggestion-slot-${String(page).replace(/_/g, '-')}`);
    const endpoint = form.dataset.assistantEndpoint;
    if (!slot || !endpoint || slot.dataset.aiSurfaceBound === '1') return;
    slot.dataset.aiSurfaceBound = '1';

    let lastPrompt = '';

    const requestAdvice = debounce(async () => {
      const preview = collectAssistantFormPreview(form);
      const prompt = buildAssistantSurfacePrompt(page, form, preview);
      if (!prompt || prompt === lastPrompt) return;
      lastPrompt = prompt;
      renderAssistantSurfaceLoading(slot);
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({
            prompt,
            path: window.location.pathname,
            context: {
              ...context,
              surface: 'inline',
              form_preview: preview,
              history: []
            }
          })
        });
        const payload = await response.json();
        if (!response.ok || !payload?.ok || !payload?.data) {
          throw new Error('Assistant surface request failed.');
        }
        renderAssistantSurface(slot, payload.data);
      } catch (error) {
        slot.innerHTML = `
          <div class="rounded-[1.75rem] border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">
            <div class="flex items-center gap-2 font-semibold text-slate-800"><i class="bi bi-robot text-sky-600"></i>AI suggestions are temporarily unavailable</div>
            <p class="mt-2">You can still continue normally, and the assistant widget remains available.</p>
          </div>
        `;
      }
    }, 750);

    requestAdvice();
    form.querySelectorAll('input, textarea, select').forEach((field) => {
      field.addEventListener('input', requestAdvice);
      field.addEventListener('change', requestAdvice);
    });
  });
});

// Reviews modal and AJAX handler
document.addEventListener('click', (e) => {
  const btn = e.target.closest && e.target.closest('.view-reviews-btn');
  if (!btn) return;
  e.preventDefault();
  const url = btn.dataset.reviewUrl;
  if (!url) return;
  btn.disabled = true;
  fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then((r) => r.json())
    .then((payload) => {
      if (!payload || !payload.html) {
        showToast('Could not load reviews right now.', 'error');
        return;
      }
      const container = document.getElementById('modal-container');
      if (!container) return;
      container.innerHTML = payload.html;
      // attach dismiss handlers
      container.querySelectorAll('[data-dismiss-modal]').forEach((node) => {
        node.addEventListener('click', () => { container.innerHTML = ''; });
      });
    })
    .catch(() => showToast('Failed to load reviews.', 'error'))
    .finally(() => { btn.disabled = false; });
});

// Close modal on escape
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const container = document.getElementById('modal-container');
    if (container && container.innerHTML.trim()) container.innerHTML = '';
  }
});

// Simple tooltip/popover: any element with data-tooltip shows native title-styled popover
document.addEventListener('mouseover', (e) => {
  const node = e.target.closest && e.target.closest('[data-tooltip]');
  if (!node) return;
  const tip = node.getAttribute('data-tooltip');
  if (!tip) return;
  node.dataset.origTitle = node.getAttribute('title') || '';
  node.setAttribute('title', tip);
});
document.addEventListener('mouseout', (e) => {
  const node = e.target.closest && e.target.closest('[data-tooltip]');
  if (!node) return;
  if (typeof node.dataset.origTitle !== 'undefined') node.setAttribute('title', node.dataset.origTitle || '');
});
