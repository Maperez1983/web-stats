// Modo Táctica: evita JS inline pesado (asistente, landing, etc.).
// Mantiene el guard-rail de submit: en modo Táctica el guardado se hace como clip en Playbook.
// IMPORTANTE: este guard SOLO debe actuar en modo Táctica real (body.tactics-mode).
// Antes bloqueaba TODOS los submits del formulario aunque estuvieramos en el creador de
// tareas -> "Crear tarea" nunca guardaba (mostraba "guarda como clip en Playbook" y no
// creaba nada). Ahora comprobamos el modo antes de bloquear.
window.addEventListener('DOMContentLoaded', () => {
  try {
    const form = document.getElementById('task-builder-form');
    if (!form) return;
    form.addEventListener('submit', (ev) => {
      // Solo interceptamos en modo Tactica (pizarra libre). En el creador/editor de
      // tareas dejamos que el submit siga su curso normal para poder crear la tarea.
      try {
        if (!document.body || !document.body.classList || !document.body.classList.contains('tactics-mode')) {
          return;
        }
      } catch (e) {
        return;
      }
      try { ev.preventDefault(); } catch (e) { /* ignore */ }
      try {
        const status = document.getElementById('task-builder-status');
        if (status) status.textContent = 'Tactica: guarda como clip en Playbook (no se crea tarea).';
      } catch (e) { /* ignore */ }
      return false;
    });
  } catch (e) { /* ignore */ }
});
