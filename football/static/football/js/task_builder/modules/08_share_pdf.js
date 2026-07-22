var cfg = window.__TASK_BUILDER_CONFIG || {};
      (function () {
        const uefaBtn = document.getElementById('share-pdf-uefa');
        const clubBtn = document.getElementById('share-pdf-club');
        const csrf = document.querySelector('#task-builder-form input[name="csrfmiddlewaretoken"]')?.value || '';
        const taskId = String(cfg.taskId || '');
        const taskKind = 'session';
        const createUrl = String(cfg.shareTaskPdfCreateUrl || '');
        const run = async (style) => {
          try {
            const password = window.prompt('Contraseña (opcional, deja vacío si no quieres):', '') || '';
            const body = new URLSearchParams();
            body.set('task_kind', taskKind);
            body.set('task_id', String(taskId));
            body.set('style', String(style || 'uefa'));
            body.set('valid_days', '30');
            if (password) body.set('password', password);
            const resp = await fetch(createUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
              credentials: 'same-origin',
              body: body.toString(),
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok || !data?.url) throw new Error(data?.error || 'No se pudo crear el enlace.');
            try { await navigator.clipboard?.writeText(data.url); } catch (e) { /* ignore */ }
            window.prompt('Enlace público (copiado si el navegador lo permite):', data.url);
          } catch (err) {
            window.alert(err?.message || 'Error al crear enlace.');
          }
        };
        uefaBtn?.addEventListener('click', () => run('uefa'));
        clubBtn?.addEventListener('click', () => run('club'));
      })();
