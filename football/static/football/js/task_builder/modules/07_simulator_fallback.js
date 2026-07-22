// Seguro extra: si el script principal falló antes de enganchar listeners, estos botones
          // deben seguir abriendo el panel del simulador (al menos).
          (function () {
            const statusEl = document.getElementById('task-builder-status');
            const simPopoverEl = document.getElementById('task-sim-popover');
            const open = function () {
              try { if (simPopoverEl) simPopoverEl.hidden = false; } catch (e) {}
              try { if (statusEl) statusEl.textContent = 'Simulador: panel abierto.'; } catch (e) {}
            };
            ['task-playbook-open-sim', 'task-playbook-open-3d', 'task-playbook-open-video', 'task-playbook-export-pack']
              .forEach(function (id) {
                var btn = document.getElementById(id);
                if (!btn) return;
                btn.addEventListener('click', open);
              });
          })();
