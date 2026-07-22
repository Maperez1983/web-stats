var cfg = window.__TASK_BUILDER_CONFIG || {};
		            // Pantalla de entrada (¿Qué quieres hacer?): selección (tap) + "Entrar" (ejecuta).
			            (function () {
		              const landing = document.getElementById('task-landing');
		              if (!landing) return;

              // Debug mínimo (solo visual): si WKWebView está tragándose los eventos, al menos veremos el contador subir.
              try {
                landing.setAttribute('data-debug', '1');
              } catch (e) { /* ignore */ }

	              const scopeKey = String(cfg.scopeKey || '').trim() || 'global';
	              const storageKey = `webstats:tpad:landing_hide_v1:${scopeKey}`;
	              const hideCheck = document.getElementById('task-landing-hide');
	              const shouldShow = (() => {
	                try {
	                  const params = new URLSearchParams(String(window.location.search || ''));
	                  return String(params.get('landing') || '') === '1';
	                } catch (e) {
	                  return false;
	                }
	              })();

	              const clearLandingParam = () => {
	                try {
	                  const url = new URL(window.location.href);
	                  url.searchParams.delete('landing');
	                  window.history.replaceState({}, '', url.toString());
	                } catch (e) { /* ignore */ }
	              };

              const setHiddenPref = () => {
                try {
                  if (hideCheck && hideCheck.checked) {
                    localStorage.setItem(storageKey, '1');
                  } else {
                    localStorage.removeItem(storageKey);
                  }
                } catch (e) { /* ignore */ }
              };

              const shouldHideLanding = () => {
                try { return localStorage.getItem(storageKey) === '1'; } catch (e) { return false; }
              };

		              const openLandingIfNeeded = () => {
		                if (shouldShow && !shouldHideLanding()) {
		                  // Asegura que el landing quede por encima de overlays insertados dinámicamente (PDF, etc.).
		                  try { document.body.appendChild(landing); } catch (e) { /* ignore */ }
		                  try { landing.hidden = false; } catch (e) { /* ignore */ }
		                }
		              };

	              const closeLanding = () => {
	                try { landing.hidden = true; } catch (e) { /* ignore */ }
	                clearLandingParam();
                  // Si estamos en modo pizarra, garantiza que el editor se cargue al cerrar.
                  try {
                    const wantsBoard = !!document.querySelector('#task-mode-tabs [data-task-mode=\"board\"].is-active,#task-mode-tabs [data-task-mode=\"both\"].is-active');
                    if (wantsBoard && typeof window.__webstatsEnsureEditorStack === 'function') {
                      window.__webstatsEnsureEditorStack();
                    }
                  } catch (e) { /* ignore */ }
	              };

              const clickFirst = (selector) => {
                const el = document.querySelector(selector);
                if (!el) return false;
                try { el.click(); } catch (e) { return false; }
                return true;
              };

              const activateTaskMode = (mode) => {
                if (!mode) return false;
                // Tabs superiores (Pizarra/Contenido).
                const btn = document.querySelector(`#task-mode-tabs [data-task-mode="${mode}"]`);
                if (btn) {
                  try { btn.click(); } catch (e) { /* ignore */ }
                  return true;
                }
                return false;
              };

              const activateSidePane = (pane) => {
                if (!pane) return false;
                const btn = document.querySelector(`#task-side-tabs [data-pane="${pane}"]`);
                if (btn) {
                  try { btn.click(); } catch (e) { /* ignore */ }
                  return true;
                }
                return false;
              };

	              landing.addEventListener('click', (ev) => {
	                // Click fuera de la tarjeta -> cerrar (no bloquear).
	                const card = landing.querySelector('.task-landing-card');
	                if (card && ev.target && card.contains(ev.target)) return;
	                setHiddenPref();
	                closeLanding();
	              });

              // iOS/WKWebView: por seguridad, enganchamos también a pointerdown/touchstart (capturing),
              // porque algunos overlays con backdrop-filter pueden “comerse” el click.
              const onAnyPress = (ev) => {
                try {
                  landing.dataset.lastPress = String(Date.now());
                } catch (e) { /* ignore */ }
              };
              try { landing.addEventListener('pointerdown', onAnyPress, { capture: true, passive: true }); } catch (e) { /* ignore */ }
              try { landing.addEventListener('touchstart', onAnyPress, { capture: true, passive: true }); } catch (e) { /* ignore */ }

              const choiceButtons = Array.from(landing.querySelectorAll('.task-landing-action[data-landing-go]') || []);
              const closeBtn = landing.querySelector('.task-landing-close[data-landing-go="close"]');
              let selectedAction = 'assistant';

              const normalizeAction = (value) => {
                const v = String(value || '').trim().toLowerCase();
                if (v === 'assistant' || v === 'config' || v === 'methodology' || v === 'load' || v === 'export' || v === 'board') return v;
                if (v === 'sheet' || v === 'text') return 'config';
                if (v === 'exportar') return 'export';
                return 'board';
              };
              const embeddedMode = document.body.classList.contains('embedded-task-builder');

              const setSelected = (actionRaw) => {
                selectedAction = normalizeAction(actionRaw);
                choiceButtons.forEach((btn) => {
                  const a = normalizeAction(btn.getAttribute('data-landing-go'));
                  const isOn = a === selectedAction;
                  btn.classList.toggle('is-selected', isOn);
                  try { btn.setAttribute('aria-pressed', isOn ? 'true' : 'false'); } catch (e) { /* ignore */ }
                });
              };

	              const runSelected = () => {
	                const action = normalizeAction(selectedAction);
	                if (action === 'assistant') {
	                  // En modo tácticas puede no existir "assistant": en ese caso solo cerramos.
	                  activateTaskMode('methodology');
	                  activateSidePane('assistant');
	                  closeLanding();
                  return;
                }
                if (action === 'config') {
                  activateTaskMode('config');
                  activateSidePane('ficha');
                  closeLanding();
                  return;
                }
                if (action === 'methodology') {
                  activateTaskMode('methodology');
                  activateSidePane('design');
                  closeLanding();
                  return;
                }
                if (action === 'load') {
                  activateTaskMode('load');
                  activateSidePane('load');
                  closeLanding();
                  return;
                }
                if (action === 'export') {
                  activateTaskMode('export');
                  activateSidePane('exportar');
                  closeLanding();
                  return;
                }
	                // board: solo entra.
                  try { if (typeof window.__webstatsEnsureEditorStack === 'function') window.__webstatsEnsureEditorStack(); } catch (e) { /* ignore */ }
	                closeLanding();
	              };

              const onChoice = (btn, ev) => {
                try { ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation?.(); } catch (e) { /* ignore */ }
                setSelected(btn.getAttribute('data-landing-go'));
              };

              // Delegación extra (robustez iPad/WKWebView): si un overlay/blur “rompe” el tap por botón,
              // capturamos en el contenedor y resolvemos el botón objetivo con `closest()`.
              const delegatedChoice = (ev) => {
                const btn = ev?.target?.closest?.('.task-landing-action[data-landing-go]');
                if (!btn) return;
                onChoice(btn, ev);
              };
              try { landing.addEventListener('pointerdown', delegatedChoice, { capture: true }); } catch (e) { /* ignore */ }
              try { landing.addEventListener('touchstart', delegatedChoice, { capture: true, passive: false }); } catch (e) { /* ignore */ }
              landing.addEventListener('click', delegatedChoice);

              choiceButtons.forEach((btn) => {
                btn.addEventListener('click', (ev) => onChoice(btn, ev));
                try { btn.addEventListener('touchstart', (ev) => onChoice(btn, ev), { capture: true, passive: false }); } catch (e) { /* ignore */ }
                // iOS/WKWebView: algunos taps no disparan click (o llegan tarde). Capturamos pointerdown.
                try { btn.addEventListener('pointerdown', (ev) => onChoice(btn, ev), { capture: true }); } catch (e) { /* ignore */ }
              });

              if (closeBtn) {
                const handler = (ev) => {
                  try { ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation?.(); } catch (e) { /* ignore */ }
                  try { setHiddenPref(); } catch (e) { /* ignore */ }
                  try { runSelected(); } catch (err) {
                    // Nunca dejes al usuario atrapado.
                    try { closeLanding(); } catch (e) { /* ignore */ }
                  }
                };
                closeBtn.addEventListener('click', handler);
                try { closeBtn.addEventListener('touchstart', handler, { capture: true, passive: false }); } catch (e) { /* ignore */ }
                try { closeBtn.addEventListener('pointerdown', handler, { capture: true }); } catch (e) { /* ignore */ }
              }

              // En modo embebido la ficha debe abrir directamente la pizarra real.
              if (embeddedMode) {
                setSelected('board');
                try { activateTaskMode('board'); } catch (e) { /* ignore */ }
                try { closeLanding(); } catch (e) { /* ignore */ }
                try {
                  window.requestAnimationFrame(() => {
                    try { if (typeof window.__webstatsEnsureEditorStack === 'function') window.__webstatsEnsureEditorStack(); } catch (err) { /* ignore */ }
                    try { document.getElementById('create-task-canvas')?.scrollIntoView({ block: 'start' }); } catch (err) { /* ignore */ }
                  });
                } catch (e) { /* ignore */ }
              } else {
                // Default: sugerimos Asistente (el usuario puede cambiar con 1 toque).
                try {
                  const params = new URLSearchParams(String(window.location.search || ''));
                  const pane = String(params.get('pane') || '').trim().toLowerCase();
                  if (pane === 'assistant') setSelected('assistant');
                  else setSelected('assistant');
                } catch (e) {
                  setSelected('assistant');
                }

	                // Mostrar solo cuando viene desde flujo rápido (ej: Sesiones → crear/editar).
	                openLandingIfNeeded();
              }
	            })();
