(function () {
					        const btn = document.getElementById('tpad-diag-copy');
					        if (!btn) return;
				        const snapRect = (el) => {
				          try {
				            if (!el || !el.getBoundingClientRect) return null;
				            const r = el.getBoundingClientRect();
				            return { w: Math.round(r.width), h: Math.round(r.height), x: Math.round(r.x), y: Math.round(r.y) };
				          } catch (e) { return null; }
				        };
				        const listScripts = (needle) => {
				          try {
				            return Array.from(document.scripts || [])
				              .map((s) => String(s.src || ''))
				              .filter((src) => src && (!needle || src.includes(needle)));
				          } catch (e) { return []; }
				        };
						        const buildDiag = async () => {
						          const form = document.getElementById('task-builder-form');
						          const canvas = document.getElementById('create-task-canvas');
						          const stage = document.getElementById('task-pitch-stage');
						          const viewport = document.getElementById('task-pitch-viewport');
						          const statusEl = document.getElementById('task-builder-status');
						          const backdrop = document.getElementById('tpad-overlay-backdrop');
						          const lines = [];
					          // Asegura carga + init antes de capturar tamaños.
					          let ensureOk = null;
					          try {
					            if (typeof window.__webstatsEnsureEditorStack === 'function') {
					              ensureOk = await window.__webstatsEnsureEditorStack();
					            }
					          } catch (e) {
					            ensureOk = null;
					          }
					          lines.push(`url=${String(location.href || '').slice(0, 240)}`);
					          lines.push(`ua=${String(navigator.userAgent || '').slice(0, 240)}`);
						          lines.push(`tactics_mode=1`);
						          lines.push(`status=${String(statusEl && statusEl.textContent ? statusEl.textContent : '').trim()}`);
						          try { lines.push(`body.overlay_backdrop_open=${document.body.classList.contains('overlay-backdrop-open') ? '1' : '0'}`); } catch (e) {}
						          try { lines.push(`backdrop.hidden=${backdrop ? String(!!backdrop.hidden) : 'n/a'}`); } catch (e) {}
						          try { lines.push(`backdrop.pointerEvents=${backdrop ? String((window.getComputedStyle(backdrop) || {}).pointerEvents || '') : 'n/a'}`); } catch (e) {}
						          try {
						            const openDetails = ['task-builder-actions-menu', 'pitch-view-menu'].map((id) => {
						              const el = document.getElementById(id);
						              return { id, open: !!(el && el.tagName === 'DETAILS' && el.open) };
						            });
						            lines.push(`overlay.details=${JSON.stringify(openDetails)}`);
						          } catch (e) {}
						          try {
						            const floatIds = ['task-command-menu','task-pattern-popover','task-formation-popover','task-overlays-popover','task-layers-popover','task-scenarios-popover'];
						            const visibles = floatIds.map((id) => {
						              const el = document.getElementById(id);
						              if (!el) return { id, visible: false };
						              const style = window.getComputedStyle ? window.getComputedStyle(el) : null;
						              const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
						              const visible = !el.hidden && style && style.display !== 'none' && style.visibility !== 'hidden' && rect && rect.width > 1 && rect.height > 1;
						              return { id, visible: !!visible, hidden: !!el.hidden, display: style ? style.display : '', rect: rect ? { w: Math.round(rect.width), h: Math.round(rect.height) } : null };
						            });
						            lines.push(`overlay.float=${JSON.stringify(visibles)}`);
						          } catch (e) {}
						          lines.push(`fabric=${typeof window.fabric}`);
						          lines.push(`initSessionsTacticalPad=${typeof window.initSessionsTacticalPad}`);
					          lines.push(`last_error=${String(window.__webstatsTpadLastError || '').trim()}`);
					          try { lines.push(`tpad_ready=${String(form?.dataset?.webstatsTpadReady || '')}`); } catch (e) {}
					          try { lines.push(`tpad_init=${String(form?.dataset?.webstatsTpadInit || '')}`); } catch (e) {}
					          try { lines.push(`tpad_last_error_ls=${String(window.localStorage?.getItem('webstats:tpad:last_error') || '').slice(0, 220)}`); } catch (e) {}
					          lines.push(`ensureEditorStack=${ensureOk === null ? 'n/a' : (ensureOk ? 'ok' : 'fail')}`);
					          lines.push(`form.fabricSrc=${form ? String(form.dataset.fabricSrc || '') : ''}`);
					          lines.push(`form.tpadSrc=${form ? String(form.dataset.tpadSrc || '') : ''}`);
						          lines.push(`rect.viewport=${JSON.stringify(snapRect(viewport))}`);
						          lines.push(`rect.stage=${JSON.stringify(snapRect(stage))}`);
						          lines.push(`rect.canvas=${JSON.stringify(snapRect(canvas))}`);
						          try {
						            const layout = document.querySelector('.pitch-layout');
						            const main = document.querySelector('.pitch-main');
						            const side = document.querySelector('.pitch-side');
						            const panelBody = document.querySelector('.panel-body');
						            lines.push(`rect.layout=${JSON.stringify(snapRect(layout))}`);
						            lines.push(`rect.main=${JSON.stringify(snapRect(main))}`);
						            lines.push(`rect.side=${JSON.stringify(snapRect(side))}`);
						            lines.push(`rect.panelBody=${JSON.stringify(snapRect(panelBody))}`);
						            lines.push(`win=${(window.innerWidth || 0)}x${(window.innerHeight || 0)} dpr=${String(window.devicePixelRatio || 1)}`);
						          } catch (e) { /* ignore */ }
						          const svg = document.getElementById('task-pitch-surface');
						          try { lines.push(`rect.svg=${JSON.stringify(snapRect(svg))}`); } catch (e) {}
						          try { lines.push(`svg.viewBox=${svg ? String(svg.getAttribute('viewBox') || '') : ''}`); } catch (e) {}
					          try { lines.push(`svg.children=${svg ? String(svg.children?.length || 0) : '0'}`); } catch (e) {}
					          try { lines.push(`canvas.attr=${canvas ? `${canvas.getAttribute('width') || ''}x${canvas.getAttribute('height') || ''}` : ''}`); } catch (e) {}
					          try { lines.push(`canvas.prop=${canvas ? `${canvas.width}x${canvas.height}` : ''}`); } catch (e) {}
					          lines.push(`scripts.fabric=${JSON.stringify(listScripts('fabric'))}`);
					          lines.push(`scripts.tpad=${JSON.stringify(listScripts('sessions_tactical_pad'))}`);
					          // Vuelve a capturar tamaños tras init (clave para saber si Fabric llegó a setDimensions).
					          try { lines.push(`rect.canvas.after=${JSON.stringify(snapRect(canvas))}`); } catch (e) {}
					          try { lines.push(`canvas.attr.after=${canvas ? `${canvas.getAttribute('width') || ''}x${canvas.getAttribute('height') || ''}` : ''}`); } catch (e) {}
					          try { lines.push(`canvas.prop.after=${canvas ? `${canvas.width}x${canvas.height}` : ''}`); } catch (e) {}
					          return lines.join('\n');
					        };
				        const copyText = async (txt) => {
				          try {
				            if (navigator.clipboard && navigator.clipboard.writeText) {
				              await navigator.clipboard.writeText(txt);
				              return true;
				            }
				          } catch (e) {}
				          try {
				            const ta = document.createElement('textarea');
				            ta.value = txt;
				            ta.style.position = 'fixed';
				            ta.style.left = '-9999px';
				            document.body.appendChild(ta);
				            ta.select();
				            document.execCommand('copy');
				            document.body.removeChild(ta);
				            return true;
				          } catch (e) { return false; }
				        };
				        btn.addEventListener('click', async () => {
				          try { btn.disabled = true; } catch (e) {}
				          const txt = await buildDiag();
				          const ok = await copyText(txt);
				          try { btn.disabled = false; } catch (e) {}
				          try {
				            const statusEl = document.getElementById('task-builder-status');
				            if (statusEl) statusEl.textContent = ok ? 'Diagnóstico copiado.' : 'No se pudo copiar diagnóstico (pega manualmente desde consola).';
				          } catch (e) {}
				          if (!ok) {
				            try { window.prompt('Copia el diagnóstico:', txt); } catch (e) {}
				          }
				        });
					      })();
