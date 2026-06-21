/* Extracted from templates/football/sessions_planner.html to reduce HTML payload. */
(function () {
  const boot = (window.sessionsPlannerBoot || {});
		      (() => {
		        const cards = document.querySelectorAll('.task.task-clickable[data-detail-url]');
		        const isInteractiveTarget = (node) =>
		          !!node.closest('a, button, input, select, textarea, form, summary, details, label');
		        const buildPdfViewerUrl = (pdfUrl, title) => {
		          const params = new URLSearchParams();
		          let u = String(pdfUrl || '').trim() || '/';
		          try {
		            const target = new URL(u, window.location.href);
		            u = `${target.pathname || '/'}${target.search || ''}${target.hash || ''}`;
		          } catch (e) {
		            // ignore
		          }
		          const back = `${window.location.pathname || '/'}${window.location.search || ''}${window.location.hash || ''}`;
		          params.set('u', u);
		          params.set('back', back);
		          params.set('title', String(title || 'PDF').trim().slice(0, 140) || 'PDF');
		          return `/pdf/viewer/?${params.toString()}`;
		        };
		        const openCard = (card, detailUrl) => {
		          if (!detailUrl) return;
		          if (card && card.hasAttribute && card.hasAttribute('data-pdf-viewer')) {
		            const title = (card.getAttribute('data-pdf-title') || '').trim() || 'PDF';
		            window.location.href = buildPdfViewerUrl(detailUrl, title);
		            return;
		          }
		          window.location.href = detailUrl;
		        };
		        if (cards.length) {
		          cards.forEach((card) => {
		            const detailUrl = card.getAttribute('data-detail-url');
		            if (!detailUrl) return;
		            card.addEventListener('click', (event) => {
		              if (isInteractiveTarget(event.target)) return;
		              openCard(card, detailUrl);
		            });
		            card.addEventListener('keydown', (event) => {
		              if (event.key !== 'Enter' && event.key !== ' ') return;
		              event.preventDefault();
		              openCard(card, detailUrl);
		            });
		          });
		        }
		      })();

	        (() => {
	          const dialog = document.getElementById('task-preview-dialog');
	          if (!dialog) return;
	          const titleEl = document.getElementById('task-preview-title');
	          const metaEl = document.getElementById('task-preview-meta');
	          const imgEl = document.getElementById('task-preview-img');
	          const summaryEl = document.getElementById('task-preview-summary');
	          const openEl = document.getElementById('task-preview-open');

	          const isInteractiveTarget = (node) =>
	            !!node.closest('a, button, input, select, textarea, form, summary, details, label');

	          const openPreview = ({ title, meta, summary, imgUrl, openUrl, relatedUrl }) => {
	            if (titleEl) titleEl.textContent = title || 'Vista previa';
	            if (metaEl) metaEl.textContent = meta || '';
	            if (summaryEl) summaryEl.textContent = summary || '';
	            if (openEl) openEl.setAttribute('href', openUrl || '#');
	            if (imgEl) {
	              imgEl.src = imgUrl || '';
	              imgEl.style.display = imgUrl ? 'block' : 'none';
	            }

	            if (typeof dialog.showModal === 'function') dialog.showModal();
	            else dialog.setAttribute('open', 'open');

	            const relatedWrap = document.getElementById('task-preview-related');
	            const relatedGrid = document.getElementById('task-preview-related-grid');
	            if (relatedWrap) relatedWrap.style.display = 'none';
	            if (relatedGrid) relatedGrid.innerHTML = '';
	            if (relatedUrl) {
	              fetch(relatedUrl, { credentials: 'same-origin' })
	                .then((r) => r.json())
	                .then((data) => {
	                  const items = (data && data.items) || [];
	                  if (!Array.isArray(items) || !items.length) return;
	                  if (!relatedWrap || !relatedGrid) return;
	                  items.slice(0, 6).forEach((item) => {
	                    const card = document.createElement('a');
	                    card.href = item.open_url || '#';
	                    card.style.textDecoration = 'none';
	                    card.style.color = 'inherit';
	                    card.style.border = '1px solid rgba(148,163,184,0.18)';
	                    card.style.borderRadius = '12px';
	                    card.style.padding = '0.55rem';
	                    card.style.background = 'rgba(255,255,255,0.04)';
	                    card.innerHTML = `
	                      <div style="font-weight:900; letter-spacing:0.06em; text-transform:uppercase; font-size:0.78rem; margin-bottom:0.35rem;">
	                        ${String(item.title || '').slice(0, 64)}
	                      </div>
	                      ${
	                        item.img_url
	                          ? `<img src="${item.img_url}" alt="" style="width:100%; aspect-ratio:16/9; border-radius:10px; border:1px solid rgba(255,255,255,0.12); object-fit:cover; background:rgba(0,0,0,0.12);" loading="lazy" />`
	                          : `<div style="width:100%; aspect-ratio:16/9; border-radius:10px; border:1px dashed rgba(255,255,255,0.16); display:flex; align-items:center; justify-content:center; opacity:0.75;">Sin gráfico</div>`
	                      }
	                      <div class="meta" style="margin-top:0.4rem; font-size:0.82rem; opacity:0.85;">
	                        ${String(item.summary || '').slice(0, 140)}
	                      </div>
	                    `;
	                    relatedGrid.appendChild(card);
	                  });
	                  relatedWrap.style.display = 'block';
	                })
	                .catch(() => {});
	            }
	          };

	          const closeIfBackdrop = (event) => {
	            const rect = dialog.getBoundingClientRect();
	            const inside =
	              event.clientX >= rect.left &&
              event.clientX <= rect.right &&
              event.clientY >= rect.top &&
              event.clientY <= rect.bottom;
            if (!inside) dialog.close();
          };
	          dialog.addEventListener('click', closeIfBackdrop);

	          document.addEventListener('click', (event) => {
	            const btn = event.target.closest('.task-preview-btn');
	            if (!btn) return;
	            event.preventDefault();
	            event.stopPropagation();

	            openPreview({
	              title: btn.getAttribute('data-title') || '',
	              meta: btn.getAttribute('data-meta') || '',
	              summary: btn.getAttribute('data-summary') || '',
	              imgUrl: btn.getAttribute('data-img-url') || '',
	              openUrl: btn.getAttribute('data-open-url') || '#',
	              relatedUrl: btn.getAttribute('data-related-url') || '',
	            });
	          });

	        })();

        (() => {
          const getCookie = (name) => {
            const cookie = (document.cookie || '')
              .split(';')
              .map((v) => v.trim())
              .find((v) => v.startsWith(`${name}=`));
            return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
          };
          const csrftoken = getCookie('csrftoken') || '';
          const buttons = document.querySelectorAll('.bookmark-btn[data-task-id]');
          if (!buttons.length) return;
          buttons.forEach((btn) => {
            btn.addEventListener('click', async (event) => {
              event.preventDefault();
              event.stopPropagation();
              const taskId = btn.getAttribute('data-task-id');
              if (!taskId) return;
              btn.disabled = true;
              try {
                const response = await fetch(`/coach/sesiones/tarea/${taskId}/bookmark/toggle/`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                  },
                  credentials: 'same-origin',
                  body: JSON.stringify({}),
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(data.error || 'No se pudo actualizar favorita.');
                const bookmarked = !!data.bookmarked;
                btn.textContent = bookmarked ? '★' : '☆';
                btn.setAttribute('aria-pressed', bookmarked ? 'true' : 'false');
                btn.title = bookmarked ? 'Quitar de favoritas' : 'Marcar como favorita';
              } catch (e) {
                alert(e.message || 'No se pudo actualizar favorita.');
              } finally {
                btn.disabled = false;
              }
            });
          });
        })();

        (() => {
          const saveBtn = document.getElementById('library-save-preset');
          const container = document.getElementById('library-presets');
          if (!saveBtn || !container) return;
          const teamId = String((boot.primaryTeamId || 0));
          const storageKey = `webstats:library:presets:${teamId}:v1`;

          const readPresets = () => {
            try {
              const raw = window.localStorage.getItem(storageKey);
              const parsed = raw ? JSON.parse(raw) : [];
              return Array.isArray(parsed) ? parsed : [];
            } catch (e) {
              return [];
            }
          };
          const writePresets = (presets) => {
            try {
              window.localStorage.setItem(storageKey, JSON.stringify(presets || []));
            } catch (e) {}
          };
          const renderPresets = () => {
            const presets = readPresets();
            container.innerHTML = '';
            if (!presets.length) return;
            presets.slice(0, 12).forEach((p) => {
              const wrap = document.createElement('span');
              wrap.style.display = 'inline-flex';
              wrap.style.gap = '0.35rem';
              const link = document.createElement('a');
              link.className = 'badge';
              link.href = p.href || '#';
              link.textContent = p.name || 'Preset';
              const del = document.createElement('button');
              del.type = 'button';
              del.className = 'badge';
              del.textContent = '×';
              del.title = 'Eliminar preset';
              del.addEventListener('click', () => {
                const next = readPresets().filter((x) => x.id !== p.id);
                writePresets(next);
                renderPresets();
              });
              wrap.appendChild(link);
              wrap.appendChild(del);
              container.appendChild(wrap);
            });
          };
          renderPresets();

          saveBtn.addEventListener('click', () => {
            const name = window.prompt('Nombre del preset (ej: “Prebenjamín · Pressing”):');
            if (!name) return;
            const href = `${window.location.pathname}${window.location.search}`;
            const presets = readPresets();
            presets.unshift({ id: `${Date.now()}-${Math.random().toString(16).slice(2)}`, name: name.slice(0, 42), href });
            writePresets(presets.slice(0, 30));
            renderPresets();
          });
        })();

        (() => {
          const chips = document.querySelectorAll('.facet-chip[data-facet][data-value]');
          if (!chips.length) return;
          const toggleParam = (params, key, value) => {
            const current = params.getAll(key);
            if (current.includes(value)) {
              const next = current.filter((v) => v !== value);
              params.delete(key);
              next.forEach((v) => params.append(key, v));
            } else {
              params.append(key, value);
            }
          };
          chips.forEach((chip) => {
            chip.addEventListener('click', () => {
              const facet = chip.getAttribute('data-facet');
              const value = chip.getAttribute('data-value');
              if (!facet || !value) return;
              const params = new URLSearchParams(window.location.search || '');
              params.set('tab', 'library');
              // Al usar chips, evitamos que las vistas legacy "por carpeta" interfieran.
              params.set('library_view', 'overview');
              params.delete('library_key');
              toggleParam(params, facet, value);
              window.location.search = params.toString();
            });
          });
        })();
	
		      (() => {
		        const form = document.getElementById('session-texts-form');
		        if (!form) return;
	        let canStore = true;
	        try {
	          const testKey = '__ls_test__';
	          window.localStorage.setItem(testKey, '1');
	          window.localStorage.removeItem(testKey);
	        } catch (e) {
	          canStore = false;
	        }
	        if (!canStore) return;
	
	        const teamId = String(form.dataset.teamId || '').trim() || 'team';
	        const sessionId = String(form.dataset.sessionId || '').trim() || 'session';
	        const scopeKey = String(form.dataset.scopeKey || '').trim() || 'coach';
	        const storageKey = `webstats:sessions:draft:${teamId}:${sessionId}:${scopeKey}:texts:v1`;
	
	        const fieldNames = ['section_warmup', 'section_activation', 'section_main', 'section_cooldown'];
	        const fields = fieldNames
	          .map((name) => form.querySelector(`[name="${name}"]`))
	          .filter(Boolean);
	        const banner = document.getElementById('session-texts-draft-banner');
	        const restoreBtn = document.getElementById('session-texts-draft-restore');
	        const discardBtn = document.getElementById('session-texts-draft-discard');
	        const statusEl = document.getElementById('session-texts-draft-status');
	        const csrfTokenEl = form.querySelector('input[name="csrfmiddlewaretoken"]');
	        const csrfToken = csrfTokenEl ? String(csrfTokenEl.value || '') : '';
	        const postUrl = form.getAttribute('action') || window.location.href;
	
	        const readValues = () => {
	          const out = {};
	          fieldNames.forEach((name) => {
	            const el = form.querySelector(`[name="${name}"]`);
	            out[name] = el ? String(el.value || '') : '';
	          });
	          return out;
	        };
	        const writeValues = (values) => {
	          if (!values || typeof values !== 'object') return;
	          fieldNames.forEach((name) => {
	            const el = form.querySelector(`[name="${name}"]`);
	            if (!el) return;
	            if (values[name] === undefined) return;
	            el.value = String(values[name] || '');
	          });
	        };
	        const loadDraft = () => {
	          try {
	            const raw = window.localStorage.getItem(storageKey);
	            if (!raw) return null;
	            const parsed = JSON.parse(raw);
	            if (!parsed || typeof parsed !== 'object') return null;
	            if (!parsed.values || typeof parsed.values !== 'object') return null;
	            return parsed;
	          } catch (e) {
	            return null;
	          }
	        };
	        const saveDraft = (values) => {
	          try {
	            window.localStorage.setItem(storageKey, JSON.stringify({ ts: Date.now(), values: values || readValues() }));
	            if (statusEl) statusEl.textContent = 'Borrador guardado.';
	          } catch (e) {
	            // ignore
	          }
	        };
		        const saveServer = async () => {
	          try {
	            const payload = new FormData(form);
	            payload.set('ajax', '1');
	            if (csrfToken && !payload.get('csrfmiddlewaretoken')) {
	              payload.set('csrfmiddlewaretoken', csrfToken);
	            }
	            const resp = await fetch(postUrl, {
	              method: 'POST',
	              body: payload,
	              credentials: 'same-origin',
	              headers: { 'X-Requested-With': 'XMLHttpRequest' },
	            });
	            const data = await resp.json().catch(() => null);
	            if (!resp.ok || !data || data.ok !== true) {
	              const msg = (data && (data.error || data.message)) ? String(data.error || data.message) : 'No se pudo guardar en servidor.';
	              if (statusEl) statusEl.textContent = msg;
	              return false;
	            }
	            if (statusEl) statusEl.textContent = 'Guardado en servidor.';
	            return true;
	          } catch (e) {
	            if (statusEl) statusEl.textContent = 'No se pudo guardar en servidor.';
	            return false;
	          }
		        };
		        try {
		          window.__WebStats = window.__WebStats || {};
		          window.__WebStats.saveSessionTexts = saveServer;
		        } catch (e) {}
	        const clearDraft = () => {
	          try {
	            window.localStorage.removeItem(storageKey);
	          } catch (e) {}
	        };
	        const debounce = (fn, ms) => {
	          let t = null;
	          return (...args) => {
	            window.clearTimeout(t);
	            t = window.setTimeout(() => fn(...args), ms);
	          };
	        };
	
	        const draft = loadDraft();
	        if (draft && banner && restoreBtn && discardBtn) {
	          const current = readValues();
	          const differs = fieldNames.some((name) => String(draft.values[name] || '') !== String(current[name] || ''));
	          if (differs) {
	            banner.hidden = false;
	            restoreBtn.addEventListener('click', () => {
	              writeValues(draft.values);
	              banner.hidden = true;
	              saveDraft(readValues());
	              scheduleServerSave();
	            });
	            discardBtn.addEventListener('click', () => {
	              clearDraft();
	              banner.hidden = true;
	              if (statusEl) statusEl.textContent = '';
	            });
	          }
	        }
	
	        const scheduleSave = debounce(() => saveDraft(readValues()), 450);
	        const scheduleServerSave = debounce(() => { void saveServer(); }, 650);
	        fields.forEach((el) => el.addEventListener('input', scheduleSave));
	        fields.forEach((el) => el.addEventListener('input', scheduleServerSave));
	
	        // Si la sesión ya tiene textos (renderizados desde servidor o restaurados localmente),
	        // intentamos persistirlos una vez en backend para que el PDF siempre los recoja,
	        // incluso si el usuario no vuelve a pulsar "Guardar textos".
	        try {
	          const hasAnyText = fields.some((el) => String(el.value || '').trim().length > 0);
	          if (hasAnyText) {
	            window.setTimeout(() => { void saveServer(); }, 900);
	          }
	        } catch (e) {}
			        form.addEventListener('submit', () => clearDraft());
		        window.addEventListener('beforeunload', () => {
		          try { saveDraft(readValues()); } catch (e) {}
		          try {
	            if (navigator.sendBeacon) {
	              const payload = new FormData(form);
	              payload.set('ajax', '1');
	              navigator.sendBeacon(postUrl, payload);
	            }
	          } catch (e) {}
			        });
			      })();

			      (() => {
			        const form = document.getElementById('session-attendance-form');
			        if (!form) return;
			        const list = document.getElementById('attendance-list');
			        const search = document.getElementById('attendance-search');
			        const btnAllPresent = document.getElementById('attendance-all-present');
			        const btnAllAbsent = document.getElementById('attendance-all-absent');
			        const btnClear = document.getElementById('attendance-clear');
			        const btnCopy = document.getElementById('attendance-copy-summary');
			        if (!list) return;
			        const rows = Array.from(list.querySelectorAll('.att-row'));
			        const normalize = (value) => String(value || '').trim().toLowerCase();
			        const applyFilter = () => {
			          const q = normalize(search ? search.value : '');
			          rows.forEach((row) => {
			            const name = normalize(row.getAttribute('data-player-name'));
			            const number = normalize(row.getAttribute('data-player-number'));
			            row.style.display = (!q || name.includes(q) || number.includes(q)) ? '' : 'none';
			          });
			        };
			        const setAll = (value) => {
			          rows.forEach((row) => {
			            if (row.style.display === 'none') return;
			            const sel = row.querySelector('select');
			            if (sel) sel.value = value;
			          });
			        };
			        if (search) search.addEventListener('input', applyFilter);
			        if (btnAllPresent) btnAllPresent.addEventListener('click', () => setAll('present'));
			        if (btnAllAbsent) btnAllAbsent.addEventListener('click', () => setAll('absent'));
			        if (btnClear) btnClear.addEventListener('click', () => setAll(''));
			        if (btnCopy) btnCopy.addEventListener('click', async () => {
			          const labels = { present: 'Presente', absent: 'Ausente', late: 'Llega tarde', injured: 'Lesionado', excused: 'Justificado' };
			          const grouped = { present: [], absent: [], late: [], injured: [], excused: [] };
			          const rowLabel = (row) => {
			            const name = String(row.getAttribute('data-player-name') || '').trim();
			            const number = String(row.getAttribute('data-player-number') || '').trim();
			            const prettyName = name ? name.replace(/\b\w/g, (c) => c.toUpperCase()) : 'Jugador';
			            return number ? `#${number} ${prettyName}` : prettyName;
			          };
			          rows.forEach((row) => {
			            const sel = row.querySelector('select');
			            const value = sel ? String(sel.value || '').trim() : '';
			            if (!value || !(value in grouped)) return;
			            grouped[value].push(rowLabel(row));
			          });
			          const sessionLabel = (() => {
			            try {
			              const sel = document.querySelector('#planner-active-session select[name="session_id"]');
			              const opt = sel && sel.selectedOptions ? sel.selectedOptions[0] : null;
			              return opt ? String(opt.textContent || '').trim() : '';
			            } catch (e) { return ''; }
			          })();
			          const lines = [];
			          if (sessionLabel) lines.push(`Asistencia · ${sessionLabel}`);
			          const order = ['present', 'absent', 'late', 'injured', 'excused'];
			          order.forEach((key) => {
			            const items = grouped[key] || [];
			            const head = `${labels[key]}: ${items.length}`;
			            lines.push(items.length ? `${head} (${items.join(', ')})` : head);
			          });
			          const text = lines.join('\n');
			          try {
			            if (navigator.clipboard && navigator.clipboard.writeText) {
			              await navigator.clipboard.writeText(text);
			            } else {
			              const ta = document.createElement('textarea');
			              ta.value = text;
			              ta.style.position = 'fixed';
			              ta.style.left = '-9999px';
			              document.body.appendChild(ta);
			              ta.focus();
			              ta.select();
			              document.execCommand('copy');
			              ta.remove();
			            }
			            btnCopy.textContent = 'Copiado';
			            window.setTimeout(() => { btnCopy.textContent = 'Copiar resumen'; }, 900);
			          } catch (e) {
			            window.alert('No se pudo copiar el resumen.');
			          }
			        });
			      })();

				      (() => {
				        const links = Array.from(document.querySelectorAll('a.session-pdf-link[data-session-pdf="1"]'));
				        if (!links.length) return;
				        const buildUrl = (href) => {
		          try {
		            const url = new URL(href, window.location.href);
		            url.searchParams.set('_ts', String(Date.now()));
		            return url.toString();
		          } catch (e) {
		            const sep = href.includes('?') ? '&' : '?';
		            return `${href}${sep}_ts=${Date.now()}`;
		          }
			        };
			        links.forEach((link) => {
			          link.addEventListener('click', async (event) => {
			            const href = link.getAttribute('href');
			            if (!href) return;
			            event.preventDefault();
			            const targetUrl = buildUrl(href);
			            const isNative = (() => {
			              try {
			                return !!(window.WebstatsPdf && window.WebstatsPdf.isNativeApp && window.WebstatsPdf.isNativeApp());
			              } catch (e) {
			                return false;
			              }
			            })();
			            const viewerUrl = (() => {
			              try {
			                const title = (link.getAttribute('data-pdf-title') || link.textContent || 'PDF').trim();
			                if (window.WebstatsPdf && typeof window.WebstatsPdf.buildViewerUrl === 'function') {
			                  return window.WebstatsPdf.buildViewerUrl(targetUrl, title);
			                }
			              } catch (e) {}
			              return '';
			            })();
			            // En navegador abrimos en nueva pestaña (para no sacar al usuario de la planificación).
			            // En app nativa evitamos `_blank` porque el webview no tiene botón atrás y se queda bloqueado.
			            const opened = (!isNative) ? window.open('about:blank', '_blank', 'noopener') : null;
			            const saver = (window.__WebStats && window.__WebStats.saveSessionTexts) ? window.__WebStats.saveSessionTexts : null;
			            if (typeof saver === 'function') {
			              try {
			                await saver();
			              } catch (e) {}
			            }
			            if (isNative) {
			              try {
			                window.location.href = viewerUrl || targetUrl;
			              } catch (e) {
			                window.location.href = targetUrl;
			              }
			              return;
			            }
			            try {
			              if (opened && !opened.closed) {
			                opened.location.href = targetUrl;
			              } else {
			                window.location.href = targetUrl;
		              }
		            } catch (e) {
		              window.location.href = targetUrl;
		            }
		          });
		        });
		      })();

		      // Guía de esta pantalla (Sesiones / Planificación).
		      (() => {
		        try {
		          const steps = [
		            {
		              anchor: '#planner-tabs',
		              title: '1) Pestañas',
		              body: 'Aquí alternas entre Sesiones, Microciclos y Biblioteca. “Crear tarea” abre el editor visual.',
		            },
		            {
		              anchor: '#planner-create-session',
		              title: '2) Crear sesión',
		              body: 'Define fecha, notas, número de jugadores y material. En “Metodología” usa “Añadir campo” para mostrar solo día MD, carga, momento o principio cuando lo necesites.',
		            },
		            {
		              anchor: '#planner-active-session',
		              title: '3) Cargar sesión + PDFs',
		              body: 'Selecciona la sesión activa. Desde aquí puedes generar el PDF (UEFA/Club).',
		            },
		            {
		              anchor: '#planner-blocks',
		              title: '4) Tareas por bloque',
		              body: 'La sesión se organiza en Calentamiento, Activación, Principal 1, Principal 2 y Vuelta a la calma.',
		            },
		            {
		              anchor: '#planner-blocks .editor-grid',
		              title: '5) Asignar o crear tareas',
		              body: 'En cada bloque puedes “Asignar” una tarea desde Biblioteca o “Crear tarea” para diseñarla desde cero.',
		            },
		            {
		              anchor: '#planner-blocks .task-list',
		              title: '6) Ordenar y editar',
		              body: 'Arrastra tareas entre bloques. Toca una tarea para editarla. Usa la papelera para quitarla de la sesión.',
		            },
		          ];
		          window.__WEBSTATS_PAGE_TOUR_ID = 'sessions_planner_v1';
		          window.__WEBSTATS_PAGE_TOUR_STEPS = steps;
		        } catch (e) { /* ignore */ }
		      })();

		      // Sesión en vivo: cronómetro por tramos (editable después).
		      (() => {
		        const panel = document.getElementById('planner-live-timeline');
		        if (!panel) return;
		        const sessionId = panel.getAttribute('data-session-id') || '';
		        if (!sessionId) return;

		        const getCookie = (name) => {
		          const cookie = (document.cookie || '')
		            .split(';')
		            .map((v) => v.trim())
		            .find((v) => v.startsWith(`${name}=`));
		          return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
		        };
		        const csrftoken = getCookie('csrftoken') || '';

		        const labels = {
		          activation: 'Activación',
		          physical: 'Físico / Preventivo',
		          main: 'Tarea principal',
		          cooldown: 'Vuelta a la calma',
		          pause: 'Pausa',
		          other: 'Otro',
		        };

		        const labelEl = document.getElementById('live-timer-label');
		        const clockEl = document.getElementById('live-timer-clock');
		        const segmentsWrap = document.getElementById('timeline-segments');

		        let runningStartIso = panel.getAttribute('data-running-start') || '';
		        let runningType = panel.getAttribute('data-running-type') || '';

		        const setRunning = (type, startedAtIso) => {
		          runningType = String(type || '');
		          runningStartIso = String(startedAtIso || '');
		          panel.setAttribute('data-running-type', runningType);
		          if (runningStartIso) panel.setAttribute('data-running-start', runningStartIso);
		          if (labelEl) labelEl.textContent = labels[runningType] || '—';
		        };

		        const updateClock = () => {
		          if (!clockEl) return;
		          if (!runningStartIso) {
		            clockEl.textContent = '00:00';
		            return;
		          }
		          const startMs = Date.parse(runningStartIso);
		          if (!startMs) {
		            clockEl.textContent = '00:00';
		            return;
		          }
		          const diff = Math.max(0, Date.now() - startMs);
		          const sec = Math.floor(diff / 1000);
		          const mm = String(Math.floor(sec / 60)).padStart(2, '0');
		          const ss = String(sec % 60).padStart(2, '0');
		          clockEl.textContent = `${mm}:${ss}`;
		        };

		        const renderTotals = (totals) => {
		          try {
		            const t = totals || {};
		            const setVal = (key, value) => {
		              const el = panel.querySelector(`[data-total-value=\"${key}\"]`);
		              if (el) el.textContent = String(Number(value || 0));
		            };
		            setVal('activation', t.activation);
		            setVal('physical', t.physical);
		            setVal('main', t.main);
		            setVal('cooldown', t.cooldown);
		            setVal('pause', t.pause);
		            setVal('total', t.total_minutes);
		          } catch (e) {}
		        };

		        const renderSegments = (segments) => {
		          if (!segmentsWrap) return;
		          const items = Array.isArray(segments) ? segments : [];
		          if (!items.length) {
		            segmentsWrap.innerHTML = `<p class=\"meta\" style=\"margin:0.35rem 0 0;\">Aún no hay tramos. Pulsa un botón para iniciar.</p>`;
		            return;
		          }
		          const rows = items
		            .map((seg) => {
		              const label = labels[seg.type] || seg.label || seg.type || 'Tramo';
		              const minutes = Number(seg.minutes || 0);
		              const isRunning = !seg.ended_at;
		              const timeLabel = seg.started_at
		                ? new Date(seg.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
		                : '';
		              const endLabel = seg.ended_at
		                ? new Date(seg.ended_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
		                : '';
		              const notes = String(seg.notes || '');
		              return `
		                <div class=\"att-row\" style=\"grid-template-columns: 1fr 110px 1fr; align-items:center;\">
		                  <div class=\"att-player\" style=\"min-width:0;\">
		                    <strong style=\"white-space:nowrap; overflow:hidden; text-overflow:ellipsis;\">
		                      ${label}
		                      ${isRunning ? '<span class=\"badge\" style=\"margin-left:0.35rem;\">En curso</span>' : ''}
		                    </strong>
		                    <small style=\"opacity:0.9;\">${timeLabel}${endLabel ? `–${endLabel}` : ''}</small>
		                  </div>
		                  <div><span class=\"badge\">${minutes}'</span></div>
		                  <div style=\"opacity:0.9; font-size:0.85rem;\">${notes}</div>
		                </div>
		              `;
		            })
		            .join('');
		          segmentsWrap.innerHTML = `<div class=\"attendance-list\" style=\"margin-top:0;\">${rows}</div>`;
		        };

		        const postTimeline = async (action, extra = {}) => {
		          const body = new URLSearchParams();
		          body.set('planner_action', action);
		          body.set('planner_tab', 'sessions');
		          body.set('ajax', '1');
		          body.set('timeline_session_id', sessionId);
		          Object.entries(extra || {}).forEach(([k, v]) => body.set(k, String(v)));
		          const response = await fetch(window.location.href, {
		            method: 'POST',
		            headers: {
		              'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
		              'X-Requested-With': 'XMLHttpRequest',
		              'X-CSRFToken': csrftoken,
		            },
		            credentials: 'same-origin',
		            body,
		          });
		          const data = await response.json().catch(() => ({}));
		          if (!response.ok || !data || !data.ok) {
		            throw new Error((data && (data.error || data.message)) || 'No se pudo actualizar el cronómetro.');
		          }
		          return data;
		        };

		        const startButtons = panel.querySelectorAll('.js-timeline-start[data-seg-type]');
		        startButtons.forEach((btn) => {
		          btn.addEventListener('click', async () => {
		            btn.disabled = true;
		            try {
		              const segType = btn.getAttribute('data-seg-type') || '';
		              const data = await postTimeline('timeline_start_segment', { segment_type: segType });
		              renderTotals(data.totals);
		              renderSegments(data.segments);
		              if (data.running && data.running.started_at) {
		                setRunning(data.running.type, data.running.started_at);
		              } else {
		                setRunning('', '');
		              }
		              updateClock();
		            } catch (e) {
		              alert(e.message || 'No se pudo iniciar el tramo.');
		              window.location.reload();
		            } finally {
		              btn.disabled = false;
		            }
		          });
		        });

		        const stopBtn = panel.querySelector('.js-timeline-stop');
		        if (stopBtn) {
		          stopBtn.addEventListener('click', async () => {
		            stopBtn.disabled = true;
		            try {
		              const data = await postTimeline('timeline_stop', {});
		              renderTotals(data.totals);
		              renderSegments(data.segments);
		              setRunning('', '');
		              updateClock();
		            } catch (e) {
		              alert(e.message || 'No se pudo detener el tramo.');
		              window.location.reload();
		            } finally {
		              stopBtn.disabled = false;
		            }
		          });
		        }

		        if (labelEl && runningType) labelEl.textContent = labels[runningType] || '—';
		        updateClock();
		        window.setInterval(updateClock, 1000);
		      })();

		      // Metodología: los campos son opcionales y se añaden bajo demanda.
		      (() => {
		        const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
		        const controlValue = (control) => {
		          if (!control) return '';
		          if (control.matches('select')) {
		            const selectedIndex = Number(control.selectedIndex || 0);
		            const first = control.options && control.options.length ? control.options[0] : null;
		            const firstHasValue = first && clean(first.value);
		            if (selectedIndex <= 0 && firstHasValue) return '';
		          }
		          if (control.type === 'checkbox' || control.type === 'radio') return control.checked ? '1' : '';
		          return clean(control.value);
		        };
		        const labelText = (label, control) => {
		          const direct = Array.from(label.childNodes || [])
		            .filter((node) => node.nodeType === Node.TEXT_NODE)
		            .map((node) => clean(node.textContent))
		            .filter(Boolean)
		            .join(' ');
		          return direct || clean(label.getAttribute('aria-label')) || clean(control?.name).replace(/^.*?_/, '').replace(/_/g, ' ') || 'Campo';
		        };
		        const initPicker = (box) => {
		          if (!box || box.dataset.methodologyReady === '1') return;
		          const grid = box.querySelector('[data-methodology-grid]');
		          if (!grid) return;
		          const labels = Array.from(grid.children || []).filter((el) => {
		            return el && el.matches && el.matches('label') && el.querySelector('input,select,textarea');
		          });
		          if (!labels.length) return;
		          box.dataset.methodologyReady = '1';
		          const controls = document.createElement('div');
		          controls.className = 'methodology-add-row';
		          controls.style.cssText = 'display:flex;gap:0.5rem;align-items:flex-end;flex-wrap:wrap;margin:0.65rem 0 0.2rem;';
		          const select = document.createElement('select');
		          select.setAttribute('aria-label', 'Campo metodológico a añadir');
		          select.style.cssText = 'max-width:260px;min-width:190px;';
		          const button = document.createElement('button');
		          button.type = 'button';
		          button.className = 'button secondary';
		          button.textContent = 'Añadir campo';
		          button.setAttribute('data-help', 'Muestra el campo metodológico seleccionado sin llenar la ficha con opciones que no necesitas.');
		          controls.append(select, button);
		          grid.parentNode.insertBefore(controls, grid);

		          const rows = labels.map((label, index) => {
		            const control = label.querySelector('input,select,textarea');
		            label.dataset.methodologyIndex = String(index);
		            return { index, label, control, text: labelText(label, control) };
		          });
		          const refreshOptions = () => {
		            const hiddenRows = rows.filter((row) => row.label.hidden);
		            select.innerHTML = '';
		            hiddenRows.forEach((row) => {
		              const option = document.createElement('option');
		              option.value = String(row.index);
		              option.textContent = row.text;
		              select.appendChild(option);
		            });
		            const hasHidden = hiddenRows.length > 0;
		            controls.hidden = !hasHidden;
		            select.disabled = !hasHidden;
		            button.disabled = !hasHidden;
		          };
		          let hasVisibleValue = false;
		          rows.forEach((row) => {
		            const filled = !!controlValue(row.control);
		            row.label.hidden = !filled;
		            if (filled) hasVisibleValue = true;
		          });
		          if (hasVisibleValue && box.matches('details')) box.open = true;
		          button.addEventListener('click', () => {
		            const row = rows.find((item) => String(item.index) === String(select.value));
		            if (!row) return;
		            row.label.hidden = false;
		            if (box.matches('details')) box.open = true;
		            refreshOptions();
		            try { row.control?.focus({ preventScroll: true }); } catch (e) {}
		          });
		          refreshOptions();
		        };
		        const boot = () => document.querySelectorAll('[data-methodology-picker]').forEach(initPicker);
		        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
		        else boot();
		      })();

})();
