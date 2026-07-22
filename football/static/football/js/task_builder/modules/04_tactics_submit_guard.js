// Modo Táctica: evita JS inline pesado (asistente, landing, etc.).
						      // Mantiene el guard-rail de submit: el guardado se hace como clip en Playbook.
						      window.addEventListener('DOMContentLoaded', () => {
						        try {
						          const form = document.getElementById('task-builder-form');
						          if (!form) return;
						          form.addEventListener('submit', (ev) => {
						            try { ev.preventDefault(); } catch (e) { /* ignore */ }
						            try {
						              const status = document.getElementById('task-builder-status');
						              if (status) status.textContent = 'Táctica: guarda como clip en Playbook (no se crea tarea).';
						            } catch (e) { /* ignore */ }
						            return false;
						          });
						        } catch (e) { /* ignore */ }
						      });
