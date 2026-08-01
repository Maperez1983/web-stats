/*
 * Selector de rival del alta de partido.
 *
 * Dos trabajos: (1) si lo que hay escrito es un equipo que ya existe, mandar su id —así el
 * servidor no tiene que adivinar por nombre—; (2) si se PARECE a uno existente pero no es
 * exacto, avisar antes de crear, porque la deduplicación no quita sufijos (C.F., C.D.…) y
 * "Alhaurín Torre" acabaría siendo un equipo nuevo distinto de "ALHAURIN DE LA TORRE C.F.".
 */
(() => {
  /* Palabras que no distinguen a un equipo de otro: formas jurídicas y partículas. Se
     quitan SOLO para sugerir ("¿te refieres a…?"), nunca para decidir por su cuenta. */
  const VACIAS = new Set([
    'cf', 'cd', 'ud', 'sad', 'fc', 'sd', 'ad', 'cp', 'ce', 'cdb', 'club', 'deportivo',
    'atletico', 'atco', 'union', 'sociedad', 'balompie', 'de', 'del', 'la', 'las', 'el',
    'los', 'y', 'the',
  ]);

  const base = (texto) =>
    String(texto || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '');

  /* Núcleo del nombre: sus palabras con contenido, ordenadas. Los puntos se quitan ANTES
     de partir, o "C.F." llegaría como "c" y "f" y no se reconocería como sigla. Así
     "Alhaurín Torre" y "ALHAURIN DE LA TORRE C.F." caen en la misma clave. */
  const nucleo = (texto) =>
    String(texto || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/\./g, '')
      .split(/[^a-z0-9]+/)
      .filter((palabra) => palabra && !VACIAS.has(palabra))
      .sort()
      .join('');

  const preparar = (input) => {
    const lista = document.getElementById(input.getAttribute('list'));
    if (!lista) return;
    const hidden = document.getElementById(`${input.id}-id`);
    const aviso = document.getElementById(`${input.id}-note`);
    const opciones = Array.from(lista.options).map((option) => ({
      id: option.dataset.id || '',
      name: option.value || '',
      location: option.dataset.location || '',
      exacto: base(option.value),
      nucleo: nucleo(option.value),
    }));

    const aplicar = (opcion) => {
      input.value = opcion.name;
      if (hidden) hidden.value = opcion.id;
      if (aviso) {
        aviso.hidden = false;
        aviso.textContent = `Se usará el equipo que ya tienes: ${opcion.name}.`;
      }
      const campoCampo = document.getElementById('locationInput');
      if (campoCampo && !campoCampo.value && opcion.location) campoCampo.value = opcion.location;
    };

    const revisar = () => {
      const escrito = input.value || '';
      if (!escrito.trim()) {
        if (hidden) hidden.value = '';
        if (aviso) aviso.hidden = true;
        return;
      }
      const exacto = opciones.find((o) => o.exacto === base(escrito));
      if (exacto) {
        aplicar(exacto);
        return;
      }
      if (hidden) hidden.value = '';
      const parecido = opciones.find((o) => o.nucleo && o.nucleo === nucleo(escrito));
      if (!aviso) return;
      if (parecido) {
        aviso.hidden = false;
        aviso.textContent = '';
        aviso.append('¿Te refieres a ');
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'rival-picker-use';
        boton.textContent = parecido.name;
        boton.addEventListener('click', () => aplicar(parecido));
        aviso.append(boton);
        aviso.append('? Si no, se creará un equipo nuevo.');
      } else {
        aviso.hidden = false;
        aviso.textContent = 'No coincide con ningún equipo tuyo: se creará uno nuevo.';
      }
    };

    input.addEventListener('change', revisar);
    input.addEventListener('blur', revisar);
    if (input.value) revisar();
  };

  document.querySelectorAll('input[data-rival-picker]').forEach(preparar);
})();
