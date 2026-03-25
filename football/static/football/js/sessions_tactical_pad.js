(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const PITCH_FORMAT_BY_PRESET = {
    full_pitch: '11v11_full',
    half_pitch: '11v11_half',
    attacking_third: 'specific_zone',
    seven_side: '7v7',
    futsal: '5v5',
    blank: 'specific_zone',
  };

  const PRESET_LABEL = {
    full_pitch: 'campo completo',
    half_pitch: 'medio campo',
    attacking_third: 'último tercio',
    seven_side: 'fútbol 7',
    futsal: 'futsal',
    blank: 'superficie libre',
  };

  const COLORS = {
    local: { fill: '#1d4ed8', stroke: '#eff6ff', text: '#ffffff' },
    rival: { fill: '#dc2626', stroke: '#fff7ed', text: '#ffffff' },
    goalkeeper: { fill: '#111827', stroke: '#facc15', text: '#facc15' },
  };

  const createSvgNode = (doc, tag, attrs) => {
    const node = doc.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  };

  const buildPitchSvg = (presetKey) => {
    const preset = String(presetKey || 'full_pitch').trim();
    const stageW = 1100;
    const stageH = 748;
    const doc = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg', null);
    const root = doc.documentElement;
    root.setAttribute('viewBox', `0 0 ${stageW} ${stageH}`);
    root.setAttribute('preserveAspectRatio', 'xMidYMid meet');

    const defs = createSvgNode(doc, 'defs');
    const gradient = createSvgNode(doc, 'linearGradient', { id: 'pitch-bg', x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '0%', 'stop-color': '#5f8f42' }));
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '100%', 'stop-color': '#557f3c' }));
    defs.appendChild(gradient);
    root.appendChild(defs);

    root.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: stageW, height: stageH, fill: '#071320' }));

    const stage = { x: 50, y: 50, width: 1000, height: 1000 * 68 / 105 };
    const scale = stage.width / 105;
    const line = '#f8fafc';
    const soft = 'rgba(248,250,252,0.66)';

    const drawFrame = (x, y, width, height, lineWidth = 4) => {
      root.appendChild(createSvgNode(doc, 'rect', {
        x,
        y,
        width,
        height,
        fill: 'url(#pitch-bg)',
        stroke: line,
        'stroke-width': lineWidth,
      }));
      const stripeW = width / 12;
      for (let index = 0; index < 12; index += 1) {
        root.appendChild(createSvgNode(doc, 'rect', {
          x: x + (index * stripeW),
          y,
          width: stripeW + 1,
          height,
          fill: index % 2 === 0 ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
          stroke: 'none',
        }));
      }
      root.appendChild(createSvgNode(doc, 'rect', {
        x,
        y,
        width,
        height,
        fill: 'transparent',
        stroke: line,
        'stroke-width': lineWidth,
      }));
    };

    const drawGoal = (x, centerY, goalDepth, goalHeight, side) => {
      const topY = centerY - (goalHeight / 2);
      const bottomY = centerY + (goalHeight / 2);
      const postX = side === 'left' ? x - goalDepth : x + goalDepth;
      root.appendChild(createSvgNode(doc, 'line', { x1: x, y1: topY, x2: postX, y2: topY, stroke: line, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'line', { x1: x, y1: bottomY, x2: postX, y2: bottomY, stroke: line, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'line', { x1: postX, y1: topY, x2: postX, y2: bottomY, stroke: line, 'stroke-width': 3 }));
    };

    const drawCornerArcs = (x, y, width, height, radius) => {
      const corners = [
        `M ${x} ${y + radius} A ${radius} ${radius} 0 0 1 ${x + radius} ${y}`,
        `M ${x + width - radius} ${y} A ${radius} ${radius} 0 0 1 ${x + width} ${y + radius}`,
        `M ${x} ${y + height - radius} A ${radius} ${radius} 0 0 0 ${x + radius} ${y + height}`,
        `M ${x + width - radius} ${y + height} A ${radius} ${radius} 0 0 0 ${x + width} ${y + height - radius}`,
      ];
      corners.forEach((path) => {
        root.appendChild(createSvgNode(doc, 'path', { d: path, fill: 'none', stroke: line, 'stroke-width': 2 }));
      });
    };

    const drawFullPitch = () => {
      drawFrame(stage.x, stage.y, stage.width, stage.height, 4);
      const centerX = stage.x + (stage.width / 2);
      const centerY = stage.y + (stage.height / 2);
      const centerRadius = 9.15 * scale;
      const penaltyDepth = 16.5 * scale;
      const goalAreaDepth = 5.5 * scale;
      const penaltyHeight = 40.32 * scale;
      const goalAreaHeight = 18.32 * scale;
      const goalHeight = 7.32 * scale;
      const goalDepth = 2.2 * scale;
      const spotDist = 11 * scale;
      const cornerRadius = 1 * scale;
      const arcRadius = 9.15 * scale;
      const arcDx = 5.5 * scale;
      const arcYOffset = Math.sqrt((9.15 * 9.15) - (5.5 * 5.5)) * scale;

      root.appendChild(createSvgNode(doc, 'line', { x1: centerX, y1: stage.y, x2: centerX, y2: stage.y + stage.height, stroke: line, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 4, fill: line }));
      root.appendChild(createSvgNode(doc, 'rect', { x: stage.x, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: stage.x, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: stage.x + stage.width - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: stage.x + stage.width - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: stage.x + spotDist, cy: centerY, r: 4, fill: line }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: stage.x + stage.width - spotDist, cy: centerY, r: 4, fill: line }));
      root.appendChild(createSvgNode(doc, 'path', { d: `M ${stage.x + penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 1 ${stage.x + penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'path', { d: `M ${stage.x + stage.width - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${stage.x + stage.width - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawGoal(stage.x, centerY, goalDepth, goalHeight, 'left');
      drawGoal(stage.x + stage.width, centerY, goalDepth, goalHeight, 'right');
      drawCornerArcs(stage.x, stage.y, stage.width, stage.height, cornerRadius);
    };

    const drawHalfPitch = () => {
      const width = 620;
      const height = width * 68 / 52.5;
      const x = (stageW - width) / 2;
      const y = (stageH - height) / 2;
      const localScale = width / 52.5;
      drawFrame(x, y, width, height, 4);
      const centerY = y + (height / 2);
      const penaltyDepth = 16.5 * localScale;
      const goalAreaDepth = 5.5 * localScale;
      const penaltyHeight = 40.32 * localScale;
      const goalAreaHeight = 18.32 * localScale;
      const goalHeight = 7.32 * localScale;
      const goalDepth = 2.2 * localScale;
      const spotDist = 11 * localScale;
      const arcRadius = 9.15 * localScale;
      const arcDx = 5.5 * localScale;
      const arcYOffset = Math.sqrt((9.15 * 9.15) - (5.5 * 5.5)) * localScale;
      const centerRadius = 9.15 * localScale;
      const rightX = x + width;

      root.appendChild(createSvgNode(doc, 'line', { x1: x, y1: y, x2: x, y2: y + height, stroke: line, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: x, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: rightX - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: rightX - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: rightX - spotDist, cy: centerY, r: 4, fill: line }));
      root.appendChild(createSvgNode(doc, 'path', { d: `M ${rightX - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${rightX - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawGoal(rightX, centerY, goalDepth, goalHeight, 'right');
    };

    const drawAttackingThird = () => {
      const width = 420;
      const height = width * 68 / 35;
      const x = (stageW - width) / 2;
      const y = (stageH - height) / 2;
      const localScale = width / 35;
      drawFrame(x, y, width, height, 4);
      const centerY = y + (height / 2);
      const penaltyDepth = 16.5 * localScale;
      const goalAreaDepth = 5.5 * localScale;
      const penaltyHeight = 40.32 * localScale;
      const goalAreaHeight = 18.32 * localScale;
      const goalHeight = 7.32 * localScale;
      const goalDepth = 2.2 * localScale;
      const spotDist = 11 * localScale;
      const arcRadius = 9.15 * localScale;
      const arcYOffset = Math.sqrt((9.15 * 9.15) - (5.5 * 5.5)) * localScale;
      const rightX = x + width;

      root.appendChild(createSvgNode(doc, 'line', { x1: x, y1: y, x2: x, y2: y + height, stroke: soft, 'stroke-width': 2 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: rightX - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'rect', { x: rightX - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: rightX - spotDist, cy: centerY, r: 4, fill: line }));
      root.appendChild(createSvgNode(doc, 'path', { d: `M ${rightX - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${rightX - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawGoal(rightX, centerY, goalDepth, goalHeight, 'right');
    };

    const drawMiniGame = (metersW, metersH, penaltyDepthMeters, penaltyHeightMeters, goalAreaDepthMeters, goalAreaHeightMeters, goalHeightMeters) => {
      const width = 920;
      const height = width * metersH / metersW;
      const x = (stageW - width) / 2;
      const y = (stageH - height) / 2;
      const localScale = width / metersW;
      drawFrame(x, y, width, height, 4);
      const centerX = x + (width / 2);
      const centerY = y + (height / 2);
      const centerRadius = Math.min(9.15, Math.min(metersW, metersH) / 7.5) * localScale;
      const cornerRadius = Math.min(1, Math.min(metersW, metersH) / 38) * localScale;
      const goalDepth = 2 * localScale;

      root.appendChild(createSvgNode(doc, 'line', { x1: centerX, y1: y, x2: centerX, y2: y + height, stroke: line, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      root.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 4, fill: line }));
      if (penaltyDepthMeters > 0 && penaltyHeightMeters > 0) {
        root.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - ((penaltyHeightMeters * localScale) / 2), width: penaltyDepthMeters * localScale, height: penaltyHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + width - (penaltyDepthMeters * localScale), y: centerY - ((penaltyHeightMeters * localScale) / 2), width: penaltyDepthMeters * localScale, height: penaltyHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      }
      if (goalAreaDepthMeters > 0 && goalAreaHeightMeters > 0) {
        root.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - ((goalAreaHeightMeters * localScale) / 2), width: goalAreaDepthMeters * localScale, height: goalAreaHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + width - (goalAreaDepthMeters * localScale), y: centerY - ((goalAreaHeightMeters * localScale) / 2), width: goalAreaDepthMeters * localScale, height: goalAreaHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      }
      drawGoal(x, centerY, goalDepth, goalHeightMeters * localScale, 'left');
      drawGoal(x + width, centerY, goalDepth, goalHeightMeters * localScale, 'right');
      drawCornerArcs(x, y, width, height, cornerRadius);
    };

    if (preset === 'half_pitch') drawHalfPitch();
    else if (preset === 'attacking_third') drawAttackingThird();
    else if (preset === 'seven_side') drawMiniGame(65, 45, 12, 24, 4, 12, 6);
    else if (preset === 'futsal') drawMiniGame(40, 20, 6, 16, 0, 0, 3);
    else drawFullPitch();

    return new XMLSerializer().serializeToString(doc);
  };

  window.initSessionsTacticalPad = function initSessionsTacticalPad() {
    const form = document.getElementById('task-builder-form');
    const canvasEl = document.getElementById('create-task-canvas');
    const stage = document.getElementById('task-pitch-stage');
    const svgSurface = document.getElementById('task-pitch-surface');
    const presetSelect = document.getElementById('draw-task-preset');
    const pitchFormatInput = document.getElementById('draw-task-pitch-format');
    const stateInput = document.getElementById('draw-canvas-state');
    const widthInput = document.getElementById('draw-canvas-width');
    const heightInput = document.getElementById('draw-canvas-height');
    const previewInput = document.getElementById('draw-canvas-preview-data');
    const playerCountInput = form.querySelector('[name="draw_task_player_count"]');
    const legacyPlayersInput = form.querySelector('[name="draw_task_players"]');
    const statusEl = document.getElementById('task-builder-status');
    const toolStrip = document.getElementById('task-basic-tools');
    const playerBank = document.getElementById('task-player-bank');
    const presetButtons = Array.from(document.querySelectorAll('[data-preset]'));
    if (!window.fabric || !form || !canvasEl || !stage || !svgSurface || !presetSelect) return;

    const setStatus = (message, isError = false) => {
      if (!statusEl) return;
      statusEl.textContent = message;
      statusEl.style.color = isError ? '#fca5a5' : 'rgba(226,232,240,0.72)';
    };

    let players = [];
    try {
      players = JSON.parse(document.getElementById('tpad-players-catalog')?.textContent || '[]');
    } catch (error) {
      players = [];
    }
    if (!Array.isArray(players)) players = [];

    const canvas = new fabric.Canvas(canvasEl, {
      preserveObjectStacking: true,
      selection: true,
    });

    let history = [];
    let pendingFactory = null;

    const fitCanvas = () => {
      const width = Math.max(320, Math.round(stage.clientWidth || 960));
      const height = Math.max(220, Math.round(stage.clientHeight || 640));
      canvas.setDimensions({ width, height });
      canvas.calcOffset();
      canvas.requestRenderAll();
    };

    const pushHistory = () => {
      const snapshot = JSON.stringify(serializeState());
      if (!history.length || history[history.length - 1] !== snapshot) history.push(snapshot);
      if (history.length > 40) history = history.slice(history.length - 40);
    };

    const setPreset = (presetValue) => {
      const preset = safeText(presetValue, 'full_pitch');
      presetSelect.value = preset;
      if (pitchFormatInput && PITCH_FORMAT_BY_PRESET[preset]) pitchFormatInput.value = PITCH_FORMAT_BY_PRESET[preset];
      presetButtons.forEach((button) => button.classList.toggle('is-active', safeText(button.dataset.preset) === preset));
      svgSurface.innerHTML = buildPitchSvg(preset);
      setStatus(`Superficie preparada: ${PRESET_LABEL[preset] || 'campo'}.`);
    };

    const serializeState = () => {
      const json = canvas.toJSON(['data']);
      json.objects = (json.objects || []).filter((item) => !(item?.data?.base));
      return json;
    };

    const sanitizeLoadedState = (raw) => {
      if (!raw || typeof raw !== 'object') return { version: '5.3.0', objects: [] };
      const objects = Array.isArray(raw.objects) ? raw.objects.filter((item) => !(item?.data?.base) && !(item?.selectable === false && item?.evented === false)) : [];
      return { version: raw.version || '5.3.0', objects };
    };

    const objectAtPointer = (factory, pointer) => {
      const left = clamp(pointer.x || 0, 24, canvas.getWidth() - 24);
      const top = clamp(pointer.y || 0, 24, canvas.getHeight() - 24);
      return factory(left, top);
    };

    const addObject = (object) => {
      if (!object) return;
      canvas.add(object);
      canvas.setActiveObject(object);
      canvas.requestRenderAll();
      pushHistory();
    };

    const playerTokenFactory = (kind, player) => (left, top) => {
      const palette = kind === 'goalkeeper_local'
        ? COLORS.goalkeeper
        : kind === 'player_rival'
          ? COLORS.rival
          : COLORS.local;
      const label = player?.number ? String(player.number).slice(0, 2) : (kind === 'goalkeeper_local' ? 'GK' : 'J');
      const initials = safeText(player?.name, kind === 'player_rival' ? 'Rival' : 'Jugador')
        .split(/\s+/)
        .map((piece) => piece[0] || '')
        .join('')
        .slice(0, 2)
        .toUpperCase() || label;
      const circle = new fabric.Circle({
        radius: kind === 'goalkeeper_local' ? 24 : 21,
        fill: palette.fill,
        stroke: palette.stroke,
        strokeWidth: 3,
        shadow: 'rgba(15,23,42,0.35) 0 4px 14px',
        originX: 'center',
        originY: 'center',
        left: 0,
        top: 0,
      });
      const text = new fabric.Text(initials, {
        originX: 'center',
        originY: 'center',
        left: 0,
        top: 0,
        fontSize: 12,
        fontWeight: '700',
        fill: palette.text,
      });
      const badge = new fabric.Text(label, {
        originX: 'center',
        originY: 'center',
        left: 0,
        top: 26,
        fontSize: 10,
        fontWeight: '700',
        fill: '#ffffff',
        backgroundColor: 'rgba(15,23,42,0.92)',
      });
      return new fabric.Group([circle, text, badge], {
        left,
        top,
        originX: 'center',
        originY: 'center',
        data: { kind: 'token', playerId: player?.id || '', playerName: safeText(player?.name, '') },
      });
    };

    const simpleFactory = (kind) => {
      if (kind === 'ball') {
        return (left, top) => new fabric.Circle({
          left, top, originX: 'center', originY: 'center',
          radius: 10, fill: '#ffffff', stroke: '#0f172a', strokeWidth: 2,
          data: { kind: 'ball' },
        });
      }
      if (kind === 'cone') {
        return (left, top) => new fabric.Triangle({
          left, top, originX: 'center', originY: 'center',
          width: 24, height: 24, fill: '#f97316', stroke: '#7c2d12', strokeWidth: 1.6,
          data: { kind: 'cone' },
        });
      }
      if (kind === 'zone') {
        return (left, top) => new fabric.Rect({
          left, top, originX: 'center', originY: 'center',
          width: 130, height: 84, fill: 'rgba(34,211,238,0.16)', stroke: '#22d3ee', strokeWidth: 3,
          rx: 12, ry: 12, data: { kind: 'zone' },
        });
      }
      if (kind === 'line') {
        return (left, top) => new fabric.Line([-55, 0, 55, 0], {
          left, top, originX: 'center', originY: 'center',
          stroke: '#f8fafc', strokeWidth: 3, data: { kind: 'line' },
        });
      }
      if (kind === 'arrow') {
        return (left, top) => new fabric.Group([
          new fabric.Line([-50, 0, 40, 0], { stroke: '#22d3ee', strokeWidth: 4, originX: 'center', originY: 'center' }),
          new fabric.Triangle({ left: 52, top: 0, width: 18, height: 18, angle: 90, fill: '#22d3ee', originX: 'center', originY: 'center' }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'arrow' } });
      }
      if (kind === 'text') {
        return (left, top) => new fabric.IText('Texto', {
          left, top, originX: 'center', originY: 'center',
          fontSize: 22, fill: '#ffffff', fontWeight: '700', data: { kind: 'text' },
        });
      }
      return null;
    };

    const activateFactory = (factory, label) => {
      pendingFactory = factory;
      Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
      Array.from(playerBank?.querySelectorAll('button') || []).forEach((button) => button.classList.remove('is-active'));
      setStatus(`Haz clic en el campo para colocar ${label}.`);
    };

    const restoreState = () => {
      let parsed = { version: '5.3.0', objects: [] };
      try {
        parsed = sanitizeLoadedState(JSON.parse(stateInput?.value || '{"version":"5.3.0","objects":[]}'));
      } catch (error) {
        parsed = { version: '5.3.0', objects: [] };
      }
      canvas.loadFromJSON(parsed, () => {
        canvas.requestRenderAll();
        pushHistory();
      });
    };

    const renderPlayerBank = () => {
      if (!playerBank) return;
      playerBank.innerHTML = '';
      players.slice(0, 36).forEach((player) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `${player.number ? `#${player.number} · ` : ''}${safeText(player.name, 'Jugador')}`;
        button.addEventListener('click', () => {
          Array.from(playerBank.querySelectorAll('button')).forEach((item) => item.classList.remove('is-active'));
          button.classList.add('is-active');
          activateFactory(playerTokenFactory('player_local', player), safeText(player.name, 'el jugador'));
        });
        playerBank.appendChild(button);
      });
    };

    const buildPreviewData = () => new Promise((resolve) => {
      const output = document.createElement('canvas');
      output.width = Math.round(canvas.getWidth());
      output.height = Math.round(canvas.getHeight());
      const context = output.getContext('2d');
      if (!context) {
        resolve('');
        return;
      }
      const svgMarkup = new XMLSerializer().serializeToString(svgSurface);
      const blob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' });
      const blobUrl = URL.createObjectURL(blob);
      const image = new Image();
      image.onload = () => {
        context.drawImage(image, 0, 0, output.width, output.height);
        context.drawImage(canvas.lowerCanvasEl, 0, 0, output.width, output.height);
        URL.revokeObjectURL(blobUrl);
        resolve(output.toDataURL('image/png', 0.92));
      };
      image.onerror = () => {
        URL.revokeObjectURL(blobUrl);
        resolve(canvas.lowerCanvasEl.toDataURL('image/png', 0.92));
      };
      image.src = blobUrl;
    });

    fitCanvas();
    setPreset(presetSelect.value || 'full_pitch');
    restoreState();
    renderPlayerBank();

    canvas.on('object:modified', pushHistory);
    canvas.on('object:added', () => {
      if (!canvas.__loading) pushHistory();
    });
    canvas.on('mouse:down', (event) => {
      if (!pendingFactory || event.target) return;
      const pointer = canvas.getPointer(event.e);
      addObject(objectAtPointer(pendingFactory, pointer));
      pendingFactory = null;
      Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
      Array.from(playerBank?.querySelectorAll('button') || []).forEach((button) => button.classList.remove('is-active'));
      setStatus('Elemento colocado.');
    });

    toolStrip?.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (!button) return;
      const action = safeText(button.dataset.action);
      const add = safeText(button.dataset.add);
      if (action === 'select') {
        pendingFactory = null;
        Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
        Array.from(playerBank?.querySelectorAll('button') || []).forEach((item) => item.classList.remove('is-active'));
        setStatus('Modo selección activo.');
        return;
      }
      if (action === 'undo') {
        if (history.length <= 1) return;
        history.pop();
        const previous = history[history.length - 1];
        canvas.loadFromJSON(JSON.parse(previous), () => canvas.requestRenderAll());
        setStatus('Último cambio deshecho.');
        return;
      }
      if (action === 'delete') {
        const active = canvas.getActiveObject();
        if (!active) return;
        canvas.remove(active);
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        pushHistory();
        setStatus('Elemento eliminado.');
        return;
      }
      if (action === 'clear') {
        canvas.getObjects().slice().forEach((item) => canvas.remove(item));
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        pushHistory();
        setStatus('Pizarra limpiada.');
        return;
      }
      if (!add) return;
      Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
      button.classList.add('is-active');
      if (add === 'player_local') activateFactory(playerTokenFactory('player_local', null), 'un jugador local');
      else if (add === 'player_rival') activateFactory(playerTokenFactory('player_rival', null), 'un jugador rival');
      else if (add === 'goalkeeper_local') activateFactory(playerTokenFactory('goalkeeper_local', null), 'un portero');
      else activateFactory(simpleFactory(add), PRESET_LABEL[add] || add);
    });

    presetButtons.forEach((button) => {
      button.addEventListener('click', () => setPreset(button.dataset.preset || 'full_pitch'));
    });
    presetSelect.addEventListener('change', () => setPreset(presetSelect.value || 'full_pitch'));

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        fitCanvas();
        setPreset(presetSelect.value || 'full_pitch');
      }, 140);
    });

    form.addEventListener('submit', async (event) => {
      if (form.dataset.previewReady === '1') {
        form.dataset.previewReady = '';
        return;
      }
      event.preventDefault();
      if (legacyPlayersInput && playerCountInput) legacyPlayersInput.value = playerCountInput.value || '';
      if (stateInput) stateInput.value = JSON.stringify(serializeState());
      if (widthInput) widthInput.value = String(Math.round(canvas.getWidth()));
      if (heightInput) heightInput.value = String(Math.round(canvas.getHeight()));
      if (previewInput) previewInput.value = await buildPreviewData();
      form.dataset.previewReady = '1';
      form.requestSubmit();
    });
  };
})();
