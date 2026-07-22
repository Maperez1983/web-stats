// Fallback: pestañas de Recursos (Base/PRO/…)
		      (function () {
		        const boot = () => {
		          const tabs = Array.from(document.querySelectorAll('.resource-tab'));
	          const panels = Array.from(document.querySelectorAll('.resource-panel'));
          if (!tabs.length || !panels.length) return;
          const summary = document.getElementById('task-resource-summary-label');
          const helper = document.querySelector('.resource-helper');
          let activeKey = 'base';
          const labelFor = (key) => (key === 'pro' ? 'PRO' : (key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Selecciona…'));
          const activate = (key) => {
            const k = String(key || '').trim();
            if (!k) return;
            activeKey = k;
            tabs.forEach((t) => t.classList.toggle('is-active', String(t.dataset.resource || '').trim() === k));
            panels.forEach((p) => {
              const visible = String(p.dataset.panel || '').trim() === k;
              try { p.hidden = !visible; } catch (e) {}
              p.classList.toggle('is-visible', visible);
            });
            if (summary) summary.textContent = labelFor(k);
            if (helper) helper.hidden = true;
          };
          tabs.forEach((tab) => {
            tab.addEventListener('click', (ev) => {
              try { ev.preventDefault(); } catch (e) {}
              try { ev.stopPropagation(); } catch (e) {}
              const k = String(tab.dataset.resource || '').trim();
              if (k && k !== activeKey) activate(k);
            }, { passive: false });
          });
          activate(activeKey);
        };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
        else boot();
      })();
