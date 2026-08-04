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
    // El saque y la 2ª parte ya se marcaron con el vídeo (botones "Saque aquí" / "2ª parte aquí").
    // Si nadie los marcó, se asume grabación que empieza en el saque, y se dice.
    const marcado = Number((document.getElementById('vs-kickoff-s') || {}).value || 0);
    if (!marcado) decir('Sin saque marcado: se toma el segundo 0. Si grabaste antes, pausa en el saque y pulsa «Saque aquí».');

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


/*
  Marcar el saque y la 2ª parte CON el vídeo: se pausa donde toca y se pulsa. Es lo que hace
  cualquiera viendo un partido; teclear "el segundo 743" no lo hace nadie.
*/
(function () {
  const url = window.VS_CLIPS_REGISTRO_URL;
  const video = document.getElementById('vs-video');
  if (!url || !video) return;
  const csrf = () => {
    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : '';
  };
  const decir = (t) => { const n = document.getElementById('vs-status'); if (n) n.textContent = t; };
  const reloj = (s) => {
    const m = Math.floor(s / 60);
    return m + "'" + String(Math.round(s % 60)).padStart(2, '0') + '"';
  };

  const marcar = async (clave, etiqueta, guardaEn) => {
    const segundo = Math.max(0, Math.round(video.currentTime || 0));
    const cuerpo = { solo_marcar: true };
    cuerpo[clave] = segundo;
    const atado = (document.getElementById('vs-match-id') || {}).value;
    if (!atado) {
      const id = window.prompt('¿De qué partido es esta grabación? Pega su número.');
      if (!id) return;
      cuerpo.match_id = Number(id) || 0;
    }
    try {
      const r = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify(cuerpo),
      });
      const d = await r.json();
      if (!d.ok && !d.marked) { decir(d.error || 'No se pudo marcar.'); return; }
      const campo = document.getElementById(guardaEn);
      if (campo) campo.value = String(segundo * 1000);
      decir(etiqueta + ' marcado en ' + reloj(segundo) + '.');
    } catch (e) {
      decir('No se pudo marcar.');
    }
  };

  const bSaque = document.getElementById('vs-mark-kickoff');
  if (bSaque) bSaque.addEventListener('click', () => marcar('kickoff_s', 'Saque inicial', 'vs-kickoff-s'));
  const bSegunda = document.getElementById('vs-mark-second-half');
  if (bSegunda) bSegunda.addEventListener('click', () => marcar('second_half_s', 'Inicio de la 2ª parte', 'vs-second-half-s'));
})();

/*
  Filtro de la lista de clips. Es lo que hace un analista todo el rato: "enséñame las pérdidas".
  Filtra sobre lo que ya está pintado -título, notas y etiquetas- sin volver al servidor.
*/
(function () {
  const caja = document.getElementById('vs-clips-filter');
  const lista = document.getElementById('vs-clips');
  const cuenta = document.getElementById('vs-clips-count-simple');
  if (!caja || !lista) return;
  let original = '';

  const aplicar = () => {
    const q = caja.value.trim().toLowerCase();
    const filas = Array.from(lista.children);
    let vistos = 0;
    filas.forEach((fila) => {
      const texto = (fila.textContent || '').toLowerCase();
      const ok = !q || texto.includes(q);
      fila.hidden = !ok;
      if (ok) vistos += 1;
    });
    if (cuenta) {
      if (!original) original = cuenta.textContent || '';
      cuenta.textContent = q ? (vistos + ' de ' + filas.length + ' clips · filtro «' + caja.value.trim() + '»') : original;
    }
  };

  caja.addEventListener('input', aplicar);
  // La lista se repinta al guardar o borrar clips: hay que volver a aplicar el filtro o
  // reaparecen los que estaban escondidos.
  try { new MutationObserver(() => { original = ''; aplicar(); }).observe(lista, { childList: true }); } catch (e) { /* ignore */ }
})();
