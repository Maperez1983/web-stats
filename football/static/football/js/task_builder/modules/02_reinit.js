(function () {
                  const btn = document.getElementById('tpad-reinit');
                  if (!btn) return;
                  btn.addEventListener('click', async () => {
                    const form = document.getElementById('task-builder-form');
                    const statusEl = document.getElementById('task-builder-status');
                    const setStatus = (msg) => { try { if (statusEl) statusEl.textContent = String(msg || ''); } catch (e) {} };
                    try {
                      if (form && form.dataset) {
                        try { delete form.dataset.webstatsTpadReady; } catch (e) {}
                        try { delete form.dataset.webstatsTpadInit; } catch (e) {}
                      }
                      try { window.__WEBSTATS_TPAD_READY = false; } catch (e) {}
                      setStatus('Reiniciando pizarra…');
                      if (typeof window.__webstatsEnsureEditorStack === 'function') {
                        await window.__webstatsEnsureEditorStack();
                      } else if (typeof window.initSessionsTacticalPad === 'function') {
                        window.initSessionsTacticalPad();
                      }
                      window.setTimeout(() => {
                        try {
                          if (typeof window.initSessionsTacticalPad === 'function') window.initSessionsTacticalPad();
                          setStatus('');
                        } catch (e) {
                          setStatus('Error al reiniciar pizarra.');
                        }
                      }, 220);
                    } catch (e) {
                      setStatus('Error al reiniciar pizarra.');
                    }
                  });
                })();
