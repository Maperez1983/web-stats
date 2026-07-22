var cfg = window.__TASK_BUILDER_CONFIG || {};
						      window.addEventListener('DOMContentLoaded', () => {
				        const tacticsMode = document.getElementById('task-builder-form')?.dataset?.tacticsMode === '1';
				        if (tacticsMode) {
				          const form = document.getElementById('task-builder-form');
				          form?.addEventListener('submit', (ev) => {
				            ev.preventDefault();
				            try {
				              const status = document.getElementById('task-builder-status');
				              if (status) status.textContent = 'Táctica: guarda como clip en Playbook (no se crea tarea).';
				            } catch (e) {}
				            return false;
				          });
				        }
            // UX: "Añadir a sesión" visible (muchos usuarios no encuentran el selector dentro de la ficha lateral).
            try {
              const openBtn = document.getElementById('task-destination-open');
              const currentEl = document.getElementById('task-destination-current');
              const select = document.getElementById('draw-target-session');
              const showDestination = () => {
                if (!currentEl) return;
                if (!select) {
                  currentEl.textContent = '';
                  return;
                }
                const opt = select.options[select.selectedIndex];
                const txt = (opt && opt.textContent) ? String(opt.textContent).trim() : '';
                currentEl.textContent = select.value ? `Destino: ${txt}` : 'Destino: Biblioteca';
              };
              showDestination();
              if (select) select.addEventListener('change', showDestination);
              if (openBtn) {
                openBtn.addEventListener('click', () => {
                  const fichaTab = document.querySelector('.side-tab[data-pane=\"ficha\"]');
                  if (fichaTab) fichaTab.click();
                  if (select) {
                    try { select.focus({ preventScroll: true }); } catch (e) { try { select.focus(); } catch (err) {} }
                  }
                });
              }
            } catch (e) {}

				        // Contexto de pantalla (necesario en varios bloques del script).
	              // Nota: `isTacticsMode` ya está declarado en el head como `var` global para evitar
	              // `ReferenceError` en Safari cuando hay múltiples <script> tags.
	              try { isTacticsMode = window.__WEBSTATS_TACTICS_MODE === true; } catch (e) { /* ignore */ }
	              try {
	                window.__WEBSTATS_SUPPRESS_AUTO_TOUR = true;
	                document.body.classList.add('suppress-auto-tour');
	              } catch (e) { /* ignore */ }
	              try {
	                const closeTourForPitchControls = (event) => {
	                  try {
	                    const target = event?.target;
	                    if (!target || !target.closest) return;
	                    if (!target.closest('#pitch-view-menu,#surface-picker,#pitch-orientation-toggle,#pitch-orientation-toggle-quick,#pitch-zoom-out,#pitch-zoom-in,#pitch-zoom-reset,#pitch-size-down,#pitch-size-up,#pitch-size-fit,#pitch-grass-toggle,#pitch-grass-select,#pitch-ad-select')) return;
	                    if (window.WebstatsTour && typeof window.WebstatsTour.close === 'function') window.WebstatsTour.close();
	                    document.body.classList.remove('ui-tour-open');
	                    const root = document.getElementById('ui-tour-root');
	                    if (root) root.style.display = 'none';
	                  } catch (e) { /* ignore */ }
	                };
	                document.addEventListener('pointerdown', closeTourForPitchControls, true);
	                document.addEventListener('click', closeTourForPitchControls, true);
	              } catch (e) { /* ignore */ }

				        // Tutorial rápido (nuevos usuarios).
				        try {
			          const tour = window.WebstatsTour;
			          const tourId = 'task_builder_v1';
			          const steps = isTacticsMode ? ([
			            {
			              anchor: '.topbar .actions',
			              title: '1) Acciones rápidas',
		              body: 'Arriba tienes lo esencial (Volver, Ayuda y Vista compacta). Aquí no se crean tareas: se trabajan escenas y clips.',
		            },
		            {
		              anchor: '#task-pitch-stage',
		              title: '2) Pizarra táctica',
		              body: 'Añade jugadores, balón y trazos en el campo. Arrastra para mover y usa Deshacer/Rehacer.',
		            },
		            {
		              anchor: '#task-player-bank',
		              title: '3) Plantilla',
		              body: 'Arrastra jugadores reales del equipo a la pizarra. “Ocultar usados” evita duplicados.',
		            },
		            {
		              anchor: '#task-side-tabs',
		              title: '4) Panel táctico',
		              body: 'Playbook guarda clips, Escenarios crea secuencias, Capas organiza el dibujo y Exportar descarga PNG/JSON.',
		            },
		            {
		              anchor: 'button.side-tab[data-pane=\"playbook\"]',
		              title: '5) Guardar clip',
		              body: 'En Playbook puedes abrir el Simulador y guardar la jugada como clip reutilizable.',
		            },
		            {
		              anchor: 'button.side-tab[data-pane=\"exportar\"]',
		              title: '6) Exportar',
		              body: 'Exporta PNG/HD o JSON para compartir o reusar. El “Pack” está en Playbook.',
		            },
		          ]) : ([
		            {
		              anchor: '.topbar .actions',
		              title: '1) Acciones rápidas',
		              body: 'Arriba tienes lo esencial (Volver, Ayuda y Vista compacta). En “Opciones” están las acciones extra (PDF UEFA/Club, compartir, etc.).',
		            },
		            {
		              anchor: '#task-pitch-stage',
		              title: '2) Pizarra',
		              body: 'Pulsa un recurso (jugador, cono, línea…) y haz clic en el campo para colocarlo. Arrastra para mover y usa Deshacer si te equivocas.',
		            },
		            {
		              anchor: '#task-player-bank',
		              title: '3) Jugadores',
				              body: 'Desde la plantilla de jugadores puedes añadir fichas a la pizarra. “Ocultar usados” evita duplicados.',
		            },
		            {
		              anchor: '#task-side-tabs',
		              title: '4) Panel lateral',
		              body: 'Aquí organizas la edición en bloques claros: Configuración, Metodología y Carga. Las utilidades extra quedan en segundo plano.',
		            },
		            {
		              anchor: '#task-methodology-card',
		              title: '5) Metodología',
		              body: 'En Metodología defines principios, organización, progresiones y criterios de éxito sin mezclarlo con la carga.',
		            },
		            {
		              anchor: 'button.side-tab[data-pane=\"preview\"]',
		              title: '6) Vista previa y PDF',
		              body: 'En “Vista previa” verás cómo quedará. El PDF se genera con “Imprimir UEFA/Club”.',
		            },
		            {
		              anchor: '.submit-row .primary',
		              title: '7) Guardar',
		              body: 'Cuando termines, pulsa “Guardar/Crear tarea”.',
		            },
		          ]);

		          const helpBtn = document.getElementById('task-builder-help');
		          if (helpBtn && tour) {
		            helpBtn.addEventListener('click', () => tour.start(tourId, steps, { force: true }));
		          }

		          // Permite que la guía global (barra superior) lance el tutorial específico de esta pantalla.
		          window.__WEBSTATS_PAGE_TOUR_ID = tourId;
		          window.__WEBSTATS_PAGE_TOUR_STEPS = steps;

		          const isNew = !String(document.getElementById('task-builder-form')?.dataset?.taskId || '').trim();
		          const urlForce = (() => {
		            try { return new URLSearchParams(window.location.search).get('tour') === '1'; } catch (e) { return false; }
		          })();
		          // Importante: en modo Táctica no auto-lanzamos el tutorial porque bloquea clics con el backdrop
		          // (en app nativa se percibe como “los botones no funcionan”). Solo se lanza manualmente:
		          // - Botón “Ayuda” (arriba)
		          // - `?tour=1`
		          if (tour) {
		            if (urlForce) {
		              tour.start(tourId, steps, { force: true });
		            } else if (!isTacticsMode) {
		              tour.startIfNeeded(tourId, steps, { force: isNew });
		            }
		          }
		        } catch (e) { /* ignore */ }

			        const compactKey = 'webstats:tpad:compact';
			        const toggleBtn = document.getElementById('task-builder-compact-toggle');
	              const guideKey = 'webstats:tpad:guide';
	              const guideBtn = document.getElementById('task-builder-simple-toggle');
	              const guideHint = document.getElementById('task-simple-hint');
                const modeLabel = document.getElementById('task-mode-label');
                const quickInsertBtn = document.getElementById('task-quick-insert');
                const quickMoveBtn = document.getElementById('task-quick-move');
                const quickDrawBtn = document.getElementById('task-quick-draw');
                const quickClipsBtn = document.getElementById('task-quick-clips');
			        const playerBank = document.getElementById('task-player-bank');
		        const playerPrev = document.getElementById('player-bank-prev');
		        const playerNext = document.getElementById('player-bank-next');
        const applyCompact = (enabled) => {
          document.body.classList.toggle('is-compact', !!enabled);
          if (toggleBtn) {
            toggleBtn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
            toggleBtn.textContent = enabled ? 'Vista normal' : 'Vista compacta';
          }
        };
        let isCompact = false;
        try {
          isCompact = window.localStorage?.getItem(compactKey) === '1';
        } catch (error) {
          isCompact = false;
        }
	        applyCompact(isCompact);
	        if (toggleBtn) {
	          toggleBtn.addEventListener('click', () => {
	            isCompact = !isCompact;
            try {
              window.localStorage?.setItem(compactKey, isCompact ? '1' : '0');
            } catch (error) {}
            applyCompact(isCompact);
	          });
	        }

	          const applyGuide = (enabled) => {
	            const on = !!enabled;
	            if (guideBtn) guideBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
	            if (guideHint) guideHint.hidden = !on;
	          };
		          let guideOn = false;
		          try {
		            const raw = window.localStorage?.getItem(guideKey);
		            guideOn = raw == null ? false : raw === '1';
		          } catch (e) {
		            guideOn = false;
		          }
	          applyGuide(guideOn);
	          if (guideBtn) {
	            guideBtn.addEventListener('click', () => {
	              guideOn = !guideOn;
	              try { window.localStorage?.setItem(guideKey, guideOn ? '1' : '0'); } catch (e) {}
	              applyGuide(guideOn);
	            });
	          }

                const setMode = (mode) => {
                  const next = String(mode || 'move');
                  document.body.classList.toggle('mode-insert', next === 'insert');
                  document.body.classList.toggle('mode-draw', next === 'draw');
                  document.body.classList.toggle('mode-move', next === 'move');
                  if (modeLabel) modeLabel.textContent = next === 'insert' ? 'Insertar' : next === 'draw' ? 'Dibujar' : 'Mover';
                };
                const isBtnActive = (selector) => {
                  try { return !!document.querySelector(selector)?.classList?.contains('is-active'); } catch (e) { return false; }
                };
                const ensureToolOff = (selector) => {
                  try {
                    const btn = document.querySelector(selector);
                    if (btn && btn.classList.contains('is-active')) btn.click();
                  } catch (e) { /* ignore */ }
                };
                const ensureToolOn = (selector) => {
                  try {
                    const btn = document.querySelector(selector);
                    if (btn && !btn.classList.contains('is-active')) btn.click();
                  } catch (e) { /* ignore */ }
                };
                const enterMoveMode = () => {
                  ensureToolOff('button[data-action=\"pencil_pro\"]');
                  ensureToolOff('button[data-action=\"draw_free\"]');
                  setMode('move');
                  try { const s = document.getElementById('task-builder-status'); if (s) s.textContent = 'Modo mover: arrastra fichas, pellizca para zoom.'; } catch (e) {}
                };
                const enterDrawMode = () => {
                  ensureToolOn('button[data-action=\"pencil_pro\"]');
                  setMode('draw');
                  try { const s = document.getElementById('task-builder-status'); if (s) s.textContent = 'Modo dibujar: usa Apple Pencil para dibujar (el dedo navega).'; } catch (e) {}
                };
                const enterInsertMode = () => {
                  setMode('insert');
                  try {
                    try { window.__webstatsTpadSetLibraryCollapsed?.(false); } catch (e) {}
                    try { if (document.body.classList.contains('library-collapsed')) document.getElementById('task-library-toggle')?.click?.(); } catch (e) {}
                    try { document.getElementById('task-library-filter')?.focus?.({ preventScroll: true }); } catch (e) { try { document.getElementById('task-library-filter')?.focus?.(); } catch (err) {} }
                  } catch (e) {}
                  try { const s = document.getElementById('task-builder-status'); if (s) s.textContent = 'Modo insertar: elige un recurso y toca el campo para colocarlo.'; } catch (e) {}
                };
                const openClipsOrScenarios = () => {
                  try {
                    const tacticsToggle = document.getElementById('task-tactics-panel-toggle');
                    const toolsToggle = document.getElementById('task-tactics-tools-toggle');
                    if (tacticsToggle) {
                      try { if (toolsToggle && toolsToggle.getAttribute('aria-pressed') === 'true') toolsToggle.click(); } catch (e) {}
                      tacticsToggle.click();
                      return;
                    }
                  } catch (e) { /* ignore */ }
                  try {
                    const btn = document.getElementById('task-scenarios-btn');
                    if (btn) btn.click();
                  } catch (e) { /* ignore */ }
                };
                quickInsertBtn?.addEventListener('click', (e) => { e.preventDefault(); enterInsertMode(); });
                quickMoveBtn?.addEventListener('click', (e) => { e.preventDefault(); enterMoveMode(); });
                quickDrawBtn?.addEventListener('click', (e) => { e.preventDefault(); enterDrawMode(); });
                quickClipsBtn?.addEventListener('click', (e) => { e.preventDefault(); openClipsOrScenarios(); });
                // Estado inicial del pill
                if (isBtnActive('button[data-action=\"pencil_pro\"]') || isBtnActive('button[data-action=\"draw_free\"]')) setMode('draw');
                else setMode('move');

	        const scrollPlayerBank = (dir) => {
	          if (!playerBank) return;
	          const amount = Math.max(240, Math.round((playerBank.clientWidth || 480) * 0.85));
	          playerBank.scrollBy({ left: dir * amount, top: 0, behavior: 'smooth' });
	        };
        playerPrev?.addEventListener('click', () => scrollPlayerBank(-1));
        playerNext?.addEventListener('click', () => scrollPlayerBank(1));
        // En modo compacto, permite rueda vertical para scroll horizontal (trackpad/mouse).
	        if (playerBank) {
	          playerBank.addEventListener('wheel', (event) => {
	            if (!document.body.classList.contains('is-compact')) return;
	            if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
	            playerBank.scrollLeft += event.deltaY;
	            event.preventDefault();
	          }, { passive: false });
	        }

	        // Multipizarra (opcional): solo afecta a cómo se imprime el PDF (y a la comunicación en UI).
	        const multiToggle = document.getElementById('task-multi-board-toggle');
	        const updateMultiUi = () => {
	          const enabled = !!(multiToggle && multiToggle.checked);
	          document.body.classList.toggle('has-multi-board', enabled);
	        };
	        if (multiToggle) multiToggle.addEventListener('change', updateMultiUi);
	        updateMultiUi();

				          const initTaskAssistant = () => {
				          const form = document.getElementById('task-builder-form');
				          const programEl = document.getElementById('task-assistant-program');
				          const levelEl = document.getElementById('task-assistant-level');
				          const minutesEl = document.getElementById('task-assistant-minutes');
				          const applyBoardEl = document.getElementById('task-assistant-apply-board');
				          const clearBoardEl = document.getElementById('task-assistant-clear-board');
				          const blueprintNameEl = document.getElementById('task-assistant-blueprint-name');
				          const blueprintSaveBtn = document.getElementById('task-assistant-blueprint-save');
				          const blueprintsUrl = String(form?.dataset?.assistantBlueprintsUrl || '').trim();
				          const blueprintsSaveUrl = String(form?.dataset?.assistantBlueprintsSaveUrl || '').trim();
				          const knowledgeFilesEl = document.getElementById('task-assistant-knowledge-files');
				          const knowledgeUploadBtn = document.getElementById('task-assistant-knowledge-upload');
				          const knowledgeUrl = String(form?.dataset?.assistantKnowledgeUrl || '').trim();
				          const knowledgeUploadUrl = String(form?.dataset?.assistantKnowledgeUploadUrl || '').trim();
				          const csrfToken = String(form?.querySelector('input[name=csrfmiddlewaretoken]')?.value || '').trim();
				          const coachDictionaryUrl = String(cfg.coachDictionaryUrl || '');
				          let coachDictionary = null;
				          let coachDictionaryLoaded = false;
				          const loadCoachDictionary = async () => {
				            if (coachDictionaryLoaded) return coachDictionary;
				            coachDictionaryLoaded = true;
				            try {
				              const res = await fetch(coachDictionaryUrl, { credentials: 'same-origin' });
				              const data = res.ok ? await res.json() : null;
				              if (data && typeof data === 'object') coachDictionary = data;
				            } catch (e) {
				              coachDictionary = null;
				            }
				            return coachDictionary;
				          };
				          let assistantBlueprints = [];
				          let assistantBlueprintsLoaded = false;
				          const reloadAssistantBlueprints = async () => {
				            assistantBlueprintsLoaded = false;
				            assistantBlueprints = [];
				            return loadAssistantBlueprints();
				          };
				          const loadAssistantBlueprints = async () => {
				            if (assistantBlueprintsLoaded) return assistantBlueprints;
				            assistantBlueprintsLoaded = true;
				            if (!blueprintsUrl) return assistantBlueprints;
				            try {
				              const res = await fetch(blueprintsUrl, { credentials: 'same-origin' });
				              const data = res.ok ? await res.json() : null;
				              const items = Array.isArray(data?.items) ? data.items : [];
				              assistantBlueprints = items;
				            } catch (err) {
				              assistantBlueprints = [];
				            }
				            return assistantBlueprints;
				          };
				          if (!form || !programEl || !levelEl || !minutesEl) return;

				          // Cargamos en segundo plano para tenerlas disponibles en sugerencias.
				          try { loadAssistantBlueprints(); } catch (e) {}
				          try { loadCoachDictionary(); } catch (e) {}

		          const toInt = (value, fallback) => {
		            const parsed = Number.parseInt(String(value || ''), 10);
		            return Number.isFinite(parsed) ? parsed : fallback;
		          };

		          const getField = (name) => {
		            if (!form.elements) return null;
		            const node = form.elements.namedItem(name);
		            if (!node) return null;
		            if (node instanceof RadioNodeList) return node;
		            return node;
		          };

		          const setValue = (name, value) => {
		            const field = getField(name);
		            if (!field) return;
		            if (field instanceof RadioNodeList) {
		              const arr = Array.from(field).filter(Boolean);
		              arr.forEach((item) => {
		                try { item.checked = String(item.value || '') === String(value || ''); } catch (err) {}
		              });
		              return;
		            }
		            try {
		              field.value = value == null ? '' : String(value);
		              field.dispatchEvent(new Event('input', { bubbles: true }));
		              field.dispatchEvent(new Event('change', { bubbles: true }));
		            } catch (err) {}
		          };

					          const setRichHtml = (plainName, html) => {
				            const wrapper = form.querySelector(`[data-rich-editor][data-rich-name="${plainName}"]`);
			            if (!wrapper) {
			              setValue(plainName, String(html || '').replace(/<[^>]*>/g, ''));
			              return;
			            }
		            const area = wrapper.querySelector('[data-rich-area]');
		            const plainField = getField(plainName);
		            const htmlName = wrapper.getAttribute('data-rich-html-name') || '';
		            const htmlField = htmlName ? getField(htmlName) : null;
		            const safeHtml = String(html || '').trim();
		            try {
		              if (area) {
		                area.innerHTML = safeHtml || '';
		                area.dispatchEvent(new Event('input', { bubbles: true }));
		              }
		              if (plainField && !(plainField instanceof RadioNodeList)) {
		                plainField.value = String((area && (area.innerText || area.textContent)) || '').trim();
		              }
		              if (htmlField && !(htmlField instanceof RadioNodeList)) {
		                htmlField.value = safeHtml;
		              }
			            } catch (err) {}
					          };

					          // --- Rival + plantilla (scouting) ---
					          (function () {
					            const rosterApiUrl = String(cfg.rivalRosterApiUrl || '').trim();
					            const select = document.getElementById('task-opponent-select');
					            const filter = document.getElementById('task-opponent-player-filter');
					            const statusEl = document.getElementById('task-opponent-status');
					            const tbody = document.getElementById('task-opponent-roster-body');
                      const tokenBank = document.getElementById('task-opponent-token-bank');
                      const tokenBankSection = document.getElementById('task-opponent-bank-section');
					            const hiddenTeamId = document.getElementById('draw-task-opponent-team-id');
					            const hiddenName = document.getElementById('draw-task-opponent-name');
					            const hiddenCode = document.getElementById('draw-task-opponent-team-code');
					            const hiddenPlayers = document.getElementById('draw-task-opponent-players-json');
					            const btnCoaching = document.getElementById('task-opponent-apply-coaching');
					            const btnRules = document.getElementById('task-opponent-apply-rules');
					            const btnCopy = document.getElementById('task-opponent-copy');
					            if (!select || !tbody) return;

					            const isTacticsMode = !!document.body?.classList?.contains('tactics-mode');
					            const storageKey = isTacticsMode ? '2j_tactics_opponent' : '2j_task_opponent';

					            const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
					              '&': '&amp;',
					              '<': '&lt;',
					              '>': '&gt;',
					              '"': '&quot;',
					              "'": '&#39;',
					            }[ch] || ch));

					            const safeJsonParse = (raw, fallback) => {
					              try { return JSON.parse(String(raw || '')); } catch (e) { return fallback; }
					            };

					            const readSelectedPlayers = () => {
					              const arr = safeJsonParse(hiddenPlayers?.value || '[]', []);
					              const list = Array.isArray(arr) ? arr : [];
					              const norm = [];
					              const seen = new Set();
					              list.forEach((x) => {
					                const v = String(x || '').trim();
					                if (!v || seen.has(v)) return;
					                seen.add(v);
					                norm.push(v.slice(0, 160));
					              });
					              return norm.slice(0, 40);
					            };

                      const renderTokenBank = (items) => {
                        if (!tokenBank) return;
                        const list = Array.isArray(items) ? items : [];
                        if (!list.length) {
                          tokenBank.textContent = '';
                          tokenBank.hidden = true;
                          try { if (tokenBankSection) tokenBankSection.hidden = true; } catch (e) {}
                          return;
                        }
                        try { if (tokenBankSection) tokenBankSection.hidden = false; } catch (e) {}
                        tokenBank.hidden = false;
                        tokenBank.textContent = '';
                        list.slice(0, 60).forEach((p) => {
                          const name = String(p?.name || '').trim();
                          if (!name) return;
                          const num = String(p?.number || '').trim().slice(0, 6);
                          const btn = document.createElement('button');
                          btn.type = 'button';
                          btn.className = 'player-token-bank';
                          btn.setAttribute('title', name);
                          const label = document.createElement('span');
                          label.className = 'token-name';
                          label.textContent = name;
                          const badge = document.createElement('span');
                          badge.className = 'token-disk';
                          const number = document.createElement('span');
                          number.className = 'token-number';
                          number.textContent = num ? num.slice(0, 2) : 'R';
                          badge.appendChild(number);
                          btn.appendChild(label);
                          btn.appendChild(badge);

                          // Click → activa inserción en el Tactical Pad (si la API está disponible).
                          btn.addEventListener('click', () => {
                            try {
                              if (window.__webstatsTpadActivateRivalToken) {
                                window.__webstatsTpadActivateRivalToken(name, num);
                              }
                            } catch (e) {}
                          });
                          // Drag & drop → coloca directamente en el campo.
                          const wireDnD = () => {
                            try {
                              if (!window.__webstatsTpadRegisterDraggableButton) return false;
                              window.__webstatsTpadRegisterDraggableButton(btn, () => ({
                                kind: 'player_rival',
                                playerName: name,
                                playerNumber: num,
                              }));
                              return true;
                            } catch (e) {
                              return false;
                            }
                          };
                          if (!wireDnD()) {
                            // Si el Tactical Pad termina de inicializar después, lo reintentamos una vez.
                            window.setTimeout(wireDnD, 800);
                          }
                          tokenBank.appendChild(btn);
                        });
                      };
					            const writeSelectedPlayers = (players) => {
					              const list = Array.isArray(players) ? players : [];
					              try {
					                if (hiddenPlayers) hiddenPlayers.value = JSON.stringify(list.slice(0, 40));
					              } catch (e) {}
					              try {
					                const payload = {
					                  v: 1,
					                  at: new Date().toISOString(),
					                  opponent_name: String(hiddenName?.value || '').trim(),
					                  opponent_team_id: String(hiddenTeamId?.value || '').trim(),
					                  opponent_team_code: String(hiddenCode?.value || '').trim(),
					                  players: list.slice(0, 40),
					                };
					                window.localStorage && window.localStorage.setItem(storageKey, JSON.stringify(payload));
					              } catch (e) {}
					            };

					            const syncHiddenOpponent = () => {
					              const opt = select.selectedOptions && select.selectedOptions.length ? select.selectedOptions[0] : null;
					              const teamId = String(opt ? (opt.value || '') : '').trim();
					              const fullName = String(opt ? (opt.getAttribute('data-full-name') || opt.textContent || '') : '').trim();
					              const code = String(opt ? (opt.getAttribute('data-team-code') || '') : '').trim();
					              try { if (hiddenTeamId) hiddenTeamId.value = teamId && teamId !== '0' ? teamId : ''; } catch (e) {}
					              try { if (hiddenName) hiddenName.value = fullName || ''; } catch (e) {}
					              try { if (hiddenCode) hiddenCode.value = code || ''; } catch (e) {}
					            };

					            const renderRows = (items) => {
					              const selected = new Set(readSelectedPlayers().map((x) => String(x || '').trim()));
					              const q = String(filter?.value || '').trim().toLowerCase();
					              const rows = Array.isArray(items) ? items : [];
					              const visible = q ? rows.filter((x) => String(x?.name || '').toLowerCase().includes(q)) : rows;
                        try { renderTokenBank(visible); } catch (e) {}

					              tbody.textContent = '';
					              if (!visible.length) {
					                const tr = document.createElement('tr');
					                tr.innerHTML = '<td colspan="7" class="meta" style="padding:0.75rem 0.6rem;">Sin jugadores (o filtro sin resultados).</td>';
					                tbody.appendChild(tr);
					                return;
					              }

					              visible.forEach((p) => {
					                const name = String(p?.name || '').trim();
					                if (!name) return;
					                const tr = document.createElement('tr');
					                const checked = selected.has(name);
					                tr.innerHTML = [
					                  '<td><input type="checkbox" class="task-opponent-pick" value="' + escapeHtml(name) + '"' + (checked ? ' checked' : '') + ' /></td>',
					                  '<td><strong>' + escapeHtml(name) + '</strong></td>',
					                  '<td class="meta">' + escapeHtml(String(p?.position || '-')) + '</td>',
					                  '<td class="meta">' + escapeHtml(String(p?.minutes || '-')) + '</td>',
					                  '<td class="meta">' + escapeHtml(String(p?.goals || '-')) + '</td>',
					                  '<td class="meta">' + escapeHtml(String(p?.yellow_cards || '-')) + '</td>',
					                  '<td class="meta">' + escapeHtml(String(p?.red_cards || '-')) + '</td>',
					                ].join('');
					                tbody.appendChild(tr);
					              });

					              Array.from(tbody.querySelectorAll('input.task-opponent-pick') || []).forEach((cb) => {
					                cb.addEventListener('change', () => {
					                  const name = String(cb.value || '').trim();
					                  const current = readSelectedPlayers();
					                  const set = new Set(current);
					                  if (cb.checked) set.add(name);
					                  else set.delete(name);
					                  writeSelectedPlayers(Array.from(set));
					                });
					              });
					            };

					            const fetchRoster = async () => {
					              syncHiddenOpponent();
					              const teamId = String(hiddenTeamId?.value || '').trim();
					              const teamCode = String(hiddenCode?.value || '').trim();
					              const rivalName = String(hiddenName?.value || '').trim();
					              if (!teamId && !teamCode && !rivalName) {
					                renderRows([]);
					                if (statusEl) statusEl.textContent = '';
					                return;
					              }
					              if (!rosterApiUrl) {
					                if (statusEl) statusEl.textContent = 'No se encontró el endpoint de plantilla rival.';
					                renderRows([]);
					                return;
					              }
					              if (statusEl) statusEl.textContent = 'Cargando plantilla rival…';
					              try {
					                const u = new URL(rosterApiUrl, window.location.origin);
					                if (teamId) u.searchParams.set('rival_team_id', teamId);
					                if (teamCode) u.searchParams.set('team_code', teamCode);
					                if (rivalName) u.searchParams.set('rival_name', rivalName);
					                const res = await fetch(u.toString(), { credentials: 'same-origin' });
					                const data = res.ok ? await res.json() : null;
					                if (!res.ok || !data?.ok) throw new Error(String(data?.error || 'No se pudo cargar.'));
					                const items = Array.isArray(data?.items) ? data.items : [];
					                const updatedAt = String(data?.snapshot?.updated_at || '').trim();
					                const warning = String(data?.warning || '').trim();
					                const msg = warning
					                  ? warning
					                  : (updatedAt ? `Plantilla cargada · ${items.length} jugadores · actualizado ${updatedAt.split('T')[0]}` : `Plantilla cargada · ${items.length} jugadores`);
					                if (statusEl) statusEl.textContent = msg;
					                renderRows(items);
					              } catch (e) {
					                if (statusEl) statusEl.textContent = 'No se pudo cargar la plantilla del rival. Usa “Análisis → Rivales” para prepararla.';
					                renderRows([]);
					              }
					            };

					            const appendToRich = (plainName, title, names) => {
					              const list = Array.isArray(names) ? names.map((x) => String(x || '').trim()).filter(Boolean) : [];
					              if (!list.length) return false;
					              const wrapper = form.querySelector(`[data-rich-editor][data-rich-name="${plainName}"]`);
					              const htmlName = wrapper ? (wrapper.getAttribute('data-rich-html-name') || '') : '';
					              const htmlField = htmlName ? getField(htmlName) : null;
					              const current = String((htmlField && !(htmlField instanceof RadioNodeList)) ? (htmlField.value || '') : '');
					              const bulletHtml = '<ul>' + list.map((n) => `<li><strong>${escapeHtml(n)}</strong>: …</li>`).join('') + '</ul>';
					              const block = `<p><strong>${escapeHtml(title || 'Rival')}</strong></p>${bulletHtml}`;
					              const merged = (current && current.trim()) ? (current.trim() + '\\n' + block) : block;
					              setRichHtml(plainName, merged);
					              return true;
					            };

					            btnCoaching?.addEventListener('click', () => {
					              const names = readSelectedPlayers();
					              const rivalName = String(hiddenName?.value || '').trim() || 'Rival';
					              if (!names.length) return window.alert('Marca al menos un jugador del rival.');
					              const ok = appendToRich('draw_task_coaching_points', `Jugadores a vigilar (vs ${rivalName})`, names);
					              if (ok) window.alert('Añadido a consignas.');
					            });
					            btnRules?.addEventListener('click', () => {
					              const names = readSelectedPlayers();
					              const rivalName = String(hiddenName?.value || '').trim() || 'Rival';
					              if (!names.length) return window.alert('Marca al menos un jugador del rival.');
					              const ok = appendToRich('draw_task_confrontation_rules', `Reglas vs ${rivalName} (jugadores clave)`, names);
					              if (ok) window.alert('Añadido a reglas.');
					            });
					            btnCopy?.addEventListener('click', async () => {
					              const names = readSelectedPlayers();
					              if (!names.length) return window.alert('Marca al menos un jugador del rival.');
					              const text = names.join('\\n');
					              try {
					                if (navigator.clipboard && navigator.clipboard.writeText) {
					                  await navigator.clipboard.writeText(text);
					                  window.alert('Copiado al portapapeles.');
					                  return;
					                }
					              } catch (e) {}
					              try {
					                const ta = document.createElement('textarea');
					                ta.value = text;
					                ta.style.position = 'fixed';
					                ta.style.left = '-9999px';
					                document.body.appendChild(ta);
					                ta.focus();
					                ta.select();
					                document.execCommand('copy');
					                document.body.removeChild(ta);
					                window.alert('Copiado al portapapeles.');
					              } catch (e) {
					                window.alert(text);
					              }
					            });

					            select.addEventListener('change', () => {
					              writeSelectedPlayers(readSelectedPlayers());
					              fetchRoster();
					            });
					            filter?.addEventListener('input', () => {
					              // Re-render sin volver a pedir al servidor: usamos dataset en el tbody actual si existe.
					              // Si no hay filas, simplemente no hace nada.
					              try {
					                const rows = Array.from(tbody.querySelectorAll('tr') || []);
					                if (!rows.length) return;
					                // Forzamos recarga desde servidor si aún no se cargó nada.
					                const hasCheckbox = !!tbody.querySelector('input.task-opponent-pick');
					                if (!hasCheckbox) return;
					                // Extrae info desde DOM actual.
					                const items = rows
					                  .map((tr) => {
					                    const strong = tr.querySelector('strong');
					                    const tds = tr.querySelectorAll('td');
					                    const name = String(strong?.textContent || '').trim();
					                    if (!name) return null;
					                    const getTd = (idx) => String((tds && tds[idx] ? tds[idx].textContent : '') || '').trim();
					                    return { name, position: getTd(2), minutes: getTd(3), goals: getTd(4), yellow_cards: getTd(5), red_cards: getTd(6) };
					                  })
					                  .filter(Boolean);
					                renderRows(items);
					              } catch (e) {}
					            });

					            // Boot: si venimos desde “Análisis rival → Crear tarea específica”.
					            try {
					              const url = new URL(window.location.href);
					              const prefill = String(url.searchParams.get('prefill') || '').trim().toLowerCase();
					              if (prefill === 'rival_roster') {
					                const seedRaw = window.localStorage && window.localStorage.getItem('2j_rival_task_seed');
					                const seed = seedRaw ? safeJsonParse(seedRaw, null) : null;
					                if (seed && typeof seed === 'object' && String(seed.kind || '') === 'rival_roster') {
					                  const rivalName = String(seed.rival_name || '').trim();
					                  const players = Array.isArray(seed.players) ? seed.players.map((x) => String(x || '').trim()).filter(Boolean) : [];
					                  if (rivalName) {
					                    // Intenta seleccionar opción por nombre.
					                    const opts = Array.from(select.options || []);
					                    const match = opts.find((o) => String(o.getAttribute('data-full-name') || o.textContent || '').toLowerCase().includes(rivalName.toLowerCase()));
					                    if (match) select.value = String(match.value || '');
					                    syncHiddenOpponent();
					                  }
					                  if (players.length) writeSelectedPlayers(players);
					                  try { window.localStorage && window.localStorage.removeItem('2j_rival_task_seed'); } catch (e) {}
					                }
					              }
					            } catch (e) {}

					            // Boot normal: restaura última selección (útil en tácticas).
					            try {
					              if (!String(hiddenName?.value || '').trim()) {
					                const raw = window.localStorage && window.localStorage.getItem(storageKey);
					                const stored = raw ? safeJsonParse(raw, null) : null;
					                if (stored && typeof stored === 'object') {
					                  const storedName = String(stored.opponent_name || '').trim();
					                  const storedPlayers = Array.isArray(stored.players) ? stored.players : [];
					                  if (storedName) {
					                    const opts = Array.from(select.options || []);
					                    const match = opts.find((o) => String(o.getAttribute('data-full-name') || o.textContent || '').toLowerCase().includes(storedName.toLowerCase()));
					                    if (match) select.value = String(match.value || '');
					                    syncHiddenOpponent();
					                  }
					                  if (storedPlayers.length) writeSelectedPlayers(storedPlayers);
					                }
					              }
					            } catch (e) {}

					            // Carga inicial si hay rival seleccionado.
					            fetchRoster();
					          })();

					          const drillsInput = document.getElementById('draw-task-drills-json');
					          const drillsPicker = document.getElementById('task-drills-picker');
					          const drillsFilter = document.getElementById('task-drills-filter');
				          const drillsAge = document.getElementById('task-drills-age');
				          const drillsSearch = document.getElementById('task-drills-search');
				          const parseJsonList = (value) => {
				            const raw = String(value || '').trim();
				            if (!raw) return [];
				            if (!(raw.startsWith('[') && raw.endsWith(']'))) return [];
				            try {
				              const parsed = JSON.parse(raw);
				              return Array.isArray(parsed) ? parsed.map((v) => String(v || '').trim()).filter(Boolean) : [];
				            } catch (err) {
				              return [];
				            }
				          };
						          const writeDrills = (ids) => {
						            const safe = Array.isArray(ids) ? ids.map((v) => String(v || '').trim()).filter(Boolean) : [];
						            const deduped = [];
						            const seen = new Set();
						            safe.forEach((id) => {
						              if (!id || seen.has(id)) return;
						              seen.add(id);
						              deduped.push(id);
						            });
					            try {
					              if (drillsInput) {
					                drillsInput.value = JSON.stringify(deduped);
					                drillsInput.dispatchEvent(new Event('change', { bubbles: true }));
					              }
					            } catch (err) {}
					            try {
					              if (!drillsPicker) return;
					              Array.from(drillsPicker.querySelectorAll('input[type="checkbox"][data-drill-id]')).forEach((cb) => {
					                const id = String(cb.getAttribute('data-drill-id') || '').trim();
					                cb.checked = !!(id && deduped.includes(id));
					              });
					            } catch (err) {}
					          };
				          const readDrills = () => {
				            const current = parseJsonList(drillsInput?.value);
				            if (current.length) return current;
				            const ids = [];
				            if (!drillsPicker) return ids;
				            Array.from(drillsPicker.querySelectorAll('input[type="checkbox"][data-drill-id]')).forEach((cb) => {
				              if (!cb.checked) return;
				              const id = String(cb.getAttribute('data-drill-id') || '').trim();
				              if (id) ids.push(id);
				            });
				            return ids;
				          };

					          try {
					            if (drillsPicker && drillsInput) {
					              // Normaliza valor inicial y engancha eventos.
					              writeDrills(readDrills());
				              Array.from(drillsPicker.querySelectorAll('input[type="checkbox"][data-drill-id]')).forEach((cb) => {
				                cb.addEventListener('change', () => {
				                  const id = String(cb.getAttribute('data-drill-id') || '').trim();
				                  let ids = readDrills();
				                  ids = Array.isArray(ids) ? ids.slice() : [];
				                  if (cb.checked) {
				                    // Añade al final (orden de selección).
				                    ids.push(id);
				                  } else {
				                    ids = ids.filter((x) => String(x || '').trim() !== id);
				                  }
				                  writeDrills(ids);
				                });
				              });
					            }
					          } catch (err) {}

					          // Añadir pictogramas a la pizarra (se pueden mover/arrastrar dentro del campo).
					          try {
					            Array.from(drillsPicker?.querySelectorAll('button[data-drill-add]') || []).forEach((btn) => {
					              btn.addEventListener('click', (event) => {
					                event.preventDefault();
					                event.stopPropagation();
					                const drillId = String(btn.getAttribute('data-drill-add') || '').trim();
					                const meta = getDrillMeta(drillId);
					                if (!meta?.icon) return;
					                try {
					                  window.dispatchEvent(new CustomEvent('webstats:tpad:assistant-board', {
					                    detail: {
					                      clear: false,
					                      items: buildBoardItemsFromDrills([drillId], { startX: 0.10, maxX: 0.10, y: 0.18, desiredSize: 64 }),
					                    },
					                  }));
					                } catch (e) { /* ignore */ }
					              });
					            });
					          } catch (e) { /* ignore */ }
				          const applyDrillsFilter = () => {
				            if (!drillsPicker) return;
				            const cat = String(drillsFilter?.value || 'all').trim();
				            const ageKey = String(drillsAge?.value || 'all').trim();
				            const ageRanges = {
				              u8: [4, 8],
				              u12: [9, 12],
				              u16: [13, 16],
				              adult: [17, 99],
				            };
				            const ageSel = ageRanges[ageKey] || null;
				            const q = String(drillsSearch?.value || '').trim().toLowerCase();
				            Array.from(drillsPicker.querySelectorAll('[data-drill-id]')).forEach((cb) => {
				              const wrapper = cb.closest('label');
				              if (!wrapper) return;
				              const wcat = String(wrapper.getAttribute('data-drill-cat') || '').trim();
				              const wlabel = String(wrapper.getAttribute('data-drill-label') || '').trim().toLowerCase();
				              const wAgeMinRaw = String(wrapper.getAttribute('data-drill-age-min') || '').trim();
				              const wAgeMaxRaw = String(wrapper.getAttribute('data-drill-age-max') || '').trim();
				              const wAgeMin = wAgeMinRaw ? parseInt(wAgeMinRaw, 10) : null;
				              const wAgeMax = wAgeMaxRaw ? parseInt(wAgeMaxRaw, 10) : null;
				              const catOk = (cat === 'all') || (wcat === cat);
				              const qOk = (!q) || wlabel.includes(q);
				              let ageOk = true;
				              if (ageSel) {
				                const minSel = ageSel[0];
				                const maxSel = ageSel[1];
				                if (wAgeMin != null && wAgeMin > maxSel) ageOk = false;
				                if (wAgeMax != null && wAgeMax < minSel) ageOk = false;
				              }
				              wrapper.style.display = (catOk && qOk && ageOk) ? '' : 'none';
				            });
				          };
				          try {
				            drillsFilter?.addEventListener('change', applyDrillsFilter);
				            drillsAge?.addEventListener('change', applyDrillsFilter);
				            drillsSearch?.addEventListener('input', applyDrillsFilter);
				            applyDrillsFilter();
				          } catch (err) {}

					          const setAssistantProgramUi = () => {
					            const program = String(programEl.value || '').trim();
				            Array.from(document.querySelectorAll('[data-assistant-program]')).forEach((node) => {
				              const key = String(node.getAttribute('data-assistant-program') || '').trim();
				              node.hidden = !!key && key !== program;
				            });
				            Array.from(document.querySelectorAll('[data-assistant-tip]')).forEach((node) => {
				              const key = String(node.getAttribute('data-assistant-tip') || '').trim();
				              node.hidden = !!key && key !== program;
				            });
				          };
			          try { programEl.addEventListener('change', setAssistantProgramUi); } catch (e) {}
				          setAssistantProgramUi();

				          // Sub-fases dinámicas para 2J Smart (dependen de la fase/foco).
				          const smartGoalEl = document.getElementById('task-assistant-goal');
				          const smartSubphaseEl = document.getElementById('task-assistant-smart-subphase');
					          const SMART_SUBPHASES = {
					            physical_field: [
					              { v: 'aerobic', label: 'Aeróbico (intervalos suaves)' },
					              { v: 'hiit', label: 'HIIT / intermitente' },
					              { v: 'rsa', label: 'RSA (repeated sprints)' },
					              { v: 'speed', label: 'Velocidad (técnica + sprints)' },
					              { v: 'cod', label: 'COD (cambios de dirección)' },
					              { v: 'plyo', label: 'Pliometría (saltos)' },
					            ],
					            physical_gym: [
					              { v: 'strength_lower', label: 'Fuerza tren inferior' },
					              { v: 'full_body', label: 'Circuito full body' },
					              { v: 'core', label: 'Core' },
					              { v: 'prehab', label: 'Prehab (isquios / tobillo)' },
					            ],
					            warmup: [
					              { v: 'no_ball', label: 'Sin balón (movilidad + carrera)' },
					              { v: 'with_ball', label: 'Con balón (rondo/juego simple)' },
					              { v: 'neuromuscular', label: 'Neuromuscular (saltos/aterrizajes/COD)' },
					            ],
				            build_up: [
				              { v: 'gk_restart', label: 'Saque de portería / reinicio' },
				              { v: '2plus1', label: 'Estructura 2+1' },
				              { v: '3plus2', label: 'Estructura 3+2' },
				              { v: 'attract_inside', label: 'Atraer por dentro' },
				              { v: 'play_wide', label: 'Salir por fuera (lateral/extremo)' },
				              { v: 'find_pivot', label: 'Encontrar al pivote/entre líneas' },
				              { v: 'break_first_line', label: 'Superar 1ª línea' },
				            ],
				            progression: [
				              { v: 'third_man', label: 'Tercer hombre' },
				              { v: 'wall_pass', label: 'Pared / devolución' },
				              { v: 'overload_isolate', label: 'Sobrecargar para aislar' },
				              { v: 'switch', label: 'Cambio de orientación' },
				              { v: 'half_spaces', label: 'Atacar intervalos (half-spaces)' },
				              { v: 'between_lines', label: 'Encontrar entre líneas' },
				              { v: 'turn_and_go', label: 'Recibir, girar y progresar' },
				            ],
					            final_third: [
					              { v: '3v3_finish', label: '3v3 + porteros (finalización)' },
					              { v: 'cross', label: 'Centros' },
					              { v: 'cutback', label: 'Pase atrás (cutback)' },
					              { v: 'through_ball', label: 'Pase al espacio' },
				              { v: 'second_post', label: '2º palo + llegada' },
				              { v: 'edge_box', label: 'Disparo frontal (borde área)' },
				              { v: 'finishing_2v1', label: 'Finalización 2v1' },
				              { v: 'finishing_3v2', label: 'Finalización 3v2' },
				            ],
				            pressing: [
				              { v: 'high', label: 'Presión alta' },
				              { v: 'mid', label: 'Bloque medio' },
				              { v: 'trap_wide', label: 'Trampa en banda' },
				              { v: 'cover_shadow', label: 'Sombra de cobertura' },
				              { v: 'press_triggers', label: 'Triggers (pase atrás/control malo)' },
				            ],
				            counterpress: [
				              { v: '5s', label: 'Regla 5 segundos' },
				              { v: '6s', label: 'Regla 6 segundos' },
				              { v: 'rest_defense', label: 'Rest-defense (equilibrio)' },
				              { v: 'protect_center', label: 'Proteger carril central' },
				            ],
				            defending: [
				              { v: 'protect_central', label: 'Proteger zona central' },
				              { v: 'deny_between_lines', label: 'Negar entre líneas' },
				              { v: 'defend_depth', label: 'Defender profundidad' },
				              { v: 'defend_cross', label: 'Defender centros' },
				              { v: 'block_shift', label: 'Basculación y cierres' },
				            ],
				            transition_atd: [
				              { v: 'counterpress', label: 'Contra-presión inmediata' },
				              { v: 'delay', label: 'Temporizar y reorganizar' },
				              { v: 'foul_or_stop', label: 'Cortar transición (si procede)' },
				            ],
				            transition_dta: [
				              { v: 'counterattack_central', label: 'Contraataque por dentro' },
				              { v: 'counterattack_wide', label: 'Contraataque por fuera' },
				              { v: 'secure_then_go', label: 'Asegurar 1º pase y atacar' },
				              { v: 'third_man_run', label: 'Ruptura del 3º hombre' },
				            ],
				            duels: [
				              { v: '1v1_wide', label: '1v1 en banda' },
				              { v: '1v1_central', label: '1v1 central' },
				              { v: '2v1', label: '2v1' },
				              { v: '1v2', label: '1v2' },
				              { v: 'shielding', label: 'Protección de balón' },
				              { v: 'tackling', label: 'Entrada/robo limpio' },
				            ],
				            set_pieces: [
				              { v: 'corner_attack', label: 'Córner ofensivo' },
				              { v: 'corner_defend', label: 'Córner defensivo' },
				              { v: 'fk_direct', label: 'Falta directa' },
				              { v: 'fk_indirect', label: 'Falta indirecta / centro' },
				              { v: 'throw_in', label: 'Saque de banda' },
				              { v: 'kickoff', label: 'Saque inicial' },
				              { v: 'second_ball', label: 'Segundas jugadas' },
				            ],
				            coord: [
				              { v: 'injury_prevention', label: 'Prevención' },
				              { v: 'speed_mechanics', label: 'Técnica de carrera' },
				              { v: 'agility_cods', label: 'Agilidad / cambios dirección' },
				              { v: 'balance', label: 'Equilibrio' },
				            ],
				          };
				          const setSelectOptions = (selectEl, options, selected = 'auto') => {
				            if (!selectEl) return;
				            const safeSelected = String(selected || 'auto').trim() || 'auto';
				            const base = [{ v: 'auto', label: 'Auto' }, ...(Array.isArray(options) ? options : [])];
				            selectEl.innerHTML = base.map((item) => {
				              const v = String(item?.v || '').trim();
				              const label = String(item?.label || v).trim();
				              const isSel = v === safeSelected;
				              return `<option value="${v}" ${isSel ? 'selected' : ''}>${label}</option>`;
				            }).join('');
				          };
				          const subphaseStorageKey = (goalKey) => `webstats:task_assistant:smart:subphase_v1:${scopeKey}:${goalKey}`;
				          const updateSmartSubphases = () => {
				            const goalKey = String(smartGoalEl?.value || 'progression').trim();
				            let stored = 'auto';
				            try { stored = String(window.localStorage?.getItem(subphaseStorageKey(goalKey)) || 'auto').trim() || 'auto'; } catch (e) {}
				            setSelectOptions(smartSubphaseEl, SMART_SUBPHASES[goalKey] || [], stored);
				          };
				          smartGoalEl?.addEventListener('change', () => {
				            updateSmartSubphases();
				          });
				          smartSubphaseEl?.addEventListener('change', () => {
				            const goalKey = String(smartGoalEl?.value || 'progression').trim();
				            const v = String(smartSubphaseEl?.value || 'auto').trim() || 'auto';
				            try { window.localStorage?.setItem(subphaseStorageKey(goalKey), v); } catch (e) {}
				          });
				          updateSmartSubphases();

				          const buildFifa11PlusTemplates = () => {
			            const level = String(levelEl.value || '1').trim();
			            const minutes = Math.max(5, Math.min(30, toInt(minutesEl.value, 8)));
			            const levelLabel = level === '3' ? 'Nivel 3' : (level === '2' ? 'Nivel 2' : 'Nivel 1');
			            const baseMaterials = 'Conos, petos, balones (opcional)';
			            const baseSpace = '2 carriles (10–15 m) + zona central';
			            const basePlayers = 'Todo el equipo (parejas)';

			            const part1 = {
			              title: `FIFA 11+ · Parte 1 · Carrera + movilidad (${levelLabel})`,
			              objective: 'Activación general, movilidad dinámica y preparación neuromuscular.',
			              minutes: minutes,
			              block: 'activation',
			              player_count: basePlayers,
				              dimensions: 'Carril 10–15 m',
				              materials: baseMaterials,
				              space: baseSpace,
				              drills: ['run_easy', 'a_skip', 'butt_kicks', 'hip_open_close', 'hamstring_sweep'],
				              board: {
				                items: [
			                  // Dos carriles con conos + flechas (muy básico, editable).
			                  { payload: { kind: 'cone_striped' }, x: 0.14, y: 0.36 },
			                  { payload: { kind: 'cone' }, x: 0.44, y: 0.36 },
			                  { payload: { kind: 'arrow_solid' }, x: 0.29, y: 0.36 },
			                  { payload: { kind: 'player_local' }, x: 0.10, y: 0.34 },
			                  { payload: { kind: 'player_local' }, x: 0.10, y: 0.38 },
			                  { payload: { kind: 'cone_striped' }, x: 0.14, y: 0.64 },
			                  { payload: { kind: 'cone' }, x: 0.44, y: 0.64 },
			                  { payload: { kind: 'arrow_solid' }, x: 0.29, y: 0.64 },
			                  { payload: { kind: 'player_local' }, x: 0.10, y: 0.62 },
			                  { payload: { kind: 'player_local' }, x: 0.10, y: 0.66 },
			                ],
			              },
			              description_html: `
			                <ul>
			                  <li>Carrera suave ida/vuelta (progresivo) + coordinación de brazos.</li>
			                  <li>Movilidad dinámica: cadera (abre/cierra), tobillo, skipping y talones.</li>
		                  <li>Trabajo por parejas: contacto controlado (hombro) y reacción (mirada al frente).</li>
		                  <li>Progresión: aumenta la velocidad y reduce el tiempo de apoyo.</li>
		                </ul>
		              `,
		              coaching_html: `
		                <ul>
		                  <li>Postura alta, tronco estable, mirada al frente.</li>
		                  <li>Apoyos cortos y silenciosos; evita valgo de rodilla en aterrizajes.</li>
		                  <li>Control técnico: intensidad sube, pero sin perder alineaciones.</li>
		                </ul>
		              `,
		              rules_html: '<ul><li>Sin oposición. Calidad técnica por encima de velocidad.</li></ul>',
		            };

		            const part2LevelTips = (() => {
		              if (level === '3') {
		                return '<li>Variante avanzada: añade inestabilidad/tiempo bajo tensión y saltos con cambio de dirección.</li>';
		              }
		              if (level === '2') {
		                return '<li>Variante media: incrementa repeticiones o duración y añade perturbaciones (compañero).</li>';
		              }
		              return '<li>Variante base: énfasis en técnica, control y rango de movimiento.</li>';
		            })();
			            const part2 = {
			              title: `FIFA 11+ · Parte 2 · Fuerza + equilibrio (${levelLabel})`,
			              objective: 'Prevención: core, isquios, cadera, estabilidad y control de rodilla/tobillo.',
			              minutes: Math.max(8, minutes),
			              block: 'activation',
			              player_count: basePlayers,
			              dimensions: 'Zona central',
			              materials: baseMaterials,
			              space: 'Zona central (colchonetas opcional)',
			              board: {
			                items: [
			                  // Estaciones simples en zona central.
			                  { payload: { kind: 'ring' }, x: 0.30, y: 0.44 },
			                  { payload: { kind: 'ring' }, x: 0.38, y: 0.44 },
			                  { payload: { kind: 'ring' }, x: 0.30, y: 0.56 },
			                  { payload: { kind: 'ring' }, x: 0.38, y: 0.56 },
			                  { payload: { kind: 'player_local' }, x: 0.27, y: 0.44 },
			                  { payload: { kind: 'player_local' }, x: 0.41, y: 0.44 },
			                  { payload: { kind: 'player_local' }, x: 0.27, y: 0.56 },
			                  { payload: { kind: 'player_local' }, x: 0.41, y: 0.56 },
			                  { payload: { kind: 'text' }, x: 0.34, y: 0.62 },
			                ],
			              },
			              description_html: `
			                <ul>
			                  <li>Core: plancha frontal + plancha lateral (técnica limpia).</li>
			                  <li>Cadena posterior: trabajo de isquios (nórdicos asistidos / bisagra de cadera).</li>
		                  <li>Equilibrio: apoyo unipodal + sentadilla a una pierna (control).</li>
		                  <li>Pliometría: saltos bajos con aterrizaje estable (rodilla alineada).</li>
		                  ${part2LevelTips}
		                </ul>
		              `,
		              coaching_html: `
		                <ul>
		                  <li>Rodilla sobre el pie (evita colapsos hacia dentro).</li>
		                  <li>Core activo: pelvis neutra en planchas y apoyos.</li>
		                  <li>Repite sólo si la técnica se mantiene; si no, regresa variante.</li>
		                </ul>
		              `,
		              rules_html: '<ul><li>Sin competición. Se para si aparece dolor o mala técnica.</li></ul>',
		            };

			            const part3 = {
			              title: `FIFA 11+ · Parte 3 · Carrera + cambios (${levelLabel})`,
			              objective: 'Activación final: velocidad, cambios de dirección y desaceleración segura.',
			              minutes: Math.max(5, Math.min(12, minutes)),
			              block: 'activation',
			              player_count: 'Todo el equipo',
			              dimensions: 'Carril 20–30 m',
				              materials: 'Conos',
				              space: 'Carril recto + marcas de giro',
				              drills: ['run_easy', 'ankling', 'side_shuffle', 'carioca', 'bounding'],
				              board: {
				                items: [
			                  { payload: { kind: 'cone_striped' }, x: 0.56, y: 0.50 },
			                  { payload: { kind: 'cone' }, x: 0.82, y: 0.50 },
			                  { payload: { kind: 'arrow_thick' }, x: 0.69, y: 0.50 },
			                  { payload: { kind: 'cone' }, x: 0.82, y: 0.40 },
			                  { payload: { kind: 'cone' }, x: 0.82, y: 0.60 },
			                  { payload: { kind: 'arrow_curve' }, x: 0.86, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.52, y: 0.48 },
			                  { payload: { kind: 'player_local' }, x: 0.52, y: 0.52 },
			                ],
			              },
			              description_html: `
			                <ul>
			                  <li>Aceleraciones progresivas (70% → 90%).</li>
			                  <li>Cambios de dirección (45°/90°) con frenada y re-aceleración.</li>
		                  <li>Desaceleración: pasos cortos, centro de gravedad bajo, control.</li>
		                  <li>Opcional: saltos con carrera (bounding) si el grupo lo tolera.</li>
		                </ul>
		              `,
		              coaching_html: `
		                <ul>
		                  <li>Frena con control: tronco ligeramente inclinado, rodilla alineada.</li>
		                  <li>Evita giros “en seco” con pie muy lejos del cuerpo.</li>
		                  <li>Calidad &gt; cantidad: descansos cortos si hace falta.</li>
		                </ul>
		              `,
		              rules_html: '<ul><li>Sin oposición. Prioriza técnica de frenada y giro.</li></ul>',
		            };

		            return {
		              fifa11plus_part1: part1,
		              fifa11plus_part2: part2,
		              fifa11plus_part3: part3,
		            };
			          };

			          const buildFundamentalsTemplates = () => {
			            const level = String(levelEl.value || '1').trim();
			            const minutes = Math.max(5, Math.min(30, toInt(minutesEl.value, 12)));
			            const levelLabel = level === '3' ? 'Nivel 3' : (level === '2' ? 'Nivel 2' : 'Nivel 1');
			            const smallSided = level === '1' ? '3v3' : (level === '2' ? '4v4' : '4v4 + comodín');

			            const dribbleGame = {
			              title: `Conducción · partido reducido (${levelLabel})`,
			              objective: 'Conducción con cabeza arriba, cambios de dirección y protección del balón en juego real.',
			              minutes: Math.max(8, minutes),
			              block: 'activation',
			              player_count: smallSided,
			              dimensions: '25x20 m',
			              materials: 'Balones, conos, petos, 2 mini porterías',
			              space: 'Rectángulo + mini porterías',
			              training_type: 'Conducción / regate',
			              description_html: `
			                <ul>
			                  <li>Juego reducido con muchos contactos de balón y transiciones rápidas.</li>
			                  <li>Prioriza conducción y regate (pases opcionales según nivel).</li>
			                  <li>Finaliza en mini porterías o en línea de fondo.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Escaneo: mirada arriba antes y durante la conducción.</li>
			                  <li>Cambios de ritmo y dirección para ganar ventaja.</li>
			                  <li>Protege con el cuerpo: balón alejado del rival, apoyo firme.</li>
			                </ul>
			              `,
			              rules_html: `
			                <ul>
			                  <li>Nivel 1: 2–3 toques antes de soltar (opcional) para fomentar conducción.</li>
			                  <li>Nivel 2–3: después de regate/1v1, se puede combinar para finalizar.</li>
			                </ul>
			              `,
			              board: {
			                items: [
			                  { payload: { kind: 'cone' }, x: 0.22, y: 0.30 },
			                  { payload: { kind: 'cone' }, x: 0.78, y: 0.30 },
			                  { payload: { kind: 'cone' }, x: 0.22, y: 0.70 },
			                  { payload: { kind: 'cone' }, x: 0.78, y: 0.70 },
			                  { payload: { kind: 'goal_mini' }, x: 0.22, y: 0.50 },
			                  { payload: { kind: 'goal_mini' }, x: 0.78, y: 0.50, angle: 180 },
			                  { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.46 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.54 },
			                  { payload: { kind: 'player_rival' }, x: 0.56, y: 0.46 },
			                  { payload: { kind: 'player_rival' }, x: 0.56, y: 0.54 },
			                ],
			              },
			            };

			            const oleadaEntry = {
			              title: `Regate + entrada · oleada (${levelLabel})`,
			              objective: 'Mejorar el 1v1: atacar con cambio de ritmo y defender con entrada segura.',
			              minutes: Math.max(10, minutes),
			              block: 'main_1',
			              player_count: '3v3 (por carriles) o 1v1 rotatorio',
			              dimensions: 'Carriles 12–15 m',
			              materials: 'Conos, petos, balones',
			              space: '3 carriles (duelos)',
			              training_type: '1v1',
			              description_html: `
			                <ul>
			                  <li>Organiza carriles de duelo para repetir situaciones de regate + entrada.</li>
			                  <li>El atacante busca superar y progresar; el defensor temporiza y entra con ventaja.</li>
			                  <li>Rotación rápida para acumular repeticiones de calidad.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Atacante: finta + cambio de ritmo, balón pegado en zonas de riesgo.</li>
			                  <li>Defensor: perfilado, distancia adecuada, entra cuando el balón está “expuesto”.</li>
			                  <li>Evita entradas a destiempo: primero temporiza, luego roba.</li>
			                </ul>
			              `,
			              rules_html: `
			                <ul>
			                  <li>Norma: no se invade carril (para repetir 1v1 claros).</li>
			                  <li>Punto por superación + progresión / por robo limpio.</li>
			                </ul>
			              `,
			              board: {
			                items: [
			                  { payload: { kind: 'shape_lane_3' }, x: 0.50, y: 0.40, scale: 2.1 },
			                  { payload: { kind: 'shape_lane_3' }, x: 0.50, y: 0.60, scale: 2.1 },
			                  { payload: { kind: 'player_local' }, x: 0.34, y: 0.50 },
			                  { payload: { kind: 'player_rival' }, x: 0.40, y: 0.50 },
			                  { payload: { kind: 'ball' }, x: 0.37, y: 0.50 },
			                ],
			              },
			            };

			            const conservationPass = {
			              title: `Conservación · pase (4v4+2) (${levelLabel})`,
			              objective: 'Encontrar líneas de pase y crear espacios libres con amplitud, profundidad y apoyos.',
			              minutes: Math.max(12, minutes),
			              block: 'main_1',
			              player_count: '4v4 + 2 comodines',
			              dimensions: '30x30 m',
			              materials: 'Balones, conos, petos',
			              space: 'Cuadrado + zonas de puntuación',
			              training_type: 'Conservación / pase',
			              description_html: `
			                <ul>
			                  <li>Posesión con comodines para facilitar continuidad y mejorar toma de decisión.</li>
			                  <li>Puntúa al recibir en zonas objetivo o tras cierto número de pases (según nivel).</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Perfil corporal para jugar a 1–2 toques cuando sea posible.</li>
			                  <li>Ocupar alturas y ejes distintos: crea triángulos, no te pegues al balón.</li>
			                  <li>Pase con ventaja: al pie “bueno” o al espacio libre.</li>
			                </ul>
			              `,
			              rules_html: `
			                <ul>
			                  <li>Nivel 1: comodines con libertad, objetivo mantener + progresar.</li>
			                  <li>Nivel 2–3: limitación de toques y zonas de puntuación.</li>
			                </ul>
			              `,
			              board: {
			                items: [
			                  { payload: { kind: 'shape_rect_long' }, x: 0.30, y: 0.50, scale: 1.4 },
			                  { payload: { kind: 'shape_rect_long' }, x: 0.70, y: 0.50, scale: 1.4 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.44 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.56 },
			                  { payload: { kind: 'player_local' }, x: 0.50, y: 0.40 },
			                  { payload: { kind: 'player_local' }, x: 0.50, y: 0.60 },
			                  { payload: { kind: 'player_rival' }, x: 0.56, y: 0.44 },
			                  { payload: { kind: 'player_rival' }, x: 0.56, y: 0.56 },
			                  { payload: { kind: 'player_rival' }, x: 0.62, y: 0.40 },
			                  { payload: { kind: 'player_rival' }, x: 0.62, y: 0.60 },
			                  { payload: { kind: 'player_away' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'player_away' }, x: 0.50, y: 0.32 },
			                  { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
			                ],
			              },
			            };

			            const conservation2v1 = {
			              title: `Conservación · 2v1 (${levelLabel})`,
			              objective: 'Crear y resolver 2v1: fijar, atraer y soltar en el momento correcto.',
			              minutes: Math.max(10, minutes),
			              block: 'main_1',
			              player_count: '2v1 por oleadas',
			              dimensions: '20x12 m',
			              materials: 'Conos, petos, balones, mini portería',
			              space: 'Carril + finalización',
			              training_type: 'Superioridad 2v1',
			              description_html: `
			                <ul>
			                  <li>Inicia 2 atacantes contra 1 defensor con objetivo de progresar y finalizar.</li>
			                  <li>Regla simple: si el defensor fija al poseedor, aparece el pase; si temporiza, ataca espacio.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Atacante con balón: conduce para fijar al defensor, no pases “sin atraer”.</li>
			                  <li>Apoyo: desmarque diagonal, distancia de pase, orienta cuerpo para jugar de cara.</li>
			                  <li>Defensor: perfilado + temporización, obliga a ir a banda o a decidir pronto.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Máximo 6–8 segundos por oleada para mantener intensidad.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'goal_mini' }, x: 0.82, y: 0.50, angle: 180 },
			                  { payload: { kind: 'cone_striped' }, x: 0.22, y: 0.40 },
			                  { payload: { kind: 'cone_striped' }, x: 0.22, y: 0.60 },
			                  { payload: { kind: 'player_local' }, x: 0.34, y: 0.46 },
			                  { payload: { kind: 'player_local' }, x: 0.34, y: 0.54 },
			                  { payload: { kind: 'player_rival' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'ball' }, x: 0.36, y: 0.46 },
			                  { payload: { kind: 'arrow_thick' }, x: 0.62, y: 0.50 },
			                ],
			              },
			            };

			            const oleadas1v1 = {
			              title: `Oleadas · 1v1 (${levelLabel})`,
			              objective: 'Resolver 1v1: ataque con iniciativa y defensa con temporización + robo limpio.',
			              minutes: Math.max(10, minutes),
			              block: 'main_1',
			              player_count: '1v1 por oleadas',
			              dimensions: '18x12 m',
			              materials: 'Conos, petos, balones, mini porterías',
			              space: 'Carril + portería',
			              training_type: '1v1',
			              description_html: `
			                <ul>
			                  <li>Oleadas cortas: entra 1 atacante vs 1 defensor, finaliza rápido y rota.</li>
			                  <li>Variantes: finalización a portería, cruzar línea, o puntuar por superar.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Atacante: ataca el pie adelantado del defensor y cambia de ritmo.</li>
			                  <li>Defensor: orienta hacia fuera y controla distancia.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Repeticiones cortas (6–8s) + descanso activo.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'shape_lane_3' }, x: 0.50, y: 0.50, scale: 2.0 },
			                  { payload: { kind: 'goal_mini' }, x: 0.82, y: 0.50, angle: 180 },
			                  { payload: { kind: 'player_local' }, x: 0.42, y: 0.50 },
			                  { payload: { kind: 'player_rival' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'ball' }, x: 0.44, y: 0.50 },
			                ],
			              },
			            };

			            const match2v1 = {
			              title: `Partido · 2v1 (${levelLabel})`,
			              objective: 'Transferir superioridades al juego: identificar 2v1 y finalizar con criterio.',
			              minutes: Math.max(12, minutes),
			              block: 'main_2',
			              player_count: '3v3 / 4v4 con comodines (crear 2v1)',
			              dimensions: '35x25 m',
			              materials: 'Conos, petos, balones, porterías',
			              space: 'Partido condicionado',
			              training_type: 'Juego aplicado',
			              description_html: `
			                <ul>
			                  <li>Partido reducido con condicionantes para provocar 2v1 (comodín o reglas de superioridad).</li>
			                  <li>Objetivo: fijar y soltar para finalizar, no acumular pases sin intención.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Fijación: conduce hacia el defensor antes de pasar.</li>
			                  <li>Apoyos por dentro y por fuera para dar 2 líneas de pase.</li>
			                  <li>Finaliza con ventaja: tiro o pase al segundo palo.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Puntúa doble si el gol viene tras un 2v1 claro.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'goal' }, x: 0.18, y: 0.50 },
			                  { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
			                  { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.46 },
			                  { payload: { kind: 'player_local' }, x: 0.44, y: 0.54 },
			                  { payload: { kind: 'player_rival' }, x: 0.56, y: 0.50 },
			                ],
			              },
			            };

			            const coordCircuit = {
			              title: `Circuito coordinativo (${levelLabel})`,
			              objective: 'Mejorar coordinación, apoyos y cambios de ritmo con y sin balón.',
			              minutes: Math.max(10, minutes),
			              block: 'activation',
			              player_count: 'Grupos de 3–4 por estación',
			              dimensions: 'Zona central',
			              materials: 'Conos, aros, escalera, picas, balones (opcional)',
			              space: 'Circuito por estaciones',
			              training_type: 'Coordinación',
			              description_html: `
			                <ul>
			                  <li>3–4 estaciones: escalera, aros, slalom, recepción/orientación.</li>
			                  <li>Trabajo por tiempo (30–45s) + cambio de estación.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Calidad de apoyos: estabilidad y control antes de velocidad.</li>
			                  <li>Progresión: añade balón o estímulo (señal/colores) si el grupo domina.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Sin competición si afecta a la técnica.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'emoji_ladder' }, x: 0.32, y: 0.50 },
			                  { payload: { kind: 'ring' }, x: 0.50, y: 0.44 },
			                  { payload: { kind: 'ring' }, x: 0.56, y: 0.44 },
			                  { payload: { kind: 'ring' }, x: 0.50, y: 0.56 },
			                  { payload: { kind: 'ring' }, x: 0.56, y: 0.56 },
			                  { payload: { kind: 'cone' }, x: 0.70, y: 0.40 },
			                  { payload: { kind: 'cone' }, x: 0.76, y: 0.50 },
			                  { payload: { kind: 'cone' }, x: 0.70, y: 0.60 },
			                  { payload: { kind: 'player_local' }, x: 0.26, y: 0.50 },
			                ],
			              },
			            };

			            const adaptedGame = {
			              title: `Juego adaptado coordinativo (${levelLabel})`,
			              objective: 'Coordinar movimientos con balón en un juego sencillo y motivante.',
			              minutes: Math.max(10, minutes),
			              block: 'activation',
			              player_count: '2 equipos (5–8 por lado)',
			              dimensions: '25x20 m',
			              materials: 'Conos, petos, balones',
			              space: 'Juego con reglas simples',
			              training_type: 'Juego adaptado',
			              description_html: `
			                <ul>
			                  <li>Juego corto con reglas que obliguen a coordinar (señales, cambios de rol, objetivos por colores).</li>
			                  <li>En categorías pequeñas: objetivos muy claros y rotaciones rápidas.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Consignas cortas: 1 idea por bloque.</li>
			                  <li>Motiva y refuerza: “lo que sale bien se repite”.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Regla ejemplo: tras 3 pases, obliga a un cambio de dirección o a atacar una zona.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'cone' }, x: 0.26, y: 0.30 },
			                  { payload: { kind: 'cone' }, x: 0.74, y: 0.30 },
			                  { payload: { kind: 'cone' }, x: 0.26, y: 0.70 },
			                  { payload: { kind: 'cone' }, x: 0.74, y: 0.70 },
			                  { payload: { kind: 'player_local' }, x: 0.46, y: 0.50 },
			                  { payload: { kind: 'player_rival' }, x: 0.54, y: 0.50 },
			                  { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
			                ],
			              },
			            };

			            return {
			              fund_dribble_game: dribbleGame,
			              fund_oleada_entry: oleadaEntry,
			              fund_conservation_pass: conservationPass,
			              fund_conservation_2v1: conservation2v1,
			              fund_oleadas_1v1: oleadas1v1,
			              fund_match_2v1: match2v1,
			              fund_coord_circuit: coordCircuit,
			              fund_adapted_game_coord: adaptedGame,
			            };
			          };

					          const buildSmartTemplates = () => {
					            const age = String((document.getElementById('task-assistant-ageband')?.value) || 'u12').trim();
					            const rawGoal = String((document.getElementById('task-assistant-goal')?.value) || 'progression').trim();
					            const smartSubphase = String((smartSubphaseEl?.value) || 'auto').trim();
					            const smartSubphaseLabel = String((smartSubphaseEl?.selectedOptions && smartSubphaseEl.selectedOptions[0]?.textContent) || '').trim();
					            const principle = String((document.getElementById('task-assistant-smart-principle')?.value) || 'auto').trim();
					            const blockPref = String((document.getElementById('task-assistant-smart-block')?.value) || 'auto').trim();
					            const approachPref = String((document.getElementById('task-assistant-smart-approach')?.value) || 'auto').trim();
					            const playersCount = toInt((document.getElementById('task-assistant-smart-players')?.value) || '', 0);
					            const materialsHint = String((document.getElementById('task-assistant-smart-materials')?.value) || '').trim();
					            const smartPrompt = String((document.getElementById('task-assistant-smart-prompt')?.value) || '').trim();
				            const minutes = Math.max(5, Math.min(30, toInt(minutesEl.value, 12)));
				            const level = String(levelEl.value || '1').trim();
				            const levelLabel = level === '3' ? 'Nivel 3' : (level === '2' ? 'Nivel 2' : 'Nivel 1');

			            const isYoung = age === 'u8';
			            const isSenior = age === 'u19';
			            const goalAliases = {
			              // Compat con valores antiguos (por si queda en cache/cola).
			              build: 'build_up',
			              press: 'pressing',
			              transition: 'transition_atd',
			              pass: 'progression',
			              dribble: 'duels',
			              '1v1': 'duels',
			              '2v1': 'duels',
			              finish: 'final_third',
			            };
				            const goal = goalAliases[rawGoal] || rawGoal;
				            const base = buildFundamentalsTemplates();
				            const allowedFormatsForApproach = (() => {
				              if (approachPref === 'analytic') return new Set(['analytic', 'circuit']);
				              if (approachPref === 'systemic') return new Set(['game', 'ssg']);
				              return null;
				            })();

				            // Carga física (campo / gimnasio): generador directo (sin depender del catálogo).
				            if (goal === 'physical_field' || goal === 'physical_gym') {
				              const sub = (smartSubphase && smartSubphase !== 'auto') ? smartSubphase : (goal === 'physical_gym' ? 'strength_lower' : 'hiit');
				              const ageLabel = age === 'u8' ? 'Fútbol base' : (age === 'u12' ? 'Formación' : (age === 'u15' ? 'Rendimiento' : 'Competición'));
				              const safePlayers = playersCount > 0 ? `${playersCount} jugadores` : (goal === 'physical_gym' ? 'Grupos 2–3' : 'Todo el equipo');
				              const maybeMaterials = (materialsHint ? materialsHint : (goal === 'physical_gym' ? 'Colchonetas, gomas, conos (opcional)' : 'Conos, cronómetro, balones (opcional)'));

				              const loadPresets = (() => {
				                // Valores orientativos (ajusta según grupo). Para U8 reducimos volumen e intensidades.
				                const young = age === 'u8';
				                const baseField = {
				                  aerobic: { series: young ? '2' : '3', reps: young ? '6' : '8', work_rest: young ? "10'' / 20''" : "20'' / 20''", rpe: young ? 'RPE 5–6' : 'RPE 6–7' },
				                  hiit: { series: young ? '2' : '3', reps: young ? '6' : '10', work_rest: young ? "10'' / 20''" : "15'' / 15''", rpe: young ? 'RPE 6' : 'RPE 7–8' },
				                  rsa: { series: young ? '2' : '3', reps: young ? '4' : '6', work_rest: young ? "6'' / 24''" : "6'' / 30''", rpe: young ? 'RPE 7' : 'RPE 8–9' },
				                  speed: { series: young ? '2' : '3', reps: young ? '4' : '6', work_rest: young ? "6'' / 30''" : "8'' / 40''", rpe: young ? 'RPE 7' : 'RPE 8' },
				                  cod: { series: young ? '2' : '3', reps: young ? '6' : '8', work_rest: young ? "8'' / 20''" : "10'' / 25''", rpe: young ? 'RPE 6–7' : 'RPE 7–8' },
				                  plyo: { series: young ? '2' : '3', reps: young ? '6' : '8', work_rest: young ? "6'' / 24''" : "8'' / 30''", rpe: young ? 'RPE 6' : 'RPE 7' },
				                };
				                const baseGym = {
				                  strength_lower: { series: young ? '2' : '3', reps: young ? '6–8' : '8–10', work_rest: young ? "30'' / 45''" : "45'' / 60''", rpe: young ? 'Técnica' : 'RPE 7' },
				                  full_body: { series: young ? '2' : '3', reps: young ? '6–8' : '8–12', work_rest: young ? "30'' / 45''" : "45'' / 60''", rpe: young ? 'Técnica' : 'RPE 7' },
				                  core: { series: young ? '2' : '3', reps: young ? "20''" : "30–40''", work_rest: young ? "20'' / 30''" : "30'' / 30''", rpe: young ? 'Control' : 'RPE 6–7' },
				                  prehab: { series: young ? '2' : '3', reps: young ? '6' : '8', work_rest: young ? "30'' / 45''" : "45'' / 60''", rpe: young ? 'Control' : 'RPE 6–7' },
				                };
				                return goal === 'physical_gym' ? baseGym : baseField;
				              })();
				              const preset = loadPresets[sub] || (goal === 'physical_gym' ? loadPresets.strength_lower : loadPresets.hiit);

				              const warmup = {
				                title: `Calentamiento · técnica carrera (${ageLabel})`,
				                objective: 'Activación general y preparación neuromuscular.',
				                minutes: Math.max(6, Math.min(12, Math.round(minutes * 0.45))),
				                block: 'activation',
				                player_count: safePlayers,
				                dimensions: goal === 'physical_gym' ? 'Zona central' : 'Carril 10–15 m',
				                materials: maybeMaterials,
				                space: goal === 'physical_gym' ? 'Zona central (sin impacto)' : 'Carriles + movilidad',
				                drills: ['run_easy', 'a_skip', 'butt_kicks', 'hip_open_close', 'hamstring_sweep'],
				                description_html: ensureListHtml(`
				                  <li>Carrera suave + movilidad dinámica (cadera, tobillo, isquios).</li>
				                  <li>Técnica de carrera: skipping / talones + pies rápidos.</li>
				                `),
				                coaching_html: ensureListHtml(`
				                  <li>Postura alta, brazos coordinados, apoyos cortos.</li>
				                  <li>Calidad por encima de velocidad (especialmente en U8).</li>
				                `),
				              };

				              const cooldown = {
				                title: `Vuelta a la calma · movilidad (${ageLabel})`,
				                objective: 'Recuperación: respiración + movilidad suave.',
				                minutes: Math.max(5, Math.min(10, Math.round(minutes * 0.35))),
				                block: 'recovery',
				                player_count: safePlayers,
				                dimensions: 'Zona central',
				                materials: '—',
				                space: 'Zona central',
				                drills: ['lunge_walk', 'hip_open_close', 'hamstring_sweep'],
				                description_html: ensureListHtml(`
				                  <li>Movilidad suave (cadera/isquios) + estiramientos dinámicos ligeros.</li>
				                  <li>Respiración y vuelta progresiva a calma.</li>
				                `),
				              };

				              const main = (() => {
				                if (goal === 'physical_gym') {
				                  const titleMap = {
				                    strength_lower: 'Fuerza tren inferior',
				                    full_body: 'Circuito full body',
				                    core: 'Core',
				                    prehab: 'Prehab (isquios/tobillo)',
				                  };
				                  const drillMap = {
				                    strength_lower: ['squat', 'hinge', 'split_squat', 'calf_raise'],
				                    full_body: ['squat', 'hinge', 'push_up', 'band_row', 'plank'],
				                    core: ['plank', 'side_plank'],
				                    prehab: ['nordic', 'calf_raise', 'plank'],
				                  };
				                  const drills = drillMap[sub] || drillMap.strength_lower;
				                  return {
				                    title: `Carga física · Gimnasio · ${titleMap[sub] || titleMap.strength_lower} (${ageLabel})`,
				                    objective: 'Desarrollar fuerza y prevención con control técnico.',
				                    minutes: Math.max(8, Math.min(25, minutes)),
				                    block: (blockPref !== 'auto' ? blockPref : 'conditioning'),
				                    player_count: safePlayers,
				                    dimensions: 'Zona central',
				                    materials: maybeMaterials,
				                    space: 'Circuito por estaciones',
				                    training_type: 'Carga física (fuerza)',
				                    series: preset.series,
				                    repetitions: preset.reps,
				                    work_rest: preset.work_rest,
				                    load_target: preset.rpe,
				                    drills,
				                    description_html: ensureListHtml(`
				                      <li>Organiza estaciones (2–3 jugadores) y rota cada ${preset.work_rest || "45'' / 60''"}.</li>
				                      <li>Prioriza técnica limpia: control de rodilla/tobillo, core activo.</li>
				                    `),
				                    coaching_html: ensureListHtml(`
				                      <li>Control de rodilla (evita valgo) y espalda neutra.</li>
				                      <li>Si se pierde técnica, reduce reps/carga.</li>
				                    `),
				                    rules_html: ensureListHtml(`<li>Sin dolor. Pausa si hay molestias.</li>`),
				                  };
				                }
				                // Campo
				                const titleMap = {
				                  aerobic: 'Aeróbico (intervalos)',
				                  hiit: 'HIIT (intermitente)',
				                  rsa: 'RSA (repeated sprints)',
				                  speed: 'Velocidad (técnica + sprints)',
				                  cod: 'COD (cambios de dirección)',
				                  plyo: 'Pliometría (saltos)',
				                };
				                const drillMap = {
				                  aerobic: ['run_easy', 'shuttle_run'],
				                  hiit: ['shuttle_run', 'acceleration', 'deceleration', 'change_direction'],
				                  rsa: ['max_sprint', 'deceleration'],
				                  speed: ['acceleration', 'max_sprint', 'ankling'],
				                  cod: ['change_direction', 'deceleration', 'side_shuffle', 'carioca'],
				                  plyo: ['jump_land', 'pogo_hops', 'bounding'],
				                };
				                const drills = drillMap[sub] || drillMap.hiit;
				                return {
				                  title: `Carga física · Campo · ${titleMap[sub] || titleMap.hiit} (${ageLabel})`,
				                  objective: 'Mejorar capacidad física específica sin perder técnica.',
				                  minutes: Math.max(8, Math.min(25, minutes)),
				                  block: (blockPref !== 'auto' ? blockPref : 'conditioning'),
				                  player_count: safePlayers,
				                  dimensions: 'Carril / zona',
				                  materials: maybeMaterials,
				                  space: 'Carriles + marcas de giro',
				                  training_type: 'Carga física (campo)',
				                  series: preset.series,
				                  repetitions: preset.reps,
				                  work_rest: preset.work_rest,
				                  load_target: preset.rpe,
				                  drills,
				                  description_html: ensureListHtml(`
				                    <li>Series: ${preset.series || '-'} · Reps: ${preset.reps || '-'} · Trabajo/descanso: ${preset.work_rest || '-'}</li>
				                    <li>Calidad de carrera y frenada. En U8, foco en juego y técnica.</li>
				                  `),
				                  coaching_html: ensureListHtml(`
				                    <li>Frenada: pasos cortos, centro de gravedad bajo, rodilla alineada.</li>
				                    <li>Velocidad: progresiva (no a tope desde la 1ª repetición).</li>
				                  `),
				                  rules_html: ensureListHtml(`<li>Descanso completo si la técnica cae.</li>`),
				                };
				              })();

				              const suggestions = [
				                { id: `phys:${goal}:${sub}:main`, meta: { goal, subphase: sub, format: 'analytic' }, tpl: main, score: 100 },
				                { id: `phys:${goal}:${sub}:warmup`, meta: { goal, subphase: 'warmup', format: 'analytic' }, tpl: warmup, score: 70 },
				                { id: `phys:${goal}:${sub}:cooldown`, meta: { goal, subphase: 'cooldown', format: 'analytic' }, tpl: cooldown, score: 60 },
				              ];

				              return {
				                smart_generate: main,
				                smart_suggestions: suggestions,
				                smart_block_1: warmup,
				                smart_block_2: main,
				                smart_block_3: cooldown,
				              };
				            }

			            const PRINCIPLES = {
			              width_depth: {
			                objective: 'crear amplitud y profundidad para abrir líneas de pase.',
			                coaching: 'Amplitud real (pegarse a línea) y profundidad (amenaza a espalda).',
			              },
			              third_man: {
			                objective: 'usar al tercer hombre para superar presión.',
			                coaching: 'Pase al pie libre, apoyo de cara y tercer hombre atacando espacio.',
			              },
			              fix_release: {
			                objective: 'fijar al defensor y soltar con ventaja.',
			                coaching: 'Conduce para atraer; suelta cuando el rival “muerde”.',
			              },
			              switch: {
			                objective: 'cambiar de orientación para atacar el lado débil.',
			                coaching: 'Antes de cambiar: atraer, asegurar y cambiar rápido y tenso.',
			              },
			              support_angles: {
			                objective: 'mejorar ángulos/distancias de apoyo.',
			                coaching: 'Triángulos, distancias útiles y perfil corporal antes de recibir.',
			              },
			              press_triggers: {
			                objective: 'coordinar triggers y roles de presión.',
			                coaching: 'Señales claras (pase atrás, control malo, banda) y coberturas.',
			              },
			              cover_balance: {
			                objective: 'mantener cobertura y equilibrio defensivo.',
			                coaching: 'Primer defensor orienta; segundo cierra línea; tercero equilibra.',
			              },
			              rest_defense: {
			                objective: 'asegurar rest-defense para evitar transiciones.',
			                coaching: 'Estructura por detrás del balón: 2+1/3+2 según fase.',
			              },
			            };
				            const applyPrinciple = (tpl) => {
				              if (!tpl || principle === 'auto') return tpl;
				              const info = PRINCIPLES[principle];
				              if (!info) return tpl;
				              const next = { ...tpl };
			              if (info.objective) {
			                next.objective = next.objective ? `${next.objective} (${info.objective})` : info.objective;
			              }
			              if (info.coaching) {
			                const extra = `<li><strong>Principio:</strong> ${info.coaching}</li>`;
			                next.coaching_html = (next.coaching_html || '').includes('<ul>')
			                  ? (next.coaching_html || '').replace('</ul>', `${extra}</ul>`)
			                  : `<ul>${extra}</ul>`;
				              }
				              return next;
				            };

				            const ensureListHtml = (html) => {
				              const h = String(html || '').trim();
				              if (!h) return '<ul></ul>';
				              if (h.includes('<ul')) return h;
				              return `<ul><li>${h}</li></ul>`;
				            };
					            const appendBullets = (html, bullets) => {
					              const items = (Array.isArray(bullets) ? bullets : []).map((b) => String(b || '').trim()).filter(Boolean);
					              if (!items.length) return html;
					              const base = ensureListHtml(html);
					              const extra = items.map((b) => `<li>${b}</li>`).join('');
					              return base.replace('</ul>', `${extra}</ul>`);
					            };
					            const escapeHtmlLite = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
					              '&': '&amp;',
					              '<': '&lt;',
					              '>': '&gt;',
					              '"': '&quot;',
					              "'": '&#39;',
					            }[ch] || ch));
					            const scaleDimensions = (dimensionsRaw, factor) => {
					              const raw = String(dimensionsRaw || '').trim();
					              if (!raw) return raw;
					              const f = Number(factor);
					              if (!Number.isFinite(f) || f < 0.5 || f > 1.6) return raw;
					              const match = raw.match(/\b(\d{2,3})\s*x\s*(\d{2,3})\b/i);
					              if (!match) return raw;
					              const w = Math.max(10, Math.round((Number(match[1]) || 0) * f));
					              const h = Math.max(10, Math.round((Number(match[2]) || 0) * f));
					              return raw.replace(match[0], `${w}x${h}`);
					            };
					            const applyAgebandHints = (tpl, opts = {}) => {
					              if (!tpl || typeof tpl !== 'object') return tpl;
					              const next = { ...tpl };
					              const ageKey = String(opts.age || age || '').trim();
					              const spec = coachDictionary?.agebands?.[ageKey] || null;
					              if (!spec) return next;
					              const label = String(spec?.label || '').trim();
					              const coachingPoints = Array.isArray(spec?.coaching_points) ? spec.coaching_points : [];
					              const constraints = Array.isArray(spec?.task_design?.constraints) ? spec.task_design.constraints : [];
					              const alreadyTagged = String(next.coaching_html || '').includes('Etapa:');
					              if (!alreadyTagged && label) {
					                next.coaching_html = appendBullets(next.coaching_html, [`Etapa: ${escapeHtmlLite(label)}`]);
					              }
					              if (coachingPoints.length) {
					                next.coaching_html = appendBullets(next.coaching_html, coachingPoints.slice(0, 2).map((p) => escapeHtmlLite(p)));
					              }
					              if (constraints.length) {
					                next.rules_html = appendBullets(next.rules_html, constraints.slice(0, 2).map((p) => escapeHtmlLite(p)));
					              }
					              const factor = ageKey === 'u8' ? 0.82 : (ageKey === 'u12' ? 0.92 : (ageKey === 'u19' ? 1.08 : 1.0));
					              next.dimensions = scaleDimensions(next.dimensions, factor);
					              return next;
					            };

					            // Ajustes por sub-fase (opcional): enfoca la tarea sin cambiar la estructura base.
					            const SUBPHASE_PRESETS = {
				              warmup: {
				                no_ball: {
				                  title_suffix: 'sin balón',
				                  training_type: 'Activación (sin balón)',
				                  coaching: [
				                    'Movilidad dinámica + técnica de carrera (apoyos, braceo, postura).',
				                    'Progresión suave: RPE 3→5, sin fatiga.',
				                  ],
				                  rules: ['Sin competición. Calidad antes que velocidad.'],
				                  board: {
				                    items: [
				                      { payload: { kind: 'emoji_ladder' }, x: 0.28, y: 0.50 },
				                      { payload: { kind: 'cone' }, x: 0.42, y: 0.42 },
				                      { payload: { kind: 'cone' }, x: 0.42, y: 0.58 },
				                      { payload: { kind: 'cone' }, x: 0.58, y: 0.42 },
				                      { payload: { kind: 'cone' }, x: 0.58, y: 0.58 },
				                      { payload: { kind: 'arrow_thick' }, x: 0.46, y: 0.50 },
				                      { payload: { kind: 'arrow_thick' }, x: 0.54, y: 0.50, angle: 180 },
				                    ],
				                  },
				                },
				                with_ball: {
				                  title_suffix: 'con balón',
				                  coaching: ['Muchos contactos: control orientado + pase con ventaja.'],
				                  rules: ['1–2 toques recomendado. Cambia roles rápido.'],
				                },
				                neuromuscular: {
				                  title_suffix: 'neuromuscular',
				                  training_type: 'Activación (neuromuscular)',
				                  coaching: ['Aterrizajes controlados, estabilidad de cadera/rodilla, COD progresivo.'],
				                  rules: ['Pocas repeticiones, descanso suficiente.'],
				                },
				              },
				              build_up: {
				                gk_restart: {
				                  title_suffix: 'reinicio (portero)',
				                  coaching: ['Portero: perfil + pase tenso al pie libre.', 'Centrales: atraer para liberar al 6.'],
				                  rules: ['Siempre inicia en portero. Punto extra si superas 1ª línea con el 6.'],
				                  board: {
				                    items: [
				                      { payload: { kind: 'goal' }, x: 0.18, y: 0.50 },
				                      { payload: { kind: 'goalkeeper_local' }, x: 0.22, y: 0.50 },
				                      { payload: { kind: 'ball' }, x: 0.24, y: 0.50 },
				                      { payload: { kind: 'player_local' }, x: 0.28, y: 0.44 },
				                      { payload: { kind: 'player_local' }, x: 0.28, y: 0.56 },
				                      { payload: { kind: 'player_local' }, x: 0.36, y: 0.50 },
				                      { payload: { kind: 'player_rival' }, x: 0.40, y: 0.44 },
				                      { payload: { kind: 'player_rival' }, x: 0.40, y: 0.56 },
				                      { payload: { kind: 'arrow_thick' }, x: 0.32, y: 0.50 },
				                    ],
				                  },
				                },
				                '2plus1': {
				                  title_suffix: 'estructura 2+1',
				                  coaching: ['Mantén 2+1 por detrás del balón para asegurar rest-defense.'],
				                  rules: ['Obligatorio dejar 2+1. Si se rompe, no puntúa la acción.'],
				                },
				                '3plus2': {
				                  title_suffix: 'estructura 3+2',
				                  coaching: ['3+2 en base: escalonamiento y líneas de pase.'],
				                  rules: ['Puntúa si progresas tras atraer y jugar al lado débil.'],
				                },
				                attract_inside: {
				                  title_suffix: 'atraer por dentro',
				                  coaching: ['Conduce/pasa por dentro para atraer; cambia cuando se cierre.'],
				                  rules: ['Punto extra si el cambio de orientación sale tras 3 pases interiores.'],
				                },
				                play_wide: {
				                  title_suffix: 'salir por fuera',
				                  coaching: ['Lateral alto y ancho; extremo fija por fuera para liberar carril interior.'],
				                  rules: ['Puntúa doble si progresas por banda y encuentras pase atrás.'],
				                },
				                find_pivot: {
				                  title_suffix: 'encontrar pivote',
				                  coaching: ['Pivote: perfil para jugar de cara o girar si hay ventaja.'],
				                  rules: ['Debe intervenir el pivote antes de progresar.'],
				                },
				                break_first_line: {
				                  title_suffix: 'superar 1ª línea',
				                  coaching: ['Primer control orientado para “romper” línea. Evita pases neutros.'],
				                  rules: ['Puntúa si superas 1ª línea con pase tenso o conducción.'],
				                },
				              },
				              progression: {
				                third_man: {
				                  title_suffix: 'tercer hombre',
				                  coaching: ['Apoyo de cara + ruptura del 3º hombre en el lado libre.'],
				                  rules: ['Puntúa si el 3º hombre recibe orientado hacia adelante.'],
				                  board: {
				                    items: [
				                      { payload: { kind: 'player_local' }, x: 0.40, y: 0.52 },
				                      { payload: { kind: 'player_local' }, x: 0.50, y: 0.42 },
				                      { payload: { kind: 'player_local' }, x: 0.60, y: 0.52 },
				                      { payload: { kind: 'ball' }, x: 0.40, y: 0.52 },
				                      { payload: { kind: 'arrow_thick' }, x: 0.46, y: 0.48 },
				                      { payload: { kind: 'arrow_thick' }, x: 0.54, y: 0.48, angle: 180 },
				                    ],
				                  },
				                },
				                wall_pass: {
				                  title_suffix: 'pared',
				                  coaching: ['Pase tenso, devolución a 1 toque, tercero ataca el espacio.'],
				                  rules: ['Gol/punto solo si hay pared (2 pases consecutivos).'],
				                },
				                overload_isolate: {
				                  title_suffix: 'sobrecargar/aislar',
				                  coaching: ['Sobra en un lado para atraer; cambia al lado débil.'],
				                  rules: ['Puntúa si el lado débil recibe en ventaja (1v1).'],
				                },
				                switch: {
				                  title_suffix: 'cambio de orientación',
				                  coaching: ['Atraer + asegurar + cambiar rápido y tenso.'],
				                  rules: ['Punto extra si el cambio supera 2 líneas rivales.'],
				                },
				                half_spaces: {
				                  title_suffix: 'half-spaces',
				                  coaching: ['Ataca el intervalo lateral-central y juega a la espalda del lateral.'],
				                  rules: ['Puntúa si progresas por half-space y finalizas con pase atrás.'],
				                },
				                between_lines: {
				                  title_suffix: 'entre líneas',
				                  coaching: ['Recepción perfilada entre líneas (hombro mirado).'],
				                  rules: ['El receptor debe girar o jugar de cara con ventaja.'],
				                },
				                turn_and_go: {
				                  title_suffix: 'recibir y girar',
				                  coaching: ['Primer control orientado para girar. Si no, juega de cara.'],
				                  rules: ['Puntúa si el receptor gira y supera rival directo.'],
				                },
				              },
				              final_third: {
				                cross: {
				                  title_suffix: 'centros',
				                  coaching: ['Atacantes: 1º palo / 2º palo / punto penal. Timing.'],
				                  rules: ['Puntúa doble si hay centro y remate en zona.'],
				                },
				                cutback: {
				                  title_suffix: 'pase atrás',
				                  coaching: ['Línea de fondo: cabeza arriba y pase atrás a la frontal.'],
				                  rules: ['Gol/punto solo si acaba con pase atrás.'],
				                },
				                through_ball: {
				                  title_suffix: 'pase al espacio',
				                  coaching: ['Temporiza para fijar y filtrar cuando el defensor salta.'],
				                  rules: ['Puntúa si el pase al espacio deja al atacante delante del defensor.'],
				                },
				                second_post: {
				                  title_suffix: '2º palo',
				                  coaching: ['Llegada al 2º palo: ni pronto ni tarde.'],
				                  rules: ['Puntúa si se ataca 2º palo con 2+ llegadas.'],
				                },
				                edge_box: {
				                  title_suffix: 'disparo frontal',
				                  coaching: ['Orientar el control para disparar: pie de apoyo y superficie.'],
				                  rules: ['Puntúa si el disparo sale tras 1–2 pases y control orientado.'],
				                },
				                finishing_2v1: {
				                  title_suffix: 'finalización 2v1',
				                  coaching: ['Con balón: fija al defensor antes de asistir. Sin balón: trayectoria al espacio.'],
				                  rules: ['Puntúa doble si el 2v1 acaba en gol.'],
				                },
				                finishing_3v2: {
				                  title_suffix: 'finalización 3v2',
				                  coaching: ['Atacar en oleada, ocupar carriles y finalizar rápido.'],
				                  rules: ['Máximo 8–10s por oleada.'],
				                },
				              },
				              pressing: {
				                high: {
				                  title_suffix: 'presión alta',
				                  coaching: ['Orientar hacia banda y saltar en trigger.'],
				                  rules: ['Punto extra si robas y finalizas en 6s.'],
				                },
				                mid: {
				                  title_suffix: 'bloque medio',
				                  coaching: ['Distancias cortas entre líneas, cierres interiores.'],
				                  rules: ['No se permite presión individual sin cobertura.'],
				                },
				                trap_wide: {
				                  title_suffix: 'trampa en banda',
				                  coaching: ['Cierra carril interior y atrapa en lateral.'],
				                  rules: ['Puntúa si fuerzas pérdida en banda.'],
				                },
				                cover_shadow: {
				                  title_suffix: 'sombra de cobertura',
				                  coaching: ['Correr tapando línea de pase al pivote/entre líneas.'],
				                  rules: ['Puntúa si bloqueas pase interior y recuperas.'],
				                },
				                press_triggers: {
				                  title_suffix: 'triggers',
				                  coaching: ['Triggers: pase atrás, control malo, receptor de espaldas.'],
				                  rules: ['Solo se salta a presionar en trigger.'],
				                },
				              },
				              counterpress: {
				                '5s': { title_suffix: 'regla 5s', coaching: ['Tras pérdida: 5s de máxima intención para recuperar o frenar.'] },
				                '6s': { title_suffix: 'regla 6s', coaching: ['Tras pérdida: 6s de máxima intención y cobertura.'] },
				                rest_defense: { title_suffix: 'rest-defense', coaching: ['Estructura por detrás del balón para estar “preparado” para la pérdida.'] },
				                protect_center: { title_suffix: 'proteger centro', coaching: ['Tras pérdida: prioridad carril central y espalda de mediocentros.'] },
				              },
				              defending: {
				                protect_central: { title_suffix: 'proteger centro', coaching: ['Cerrar carril central; orientar fuera.'] },
				                deny_between_lines: { title_suffix: 'negar entre líneas', coaching: ['No permitir recepciones a la espalda del medio.'] },
				                defend_depth: { title_suffix: 'defender profundidad', coaching: ['Línea lista para correr hacia atrás; perfil y distancias.'] },
				                defend_cross: { title_suffix: 'defender centros', coaching: ['Cierre 2º palo y zona punto penal; roles claros.'] },
				                block_shift: { title_suffix: 'basculación', coaching: ['Basculación rápida y cierres del lado débil.'] },
				              },
				              transition_atd: {
				                counterpress: { title_suffix: 'contra-presión', coaching: ['Tras pérdida: primer paso y orientación correctos.'] },
				                delay: { title_suffix: 'temporizar', coaching: ['Si no se puede recuperar: temporiza para reorganizar.'] },
				                foul_or_stop: { title_suffix: 'cortar transición', coaching: ['Si procede: cortar con falta táctica o impedir avance.'] },
				              },
				              transition_dta: {
				                counterattack_central: { title_suffix: 'contraataque por dentro', coaching: ['Primer pase vertical al carril central.'] },
				                counterattack_wide: { title_suffix: 'contraataque por fuera', coaching: ['Abrir rápido a banda para correr.'] },
				                secure_then_go: { title_suffix: 'asegurar y atacar', coaching: ['Asegura el 1º pase si no hay ventaja inmediata.'] },
				                third_man_run: { title_suffix: 'ruptura 3º hombre', coaching: ['3º hombre ataca el espacio tras apoyo.'] },
				              },
				              duels: {
				                '1v1_wide': { title_suffix: '1v1 banda', coaching: ['Atacar el espacio, cambio de ritmo y proteger balón.'] },
				                '1v1_central': { title_suffix: '1v1 central', coaching: ['Cerrar perfil y orientar al rival a su lado débil.'] },
				                '2v1': { title_suffix: '2v1', coaching: ['Fijar y soltar con ventaja; apoyo en diagonal.'] },
				                '1v2': { title_suffix: '1v2', coaching: ['Conservar y esperar apoyo; proteger balón.'] },
				                shielding: { title_suffix: 'protección', coaching: ['Cadera entre rival y balón; escudo y giro.'] },
				                tackling: { title_suffix: 'entrada/robo', coaching: ['Temporiza y entra cuando el balón está “lejos” del pie.'] },
				              },
				              set_pieces: {
				                corner_attack: { title_suffix: 'córner ofensivo', coaching: ['Roles: bloqueos, remate, segunda jugada.'] },
				                corner_defend: { title_suffix: 'córner defensivo', coaching: ['Marcaje y zonas: 1º palo, punto penal, 2º palo.'] },
				                fk_direct: { title_suffix: 'falta directa', coaching: ['Rutina 1–2 opciones: tiro o pase.'] },
				                fk_indirect: { title_suffix: 'falta indirecta', coaching: ['Centro con timing + segundas jugadas.'] },
				                throw_in: { title_suffix: 'saque de banda', coaching: ['Desmarques cortos/largos y 3ª opción.'] },
				                kickoff: { title_suffix: 'saque inicial', coaching: ['Señal, apoyo y progresión segura.'] },
				                second_ball: { title_suffix: 'segundas jugadas', coaching: ['Estructura para capturar rechaces y atacar rápido.'] },
				              },
				              coord: {
				                injury_prevention: { title_suffix: 'prevención', coaching: ['Tobillo-rodilla-cadera: estabilidad y control.'] },
				                speed_mechanics: { title_suffix: 'técnica de carrera', coaching: ['Postura, braceo, apoyo bajo centro de gravedad.'] },
				                agility_cods: { title_suffix: 'agilidad/COD', coaching: ['Frenada, apoyos, salida; progresión.'] },
				                balance: { title_suffix: 'equilibrio', coaching: ['Equilibrio estático/dinámico + perturbaciones.'] },
				              },
				            };

					            const applySubphase = (tpl, goalKey, subKey) => {
					              if (!tpl || !goalKey || !subKey || subKey === 'auto') return tpl;
				              const preset = SUBPHASE_PRESETS?.[goalKey]?.[subKey];
				              if (!preset) return tpl;
				              const next = { ...tpl };
				              const label = smartSubphaseLabel || preset.title_suffix || subKey;
				              if (preset.title_suffix) {
				                next.title = `${String(next.title || '').trim()} · ${preset.title_suffix}`;
				              } else if (label) {
				                next.title = `${String(next.title || '').trim()} · ${label}`;
				              }
				              if (preset.training_type) next.training_type = preset.training_type;
				              if (preset.objective_suffix) {
				                next.objective = next.objective ? `${next.objective} (${preset.objective_suffix})` : preset.objective_suffix;
				              }
				              next.description_html = appendBullets(next.description_html, preset.description || []);
				              next.coaching_html = appendBullets(next.coaching_html, preset.coaching || []);
				              next.rules_html = appendBullets(next.rules_html, preset.rules || []);
				              if (preset.board && Array.isArray(preset.board.items)) {
				                next.board = preset.board;
				              }
					              return next;
					            };

					            const addSections = (tpl, sections) => {
					              if (!tpl || typeof tpl !== 'object') return tpl;
					              const s = sections && typeof sections === 'object' ? sections : {};
					              const next = { ...tpl };
					              if (s.progression_html && next.progression_html == null) next.progression_html = String(s.progression_html);
					              if (s.regression_html && next.regression_html == null) next.regression_html = String(s.regression_html);
					              if (s.success_criteria_html && next.success_criteria_html == null) next.success_criteria_html = String(s.success_criteria_html);
					              return next;
					            };

					            // Plantillas "UEFA-style": siempre intenta incluir progresión, regresión y criterio de éxito.
					            const SECTIONS_BY_GOAL = {
					              warmup: {
					                progression_html: '<ul><li>Reduce espacio / sube toques mínimos.</li><li>Añade estímulo (señal/colores) o balón tras dominio.</li></ul>',
					                regression_html: '<ul><li>Amplía espacio y baja intensidad.</li><li>Quita reglas (libre) hasta asegurar técnica.</li></ul>',
					                success_criteria_html: '<ul><li>Intensidad progresiva sin fatiga.</li><li>Técnica limpia: control orientado y pase con ventaja.</li></ul>',
					              },
					              build_up: {
					                progression_html: '<ul><li>Limita toques en primera línea.</li><li>Presión rival más agresiva o +1 defensor.</li><li>Añade objetivo de finalizar tras superar 1ª línea.</li></ul>',
					                regression_html: '<ul><li>Más tiempo/espacio (zona mayor).</li><li>Defensores condicionados (solo interceptar).</li><li>Permite “comodín” para asegurar salida.</li></ul>',
					                success_criteria_html: '<ul><li>Superas 1ª línea con ventaja (pase tenso / conducción).</li><li>Jugadores perfilados y con escalonamiento.</li></ul>',
					              },
					              progression: {
					                progression_html: '<ul><li>Obliga a progresar por zonas (3 zonas).</li><li>Reduce espacio o añade 1 defensor.</li><li>Puntúa doble tras cambio de orientación.</li></ul>',
					                regression_html: '<ul><li>Añade comodines (4v4+2/3).</li><li>Aumenta el ancho del campo.</li></ul>',
					                success_criteria_html: '<ul><li>El equipo encuentra al hombre libre y supera líneas con intención.</li><li>Recepciones perfiladas (entre líneas/half-space).</li></ul>',
					              },
					              final_third: {
					                progression_html: '<ul><li>Finalizar en ventana de 6–8s.</li><li>Añade defensor recuperando (transición).</li><li>Restricción: 1 contacto en zona de remate.</li></ul>',
					                regression_html: '<ul><li>Superioridad ofensiva (3v2/4v3).</li><li>Permite 2–3 toques extra para ajustar.</li></ul>',
					                success_criteria_html: '<ul><li>Finalización con decisión (tiro/pase atrás/centro) y ocupación de zonas (1º/2º palo/punto penal).</li></ul>',
					              },
					              pressing: {
					                progression_html: '<ul><li>Activa triggers obligatorios (pase atrás, control malo, receptor de espaldas).</li><li>Reduce espacio para aumentar densidad.</li></ul>',
					                regression_html: '<ul><li>Bloque medio sin saltos largos (distancias).</li><li>Permite comodín para estabilizar posesión rival.</li></ul>',
					                success_criteria_html: '<ul><li>Robo coordinado (orientar + coberturas) y finalización/ataque rápido tras recuperar.</li></ul>',
					              },
					              counterpress: {
					                progression_html: '<ul><li>Regla 5s para recuperar o replegar.</li><li>Puntúa doble si recuperas y finalizas en 6–8s.</li></ul>',
					                regression_html: '<ul><li>Permite 1 pase “seguro” tras pérdida antes de presionar.</li><li>Aumenta el espacio para reducir estrés.</li></ul>',
					                success_criteria_html: '<ul><li>Tras pérdida: reacción inmediata + protección carril central.</li></ul>',
					              },
					              defending: {
					                progression_html: '<ul><li>Limita zonas de defensa (carril central prioritario).</li><li>Añade “tercer hombre” atacante para exigir coberturas.</li></ul>',
					                regression_html: '<ul><li>Atacantes con restricciones (máximo 2 toques).</li><li>Zona más pequeña y roles más claros.</li></ul>',
					                success_criteria_html: '<ul><li>Bloque compacto: distancias entre líneas, basculación y cierres del lado débil.</li></ul>',
					              },
					              transition_atd: {
					                progression_html: '<ul><li>Ventana 5s: o recuperas o repliegas a bloque.</li><li>Añade gol/objetivo tras robo del rival.</li></ul>',
					                regression_html: '<ul><li>Permite 1 pase rival antes de contraatacar.</li><li>Reduce número de atacantes en transición.</li></ul>',
					                success_criteria_html: '<ul><li>Tras pérdida: primera acción correcta (sprint, orientar, temporizar) y reorganización.</li></ul>',
					              },
					              transition_dta: {
					                progression_html: '<ul><li>Finalizar en 6–8s tras recuperar.</li><li>Añade defensor recuperando desde atrás.</li></ul>',
					                regression_html: '<ul><li>Superioridad ofensiva inicial (3v2).</li><li>Más espacio para conducir y decidir.</li></ul>',
					                success_criteria_html: '<ul><li>Primer pase seguro + siguiente vertical si aparece; ocupación de carriles.</li></ul>',
					              },
					              duels: {
					                progression_html: '<ul><li>Puntúa doble si el 1v1 acaba en tiro.</li><li>Añade apoyo (2v1) tras 3s.</li></ul>',
					                regression_html: '<ul><li>Espacio mayor para más tiempo de decisión.</li><li>Defensor condicionado (solo orientar).</li></ul>',
					                success_criteria_html: '<ul><li>Atacante: cambio de ritmo y protección; defensor: perfil, temporizar y robar limpio.</li></ul>',
					              },
					              set_pieces: {
					                progression_html: '<ul><li>Añade segundas jugadas + transición defensiva.</li><li>Introduce 2 variantes con señal.</li></ul>',
					                regression_html: '<ul><li>Menos oposiciones (sin saltos) para fijar timing.</li><li>Solo 1 variante hasta dominar.</li></ul>',
					                success_criteria_html: '<ul><li>Roles claros, timing y ejecución tensa (centro/pase).</li></ul>',
					              },
					              coord: {
					                progression_html: '<ul><li>Añade balón tras dominio del patrón.</li><li>Aumenta velocidad y exige calidad técnica.</li></ul>',
					                regression_html: '<ul><li>Menos estaciones / patrón más simple.</li><li>Más descanso y control postural.</li></ul>',
					                success_criteria_html: '<ul><li>Movimientos estables (tobillo/rodilla/cadera) y técnica limpia antes de intensidad.</li></ul>',
					              },
					            };
					            const applySections = (goalKey, tpl) => addSections(tpl, SECTIONS_BY_GOAL[String(goalKey || '').trim()] || {});

					            const warmup = (isSenior)
				              ? {
				                  title: `Activación con balón · rondo + movilidad (${levelLabel})`,
			                  objective: 'Activar con balón: movilidad dinámica + toma de decisión a baja/media intensidad.',
			                  minutes: Math.max(8, minutes),
			                  block: 'activation',
			                  player_count: '6–12',
			                  dimensions: '2 rondos 8x8 m',
			                  materials: 'Balones, conos, petos',
			                  space: '2 zonas',
			                  training_type: 'Activación con balón',
			                  description_html: `
			                    <ul>
			                      <li>Rondo 4v1/5v2 por bloques cortos.</li>
			                      <li>Entre bloques: movilidad dinámica (cadera/tobillo) y cambios de ritmo suaves.</li>
			                    </ul>
			                  `,
			                  coaching_html: `
			                    <ul>
			                      <li>Perfil corporal antes de recibir, control orientado y pase con ventaja.</li>
			                      <li>Sube intensidad de forma progresiva sin fatigar.</li>
			                    </ul>
			                  `,
			                  rules_html: '<ul><li>2 toques recomendado; cambia defensores al recuperar.</li></ul>',
			                  board: {
			                    items: [
			                      { payload: { kind: 'shape_rect' }, x: 0.34, y: 0.48, scale: 1.2 },
			                      { payload: { kind: 'shape_rect' }, x: 0.66, y: 0.48, scale: 1.2 },
			                      { payload: { kind: 'ball' }, x: 0.34, y: 0.48 },
			                      { payload: { kind: 'ball' }, x: 0.66, y: 0.48 },
			                      { payload: { kind: 'player_local' }, x: 0.30, y: 0.44 },
			                      { payload: { kind: 'player_local' }, x: 0.38, y: 0.44 },
			                      { payload: { kind: 'player_local' }, x: 0.30, y: 0.52 },
			                      { payload: { kind: 'player_local' }, x: 0.38, y: 0.52 },
			                      { payload: { kind: 'player_rival' }, x: 0.34, y: 0.48 },
			                      { payload: { kind: 'player_local' }, x: 0.62, y: 0.44 },
			                      { payload: { kind: 'player_local' }, x: 0.70, y: 0.44 },
			                      { payload: { kind: 'player_local' }, x: 0.62, y: 0.52 },
			                      { payload: { kind: 'player_local' }, x: 0.70, y: 0.52 },
			                      { payload: { kind: 'player_rival' }, x: 0.66, y: 0.48 },
			                    ],
			                  },
			                }
			              : {
			                  title: `Activación con balón · juegos simples (${levelLabel})`,
			                  objective: 'Activar jugando: conducción, coordinación y diversión con balón.',
			                  minutes: Math.max(8, minutes),
			                  block: 'activation',
			                  player_count: 'Todo el equipo',
			                  dimensions: '25x20 m',
			                  materials: 'Balones, conos, petos',
			                  space: 'Rectángulo',
			                  training_type: 'Activación',
			                  description_html: '<ul><li>Juego “pilla-pilla con balón” + cambios de dirección.</li><li>Mini retos: cambio de pie, giro, frenada.</li></ul>',
			                  coaching_html: '<ul><li>Una consigna cada vez.</li><li>Muchos contactos y sonrisas.</li></ul>',
			                  rules_html: '<ul><li>Seguridad: cabeza arriba, sin entradas.</li></ul>',
			                  board: base.fund_adapted_game_coord?.board || null,
			                };

			            const buildUp = {
			              title: `Salida y progresión · juego posicional (${levelLabel})`,
			              objective: 'Mejorar salida y progresión: crear líneas de pase, atraer y superar presión.',
			              minutes: Math.max(12, minutes),
			              block: isSenior ? 'main_1' : 'main_1',
			              player_count: isSenior ? '6v4 + porteros (ajustable)' : '5v3 (ajustable)',
			              dimensions: isSenior ? '45x35 m' : '35x25 m',
			              materials: 'Balones, petos, conos, 2 porterías',
			              space: '1/2 campo (o 2/3)',
			              training_type: 'Salida',
			              description_html: `
			                <ul>
			                  <li>Equipo en posesión construye desde atrás para progresar a zona objetivo.</li>
			                  <li>Equipo rival presiona con reglas para provocar repeticiones.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Portero/centrales: atraer para liberar al 6/8.</li>
			                  <li>Laterales: altura y amplitud; extremo fija por fuera.</li>
			                  <li>Tercer hombre y cambios de orientación cuando se cierra un lado.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Puntúa por salir limpio a zona objetivo o superar línea con control.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'goal' }, x: 0.18, y: 0.50 },
			                  { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
			                  { payload: { kind: 'shape_rect_long' }, x: 0.50, y: 0.50, scale: 2.2 },
			                  { payload: { kind: 'player_local' }, x: 0.26, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.30, y: 0.42 },
			                  { payload: { kind: 'player_local' }, x: 0.30, y: 0.58 },
			                  { payload: { kind: 'player_local' }, x: 0.36, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.42, y: 0.44 },
			                  { payload: { kind: 'player_local' }, x: 0.42, y: 0.56 },
			                  { payload: { kind: 'player_rival' }, x: 0.52, y: 0.44 },
			                  { payload: { kind: 'player_rival' }, x: 0.52, y: 0.56 },
			                  { payload: { kind: 'player_rival' }, x: 0.58, y: 0.50 },
			                  { payload: { kind: 'player_rival' }, x: 0.62, y: 0.50 },
			                  { payload: { kind: 'ball' }, x: 0.26, y: 0.50 },
			                ],
			              },
			            };

			            const press = {
			              title: `Presión tras pérdida · recuperar en 6s (${levelLabel})`,
			              objective: 'Organizar presión tras pérdida: reacción, cierres de línea de pase y recuperación.',
			              minutes: Math.max(10, minutes),
			              block: isSenior ? 'main_1' : 'main_1',
			              player_count: isSenior ? '5v5 + 2 comodines' : '4v4 + 2 comodines',
			              dimensions: isSenior ? '30x25 m' : '25x20 m',
			              materials: 'Balones, petos, conos',
			              space: 'Zona media',
			              training_type: 'Presión',
			              description_html: `
			                <ul>
			                  <li>Posesión con comodines para continuidad.</li>
			                  <li>Al perder: 6 segundos para recuperar o replegar a bloque medio.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Primer defensor: sprint + orientar.</li>
			                  <li>Segundo/tercero: cerrar líneas de pase (no correr “a lo loco”).</li>
			                  <li>Comunicación: “voy”, “cubro”, “cierro dentro/fuera”.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Recuperación en 6s = 2 puntos; si no, replegar y reiniciar.</li></ul>',
			              board: base.fund_conservation_pass?.board || null,
			            };

			            const finish = {
			              title: `Finalización · 3v2 + portero (${levelLabel})`,
			              objective: 'Finalizar con ventaja: decidir entre tiro, pase al 2º palo o conducción.',
			              minutes: Math.max(12, minutes),
			              block: 'main_2',
			              player_count: isSenior ? '3v2 + portero' : '2v1 + portero',
			              dimensions: isSenior ? '35x25 m' : '28x20 m',
			              materials: 'Balones, petos, conos, portería',
			              space: 'Zona de finalización',
			              training_type: 'Finalización',
			              description_html: `
			                <ul>
			                  <li>Oleadas a zona de finalización con superioridad ofensiva.</li>
			                  <li>Busca finalización rápida con lectura del defensor y portero.</li>
			                </ul>
			              `,
			              coaching_html: `
			                <ul>
			                  <li>Atacante con balón: fija al defensor antes de asistir.</li>
			                  <li>Segundo palo: llegada a tiempo, no demasiado pronto.</li>
			                  <li>Portero: achique y comunicación.</li>
			                </ul>
			              `,
			              rules_html: '<ul><li>Máximo 8–10s por oleada; rotación inmediata.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
			                  { payload: { kind: 'goalkeeper_local' }, x: 0.78, y: 0.50 },
			                  { payload: { kind: 'player_local' }, x: 0.56, y: 0.44 },
			                  { payload: { kind: 'player_local' }, x: 0.56, y: 0.56 },
			                  { payload: { kind: 'player_local' }, x: 0.50, y: 0.50 },
			                  { payload: { kind: 'player_rival' }, x: 0.66, y: 0.46 },
			                  { payload: { kind: 'player_rival' }, x: 0.66, y: 0.54 },
			                  { payload: { kind: 'ball' }, x: 0.52, y: 0.50 },
			                  { payload: { kind: 'arrow_thick' }, x: 0.64, y: 0.50 },
			                ],
			              },
			            };

			            const transition = {
			              title: `Transición ataque-defensa · 5s reacción (${levelLabel})`,
			              objective: 'Reaccionar a la pérdida/recuperación: decisión rápida y organización inmediata.',
			              minutes: Math.max(10, minutes),
			              block: 'main_2',
			              player_count: isSenior ? '6v6' : '4v4',
			              dimensions: isSenior ? '35x30 m' : '25x20 m',
			              materials: 'Balones, petos, conos',
			              space: 'Partido condicionado',
			              training_type: 'Transición',
			              description_html: '<ul><li>Juego reducido con regla: tras pérdida, 5s para recuperar o replegar.</li><li>Tras recuperación, 5s para finalizar o progresar.</li></ul>',
			              coaching_html: '<ul><li>Primer paso tras pérdida/recuperación: sprint + dirección correcta.</li><li>Orientación del cuerpo para ver balón y rival.</li></ul>',
			              rules_html: '<ul><li>Puntúa doble si finalizas en ventana de 5s.</li></ul>',
			              board: base.fund_dribble_game?.board || null,
			            };

			            const coord = base.fund_coord_circuit;

			            const progression = applyPrinciple({
			              ...(base.fund_conservation_pass || {}),
			              title: `Progresión · conservación + zonas (${levelLabel})`,
			              objective: 'Progresar mediante pases: fijar, atraer y encontrar la zona libre.',
			              block: isSenior ? 'main_1' : 'main_1',
			            });
			            const finalThird = applyPrinciple(finish);
			            const pressing = applyPrinciple({
			              ...press,
			              title: `Presión organizada · robar y finalizar (${levelLabel})`,
			              objective: 'Coordinar presión para recuperar y atacar rápido.',
			              block: 'main_1',
			            });
			            const counterpress = applyPrinciple(press);
			            const defending = applyPrinciple({
			              title: `Defensa en bloque · cierres y basculación (${levelLabel})`,
			              objective: 'Defender en bloque: temporizar, cerrar líneas y proteger zona central.',
			              minutes: Math.max(10, minutes),
			              block: 'main_1',
			              player_count: isSenior ? '6v6 (bloque vs ataque)' : '4v4 (bloque vs ataque)',
			              dimensions: isSenior ? '40x30 m' : '30x22 m',
			              materials: 'Petos, conos, balones',
			              space: 'Zona media',
			              training_type: 'Defensa en bloque',
			              description_html: '<ul><li>Equipo defensor en bloque medio/bajo; el atacante busca progresar.</li><li>Reinicia tras robo o salida.</li></ul>',
			              coaching_html: '<ul><li>Distancias entre líneas, basculación y coberturas.</li><li>Orientar al rival hacia fuera.</li></ul>',
			              rules_html: '<ul><li>Punto por robo + salida; punto por progresión del ataque.</li></ul>',
			              board: buildUp?.board || null,
			            });
			            const transitionATD = applyPrinciple(transition);
			            const transitionDTA = applyPrinciple({
			              title: `Transición defensa-ataque · atacar espacio (${levelLabel})`,
			              objective: 'Tras recuperar: atacar espacio libre con 2–3 pases y finalización.',
			              minutes: Math.max(10, minutes),
			              block: 'main_2',
			              player_count: isSenior ? '5v5' : '4v4',
			              dimensions: isSenior ? '35x28 m' : '28x20 m',
			              materials: 'Balones, petos, conos, porterías',
			              space: 'Partido condicionado',
			              training_type: 'Transición',
			              description_html: '<ul><li>Tras recuperación hay ventana de 6–8s para finalizar.</li><li>Si no hay opción, conservar y reorganizar.</li></ul>',
			              coaching_html: '<ul><li>Primer pase seguro, segundo vertical si aparece.</li><li>Desmarques de ruptura y apoyo por detrás.</li></ul>',
			              rules_html: '<ul><li>Gol en ventana de transición = doble.</li></ul>',
			              board: base.fund_dribble_game?.board || null,
			            });
			            const duels = applyPrinciple(base.fund_oleadas_1v1 || base.fund_conservation_2v1);
			            const setPieces = applyPrinciple({
			              title: `ABP · diseño y roles (${levelLabel})`,
			              objective: 'Diseñar ABP: roles, timing y segundas jugadas.',
			              minutes: Math.max(10, minutes),
			              block: 'set_pieces',
			              player_count: 'Todo el equipo',
			              dimensions: 'Zona de área',
			              materials: 'Balones, conos',
			              space: 'Área + puntos de referencia',
			              training_type: 'ABP',
			              description_html: '<ul><li>Define 1–2 ABP (córner/falta) y repite con corrección.</li><li>Incluye segundas jugadas y transición defensiva.</li></ul>',
			              coaching_html: '<ul><li>Roles claros (bloqueos, remate, segunda jugada).</li><li>Timing y señales.</li></ul>',
			              rules_html: '<ul><li>Repeticiones cortas; calidad en ejecución.</li></ul>',
			              board: {
			                items: [
			                  { payload: { kind: 'goal' }, x: 0.86, y: 0.50, angle: 180 },
			                  { payload: { kind: 'ball' }, x: 0.74, y: 0.30 },
			                  { payload: { kind: 'player_local' }, x: 0.72, y: 0.46 },
			                  { payload: { kind: 'player_local' }, x: 0.74, y: 0.52 },
			                  { payload: { kind: 'player_local' }, x: 0.78, y: 0.46 },
			                  { payload: { kind: 'player_rival' }, x: 0.80, y: 0.52 },
			                  { payload: { kind: 'player_rival' }, x: 0.82, y: 0.46 },
			                  { payload: { kind: 'arrow_curve' }, x: 0.78, y: 0.44 },
			                ],
			              },
			            });

				            const mapping = {
				              warmup: applySections('warmup', warmup),
				              build_up: applySections('build_up', applyPrinciple(buildUp)),
				              progression: applySections('progression', progression),
				              final_third: applySections('final_third', finalThird),
				              pressing: applySections('pressing', pressing),
				              counterpress: applySections('counterpress', counterpress),
				              defending: applySections('defending', defending),
				              transition_atd: applySections('transition_atd', transitionATD),
				              transition_dta: applySections('transition_dta', transitionDTA),
				              duels: applySections('duels', duels),
				              set_pieces: applySections('set_pieces', setPieces),
				              coord: applySections('coord', applyPrinciple(coord)),
				            };

				            const pick = mapping[goal] || progression;
				            const pickBase = pick ? { ...pick } : null;
				            // Ajustes suaves por edad.
				            if (isYoung && pickBase) {
				              pickBase.block = 'activation';
				              pickBase.minutes = Math.max(8, Math.min(15, minutes));
				              pickBase.dimensions = pickBase.dimensions || '25x20 m';
				            }
				            // Añade una pista de material si el usuario la ha escrito.
					            if (materialsHint) {
					              try {
					                if (pickBase) {
					                  pickBase.materials = pickBase.materials ? `${pickBase.materials} · ${materialsHint}` : materialsHint;
					                }
					              } catch (e) { /* ignore */ }
					            }
					            const pickWithSubphase = applyAgebandHints(applySubphase((pickBase || pick), goal, smartSubphase));
						            const cooldown = {
						              title: `Vuelta a la calma · movilidad + respiración (${levelLabel})`,
						              objective: 'Bajar pulsaciones, recuperar movilidad y cerrar con feedback breve.',
						              minutes: Math.max(6, Math.min(12, Math.round(minutes * 0.8))),
				              block: 'recovery',
				              player_count: 'Todo el equipo',
				              dimensions: 'Zona central',
				              materials: 'Conos (opcional)',
				              space: 'Zona central',
				              training_type: 'Recuperación',
				              description_html: `
				                <ul>
				                  <li>Jog suave + movilidad dinámica suave (cadera, tobillo, isquios).</li>
				                  <li>Respiración/relajación 2–3 min y feedback rápido.</li>
				                </ul>
				              `,
				              coaching_html: `
				                <ul>
				                  <li>Control de respiración, postura y amplitud progresiva.</li>
				                  <li>Cierra con 1 idea: qué se hizo bien y qué mejorar.</li>
				                </ul>
				              `,
						              rules_html: '<ul><li>Sin competición. Prioriza recuperación.</li></ul>',
						              board: { items: [{ payload: { kind: 'text' }, x: 0.50, y: 0.50 }] },
						            };
						            const cooldownTpl = applyAgebandHints(cooldown);

					            const buildExternalKnowledgeCandidates = () => {
					              // Usamos recursos públicos como inspiración y enlazamos a la fuente.
					              // El texto/estructura de la tarea es propio (no copiamos el contenido original).
						              const tc = {
						                name: 'FIFA Training Centre',
						                urls: {
						                  u8_teambuilding: 'https://www.fifatrainingcentre.com/en/practice/grassroots/4-to-8/teambuilding.php',
						                  u12_switch_play: 'https://www.fifatrainingcentre.com/en/practice/grassroots/8-to-12/switch-of-play.php',
						                  u12_unopposed_warmups: 'https://www.fifatrainingcentre.com/en/practice/grassroots/grassroots-and-youth-football-essentials/grassroots-coaching-essentials/stanley-2-focusing-on-technical-skills-in-unopposed-warm-ups.php',
						                  attacking_reduced: 'https://www.fifatrainingcentre.com/en/practice/talent-coach-programme/sessions/attacking-games-with-reduced-numbers.php',
						                },
						              };

					              const list = [];
					              const push = (id, tpl, meta = {}) => {
					                if (!tpl) return;
					                list.push({
					                  id,
					                  tpl: { ...tpl },
					                  meta: { ...meta },
					                });
					              };

						              push(
						                'kb_tc_u8_tag',
					                {
					                  title: `Activación · persecución por parejas (${levelLabel})`,
					                  objective: 'Elevar temperatura y activar coordinación en un juego de persecución divertido.',
					                  minutes: Math.max(8, Math.min(12, minutes)),
					                  block: 'activation',
					                  player_count: 'Parejas (o tríos si impar)',
					                  dimensions: '2–4 mini zonas (8x8 m aprox.)',
					                  materials: 'Conos, petos (opcional)',
					                  space: 'Zonas con “casa”',
					                  training_type: 'Juego de activación',
					                  age_group: 'u8',
					                  description_html: `
					                    <ul>
					                      <li>Organiza parejas enfrentadas: a la señal, uno persigue y el otro escapa hasta su “casa”.</li>
					                      <li>Varía desplazamientos: lateral, atrás, skipping, cambios de ritmo.</li>
					                      <li>Progresión: añade balón en conducción cuando domine (sin perder calidad).</li>
					                    </ul>
					                  `,
					                  coaching_html: `
					                    <ul>
					                      <li>Postura y apoyos: correr “con control”, no solo rápido.</li>
					                      <li>Señales cortas: una consigna por bloque.</li>
					                    </ul>
					                  `,
					                  rules_html: '<ul><li>Sin contacto. Cambia roles cada 20–30s.</li></ul>',
					                  board: {
					                    items: [
					                      { payload: { kind: 'shape_rect' }, x: 0.34, y: 0.50, scale: 1.2 },
					                      { payload: { kind: 'shape_rect' }, x: 0.66, y: 0.50, scale: 1.2 },
					                      { payload: { kind: 'player_local' }, x: 0.30, y: 0.45 },
					                      { payload: { kind: 'player_rival' }, x: 0.38, y: 0.55 },
					                      { payload: { kind: 'arrow_thick' }, x: 0.34, y: 0.50 },
					                      { payload: { kind: 'player_local' }, x: 0.62, y: 0.45 },
					                      { payload: { kind: 'player_rival' }, x: 0.70, y: 0.55 },
					                      { payload: { kind: 'arrow_thick' }, x: 0.66, y: 0.50 },
					                    ],
					                  },
					                  source_name: tc.name,
					                  source_url: tc.urls.u8_teambuilding,
					                },
					                { goal: 'warmup', age, format: 'game', intensity: 'low', subphase: (goal === 'warmup' ? smartSubphase : 'auto') },
					              );

						              push(
						                'kb_tc_u12_unopposed',
						                {
						                  title: `Calentamiento técnico (sin oposición) (${levelLabel})`,
						                  objective: 'Repetir gestos técnicos a baja/media intensidad antes del juego con oposición.',
						                  minutes: Math.max(8, Math.min(12, minutes)),
						                  block: 'activation',
						                  player_count: 'Grupos de 3–5',
						                  dimensions: '10–20 m por estación',
						                  materials: 'Balones, conos, mini vallas (opcional)',
						                  space: 'Circuito por estaciones',
						                  training_type: 'Técnica (sin oposición)',
						                  age_group: 'u12',
						                  description_html: `
						                    <ul>
						                      <li>Estaciones de técnica básica: pase/recepción, conducción, coordinación.</li>
						                      <li>En cada estación: calidad técnica + ritmo progresivo.</li>
						                      <li>Cierra con 1 mini reto competitivo corto (sin fatiga).</li>
						                    </ul>
						                  `,
						                  coaching_html: `
						                    <ul>
						                      <li>Equilibrio entre técnica y velocidad: primero limpio, luego rápido.</li>
						                      <li>Feedback corto: 1 corrección cada vez.</li>
						                    </ul>
						                  `,
						                  rules_html: '<ul><li>Rotación cada 60–90s.</li></ul>',
						                  board: base.fund_coord_circuit?.board || null,
						                  source_name: tc.name,
						                  source_url: tc.urls.u12_unopposed_warmups,
						                },
						                { goal: 'warmup', age, format: 'circuit', intensity: 'low' },
						              );

						              push(
						                'kb_tc_attack_numbers',
					                {
					                  title: `Ataque · superioridades y finalización (${levelLabel})`,
					                  objective: 'Atacar con agresividad: crear 2v1, fijar y finalizar con decisión.',
					                  minutes: Math.max(12, Math.min(20, minutes)),
					                  block: 'main_1',
					                  player_count: '2v2, 3v2, 4v4 (adaptable)',
					                  dimensions: isSenior ? '40x30 m' : '30x22 m',
					                  materials: 'Balones, petos, conos, porterías',
					                  space: 'Zona de ataque',
					                  training_type: 'Ataque',
					                  description_html: `
					                    <ul>
					                      <li>Secuencias cortas de ataque con superioridad (2v1 / 3v2) para repetir decisiones “fijar + soltar”.</li>
					                      <li>Tras cada acción, reinicia rápido para acumular repeticiones de calidad.</li>
					                      <li>Termina en juego reducido con objetivo de finalizar en 6–8s.</li>
					                    </ul>
					                  `,
					                  coaching_html: `
					                    <ul>
					                      <li>Con balón: fija al defensor antes de asistir; cambia de ritmo para ganar ventaja.</li>
					                      <li>Sin balón: desmarque con intención (apoyo/ruptura) y orientar el cuerpo hacia portería.</li>
					                    </ul>
					                  `,
					                  rules_html: '<ul><li>Gol en 6–8s = doble (ventana de decisión).</li></ul>',
					                  board: {
					                    items: [
					                      { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
					                      { payload: { kind: 'goalkeeper_local' }, x: 0.78, y: 0.50 },
					                      { payload: { kind: 'player_local' }, x: 0.54, y: 0.44 },
					                      { payload: { kind: 'player_local' }, x: 0.54, y: 0.56 },
					                      { payload: { kind: 'player_rival' }, x: 0.66, y: 0.46 },
					                      { payload: { kind: 'player_rival' }, x: 0.66, y: 0.54 },
					                      { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
					                      { payload: { kind: 'arrow_thick' }, x: 0.60, y: 0.50 },
					                    ],
					                  },
					                  source_name: tc.name,
					                  source_url: tc.urls.attacking_reduced,
					                },
					                { goal: 'final_third', age, format: 'ssg', intensity: 'high' },
						              );

						              push(
						                'kb_tc_u12_switch_play',
						                {
						                  title: `Progresión · cambio de orientación (${levelLabel})`,
						                  objective: 'Atraer por un lado y atacar el lado débil con cambio de orientación.',
						                  minutes: Math.max(10, Math.min(18, minutes)),
						                  block: 'main_1',
						                  player_count: '1v1/2v2 + rotaciones',
						                  dimensions: isSenior ? '35x25 m' : '30x20 m',
						                  materials: 'Balones, conos, 4 mini porterías',
						                  space: 'Campo con 4 porterías',
						                  training_type: 'Juego reducido',
						                  age_group: 'u12',
						                  description_html: `
						                    <ul>
						                      <li>Juego con 4 mini porterías: puntúa cambiando de lado antes de finalizar.</li>
						                      <li>Progresión: llama 2 números (2v2) y exige cambio de orientación.</li>
						                    </ul>
						                  `,
						                  coaching_html: `
						                    <ul>
						                      <li>Cabeza arriba: identifica el lado débil rápido.</li>
						                      <li>Pase tenso al pie más alejado y primer control orientado.</li>
						                    </ul>
						                  `,
						                  rules_html: '<ul><li>Gol tras cambio de orientación = doble.</li></ul>',
						                  board: base.fund_match_2v1?.board || null,
						                  source_name: tc.name,
						                  source_url: tc.urls.u12_switch_play,
						                },
						                { goal: 'progression', age, format: 'game', intensity: 'medium' },
						              );

					              return list.filter((item) => {
					                const g = String(item?.meta?.goal || '').trim();
					                if (!g) return false;
					                if (goal === 'warmup') return g === 'warmup';
					                return g === goal;
					              });
					            };
				            // Catálogo de candidatos (mínimo viable).
					            const catalog = [];
					            const inferComplexity = () => {
					              const lvl = String(level || '1').trim();
					              if (lvl === '3') return 'high';
					              if (lvl === '2') return 'medium';
					              return 'low';
					            };
					            const DEFAULT_SYSTEM_META = {
					              warmup: { strategy: 'circuit', dynamics: 'extensive', structure: 'complete', coordination: 'player', coordination_skills: 'movements', tactical_intent: 'maintain' },
					              coord: { strategy: 'circuit', dynamics: 'speed', structure: 'sectorial', coordination: 'player', coordination_skills: 'direction_change', tactical_intent: 'maintain' },
					              physical_field: { strategy: 'circuit', dynamics: 'endurance', structure: 'sectorial', coordination: 'player', coordination_skills: 'start_stop', tactical_intent: 'maintain' },
					              physical_gym: { strategy: 'circuit', dynamics: 'strength', structure: 'sectorial', coordination: 'player', coordination_skills: 'balance', tactical_intent: 'maintain' },
					              build_up: { strategy: 'positional', dynamics: 'intense_interaction', structure: 'intersectorial', coordination: 'team', coordination_skills: 'pass', tactical_intent: 'build' },
					              progression: { strategy: 'positional', dynamics: 'intense_interaction', structure: 'intersectorial', coordination: 'team', coordination_skills: 'pass', tactical_intent: 'progress' },
					              final_third: { strategy: 'reduced_games', dynamics: 'intense_interaction', structure: 'complete', coordination: 'team', coordination_skills: 'shots', tactical_intent: 'finish' },
					              pressing: { strategy: 'reduced_games', dynamics: 'intense_interaction', structure: 'complete', coordination: 'team', coordination_skills: 'interceptions', tactical_intent: 'press' },
					              counterpress: { strategy: 'reduced_games', dynamics: 'intense_interaction', structure: 'complete', coordination: 'team', coordination_skills: 'interceptions', tactical_intent: 'press' },
					              defending: { strategy: 'lines_work', dynamics: 'intense_interaction', structure: 'complete', coordination: 'team', coordination_skills: 'tackles', tactical_intent: 'def_organized' },
					              transition_atd: { strategy: 'waves', dynamics: 'intense_action', structure: 'intersectorial', coordination: 'team', coordination_skills: 'start_stop', tactical_intent: 'counter' },
					              transition_dta: { strategy: 'waves', dynamics: 'intense_action', structure: 'intersectorial', coordination: 'team', coordination_skills: 'start_stop', tactical_intent: 'counter' },
					              duels: { strategy: 'reduced_games', dynamics: 'intense_action', structure: 'sectorial', coordination: 'players', coordination_skills: 'balance', tactical_intent: '1v1' },
					              set_pieces: { strategy: 'abp', dynamics: 'adm', structure: 'sectorial', coordination: 'team', coordination_skills: 'pass', tactical_intent: 'abp_att' },
					            };
					            const inferPlayersMinMaxFromText = (value) => {
					              const text = String(value || '').toLowerCase().trim();
					              if (!text) return { min: 0, max: 0 };

					              const keeperMatch = text.match(/(\d+)\s*(?:p|porteros|portero)\b/);
					              const keeperCount = keeperMatch
					                ? (Number.parseInt(keeperMatch[1], 10) || 0)
					                : (text.includes('porteros') ? 2 : (text.includes('portero') ? 1 : 0));

					              const totals = [];
					              try {
					                const rx = /(\d+)\s*v\s*(\d+)(?:\s*\+\s*(\d+))?/g;
					                let match;
					                // eslint-disable-next-line no-cond-assign
					                while ((match = rx.exec(text)) !== null) {
					                  const a = Number.parseInt(match[1], 10) || 0;
					                  const b = Number.parseInt(match[2], 10) || 0;
					                  const c = Number.parseInt(match[3] || '0', 10) || 0;
					                  if (a || b || c) totals.push(a + b + c);
					                }
					              } catch (e) {}

					              // Ej: "14+2P"
					              const plusP = text.match(/(\d+)\s*\+\s*(\d+)\s*p\b/);
					              if (plusP) {
					                const a = Number.parseInt(plusP[1], 10) || 0;
					                const b = Number.parseInt(plusP[2], 10) || 0;
					                if (a || b) totals.push(a + b);
					              }

					              // Rangos (ej: 5-8 por lado).
					              const range = text.match(/(\d+)\s*[–-]\s*(\d+)/);
					              if (!totals.length && range) {
					                const lo = Number.parseInt(range[1], 10) || 0;
					                const hi = Number.parseInt(range[2], 10) || 0;
					                if (lo && hi) {
					                  const isPerSide = text.includes('por lado') || text.includes('por equipo') || text.includes('por lado');
					                  totals.push((isPerSide ? (2 * lo) : lo));
					                  totals.push((isPerSide ? (2 * hi) : hi));
					                }
					              }

					              if (!totals.length) return { min: 0, max: 0 };
					              let min = Math.min(...totals);
					              let max = Math.max(...totals);
					              if (keeperCount) {
					                min += keeperCount;
					                max += keeperCount;
					              }
					              return { min: Math.max(0, min), max: Math.max(0, max) };
					            };
					            const applySystemMeta = (goalKey, tpl, meta = {}) => {
					              if (!tpl || typeof tpl !== 'object') return tpl;
					              const g = String(goalKey || '').trim() || String(meta.goal || '').trim();
					              const base = DEFAULT_SYSTEM_META[g] || DEFAULT_SYSTEM_META[String(meta.goal || '').trim()] || null;
					              const out = { ...(tpl || {}) };
					              const format = String(meta.format || '').trim();
					              const subphase = String(meta.subphase || '').trim();

					              const setIfEmpty = (key, value) => {
					                if (!value) return;
					                const cur = out[key];
					                if (cur == null || String(cur).trim() === '') out[key] = value;
					              };

					              const complexity = inferComplexity();
					              if (subphase === 'cooldown' || String(out.block || '') === 'recovery') {
					                setIfEmpty('dynamics', 'recovery');
					                setIfEmpty('coordination', 'player');
					                setIfEmpty('coordination_skills', 'movements');
					                setIfEmpty('tactical_intent', 'maintain');
					                setIfEmpty('complexity', 'low');
					              } else {
					                setIfEmpty('complexity', complexity);
					              }

					              if (base) {
					                setIfEmpty('strategy', base.strategy);
					                setIfEmpty('dynamics', base.dynamics);
					                setIfEmpty('structure', base.structure);
					                setIfEmpty('coordination', base.coordination);
					                setIfEmpty('coordination_skills', base.coordination_skills);
					                setIfEmpty('tactical_intent', base.tactical_intent);
					              }

					              // Ajustes por formato si viene definido.
					              if (format === 'circuit') setIfEmpty('strategy', 'circuit');
					              if (format === 'ssg' || format === 'game') setIfEmpty('strategy', 'reduced_games');
					              if (format === 'analytic') setIfEmpty('strategy', 'combined');

					              return out;
					            };
					            const addCandidate = (id, tpl, meta = {}) => {
					              if (!tpl) return;
					              const goalKey = meta.goal || goal;
					              const enrichedTpl = applySystemMeta(goalKey, tpl, meta);
					              const inferred = inferPlayersMinMaxFromText(enrichedTpl?.player_count);
					              const playersMin = (meta.players_min != null && Number(meta.players_min)) ? Number(meta.players_min) : (Number(inferred.min) || 0);
					              const playersMax = (meta.players_max != null && Number(meta.players_max)) ? Number(meta.players_max) : (Number(inferred.max) || 0);
					              catalog.push({
					                id: String(id || '').trim(),
					                tpl: enrichedTpl,
					                meta: {
					                  goal: meta.goal || goal,
					                  age,
					                  subphase: meta.subphase || 'auto',
					                  format: meta.format || 'auto',
					                  intensity: meta.intensity || 'auto',
					                  players_min: playersMin,
					                  players_max: playersMax,
					                },
					              });
					            };
					            addCandidate(
					              'smart_warmup',
					              (goal === 'warmup' ? applySubphase(mapping.warmup, 'warmup', smartSubphase) : mapping.warmup),
					              { goal: 'warmup', subphase: (goal === 'warmup' ? smartSubphase : 'auto'), format: isSenior ? 'ssg' : 'game', intensity: 'low' },
					            );
					            addCandidate('smart_main', pickWithSubphase, { goal, subphase: smartSubphase, format: (goal === 'coord' ? 'circuit' : 'game') });

					            const addVariant = (id, goalKey, baseTpl, overrides = {}, meta = {}) => {
					              if (!baseTpl) return;
					              const merged = { ...(baseTpl || {}), ...(overrides || {}) };
					              const withSections = applySections(goalKey, merged);
					              const withSub = applySubphase(withSections, goalKey, smartSubphase);
					              addCandidate(id, withSub, { goal: goalKey, subphase: meta.subphase || 'auto', format: meta.format || 'auto', intensity: meta.intensity || 'auto' });
					            };

					            // Variantes "reales" por objetivo: 30+ tareas base (antes de sub-fases/principios).
					            addVariant(
					              'smart_build_3lanes',
					              'build_up',
					              mapping.build_up,
					              {
					                title: `Salida · 3 carriles + zonas objetivo (${levelLabel})`,
					                dimensions: isSenior ? '55x40 m (3 carriles)' : '40x28 m (3 carriles)',
					                player_count: isSenior ? '7v6 + porteros (adaptable)' : '5v4 (adaptable)',
					                rules_html: '<ul><li>Progresar de carril (cambio de carril) = 1 punto.</li><li>Superar 1ª línea y encontrar al pivote = 2 puntos.</li></ul>',
					              },
					              { format: 'game' },
					            );
					            addVariant(
					              'smart_build_exit_gates',
					              'build_up',
					              mapping.build_up,
					              {
					                title: `Salida · superar 1ª línea por puertas (${levelLabel})`,
					                dimensions: isSenior ? '45x35 m + 2 puertas' : '35x25 m + 2 puertas',
					                rules_html: '<ul><li>Punto si progresas atravesando una puerta con control o pase.</li><li>Tras puerta, finaliza en 6–8s (doble).</li></ul>',
					              },
					              { format: 'ssg' },
					            );
					            addVariant(
					              'smart_build_pattern',
					              'build_up',
					              mapping.build_up,
					              {
					                title: `Salida · patrón 3+2 (semi-oposición) (${levelLabel})`,
					                player_count: '6–10 (rotaciones)',
					                training_type: 'Patrón / repetición con oposición ligera',
					                rules_html: '<ul><li>Empieza siempre en portero. Secuencia: central → pivote → lateral/extremo → progresión.</li></ul>',
					              },
					              { format: 'analytic', intensity: 'medium' },
					            );

					            addVariant(
					              'smart_prog_3v3plus3',
					              'progression',
					              mapping.progression,
					              {
					                title: `Progresión · 3v3 + 3 comodines (${levelLabel})`,
					                player_count: '3v3 + 3 (2 fuera + 1 interior)',
					                dimensions: isSenior ? '32x26 m' : '28x20 m',
					                rules_html: '<ul><li>Puntúa por encontrar comodín interior y progresar a zona objetivo.</li></ul>',
					              },
					              { format: 'ssg' },
					            );
					            addVariant(
					              'smart_prog_switch',
					              'progression',
					              mapping.progression,
					              {
					                title: `Progresión · atraer y cambiar (${levelLabel})`,
					                rules_html: '<ul><li>Tras 4 pases en un lado, el cambio al lado débil es obligatorio.</li><li>Cambio y progresión = doble.</li></ul>',
					              },
					              { format: 'game' },
					            );
					            addVariant(
					              'smart_prog_between_lines',
					              'progression',
					              mapping.progression,
					              {
					                title: `Progresión · encontrar entre líneas (${levelLabel})`,
					                rules_html: '<ul><li>Gol/punto solo si hay recepción entre líneas y giro o pase vertical.</li></ul>',
					              },
					              { format: 'ssg' },
					            );

					            addVariant(
					              'smart_final_cross',
					              'final_third',
					              mapping.final_third,
					              {
					                title: `Último tercio · centros + zonas de remate (${levelLabel})`,
					                training_type: 'Finalización (centros)',
					                rules_html: '<ul><li>Remate 1º/2º palo o punto penal = válido.</li><li>Pase atrás a frontal = doble.</li></ul>',
					              },
					              { format: 'game', intensity: 'high' },
					            );
					            addVariant(
					              'smart_final_cutback',
					              'final_third',
					              mapping.final_third,
					              {
					                title: `Último tercio · llegar a línea y pase atrás (${levelLabel})`,
					                rules_html: '<ul><li>Solo puntúa si el gol llega tras pase atrás (cutback).</li></ul>',
					              },
					              { format: 'ssg', intensity: 'high' },
					            );
						            addVariant(
						              'smart_final_waves',
						              'final_third',
						              mapping.final_third,
						              {
						                title: `Finalización · oleadas 3v2 (${levelLabel})`,
						                player_count: isSenior ? '3v2 + portero' : '2v1/3v2',
						                rules_html: '<ul><li>Máximo 10s por oleada. Rotación inmediata.</li></ul>',
						              },
						              { format: 'analytic', intensity: 'high' },
						            );
						            addVariant(
						              'smart_final_3v3_eq',
						              'final_third',
						              mapping.final_third,
						              {
						                title: `Finalización · 3v3 + porteros (igualdad) (${levelLabel})`,
						                objective: 'Resolver finalización en espacio reducido con ritmo alto y foco en remate/1v1.',
						                training_type: 'Juego reducido (finalización)',
						                block: 'main_1',
						                minutes: Math.max(10, Math.min(16, minutes)),
						                player_count: '3v3 + 2 porteros',
						                dimensions: isSenior ? '35x25 m' : (isYoung ? '22x16 m' : '30x20 m'),
						                materials: 'Balones, conos, 2 porterías, petos',
						                space: 'Rectángulo con 2 porterías',
						                drills: ['acceleration', 'deceleration', 'change_direction'],
						                description_html: `
						                  <ul>
						                    <li>Juego 3v3 + porteros en espacio reducido. Objetivo: finalizar rápido.</li>
						                    <li>Provoca 1v1, tiros tras conducción corta y segundas jugadas.</li>
						                    <li>Tras gol o salida, reinicia el portero (ritmo alto).</li>
						                  </ul>
						                `,
						                coaching_html: `
						                  <ul>
						                    <li>Atacante: prepara el tiro con 1–2 toques útiles; finaliza con ventaja.</li>
						                    <li>Defensor: acosa al poseedor y cierra líneas de tiro tras pérdida.</li>
						                    <li>Portero: juego rápido para dar continuidad.</li>
						                  </ul>
						                `,
						                rules_html: '<ul><li>Opcional: gol a 1 toque = doble.</li></ul>',
						                board: {
						                  items: [
						                    { payload: { kind: 'goal' }, x: 0.18, y: 0.50 },
						                    { payload: { kind: 'goalkeeper_local' }, x: 0.22, y: 0.50 },
						                    { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
						                    { payload: { kind: 'goalkeeper_rival' }, x: 0.78, y: 0.50 },
						                    { payload: { kind: 'shape_rect' }, x: 0.50, y: 0.50, scale: 1.55 },
						                    { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
						                    { payload: { kind: 'player_local' }, x: 0.44, y: 0.44 },
						                    { payload: { kind: 'player_local' }, x: 0.44, y: 0.56 },
						                    { payload: { kind: 'player_local' }, x: 0.50, y: 0.50 },
						                    { payload: { kind: 'player_rival' }, x: 0.56, y: 0.44 },
						                    { payload: { kind: 'player_rival' }, x: 0.56, y: 0.56 },
						                    { payload: { kind: 'player_rival' }, x: 0.62, y: 0.50 },
						                  ],
						                },
						              },
						              { format: 'ssg', intensity: 'high', subphase: '3v3_finish' },
						            );
						            addVariant(
						              'smart_final_3v3_defsup',
						              'final_third',
						              mapping.final_third,
						              {
						                title: `Finalización · 3v3 + porteros (defensa +1) (${levelLabel})`,
						                objective: 'Finalizar con poco espacio: defender protege zona y obliga a tiros/segundas jugadas.',
						                training_type: 'Juego reducido (finalización)',
						                block: 'main_1',
						                minutes: Math.max(10, Math.min(16, minutes)),
						                player_count: '3v3 + 2 porteros',
						                dimensions: isSenior ? '38x26 m' : (isYoung ? '24x16 m' : '32x22 m'),
						                materials: 'Balones, conos, 2 porterías, petos',
						                space: 'Rectángulo + zona defensiva marcada',
						                drills: ['deceleration', 'change_direction'],
						                description_html: `
						                  <ul>
						                    <li>Como el 3v3, pero el equipo defensor deja 1 jugador fijo en su zona defensiva.</li>
						                    <li>Objetivo: fomentar protección de espacios y obligar a elegir tiro/último pase.</li>
						                    <li>Variante: tiro desde fuera de zona = doble (si procede).</li>
						                  </ul>
						                `,
						                coaching_html: `
						                  <ul>
						                    <li>Atacante: atrae al defensor fijo y busca ángulos de tiro/pase atrás.</li>
						                    <li>Defensa: equilibrio y cierre tras pérdida; acoso al poseedor.</li>
						                  </ul>
						                `,
						                rules_html: '<ul><li>Defensor fijo no puede salir de su zona (marcada con conos).</li></ul>',
						                board: {
						                  items: [
						                    { payload: { kind: 'goal' }, x: 0.18, y: 0.50 },
						                    { payload: { kind: 'goalkeeper_local' }, x: 0.22, y: 0.50 },
						                    { payload: { kind: 'goal' }, x: 0.82, y: 0.50, angle: 180 },
						                    { payload: { kind: 'goalkeeper_rival' }, x: 0.78, y: 0.50 },
						                    { payload: { kind: 'shape_rect' }, x: 0.50, y: 0.50, scale: 1.55 },
						                    { payload: { kind: 'shape_rect' }, x: 0.30, y: 0.50, scale: 0.75 },
						                    { payload: { kind: 'ball' }, x: 0.50, y: 0.50 },
						                    { payload: { kind: 'player_rival' }, x: 0.30, y: 0.50 },
						                    { payload: { kind: 'player_local' }, x: 0.48, y: 0.44 },
						                    { payload: { kind: 'player_local' }, x: 0.48, y: 0.56 },
						                    { payload: { kind: 'player_rival' }, x: 0.60, y: 0.44 },
						                    { payload: { kind: 'player_rival' }, x: 0.60, y: 0.56 },
						                  ],
						                },
						              },
						              { format: 'ssg', intensity: 'high', subphase: '3v3_finish' },
						            );
						            addVariant(
						              'smart_final_3v3_2touch',
						              'final_third',
						              mapping.final_third,
						              {
						                title: `Finalización · 3v3 + porteros (máx. 2 toques) (${levelLabel})`,
						                objective: 'Aumentar ritmo de decisión y remate/pase final en espacio reducido.',
						                training_type: 'Juego reducido (finalización)',
						                block: 'main_1',
						                minutes: Math.max(10, Math.min(16, minutes)),
						                player_count: '3v3 + 2 porteros',
						                dimensions: isSenior ? '35x25 m' : (isYoung ? '22x16 m' : '30x20 m'),
						                materials: 'Balones, conos, 2 porterías, petos',
						                space: 'Rectángulo con 2 porterías',
						                load_target: isYoung ? 'RPE 6' : 'RPE 7–8',
						                rules_html: '<ul><li>Máximo 2 toques por jugador (U8: libre o 3 toques).</li><li>Tras pérdida, el portero del equipo que recupera reinicia rápido.</li></ul>',
						              },
						              { format: 'ssg', intensity: 'high', subphase: '3v3_finish' },
						            );

					            addVariant(
					              'smart_press_triggers',
					              'pressing',
					              mapping.pressing,
					              {
					                title: `Presión organizada · triggers + coberturas (${levelLabel})`,
					                rules_html: '<ul><li>Triggers: pase atrás, control malo, receptor de espaldas.</li><li>Robo y finalización en 6–8s = doble.</li></ul>',
					              },
					              { format: 'ssg', intensity: 'high' },
					            );
					            addVariant(
					              'smart_press_trap_wide',
					              'pressing',
					              mapping.pressing,
					              {
					                title: `Presión · trampa en banda (${levelLabel})`,
					                rules_html: '<ul><li>Orientar fuera y cerrar carril interior.</li><li>Punto si fuerzas pérdida en banda.</li></ul>',
					              },
					              { format: 'game', intensity: 'high' },
					            );
					            addVariant(
					              'smart_def_block',
					              'defending',
					              mapping.defending,
					              {
					                title: `Defensa en bloque · proteger carril central (${levelLabel})`,
					                rules_html: '<ul><li>El carril central vale doble: no permitir recepciones entre líneas.</li></ul>',
					              },
					              { format: 'game', intensity: 'medium' },
					            );

					            addVariant(
					              'smart_tr_atd_5s',
					              'transition_atd',
					              mapping.transition_atd,
					              {
					                title: `Transición A→D · 5s recuperar o replegar (${levelLabel})`,
					                rules_html: '<ul><li>Tras pérdida: 5s para recuperar; si no, replegar a bloque.</li></ul>',
					              },
					              { format: 'game', intensity: 'high' },
					            );
					            addVariant(
					              'smart_tr_dta_8s',
					              'transition_dta',
					              mapping.transition_dta,
					              {
					                title: `Transición D→A · finalizar en 8s (${levelLabel})`,
					                rules_html: '<ul><li>Tras recuperar: 8s para finalizar o llegar a zona objetivo.</li></ul>',
					              },
					              { format: 'game', intensity: 'high' },
					            );

					            addVariant(
					              'smart_duels_1v1_lanes',
					              'duels',
					              mapping.duels,
					              {
					                title: `Duelos · 1v1 en carriles (${levelLabel})`,
					                player_count: '1v1 (rotaciones rápidas)',
					                dimensions: '12x8 m (carril) x 2–4',
					                rules_html: '<ul><li>Atacante debe cambiar de ritmo.</li><li>Defensor orienta a zona “débil”.</li></ul>',
					              },
					              { format: 'analytic', intensity: 'high' },
					            );

					            addVariant(
					              'smart_abp_corner',
					              'set_pieces',
					              mapping.set_pieces,
					              {
					                title: `ABP · córner ofensivo (roles + 2 variantes) (${levelLabel})`,
					                rules_html: '<ul><li>Ensaya 2 variantes con señal.</li><li>Incluye segunda jugada + transición defensiva.</li></ul>',
					              },
					              { format: 'analytic', intensity: 'medium' },
					            );

					            addVariant(
					              'smart_coord_injury',
					              'coord',
					              mapping.coord,
					              {
					                title: `Prevención · tobillo-rodilla-cadera (${levelLabel})`,
					                training_type: 'Prevención',
					                rules_html: '<ul><li>Pocas repeticiones, mucha calidad. Descanso suficiente.</li></ul>',
					              },
					              { format: 'circuit', intensity: 'low' },
					            );

					            // Variantes por sub-fase (solo para el objetivo actual) para enriquecer sugerencias.
					            try {
				              const presetKeys = Object.keys(SUBPHASE_PRESETS?.[goal] || {});
				              presetKeys.slice(0, 12).forEach((subKey) => {
				                const baseTpl = pickBase || mapping[goal] || pick;
				                const variant = applySubphase(baseTpl, goal, subKey);
				                if (!variant) return;
				                addCandidate(`smart_${goal}_${subKey}`, variant, { goal, subphase: subKey, format: (goal === 'coord' ? 'circuit' : 'game') });
				              });
				            } catch (e) {}
				            addCandidate('smart_alt_1', mapping.progression, { goal: 'progression', format: 'ssg' });
				            addCandidate('smart_alt_2', mapping.duels, { goal: 'duels', format: 'analytic' });
				            addCandidate('smart_alt_3', mapping.build_up, { goal: 'build_up', format: 'game' });
			            addCandidate('smart_alt_4', mapping.pressing, { goal: 'pressing', format: 'ssg' });
			            addCandidate('smart_alt_5', mapping.counterpress, { goal: 'counterpress', format: 'ssg' });
			            addCandidate('smart_alt_6', mapping.final_third, { goal: 'final_third', format: 'analytic' });
			            addCandidate('smart_alt_7', mapping.transition_atd, { goal: 'transition_atd', format: 'game' });
				            addCandidate('smart_alt_8', mapping.transition_dta, { goal: 'transition_dta', format: 'game' });
				            addCandidate('smart_alt_9', mapping.defending, { goal: 'defending', format: 'game' });
				            addCandidate('smart_alt_10', mapping.set_pieces, { goal: 'set_pieces', format: 'analytic' });
				            addCandidate('smart_cooldown', cooldown, { goal: 'warmup', format: 'analytic', intensity: 'low' });
				            try {
				              buildExternalKnowledgeCandidates().forEach((item) => {
				                addCandidate(item.id, item.tpl, item.meta);
				              });
				            } catch (e) {}
				            try {
				              (assistantBlueprints || []).slice(0, 240).forEach((bp) => {
				                const payload = (bp && typeof bp === 'object') ? (bp.payload || {}) : {};
				                const meta = (payload && typeof payload === 'object') ? (payload.meta || {}) : {};
				                const tplRaw = (payload && typeof payload === 'object') ? (payload.tpl || payload.template || {}) : {};
				                if (!tplRaw || typeof tplRaw !== 'object') return;
				                const tpl = { ...tplRaw };
				                // Etiqueta para que el usuario sepa de dónde viene.
				                const scope = String((bp && bp.scope) || '').trim();
				                if (scope === 'system') {
				                  tpl.source_name = tpl.source_name || 'Plantilla del sistema';
				                } else {
				                  tpl.source_name = tpl.source_name || 'Plantilla del equipo';
				                }
				                // Normalizamos canvas_state si viene como string.
				                if (typeof tpl.canvas_state === 'string') {
				                  try { tpl.canvas_state = JSON.parse(tpl.canvas_state); } catch (err) {}
				                }
				                const goalKey = String(meta.goal || meta.focus || meta.phase || '').trim() || goal;
				                const subphaseKey = String(meta.subphase || 'auto').trim() || 'auto';
				                const approachKey = String(meta.approach || meta.methodology || 'auto').trim() || 'auto';
				                const format = (approachKey === 'analytic') ? 'analytic' : ((approachKey === 'systemic') ? 'game' : 'auto');
				                addCandidate(`bp_${bp.id}`, tpl, { goal: goalKey, subphase: subphaseKey, format, intensity: 'auto' });
				              });
				            } catch (e) {}

						            const scoreCandidate = (item) => {
						              const tpl = item?.tpl || {};
						              const meta = item?.meta || {};
						              let score = 0;
					              if (String(meta.goal || '') === goal) score += 50;
				              if (smartSubphase !== 'auto') {
				                const sp = String(meta.subphase || 'auto').trim();
				                if (sp === smartSubphase) score += 20;
				                else if (sp === 'auto') score -= 4;
				                else score -= 2;
				              }
				              if (goal === 'warmup' && String(item.id || '').includes('warmup')) score += 10;
				              if (blockPref !== 'auto' && String(tpl.block || '') === blockPref) score += 12;
				              if (allowedFormatsForApproach && allowedFormatsForApproach.has(String(meta.format || ''))) score += 10;
				              if (allowedFormatsForApproach && !allowedFormatsForApproach.has(String(meta.format || ''))) score -= 6;
			              const tMin = Number(tpl.minutes) || 0;
			              if (tMin) score += Math.max(0, 12 - Math.abs(tMin - minutes));
					              if (playersCount > 0) {
				                // Si no tenemos rango, no penalizamos.
				                const lo = Number(meta.players_min) || 0;
				                const hi = Number(meta.players_max) || 0;
				                // Tolerancia: el entrenador introduce nº TOTAL (aprox). Si se sale por 1–2 jugadores, penaliza poco.
				                const penalty = (diff) => {
				                  const d = Math.max(0, Number(diff) || 0);
				                  if (d <= 0) return 0;
				                  if (d <= 1) return 1;
				                  if (d <= 2) return 3;
				                  return Math.min(12, 4 + (d - 2) * 2);
				                };
				                if (lo && playersCount < lo) score -= penalty(lo - playersCount);
				                if (hi && playersCount > hi) score -= penalty(playersCount - hi);
					              }
					              // Prompt libre: prioriza tareas cuyo texto/objetivo coincide con lo que pide el entrenador.
					              if (promptTokens.length) {
					                try {
					                  const corpusRaw = [
					                    tpl.title,
					                    tpl.objective,
					                    tpl.space,
					                    tpl.dimensions,
					                    tpl.materials,
					                    stripHtml(tpl.description_html),
					                    stripHtml(tpl.coaching_html),
					                    stripHtml(tpl.rules_html),
					                    stripHtml(tpl.progression_html),
					                    stripHtml(tpl.success_criteria_html),
					                  ].join(' ');
					                  const corpusTokens = tokenize(corpusRaw);
					                  const corpusSet = new Set(corpusTokens);
					                  let matches = 0;
					                  promptTokens.forEach((tok) => { if (corpusSet.has(tok)) matches += 1; });
					                  score += Math.min(28, matches * 4);
					                  if (!matches) score -= 2;
					                } catch (e) {}
					              }
					              // Principio elegido: prioriza tareas que ya lo contienen (o vocabulario asociado).
					              if (principle && principle !== 'auto') {
					                try {
					                  const spec = (coachDictionary && coachDictionary.principles && coachDictionary.principles[principle]) ? coachDictionary.principles[principle] : null;
					                  const keys = Array.isArray(spec?.keywords) ? spec.keywords : [];
					                  if (keys.length) {
					                    const corpus = normalizeKey([
					                      tpl.title,
					                      tpl.objective,
					                      tpl.training_type,
					                      stripHtml(tpl.description_html),
					                      stripHtml(tpl.coaching_html),
					                      stripHtml(tpl.rules_html),
					                    ].join(' '));
					                    let hits = 0;
					                    keys.slice(0, 18).forEach((kw) => {
					                      const needle = normalizeKey(kw);
					                      if (needle && corpus.includes(needle)) hits += 1;
					                    });
					                    score += Math.min(18, hits * 4);
					                    if (!hits) score -= 2;
					                  }
					                } catch (e) {}
					              }
						              // Bonus por ficha "completa": hace que la recomendación sea más útil sin tocar el modelo.
						              if (tpl.description_html) score += 2;
						              if (tpl.coaching_html) score += 1;
					              if (tpl.rules_html) score += 1;
					              if (tpl.progression_html) score += 1;
					              if (tpl.success_criteria_html) score += 1;
					              if (tpl.board && Array.isArray(tpl.board.items) && tpl.board.items.length) score += 1;
					              if (tpl.canvas_state && typeof tpl.canvas_state === 'object') score += 1;

					              // Preferencia ligera por plantillas del equipo (si existen).
					              const id = String(item?.id || '');
					              const src = String(tpl.source_name || '').toLowerCase();
					              // Si hay plantillas del equipo, deben dominar el ranking.
					              if (id.startsWith('bp_')) score += 16;
					              if (src.includes('equipo')) score += 4;
				              return score;
				            };

						            const normalizeKey = (value) => String(value || '')
						              .toLowerCase()
						              .replace(/\s+/g, ' ')
						              .replace(/[^a-z0-9áéíóúüñ ]+/gi, '')
						              .trim()
						              .slice(0, 140);
						            const escapeHtml = (value) => String(value == null ? '' : value)
						              .replace(/&/g, '&amp;')
						              .replace(/</g, '&lt;')
						              .replace(/>/g, '&gt;')
						              .replace(/"/g, '&quot;')
						              .replace(/'/g, '&#039;');
						            const stripHtml = (html) => String(html || '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
						            const STOPWORDS = new Set([
						              'de','del','la','el','los','las','un','una','unos','unas','y','o','u','a','en','por','para','con','sin','sobre','entre',
						              'al','se','que','como','más','mas','muy','ya','si','no','lo','su','sus','mi','mis','tu','tus','nuestro','nuestra','vuestro',
						              'cada','todos','todas','todo','toda','este','esta','estos','estas','eso','esa','aquí','ahi','allí','hoy',
						              'hacer','trabajar','provocar','buscar','mejorar','evitar','crear','generar','realizar','aplicar',
						              'juego','partido','tarea','ejercicio','situación','situacion','zona','campo','balón','balon','portería','porteria',
						              'jugador','jugadores','equipo','rival','comodín','comodin',
						            ]);
						            const tokenize = (text) => {
						              const norm = normalizeKey(text);
						              if (!norm) return [];
						              return norm.split(' ').map((t) => String(t || '').trim()).filter((t) => t.length >= 3 && !STOPWORDS.has(t)).slice(0, 64);
						            };
						            const promptTokens = tokenize(smartPrompt).slice(0, 18);
						            const applyPromptToTpl = (tpl) => {
						              if (!tpl || typeof tpl !== 'object') return tpl;
						              const next = { ...tpl };
						              if (smartPrompt) {
						                const note = `<li><strong>Adaptación (descripción):</strong> ${escapeHtml(smartPrompt)}</li>`;
						                next.description_html = (next.description_html || '').includes('<ul>')
						                  ? String(next.description_html || '').replace('</ul>', `${note}</ul>`)
						                  : `<ul>${note}</ul>${ensureListHtml(next.description_html || '')}`;
						              }
						              if (principle && principle !== 'auto') {
						                const spec = (coachDictionary && coachDictionary.principles && coachDictionary.principles[principle]) ? coachDictionary.principles[principle] : null;
						                const label = String(spec?.label || '').trim()
						                  || String(document.getElementById('task-assistant-smart-principle')?.selectedOptions?.[0]?.textContent || '').trim();
						                const points = Array.isArray(spec?.coaching_points) ? spec.coaching_points : [];
						                const line = label
						                  ? `<li><strong>Foco (principio):</strong> ${escapeHtml(label)}${points.length ? ` · ${escapeHtml(String(points[0] || '').trim())}` : ''}</li>`
						                  : '';
						                if (line) {
						                  next.coaching_html = (next.coaching_html || '').includes('<ul>')
						                    ? String(next.coaching_html || '').replace('</ul>', `${line}</ul>`)
						                    : `<ul>${line}</ul>${ensureListHtml(next.coaching_html || '')}`;
						                }
						              }
							              if (materialsHint) {
							                next.materials = String(next.materials || '').trim()
							                  ? String(next.materials || '').trim()
							                  : materialsHint;
							              }
							              return applyAgebandHints(next);
							            };
						            const scoredCandidates = catalog
						              .filter((item) => {
						                if (!item?.tpl) return false;
					                const itemGoal = String(item.meta?.goal || '').trim();
					                if (goal === 'warmup') {
					                  if (itemGoal !== 'warmup') return false;
					                } else {
					                  if (itemGoal !== goal) return false;
					                }
				                if (blockPref !== 'auto' && String(item.tpl.block || '') !== blockPref) return false;
				                if (allowedFormatsForApproach && !allowedFormatsForApproach.has(String(item.meta?.format || ''))) return false;
				                if (smartSubphase !== 'auto') {
				                  const sp = String(item.meta?.subphase || 'auto').trim();
				                  // Permite variantes específicas y, si no hay, la base (auto).
				                  if (sp !== smartSubphase && sp !== 'auto') return false;
					                }
					                return true;
					              })
					              .map((item) => ({ ...item, score: scoreCandidate(item) }));

					            // Dedup: evita sugerir la misma tarea varias veces si entran duplicados por sub-fase/plantillas.
					            const byKey = new Map();
					            scoredCandidates.forEach((item) => {
					              const tpl = item?.tpl || {};
					              const keyParts = [
					                String(item?.meta?.goal || goal),
					                normalizeKey(tpl.title || ''),
					                normalizeKey(tpl.objective || ''),
					                normalizeKey(tpl.dimensions || ''),
					              ].filter(Boolean);
					              const key = keyParts.join('|') || String(item?.id || '');
					              const prev = byKey.get(key);
					              if (!prev || (Number(item.score) || 0) > (Number(prev.score) || 0)) byKey.set(key, item);
					            });
					            const sorted = Array.from(byKey.values()).sort((a, b) => (b.score || 0) - (a.score || 0));
					            const diversifySuggestions = (items, limit = 6) => {
					              const maxPerStrategy = 2;
					              const maxPerTrainingType = 2;
					              const maxPerFormat = 3;
					              const strategyCount = new Map();
					              const trainingCount = new Map();
					              const formatCount = new Map();
					              const picked = [];
					              const canPick = (map, key, max) => (map.get(key) || 0) < max;
					              const inc = (map, key) => map.set(key, (map.get(key) || 0) + 1);
					              const isBlueprint = (it) => String(it?.id || '').startsWith('bp_');
					              const blueprintItems = items.filter((it) => isBlueprint(it));
					              const systemItems = items.filter((it) => !isBlueprint(it));
					              const tryPick = (pool) => {
					                pool.forEach((it) => {
					                  if (picked.length >= limit) return;
					                  const tpl = it?.tpl || {};
					                  const strat = String(tpl.strategy || '').trim() || 'other';
					                  const training = String(tpl.training_type || '').trim() || 'other';
					                  const fmt = String(it?.meta?.format || '').trim() || 'other';
					                  if (!canPick(strategyCount, strat, maxPerStrategy)) return;
					                  if (!canPick(trainingCount, training, maxPerTrainingType)) return;
					                  if (!canPick(formatCount, fmt, maxPerFormat)) return;
					                  picked.push(it);
					                  inc(strategyCount, strat);
					                  inc(trainingCount, training);
					                  inc(formatCount, fmt);
					                });
					              };

					              // Prioriza "tus plantillas" si existen: mete hasta 4 (o deja al menos 2 huecos para sistema).
					              const targetBlueprints = Math.min(
					                blueprintItems.length,
					                Math.max(0, limit - 2),
					                4,
					              );
					              if (targetBlueprints > 0) {
					                blueprintItems.slice(0, targetBlueprints).forEach((it) => {
					                  if (picked.length >= limit) return;
					                  if (picked.includes(it)) return;
					                  const tpl = it?.tpl || {};
					                  const strat = String(tpl.strategy || '').trim() || 'other';
					                  const training = String(tpl.training_type || '').trim() || 'other';
					                  const fmt = String(it?.meta?.format || '').trim() || 'other';
					                  picked.push(it);
					                  // Actualiza contadores para que el resto mantenga algo de variedad.
					                  inc(strategyCount, strat);
					                  inc(trainingCount, training);
					                  inc(formatCount, fmt);
					                });
					              }

					              // Completa con sistema aplicando diversidad.
					              tryPick(systemItems);
					              if (picked.length < limit) {
					                items.forEach((it) => {
					                  if (picked.length >= limit) return;
					                  if (picked.includes(it)) return;
					                  picked.push(it);
					                });
					              }
					              return picked.slice(0, limit);
					            };
						            const suggestions = diversifySuggestions(sorted, 6)
						              .map((item) => (item && item.tpl ? ({ ...item, tpl: applyPromptToTpl(item.tpl) }) : item));

					            const best = suggestions[0]?.tpl || applyPromptToTpl(pickWithSubphase);

					            return {
					              smart_generate: applyAgebandHints(best),
					              smart_suggestions: (Array.isArray(suggestions) ? suggestions : []).map((s) => (s && s.tpl ? ({ ...s, tpl: applyAgebandHints(s.tpl) }) : s)),
					              smart_block_1: applyAgebandHints(warmup),
					              smart_block_2: applyAgebandHints(best),
				              smart_block_3: cooldownTpl,
				            };
				          };

				          const buildTemplatesForProgram = (program) => {
					            const p = String(program || '').trim();
				            if (p === 'fifa11plus') return buildFifa11PlusTemplates();
				            if (p === 'smart') return buildSmartTemplates();
				            if (p === 'fundamentals') return buildFundamentalsTemplates();
				            return {};
				          };

					          const queueRow = document.getElementById('task-assistant-queue');
					          const queueText = document.getElementById('task-assistant-queue-text');
					          const queueNextBtn = document.getElementById('task-assistant-queue-next');
					          const queueClearBtn = document.getElementById('task-assistant-queue-clear');
					          const scopeKey = String(form.dataset.scopeKey || 'coach').trim() || 'coach';
					          const queueKey = `webstats:task_assistant:queue_v1:${scopeKey}`;
					          const smartPromptEl = document.getElementById('task-assistant-smart-prompt');
					          const smartPromptKey = `webstats:task_assistant:smart_prompt_v1:${scopeKey}`;
					          const readSmartPrompt = () => {
					            if (!smartPromptEl) return '';
					            try {
					              const raw = window.localStorage?.getItem(smartPromptKey) || '';
					              return String(raw || '').trim().slice(0, 600);
					            } catch (e) {
					              return '';
					            }
					          };
					          const writeSmartPrompt = (value) => {
					            if (!smartPromptEl) return;
					            try { window.localStorage?.setItem(smartPromptKey, String(value || '').trim().slice(0, 600)); } catch (e) { /* ignore */ }
					          };
					          try {
					            if (smartPromptEl && !String(smartPromptEl.value || '').trim()) {
					              smartPromptEl.value = readSmartPrompt();
					            }
					          } catch (e) { /* ignore */ }
					          let smartPromptTimer = null;
					          smartPromptEl?.addEventListener('input', () => {
					            const value = String(smartPromptEl.value || '').trim().slice(0, 600);
					            writeSmartPrompt(value);
					            // Si ya hay sugerencias en pantalla y estamos en Smart, refresca.
					            if (String(programEl.value || '') !== 'smart') return;
					            if (smartPromptTimer) window.clearTimeout(smartPromptTimer);
					            smartPromptTimer = window.setTimeout(() => {
					              try {
					                const hasContent = smartSuggestionsBox && String(smartSuggestionsBox.innerHTML || '').trim().length > 0;
					                if (hasContent) renderSmartSuggestions();
					              } catch (e) {}
					            }, 220);
					          });
					          const readQueue = () => {
					            try {
					              const raw = window.localStorage?.getItem(queueKey) || '';
				              const parsed = raw ? JSON.parse(raw) : null;
				              const items = Array.isArray(parsed?.items) ? parsed.items : [];
				              return { v: 1, created_at: parsed?.created_at || null, items };
				            } catch (e) {
				              return { v: 1, created_at: null, items: [] };
				            }
				          };
				          const writeQueue = (queue) => {
				            try {
				              const items = Array.isArray(queue?.items) ? queue.items : [];
				              window.localStorage?.setItem(queueKey, JSON.stringify({ v: 1, created_at: queue?.created_at || new Date().toISOString(), items }));
				            } catch (e) { /* ignore */ }
				          };
				          const clearQueue = () => writeQueue({ v: 1, created_at: new Date().toISOString(), items: [] });
				          const setQueueItems = (items) => writeQueue({ v: 1, created_at: new Date().toISOString(), items: Array.isArray(items) ? items : [] });
				          const updateQueueUi = () => {
				            const q = readQueue();
				            const count = q.items.length;
				            if (queueRow) queueRow.hidden = !(count > 0);
				            if (queueText) queueText.textContent = count > 0 ? `Tareas en cola: ${count}.` : '';
				            if (queueNextBtn) queueNextBtn.disabled = !(count > 0);
				            if (queueClearBtn) queueClearBtn.disabled = !(count > 0);
				          };

				          const openNextTask = () => {
				            const q = readQueue();
				            if (!q.items.length) return;
				            const base = String(form.dataset.taskCreateUrl || '').trim();
				            if (!base) {
				              window.alert('No se encontró la URL para crear una nueva tarea.');
				              return;
				            }
				            try {
				              const target = new URL(base, window.location.origin);
				              const current = new URL(window.location.href);
				              const workspace = current.searchParams.get('workspace');
				              if (workspace && !target.searchParams.has('workspace')) target.searchParams.set('workspace', workspace);
				              target.searchParams.set('assistant_next', '1');
				              window.location.href = target.toString();
				            } catch (e) {
				              window.location.href = `${base}?assistant_next=1`;
				            }
				          };

				          queueNextBtn?.addEventListener('click', openNextTask);
				          queueClearBtn?.addEventListener('click', () => {
				            clearQueue();
				            updateQueueUi();
				          });

						          const applyTpl = (tpl, options = {}) => {
					            if (!tpl || typeof tpl !== 'object') return false;
					            const wantsBoard = !!(applyBoardEl && applyBoardEl.checked);
					            const willClearBoard = !!(clearBoardEl && clearBoardEl.checked);
					            const confirmEnabled = options.confirm !== false;
				            if (confirmEnabled) {
				              const confirmMsg = wantsBoard
				                ? (`Esto rellenará campos de la tarea y ${willClearBoard ? 'reemplazará' : 'añadirá a'} la pizarra. ¿Continuar?`)
				                : 'Esto rellenará campos de la tarea actual. ¿Continuar?';
				              const ok = window.confirm(confirmMsg);
				              if (!ok) return false;
				            }

				            if (tpl.title != null) setValue('draw_task_title', tpl.title);
				            if (tpl.objective != null) setValue('draw_task_objective', tpl.objective);
				            if (tpl.block != null) setValue('draw_task_block', tpl.block);
				            if (tpl.minutes != null) setValue('draw_task_minutes', tpl.minutes);
				            if (tpl.player_count != null) setValue('draw_task_player_count', tpl.player_count);
					            if (tpl.dimensions != null) setValue('draw_task_dimensions', tpl.dimensions);
					            if (tpl.materials != null) setValue('draw_task_materials', tpl.materials);
					            if (tpl.space != null) setValue('draw_task_space', tpl.space);
						            if (tpl.training_type) setValue('draw_task_training_type', tpl.training_type);
						            if (tpl.strategy != null) setValue('draw_task_strategy', tpl.strategy);
						            if (tpl.dynamics != null) setValue('draw_task_dynamics', tpl.dynamics);
						            if (tpl.structure != null) setValue('draw_task_structure', tpl.structure);
						            if (tpl.coordination != null) setValue('draw_task_coordination', tpl.coordination);
						            if (tpl.coordination_skills != null) setValue('draw_task_coordination_skills', tpl.coordination_skills);
						            if (tpl.tactical_intent != null) setValue('draw_task_tactical_intent', tpl.tactical_intent);
						            if (tpl.complexity != null) setValue('draw_task_complexity', tpl.complexity);
							            if (tpl.age_group) setValue('draw_task_age_group', tpl.age_group);
						            if (tpl.series != null) setValue('draw_task_series', tpl.series);
						            if (tpl.repetitions != null) setValue('draw_task_repetitions', tpl.repetitions);
						            if (tpl.work_rest != null) setValue('draw_task_work_rest', tpl.work_rest);
					            if (tpl.load_target != null) setValue('draw_task_load_target', tpl.load_target);
						            if (tpl.description_html != null) setRichHtml('draw_task_description', tpl.description_html);
						            if (tpl.coaching_html != null) setRichHtml('draw_task_coaching_points', tpl.coaching_html);
						            if (tpl.rules_html != null) setRichHtml('draw_task_confrontation_rules', tpl.rules_html);
						            if (tpl.progression_html != null) setRichHtml('draw_task_progression', tpl.progression_html);
						            if (tpl.regression_html != null) setRichHtml('draw_task_regression', tpl.regression_html);
						            if (tpl.success_criteria_html != null) setRichHtml('draw_task_success_criteria', tpl.success_criteria_html);
						            if (tpl.drills && Array.isArray(tpl.drills)) {
						              writeDrills(tpl.drills);
						            }

						            if (wantsBoard) {
						              try {
						                const boardItems = (tpl.board && Array.isArray(tpl.board.items)) ? tpl.board.items : [];
						                const drillItems = (tpl.drills && Array.isArray(tpl.drills)) ? buildBoardItemsFromDrills(tpl.drills) : [];
						                const merged = []
						                  .concat(Array.isArray(boardItems) ? boardItems : [])
						                  .concat(Array.isArray(drillItems) ? drillItems : []);
						                if (!merged.length) return;
						                window.dispatchEvent(new CustomEvent('webstats:tpad:assistant-board', {
						                  detail: {
						                    clear: willClearBoard,
						                    items: merged,
						                  },
						                }));
						              } catch (err) {}
						            }
					            if (tpl.canvas_state && typeof tpl.canvas_state === 'object') {
					              try {
					                setValue('draw_canvas_state', JSON.stringify(tpl.canvas_state));
					                if (tpl.canvas_width) setValue('draw_canvas_width', tpl.canvas_width);
					                if (tpl.canvas_height) setValue('draw_canvas_height', tpl.canvas_height);
					              } catch (err) {}
					            }

				            const fichaTab = document.querySelector('#task-side-tabs .side-tab[data-pane="ficha"]');
				            try { fichaTab?.click(); } catch (err) {}
				            return true;
				          };

				          const applyTemplate = (key, options = {}) => {
				            const program = String(programEl.value || '').trim();
				            const templates = buildTemplatesForProgram(program);
				            const tpl = templates[key];
				            if (!tpl) return false;
				            return applyTpl(tpl, options);
				          };

				          Array.from(document.querySelectorAll('[data-assistant-template]')).forEach((btn) => {
				            btn.addEventListener('click', () => {
				              const key = String(btn.getAttribute('data-assistant-template') || '').trim();
				              if (key) applyTemplate(key);
				            });
				          });

				          // Botones Smart.
				          const smartBtn = document.getElementById('task-assistant-smart-generate');
				          const smartSessionBtn = document.getElementById('task-assistant-smart-generate-session');
				          const smartSuggestBtn = document.getElementById('task-assistant-smart-suggest');
				          const smartSuggestionsBox = document.getElementById('task-assistant-smart-suggestions');
				          const pushQueueItem = (tpl) => {
				            if (!tpl) return;
				            const q = readQueue();
				            q.items = Array.isArray(q.items) ? q.items : [];
				            q.items.push(tpl);
				            writeQueue(q);
				            updateQueueUi();
				          };
								          const renderSmartSuggestions = () => {
								            if (!smartSuggestionsBox) return;
								            const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
								              '&': '&amp;',
							              '<': '&lt;',
							              '>': '&gt;',
								              '"': '&quot;',
								              "'": '&#39;',
								            }[ch] || ch));
							            const selectLabelFor = (fieldName, rawValue) => {
							              const value = String(rawValue ?? '').trim();
							              if (!value) return '';
							              try {
							                const sel = form?.querySelector?.(`[name="${String(fieldName || '').trim()}"]`);
							                if (sel && String(sel.tagName || '').toUpperCase() === 'SELECT') {
							                  const opt = Array.from(sel.options || []).find((o) => String(o.value || '') === value);
							                  const label = String(opt?.textContent || '').trim();
							                  return label || value;
							                }
							              } catch (e) { /* ignore */ }
							              return value;
							            };
							            const safeTplHtml = (html) => {
							              const raw = String(html ?? '').trim();
							              if (!raw) return '';
							              try {
							                const parser = new DOMParser();
							                const doc = parser.parseFromString(raw, 'text/html');
							                const allowed = new Set(['UL', 'OL', 'LI', 'BR', 'B', 'STRONG', 'I', 'EM', 'U', 'P', 'DIV', 'SPAN']);
							                const walk = (node) => {
							                  if (!node) return;
							                  const kids = Array.from(node.childNodes || []);
							                  kids.forEach((child) => {
							                    if (child.nodeType === 1) {
							                      const tag = String(child.tagName || '').toUpperCase();
							                      if (tag === 'SCRIPT' || tag === 'STYLE') {
							                        try { child.remove(); } catch (e) {}
							                        return;
							                      }
							                      if (!allowed.has(tag)) {
							                        // Reemplaza el nodo por su texto.
							                        const txt = doc.createTextNode(child.textContent || '');
							                        try { child.replaceWith(txt); } catch (e) {}
							                        return;
							                      }
							                      // Limpia atributos peligrosos.
							                      try {
							                        Array.from(child.attributes || []).forEach((attr) => {
							                          const name = String(attr?.name || '').toLowerCase();
							                          if (name.startsWith('on') || name === 'style' || name === 'href' || name === 'src') {
							                            try { child.removeAttribute(attr.name); } catch (e) {}
							                          }
							                        });
							                      } catch (e) {}
							                      walk(child);
							                    }
							                  });
							                };
							                walk(doc.body);
							                return String(doc.body.innerHTML || '').trim();
							              } catch (e) {
							                return escapeHtml(raw);
							              }
							            };
							            const stripTags = (html) => String(html ?? '')
							              .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')
							              .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')
							              .replace(/<[^>]+>/g, ' ')
							              .replace(/\s+/g, ' ')
						              .trim();
						            const clipText = (text, maxLen = 220) => {
						              const t = String(text || '').trim();
						              if (!t) return '';
						              return t.length > maxLen ? `${t.slice(0, Math.max(0, maxLen - 1))}…` : t;
						            };
							            const clamp01 = (value) => {
							              const n = Number(value);
							              if (!Number.isFinite(n)) return 0.5;
							              return Math.max(0.02, Math.min(0.98, n));
							            };
							            const canvasPreviewCache = window.__webstatsSmartPreviewCache || new Map();
							            window.__webstatsSmartPreviewCache = canvasPreviewCache;
							            const renderPitchPreviewFromCanvasState = async (pitchEl, tpl, cacheKeyHint = '') => {
							              if (!pitchEl) return false;
							              const state = tpl?.canvas_state;
							              if (!state || typeof state !== 'object') return false;
							              const fabricLib = window.fabric;
							              if (!fabricLib || typeof fabricLib.StaticCanvas !== 'function') return false;
							              const w = Number(tpl?.canvas_width) || 1280;
							              const h = Number(tpl?.canvas_height) || 720;
								              const signature = (() => {
								                try {
								                  const objects = Array.isArray(state.objects) ? state.objects : [];
								                  const sample = objects.slice(0, 12).map((obj) => String(obj?.type || obj?.data?.kind || '')).join('|');
								                  const len = (() => {
								                    try { return JSON.stringify(objects.slice(0, 25)).length; } catch (e) { return 0; }
								                  })();
								                  return `${w}x${h}:${objects.length}:${sample}:${len}`;
								                } catch (e) {
								                  return `${w}x${h}:${Number((state.objects || []).length) || 0}`;
								                }
								              })();
								              const keyBase = String(cacheKeyHint || tpl?.source_url || tpl?.source_name || 'cs').trim() || 'cs';
								              const key = `${keyBase}:${signature}`;
							              const cached = canvasPreviewCache.get(key);
							              if (cached) {
							                pitchEl.innerHTML = `<img class="assistant-suggestion-canvasimg" alt="" src="${cached}" />`;
							                return true;
							              }
							              // Placeholder mientras renderiza.
							              pitchEl.innerHTML = '<div class="meta" style="padding:0.55rem; opacity:0.85;">Generando vista previa…</div>';
							              try {
							                const offscreen = document.createElement('canvas');
							                offscreen.width = Math.max(240, Math.min(1600, w));
							                offscreen.height = Math.max(180, Math.min(1200, h));
							                const sc = new fabricLib.StaticCanvas(offscreen, { renderOnAddRemove: false });
							                try { sc.backgroundColor = null; } catch (e) {}
							                const json = {
							                  version: state.version || '5.3.0',
							                  objects: Array.isArray(state.objects) ? state.objects : [],
							                };
							                await new Promise((resolve) => {
							                  try {
							                    sc.loadFromJSON(json, () => {
							                      try { sc.renderAll(); } catch (e) {}
							                      resolve(true);
							                    });
							                  } catch (e) {
							                    resolve(false);
							                  }
							                });
							                const multiplier = Math.max(0.18, Math.min(0.38, 420 / Math.max(1, offscreen.width)));
							                const dataUrl = sc.toDataURL({ format: 'png', multiplier });
							                try { sc.dispose(); } catch (e) {}
							                if (dataUrl && typeof dataUrl === 'string' && dataUrl.startsWith('data:image/')) {
							                  canvasPreviewCache.set(key, dataUrl);
							                  pitchEl.innerHTML = `<img class="assistant-suggestion-canvasimg" alt="" src="${dataUrl}" />`;
							                  return true;
							                }
							              } catch (e) {
							                // ignore
							              }
							              return false;
							            };
								            const renderPitchPreview = (pitchEl, item, idxHint = 0) => {
								              if (!pitchEl) return;
								              pitchEl.innerHTML = '';
								              const tpl = (item && typeof item === 'object' && item.tpl) ? (item.tpl || {}) : (item || {});
								              const cacheKey = String((item && item.id) || '').trim() || `idx:${Number(idxHint) || 0}`;
								              const boardItems = (tpl?.board && Array.isArray(tpl.board.items)) ? tpl.board.items : [];
								              const drillItems = (tpl?.drills && Array.isArray(tpl.drills))
								                ? buildBoardItemsFromDrills(tpl.drills, { maxIcons: 12, desiredSize: 56 })
								                : [];

								              const renderNoBoard = () => {
								                const msg = document.createElement('div');
								                msg.className = 'meta';
								                msg.style.cssText = 'padding:0.55rem; opacity:0.85;';
								                msg.textContent = 'Sin pizarra.';
								                pitchEl.appendChild(msg);
								              };
								              const renderFromItems = (items) => {
								                if (!Array.isArray(items) || !items.length) return false;
								                const pickEmoji = (kind) => {
								                  const k = String(kind || '').trim();
								                  const map = {
								                    emoji_ladder: '🪜',
								                    emoji_hurdle: '🟧',
								                    emoji_cones: '🔺',
								                    emoji_poles: '🟨',
								                    emoji_mini_goal: '🥅',
								                    emoji_gates: '🚪',
								                    emoji_whistle: '🎺',
								                  };
								                  return map[k] || '';
								                };
									                const makeItemEl = (kind, angle = 0, item = null) => {
									                  const k = String(kind || '').trim();
									                  if (k.startsWith('image_url:')) {
									                    const el = document.createElement('div');
									                    el.className = 'assistant-suggestion-item is-circle is-asset';
									                    const img = document.createElement('img');
									                    img.src = k.slice('image_url:'.length);
									                    img.alt = '';
									                    img.draggable = false;
									                    el.appendChild(img);
									                    return el;
									                  }
									                  if (k.startsWith('shape_')) {
									                    const shape = document.createElement('div');
									                    shape.className = 'assistant-suggestion-shape';
									                    const rotate = Number.isFinite(Number(angle)) ? Number(angle) : 0;
									                    shape.style.transform = `translate(-50%, -50%) rotate(${rotate}deg)`;
									                    const rawScale = Number(item?.scale || item?.payload?.scale || 1) || 1;
									                    const s = Math.max(0.55, Math.min(3.0, rawScale));
									                    let baseW = 76;
									                    let baseH = 52;
									                    if (k === 'shape_rect_long') { baseW = 110; baseH = 44; }
					                    if (k === 'shape_lane_3' || k === 'shape_lane_4' || k === 'shape_lane_5') { baseW = 64; baseH = 150; shape.classList.add('is-lane'); }
					                    if (k === 'shape_grid_120') { baseW = 148; baseH = 122; shape.classList.add('is-lane'); }
									                    shape.style.width = `${Math.round(baseW * s)}px`;
									                    shape.style.height = `${Math.round(baseH * s)}px`;
									                    return shape;
									                  }
									                  const el = document.createElement('div');
									                  el.className = 'assistant-suggestion-item';
									                  const rotate = Number.isFinite(Number(angle)) ? Number(angle) : 0;
									                  el.style.transform = `translate(-50%, -50%) rotate(${rotate}deg)`;
									                  const emoji = pickEmoji(k);
								                  if (emoji) {
								                    el.classList.add('is-circle');
								                    el.textContent = emoji;
								                    el.style.fontSize = '14px';
								                    return el;
								                  }
									                  if (k === 'goal') {
									                    el.classList.add('is-goal');
									                    el.textContent = '';
									                    return el;
									                  }
									                  if (k === 'goal_mini') {
									                    el.classList.add('is-goal');
									                    el.style.width = '18px';
									                    el.style.height = '10px';
									                    el.style.borderWidth = '2px';
									                    return el;
									                  }
									                  if (k === 'cone' || k === 'cone_striped') {
									                    el.classList.add('is-cone');
									                    el.textContent = '';
									                    return el;
									                  }
								                  if (k === 'ring') {
								                    el.classList.add('is-ring', 'is-circle');
								                    el.textContent = '';
								                    return el;
								                  }
									                  if (k === 'arrow_solid' || k === 'arrow_dotted' || k === 'arrow_curve' || k === 'arrow_thick') {
									                    el.classList.add('is-arrow', 'is-circle');
									                    el.textContent = '➜';
									                    return el;
									                  }
									                  if (k === 'ball') {
									                    el.classList.add('is-ball', 'is-circle');
									                    el.textContent = '⚽';
									                    el.style.fontSize = '13px';
									                    return el;
									                  }
									                  if (k === 'goalkeeper_local' || k === 'goalkeeper_rival') {
									                    el.classList.add('is-circle', 'is-keeper');
									                    if (k === 'goalkeeper_rival') el.classList.add('is-rival');
									                    el.textContent = 'PT';
									                    el.style.fontSize = '10px';
									                    return el;
									                  }
									                  if (k === 'player_local') {
									                    el.classList.add('is-local', 'is-circle');
									                    el.textContent = 'L';
									                    return el;
									                  }
									                  if (k === 'player_away') {
									                    el.classList.add('is-rival', 'is-circle');
									                    el.textContent = 'A';
									                    return el;
									                  }
									                  if (k === 'player_rival') {
									                    el.classList.add('is-rival', 'is-circle');
									                    el.textContent = 'R';
									                    return el;
									                  }
								                  if (k === 'text') {
								                    el.classList.add('is-circle');
								                    el.textContent = 'T';
								                    return el;
								                  }
								                  el.classList.add('is-circle');
								                  el.textContent = '•';
								                  return el;
								                };
									                items.slice(0, 120).forEach((it) => {
									                  const kind = it?.payload?.kind;
									                  const node = makeItemEl(kind, it?.angle || 0, it || null);
									                  if (String(kind || '').trim() === 'text') {
									                    const rawText = String(it?.payload?.text || it?.payload?.value || '').trim();
									                    if (rawText) node.textContent = rawText.slice(0, 2).toUpperCase();
									                  }
									                  node.style.left = `${clamp01(it?.x) * 100}%`;
									                  node.style.top = `${clamp01(it?.y) * 100}%`;
									                  pitchEl.appendChild(node);
									                });
								                return true;
								              };

								              // Prioridad: si hay canvas_state, pintamos la miniatura real (usa recursos/pizarra real).
								              if (tpl?.canvas_state && typeof tpl.canvas_state === 'object') {
								                renderPitchPreviewFromCanvasState(pitchEl, tpl, cacheKey).then((ok) => {
								                  if (ok) return;
								                  pitchEl.innerHTML = '';
								                  if (renderFromItems(boardItems)) return;
								                  if (renderFromItems(drillItems)) return;
								                  renderNoBoard();
								                });
								                return;
								              }

								              if (renderFromItems(boardItems)) return;
								              if (renderFromItems(drillItems)) return;
								              renderNoBoard();
								            };
						            const templates = buildTemplatesForProgram('smart');
						            const suggestions = Array.isArray(templates.smart_suggestions) ? templates.smart_suggestions : [];
						            if (!suggestions.length) {
						              smartSuggestionsBox.innerHTML = '<div class="meta" style="opacity:0.85;">No hay sugerencias todavía. Pulsa “Sugerir tareas”.</div>';
					              return;
						            }
							            const rows = suggestions.map((item, index) => {
							              const tpl = item?.tpl || {};
							              const title = String(tpl.title || '').trim() || `Sugerencia ${index + 1}`;
							              const minutes = String(tpl.minutes || '').trim();
							              const players = String(tpl.player_count || '').trim();
							              const block = String(tpl.block || '').trim();
							              const meta = [minutes ? `${minutes}’` : '', players || '', block || ''].filter(Boolean).join(' · ');
							              const sourceName = String(tpl.source_name || '').trim();
							              const sourceUrl = String(tpl.source_url || '').trim();
							              const sourceHtml = sourceUrl
							                ? `<a class="meta" style="opacity:0.9;" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Fuente: ${escapeHtml(sourceName || 'Referencia')}</a>`
							                : (sourceName ? `<span class="meta" style="opacity:0.9;">Fuente: ${escapeHtml(sourceName)}</span>` : '');
							              const objective = clipText(stripTags(tpl.objective || ''), 280);
							              const descriptionHtml = safeTplHtml(tpl.description_html || '');
							              const rulesHtml = safeTplHtml(tpl.rules_html || '');
							              const coachingHtml = safeTplHtml(tpl.coaching_html || '');
							              const progressionHtml = safeTplHtml(tpl.progression_html || '');
							              const regressionHtml = safeTplHtml(tpl.regression_html || '');
							              const successHtml = safeTplHtml(tpl.success_criteria_html || '');
							              const dims = String(tpl.dimensions || '').trim();
							              const mats = String(tpl.materials || '').trim();
							              const space = String(tpl.space || '').trim();
							              const durationLabel = minutes ? `${escapeHtml(minutes)} min` : '-';
							              const spaceLabel = escapeHtml(dims || space || '-');
							              const blockLabel = escapeHtml(selectLabelFor('draw_task_block', tpl.block) || '-');
							              const playersLabel = escapeHtml(players || '-');
							              const strategyLabel = escapeHtml(selectLabelFor('draw_task_strategy', tpl.strategy) || '-');
							              const dynamicsLabel = escapeHtml(selectLabelFor('draw_task_dynamics', tpl.dynamics) || '-');
							              const complexityLabel = escapeHtml(selectLabelFor('draw_task_complexity', tpl.complexity) || '-');
							              const structureLabel = escapeHtml(selectLabelFor('draw_task_structure', tpl.structure) || '-');
							              const coordinationLabel = escapeHtml(selectLabelFor('draw_task_coordination', tpl.coordination) || '-');
							              const coordSkillsLabel = escapeHtml(selectLabelFor('draw_task_coordination_skills', tpl.coordination_skills) || '-');
							              const tacticalIntentLabel = escapeHtml(selectLabelFor('draw_task_tactical_intent', tpl.tactical_intent) || '-');
							              return `
							                <div class="assistant-suggestion-card" data-smart-card="${index}">
							                  <div style="display:flex; align-items:baseline; justify-content:space-between; gap:0.75rem; flex-wrap:wrap;">
							                    <strong>${escapeHtml(`${index + 1}. ${title}`)}</strong>
							                    <span class="meta" style="opacity:0.85;">${escapeHtml(meta)}</span>
							                  </div>
							                  ${sourceHtml ? `<div style="display:flex; justify-content:flex-end;">${sourceHtml}</div>` : ''}
							                  <div class="assistant-suggestion-preview" title="Vista previa de la pizarra (orientativa)">
							                    <div class="assistant-suggestion-pitch" data-smart-pitch="${index}"></div>
							                  </div>
							                  <div class="assistant-suggestion-peek" data-smart-peek="${index}" hidden>
							                    <div class="assistant-suggestion-section-title">Detalles del ejercicio</div>
							                    <table class="assistant-suggestion-table" aria-label="Detalles del ejercicio">
							                      <tr>
							                        <td class="label">Título</td>
							                        <td class="value" colspan="3">${escapeHtml(title)}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Estrategia</td>
							                        <td class="value">${strategyLabel}</td>
							                        <td class="label">Objetivos</td>
							                        <td class="value">${escapeHtml(objective || '-')}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Espacio</td>
							                        <td class="value">${spaceLabel}</td>
							                        <td class="label">Tiempo</td>
							                        <td class="value">${durationLabel}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Jugadores</td>
							                        <td class="value">${playersLabel}</td>
							                        <td class="label">Bloque</td>
							                        <td class="value">${blockLabel}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Dinámica</td>
							                        <td class="value">${dynamicsLabel}</td>
							                        <td class="label">Complejidad</td>
							                        <td class="value">${complexityLabel}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Situación de Juego</td>
							                        <td class="value">${structureLabel}</td>
							                        <td class="label">Coordinación</td>
							                        <td class="value">${coordinationLabel}</td>
							                      </tr>
							                      <tr>
							                        <td class="label">Habilidades Coordinativas</td>
							                        <td class="value">${coordSkillsLabel}</td>
							                        <td class="label">Intención / Acción Táctica</td>
							                        <td class="value">${tacticalIntentLabel}</td>
							                      </tr>
							                    </table>
							                    <div class="assistant-suggestion-section-title">Consigna / Explicación</div>
							                    <div class="assistant-suggestion-copy">
							                      <div><strong>Descripción:</strong> ${descriptionHtml ? `<div>${descriptionHtml}</div>` : '<span>-</span>'}</div>
							                      ${coachingHtml ? `<div><strong>Consignas:</strong><div>${coachingHtml}</div></div>` : ''}
							                      ${rulesHtml ? `<div><strong>Normas de confrontación:</strong><div>${rulesHtml}</div></div>` : ''}
							                      ${progressionHtml ? `<div><strong>Progresión:</strong><div>${progressionHtml}</div></div>` : ''}
							                      ${regressionHtml ? `<div><strong>Regresión:</strong><div>${regressionHtml}</div></div>` : ''}
							                      ${successHtml ? `<div><strong>Criterio de éxito:</strong><div>${successHtml}</div></div>` : ''}
							                      ${mats ? `<div><strong>Material:</strong> <span>${escapeHtml(mats)}</span></div>` : ''}
							                    </div>
							                  </div>
							                  <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
							                    <button type="button" class="button" data-smart-peek-toggle="${index}">Vista previa</button>
							                    <button type="button" class="button" data-smart-apply="${index}">Aplicar</button>
							                    <button type="button" class="button" data-smart-queue="${index}">Añadir a cola</button>
							                  </div>
							                </div>
							              `;
							            }).join('');
					            smartSuggestionsBox.innerHTML = rows;
						            // Renderiza la vista previa de pizarra en cada sugerencia.
						            try {
						              const templates3 = buildTemplatesForProgram('smart');
						              const list = Array.isArray(templates3.smart_suggestions) ? templates3.smart_suggestions : [];
						              list.forEach((item, idx) => {
						                const pitchEl = smartSuggestionsBox.querySelector(`[data-smart-pitch="${idx}"]`);
						                renderPitchPreview(pitchEl, item || {}, idx);
						              });
						            } catch (e) { /* ignore */ }
					            // Toggle de vista previa (sin tocar la tarea actual).
					            Array.from(smartSuggestionsBox.querySelectorAll('[data-smart-peek-toggle]')).forEach((btn) => {
					              btn.addEventListener('click', () => {
					                const idx = Number(btn.getAttribute('data-smart-peek-toggle') || '0') || 0;
					                const card = btn.closest('.assistant-suggestion-card');
					                const pane = smartSuggestionsBox.querySelector(`[data-smart-peek="${idx}"]`);
					                const isOpen = !!(card && card.classList.contains('is-peek-open'));
					                if (card) card.classList.toggle('is-peek-open', !isOpen);
					                if (pane) pane.hidden = isOpen;
					                btn.textContent = isOpen ? 'Vista previa' : 'Ocultar';
					              });
					            });
					            Array.from(smartSuggestionsBox.querySelectorAll('[data-smart-apply]')).forEach((btn) => {
					              btn.addEventListener('click', () => {
					                const idx = Number(btn.getAttribute('data-smart-apply') || '0') || 0;
					                const templates2 = buildTemplatesForProgram('smart');
				                const list = Array.isArray(templates2.smart_suggestions) ? templates2.smart_suggestions : [];
				                const item = list[idx];
				                if (item?.tpl) applyTpl(item.tpl);
				              });
				            });
				            Array.from(smartSuggestionsBox.querySelectorAll('[data-smart-queue]')).forEach((btn) => {
				              btn.addEventListener('click', () => {
				                const idx = Number(btn.getAttribute('data-smart-queue') || '0') || 0;
				                const templates2 = buildTemplatesForProgram('smart');
				                const list = Array.isArray(templates2.smart_suggestions) ? templates2.smart_suggestions : [];
				                const item = list[idx];
				                if (item?.tpl) {
				                  pushQueueItem(item.tpl);
				                  setAssistantProgramUi();
				                }
				              });
				            });
				          };

				          smartSuggestBtn?.addEventListener('click', () => {
				            renderSmartSuggestions();
				          });

				          smartBtn?.addEventListener('click', () => {
				            renderSmartSuggestions();
				            applyTemplate('smart_generate');
				          });
					          smartSessionBtn?.addEventListener('click', () => {
					            const templates = buildTemplatesForProgram('smart');
					            const block = [templates.smart_block_1, templates.smart_block_2, templates.smart_block_3].filter(Boolean);
					            if (!block.length) return;
				            const wantsBoard = !!(applyBoardEl && applyBoardEl.checked);
				            const willClearBoard = !!(clearBoardEl && clearBoardEl.checked);
				            const confirmMsg = wantsBoard
				              ? (`Esto rellenará 1 tarea y dejará ${Math.max(0, block.length - 1)} en cola (${willClearBoard ? 'reemplazando' : 'añadiendo'} pizarra). ¿Continuar?`)
				              : `Esto rellenará 1 tarea y dejará ${Math.max(0, block.length - 1)} en cola. ¿Continuar?`;
				            const ok = window.confirm(confirmMsg);
				            if (!ok) return;
				            applyTpl(block[0], { confirm: false });
				            setQueueItems(block.slice(1));
				            updateQueueUi();
					            renderSmartSuggestions();
					          });

						          const inferBlueprintCategory = (goalKey) => {
						            const g = String(goalKey || '').trim();
						            if (g === 'physical_field' || g === 'physical_gym') return 'physical';
						            if (g === 'build_up' || g === 'progression') return 'build_up';
						            if (g === 'pressing' || g === 'counterpress' || g === 'defending') return 'pressing';
						            if (String(g).startsWith('transition')) return 'transition';
						            if (g === 'final_third' || g === 'duels') return 'finishing';
						            if (g === 'set_pieces') return 'abp';
						            if (g === 'coord' || g === 'warmup') return 'physical';
						            return 'other';
						          };

					          // Mapa (id -> {icon, label}) para reutilizar pictogramas en Asistente / previews.
					          let drillMetaCache = null;
					          const buildDrillMetaCache = () => {
					            const map = new Map();
					            if (!drillsPicker) return map;
					            try {
					              Array.from(drillsPicker.querySelectorAll('label.chip-toggle')).forEach((label) => {
					                const cb = label.querySelector('input[type="checkbox"][data-drill-id]');
					                const img = label.querySelector('img.drill-icon');
					                const id = String(cb?.getAttribute('data-drill-id') || '').trim();
					                if (!id) return;
					                const icon = String(img?.src || '').trim();
					                const dLabel = String(label.getAttribute('data-drill-label') || label.title || '').trim();
					                map.set(id, { icon, label: dLabel });
					              });
					            } catch (e) { /* ignore */ }
					            return map;
					          };
					          const getDrillMeta = (id) => {
					            const key = String(id || '').trim();
					            if (!key) return null;
					            if (!drillMetaCache) drillMetaCache = buildDrillMetaCache();
					            return drillMetaCache.get(key) || null;
					          };
					          const buildBoardItemsFromDrills = (ids, opts = {}) => {
					            const list = Array.isArray(ids) ? ids.map((v) => String(v || '').trim()).filter(Boolean) : [];
					            if (!list.length) return [];
					            const maxIcons = Number.isFinite(Number(opts.maxIcons)) ? Number(opts.maxIcons) : 12;
					            const y = Number.isFinite(Number(opts.y)) ? Number(opts.y) : 0.18;
					            const startX = Number.isFinite(Number(opts.startX)) ? Number(opts.startX) : 0.10;
					            const maxX = Number.isFinite(Number(opts.maxX)) ? Number(opts.maxX) : 0.88;
					            const desiredSize = Number.isFinite(Number(opts.desiredSize)) ? Number(opts.desiredSize) : 58;
					            const usable = [];
					            list.slice(0, maxIcons).forEach((drillId) => {
					              const meta = getDrillMeta(drillId);
					              if (!meta?.icon) return;
					              usable.push({ id: drillId, icon: meta.icon, label: meta.label || drillId });
					            });
					            if (!usable.length) return [];
					            const step = usable.length > 1 ? Math.min(0.10, (maxX - startX) / Math.max(1, usable.length - 1)) : 0;
					            return usable.map((it, index) => ({
					              x: startX + (step * index),
					              y,
					              angle: 0,
					              payload: {
					                kind: `image_url:${it.icon}`,
					                title: it.label,
					                desiredSize,
					              },
					            }));
					          };

					          const buildBlueprintPayloadFromForm = () => {
					            const getVal = (name) => {
					              const f = getField(name);
					              if (!f || f instanceof RadioNodeList) return '';
					              return String(f.value || '').trim();
					            };
					            const getHtml = (name) => {
					              const f = getField(name);
					              if (!f || f instanceof RadioNodeList) return '';
					              return String(f.value || '').trim();
					            };
					            let canvasState = null;
					            try {
					              const raw = getVal('draw_canvas_state');
					              canvasState = raw ? JSON.parse(raw) : null;
					            } catch (e) {
					              canvasState = null;
					            }
					            const tpl = {
					              title: getVal('draw_task_title'),
					              objective: getVal('draw_task_objective'),
					              block: getVal('draw_task_block'),
					              minutes: toInt(getVal('draw_task_minutes'), 15),
					              player_count: getVal('draw_task_player_count') || getVal('draw_task_players_distribution') || '',
					              dimensions: getVal('draw_task_dimensions'),
					              materials: getVal('draw_task_materials'),
					              space: getVal('draw_task_space'),
					              training_type: getVal('draw_task_training_type'),
					              age_group: getVal('draw_task_age_group'),
					              description_html: getHtml('draw_task_description_html'),
					              coaching_html: getHtml('draw_task_coaching_points_html'),
					              rules_html: getHtml('draw_task_confrontation_rules_html'),
					              progression_html: getHtml('draw_task_progression_html'),
					              regression_html: getHtml('draw_task_regression_html'),
					              success_criteria_html: getHtml('draw_task_success_criteria_html'),
					              canvas_state: canvasState,
					              canvas_width: toInt(getVal('draw_canvas_width'), 1280),
					              canvas_height: toInt(getVal('draw_canvas_height'), 720),
					              source_name: 'Plantilla del equipo',
					            };
					            const goalKey = String(document.getElementById('task-assistant-goal')?.value || '').trim() || 'other';
					            const subphaseKey = String(document.getElementById('task-assistant-smart-subphase')?.value || 'auto').trim() || 'auto';
					            const approachKey = String(document.getElementById('task-assistant-smart-approach')?.value || 'auto').trim() || 'auto';
					            const principleKey = String(document.getElementById('task-assistant-smart-principle')?.value || 'auto').trim() || 'auto';
					            const meta = {
					              v: 1,
					              created_at: new Date().toISOString(),
					              scope_key: String(form.dataset.scopeKey || '').trim() || 'coach',
					              goal: goalKey,
					              subphase: subphaseKey,
					              approach: approachKey,
					              principle: principleKey,
					            };
					            return { tpl, meta };
					          };

						          blueprintSaveBtn?.addEventListener('click', async () => {
					            if (!blueprintsSaveUrl) {
					              window.alert('No se encontró el endpoint para guardar plantillas.');
					              return;
					            }
					            const rawName = String(blueprintNameEl?.value || '').trim();
					            const fallbackName = String(getField('draw_task_title')?.value || '').trim();
					            const name = (rawName || fallbackName).slice(0, 160);
					            if (!name) {
					              window.alert('Pon un nombre a la plantilla (o escribe un título de tarea).');
					              return;
					            }
					            const payload = buildBlueprintPayloadFromForm();
					            const category = inferBlueprintCategory(payload?.meta?.goal || '');
					            try {
					              const res = await fetch(blueprintsSaveUrl, {
					                method: 'POST',
					                credentials: 'same-origin',
					                headers: {
					                  'Content-Type': 'application/json',
					                  ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
					                },
					                body: JSON.stringify({
					                  name,
					                  category,
					                  description: '',
					                  payload,
					                }),
					              });
					              const data = res.ok ? await res.json() : null;
					              if (!res.ok || !data?.ok) {
					                window.alert(String(data?.error || 'No se pudo guardar la plantilla.'));
					                return;
					              }
					              try {
					                blueprintNameEl.value = name;
					              } catch (e) {}
					              // Recarga y refresca sugerencias para que aparezca como candidata.
					              try { await reloadAssistantBlueprints(); } catch (e) {}
					              try { renderSmartSuggestions(); } catch (e) {}
					              window.alert('Plantilla guardada.');
					            } catch (err) {
					              window.alert('No se pudo guardar la plantilla.');
					            }
						          });

						          knowledgeUploadBtn?.addEventListener('click', async () => {
						            if (!knowledgeUploadUrl) {
						              window.alert('No se encontró el endpoint para subir documentos.');
						              return;
						            }
						            const files = Array.from(knowledgeFilesEl?.files || []);
						            if (!files.length) {
						              window.alert('Selecciona uno o varios documentos.');
						              return;
						            }
						            const fd = new FormData();
						            try {
						              const scopeSystem = document.getElementById('task-assistant-knowledge-scope-system');
						              if (scopeSystem && scopeSystem.checked) fd.append('scope', 'system');
						            } catch (e) {}
						            files.slice(0, 12).forEach((file) => {
						              try { fd.append('documents', file, file.name || 'documento.pdf'); } catch (e) {}
						            });
						            try {
						              const res = await fetch(knowledgeUploadUrl, {
						                method: 'POST',
						                credentials: 'same-origin',
						                headers: {
						                  ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
						                },
						                body: fd,
						              });
						              const data = res.ok ? await res.json() : null;
						              if (!res.ok || !data?.ok) {
						                window.alert(String(data?.error || 'No se pudieron subir los documentos.'));
						                return;
						              }
						              try { if (knowledgeFilesEl) knowledgeFilesEl.value = ''; } catch (e) {}
						              try { await reloadAssistantBlueprints(); } catch (e) {}
						              try { renderSmartSuggestions(); } catch (e) {}
						              const created = Number(data?.blueprints?.created || 0) || 0;
						              const updated = Number(data?.blueprints?.updated || 0) || 0;
						              const msg = `Subidos: ${Number(data?.saved || 0) || 0}. Plantillas creadas/actualizadas: ${created}/${updated}.`;
						              window.alert(msg);
						            } catch (err) {
						              window.alert('No se pudieron subir los documentos.');
						            }
						          });

						          // Auto-aplicar desde cola cuando se abre /nueva con ?assistant_next=1
						          const bootFromQueue = () => {
				            try {
				              const url = new URL(window.location.href);
				              if (url.searchParams.get('assistant_next') !== '1') return;
				              const q = readQueue();
				              const next = q.items.shift();
				              if (!next) {
				                updateQueueUi();
				                return;
				              }
				              writeQueue(q);
				              applyTpl(next, { confirm: false });
				              updateQueueUi();
				              try {
				                url.searchParams.delete('assistant_next');
				                window.history.replaceState({}, '', url.toString());
				              } catch (e) { /* ignore */ }
				            } catch (e) { /* ignore */ }
				          };

				          updateQueueUi();
				          bootFromQueue();
				        };

            // Rendimiento (iPad/Safari): diferimos la inicialización pesada para que la página
            // pinte primero y el scroll/inputs respondan desde el inicio.
            //
            // Nota: en Safari/WebKit algunos bloques con `const scheduleIdle` han provocado
            // `ReferenceError: Can't find variable: scheduleIdle` por scoping/concatenación de scripts.
            // Lo hacemos ultra-defensivo: definimos un helper global (window) y lo usamos por referencia.
            const __webstatsScheduleIdle = (fn, timeoutMs = 1400) => {
              try {
                if (typeof window.requestIdleCallback === 'function') {
                  return window.requestIdleCallback(fn, { timeout: timeoutMs });
                }
              } catch (e) { /* ignore */ }
              return window.setTimeout(fn, 120);
            };
            try {
              if (typeof window.__webstatsScheduleIdle !== 'function') window.__webstatsScheduleIdle = __webstatsScheduleIdle;
            } catch (e) { /* ignore */ }

            try {

			          try {
			            const statusEl = document.getElementById('task-builder-status');
			            if (statusEl && !String(statusEl.textContent || '').trim()) {
			              statusEl.textContent = 'Cargando editor…';
			            }
		          } catch (e) { /* ignore */ }

				          (window.__webstatsScheduleIdle || __webstatsScheduleIdle)(() => {
				            // Ultra-robusto: en HTML grande + Safari, el timeout puede disparar antes de que los
				            // scripts `defer` (fabric + sessions_tactical_pad) hayan ejecutado.
				            // Reintentamos unas cuantas veces hasta que exista `window.initSessionsTacticalPad`.
				            const boot = (attempt = 0) => {
				              try {
				                if (typeof window.initSessionsTacticalPad === 'function') {
				                  window.initSessionsTacticalPad();
				                  try {
				                    const statusEl = document.getElementById('task-builder-status');
				                    if (statusEl && String(statusEl.textContent || '').trim() === 'Cargando editor…') statusEl.textContent = '';
				                  } catch (e) { /* ignore */ }
				                  return;
				                }
				              } catch (e) { /* ignore */ }
				              if (attempt >= 40) return; // ~4s max
				              try { window.setTimeout(() => boot(attempt + 1), 100); } catch (e) { /* ignore */ }
				            };
				            boot(0);
				          }, 1800);
			            } catch (e) {
		              try {
		                const statusEl = document.getElementById('task-builder-status');
	                if (statusEl) statusEl.textContent = 'Error al inicializar la pizarra. Se activó modo seguro.';
	              } catch (err) { /* ignore */ }
	              try { window.alert('Error al inicializar la pizarra. Envía una captura del mensaje rojo superior para diagnosticar.'); } catch (err) { /* ignore */ }
	            }
		            // El recomendador/asistente es pesado: inicializa en idle para no bloquear la pizarra.
		            try {
		              (window.__webstatsScheduleIdle || __webstatsScheduleIdle)(() => { try { initTaskAssistant(); } catch (e) { /* ignore */ } }, 2400);
		            } catch (e) { /* ignore */ }

            // Fallback UX (modo táctica): si el JS principal tarda en cargar o falla,
            // al pulsar “Simulador” al menos mostramos el panel del simulador.
            try {
              const isTacticsModeFallback = !!cfg.tacticsMode;
              if (isTacticsModeFallback) {
                const statusEl = document.getElementById('task-builder-status');
                const simPopoverEl = document.getElementById('task-sim-popover');
                const openSimFallback = () => {
                  try { if (simPopoverEl) simPopoverEl.hidden = false; } catch (e) { /* ignore */ }
                  try { if (statusEl) statusEl.textContent = 'Simulador: panel abierto.'; } catch (e) { /* ignore */ }
                };
                ['task-playbook-open-sim', 'task-playbook-open-3d', 'task-playbook-open-video', 'task-playbook-export-pack']
                  .forEach((id) => {
                    const btn = document.getElementById(id);
                    if (!btn) return;
                    btn.addEventListener('click', openSimFallback);
                  });
              }
            } catch (e) { /* ignore */ }
			      });
