(function () {
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
          const labels = Array.from(grid.children || []).filter((el) => el && el.matches && el.matches('label') && el.querySelector('input,select,textarea'));
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
          rows.forEach((row) => { row.label.hidden = !controlValue(row.control); });
          button.addEventListener('click', () => {
            const row = rows.find((item) => String(item.index) === String(select.value));
            if (!row) return;
            row.label.hidden = false;
            refreshOptions();
            try { row.control?.focus({ preventScroll: true }); } catch (e) {}
          });
          refreshOptions();
        };
        const boot = () => document.querySelectorAll('[data-methodology-picker]').forEach(initPicker);
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
        else boot();
      })();
