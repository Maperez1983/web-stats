// Rendimiento: cargamos Fabric + editor (TPad) + 3D SOLO cuando hace falta.
			      (function () {
			        const form = document.getElementById('task-builder-form');
			        if (!form) return;
		        const fabricSrc = String(form.dataset.fabricSrc || '').trim();
		        const tpadSrc = String(form.dataset.tpadSrc || '').trim();
		        const threeSrc = String(form.dataset.threeSrc || '').trim();
		        const threeGltfLoaderSrc = String(form.dataset.threeGltfLoaderSrc || '').trim();
		        const threeDracoLoaderSrc = String(form.dataset.threeDracoLoaderSrc || '').trim();
		        const sim3dSrc = String(form.dataset.sim3dSrc || '').trim();
		        const statusEl = document.getElementById('task-builder-status');

		        const setStatus = (msg) => {
		          try { if (statusEl) statusEl.textContent = String(msg || '').trim(); } catch (e) { /* ignore */ }
		        };

			        const loadOnce = (src, key, isReady) => {
			          if (!src) return Promise.reject(new Error('no-src'));
			          try {
			            if (typeof isReady === 'function' && isReady()) return Promise.resolve(true);
			          } catch (e) { /* ignore */ }
			          if (window[key]) return window[key];
			          window[key] = new Promise((resolve, reject) => {
			            try {
			              const base = src.split('?')[0];
			              const existing = Array.from(document.scripts || []).find((s) => String(s.src || '').includes(base));
			              if (existing) {
			                try {
			                  if (typeof isReady === 'function' && isReady()) { resolve(true); return; }
			                } catch (e) { /* ignore */ }
			                // Si el script existe pero aún no ha ejecutado (defer), esperamos a su load.
			                try {
			                  if (existing.__webstatsLoadOncePromise) {
			                    existing.__webstatsLoadOncePromise.then(resolve).catch(reject);
			                    return;
			                  }
			                } catch (e) { /* ignore */ }
			                const p = new Promise((res, rej) => {
			                  let settled = false;
			                  const done = () => {
			                    if (settled) return;
			                    settled = true;
			                    try { existing.dataset.webstatsLoaded = '1'; } catch (e) { /* ignore */ }
			                    res(true);
			                  };
			                  const fail = () => {
			                    if (settled) return;
			                    settled = true;
			                    rej(new Error('load-failed'));
			                  };
			                  try { existing.addEventListener('load', done, { once: true }); } catch (e) { /* ignore */ }
			                  try { existing.addEventListener('error', fail, { once: true }); } catch (e) { /* ignore */ }
				                  // Fallback: algunos WebViews no disparan load si ya ocurrió.
				                  // Importante: en iPad/Safari (y JS grande) el parse puede tardar bastante.
				                  // Si marcamos fail demasiado pronto, cacheamos una Promise rechazada y el editor
				                  // queda "muerto" aunque el script termine de cargar después.
				                  const startTs = Date.now();
				                  const maxWaitMs = 12000;
				                  const poll = () => {
				                    try {
				                      // Si no podemos detectar readiness, asumimos que el script existente ya está OK.
				                      if (typeof isReady !== 'function') { done(); return; }
				                      if (isReady()) { done(); return; }
				                    } catch (e) {
				                      // Seguimos esperando salvo que se agote el timeout.
				                    }
				                    if ((Date.now() - startTs) >= maxWaitMs) { fail(); return; }
				                    window.setTimeout(poll, 450);
				                  };
				                  window.setTimeout(poll, 1200);
				                });
			                try { existing.__webstatsLoadOncePromise = p; } catch (e) { /* ignore */ }
			                p.then(resolve).catch(reject);
			                return;
			              }
			            } catch (e) { /* ignore */ }
			            const s = document.createElement('script');
			            s.src = src;
			            s.defer = true;
                  s.onload = () => {
                    const finish = () => {
			              try { s.dataset.webstatsLoaded = '1'; } catch (e) { /* ignore */ }
			              resolve(true);
                    };
                    try {
                      if (typeof isReady !== 'function') { finish(); return; }
                      if (isReady()) { finish(); return; }
                    } catch (e) { /* ignore */ }
                    const startTs = Date.now();
                    const maxWaitMs = 12000;
                    const poll = () => {
                      try {
                        if (isReady()) { finish(); return; }
                      } catch (e) { /* ignore */ }
                      if ((Date.now() - startTs) >= maxWaitMs) {
                        reject(new Error('load-ready-timeout'));
                        return;
                      }
                      window.setTimeout(poll, 300);
                    };
                    window.setTimeout(poll, 50);
                  };
			            s.onerror = () => reject(new Error('load-failed'));
			            document.head.appendChild(s);
			          });
			          return window[key];
			        };

              const pitch25dSrc = form?.dataset?.pitch25dSrc || '';
			        const ensureFabric = () => {
			          try { if (window.fabric) return Promise.resolve(true); } catch (e) { /* ignore */ }
			          return loadOnce(fabricSrc, '__webstats_fabric_promise', () => !!window.fabric);
			        };
              const ensurePitch25d = () => {
                try { if (window.WebstatsPitch25D && typeof window.WebstatsPitch25D.buildPitchSvg === 'function') return Promise.resolve(true); } catch (e) { /* ignore */ }
                if (!pitch25dSrc) return Promise.resolve(false);
                return loadOnce(pitch25dSrc, '__webstats_pitch25d_promise', () => !!(window.WebstatsPitch25D && typeof window.WebstatsPitch25D.buildPitchSvg === 'function'));
              };
			        const ensureTpad = () => loadOnce(tpadSrc, '__webstats_tpad_promise', () => typeof window.initSessionsTacticalPad === 'function');

			        const ensureThree = () => {
			          try { if (window.THREE && window.THREE.WebGLRenderer) return Promise.resolve(true); } catch (e) { /* ignore */ }
			          if (!threeSrc) return Promise.resolve(false);
			          if (window.__webstats_three_promise) return window.__webstats_three_promise;
			          window.__webstats_three_promise = import(threeSrc)
			            .then((mod) => {
			              try { window.THREE = mod; } catch (e) { /* ignore */ }
			              return !!(mod && mod.WebGLRenderer);
			            })
			            .catch(() => false);
			          return window.__webstats_three_promise;
			        };
			        const ensureGltfLoader = () => {
			          if (!threeGltfLoaderSrc) return Promise.resolve(false);
			          try { if (window.__WEBSTATS_GLTF_LOADER_CLASS) return Promise.resolve(true); } catch (e) { /* ignore */ }
			          if (window.__webstats_gltf_loader_promise) return window.__webstats_gltf_loader_promise;
			          const dracoPromise = threeDracoLoaderSrc
			            ? import(threeDracoLoaderSrc)
			                .then((mod) => {
			                  try { window.__WEBSTATS_DRACO_LOADER_CLASS = mod && mod.DRACOLoader; } catch (e) { /* ignore */ }
			                  return !!(mod && mod.DRACOLoader);
			                })
			                .catch(() => false)
			            : Promise.resolve(false);
			          window.__webstats_gltf_loader_promise = Promise.all([
			            import(threeGltfLoaderSrc),
			            dracoPromise,
			          ])
			            .then(([mod]) => {
			              try { window.__WEBSTATS_GLTF_LOADER_CLASS = mod && mod.GLTFLoader; } catch (e) { /* ignore */ }
			              return !!(mod && mod.GLTFLoader);
			            })
			            .catch(() => false);
			          return window.__webstats_gltf_loader_promise;
			        };
			        const ensureSim3d = () => {
			          if (!sim3dSrc) return Promise.resolve(true);
			          return loadOnce(sim3dSrc, '__webstats_sim3d_promise');
			        };

			        const ensureEditorStack = () => {
			          setStatus('Cargando editor…');
			          return ensurePitch25d()
                  .then(() => ensureFabric())
			            .then(() => ensureTpad())
			            .then(() => {
			              try {
			                if (window.initSessionsTacticalPad) window.initSessionsTacticalPad();
			              } catch (e) {
			                try { window.__webstatsTpadLastError = String(e && (e.message || e) ? (e.message || e) : e).slice(0, 220); } catch (err) { /* ignore */ }
			                setStatus(`Error pizarra: ${String(window.__webstatsTpadLastError || 'init').slice(0, 180)}`);
			                return true;
			              }
			              setStatus('');
			              return true;
			            })
			            .catch(() => { setStatus('No se pudo cargar el editor.'); return false; });
			        };

			        const ensure3dStack = () => {
			          setStatus('Cargando 3D…');
			          return ensureEditorStack()
			            .then(() => ensureThree())
			            .then(() => ensureGltfLoader())
			            .then(() => ensureSim3d())
			            .then(() => { setStatus(''); return true; })
			            .catch(() => { setStatus('No se pudo cargar la Vista 3D.'); return false; });
			        };

            // Expose minimal hooks for other inline scripts (landing / mode switchers).
            // Keeps lazy-loading while ensuring the pitch is available when user chooses "Pizarra".
            try { window.__webstatsEnsureEditorStack = ensureEditorStack; } catch (e) { /* ignore */ }
            try { window.__webstatsEnsure3dStack = ensure3dStack; } catch (e) { /* ignore */ }

		        const hookClick = (id, ensureFn, markerKey) => {
		          const el = document.getElementById(id);
		          if (!el) return;
		          const key = markerKey || 'webstatsReady';
		          el.addEventListener('click', async (ev) => {
		            try {
		              const editorReady = (() => {
		                try { return (form?.dataset?.webstatsTpadReady === '1') || (window.__WEBSTATS_TPAD_READY === true); } catch (e) { return false; }
		              })();
		              if (editorReady && key === 'webstatsEditorReady') {
		                try { el.dataset[key] = '1'; } catch (e) { /* ignore */ }
		                return;
		              }
		              if (el.dataset?.[key] === '1') return;
		              if (typeof ensureFn !== 'function') return;
		              ev.preventDefault();
		              ev.stopPropagation();
		              const ok = await ensureFn();
		              if (!ok) return;
		              try { el.dataset[key] = '1'; } catch (e) { /* ignore */ }
		              // Re-dispara el click para que lo capture el handler real.
		              try { el.click(); } catch (e) { /* ignore */ }
		            } catch (e) { /* ignore */ }
		          }, { capture: true });
		        };

		        // Editor: al abrir pizarra/simulador/recursos, garantizamos Fabric+TPad.
		        // (Sin esto, iPad se queda "pensando" porque parsea 1MB de JS aunque no lo uses.)
		        hookClick('surface-trigger', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-view-menu', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-orientation-toggle-quick', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-orientation-toggle', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-grass-toggle', ensureEditorStack, 'webstatsEditorReady');
            hookClick('pitch-ad-select', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-zoom-out', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-zoom-in', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-zoom-reset', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-size-down', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-size-up', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-size-fit', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('task-sim-toggle', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('task-sim-open', ensureEditorStack, 'webstatsEditorReady');
		        hookClick('pitch-3d-open-standard', ensure3dStack, 'webstats3dReady');
		        hookClick('pitch-3d-open-tactics', ensure3dStack, 'webstats3dReady');
		        hookClick('task-playbook-open-sim', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-playbook-open-video', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-playbook-export-pack', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-step-add', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-step-play', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-step-duplicate', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-step-remove', ensureEditorStack, 'webstatsEditorReady');
			        // Táctica: botones superiores (Playbook/Herramientas/Simulador + guardado) también deben cargar el editor.
			        hookClick('task-tactics-panel-toggle', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-tactics-tools-toggle', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('task-tactics-sim-open', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('tactics-save-top', ensureEditorStack, 'webstatsEditorReady');
			        hookClick('tactics-save-task-top', ensureEditorStack, 'webstatsEditorReady');
				        hookClick('tactics-save-task-system-top', ensureEditorStack, 'webstatsEditorReady');
				        hookClick('tactics-save-clip-top', ensureEditorStack, 'webstatsEditorReady');

			        // Heurística: si el usuario está realmente en el editor (no solo leyendo),
		        // precargamos en idle para que el primer toque sea instantáneo.
		        //
		        // Safari/WebKit: hemos visto `ReferenceError: Can't find variable: scheduleIdle` en producción
		        // (probablemente por alcance entre scripts inline). Evitamos ese identificador y usamos un helper
		        // global ultra-defensivo.
		        const __webstatsScheduleIdleLocal = (fn, timeoutMs = 1600) => {
		          try {
		            if (typeof window.requestIdleCallback === 'function') {
		              return window.requestIdleCallback(fn, { timeout: timeoutMs });
		            }
		          } catch (e) { /* ignore */ }
		          return window.setTimeout(fn, 120);
		        };
		        try {
		          if (typeof window.__webstatsScheduleIdle !== 'function') window.__webstatsScheduleIdle = __webstatsScheduleIdleLocal;
		        } catch (e) { /* ignore */ }
		        const preloadEditorIfNeeded = () => {
		          const hasTaskId = !!String(form.dataset.taskId || '').trim();
              const isTacticsMode = String(form.dataset.tacticsMode || '').trim() === '1';
		          const hasGraphicalSurface = !!document.querySelector('.pitch-stage, #task-pitch-surface');
		          const wantsBoard = !!document.querySelector('#task-mode-tabs [data-task-mode=\"board\"].is-active,#task-mode-tabs [data-task-mode=\"both\"].is-active');
		          if (isTacticsMode || hasGraphicalSurface || hasTaskId || wantsBoard) ensureEditorStack();
		        };
		        (window.__webstatsScheduleIdle || __webstatsScheduleIdleLocal)(preloadEditorIfNeeded, 2200);

            // Editor normal: si la superficie gráfica ya está visible, cargamos la pizarra en cuanto la UI
            // esté montada para que los controles (orientación, césped, tamaño, etc.) respondan al primer click.
            try {
              const isTacticsModeNow = String(form.dataset.tacticsMode || '').trim() === '1';
              const hasGraphicalSurfaceNow = !!document.querySelector('.pitch-stage, #task-pitch-surface');
              if (!isTacticsModeNow && hasGraphicalSurfaceNow) {
                ensureEditorStack();
                window.setTimeout(() => { try { ensureEditorStack(); } catch (e) { /* ignore */ } }, 650);
              }
            } catch (e) { /* ignore */ }

            // En Táctica, la pizarra es el producto: cargamos el editor inmediatamente para evitar
            // que el usuario vea un campo oscuro (placeholder) varios segundos.
            // En algunos navegadores (Safari) o tras un deploy, el primer tick puede ocurrir antes de que
            // la UI esté "estable" (fuentes/CSS) y el lazy-load falla silenciosamente. Reintentamos.
            try {
              const isTacticsModeNow = String(form.dataset.tacticsMode || '').trim() === '1';
              if (isTacticsModeNow) {
                ensureEditorStack();
                window.setTimeout(() => { try { ensureEditorStack(); } catch (e) { /* ignore */ } }, 650);
                window.setTimeout(() => { try { ensureEditorStack(); } catch (e) { /* ignore */ } }, 2200);
              }
            } catch (e) { /* ignore */ }

		        // 3D de pizarra (usa Three.js dentro del editor TPad).
		        hookClick(
		          'pitch-3d-open-standard',
		          () => ensureEditorStack().then((ok) => (ok ? ensureThree().then(() => true) : false)),
		          'webstatsThreeReady'
		        );
		        hookClick(
		          'pitch-3d-open-tactics',
		          () => ensureEditorStack().then((ok) => (ok ? ensureThree().then(() => true) : false)),
		          'webstatsThreeReady'
		        );
		        // 3D del simulador (usa visor dedicado)
		        hookClick(
		          'task-sim-view-3d',
		          () => ensureEditorStack().then((ok) => (ok ? ensure3dStack() : false)),
		          'webstats3dReady'
		        );
		        hookClick(
		          'task-playbook-open-3d',
		          () => ensureEditorStack().then((ok) => (ok ? ensure3dStack() : false)),
		          'webstats3dReady'
		        );
		      })();
