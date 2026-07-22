(function () {
					        const report = (msg) => {
					          try {
					            const el = document.getElementById('task-builder-status');
					            if (el) el.textContent = String(msg || '').trim();
					          } catch (e) { /* ignore */ }
					        };
				        const recordErr = (err, label = 'initSessionsTacticalPad') => {
				          try {
				            const info = `${label}: ${String(err && (err.message || err) ? (err.message || err) : err)}`.slice(0, 220);
				            window.__webstatsTpadLastError = info;
				            report(`Error pizarra: ${info}`);
				          } catch (e) { /* ignore */ }
				        };
					        const boot = () => {
					          const form = document.getElementById('task-builder-form');
					          const isReady = () => {
					            try { return (form?.dataset?.webstatsTpadReady === '1') || (window.__WEBSTATS_TPAD_READY === true); } catch (e) { return false; }
					          };
					          if (isReady()) return;
					          try {
					            if (window.initSessionsTacticalPad) {
					              window.initSessionsTacticalPad();
					              if (isReady()) return;
					            }
					          } catch (e) {
					            recordErr(e);
					          }
					          // Si aún no está listo, mostramos estado (útil en Safari cuando los defer tardan).
					          try { report('Cargando pizarra…'); } catch (e) { /* ignore */ }
					        };
					        // `defer` ejecuta antes de DOMContentLoaded, pero en Safari a veces el orden es sensible.
					        // Reintentos: si el primer init falla (timing/DOM/recursos), reintentamos unos segundos.
					        const scheduleBootRetries = () => {
					          try {
					            let attempts = 0;
					            const tick = () => {
					              attempts += 1;
					              boot();
					              const form = document.getElementById('task-builder-form');
					              const ready = (() => {
					                try { return (form?.dataset?.webstatsTpadReady === '1') || (window.__WEBSTATS_TPAD_READY === true); } catch (e) { return false; }
					              })();
					              if (ready) return;
					              if (attempts >= 8) return;
					              const delay = attempts < 3 ? 120 : attempts < 6 ? 420 : 900;
					              window.setTimeout(tick, delay);
					            };
					            window.setTimeout(tick, 0);
					          } catch (e) { /* ignore */ }
					        };
					        try { scheduleBootRetries(); } catch (e) { /* ignore */ }
					        try { window.addEventListener('DOMContentLoaded', scheduleBootRetries, { once: true }); } catch (e) { /* ignore */ }
					        try { window.addEventListener('load', scheduleBootRetries, { once: true }); } catch (e) { /* ignore */ }
				        // Captura errores globales para diagnóstico rápido.
				        try {
				          window.addEventListener('error', (ev) => {
				            try {
				              const msg = String(ev && ev.message ? ev.message : '').trim();
				              if (msg && (msg.toLowerCase().includes('tactical') || msg.toLowerCase().includes('tpad') || msg.toLowerCase().includes('fabric') || msg.toLowerCase().includes('create-task-canvas'))) {
				                recordErr(msg, 'window.onerror');
				              }
				            } catch (e) { /* ignore */ }
				          });
				        } catch (e) { /* ignore */ }
				      })();
