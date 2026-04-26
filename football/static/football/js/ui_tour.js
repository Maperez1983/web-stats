(() => {
  const safeText = (value, fallback = '') => String(value ?? '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const DEFAULT_BACKDROP = 'rgba(2,6,23,0.72)';
  const DEFAULT_ACCENT = 'rgba(34,211,238,0.9)';

  const ensureStyles = () => {
    if (document.getElementById('webstats-ui-tour-styles')) return;
    const style = document.createElement('style');
    style.id = 'webstats-ui-tour-styles';
    style.textContent = `
      .ui-tour-root{position:fixed;inset:0;z-index:10000;display:none;align-items:stretch;justify-content:stretch}
      .ui-tour-backdrop{position:absolute;inset:0;background:${DEFAULT_BACKDROP};}
      .ui-tour-hole{position:absolute;border-radius:16px;box-shadow:0 0 0 9999px ${DEFAULT_BACKDROP};outline:2px solid ${DEFAULT_ACCENT};outline-offset:2px;pointer-events:none;transition:top .12s ease,left .12s ease,width .12s ease,height .12s ease}
      .ui-tour-popover{position:absolute;max-width:min(420px,calc(100vw - 32px));min-width:min(320px,calc(100vw - 32px));border-radius:16px;border:1px solid rgba(255,255,255,0.14);background:rgba(15,23,42,0.96);color:rgba(248,250,252,0.96);box-shadow:0 18px 42px rgba(2,6,23,0.55);backdrop-filter:blur(10px);padding:14px 14px 12px}
      .ui-tour-title{font-weight:900;font-size:14px;letter-spacing:.2px;margin:0 0 6px}
      .ui-tour-body{margin:0;color:rgba(226,232,240,0.92);font-size:13px;line-height:1.35}
      .ui-tour-controls{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:12px;flex-wrap:wrap}
      .ui-tour-progress{font-size:12px;color:rgba(148,163,184,0.95)}
      .ui-tour-btns{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;margin-left:auto}
      .ui-tour-btn{appearance:none;border:1px solid rgba(255,255,255,0.16);background:rgba(255,255,255,0.06);color:rgba(248,250,252,0.96);border-radius:12px;padding:8px 10px;font-weight:800;font-size:12px;cursor:pointer}
      .ui-tour-btn.primary{border-color:rgba(34,211,238,0.45);background:rgba(34,211,238,0.18)}
      .ui-tour-btn.danger{border-color:rgba(248,113,113,0.35);background:rgba(248,113,113,0.12)}
      .ui-tour-btn:active{transform:translateY(1px)}
      @media (max-width: 820px){
        .ui-tour-popover{left:16px !important;right:16px !important;bottom:16px !important;top:auto !important;min-width:0;max-width:none}
        .ui-tour-hole{border-radius:14px}
      }
    `.trim();
    document.head.appendChild(style);
  };

  const ensureRoot = () => {
    ensureStyles();
    let root = document.getElementById('ui-tour-root');
    if (root) return root;
    root = document.createElement('div');
    root.id = 'ui-tour-root';
    root.className = 'ui-tour-root';
    root.innerHTML = `
      <div class="ui-tour-backdrop" data-tour-backdrop></div>
      <div class="ui-tour-hole" data-tour-hole></div>
      <div class="ui-tour-popover" data-tour-popover role="dialog" aria-modal="true" aria-label="Tutorial">
        <h3 class="ui-tour-title" data-tour-title></h3>
        <p class="ui-tour-body" data-tour-body></p>
        <div class="ui-tour-controls">
          <div class="ui-tour-progress" data-tour-progress></div>
          <div class="ui-tour-btns">
            <button type="button" class="ui-tour-btn danger" data-tour-skip>Salir</button>
            <button type="button" class="ui-tour-btn" data-tour-prev>Anterior</button>
            <button type="button" class="ui-tour-btn primary" data-tour-next>Siguiente</button>
          </div>
        </div>
      </div>
    `.trim();
    document.body.appendChild(root);
    return root;
  };

  const resolveAnchor = (step) => {
    if (!step) return null;
    if (step.el && step.el.getBoundingClientRect) return step.el;
    const selector = safeText(step.anchor);
    if (!selector) return null;
    try { return document.querySelector(selector); } catch (e) { return null; }
  };

  const rectForAnchor = (el) => {
    const r = el.getBoundingClientRect();
    const pad = 10;
    const top = clamp(r.top - pad, 10, window.innerHeight - 20);
    const left = clamp(r.left - pad, 10, window.innerWidth - 20);
    const width = clamp(r.width + (pad * 2), 24, window.innerWidth - left - 10);
    const height = clamp(r.height + (pad * 2), 24, window.innerHeight - top - 10);
    return { top, left, width, height, raw: r };
  };

  const positionPopover = (popover, holeRect) => {
    const margin = 14;
    const vw = window.innerWidth || 1200;
    const vh = window.innerHeight || 800;
    const preferredW = Math.min(420, vw - (margin * 2));
    const approxH = 180;

    let top = holeRect.top + holeRect.height + 12;
    let left = clamp(holeRect.left + (holeRect.width / 2) - (preferredW / 2), margin, vw - preferredW - margin);

    const spaceBelow = vh - top - margin;
    const spaceAbove = holeRect.top - margin;
    if (spaceBelow < approxH && spaceAbove > approxH) {
      top = Math.max(margin, holeRect.top - approxH - 12);
    }
    if (top + approxH > vh - margin) {
      top = Math.max(margin, vh / 2 - approxH / 2);
    }

    popover.style.width = `${preferredW}px`;
    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
    popover.style.right = 'auto';
    popover.style.bottom = 'auto';
  };

  const buildStorageKey = (id) => `webstats:ui_tour:${safeText(id, 'tour')}:done`;

  const Tour = () => {
    const state = {
      id: '',
      steps: [],
      index: 0,
      storageKey: '',
      active: false,
    };

    const root = ensureRoot();
    const hole = root.querySelector('[data-tour-hole]');
    const popover = root.querySelector('[data-tour-popover]');
    const title = root.querySelector('[data-tour-title]');
    const body = root.querySelector('[data-tour-body]');
    const progress = root.querySelector('[data-tour-progress]');
    const nextBtn = root.querySelector('[data-tour-next]');
    const prevBtn = root.querySelector('[data-tour-prev]');
    const skipBtn = root.querySelector('[data-tour-skip]');

    const close = (markDone = false) => {
      state.active = false;
      root.style.display = 'none';
      document.body.classList.remove('ui-tour-open');
      window.removeEventListener('resize', onReposition, true);
      window.removeEventListener('scroll', onReposition, true);
      document.removeEventListener('keydown', onKeydown, true);
      if (markDone && state.storageKey) {
        try { window.localStorage?.setItem(state.storageKey, '1'); } catch (e) { /* ignore */ }
      }
    };

    const onKeydown = (event) => {
      if (!state.active) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        close(false);
      }
      if (event.key === 'ArrowRight') next();
      if (event.key === 'ArrowLeft') prev();
    };

    const onReposition = () => {
      if (!state.active) return;
      renderStep(false);
    };

    const renderStep = (shouldScroll = true) => {
      if (!state.active) return;
      const step = state.steps[state.index];
      const el = resolveAnchor(step);
      if (!el) {
        // Salta pasos rotos.
        if (state.index < state.steps.length - 1) {
          state.index += 1;
          renderStep(shouldScroll);
        } else {
          close(true);
        }
        return;
      }

      const stepTitle = safeText(step.title, 'Tutorial');
      const stepBody = safeText(step.body, '');
      title.textContent = stepTitle;
      body.textContent = stepBody;
      progress.textContent = `${state.index + 1} / ${state.steps.length}`;
      prevBtn.disabled = state.index <= 0;
      nextBtn.textContent = state.index >= state.steps.length - 1 ? 'Terminar' : 'Siguiente';

      if (shouldScroll) {
        try { el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' }); } catch (e) { /* ignore */ }
      }

      const holeRect = rectForAnchor(el);
      hole.style.top = `${holeRect.top}px`;
      hole.style.left = `${holeRect.left}px`;
      hole.style.width = `${holeRect.width}px`;
      hole.style.height = `${holeRect.height}px`;

      positionPopover(popover, holeRect);
    };

    const next = () => {
      if (!state.active) return;
      if (state.index >= state.steps.length - 1) {
        close(true);
        return;
      }
      state.index += 1;
      renderStep(true);
    };

    const prev = () => {
      if (!state.active) return;
      if (state.index <= 0) return;
      state.index -= 1;
      renderStep(true);
    };

    nextBtn.addEventListener('click', next);
    prevBtn.addEventListener('click', prev);
    skipBtn.addEventListener('click', () => close(false));

    const start = (id, steps, options = {}) => {
      const normalizedSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
      if (!normalizedSteps.length) return false;
      state.id = safeText(id, 'tour');
      state.steps = normalizedSteps;
      state.index = 0;
      state.storageKey = safeText(options.storageKey) || buildStorageKey(state.id);
      state.active = true;
      root.style.display = 'flex';
      document.body.classList.add('ui-tour-open');
      window.addEventListener('resize', onReposition, true);
      window.addEventListener('scroll', onReposition, true);
      document.addEventListener('keydown', onKeydown, true);
      // Pequeño delay para que layout/offsets estén asentados.
      window.setTimeout(() => renderStep(true), 60);
      return true;
    };

    const startIfNeeded = (id, steps, options = {}) => {
      // Política producto: el tutorial NO debe auto-saltar. Solo se muestra:
      // - Si el usuario lo fuerza vía URL `?tour=1`
      // - O si el propio usuario lo lanza desde "Ayuda" (que usa `start()`)
      // - (Opcional interno) si se habilita explícitamente el auto-tutorial en localStorage
      //   `webstats:ui_tour:auto` = "1"
      const urlForce = (() => {
        try { return new URLSearchParams(window.location.search).get('tour') === '1'; } catch (e) { return false; }
      })();
      const autoEnabled = (() => {
        try { return safeText(window.localStorage?.getItem('webstats:ui_tour:auto')) === '1'; } catch (e) { return false; }
      })();
      if (!urlForce && !autoEnabled) return false;

      const storageKey = safeText(options.storageKey) || buildStorageKey(id);
      if (!urlForce) {
        try {
          const seen = safeText(window.localStorage?.getItem(storageKey));
          if (seen === '1') return false;
        } catch (e) { /* ignore */ }
      }
      return start(id, steps, { ...options, storageKey, force: true });
    };

    const reset = (id) => {
      const storageKey = buildStorageKey(id);
      try { window.localStorage?.removeItem(storageKey); } catch (e) { /* ignore */ }
    };

    return { start, startIfNeeded, reset, close };
  };

  window.WebstatsTour = window.WebstatsTour || Tour();
})();
