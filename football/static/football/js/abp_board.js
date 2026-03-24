(function () {
  const shared = window.FootballTacticalShared || {};
  const readStorageJson = shared.readStorageJson || (() => ({}));
  const writeStorageJson = shared.writeStorageJson || (() => false);
  const downloadJson = shared.downloadJson || (() => {});

  const PLAYBOOK_STORAGE_KEY = 'abpPlaybook:v2';
  const DRAFT_STORAGE_KEY = `abpBoardDraft:v2:${window.location.pathname}`;

  document.addEventListener('DOMContentLoaded', () => {
    const field = document.getElementById('abp-field');
    if (!field) return;

    const movesLog = document.getElementById('moves-log');
    const playersList = document.getElementById('players-list');
    const recordBtn = document.getElementById('record-btn');
    const stopBtn = document.getElementById('stop-btn');
    const playBtn = document.getElementById('play-btn');
    const addRivalBtn = document.getElementById('add-rival-btn');
    const clearBtn = document.getElementById('clear-btn');
    const exportBtn = document.getElementById('export-btn');
    const playbookSelect = document.getElementById('playbook-select');
    const savePlayBtn = document.getElementById('save-play-btn');
    const loadPlayBtn = document.getElementById('load-play-btn');
    const deletePlayBtn = document.getElementById('delete-play-btn');
    const quickComponents = Array.from(document.querySelectorAll('[data-component]'));

    const state = {
      playing: false,
      recording: false,
      selectedTokenId: null,
      timeline: [],
      tokens: [],
    };

    const log = (text) => {
      if (!movesLog) return;
      const line = document.createElement('div');
      line.textContent = text;
      movesLog.prepend(line);
    };
    const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const fieldRect = () => field.getBoundingClientRect();
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const writeSnapshot = (type, token) => {
      if (!state.recording || !token) return;
      state.timeline.push({
        t: Date.now(),
        type,
        tokenId: token.dataset.id,
        label: token.dataset.label,
        x: parseFloat(token.dataset.x || '50'),
        y: parseFloat(token.dataset.y || '50'),
      });
      saveDraft();
    };
    const placeToken = (token, xPct, yPct) => {
      const x = clamp(xPct, 2, 98);
      const y = clamp(yPct, 2, 98);
      token.style.left = `${x}%`;
      token.style.top = `${y}%`;
      token.dataset.x = String(x);
      token.dataset.y = String(y);
    };
    const buildPayload = () => ({
      generated_at: new Date().toISOString(),
      timeline: state.timeline,
      tokens: state.tokens.map((token) => ({
        id: token.dataset.id,
        kind: token.dataset.kind || '',
        label: token.dataset.label,
        number: token.textContent || '',
        side: token.dataset.side || 'team',
        x: token.dataset.x,
        y: token.dataset.y,
      })),
    });
    const saveDraft = () => {
      writeStorageJson(DRAFT_STORAGE_KEY, buildPayload());
    };
    const createToken = (label, number = '--', rival = false, kind = '') => {
      const token = document.createElement('div');
      token.className = `token ${kind ? `material ${kind}` : rival ? 'rival' : 'team'}`;
      token.textContent = number;
      token.title = label;
      token.dataset.label = label;
      token.dataset.id = uid();
      token.dataset.side = rival ? 'rival' : 'team';
      token.dataset.kind = kind;
      placeToken(token, 50, 50);
      token.addEventListener('pointerdown', (event) => {
        if (state.playing) return;
        token.classList.add('selected');
        state.selectedTokenId = token.dataset.id;
        token.setPointerCapture(event.pointerId);
        const onMove = (moveEvent) => {
          const rect = fieldRect();
          placeToken(token, ((moveEvent.clientX - rect.left) / rect.width) * 100, ((moveEvent.clientY - rect.top) / rect.height) * 100);
          writeSnapshot('move', token);
        };
        const onUp = () => {
          token.classList.remove('selected');
          token.removeEventListener('pointermove', onMove);
          token.removeEventListener('pointerup', onUp);
          token.removeEventListener('pointercancel', onUp);
          saveDraft();
        };
        token.addEventListener('pointermove', onMove);
        token.addEventListener('pointerup', onUp);
        token.addEventListener('pointercancel', onUp);
      });
      field.appendChild(token);
      state.tokens.push(token);
      writeSnapshot('add', token);
      saveDraft();
    };
    const clearBoard = (keepLog = false) => {
      state.tokens.forEach((token) => token.remove());
      state.tokens = [];
      state.timeline = [];
      saveDraft();
      if (!keepLog) log('Pizarra reseteada');
    };
    const hydrateFromPayload = (payload) => {
      clearBoard(true);
      state.timeline = Array.isArray(payload?.timeline) ? payload.timeline : [];
      (Array.isArray(payload?.tokens) ? payload.tokens : []).forEach((entry) => {
        createToken(entry?.label || 'TOKEN', entry?.number || '--', String(entry?.side || '') === 'rival', String(entry?.kind || ''));
        const token = state.tokens[state.tokens.length - 1];
        placeToken(token, parseFloat(entry?.x || '50'), parseFloat(entry?.y || '50'));
      });
      saveDraft();
    };
    const readPlaybook = () => {
      const parsed = readStorageJson(PLAYBOOK_STORAGE_KEY, {});
      return parsed && typeof parsed === 'object' ? parsed : {};
    };
    const writePlaybook = (payload) => {
      writeStorageJson(PLAYBOOK_STORAGE_KEY, payload || {});
    };
    const refreshPlaybookSelect = () => {
      if (!playbookSelect) return;
      const playbook = readPlaybook();
      playbookSelect.innerHTML = '<option value="">Jugada actual (sin guardar)</option>';
      Object.keys(playbook).sort().forEach((name) => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        playbookSelect.appendChild(option);
      });
    };

    playersList?.addEventListener('click', (event) => {
      const btn = event.target.closest('.player-chip');
      if (!btn) return;
      createToken(btn.dataset.player || 'JUGADOR', btn.dataset.number || '--', false);
      log(`Añadido ${btn.dataset.player || 'jugador'} al campo`);
    });
    addRivalBtn?.addEventListener('click', () => {
      createToken('RIVAL', 'R', true);
      log('Añadida ficha rival al campo');
    });
    quickComponents.forEach((btn) => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.component || '';
        if (type === 'ball') createToken('BALÓN', '●', false, 'ball');
        if (type === 'goal') createToken('PORTERÍA', '▭', false, 'goal');
        if (type === 'mini-goal') createToken('MINI PORTERÍA', '▯', false, 'goal');
        if (type === 'arrow') createToken('FLECHA', '➜', false, 'arrow');
        if (type === 'cone') createToken('CONO', '△', false, 'cone');
      });
    });
    recordBtn?.addEventListener('click', () => {
      state.recording = true;
      log('Grabación iniciada');
    });
    stopBtn?.addEventListener('click', () => {
      state.recording = false;
      log('Grabación detenida');
    });
    clearBtn?.addEventListener('click', () => clearBoard());
    playBtn?.addEventListener('click', async () => {
      if (!state.timeline.length || state.playing) return;
      state.playing = true;
      log(`Reproduciendo ${state.timeline.length} movimientos`);
      const first = state.timeline[0].t;
      for (const frame of state.timeline) {
        const wait = Math.max(0, frame.t - first);
        await new Promise((resolve) => window.setTimeout(resolve, Math.min(wait, 300)));
        const token = state.tokens.find((item) => item.dataset.id === frame.tokenId);
        if (token) placeToken(token, frame.x, frame.y);
      }
      state.playing = false;
    });
    exportBtn?.addEventListener('click', () => {
      downloadJson(buildPayload(), 'abp-playbook.json');
      log('Jugada exportada en JSON');
    });
    savePlayBtn?.addEventListener('click', () => {
      const name = window.prompt('Nombre de la jugada:');
      if (!name) return;
      const trimmed = name.trim();
      if (!trimmed) return;
      const playbook = readPlaybook();
      playbook[trimmed] = buildPayload();
      writePlaybook(playbook);
      refreshPlaybookSelect();
      if (playbookSelect) playbookSelect.value = trimmed;
      log(`Jugada guardada: ${trimmed}`);
    });
    loadPlayBtn?.addEventListener('click', () => {
      const selected = playbookSelect?.value || '';
      if (!selected) return;
      const playbook = readPlaybook();
      const payload = playbook[selected];
      if (!payload) return;
      hydrateFromPayload(payload);
      log(`Jugada cargada: ${selected}`);
    });
    deletePlayBtn?.addEventListener('click', () => {
      const selected = playbookSelect?.value || '';
      if (!selected) return;
      const playbook = readPlaybook();
      delete playbook[selected];
      writePlaybook(playbook);
      refreshPlaybookSelect();
      log(`Jugada eliminada: ${selected}`);
    });

    refreshPlaybookSelect();
    const existingDraft = readStorageJson(DRAFT_STORAGE_KEY, {});
    if (existingDraft && Array.isArray(existingDraft.tokens) && existingDraft.tokens.length) {
      hydrateFromPayload(existingDraft);
      log('Borrador ABP recuperado.');
    }
  });
})();
