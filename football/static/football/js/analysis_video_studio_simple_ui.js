(function () {
  const init = () => {
    const tabClip = document.getElementById('vs-tab-clip');
    const tabAdvanced = document.getElementById('vs-tab-advanced');
    const panelClip = document.getElementById('vs-panel-clip');
    const panelAdvanced = document.getElementById('vs-panel-advanced');
    if (!tabClip || !tabAdvanced || !panelClip || !panelAdvanced) return;

    let advancedBootstrapped = false;
    let advancedRetries = 0;
    const tryEnableAdvanced = () => {
      try {
        if (typeof window.__vsEnableAdvancedFeatures === 'function') {
          window.__vsEnableAdvancedFeatures();
          return true;
        }
      } catch (e) {
        // ignore
      }
      return false;
    };

    const setActive = (name) => {
      const isClip = name === 'clip';
      tabClip.setAttribute('aria-selected', String(isClip));
      tabAdvanced.setAttribute('aria-selected', String(!isClip));
      tabClip.tabIndex = isClip ? 0 : -1;
      tabAdvanced.tabIndex = isClip ? -1 : 0;
      panelClip.hidden = !isClip;
      panelAdvanced.hidden = isClip;
      try { document.body.classList.toggle('vs-advanced', !isClip); } catch (e) { /* ignore */ }

      if (!isClip && !advancedBootstrapped) {
        advancedBootstrapped = true;
        if (!tryEnableAdvanced()) {
          const tick = () => {
            if (tryEnableAdvanced()) return;
            advancedRetries += 1;
            if (advancedRetries > 10) return;
            window.setTimeout(tick, 250);
          };
          window.setTimeout(tick, 250);
        }
      }
    };

    tabClip.addEventListener('click', () => setActive('clip'));
    tabAdvanced.addEventListener('click', () => setActive('advanced'));

    setActive('clip');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();

/*
  "Clips del registro": el etiquetado del domingo convertido en cortes.

  Va aquí y no en el estudio grande (11k líneas) a propósito: es una pieza pequeña, independiente y
  que se entiende sola. Pregunta lo único que el programa no puede saber -en qué segundo del vídeo
  se pita el inicio- y deja que el servidor haga el resto.
*/
(function () {
  const boton = document.getElementById('vs-clips-registro');
  if (!boton || !window.VS_CLIPS_REGISTRO_URL) return;
  const csrf = () => {
    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : '';
  };
  const decir = (texto) => {
    const n = document.getElementById('vs-status');
    if (n) n.textContent = texto; else window.alert(texto);
  };

  boton.addEventListener('click', async () => {
    const video = document.getElementById('vs-video');
    const atado = (document.getElementById('vs-match-id') || {}).value;
    const cuerpo = { duration_s: video && video.duration ? video.duration : 0 };

    if (!atado) {
      const id = window.prompt('¿De qué partido es esta grabación? Pega el número de partido (lo ves en su ficha).');
      if (!id) return;
      cuerpo.match_id = Number(id) || 0;
    }
    // El minuto 0 del partido casi nunca es el segundo 0 del vídeo: se graba antes del saque.
    const inicio = window.prompt('¿En qué segundo del vídeo se pita el inicio? (0 si empieza justo)', '0');
    if (inicio === null) return;
    cuerpo.kickoff_s = Number(inicio) || 0;
    const segunda = window.prompt('¿Y en qué segundo empieza la 2ª parte? (0 si la grabación es continua)', '0');
    if (segunda === null) return;
    cuerpo.second_half_s = Number(segunda) || 0;

    decir('Generando clips desde el registro…');
    try {
      const r = await fetch(window.VS_CLIPS_REGISTRO_URL, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(cuerpo),
      });
      const d = await r.json();
      if (!d.ok) { decir(d.error || 'No se pudieron generar los clips.'); return; }
      const restos = [];
      if (d.skipped) restos.push(d.skipped + ' ya estaban');
      if (d.without_minute) restos.push(d.without_minute + ' sin minuto anotado');
      decir('Creados ' + d.created + ' clips' + (restos.length ? ' (' + restos.join(', ') + ')' : '') + '. Recarga para verlos.');
    } catch (e) {
      decir('No se pudieron generar los clips.');
    }
  });
})();
