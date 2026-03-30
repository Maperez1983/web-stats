(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const runWhenIdle = (fn, timeout = 900) => {
    if (typeof window === 'undefined') return fn();
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(() => fn(), { timeout });
      return;
    }
    window.setTimeout(() => fn(), Math.min(350, timeout));
  };
  const hexToRgb = (hex) => {
    const cleaned = String(hex || '').trim().replace('#', '');
    if (cleaned.length !== 3 && cleaned.length !== 6) return null;
    const normalized = cleaned.length === 3 ? cleaned.split('').map((char) => char + char).join('') : cleaned;
    const value = Number.parseInt(normalized, 16);
    if (Number.isNaN(value)) return null;
    return {
      r: (value >> 16) & 255,
      g: (value >> 8) & 255,
      b: value & 255,
    };
  };
  const rgbToHex = (r, g, b) => `#${[r, g, b].map((channel) => clamp(Number(channel) || 0, 0, 255).toString(16).padStart(2, '0')).join('')}`;
  const rgbaFromHex = (hex, alpha = 1) => {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    return `rgba(${rgb.r},${rgb.g},${rgb.b},${alpha})`;
  };
  const parseColorToHex = (value, fallback = '#22d3ee') => {
    const color = String(value || '').trim();
    if (!color) return fallback;
    if (color.startsWith('#')) {
      const rgb = hexToRgb(color);
      return rgb ? rgbToHex(rgb.r, rgb.g, rgb.b) : fallback;
    }
    const rgbaMatch = color.match(/rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (rgbaMatch) {
      return rgbToHex(rgbaMatch[1], rgbaMatch[2], rgbaMatch[3]);
    }
    return fallback;
  };
  const darkenHex = (hex, factor = 0.35) => {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    const f = clamp(Number(factor) || 0.35, 0, 0.95);
    return rgbToHex(
      Math.round(rgb.r * (1 - f)),
      Math.round(rgb.g * (1 - f)),
      Math.round(rgb.b * (1 - f)),
    );
  };
  const isLightHex = (hex) => {
    const rgb = hexToRgb(hex);
    if (!rgb) return false;
    // Perceived luminance.
    const luma = (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255;
    return luma >= 0.68;
  };
  const contrastTextForFill = (hex) => (isLightHex(hex) ? '#0b1220' : '#ffffff');

  const PITCH_FORMAT_BY_PRESET = {
    full_pitch: '11v11_full',
    half_pitch: '11v11_half',
    attacking_third: 'specific_zone',
    middle_third: 'specific_zone',
    defensive_third: 'specific_zone',
    seven_side: '7v7',
    seven_side_single: '7v7',
    futsal: '5v5',
    blank: 'specific_zone',
  };

  const PRESET_LABEL = {
    full_pitch: 'campo completo',
    half_pitch: 'medio campo',
    attacking_third: 'último tercio',
    middle_third: 'tercio medio',
    defensive_third: 'primer tercio',
    seven_side: 'fútbol 7 doble',
    seven_side_single: 'fútbol 7 individual',
    futsal: 'futsal',
    blank: 'superficie libre',
  };
  const ORIENTATION_LABEL = {
    landscape: 'horizontal',
    portrait: 'vertical',
  };

  const COLORS = {
    local: { fill: '#1d4ed8', stroke: '#eff6ff', text: '#ffffff' },
    rival: { fill: '#dc2626', stroke: '#fff7ed', text: '#ffffff' },
    goalkeeper: { fill: '#111827', stroke: '#facc15', text: '#facc15' },
    goalkeeper_blue: { fill: '#1d4ed8', stroke: '#eff6ff', text: '#ffffff' },
  };
  const RESOURCE_LABELS = {
    ball: 'el balón',
    cone: 'un cono',
    zone: 'una zona',
    text: 'un texto',
    goal: 'una portería',
    token: 'un jugador',
    line: 'una línea',
    arrow: 'una flecha',
    line_solid: 'una línea continua',
    line_dash: 'una línea discontinua',
    line_dot: 'una línea de puntos',
    line_double: 'una línea doble',
    arrow_solid: 'una flecha continua',
    arrow_dash: 'una flecha discontinua',
    arrow_dot: 'una flecha de puntos',
    arrow_curve: 'una flecha curva',
    shape_circle: 'un círculo',
    shape_square: 'un cuadrado',
    shape_rect: 'un rectángulo',
    shape_triangle: 'un triángulo',
    shape_diamond: 'un rombo',
    emoji_ball: 'un balón emoji',
    emoji_cone: 'un cono emoji',
    emoji_pole: 'una pica emoji',
    emoji_ladder: 'una escalera emoji',
    emoji_ring: 'un aro emoji',
    emoji_hurdle: 'una valla emoji',
    emoji_bib: 'un peto emoji',
    emoji_mannequin: 'un maniquí emoji',
    emoji_wall: 'un muro emoji',
    emoji_goal: 'una portería emoji',
    emoji_mini_goal: 'una mini portería emoji',
    emoji_whistle: 'un silbato emoji',
    emoji_stopwatch: 'un cronómetro emoji',
  };
  const EMOJI_LIBRARY = {
    emoji_ball: '⚽',
    emoji_cone: '🔺',
    emoji_pole: '📍',
    emoji_ladder: '🪜',
    emoji_ring: '⭕',
    emoji_hurdle: '🚧',
    emoji_bib: '🦺',
    emoji_mannequin: '🧍',
    emoji_wall: '🧱',
    emoji_goal: '🥅',
    emoji_mini_goal: '🥅',
    emoji_whistle: '📣',
    emoji_stopwatch: '⏱️',
  };

  const createSvgNode = (doc, tag, attrs) => {
    const node = doc.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  };
  const shortPlayerName = (name) => {
    const raw = safeText(name, 'Jugador');
    if (raw.length <= 16) return raw;
    const parts = raw.split(/\s+/).filter(Boolean);
    if (parts.length > 1) {
      const compact = `${parts[0]} ${parts[parts.length - 1]}`;
      if (compact.length <= 16) return compact;
    }
    return `${raw.slice(0, 15).trim()}…`;
  };

  const buildPitchSvg = (presetKey, orientationKey = 'landscape') => {
    const preset = String(presetKey || 'full_pitch').trim();
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const stageW = orientation === 'portrait' ? 748 : 1100;
    const stageH = orientation === 'portrait' ? 1100 : 748;
    const drawW = 1100;
    const drawH = 748;
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

    // El fondo lo da el contenedor del editor. Aquí dejamos el SVG sin "marco negro"
    // para que el campo ocupe el máximo espacio posible (especialmente en vertical).
    root.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: stageW, height: stageH, fill: 'transparent' }));
    const drawRoot = createSvgNode(doc, 'g');
    if (orientation === 'portrait') {
      drawRoot.setAttribute('transform', `translate(${stageW} 0) rotate(90)`);
    }
    root.appendChild(drawRoot);

    const createStage = (orientation, desiredAspect = 105 / 68) => {
      // En vertical, el grupo se rota 90 grados: el sistema de coordenadas "dibuja"
      // sobre un lienzo efectivo de (stageH x stageW). Mantenemos proporción real 105x68.
      // Deja margen suficiente para que el trazo del borde no se recorte en miniaturas / contenedores con overflow hidden.
      const margin = 18;
      const portrait = orientation === 'portrait';
      const effectiveW = portrait ? stageH : stageW;
      const effectiveH = portrait ? stageW : stageH;
      const availableWidth = effectiveW - margin * 2;
      const availableHeight = effectiveH - margin * 2;

      let width = availableWidth;
      let height = width / desiredAspect;
      if (height > availableHeight) {
        height = availableHeight;
        width = height * desiredAspect;
      }
      const offsetX = (effectiveW - width) / 2;
      const offsetY = (effectiveH - height) / 2;
      return { x: offsetX, y: offsetY, width, height };
    };
    let stage = createStage(orientation);
    const scale = stage.width / 105;
    const line = '#f8fafc';
    const soft = 'rgba(248,250,252,0.66)';

    const drawFrame = (x, y, width, height, lineWidth = 4) => {
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
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
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: x + (index * stripeW),
          y,
          width: stripeW + 1,
          height,
          fill: index % 2 === 0 ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
          stroke: 'none',
        }));
      }
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
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
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: topY, x2: postX, y2: topY, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: bottomY, x2: postX, y2: bottomY, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: postX, y1: topY, x2: postX, y2: bottomY, stroke: line, 'stroke-width': 3 }));
    };

    const drawCornerArcs = (x, y, width, height, radius) => {
      const corners = [
        `M ${x} ${y + radius} A ${radius} ${radius} 0 0 1 ${x + radius} ${y}`,
        `M ${x + width - radius} ${y} A ${radius} ${radius} 0 0 1 ${x + width} ${y + radius}`,
        `M ${x} ${y + height - radius} A ${radius} ${radius} 0 0 0 ${x + radius} ${y + height}`,
        `M ${x + width - radius} ${y + height} A ${radius} ${radius} 0 0 0 ${x + width} ${y + height - radius}`,
      ];
      corners.forEach((path) => {
        drawRoot.appendChild(createSvgNode(doc, 'path', { d: path, fill: 'none', stroke: line, 'stroke-width': 2 }));
      });
    };

	    const drawSevenSideOverlay = (fieldX, fieldY, fieldWidth, fieldHeight) => {
	      const halfWidth = fieldWidth / 2;
	      const sevenHeight = fieldHeight * 0.84;
	      const sevenWidth = sevenHeight * 45 / 65;
	      const insetY = (fieldHeight - sevenHeight) / 2;
	      const leftSevenX = fieldX + (halfWidth - sevenWidth) / 2;
	      const rightSevenX = fieldX + halfWidth + ((halfWidth - sevenWidth) / 2);
	      const sevenY = fieldY + insetY;
	      const metersH = 65;
	      const scaleLocal = sevenHeight / metersH;
	      const areaDepth = 13 * scaleLocal;
	      const areaWidth = 26 * scaleLocal;
	      const goalAreaDepth = 4.5 * scaleLocal;
	      const goalAreaWidth = 12 * scaleLocal;
	      const goalHeight = 6 * scaleLocal;
	      const goalDepth = 1.8 * scaleLocal;
	      const spotDist = 8 * scaleLocal;
	      const offsideColor = '#facc15';
	      const drawOne = (x) => {
	        drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: sevenY, width: sevenWidth, height: sevenHeight, fill: 'rgba(34,211,238,0.08)', stroke: '#67e8f9', 'stroke-width': 2.2, 'stroke-dasharray': '8 6' }));
	        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: sevenY + (sevenHeight / 2), x2: x + sevenWidth, y2: sevenY + (sevenHeight / 2), stroke: '#67e8f9', 'stroke-width': 2 }));
	        // Fuera de juego (Fútbol 7): líneas a 13m de cada línea de fondo.
	        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: sevenY + areaDepth, x2: x + sevenWidth, y2: sevenY + areaDepth, stroke: offsideColor, 'stroke-width': 3, 'stroke-opacity': 0.92 }));
	        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: sevenY + sevenHeight - areaDepth, x2: x + sevenWidth, y2: sevenY + sevenHeight - areaDepth, stroke: offsideColor, 'stroke-width': 3, 'stroke-opacity': 0.92 }));
	        drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + (sevenHeight / 2), r: 5.5 * scaleLocal, fill: 'none', stroke: 'rgba(103,232,249,0.66)', 'stroke-width': 2 }));
	        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - areaWidth) / 2, y: sevenY, width: areaWidth, height: areaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
	        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - areaWidth) / 2, y: sevenY + sevenHeight - areaDepth, width: areaWidth, height: areaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - goalAreaWidth) / 2, y: sevenY, width: goalAreaWidth, height: goalAreaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - goalAreaWidth) / 2, y: sevenY + sevenHeight - goalAreaDepth, width: goalAreaWidth, height: goalAreaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + spotDist, r: 3.5, fill: '#67e8f9' }));
        drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + sevenHeight - spotDist, r: 3.5, fill: '#67e8f9' }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY, x2: x + ((sevenWidth - goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth + goalHeight) / 2), y1: sevenY, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY - goalDepth, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY + sevenHeight, x2: x + ((sevenWidth - goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth + goalHeight) / 2), y1: sevenY + sevenHeight, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY + sevenHeight + goalDepth, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
      };
      drawOne(leftSevenX);
      drawOne(rightSevenX);
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

      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: centerX, y1: stage.y, x2: centerX, y2: stage.y + stage.height, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 4, fill: line }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: stage.x, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: stage.x, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: stage.x + stage.width - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: stage.x + stage.width - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: stage.x + spotDist, cy: centerY, r: 4, fill: line }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: stage.x + stage.width - spotDist, cy: centerY, r: 4, fill: line }));
      drawRoot.appendChild(createSvgNode(doc, 'path', { d: `M ${stage.x + penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 1 ${stage.x + penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'path', { d: `M ${stage.x + stage.width - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${stage.x + stage.width - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawGoal(stage.x, centerY, goalDepth, goalHeight, 'left');
      drawGoal(stage.x + stage.width, centerY, goalDepth, goalHeight, 'right');
      drawCornerArcs(stage.x, stage.y, stage.width, stage.height, cornerRadius);
    };

    const drawHalfPitch = () => {
      const metersW = 52.5;
      const metersH = 68;
      const pitch = createStage(orientation, metersW / metersH);
      const x = pitch.x;
      const y = pitch.y;
      const width = pitch.width;
      const height = pitch.height;
      const localScale = width / metersW;
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
      const centerRadius = 9.15 * localScale;
      const rightX = x + width;

      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: y, x2: x, y2: y + height, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: rightX - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: rightX - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: rightX - spotDist, cy: centerY, r: 4, fill: line }));
      drawRoot.appendChild(createSvgNode(doc, 'path', { d: `M ${rightX - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${rightX - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawGoal(rightX, centerY, goalDepth, goalHeight, 'right');
    };

    const drawThirdZone = (side = 'attacking') => {
      const metersW = 35;
      const metersH = 68;
      const pitch = createStage(orientation, metersW / metersH);
      const x = pitch.x;
      const y = pitch.y;
      const width = pitch.width;
      const height = pitch.height;
      const localScale = width / metersW;
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
      const isRight = side !== 'defensive';
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: isRight ? x : rightX, y1: y, x2: isRight ? x : rightX, y2: y + height, stroke: soft, 'stroke-width': 2 }));
      if (isRight) {
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: rightX - penaltyDepth, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: rightX - goalAreaDepth, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: rightX - spotDist, cy: centerY, r: 4, fill: line }));
        drawRoot.appendChild(createSvgNode(doc, 'path', { d: `M ${rightX - penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 0 ${rightX - penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawGoal(rightX, centerY, goalDepth, goalHeight, 'right');
      } else {
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - (penaltyHeight / 2), width: penaltyDepth, height: penaltyHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - (goalAreaHeight / 2), width: goalAreaDepth, height: goalAreaHeight, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + spotDist, cy: centerY, r: 4, fill: line }));
        drawRoot.appendChild(createSvgNode(doc, 'path', { d: `M ${x + penaltyDepth} ${centerY - arcYOffset} A ${arcRadius} ${arcRadius} 0 0 1 ${x + penaltyDepth} ${centerY + arcYOffset}`, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawGoal(x, centerY, goalDepth, goalHeight, 'left');
      }
    };

    const drawMiddleThird = () => {
      const metersW = 35;
      const metersH = 68;
      const pitch = createStage(orientation, metersW / metersH);
      const x = pitch.x;
      const y = pitch.y;
      const width = pitch.width;
      const height = pitch.height;
      const localScale = width / metersW;
      drawFrame(x, y, width, height, 4);
      const centerX = x + (width / 2);
      const centerY = y + (height / 2);
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x, y1: y, x2: x, y2: y + height, stroke: soft, 'stroke-width': 2 }));
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + width, y1: y, x2: x + width, y2: y + height, stroke: soft, 'stroke-width': 2 }));
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: centerX, y1: y, x2: centerX, y2: y + height, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 9.15 * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 4, fill: line }));
    };

    const drawMiniGame = (metersW, metersH, penaltyDepthMeters, penaltyHeightMeters, goalAreaDepthMeters, goalAreaHeightMeters, goalHeightMeters, options = {}) => {
      const pitch = createStage(orientation, metersW / metersH);
      const x = pitch.x;
      const y = pitch.y;
      const width = pitch.width;
      const height = pitch.height;
      const localScale = width / metersW;
      drawFrame(x, y, width, height, 4);
      const centerX = x + (width / 2);
      const centerY = y + (height / 2);
      const centerRadius = Math.min(9.15, Math.min(metersW, metersH) / 7.5) * localScale;
      const cornerRadius = Math.min(1, Math.min(metersW, metersH) / 38) * localScale;
      const goalDepth = 2 * localScale;
      const offsideColor = options?.offsideColor || '#facc15';
      const offsideDistance = Number(options?.offsideLineFromGoalMeters);

      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: centerX, y1: y, x2: centerX, y2: y + height, stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: centerRadius, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: centerX, cy: centerY, r: 4, fill: line }));
      if (!Number.isNaN(offsideDistance) && offsideDistance > 0 && offsideDistance < (metersW / 2)) {
        const leftOffsideX = x + (offsideDistance * localScale);
        const rightOffsideX = x + width - (offsideDistance * localScale);
        drawRoot.appendChild(createSvgNode(doc, 'line', {
          x1: leftOffsideX, y1: y, x2: leftOffsideX, y2: y + height,
          stroke: offsideColor, 'stroke-width': 3, 'stroke-opacity': 0.92,
        }));
        drawRoot.appendChild(createSvgNode(doc, 'line', {
          x1: rightOffsideX, y1: y, x2: rightOffsideX, y2: y + height,
          stroke: offsideColor, 'stroke-width': 3, 'stroke-opacity': 0.92,
        }));
      }
      if (penaltyDepthMeters > 0 && penaltyHeightMeters > 0) {
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - ((penaltyHeightMeters * localScale) / 2), width: penaltyDepthMeters * localScale, height: penaltyHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + width - (penaltyDepthMeters * localScale), y: centerY - ((penaltyHeightMeters * localScale) / 2), width: penaltyDepthMeters * localScale, height: penaltyHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      }
      if (goalAreaDepthMeters > 0 && goalAreaHeightMeters > 0) {
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: centerY - ((goalAreaHeightMeters * localScale) / 2), width: goalAreaDepthMeters * localScale, height: goalAreaHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + width - (goalAreaDepthMeters * localScale), y: centerY - ((goalAreaHeightMeters * localScale) / 2), width: goalAreaDepthMeters * localScale, height: goalAreaHeightMeters * localScale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      }
      drawGoal(x, centerY, goalDepth, goalHeightMeters * localScale, 'left');
      drawGoal(x + width, centerY, goalDepth, goalHeightMeters * localScale, 'right');
      drawCornerArcs(x, y, width, height, cornerRadius);
    };

    if (preset === 'half_pitch') drawHalfPitch();
    else if (preset === 'attacking_third') drawThirdZone('attacking');
    else if (preset === 'defensive_third') drawThirdZone('defensive');
    else if (preset === 'middle_third') drawMiddleThird();
    else if (preset === 'seven_side') {
      drawFullPitch();
      drawSevenSideOverlay(stage.x, stage.y, stage.width, stage.height);
    }
    else if (preset === 'seven_side_single') drawMiniGame(65, 45, 13, 26, 4.5, 12, 6, { offsideLineFromGoalMeters: 13, offsideColor: '#facc15' });
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
    const surfacePicker = document.getElementById('surface-picker');
    const surfaceTrigger = document.getElementById('surface-trigger');
    const surfaceMenu = document.getElementById('surface-menu');
    const surfaceTriggerLabel = document.getElementById('surface-trigger-label');
    const orientationInput = document.getElementById('draw-task-pitch-orientation');
    const orientationToggle = document.getElementById('pitch-orientation-toggle');
    const orientationLabel = document.getElementById('pitch-orientation-label');
    const viewportEl = document.getElementById('task-pitch-viewport');
    const zoomInput = document.getElementById('draw-task-pitch-zoom');
    const zoomOutButton = document.getElementById('pitch-zoom-out');
    const zoomInButton = document.getElementById('pitch-zoom-in');
    const zoomResetButton = document.getElementById('pitch-zoom-reset');
    const zoomLabel = document.getElementById('pitch-zoom-label');
	    const pitchFormatInput = document.getElementById('draw-task-pitch-format');
    const stateInput = document.getElementById('draw-canvas-state');
    const widthInput = document.getElementById('draw-canvas-width');
    const heightInput = document.getElementById('draw-canvas-height');
    const previewInput = document.getElementById('draw-canvas-preview-data');
    const livePreviewImg = document.getElementById('task-live-preview');
    const livePreviewPlaceholder = document.getElementById('task-live-preview-placeholder');
    const playerCountInput = form.querySelector('[name="draw_task_player_count"]');
    const legacyPlayersInput = form.querySelector('[name="draw_task_players"]');
	    const statusEl = document.getElementById('task-builder-status');
	    const toolStrip = document.getElementById('task-basic-tools');
	    const playerBank = document.getElementById('task-player-bank');
	    const libraryPane = document.querySelector('.side-pane[data-pane="biblioteca"]');
	    const selectionToolbar = document.getElementById('task-selection-toolbar');
    const selectionSummary = document.getElementById('task-selection-summary');
    const scaleXInput = document.getElementById('task-scale-x');
    const scaleYInput = document.getElementById('task-scale-y');
	    const rotationInput = document.getElementById('task-rotation');
	    const colorInput = document.getElementById('task-style-color');
	    const strokeWidthRow = document.getElementById('task-stroke-width-row');
		    const strokeWidthInput = document.getElementById('task-stroke-width');
		    const strokePresetsRow = document.getElementById('task-stroke-presets');
		    const commandBar = document.getElementById('task-command-bar');
		    const commandMoreBtn = document.getElementById('task-command-more');
		    const commandMenu = document.getElementById('task-command-menu');
		    const layersList = document.getElementById('task-layers-list');
		    const timelineList = document.getElementById('task-timeline-list');
	    const stepTitleInput = document.getElementById('task-step-title');
	    const stepDurationInput = document.getElementById('task-step-duration');
    const addStepButton = document.getElementById('task-step-add');
    const duplicateStepButton = document.getElementById('task-step-duplicate');
    const removeStepButton = document.getElementById('task-step-remove');
    const playStepButton = document.getElementById('task-step-play');
    const presetButtons = Array.from(document.querySelectorAll('.surface-option[data-preset]'));
    const surfaceThumbs = Array.from(document.querySelectorAll('[data-surface-thumb]'));
    const inspectorSlots = new Map(
      Array.from(document.querySelectorAll('[data-inspector-slot]'))
        .map((node) => [safeText(node.dataset.inspectorSlot), node])
        .filter(([key]) => !!key),
    );
    const sideTabs = Array.from(document.querySelectorAll('#task-side-tabs .side-tab'));
    const sidePanes = Array.from(document.querySelectorAll('.side-pane[data-pane]'));
	    const assignedHidden = document.getElementById('assigned-players-hidden');
	    const assignedSummary = document.getElementById('task-assigned-summary');
	    const exportPngBtn = document.getElementById('export-png');
	    const exportPngHdBtn = document.getElementById('export-png-hd');
	    const exportJsonBtn = document.getElementById('export-json');
	    const exportStepsBtn = document.getElementById('export-png-steps');
	    const exportWebmBtn = document.getElementById('export-webm');
    if (!window.fabric || !form || !canvasEl || !stage || !svgSurface || !presetSelect) return;

    const draftAlert = document.getElementById('task-builder-draft-alert');
    const keepaliveUrl = safeText(form.dataset.keepaliveUrl);
    const saveSuccess = safeText(form.dataset.saveSuccess) === '1';
    const draftKey = safeText(form.dataset.draftKey);
    const draftNewKey = safeText(form.dataset.draftNewKey);
    const currentDraftUrl = `${window.location.pathname}${window.location.search || ''}`;
    const canUseStorage = (() => {
      try {
        const probeKey = '__tpad_storage_probe__';
        window.localStorage.setItem(probeKey, '1');
        window.localStorage.removeItem(probeKey);
        return true;
      } catch (error) {
        return false;
      }
    })();
    const setDraftAlert = (message) => {
      if (!draftAlert) return;
      const text = safeText(message);
      draftAlert.textContent = text;
      draftAlert.hidden = !text;
    };

    const clearDraftKeys = () => {
      if (!canUseStorage) return;
      const keys = new Set([draftKey, draftNewKey].map((k) => safeText(k)).filter(Boolean));
      keys.forEach((key) => {
        try {
          window.localStorage.removeItem(key);
        } catch (error) {
          // ignore
        }
      });
    };
    const readDraft = (key) => {
      if (!canUseStorage) return null;
      const safeKey = safeText(key);
      if (!safeKey) return null;
      let raw = '';
      try {
        raw = window.localStorage.getItem(safeKey) || '';
      } catch (error) {
        raw = '';
      }
      if (!raw) return null;
      try {
        return JSON.parse(raw);
      } catch (error) {
        try {
          window.localStorage.removeItem(safeKey);
        } catch (removeError) {
          // ignore
        }
        return null;
      }
    };
    const applyDraftToForm = (draft) => {
      const fields = draft && typeof draft === 'object' ? draft.fields : null;
      if (!fields || typeof fields !== 'object') return false;
      const elements = Array.from(form.elements || []);
      elements.forEach((el) => {
        if (!el || !el.name) return;
        const key = safeText(el.name);
        if (!Object.prototype.hasOwnProperty.call(fields, key)) return;
        const stored = fields[key];
        const type = safeText(el.type);
        if (type === 'file' || type === 'password') return;
        if (type === 'checkbox') {
          if (Array.isArray(stored)) {
            el.checked = stored.map((v) => safeText(v)).includes(safeText(el.value));
          } else {
            el.checked = !!stored;
          }
          return;
        }
        if (type === 'radio') {
          el.checked = safeText(stored) === safeText(el.value);
          return;
        }
        if (el.tagName === 'SELECT' && el.multiple && Array.isArray(stored)) {
          const wanted = new Set(stored.map((v) => safeText(v)));
          Array.from(el.options || []).forEach((opt) => {
            opt.selected = wanted.has(safeText(opt.value));
          });
          return;
        }
        el.value = stored == null ? '' : String(stored);
      });
      return true;
    };

    if (saveSuccess) {
      clearDraftKeys();
      setDraftAlert('');
    } else if (draftKey) {
      const draft = readDraft(draftKey);
      const matchesUrl = !draft?.url || safeText(draft.url) === currentDraftUrl;
      if (draft && matchesUrl && applyDraftToForm(draft)) {
        const stamp = safeText(draft.updated_at);
        setDraftAlert(stamp ? `Borrador local recuperado (${stamp}).` : 'Borrador local recuperado.');
      } else {
        setDraftAlert('');
      }
    }

	    const setStatus = (message, isError = false) => {
	      if (!statusEl) return;
	      statusEl.textContent = message;
	      statusEl.style.color = isError ? '#fca5a5' : 'rgba(226,232,240,0.72)';
	    };

	    const initRichEditors = () => {
	      const wrappers = Array.from(form.querySelectorAll('[data-rich-editor]'));
	      if (!wrappers.length) return;

	      const applyCaseToSelection = (mode) => {
	        const selection = window.getSelection ? window.getSelection() : null;
	        if (!selection || selection.rangeCount <= 0) return false;
	        const range = selection.getRangeAt(0);
	        if (!range || range.collapsed) return false;
	        const text = String(range.toString() || '');
	        const replaced = mode === 'upper' ? text.toUpperCase() : text.toLowerCase();
	        range.deleteContents();
	        range.insertNode(document.createTextNode(replaced));
	        selection.removeAllRanges();
	        selection.addRange(range);
	        return true;
	      };

	      wrappers.forEach((wrapper) => {
	        const plainName = safeText(wrapper.dataset.richName);
	        const htmlName = safeText(wrapper.dataset.richHtmlName);
	        if (!plainName || !htmlName) return;
	        const area = wrapper.querySelector('[data-rich-area]');
	        const toolbar = wrapper.querySelector('.rich-toolbar');
	        const plainField = form.querySelector(`[name="${CSS.escape(plainName)}"]`);
	        const htmlField = form.querySelector(`[name="${CSS.escape(htmlName)}"]`);
	        if (!area || !plainField || !htmlField) return;

	        const normalizePlain = (value) => String(value || '')
	          .replace(/\u00a0/g, ' ')
	          .replace(/[ \t]+\n/g, '\n')
	          .replace(/\n{3,}/g, '\n\n')
	          .trim();

	        const sync = () => {
	          htmlField.value = String(area.innerHTML || '').trim();
	          plainField.value = normalizePlain(area.innerText || area.textContent || '');
	          plainField.dispatchEvent(new Event('input', { bubbles: true }));
	        };

	        area.addEventListener('input', sync);
	        area.addEventListener('blur', sync);
	        area.addEventListener('paste', (event) => {
	          const text = event.clipboardData?.getData('text/plain');
	          if (typeof text !== 'string') return;
	          event.preventDefault();
	          try {
	            document.execCommand('insertText', false, text);
	          } catch (error) {
	            // fallback
	            const selection = window.getSelection ? window.getSelection() : null;
	            if (!selection || selection.rangeCount <= 0) return;
	            const range = selection.getRangeAt(0);
	            range.deleteContents();
	            range.insertNode(document.createTextNode(text));
	          }
	          sync();
	        });

	        toolbar?.addEventListener('click', (event) => {
	          const btn = event.target.closest('button[data-rich-cmd]');
	          if (!btn) return;
	          event.preventDefault();
	          const cmd = safeText(btn.dataset.richCmd);
	          if (!cmd) return;
	          area.focus();
	          if (cmd === 'upper' || cmd === 'lower') {
	            const did = applyCaseToSelection(cmd);
	            if (!did) setStatus('Selecciona texto para cambiar mayúsculas/minúsculas.', true);
	            sync();
	            return;
	          }
	          try {
	            document.execCommand(cmd, false, null);
	          } catch (error) {
	            // ignore
	          }
	          sync();
	        });

	        // Inicializa hidden fields al cargar (para el caso de que vengan con HTML).
	        sync();
	      });
	    };
	    initRichEditors();

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

	    const GRID_SIZES = [28, 40, 56];
	    const gridPrefsKey = 'tpad_grid_prefs_v1';
	    const readGridPrefs = () => {
	      if (!canUseStorage) return null;
	      try {
	        return JSON.parse(window.localStorage.getItem(gridPrefsKey) || 'null');
	      } catch (error) {
	        return null;
	      }
	    };
	    const writeGridPrefs = (prefs) => {
	      if (!canUseStorage) return;
	      try {
	        window.localStorage.setItem(gridPrefsKey, JSON.stringify(prefs || {}));
	      } catch (error) {
	        // ignore
	      }
	    };
	    const initialGridPrefs = readGridPrefs() || {};
	    let gridVisible = !!initialGridPrefs.visible;
	    let gridSnapEnabled = !!initialGridPrefs.snap;
	    let gridSizeIndex = clamp(Number(initialGridPrefs.sizeIndex) || 1, 0, GRID_SIZES.length - 1);
	    const gridSizePx = () => GRID_SIZES[gridSizeIndex] || 40;
	    const syncGridUi = (options = {}) => {
	      if (!stage) return;
	      stage.classList.toggle('has-grid', !!gridVisible);
	      stage.style.setProperty('--grid-size', `${gridSizePx()}px`);
	      if (!options.silent) writeGridPrefs({ visible: gridVisible, snap: gridSnapEnabled, sizeIndex: gridSizeIndex });
	    };
	    const toggleGridVisible = () => {
	      gridVisible = !gridVisible;
	      syncGridUi();
	      setStatus(gridVisible ? 'Rejilla activada.' : 'Rejilla oculta.');
	    };
	    const toggleGridSnap = () => {
	      gridSnapEnabled = !gridSnapEnabled;
	      syncGridUi();
	      setStatus(gridSnapEnabled ? 'Snap a rejilla activado (Alt lo desactiva temporalmente).' : 'Snap a rejilla desactivado (Alt lo activa temporalmente).');
	    };
	    const cycleGridSize = () => {
	      gridSizeIndex = (gridSizeIndex + 1) % GRID_SIZES.length;
	      syncGridUi();
	      const label = gridSizeIndex === 0 ? 'S' : (gridSizeIndex === 1 ? 'M' : 'L');
	      setStatus(`Tamaño de rejilla: ${label}.`);
	    };
	    const shouldSnapToGridForEvent = (rawEvent) => {
	      const alt = !!rawEvent?.altKey;
	      return gridSnapEnabled ? !alt : alt;
	    };
	    const snapPointToGrid = (point) => {
	      const size = gridSizePx();
	      const baseX = Number(point?.x) || 0;
	      const baseY = Number(point?.y) || 0;
	      const snappedX = Math.round(baseX / size) * size;
	      const snappedY = Math.round(baseY / size) * size;
	      return {
	        x: clamp(snappedX, 0, canvas.getWidth()),
	        y: clamp(snappedY, 0, canvas.getHeight()),
	      };
	    };
	    syncGridUi({ silent: true });

		    let history = [];
	      let historyIndex = -1;
			    let pendingFactory = null;
			    let pendingKind = '';
			    const lastPlacedByKind = new Map();
			    let clipboardObject = null;
			    let pasteOffset = 0;
			    let layerUidCounter = 1;
			    const DRAG_MIME = 'application/x-webstats-tactical-resource';
		    let previewRefreshTimer = null;
	    let previewBuildInFlight = false;
	    let exportInFlight = false;
    let surfacesRendered = false;
    let timeline = [];
    let activeStepIndex = -1;
    let playbackTimer = null;
    let playbackRestoreState = null;
    let pitchOrientation = safeText(orientationInput?.value, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
	    let pitchZoom = Number.parseFloat(String(zoomInput?.value || '').trim());
	    let zoomTouched = false;
	    let spacePanArmed = false;
	    let spacePanning = false;
	    let spacePanStart = null;
	    if (!Number.isFinite(pitchZoom)) {
	      pitchZoom = pitchOrientation === 'portrait' ? 1.15 : 1.0;
	    }
    pitchZoom = clamp(pitchZoom, 0.8, 1.6);

    const clampScale = (value) => clamp(Number(value) || 1, 0.4, 2.6);
	    const normalizeEditableObject = (object) => {
	      if (!object) return object;
	      const locked = !!object?.data?.locked;
	      object.set({
	        hasControls: !locked,
	        hasBorders: true,
	        transparentCorners: false,
	        cornerStyle: 'circle',
	        cornerColor: '#22d3ee',
	        borderColor: '#67e8f9',
	        cornerStrokeColor: '#071320',
	        padding: 8,
	        lockScalingFlip: true,
	      });
	      if (locked) {
	        object.set({
	          lockMovementX: true,
	          lockMovementY: true,
	          lockScalingX: true,
	          lockScalingY: true,
	          lockRotation: true,
	          hoverCursor: 'default',
	          moveCursor: 'default',
	        });
	      } else {
	        object.set({
	          lockMovementX: false,
	          lockMovementY: false,
	          lockScalingX: false,
	          lockScalingY: false,
	          lockRotation: false,
	        });
	      }
	      return object;
	    };
    const isColorizableObject = (object) => {
      const kind = safeText(object?.data?.kind);
      if (!kind) return false;
      if (kind === 'token' || kind === 'ball' || kind === 'cone' || kind === 'zone' || kind === 'text' || kind === 'goal') return true;
      if (kind.startsWith('line') || kind.startsWith('arrow') || kind.startsWith('shape')) return true;
      if (kind.startsWith('emoji_')) return true;
      return false;
    };
    const isBackgroundShape = (object) => {
      const kind = safeText(object?.data?.kind);
      if (!kind) return false;
      return kind === 'zone' || kind.startsWith('shape-') || kind === 'goal';
    };
    const getObjectStrokeWidth = (object) => {
      if (!object) return 0;
      const value = Number(object.strokeWidth);
      if (Number.isFinite(value) && value > 0) return value;
      if (Array.isArray(object._objects)) {
        for (const child of object._objects) {
          const nested = getObjectStrokeWidth(child);
          if (nested) return nested;
        }
      }
      return 0;
    };
    const applyObjectStrokeWidth = (object, strokeWidth) => {
      if (!object) return;
      const width = clamp(Number(strokeWidth) || 3, 1, 14);
      if (typeof object.set === 'function' && object.strokeWidth !== undefined) {
        object.set({ strokeWidth: width });
      }
      const kind = safeText(object?.data?.kind);
      if (Array.isArray(object._objects)) {
        object._objects.forEach((child) => {
          if (!child) return;
          if (child.strokeWidth !== undefined) child.set({ strokeWidth: width });
          if (kind.startsWith('arrow') && child.type === 'triangle' && child.width && child.height) {
            const headSize = clamp(width * 5, 14, 44);
            child.set({ width: headSize, height: headSize });
          }
        });
        object.dirty = true;
      }
      setObjectData(object, { stroke_width: width });
    };
    const activeInspectableObject = () => canvas.getActiveObject() || null;
    const setObjectData = (object, patch) => {
      if (!object || typeof object !== 'object') return;
      object.data = { ...(object.data || {}), ...(patch || {}) };
    };
    const objectPreferredColor = (object) => {
      if (!object) return '#22d3ee';
      const stored = parseColorToHex(object?.data?.color, '');
      if (stored) return stored;
      const kind = safeText(object?.data?.kind);
      if (kind === 'token' && Array.isArray(object._objects)) {
        // Local token: devuelve el color de la franja si existe.
        const stripe = object._objects.find((child) => child && child.type === 'rect' && Number(child.width) <= 14 && Number(child.height) >= 40);
        const stripeFill = stripe ? parseColorToHex(stripe.fill, '') : '';
        if (stripeFill) return stripeFill;
        const circle = object._objects.find((child) => child && child.type === 'circle');
        const circleFill = circle ? parseColorToHex(circle.fill, '') : '';
        if (circleFill) return circleFill;
      }
      if (Array.isArray(object._objects) && object._objects.length) {
        for (const child of object._objects) {
          const nested = objectPreferredColor(child);
          if (nested) return nested;
        }
      }
      const stroke = parseColorToHex(object.stroke, '');
      if (stroke) return stroke;
      const fill = parseColorToHex(object.fill, '');
      if (fill) return fill;
      return '#22d3ee';
    };
	    const applyTokenColor = (group, colorHex) => {
	      if (!group || !Array.isArray(group._objects)) return;
	      setObjectData(group, { color: colorHex });
	      const tokenKind = safeText(group?.data?.token_kind);
	      const stripeRects = group._objects.filter((child) => child && child.type === 'rect' && Number(child.width) <= 14 && Number(child.height) >= 40);
	      const treatAsLocal = tokenKind === 'player_local' || (!tokenKind && stripeRects.length >= 2);
	      if (treatAsLocal) {
	        stripeRects.forEach((child) => child.set({ fill: colorHex }));
	        group.dirty = true;
	        return;
	      }
	      if (tokenKind === 'player_away') {
	        const circle = group._objects.find((child) => child && child.type === 'circle');
	        if (circle) {
	          circle.set({
	            fill: colorHex,
	            stroke: 'rgba(255,255,255,0.92)',
	          });
	        }
	        const contrast = contrastTextForFill(colorHex);
	        const textNodes = group._objects.filter((child) => child && child.type === 'text');
	        // Solo recolorea el dorsal central; el nombre va sobre una etiqueta oscura fija.
	        textNodes.forEach((node) => {
	          if (!node) return;
	          const top = Number(node.top) || 0;
	          if (Math.abs(top) < 1) node.set({ fill: contrast });
	        });
	        group.dirty = true;
	        return;
	      }
	      const circle = group._objects.find((child) => child && child.type === 'circle');
	      if (circle) {
	        circle.set({
	          fill: colorHex,
	          stroke: 'rgba(255,255,255,0.92)',
	        });
	      }
      const textNodes = group._objects.filter((child) => child && child.type === 'text');
      const contrast = contrastTextForFill(colorHex);
      textNodes.forEach((node) => {
        if (!node) return;
        // Mantén blanco si el texto tiene fondo oscuro (etiqueta inferior).
        if (node.backgroundColor) {
          node.set({ fill: '#ffffff' });
          return;
        }
        node.set({ fill: contrast });
      });
      group.dirty = true;
    };
    const applyEmojiColor = (group, colorHex) => {
      if (!group || !Array.isArray(group._objects)) return;
      setObjectData(group, { color: colorHex });
      const circle = group._objects.find((child) => child && child.type === 'circle');
      if (circle) circle.set({ stroke: colorHex, fill: rgbaFromHex(colorHex, 0.16) });
      group.dirty = true;
    };
    const applyObjectColor = (object, colorHex) => {
      if (!object) return;
      const kind = safeText(object?.data?.kind);
      if (kind) setObjectData(object, { color: colorHex });
      if (kind === 'token') {
        applyTokenColor(object, colorHex);
        return;
      }
      if (kind.startsWith('emoji_') && Array.isArray(object._objects)) {
        applyEmojiColor(object, colorHex);
        return;
      }
      if (kind.startsWith('emoji_') && object && object.type === 'text') {
        // Compat: emojis antiguos eran Text plano. Los convertimos a Group con halo para poder colorear.
        const insertIndex = canvas.getObjects().indexOf(object);
        const factory = simpleFactory(kind);
        if (typeof factory === 'function') {
          const replacement = factory(Number(object.left) || 0, Number(object.top) || 0);
          if (replacement) {
            replacement.set({
              angle: Number(object.angle) || 0,
              scaleX: Number(object.scaleX) || 1,
              scaleY: Number(object.scaleY) || 1,
            });
            normalizeEditableObject(replacement);
            canvas.remove(object);
            if (insertIndex >= 0) canvas.insertAt(replacement, insertIndex, false);
            else canvas.add(replacement);
            canvas.setActiveObject(replacement);
            applyEmojiColor(replacement, colorHex);
          }
        }
        return;
      }
      if (Array.isArray(object._objects) && object._objects.length) {
        object._objects.forEach((child) => applyObjectColor(child, colorHex));
        object.dirty = true;
        return;
      }
      if (kind === 'zone') {
        object.set({ stroke: colorHex, fill: rgbaFromHex(colorHex, 0.16) });
        return;
      }
      if (kind === 'cone') {
        object.set({ fill: colorHex, stroke: darkenHex(colorHex, 0.55) });
        return;
      }
      if (kind === 'ball') {
        object.set({ fill: colorHex, stroke: darkenHex(colorHex, 0.75) });
        return;
      }
      if (kind === 'text') {
        object.set({ fill: colorHex });
        return;
      }
      if (kind.startsWith('shape')) {
        object.set({ stroke: colorHex, fill: rgbaFromHex(colorHex, 0.12) });
        return;
      }
      if (kind.startsWith('line')) {
        object.set({ stroke: colorHex });
        return;
      }
      if (kind.startsWith('arrow')) {
        if ('stroke' in object && object.stroke) object.set({ stroke: colorHex });
        if ('fill' in object && object.fill !== undefined && object.fill !== '') object.set({ fill: colorHex });
        return;
      }
      if ('stroke' in object && object.stroke) object.set({ stroke: colorHex });
      if ('fill' in object && object.fill !== undefined && object.fill !== '') object.set({ fill: colorHex });
    };
	    const objectLabel = (object) => {
	      const kind = safeText(object?.data?.kind).replace(/-/g, '_');
	      return RESOURCE_LABELS[kind] || 'el elemento';
	    };
	    const renderLayers = () => {
	      if (!layersList) return;
	      const objects = (canvas.getObjects() || []).filter((obj) => obj && !obj?.data?.base);
	      const used = new Set();
	      objects.forEach((obj) => {
	        obj.data = obj.data || {};
	        const current = safeText(obj.data.layer_uid);
	        if (!current || used.has(current)) {
	          obj.data.layer_uid = `layer_${Date.now()}_${layerUidCounter++}`;
	        }
	        used.add(safeText(obj.data.layer_uid));
	      });

	      const active = canvas.getActiveObject();
	      const activeObjects = (() => {
	        if (!active) return [];
	        if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	        return [active];
	      })();
	      const activeUids = new Set(activeObjects.map((obj) => safeText(obj?.data?.layer_uid)).filter(Boolean));

	      layersList.textContent = '';
	      const ordered = objects.slice().reverse();
	      ordered.forEach((obj) => {
	        const uid = safeText(obj?.data?.layer_uid);
	        const kind = safeText(obj?.data?.kind);
	        const locked = !!obj?.data?.locked;
	        const visible = obj?.visible !== false;

	        let title = objectLabel(obj);
	        let subtitle = '';
	        if (kind === 'token') {
	          const tokenKind = safeText(obj?.data?.token_kind).replace(/-/g, '_');
	          title = RESOURCE_LABELS[tokenKind] || 'Jugador';
	          subtitle = safeText(obj?.data?.playerName);
	        } else if (kind === 'text' && typeof obj.text === 'string') {
	          title = obj.text.trim().slice(0, 40) || 'Texto';
	        }
	        const flags = [];
	        if (!visible) flags.push('Oculto');
	        if (locked) flags.push('Bloqueado');
	        if (flags.length) {
	          subtitle = subtitle ? `${subtitle} · ${flags.join(' · ')}` : flags.join(' · ');
	        }

	        const row = document.createElement('div');
	        row.className = 'layer-row';
	        if (uid && activeUids.has(uid)) row.classList.add('is-active');
	        row.dataset.layerUid = uid;

	        const titleBox = document.createElement('div');
	        titleBox.className = 'layer-title';
	        const strong = document.createElement('strong');
	        strong.textContent = title;
	        titleBox.appendChild(strong);
	        const small = document.createElement('small');
	        small.textContent = subtitle || (RESOURCE_LABELS[safeText(kind).replace(/-/g, '_')] || safeText(kind));
	        titleBox.appendChild(small);
	        row.appendChild(titleBox);

	        const actions = document.createElement('div');
	        actions.className = 'layer-actions';
	        const mkBtn = (action, label, aria) => {
	          const btn = document.createElement('button');
	          btn.type = 'button';
	          btn.dataset.layerAction = action;
	          btn.dataset.layerUid = uid;
	          btn.textContent = label;
	          btn.title = aria;
	          btn.setAttribute('aria-label', aria);
	          return btn;
	        };
	        actions.appendChild(mkBtn('up', '↑', 'Subir capa'));
	        actions.appendChild(mkBtn('down', '↓', 'Bajar capa'));
	        actions.appendChild(mkBtn('visible', visible ? '👁' : '🙈', visible ? 'Ocultar' : 'Mostrar'));
	        actions.appendChild(mkBtn('lock', locked ? '🔒' : '🔓', locked ? 'Desbloquear' : 'Bloquear'));
	        row.appendChild(actions);

	        layersList.appendChild(row);
	      });
	    };
	    const syncInspector = () => {
	      if (!selectionToolbar || !selectionSummary || !scaleXInput || !scaleYInput || !rotationInput || !colorInput) return;
	      const active = activeInspectableObject();
	      const enabled = !!active;
	      if (!enabled) {
	        selectionToolbar.hidden = true;
	        selectionToolbar.querySelectorAll('input,button').forEach((node) => { node.disabled = true; });
	        selectionSummary.textContent = 'Selecciona un recurso para ajustarlo.';
	        scaleXInput.value = '100';
	        scaleYInput.value = '100';
	        rotationInput.value = '0';
	        colorInput.value = '#22d3ee';
	        if (strokeWidthRow) strokeWidthRow.hidden = true;
	        if (strokePresetsRow) strokePresetsRow.hidden = true;
	        if (strokeWidthInput) strokeWidthInput.value = '3';
	        return;
	      }
      selectionToolbar.hidden = false;
      const canColor = isColorizableObject(active);
      selectionToolbar.querySelectorAll('input,button').forEach((node) => { node.disabled = false; });
      colorInput.disabled = !canColor;
      selectionToolbar.querySelectorAll('button[data-color]').forEach((node) => { node.disabled = !canColor; });
      selectionSummary.textContent = `Ajustando ${objectLabel(active)} seleccionado.`;
      scaleXInput.value = String(Math.round((Number(active.scaleX) || 1) * 100));
      scaleYInput.value = String(Math.round((Number(active.scaleY) || 1) * 100));
      rotationInput.value = String(Math.round(Number(active.angle) || 0));
      colorInput.value = objectPreferredColor(active);
      const strokeWidth = getObjectStrokeWidth(active);
	      if (strokeWidthRow && strokeWidthInput) {
	        const canStroke = strokeWidth > 0;
	        strokeWidthRow.hidden = !canStroke;
	        if (strokePresetsRow) strokePresetsRow.hidden = !canStroke;
	        strokeWidthInput.disabled = !canStroke;
	        if (canStroke) strokeWidthInput.value = String(Math.round(strokeWidth));
	      }
	    };
    const commitObjectChange = (message) => {
      canvas.requestRenderAll();
      pushHistory();
      syncInspector();
      refreshLivePreview();
      if (message) setStatus(message);
    };
	    const applyToActiveFlexibleObject = (callback, message) => {
	      const active = activeInspectableObject();
	      if (!active) return;
	      if (active?.data?.locked) {
	        setStatus('Elemento bloqueado. Usa “Desbloquear” para editarlo.', true);
	        return;
	      }
	      callback(active);
	      active.setCoords();
	      commitObjectChange(message);
	    };

	    const getSelectionObjects = () => {
	      const active = canvas.getActiveObject();
	      if (!active) return [];
	      if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	      return [active];
	    };
	    const selectionCenter = () => {
	      const active = canvas.getActiveObject();
	      if (active && typeof active.getCenterPoint === 'function') return active.getCenterPoint();
	      return new fabric.Point(canvas.getWidth() / 2, canvas.getHeight() / 2);
	    };
	    const alignSelection = (axis) => {
	      const objects = getSelectionObjects();
	      if (objects.length < 2) {
	        setStatus('Selecciona al menos 2 elementos para alinear.', true);
	        return;
	      }
	      const center = selectionCenter();
	      objects.forEach((obj) => {
	        if (!obj || obj?.data?.locked) return;
	        const current = obj.getCenterPoint();
	        const next = new fabric.Point(axis === 'x' ? center.x : current.x, axis === 'y' ? center.y : current.y);
	        obj.setPositionByOrigin(next, 'center', 'center');
	        obj.setCoords();
	      });
	      canvas.requestRenderAll();
	      pushHistory();
	      syncInspector();
	      refreshLivePreview();
	      setStatus(axis === 'x' ? 'Alineado por centro X.' : 'Alineado por centro Y.');
	    };
		    const distributeSelection = (axis) => {
		      const objects = getSelectionObjects().filter((obj) => obj && !obj?.data?.locked);
		      if (objects.length < 3) {
		        setStatus('Selecciona al menos 3 elementos para distribuir.', true);
		        return;
		      }
	      const items = objects
	        .map((obj) => ({ obj, center: obj.getCenterPoint() }))
	        .sort((a, b) => (axis === 'x' ? a.center.x - b.center.x : a.center.y - b.center.y));
	      const first = items[0].center;
	      const last = items[items.length - 1].center;
	      const span = axis === 'x' ? (last.x - first.x) : (last.y - first.y);
	      const step = span / (items.length - 1);
	      items.forEach((item, index) => {
	        const c = item.obj.getCenterPoint();
	        const next = axis === 'x'
	          ? new fabric.Point(first.x + (step * index), c.y)
	          : new fabric.Point(c.x, first.y + (step * index));
	        item.obj.setPositionByOrigin(next, 'center', 'center');
	        item.obj.setCoords();
	      });
	      canvas.requestRenderAll();
	      pushHistory();
	      syncInspector();
		      refreshLivePreview();
		      setStatus(axis === 'x' ? 'Distribución horizontal aplicada.' : 'Distribución vertical aplicada.');
		    };
		    const cloneObjectAsync = (obj) => new Promise((resolve) => {
		      try {
		        obj.clone((cloned) => resolve(cloned || null), ['data']);
		      } catch (error) {
		        resolve(null);
		      }
		    });
		    const patternDuplicate = async (axis) => {
		      const active = canvas.getActiveObject();
		      if (!active) {
		        setStatus('Selecciona un elemento para crear un patrón.', true);
		        return;
		      }

		      const bounds = typeof active.getBoundingRect === 'function' ? active.getBoundingRect(true, true) : null;
		      const defaultSpacing = axis === 'x'
		        ? clamp(Math.round((bounds?.width || 40) + 12), 12, 320)
		        : clamp(Math.round((bounds?.height || 40) + 12), 12, 320);

		      const countRaw = window.prompt('¿Cuántas copias quieres añadir?', '4');
		      if (countRaw === null) return;
		      const count = clamp(Number.parseInt(String(countRaw), 10) || 0, 1, 25);
		      if (!count) {
		        setStatus('Número de copias no válido.', true);
		        return;
		      }

		      const spacingRaw = window.prompt('Separación (px) entre copias:', String(defaultSpacing));
		      if (spacingRaw === null) return;
		      const spacing = clamp(Number.parseInt(String(spacingRaw), 10) || 0, 8, 400);
		      if (!spacing) {
		        setStatus('Separación no válida.', true);
		        return;
		      }

		      const dx = axis === 'x' ? spacing : 0;
		      const dy = axis === 'y' ? spacing : 0;
		      const sources = getSelectionObjects();
		      if (!sources.length) return;

		      const added = [];
		      for (let i = 1; i <= count; i += 1) {
		        const clones = await Promise.all(sources.map((obj) => cloneObjectAsync(obj)));
		        clones.filter(Boolean).forEach((cloned) => {
		          cloned.set({
		            left: (Number(cloned.left) || 0) + (dx * i),
		            top: (Number(cloned.top) || 0) + (dy * i),
		          });
		          normalizeEditableObject(cloned);
		          if (Array.isArray(cloned._objects)) cloned._objects.forEach((obj) => normalizeEditableObject(obj));
		          canvas.add(cloned);
		          if (isBackgroundShape(cloned)) canvas.sendToBack(cloned);
		          cloned.setCoords();
		          added.push(cloned);
		        });
		      }

		      if (!added.length) {
		        setStatus('No se pudo duplicar la selección.', true);
		        return;
		      }

		      canvas.discardActiveObject();
		      if (added.length === 1) canvas.setActiveObject(added[0]);
		      else canvas.setActiveObject(new fabric.ActiveSelection(added, { canvas }));
		      canvas.requestRenderAll();
		      persistActiveStepSnapshot();
		      pushHistory();
		      syncInspector();
		      refreshLivePreview();
		      setStatus('Patrón creado.');
		    };
		    const setSelectionLayer = (mode) => {
		      const objects = getSelectionObjects();
		      if (!objects.length) return;
		      objects.forEach((obj) => {
	        if (!obj) return;
	        if (mode === 'front') canvas.bringToFront(obj);
	        else canvas.sendToBack(obj);
	      });
	      canvas.requestRenderAll();
	      pushHistory();
	      setStatus(mode === 'front' ? 'Traído al frente.' : 'Enviado atrás.');
	    };
	    const toggleLockSelection = () => {
	      const objects = getSelectionObjects();
	      if (!objects.length) return;
	      const allLocked = objects.every((obj) => !!obj?.data?.locked);
	      objects.forEach((obj) => {
	        if (!obj) return;
	        const nextLocked = !allLocked;
	        obj.data = obj.data || {};
	        obj.data.locked = nextLocked;
	        normalizeEditableObject(obj);
	        obj.setCoords();
	      });
	      canvas.requestRenderAll();
	      pushHistory();
	      syncInspector();
	      setStatus(allLocked ? 'Elementos desbloqueados.' : 'Elementos bloqueados.');
	    };
	    const groupSelection = () => {
	      const active = canvas.getActiveObject();
	      if (!active || active.type !== 'activeSelection' || typeof active.toGroup !== 'function') {
	        setStatus('Selecciona varios elementos para agrupar.', true);
	        return;
	      }
	      const group = active.toGroup();
	      canvas.setActiveObject(group);
	      canvas.requestRenderAll();
	      pushHistory();
	      syncInspector();
	      setStatus('Grupo creado.');
	    };
	    const ungroupSelection = () => {
	      const active = canvas.getActiveObject();
	      if (!active || active.type !== 'group' || typeof active.toActiveSelection !== 'function') {
	        setStatus('Selecciona un grupo para desagrupar.', true);
	        return;
	      }
	      const sel = active.toActiveSelection();
	      canvas.setActiveObject(sel);
	      canvas.requestRenderAll();
	      pushHistory();
	      syncInspector();
	      setStatus('Grupo deshecho.');
	    };

	    const setCommandMenuOpen = (open) => {
	      if (!commandMenu) return;
	      commandMenu.hidden = !open;
	    };
	    commandMoreBtn?.addEventListener('click', (event) => {
	      event.preventDefault();
	      event.stopPropagation();
	      setCommandMenuOpen(commandMenu?.hidden);
	    });
		    commandMenu?.addEventListener('click', (event) => {
		      const button = event.target.closest('button[data-command]');
		      if (!button) return;
		      const command = safeText(button.dataset.command);
		      if (!command) return;
		      setCommandMenuOpen(false);
		      if (command === 'align_x') alignSelection('x');
		      else if (command === 'align_y') alignSelection('y');
		      else if (command === 'distribute_x') distributeSelection('x');
		      else if (command === 'distribute_y') distributeSelection('y');
		      else if (command === 'pattern_row') patternDuplicate('x');
		      else if (command === 'pattern_col') patternDuplicate('y');
		      else if (command === 'front') setSelectionLayer('front');
		      else if (command === 'back') setSelectionLayer('back');
		      else if (command === 'lock') toggleLockSelection();
		      else if (command === 'grid_toggle') toggleGridVisible();
		      else if (command === 'grid_snap') toggleGridSnap();
		      else if (command === 'grid_size') cycleGridSize();
		      else if (command === 'group') groupSelection();
		      else if (command === 'ungroup') ungroupSelection();
		    });
		    document.addEventListener('click', (event) => {
		      if (!commandMenu || commandMenu.hidden) return;
		      const inside = event.target && (event.target.closest('#task-command-bar') || event.target.closest('#task-command-menu'));
		      if (!inside) setCommandMenuOpen(false);
		    });

		    const findObjectByLayerUid = (uid) => (canvas.getObjects() || []).find((obj) => safeText(obj?.data?.layer_uid) === safeText(uid));
		    const commitLayerChange = (message) => {
		      canvas.requestRenderAll();
		      persistActiveStepSnapshot();
		      pushHistory();
		      syncInspector();
		      refreshLivePreview();
		      renderLayers();
		      if (message) setStatus(message);
		    };
		    layersList?.addEventListener('click', (event) => {
		      const actionBtn = event.target.closest('button[data-layer-action]');
		      const targetUid = safeText(actionBtn?.dataset?.layerUid || event.target.closest('.layer-row')?.dataset?.layerUid);
		      if (!targetUid) return;
		      const obj = findObjectByLayerUid(targetUid);
		      if (!obj) {
		        renderLayers();
		        return;
		      }

		      if (!actionBtn) {
		        if (obj.visible === false) {
		          obj.visible = true;
		          canvas.setActiveObject(obj);
		          commitLayerChange('Elemento mostrado.');
		          return;
		        }
		        canvas.setActiveObject(obj);
		        canvas.requestRenderAll();
		        syncInspector();
		        renderLayers();
		        return;
		      }

		      const action = safeText(actionBtn.dataset.layerAction);
		      if (!action) return;
		      if (action === 'up') {
		        canvas.bringForward(obj);
		        commitLayerChange('Capa subida.');
		        return;
		      }
		      if (action === 'down') {
		        canvas.sendBackwards(obj);
		        commitLayerChange('Capa bajada.');
		        return;
		      }
		      if (action === 'visible') {
		        const next = obj.visible === false;
		        obj.visible = next;
		        if (!next) {
		          const active = canvas.getActiveObject();
		          if (active === obj) canvas.discardActiveObject();
		        }
		        commitLayerChange(next ? 'Elemento mostrado.' : 'Elemento oculto.');
		        return;
		      }
		      if (action === 'lock') {
		        obj.data = obj.data || {};
		        obj.data.locked = !obj.data.locked;
		        normalizeEditableObject(obj);
		        obj.setCoords();
		        commitLayerChange(obj.data.locked ? 'Elemento bloqueado.' : 'Elemento desbloqueado.');
		      }
		    });

	    const fitCanvas = (preserveObjects = false) => {
	      const previousWidth = canvas.getWidth() || 0;
	      const previousHeight = canvas.getHeight() || 0;
      const width = Math.max(320, Math.round(stage.clientWidth || 960));
      const height = Math.max(220, Math.round(stage.clientHeight || 640));
      canvas.setDimensions({ width, height });
      if (preserveObjects && previousWidth > 0 && previousHeight > 0) {
        const scaleX = width / previousWidth;
        const scaleY = height / previousHeight;
        const uniformScale = Math.min(scaleX, scaleY);
        canvas.getObjects().forEach((item) => {
          item.set({
            left: (Number(item.left) || 0) * scaleX,
            top: (Number(item.top) || 0) * scaleY,
            scaleX: clampScale((Number(item.scaleX) || 1) * uniformScale),
            scaleY: clampScale((Number(item.scaleY) || 1) * uniformScale),
          });
          item.setCoords();
        });
      }
      canvas.calcOffset();
      canvas.requestRenderAll();
    };
    const syncOrientationUi = () => {
      if (orientationInput) orientationInput.value = pitchOrientation;
      if (orientationLabel) orientationLabel.textContent = ORIENTATION_LABEL[pitchOrientation] === 'vertical' ? 'Vertical' : 'Horizontal';
      stage.classList.toggle('is-portrait', pitchOrientation === 'portrait');
      viewportEl?.classList.toggle('is-portrait', pitchOrientation === 'portrait');
      orientationToggle?.classList.toggle('is-active', pitchOrientation === 'portrait');
    };
    const syncZoomUi = () => {
      if (zoomInput) zoomInput.value = String(pitchZoom.toFixed(2));
      if (zoomLabel) zoomLabel.textContent = `${Math.round(pitchZoom * 100)}%`;
      stage.style.setProperty('--pitch-zoom', String(pitchZoom));
      viewportEl?.classList.toggle('is-zoomed', pitchZoom > 1.02);
      canvas.calcOffset();
    };
    const applyPitchZoom = (value, options = {}) => {
      const next = clamp(Number(value) || 1, 0.8, 1.6);
      pitchZoom = next;
      if (!options.silent) zoomTouched = true;
      syncZoomUi();
      if (!options.silent) setStatus(`Zoom: ${Math.round(pitchZoom * 100)}%.`);
    };

    const serializeCanvasOnly = () => {
      const json = canvas.toJSON(['data']);
      json.objects = (json.objects || []).filter((item) => !(item?.data?.base));
      return json;
    };
    const normalizeTimeline = (raw) => {
      if (!Array.isArray(raw)) return [];
      return raw
        .map((item, index) => {
          if (!item || typeof item !== 'object' || !item.canvas_state || typeof item.canvas_state !== 'object') return null;
          return {
            title: safeText(item.title, `Paso ${index + 1}`),
            duration: clamp(Number(item.duration) || 3, 1, 20),
            canvas_state: sanitizeLoadedState(item.canvas_state),
          };
        })
        .filter(Boolean)
        .slice(0, 24);
    };
    const persistActiveStepMeta = () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(stepTitleInput?.value, `Paso ${activeStepIndex + 1}`);
      timeline[activeStepIndex].duration = clamp(Number(stepDurationInput?.value) || 3, 1, 20);
    };
    const persistActiveStepSnapshot = () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      persistActiveStepMeta();
      timeline[activeStepIndex].canvas_state = serializeCanvasOnly();
    };
    const syncStepInputs = () => {
      const active = activeStepIndex >= 0 ? timeline[activeStepIndex] : null;
      [stepTitleInput, stepDurationInput, duplicateStepButton, removeStepButton, playStepButton].forEach((node) => {
        if (!node) return;
        node.disabled = !active && node !== playStepButton;
      });
      if (playStepButton) playStepButton.disabled = timeline.length <= 0;
      if (!active) {
        if (stepTitleInput) stepTitleInput.value = '';
        if (stepDurationInput) stepDurationInput.value = '3';
        return;
      }
      if (stepTitleInput) stepTitleInput.value = active.title || `Paso ${activeStepIndex + 1}`;
      if (stepDurationInput) stepDurationInput.value = String(active.duration || 3);
    };
    const renderTimeline = () => {
      if (!timelineList) return;
      if (!timeline.length) {
        timelineList.innerHTML = '<div class="timeline-empty">Todavía no hay pasos. Diseña la salida inicial y pulsa "Añadir paso".</div>';
        syncStepInputs();
        return;
      }
      timelineList.innerHTML = '';
      timeline.forEach((step, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `timeline-step${index === activeStepIndex ? ' is-active' : ''}`;
        button.dataset.stepIndex = String(index);
        button.innerHTML = `
          <div>
            <strong>${step.title || `Paso ${index + 1}`}</strong>
            <span>${step.duration || 3} s · escena ${index + 1}</span>
          </div>
          <span>${index === activeStepIndex ? 'Editando' : 'Abrir'}</span>
        `;
        timelineList.appendChild(button);
      });
      syncStepInputs();
    };
    const loadCanvasSnapshot = (rawState, callback) => {
      const parsed = sanitizeLoadedState(rawState);
      canvas.__loading = true;
      canvas.loadFromJSON(parsed, () => {
        canvas.getObjects().forEach((item) => normalizeEditableObject(item));
        canvas.__loading = false;
        canvas.requestRenderAll();
        syncInspector();
        refreshLivePreview();
        if (typeof callback === 'function') callback();
      });
    };
    const applySerializedState = (rawState, options = {}) => {
      const parsed = rawState && typeof rawState === 'object' ? rawState : { version: '5.3.0', objects: [] };
      timeline = normalizeTimeline(parsed.timeline);
      const nextIndex = timeline.length
        ? clamp(Number(parsed.active_step_index) || 0, 0, timeline.length - 1)
        : -1;
      activeStepIndex = nextIndex;
      const sourceState = activeStepIndex >= 0 ? timeline[activeStepIndex].canvas_state : parsed;
      loadCanvasSnapshot(sourceState, () => {
        renderTimeline();
        if (options.pushHistory) pushHistory();
      });
    };
    const pushHistory = () => {
      const snapshot = JSON.stringify(serializeState());
      if (historyIndex >= 0 && history[historyIndex] === snapshot) return;
      if (historyIndex >= 0 && historyIndex < history.length - 1) {
        history = history.slice(0, historyIndex + 1);
      }
      history.push(snapshot);
      historyIndex = history.length - 1;
      if (history.length > 60) {
        const drop = history.length - 60;
        history = history.slice(drop);
        historyIndex = Math.max(0, historyIndex - drop);
      }
    };

    const performUndo = () => {
      if (historyIndex <= 0) return false;
      historyIndex -= 1;
      applySerializedState(JSON.parse(history[historyIndex]));
      setStatus('Último cambio deshecho.');
      return true;
    };

    const performRedo = () => {
      if (historyIndex < 0 || historyIndex >= history.length - 1) return false;
      historyIndex += 1;
      applySerializedState(JSON.parse(history[historyIndex]));
      setStatus('Cambio rehecho.');
      return true;
    };

	    const duplicateActiveObject = () => {
	      const active = canvas.getActiveObject();
	      if (!active) {
	        setStatus('No hay elemento seleccionado para duplicar.', true);
	        return;
      }
      active.clone((cloned) => {
        const dx = 18;
        const dy = 18;
        canvas.discardActiveObject();

        if (cloned && cloned.type === 'activeSelection') {
          const added = [];
          cloned.canvas = canvas;
          cloned.forEachObject((obj) => {
            obj.set({
              left: (Number(obj.left) || 0) + dx,
              top: (Number(obj.top) || 0) + dy,
            });
            normalizeEditableObject(obj);
            canvas.add(obj);
            added.push(obj);
          });
          const selection = new fabric.ActiveSelection(added, { canvas });
          canvas.setActiveObject(selection);
          selection.setCoords();
        } else if (cloned) {
          cloned.set({
            left: (Number(cloned.left) || 0) + dx,
            top: (Number(cloned.top) || 0) + dy,
          });
          normalizeEditableObject(cloned);
          if (Array.isArray(cloned._objects)) cloned._objects.forEach((obj) => normalizeEditableObject(obj));
          canvas.add(cloned);
          canvas.setActiveObject(cloned);
          cloned.setCoords();
        }

        canvas.requestRenderAll();
        persistActiveStepSnapshot();
        pushHistory();
        syncInspector();
        refreshLivePreview();
	        setStatus('Elemento duplicado.');
	      }, ['data']);
	    };

	    const copyActiveObject = () => {
	      const active = canvas.getActiveObject();
	      if (!active) {
	        setStatus('No hay elemento seleccionado para copiar.', true);
	        return;
	      }
	      active.clone((cloned) => {
	        clipboardObject = cloned;
	        pasteOffset = 0;
	        setStatus('Elemento copiado.');
	      }, ['data']);
	    };

	    const pasteClipboardObject = () => {
	      if (!clipboardObject) {
	        setStatus('No hay nada copiado todavía.', true);
	        return;
	      }
	      const dx = 18 + (pasteOffset % 54);
	      const dy = 18 + (pasteOffset % 54);
	      pasteOffset += 18;
	      clipboardObject.clone((cloned) => {
	        canvas.discardActiveObject();
	        if (cloned && cloned.type === 'activeSelection') {
	          const added = [];
	          cloned.canvas = canvas;
	          cloned.forEachObject((obj) => {
	            obj.set({
	              left: (Number(obj.left) || 0) + dx,
	              top: (Number(obj.top) || 0) + dy,
	            });
	            normalizeEditableObject(obj);
	            canvas.add(obj);
	            added.push(obj);
	          });
	          const selection = new fabric.ActiveSelection(added, { canvas });
	          canvas.setActiveObject(selection);
	          selection.setCoords();
	        } else if (cloned) {
	          cloned.set({
	            left: (Number(cloned.left) || 0) + dx,
	            top: (Number(cloned.top) || 0) + dy,
	          });
	          normalizeEditableObject(cloned);
	          if (Array.isArray(cloned._objects)) cloned._objects.forEach((obj) => normalizeEditableObject(obj));
	          canvas.add(cloned);
	          canvas.setActiveObject(cloned);
	          cloned.setCoords();
	        }
	        canvas.requestRenderAll();
	        persistActiveStepSnapshot();
	        pushHistory();
	        syncInspector();
	        refreshLivePreview();
	        setStatus('Pegado.');
	      }, ['data']);
	    };

    const applyPitchSurface = (presetValue, orientationValue) => {
      // Evita SVG anidados (innerHTML con <svg> completo) que luego rompen la previsualización y el PDF.
      const markup = buildPitchSvg(presetValue, orientationValue);
      try {
        const parsed = new DOMParser().parseFromString(markup, 'image/svg+xml');
        const root = parsed.documentElement;
        if (root && root.tagName && root.tagName.toLowerCase() === 'svg') {
          svgSurface.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
          svgSurface.setAttribute('viewBox', root.getAttribute('viewBox') || '0 0 1100 748');
          svgSurface.setAttribute('preserveAspectRatio', root.getAttribute('preserveAspectRatio') || 'xMidYMid meet');
          while (svgSurface.firstChild) svgSurface.removeChild(svgSurface.firstChild);
          Array.from(root.childNodes).forEach((child) => {
            svgSurface.appendChild(svgSurface.ownerDocument.importNode(child, true));
          });
          return;
        }
      } catch (error) {
        // Fallback: deja el markup tal cual si el parseo falla.
      }
      svgSurface.innerHTML = markup;
    };

    const setPreset = (presetValue) => {
      const preset = safeText(presetValue, 'full_pitch');
      presetSelect.value = preset;
      if (pitchFormatInput && PITCH_FORMAT_BY_PRESET[preset]) pitchFormatInput.value = PITCH_FORMAT_BY_PRESET[preset];
      presetButtons.forEach((button) => button.classList.toggle('is-active', safeText(button.dataset.preset) === preset));
      if (surfaceTriggerLabel) surfaceTriggerLabel.textContent = PRESET_LABEL[preset] || 'Campo completo';
      applyPitchSurface(preset, pitchOrientation);
      refreshLivePreview();
      setStatus(`Superficie preparada: ${PRESET_LABEL[preset] || 'campo'} en ${ORIENTATION_LABEL[pitchOrientation]}.`);
    };
    const applyPitchOrientation = (nextOrientation, options = {}) => {
      const normalized = safeText(nextOrientation, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
      if (normalized === pitchOrientation && !options.force) return;
      pitchOrientation = normalized;
      syncOrientationUi();
      if (!zoomTouched) {
        pitchZoom = pitchOrientation === 'portrait' ? 1.15 : 1.0;
        syncZoomUi();
      }
      fitCanvas(options.preserveObjects !== false);
      setPreset(presetSelect.value || 'full_pitch');
      if (!options.silent) setStatus(`Campo en ${ORIENTATION_LABEL[pitchOrientation]}.`);
      if (options.pushHistory) {
        pushHistory();
      }
    };

    const renderSurfaceThumbs = () => {
      if (surfacesRendered) return;
      surfaceThumbs.forEach((node) => {
        const preset = safeText(node.dataset.surfaceThumb, 'full_pitch');
        node.innerHTML = buildPitchSvg(preset);
      });
      surfacesRendered = true;
    };

    const setSurfaceMenuOpen = (open) => {
      if (!surfacePicker) return;
      surfacePicker.classList.toggle('is-open', !!open);
    };

    const serializeState = () => {
      persistActiveStepSnapshot();
      const json = serializeCanvasOnly();
      json.timeline = timeline.map((step, index) => ({
        title: safeText(step.title, `Paso ${index + 1}`),
        duration: clamp(Number(step.duration) || 3, 1, 20),
        canvas_state: sanitizeLoadedState(step.canvas_state),
      }));
      json.active_step_index = activeStepIndex;
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
	      normalizeEditableObject(object);
	      canvas.add(object);
      if (isBackgroundShape(object)) canvas.sendToBack(object);
      canvas.setActiveObject(object);
      canvas.requestRenderAll();
      pushHistory();
      syncInspector();
	    };
	    const snapPointToCenters = (point, target, threshold = 10) => {
	      const baseX = Number(point?.x) || 0;
	      const baseY = Number(point?.y) || 0;
	      let bestDx = threshold + 1;
	      let bestDy = threshold + 1;
	      let snapX = null;
	      let snapY = null;
	      canvas.getObjects().forEach((obj) => {
	        if (!obj || obj === target) return;
	        if (obj.evented === false && obj.selectable === false) return;
	        const center = obj.getCenterPoint();
	        const dx = Math.abs(center.x - baseX);
	        const dy = Math.abs(center.y - baseY);
	        if (dx <= threshold && dx < bestDx) {
	          bestDx = dx;
	          snapX = center.x;
	        }
	        if (dy <= threshold && dy < bestDy) {
	          bestDy = dy;
	          snapY = center.y;
	        }
	      });
	      return {
	        x: snapX === null ? baseX : snapX,
	        y: snapY === null ? baseY : snapY,
	        snappedX: snapX !== null,
	        snappedY: snapY !== null,
	      };
	    };
	    const clearPendingPlacement = () => {
	      pendingFactory = null;
	      pendingKind = '';
	      Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
	      Array.from(playerBank?.querySelectorAll('button') || []).forEach((button) => button.classList.remove('is-active'));
	      Array.from(libraryPane?.querySelectorAll('button[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
	    };
    const pointerFromStageEvent = (event) => {
      const rect = stage.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * canvas.getWidth();
      const y = ((event.clientY - rect.top) / rect.height) * canvas.getHeight();
      return {
        x: clamp(x, 24, canvas.getWidth() - 24),
        y: clamp(y, 24, canvas.getHeight() - 24),
      };
    };
    const createFactoryFromPayload = (payload) => {
      if (!payload || typeof payload !== 'object') return null;
      if (payload.playerId) {
        const player = players.find((item) => String(item.id) === String(payload.playerId));
        if (!player) return null;
        return {
          factory: playerTokenFactory(payload.kind || 'player_local', player),
          label: safeText(player.name, 'el jugador'),
        };
      }
      if (payload.kind === 'player_local') return { factory: playerTokenFactory('player_local', null), label: 'un jugador local' };
      if (payload.kind === 'player_rival') return { factory: playerTokenFactory('player_rival', null), label: 'un jugador rival' };
      if (payload.kind === 'player_away') return { factory: playerTokenFactory('player_away', null), label: 'un jugador con segunda equipación' };
      if (payload.kind === 'goalkeeper_local') return { factory: playerTokenFactory('goalkeeper_local', null), label: 'un portero' };
      return { factory: simpleFactory(payload.kind), label: RESOURCE_LABELS[payload.kind] || payload.kind };
    };
    const addPayloadAtPointer = (payload, pointer) => {
      const resolved = createFactoryFromPayload(payload);
      if (!resolved?.factory) return false;
      addObject(objectAtPointer(resolved.factory, pointer));
      clearPendingPlacement();
      setStatus(`${resolved.label} colocado.`);
      return true;
    };
    const registerDraggableButton = (button, payloadBuilder) => {
      if (!button) return;
      button.draggable = true;
      button.addEventListener('dragstart', (event) => {
        const payload = payloadBuilder();
        if (!payload) {
          event.preventDefault();
          return;
        }
        event.dataTransfer?.setData(DRAG_MIME, JSON.stringify(payload));
        event.dataTransfer?.setData('text/plain', JSON.stringify(payload));
        if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
        button.classList.add('is-dragging');
        setStatus('Suelta el recurso sobre el campo.');
      });
      button.addEventListener('dragend', () => {
        button.classList.remove('is-dragging');
        stage.classList.remove('is-drop-target');
      });
    };

	    const playerTokenFactory = (kind, player) => (left, top) => {
	      const playerNameLower = safeText(player?.name, '').toLowerCase();
	      const goalkeeperPreferBlue = playerNameLower.includes('trivi') || playerNameLower.includes('antonio');
	      const palette = kind === 'goalkeeper_local'
	        ? (goalkeeperPreferBlue ? COLORS.goalkeeper_blue : COLORS.goalkeeper)
	        : kind === 'player_rival'
	          ? COLORS.rival
	          : COLORS.local;
      const label = player?.number ? String(player.number).slice(0, 2) : (kind === 'goalkeeper_local' ? 'GK' : 'J');
      const displayName = shortPlayerName(player?.name || (kind === 'player_rival' ? 'Rival' : 'Jugador'));
      const initials = safeText(player?.name, kind === 'player_rival' ? 'Rival' : 'Jugador')
        .split(/\s+/)
        .map((piece) => piece[0] || '')
        .join('')
        .slice(0, 2)
        .toUpperCase() || label;
      const tokenParts = [];
	      if (kind === 'player_local' || kind === 'player_away') {
	        const radius = 23;
	        const chipClip = new fabric.Circle({
	          radius: radius - 1.6,
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: 0,
	        });
	        const isAway = kind === 'player_away';
	        const baseCircle = new fabric.Circle({
	          radius,
	          fill: isAway ? '#facc15' : '#ffffff',
	          stroke: '#e2e8f0',
	          strokeWidth: 3,
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: 0,
	          shadow: 'rgba(15,23,42,0.28) 0 5px 14px',
	        });
	        tokenParts.push(baseCircle);
	        if (!isAway) {
	          [-13, 0, 13].forEach((offset) => {
	            const stripe = new fabric.Rect({
	              left: offset,
	              top: 0,
	              width: 10,
	              height: 48,
	              fill: '#1f7a38',
	              originX: 'center',
	              originY: 'center',
	            });
	            stripe.clipPath = chipClip;
	            tokenParts.push(stripe);
	          });
	        }
	        tokenParts.push(new fabric.Text(label, {
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: 0,
	          fontSize: 17,
	          fontWeight: '900',
	          fill: isAway ? '#0b1220' : '#ffffff',
	          stroke: '#102734',
	          strokeWidth: 0.45,
	        }));
        tokenParts.push(new fabric.Rect({
          originX: 'center',
          originY: 'center',
          left: 0,
          top: -35,
          width: Math.max(42, Math.min(90, (displayName.length * 6.4) + 14)),
          height: 18,
          rx: 7,
          ry: 7,
          fill: 'rgba(15,23,42,0.94)',
          stroke: 'rgba(255,255,255,0.14)',
          strokeWidth: 1,
        }));
        tokenParts.push(new fabric.Text(displayName, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: -35,
          fontSize: 10,
          fontWeight: '700',
          fill: '#f8fafc',
        }));
      } else {
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
        tokenParts.push(circle);
        tokenParts.push(new fabric.Text(initials, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 0,
          fontSize: 12,
          fontWeight: '700',
          fill: palette.text,
        }));
        tokenParts.push(new fabric.Text(label, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 26,
          fontSize: 10,
          fontWeight: '700',
          fill: '#ffffff',
          backgroundColor: 'rgba(15,23,42,0.92)',
        }));
      }
	      return new fabric.Group(tokenParts, {
        left,
        top,
        originX: 'center',
        originY: 'center',
	        data: {
	          kind: 'token',
	          token_kind: kind,
	          color: kind === 'player_local' ? '#1f7a38' : (kind === 'player_away' ? '#facc15' : palette.fill),
	          playerId: player?.id || '',
	          playerName: safeText(player?.name, ''),
	        },
	      });
	    };

    const simpleFactory = (kind) => {
      if (kind === 'ball') {
        return (left, top) => new fabric.Circle({
          left, top, originX: 'center', originY: 'center',
          radius: 10, fill: '#ffffff', stroke: '#0f172a', strokeWidth: 2,
          data: { kind: 'ball', color: '#ffffff' },
        });
      }
      if (kind === 'cone') {
        return (left, top) => new fabric.Triangle({
          left, top, originX: 'center', originY: 'center',
          width: 24, height: 24, fill: '#f97316', stroke: '#7c2d12', strokeWidth: 1.6,
          data: { kind: 'cone', color: '#f97316' },
        });
      }
      if (kind === 'zone') {
        return (left, top) => new fabric.Rect({
          left, top, originX: 'center', originY: 'center',
          width: 130, height: 84, fill: 'rgba(34,211,238,0.16)', stroke: '#22d3ee', strokeWidth: 3,
          rx: 12, ry: 12, data: { kind: 'zone', color: '#22d3ee' },
        });
      }
      if (kind === 'goal') {
        return (left, top) => {
          const stroke = '#f8fafc';
          const strokeWidth = 3;
          const w = 128;
          const h = 74;
          const frame = new fabric.Rect({
            left: 0,
            top: 0,
            originX: 'center',
            originY: 'center',
            width: w,
            height: h,
            rx: 8,
            ry: 8,
            fill: '',
            stroke,
            strokeWidth,
          });
          const netStroke = 'rgba(248,250,252,0.22)';
          const net = [];
          for (let x = -w / 2 + 14; x <= w / 2 - 14; x += 18) {
            net.push(new fabric.Line([x, -h / 2 + 10, x, h / 2 - 10], {
              stroke: netStroke,
              strokeWidth: 1,
              originX: 'center',
              originY: 'center',
              selectable: false,
              evented: false,
            }));
          }
          for (let y = -h / 2 + 10; y <= h / 2 - 10; y += 16) {
            net.push(new fabric.Line([-w / 2 + 12, y, w / 2 - 12, y], {
              stroke: netStroke,
              strokeWidth: 1,
              originX: 'center',
              originY: 'center',
              selectable: false,
              evented: false,
            }));
          }
          const group = new fabric.Group([frame, ...net], {
            left,
            top,
            originX: 'center',
            originY: 'center',
            data: { kind: 'goal', color: stroke, stroke_width: strokeWidth },
          });
          return group;
        };
      }
      if (kind === 'line' || kind === 'line_solid') {
        return (left, top) => new fabric.Line([-55, 0, 55, 0], {
          left, top, originX: 'center', originY: 'center',
          stroke: '#f8fafc', strokeWidth: 3, data: { kind: 'line' },
        });
      }
      if (kind === 'line_dash') {
        return (left, top) => new fabric.Line([-55, 0, 55, 0], {
          left, top, originX: 'center', originY: 'center',
          stroke: '#f8fafc', strokeWidth: 3, strokeDashArray: [12, 8], data: { kind: 'line-dash' },
        });
      }
      if (kind === 'line_dot') {
        return (left, top) => new fabric.Line([-55, 0, 55, 0], {
          left, top, originX: 'center', originY: 'center',
          stroke: '#f8fafc', strokeWidth: 3, strokeDashArray: [2, 9], strokeLineCap: 'round', data: { kind: 'line-dot' },
        });
      }
      if (kind === 'line_double') {
        return (left, top) => new fabric.Group([
          new fabric.Line([-55, -8, 55, -8], { stroke: '#f8fafc', strokeWidth: 3 }),
          new fabric.Line([-55, 8, 55, 8], { stroke: '#f8fafc', strokeWidth: 3 }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'line-double' } });
      }
      if (kind === 'arrow' || kind === 'arrow_solid') {
        return (left, top) => new fabric.Group([
          new fabric.Line([-50, 0, 40, 0], { stroke: '#22d3ee', strokeWidth: 4, originX: 'center', originY: 'center' }),
          new fabric.Triangle({ left: 52, top: 0, width: 18, height: 18, angle: 90, fill: '#22d3ee', originX: 'center', originY: 'center' }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'arrow' } });
      }
      if (kind === 'arrow_dash') {
        return (left, top) => new fabric.Group([
          new fabric.Line([-50, 0, 40, 0], { stroke: '#22d3ee', strokeWidth: 4, strokeDashArray: [12, 8], originX: 'center', originY: 'center' }),
          new fabric.Triangle({ left: 52, top: 0, width: 18, height: 18, angle: 90, fill: '#22d3ee', originX: 'center', originY: 'center' }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'arrow-dash' } });
      }
      if (kind === 'arrow_dot') {
        return (left, top) => new fabric.Group([
          new fabric.Line([-50, 0, 40, 0], { stroke: '#22d3ee', strokeWidth: 4, strokeDashArray: [2, 10], strokeLineCap: 'round', originX: 'center', originY: 'center' }),
          new fabric.Triangle({ left: 52, top: 0, width: 18, height: 18, angle: 90, fill: '#22d3ee', originX: 'center', originY: 'center' }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'arrow-dot' } });
      }
      if (kind === 'arrow_curve') {
        return (left, top) => new fabric.Group([
          new fabric.Path('M -50 22 Q -8 -30 46 10', {
            left: 0,
            top: 0,
            originX: 'center',
            originY: 'center',
            stroke: '#22d3ee',
            fill: '',
            strokeWidth: 4,
            strokeLineCap: 'round',
            strokeLineJoin: 'round',
          }),
          new fabric.Triangle({ left: 58, top: 10, width: 18, height: 18, angle: 122, fill: '#22d3ee', originX: 'center', originY: 'center' }),
        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'arrow-curve' } });
      }
      if (kind === 'shape_circle') {
        return (left, top) => new fabric.Circle({
          left, top, originX: 'center', originY: 'center',
          radius: 46, fill: 'rgba(34,211,238,0.12)', stroke: '#22d3ee', strokeWidth: 3, data: { kind: 'shape-circle' },
        });
      }
      if (kind === 'shape_square') {
        return (left, top) => new fabric.Rect({
          left, top, originX: 'center', originY: 'center',
          width: 96, height: 96, fill: 'rgba(34,211,238,0.12)', stroke: '#22d3ee', strokeWidth: 3, data: { kind: 'shape-square' },
        });
      }
      if (kind === 'shape_rect') {
        return (left, top) => new fabric.Rect({
          left, top, originX: 'center', originY: 'center',
          width: 126, height: 78, rx: 10, ry: 10, fill: 'rgba(34,211,238,0.12)', stroke: '#22d3ee', strokeWidth: 3, data: { kind: 'shape-rect' },
        });
      }
      if (kind === 'shape_triangle') {
        return (left, top) => new fabric.Triangle({
          left, top, originX: 'center', originY: 'center',
          width: 106, height: 92, fill: 'rgba(34,211,238,0.12)', stroke: '#22d3ee', strokeWidth: 3, data: { kind: 'shape-triangle' },
        });
      }
      if (kind === 'shape_diamond') {
        return (left, top) => new fabric.Rect({
          left, top, originX: 'center', originY: 'center',
          width: 94, height: 94, angle: 45, fill: 'rgba(34,211,238,0.12)', stroke: '#22d3ee', strokeWidth: 3, data: { kind: 'shape-diamond' },
        });
      }
      if (kind === 'text') {
        return (left, top) => new fabric.IText('Texto', {
          left, top, originX: 'center', originY: 'center',
          fontSize: 22, fill: '#ffffff', fontWeight: '700', data: { kind: 'text', color: '#ffffff' },
        });
      }
      if (EMOJI_LIBRARY[kind]) {
        return (left, top) => new fabric.Group(
          [
            new fabric.Circle({
              radius: 18,
              originX: 'center',
              originY: 'center',
              left: 0,
              top: 0,
              fill: rgbaFromHex('#22d3ee', 0.16),
              stroke: '#22d3ee',
              strokeWidth: 2,
            }),
            new fabric.Text(EMOJI_LIBRARY[kind], {
              originX: 'center',
              originY: 'center',
              left: 0,
              top: 0,
              fontSize: 28,
            }),
          ],
          {
            left,
            top,
            originX: 'center',
            originY: 'center',
            data: { kind, color: '#22d3ee' },
          },
        );
      }
      return null;
    };

	    const activateFactory = (factory, label, kind = '') => {
	      pendingFactory = factory;
	      pendingKind = safeText(kind || '');
	      Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
	      Array.from(playerBank?.querySelectorAll('button') || []).forEach((button) => button.classList.remove('is-active'));
	      setStatus(`Haz clic en el campo para colocar ${label}. (Shift: varios · Cmd/Ctrl: alinear por centro)`);
	    };

	    const restoreState = () => {
      let parsed = { version: '5.3.0', objects: [] };
      try {
        parsed = JSON.parse(stateInput?.value || '{"version":"5.3.0","objects":[]}');
      } catch (error) {
        parsed = { version: '5.3.0', objects: [] };
      }
      applySerializedState(parsed, { pushHistory: true });
	    };

	    const isGoalkeeperPlayer = (player) => {
	      const pos = safeText(player?.position, '').toLowerCase();
	      if (!pos) return false;
	      return pos.includes('portero') || pos === 'gk' || pos.includes('goalkeeper');
	    };

	    const renderPlayerBank = () => {
	      if (!playerBank) return;
	      playerBank.innerHTML = '';
	      players.slice(0, 25).forEach((player) => {
	        const kind = isGoalkeeperPlayer(player) ? 'goalkeeper_local' : 'player_local';
	        const button = document.createElement('button');
	        button.type = 'button';
	        button.className = 'player-token-bank';
	        const name = document.createElement('span');
	        name.className = 'token-name';
	        name.textContent = shortPlayerName(player.name);
	        const disk = document.createElement('span');
	        disk.className = 'token-disk';
	        const number = document.createElement('span');
	        number.className = 'token-number';
	        number.textContent = kind === 'goalkeeper_local' ? 'GK' : (player.number ? String(player.number).slice(0, 2) : 'J');
	        disk.appendChild(number);
	        button.appendChild(name);
	        button.appendChild(disk);
	        registerDraggableButton(button, () => ({ kind, playerId: String(player.id) }));
		        button.addEventListener('click', () => {
		          Array.from(playerBank.querySelectorAll('button')).forEach((item) => item.classList.remove('is-active'));
		          button.classList.add('is-active');
		          activateFactory(playerTokenFactory(kind, player), safeText(player.name, 'el jugador'), kind);
		        });
	        playerBank.appendChild(button);
	      });
	    };
    const selectTimelineStep = (index) => {
      if (index < 0 || index >= timeline.length) return;
      if (playbackTimer) return;
      persistActiveStepSnapshot();
      activeStepIndex = index;
      loadCanvasSnapshot(timeline[index].canvas_state, () => {
        renderTimeline();
        setStatus(`Editando ${timeline[index].title}.`);
      });
    };
    const addTimelineStep = (duplicateCurrent = false) => {
      persistActiveStepSnapshot();
      const baseState = duplicateCurrent && activeStepIndex >= 0 && timeline[activeStepIndex]
        ? sanitizeLoadedState(timeline[activeStepIndex].canvas_state)
        : serializeCanvasOnly();
      const insertionIndex = activeStepIndex >= 0 ? activeStepIndex + 1 : timeline.length;
      const sourceTitle = duplicateCurrent && activeStepIndex >= 0 && timeline[activeStepIndex]
        ? safeText(timeline[activeStepIndex].title, `Paso ${activeStepIndex + 1}`)
        : '';
      timeline.splice(insertionIndex, 0, {
        title: duplicateCurrent ? `${sourceTitle} copia` : `Paso ${timeline.length + 1}`,
        duration: duplicateCurrent && activeStepIndex >= 0 && timeline[activeStepIndex] ? clamp(Number(timeline[activeStepIndex].duration) || 3, 1, 20) : 3,
        canvas_state: baseState,
      });
      activeStepIndex = insertionIndex;
      renderTimeline();
      pushHistory();
      setStatus(duplicateCurrent ? 'Paso duplicado.' : 'Paso añadido.');
    };
    const removeTimelineStep = () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline.splice(activeStepIndex, 1);
      if (!timeline.length) {
        activeStepIndex = -1;
        renderTimeline();
        pushHistory();
        setStatus('Paso eliminado.');
        return;
      }
      activeStepIndex = clamp(activeStepIndex, 0, timeline.length - 1);
      loadCanvasSnapshot(timeline[activeStepIndex].canvas_state, () => {
        renderTimeline();
        pushHistory();
        setStatus('Paso eliminado.');
      });
    };
    const stopPlayback = (restore = true) => {
      if (playbackTimer) {
        window.clearTimeout(playbackTimer);
        playbackTimer = null;
      }
      if (playStepButton) playStepButton.textContent = 'Reproducir';
      if (restore && playbackRestoreState) {
        const savedState = playbackRestoreState;
        playbackRestoreState = null;
        applySerializedState(savedState);
        return;
      }
      playbackRestoreState = null;
      renderTimeline();
    };
    const playTimeline = () => {
      if (playbackTimer) {
        stopPlayback(true);
        setStatus('Reproducción detenida.');
        return;
      }
      if (!timeline.length) {
        setStatus('Añade al menos un paso para reproducir la tarea.', true);
        return;
      }
      persistActiveStepSnapshot();
      playbackRestoreState = serializeState();
      let playIndex = 0;
      if (playStepButton) playStepButton.textContent = 'Detener';
      const runNext = () => {
        if (playIndex >= timeline.length) {
          stopPlayback(true);
          setStatus('Animación finalizada.');
          return;
        }
        activeStepIndex = playIndex;
        loadCanvasSnapshot(timeline[playIndex].canvas_state, () => {
          renderTimeline();
          setStatus(`Reproduciendo ${timeline[playIndex].title}.`);
          playbackTimer = window.setTimeout(() => {
            playIndex += 1;
            runNext();
          }, clamp(Number(timeline[playIndex].duration) || 3, 1, 20) * 1000);
        });
      };
      runNext();
    };

	    const buildPreviewData = () => new Promise((resolve) => {
      const sourceWidth = Math.round(canvas.getWidth());
      const sourceHeight = Math.round(canvas.getHeight());
      // En iPad conviene limitar el tamaño para que no bloquee el hilo principal.
      const maxPreviewWidth = 720;
      const ratio = sourceWidth > maxPreviewWidth ? (maxPreviewWidth / sourceWidth) : 1;
      const output = document.createElement('canvas');
      output.width = Math.max(320, Math.round(sourceWidth * ratio));
      output.height = Math.max(180, Math.round(sourceHeight * ratio));
      const context = output.getContext('2d');
      if (!context) {
        resolve('');
        return;
      }
      // Fondo sólido para que la preview y el PDF no muestren "barras" por transparencia.
      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, output.width, output.height);
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
    const applyLivePreview = (dataUrl) => {
      if (!livePreviewImg || !livePreviewPlaceholder) return;
      if (!dataUrl) {
        livePreviewImg.hidden = true;
        livePreviewPlaceholder.hidden = false;
        return;
      }
      livePreviewImg.src = dataUrl;
      livePreviewImg.hidden = false;
      livePreviewPlaceholder.hidden = true;
    };
	    const refreshLivePreview = () => {
	      if (exportInFlight) return;
	      window.clearTimeout(previewRefreshTimer);
	      previewRefreshTimer = window.setTimeout(async () => {
	        if (previewBuildInFlight) return;
        previewBuildInFlight = true;
        try {
          const dataUrl = await buildPreviewData();
          if (previewInput) previewInput.value = dataUrl;
          applyLivePreview(dataUrl);
        } finally {
          previewBuildInFlight = false;
        }
      }, 650);
    };

    const activateSidePane = (key) => {
      sideTabs.forEach((tab) => {
        const active = safeText(tab.dataset.pane) === key;
        tab.classList.toggle('is-active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      sidePanes.forEach((pane) => pane.classList.toggle('is-active', safeText(pane.dataset.pane) === key));
    };
    sideTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const key = safeText(tab.dataset.pane);
        if (key) activateSidePane(key);
      });
    });

    const extractAssignedPlayerIdsFromState = (state) => {
      const ids = new Set();
      const collectFromCanvasState = (canvasState) => {
        if (!canvasState || typeof canvasState !== 'object') return;
        const objects = Array.isArray(canvasState.objects) ? canvasState.objects : [];
        objects.forEach((obj) => {
          const kind = safeText(obj?.data?.kind);
          if (kind === 'token') {
            const pid = obj?.data?.playerId || '';
            const parsed = Number.parseInt(String(pid), 10);
            if (Number.isFinite(parsed) && parsed > 0) ids.add(parsed);
          }
        });
      };
      collectFromCanvasState(state);
      const timeline = Array.isArray(state?.timeline) ? state.timeline : [];
      timeline.forEach((step) => collectFromCanvasState(step?.canvas_state));
      return Array.from(ids).sort((a, b) => a - b);
    };

    const syncAssignedPlayersHidden = (state) => {
      if (!assignedHidden) return;
      assignedHidden.innerHTML = '';
      const ids = extractAssignedPlayerIdsFromState(state);
      ids.forEach((id) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'assigned_player_ids';
        input.value = String(id);
        assignedHidden.appendChild(input);
      });
      if (assignedSummary) {
        if (!ids.length) {
          assignedSummary.textContent = 'No hay jugadores detectados todavía. Usa chapas de la plantilla para que se asignen automáticamente.';
          return;
        }
        const labelById = new Map(players.map((p) => [Number.parseInt(String(p.id), 10), p]));
        const chunks = ids
          .map((id) => {
            const p = labelById.get(id);
            if (!p) return `#${id}`;
            const num = p.number ? `#${String(p.number).slice(0, 2)} · ` : '';
            return `${num}${shortPlayerName(p.name)}`;
          })
          .slice(0, 10);
        const extra = Math.max(0, ids.length - chunks.length);
        assignedSummary.textContent = extra ? `${chunks.join(', ')} y ${extra} más.` : chunks.join(', ');
      }
    };
    const syncHiddenBuilderFields = async () => {
      if (legacyPlayersInput && playerCountInput) legacyPlayersInput.value = playerCountInput.value || '';
      const stateObj = serializeState();
      syncAssignedPlayersHidden(stateObj);
      if (stateInput) stateInput.value = JSON.stringify(stateObj);
      if (widthInput) widthInput.value = String(Math.round(canvas.getWidth()));
      if (heightInput) heightInput.value = String(Math.round(canvas.getHeight()));
      const dataUrl = await buildPreviewData();
      if (previewInput) previewInput.value = dataUrl;
      applyLivePreview(dataUrl);
      return dataUrl;
    };
    const submitPrintPreview = async (style) => {
      const actionUrl = form.dataset.pdfPreviewUrl;
      if (!actionUrl) {
        setStatus('No se encontró la ruta de previsualización PDF.', true);
        return;
      }

      // Los navegadores bloquean pestañas abiertas tras un await. Abrimos la pestaña de destino
      // de forma síncrona (gesto del click) y luego enviamos el POST cuando la pizarra esté serializada.
      const targetName = `tpad_pdf_${Date.now()}`;
      let previewWin = null;
      try {
        previewWin = window.open('about:blank', targetName);
      } catch (error) {
        previewWin = null;
      }
      if (previewWin && previewWin.document) {
        previewWin.document.open();
        previewWin.document.write('<!doctype html><html lang="es"><meta charset="utf-8"><title>Generando PDF…</title><body style="font-family:system-ui,Segoe UI,Arial,sans-serif;padding:24px;"><h1 style="font-size:16px;margin:0 0 8px;">Generando PDF…</h1><p style="margin:0;color:#334155;">En unos segundos aparecerá el documento.</p></body></html>');
        previewWin.document.close();
      }

      await syncHiddenBuilderFields();
      const tempForm = document.createElement('form');
      tempForm.method = 'post';
      // actionUrl puede incluir query (?user=... o ?workspace=...). Si concatenamos "?style="
      // rompemos el query string y el backend no detecta el workspace, devolviendo 403.
      const targetStyle = safeText(style, 'uefa');
      let resolvedAction = '';
      try {
        const url = new URL(actionUrl, window.location.origin);
        url.searchParams.set('style', targetStyle || 'uefa');
        // Si el editor se está usando con ?workspace=... en la URL actual, lo propagamos
        // para que el PDF preview siempre resuelva el workspace correctamente.
        const current = new URL(window.location.href);
        const currentWs = safeText(current.searchParams.get('workspace'));
        if (currentWs && !safeText(url.searchParams.get('workspace'))) {
          url.searchParams.set('workspace', currentWs);
        }
        resolvedAction = url.toString();
      } catch (error) {
        resolvedAction = `${actionUrl}${actionUrl.includes('?') ? '&' : '?'}style=${encodeURIComponent(targetStyle || 'uefa')}`;
      }
      tempForm.action = resolvedAction;
      tempForm.target = previewWin ? targetName : '_self';
      const payload = new FormData(form);
      payload.forEach((value, key) => {
        if (value instanceof File) return;
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = String(value);
        tempForm.appendChild(input);
      });
      document.body.appendChild(tempForm);
      tempForm.submit();
      tempForm.remove();
    };

	    syncOrientationUi();
	    syncZoomUi();
	    fitCanvas();
	    setPreset(presetSelect.value || 'full_pitch');
	    restoreState();
	    renderLayers();
	    runWhenIdle(() => renderPlayerBank(), 1100);
    try {
      syncAssignedPlayersHidden(serializeState());
    } catch (error) {
      // ignore
    }
    runWhenIdle(() => refreshLivePreview(), 1100);

    let draftSaveTimer = null;
    const persistDraftNow = (reason) => {
      if (!canUseStorage || !draftKey || saveSuccess) return;
      const elements = Array.from(form.elements || []);
      const fields = {};
      const checkboxBuckets = new Map();
      elements.forEach((el) => {
        if (!el || !el.name) return;
        const key = safeText(el.name);
        if (!key) return;
        if (key === 'csrfmiddlewaretoken' || key === 'draw_canvas_preview_data') return;
        const type = safeText(el.type);
        if (type === 'file' || type === 'password' || type === 'submit' || type === 'button' || type === 'reset') return;
        if (type === 'checkbox') {
          const bucket = checkboxBuckets.get(key) || [];
          if (el.checked) bucket.push(safeText(el.value) || 'on');
          checkboxBuckets.set(key, bucket);
          return;
        }
        if (type === 'radio') {
          if (el.checked) fields[key] = safeText(el.value);
          return;
        }
        if (el.tagName === 'SELECT' && el.multiple) {
          fields[key] = Array.from(el.selectedOptions || []).map((opt) => safeText(opt.value));
          return;
        }
        fields[key] = el.value == null ? '' : String(el.value);
      });
      checkboxBuckets.forEach((bucket, key) => {
        fields[key] = bucket;
      });
      try {
        fields.draw_canvas_state = JSON.stringify(serializeState());
      } catch (error) {
        // leave current hidden value
      }
      try {
        fields.draw_canvas_width = String(Math.round(canvas.getWidth()));
        fields.draw_canvas_height = String(Math.round(canvas.getHeight()));
      } catch (error) {
        // ignore
      }
      const payload = {
        v: 1,
        url: currentDraftUrl,
        updated_at: new Date().toISOString(),
        reason: safeText(reason),
        fields,
      };
      try {
        window.localStorage.setItem(draftKey, JSON.stringify(payload));
      } catch (error) {
        // ignore (quota / privacy mode)
      }
    };
    const scheduleDraftSave = (reason) => {
      if (!canUseStorage || !draftKey || saveSuccess) return;
      window.clearTimeout(draftSaveTimer);
      draftSaveTimer = window.setTimeout(() => persistDraftNow(reason || 'auto'), 900);
    };

    if (canUseStorage && draftKey && !saveSuccess) {
      form.addEventListener('input', () => scheduleDraftSave('input'));
      form.addEventListener('change', () => scheduleDraftSave('change'));
    }

    if (keepaliveUrl) {
      const ping = async () => {
        try {
          const response = await fetch(keepaliveUrl, { credentials: 'same-origin' });
          const redirectedToLogin = response.redirected && /\/login\/?$/.test(new URL(response.url).pathname);
          if (redirectedToLogin || response.status === 401 || response.status === 403) {
            persistDraftNow('session-expired');
            setDraftAlert('Sesión caducada. Se guardó un borrador local; inicia sesión y vuelve a esta pestaña.');
            return false;
          }
          return true;
        } catch (error) {
          return true;
        }
      };
      // Primer ping pronto para renovar el vencimiento tras abrir el editor.
      window.setTimeout(() => {
        ping();
      }, 25_000);
      const keepaliveTimer = window.setInterval(async () => {
        const ok = await ping();
        if (!ok) window.clearInterval(keepaliveTimer);
      }, 240_000);
    }

	    canvas.on('object:modified', () => {
	      if (canvas.__loading) return;
	      persistActiveStepSnapshot();
	      pushHistory();
	      syncInspector();
	      renderLayers();
	      refreshLivePreview();
	      scheduleDraftSave('canvas');
	    });
	    canvas.on('object:added', () => {
	      if (!canvas.__loading) {
	        persistActiveStepSnapshot();
	        pushHistory();
	        renderLayers();
	      }
	      refreshLivePreview();
	      scheduleDraftSave('canvas');
	    });
	    canvas.on('object:removed', () => {
	      if (!canvas.__loading) {
	        persistActiveStepSnapshot();
	        pushHistory();
	        renderLayers();
	      }
	      refreshLivePreview();
	      scheduleDraftSave('canvas');
	    });
		    canvas.on('object:moving', (event) => {
		      const target = event?.target;
		      const rawEvent = event?.e;
		      if (!target || !rawEvent) return;
		      const targetCenter = target.getCenterPoint();
		      const isMod = !!(rawEvent.ctrlKey || rawEvent.metaKey);
		      const snapGrid = shouldSnapToGridForEvent(rawEvent);
		      let next = { x: targetCenter.x, y: targetCenter.y };
		      let didSnap = false;
		      if (isMod) {
		        const snapped = snapPointToCenters(next, target, 10);
		        if (snapped.snappedX || snapped.snappedY) {
		          next = { x: snapped.x, y: snapped.y };
		          didSnap = true;
		        }
		      } else if (snapGrid) {
		        next = snapPointToGrid(next);
		        didSnap = true;
		      }
		      if (!didSnap) return;
		      target.setPositionByOrigin(new fabric.Point(next.x, next.y), 'center', 'center');
		      target.setCoords();
		    });

	    const buildCompositeCanvas = async (options = {}) => {
	      const sourceWidth = Math.round(canvas.getWidth());
	      const sourceHeight = Math.round(canvas.getHeight());
	      const maxWidth = clamp(Number(options.maxWidth) || sourceWidth, 320, 4096);
	      const ratio = sourceWidth > maxWidth ? (maxWidth / sourceWidth) : 1;
	      const output = document.createElement('canvas');
	      output.width = Math.max(320, Math.round(sourceWidth * ratio));
	      output.height = Math.max(180, Math.round(sourceHeight * ratio));
	      const context = output.getContext('2d');
	      if (!context) return null;
	      context.fillStyle = '#ffffff';
	      context.fillRect(0, 0, output.width, output.height);
	      const svgMarkup = new XMLSerializer().serializeToString(svgSurface);
	      const blob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' });
	      const blobUrl = URL.createObjectURL(blob);
	      const image = new Image();
	      await new Promise((resolve) => {
	        image.onload = resolve;
	        image.onerror = resolve;
	        image.src = blobUrl;
	      });
	      try { URL.revokeObjectURL(blobUrl); } catch (error) { /* ignore */ }
	      try {
	        context.drawImage(image, 0, 0, output.width, output.height);
	      } catch (error) {
	        // ignore
	      }
	      context.drawImage(canvas.lowerCanvasEl, 0, 0, output.width, output.height);
	      return output;
	    };

	    const downloadBlob = (blob, filename) => {
	      if (!blob) return;
	      const url = URL.createObjectURL(blob);
	      const link = document.createElement('a');
	      link.href = url;
	      link.download = filename || `export_${Date.now()}`;
	      document.body.appendChild(link);
	      link.click();
	      link.remove();
	      window.setTimeout(() => {
	        try { URL.revokeObjectURL(url); } catch (error) { /* ignore */ }
	      }, 2_500);
	    };

	    const canvasToBlob = (c, type = 'image/png', quality = 0.92) => new Promise((resolve) => {
	      try {
	        c.toBlob((blob) => resolve(blob), type, quality);
	      } catch (error) {
	        resolve(null);
	      }
	    });

	    const fileSafeSlug = (value) => safeText(value || '')
	      .toLowerCase()
	      .replace(/[^a-z0-9]+/g, '-')
	      .replace(/^-+|-+$/g, '')
	      .slice(0, 60) || 'tarea';

	    const exportCurrentPng = async (maxWidth) => {
	      const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
	      const composite = await buildCompositeCanvas({ maxWidth });
	      if (!composite) {
	        setStatus('No se pudo generar la imagen.', true);
	        return;
	      }
	      const blob = await canvasToBlob(composite, 'image/png', 0.92);
	      if (!blob) {
	        setStatus('No se pudo generar el PNG.', true);
	        return;
	      }
	      downloadBlob(blob, `${title}.png`);
	      setStatus('PNG descargado.');
	    };

	    const exportStateJson = () => {
	      const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
	      const payload = serializeState();
	      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
	      downloadBlob(blob, `${title}.json`);
	      setStatus('JSON descargado.');
	    };
	    canvas.on('selection:created', syncInspector);
	    canvas.on('selection:updated', syncInspector);
	    canvas.on('selection:cleared', syncInspector);
	    canvas.on('selection:created', renderLayers);
	    canvas.on('selection:updated', renderLayers);
	    canvas.on('selection:cleared', renderLayers);
	    const syncInspectorDock = () => {
	      const active = activeInspectableObject();
	      if (!active) return;
	      dockInspectorIntoPanel(panelKeyForObject(active));
	    };
    canvas.on('selection:created', syncInspectorDock);
    canvas.on('selection:updated', syncInspectorDock);
		    canvas.on('mouse:down', (event) => {
		      if (!pendingFactory || event.target) return;
		      const raw = canvas.getPointer(event.e);
		      const base = { x: Number(raw?.x) || 0, y: Number(raw?.y) || 0 };
		      const e = event?.e;
		      const isMod = !!(e && (e.ctrlKey || e.metaKey));
		      const snapGrid = shouldSnapToGridForEvent(e);
		      const isShift = !!(e && e.shiftKey);
		      let pointer = base;

		      if (isMod) {
		        pointer = snapPointToCenters(base, null, 10);
		      } else if (snapGrid) {
		        pointer = snapPointToGrid(base);
		      } else if (pendingKind && lastPlacedByKind.has(pendingKind)) {
		        // Snap suave a la última colocación del mismo tipo (útil para alinear conos/jugadores).
		        const last = lastPlacedByKind.get(pendingKind);
		        const threshold = 16;
	        pointer = {
	          x: Math.abs(base.x - last.x) <= threshold ? last.x : base.x,
	          y: Math.abs(base.y - last.y) <= threshold ? last.y : base.y,
	        };
	      }

	      addObject(objectAtPointer(pendingFactory, pointer));
	      if (pendingKind) lastPlacedByKind.set(pendingKind, { x: pointer.x, y: pointer.y, ts: Date.now() });
	      if (!isShift) clearPendingPlacement();
	      setStatus(isShift ? 'Elemento colocado. Sigue colocando (Shift activo).' : 'Elemento colocado.');
	    });
    canvas.on('mouse:down', (event) => {
      const target = event.target;
      if (!target || !isBackgroundShape(target) || !event.e || event.e.shiftKey) return;
      try {
        const wasEvented = target.evented !== false;
        target.evented = false;
        const underneath = canvas.findTarget(event.e, true);
        target.evented = wasEvented;
        if (underneath && underneath !== target) {
          canvas.setActiveObject(underneath);
          canvas.requestRenderAll();
          syncInspector();
        }
      } catch (error) {
        // ignore
      }
    });

    stage.addEventListener('dragover', (event) => {
      if (!event.dataTransfer?.types?.includes(DRAG_MIME) && !event.dataTransfer?.types?.includes('text/plain')) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
      stage.classList.add('is-drop-target');
    });
    stage.addEventListener('dragleave', (event) => {
      if (event.currentTarget !== stage) return;
      stage.classList.remove('is-drop-target');
    });
    stage.addEventListener('drop', (event) => {
      const raw = event.dataTransfer?.getData(DRAG_MIME) || event.dataTransfer?.getData('text/plain');
      if (!raw) return;
      event.preventDefault();
      stage.classList.remove('is-drop-target');
      let payload = null;
      try {
        payload = JSON.parse(raw);
      } catch (error) {
        payload = null;
      }
      if (!payload) return;
      addPayloadAtPointer(payload, pointerFromStageEvent(event));
    });

    timelineList?.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-step-index]');
      if (!button) return;
      selectTimelineStep(Number(button.dataset.stepIndex));
    });
    addStepButton?.addEventListener('click', () => addTimelineStep(false));
    duplicateStepButton?.addEventListener('click', () => addTimelineStep(true));
    removeStepButton?.addEventListener('click', removeTimelineStep);
    playStepButton?.addEventListener('click', playTimeline);
    stepTitleInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(stepTitleInput.value, `Paso ${activeStepIndex + 1}`);
      renderTimeline();
    });
    stepTitleInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(stepTitleInput.value, `Paso ${activeStepIndex + 1}`);
      pushHistory();
    });
    stepDurationInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(stepDurationInput.value) || 3, 1, 20);
      renderTimeline();
    });
    stepDurationInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(stepDurationInput.value) || 3, 1, 20);
      pushHistory();
    });

    scaleXInput?.addEventListener('input', () => {
      applyToActiveFlexibleObject((active) => {
        active.scaleX = clampScale(Number(scaleXInput.value) / 100);
      }, 'Longitud actualizada.');
    });
    scaleYInput?.addEventListener('input', () => {
      applyToActiveFlexibleObject((active) => {
        active.scaleY = clampScale(Number(scaleYInput.value) / 100);
      }, 'Altura actualizada.');
    });
    rotationInput?.addEventListener('input', () => {
      applyToActiveFlexibleObject((active) => {
        active.rotate(Number(rotationInput.value) || 0);
      }, 'Orientación actualizada.');
    });
    colorInput?.addEventListener('input', () => {
      applyToActiveFlexibleObject((active) => {
        applyObjectColor(active, colorInput.value || '#22d3ee');
      }, 'Color actualizado.');
    });
    strokeWidthInput?.addEventListener('input', () => {
      applyToActiveFlexibleObject((active) => {
        applyObjectStrokeWidth(active, Number(strokeWidthInput.value) || 3);
      }, 'Grosor actualizado.');
    });
		    selectionToolbar?.addEventListener('click', (event) => {
		      const button = event.target.closest('button');
		      if (!button) return;
		      const inspectorAction = safeText(button.dataset.inspectorAction);
		      if (inspectorAction === 'duplicate') {
		        duplicateActiveObject();
		        return;
		      }
	      if (inspectorAction === 'copy') {
	        copyActiveObject();
	        return;
	      }
		      if (inspectorAction === 'paste') {
		        pasteClipboardObject();
		        return;
		      }
		      const scalePreset = Number(button.dataset.scalePreset);
		      if (!Number.isNaN(scalePreset) && button.dataset.scalePreset !== undefined) {
		        const next = clampScale(scalePreset / 100);
		        if (scaleXInput) scaleXInput.value = String(scalePreset);
		        if (scaleYInput) scaleYInput.value = String(scalePreset);
		        applyToActiveFlexibleObject((active) => {
		          active.set({ scaleX: next, scaleY: next });
		        }, `Tamaño: ${scalePreset}%.`);
		        return;
		      }
		      const strokePreset = Number(button.dataset.strokePreset);
		      if (!Number.isNaN(strokePreset) && button.dataset.strokePreset !== undefined) {
		        if (strokeWidthInput) strokeWidthInput.value = String(strokePreset);
		        applyToActiveFlexibleObject((active) => {
		          applyObjectStrokeWidth(active, strokePreset);
		        }, `Grosor: ${strokePreset}.`);
		        return;
		      }
		      const colorValue = safeText(button.dataset.color);
		      if (colorValue) {
		        if (colorInput) colorInput.value = colorValue;
		        applyToActiveFlexibleObject((active) => {
          applyObjectColor(active, colorValue);
        }, 'Color actualizado.');
        return;
      }
      const rotateStep = Number(button.dataset.rotateStep);
      if (!Number.isNaN(rotateStep) && button.dataset.rotateStep !== undefined) {
        applyToActiveFlexibleObject((active) => {
          active.rotate((Number(active.angle) || 0) + rotateStep);
        }, 'Orientación actualizada.');
        return;
      }
      const nudgeX = Number(button.dataset.nudgeX);
      const nudgeY = Number(button.dataset.nudgeY);
      if ((!Number.isNaN(nudgeX) || !Number.isNaN(nudgeY)) && (button.dataset.nudgeX !== undefined || button.dataset.nudgeY !== undefined)) {
        applyToActiveFlexibleObject((active) => {
          active.left = clamp((Number(active.left) || 0) + (Number.isNaN(nudgeX) ? 0 : nudgeX), 12, canvas.getWidth() - 12);
          active.top = clamp((Number(active.top) || 0) + (Number.isNaN(nudgeY) ? 0 : nudgeY), 12, canvas.getHeight() - 12);
        }, 'Posición actualizada.');
      }
    });

    const handleCanvasAction = (action) => {
      if (action === 'select') {
        pendingFactory = null;
        Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((item) => item.classList.remove('is-active'));
        Array.from(playerBank?.querySelectorAll('button') || []).forEach((item) => item.classList.remove('is-active'));
        setStatus('Modo selección activo.');
        return true;
      }
      if (action === 'undo') return performUndo();
      if (action === 'redo') return performRedo();
	      if (action === 'delete') {
	        const active = canvas.getActiveObject();
	        if (!active) return false;
	        if (active.type === 'activeSelection' && typeof active.getObjects === 'function') {
	          const objects = active.getObjects();
	          canvas.discardActiveObject();
	          objects.forEach((obj) => {
	            if (obj) canvas.remove(obj);
	          });
	        } else {
	          canvas.remove(active);
	          canvas.discardActiveObject();
	        }
	        canvas.requestRenderAll();
	        pushHistory();
	        syncInspector();
	        setStatus('Elemento eliminado.');
	        return true;
	      }
      if (action === 'duplicate') {
        duplicateActiveObject();
        return true;
      }
      if (action === 'clear') {
        canvas.getObjects().slice().forEach((item) => canvas.remove(item));
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        pushHistory();
        syncInspector();
        setStatus('Pizarra limpiada.');
        return true;
      }
      return false;
    };

	    toolStrip?.addEventListener('click', (event) => {
	      const button = event.target.closest('button');
	      if (!button) return;
      const action = safeText(button.dataset.action);
      const add = safeText(button.dataset.add);
	      if (action && handleCanvasAction(action)) return;
	      if (!add) return;
	      Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
	      button.classList.add('is-active');
		      if (add === 'player_local') activateFactory(playerTokenFactory('player_local', null), 'un jugador local', 'player_local');
		      else if (add === 'player_rival') activateFactory(playerTokenFactory('player_rival', null), 'un jugador rival', 'player_rival');
		      else if (add === 'player_away') activateFactory(playerTokenFactory('player_away', null), 'un jugador con segunda equipación', 'player_away');
		      else if (add === 'goalkeeper_local') activateFactory(playerTokenFactory('goalkeeper_local', null), 'un portero', 'goalkeeper_local');
		      else activateFactory(simpleFactory(add), RESOURCE_LABELS[add] || add, add);
		    });

	    libraryPane?.addEventListener('click', (event) => {
	      const button = event.target.closest('button[data-add]');
	      if (!button) return;
	      const add = safeText(button.dataset.add);
	      if (!add) return;
	      Array.from(libraryPane.querySelectorAll('button[data-add]')).forEach((item) => item.classList.remove('is-active'));
	      button.classList.add('is-active');
	      if (add === 'player_local') activateFactory(playerTokenFactory('player_local', null), 'un jugador local', 'player_local');
	      else if (add === 'player_rival') activateFactory(playerTokenFactory('player_rival', null), 'un jugador rival', 'player_rival');
	      else if (add === 'player_away') activateFactory(playerTokenFactory('player_away', null), 'un jugador con segunda equipación', 'player_away');
	      else if (add === 'goalkeeper_local') activateFactory(playerTokenFactory('goalkeeper_local', null), 'un portero', 'goalkeeper_local');
	      else activateFactory(simpleFactory(add), RESOURCE_LABELS[add] || add, add);
	    });
	    syncInspector();

			    document.addEventListener('keydown', (event) => {
			      const key = String(event.key || '').toLowerCase();
			      const isMod = event.metaKey || event.ctrlKey;
				      const isShift = !!event.shiftKey;
				      const el = document.activeElement;
				      const tag = (el && el.tagName) ? el.tagName.toLowerCase() : '';
				      if (tag === 'input' || tag === 'textarea' || tag === 'select' || (el && el.isContentEditable)) return;
				      if (key === 'escape' && !commandMenu?.hidden) {
				        setCommandMenuOpen(false);
				        event.preventDefault();
				        return;
				      }
				      if ((event.code === 'Space' || key === ' ') && viewportEl) {
				        // Modo "mano": espacio + arrastrar para desplazar el viewport (como Camelot).
				        if (!spacePanArmed) {
				          spacePanArmed = true;
				          viewportEl.classList.add('is-hand');
				        }
				        event.preventDefault();
				        return;
				      }
				      if (!isMod && key === 'g') {
				        event.preventDefault();
				        toggleGridVisible();
				        return;
				      }
				      if (isMod && key === 'g') {
				        event.preventDefault();
				        if (isShift) ungroupSelection();
				        else groupSelection();
				        return;
			      }
			      if (isMod && key === 'l') {
			        event.preventDefault();
			        toggleLockSelection();
			        return;
			      }
			      if (isMod && (event.key === '[' || event.key === ']')) {
			        event.preventDefault();
			        setSelectionLayer(event.key === ']' ? 'front' : 'back');
			        return;
			      }
	        if (isMod && key === 's') {
	          event.preventDefault();
	          persistDraftNow('shortcut-save');
	          setStatus('Guardando…');
          form.requestSubmit();
          return;
        }
        if (isMod && key === 'z' && !isShift) {
          event.preventDefault();
          performUndo();
          return;
        }
        if (isMod && (key === 'y' || (key === 'z' && isShift))) {
          event.preventDefault();
          performRedo();
          return;
        }
        if (key === 'escape') {
          event.preventDefault();
          pendingFactory = null;
          Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((item) => item.classList.remove('is-active'));
          Array.from(playerBank?.querySelectorAll('button') || []).forEach((item) => item.classList.remove('is-active'));
          canvas.discardActiveObject();
          canvas.requestRenderAll();
          syncInspector();
          setStatus('Modo selección activo.');
          return;
        }
        if (key === 'delete' || key === 'backspace') {
          const did = handleCanvasAction('delete');
          if (did) event.preventDefault();
          return;
        }
	      if (isMod && key === 'd') {
	        event.preventDefault();
	        duplicateActiveObject();
	      }
	      if (isMod && key === 'c') {
	        event.preventDefault();
	        copyActiveObject();
	      }
		      if (isMod && key === 'v') {
		        event.preventDefault();
		        pasteClipboardObject();
		      }
		    });

		    document.addEventListener('keyup', (event) => {
		      const key = String(event.key || '').toLowerCase();
		      if (!(event.code === 'Space' || key === ' ')) return;
		      spacePanArmed = false;
		      spacePanning = false;
		      spacePanStart = null;
		      viewportEl?.classList.remove('is-hand');
		      viewportEl?.classList.remove('is-grabbing');
		    });

		    const startSpacePan = (event) => {
		      if (!viewportEl || !spacePanArmed) return;
		      // Solo tiene sentido si el viewport puede desplazarse.
		      const canScroll = viewportEl.scrollWidth > viewportEl.clientWidth || viewportEl.scrollHeight > viewportEl.clientHeight;
		      if (!canScroll) return;
		      spacePanning = true;
		      spacePanStart = {
		        x: Number(event.clientX) || 0,
		        y: Number(event.clientY) || 0,
		        scrollLeft: viewportEl.scrollLeft,
		        scrollTop: viewportEl.scrollTop,
		      };
		      viewportEl.classList.add('is-grabbing');
		      event.preventDefault();
		      event.stopPropagation();
		    };
		    const moveSpacePan = (event) => {
		      if (!viewportEl || !spacePanning || !spacePanStart) return;
		      const dx = (Number(event.clientX) || 0) - spacePanStart.x;
		      const dy = (Number(event.clientY) || 0) - spacePanStart.y;
		      viewportEl.scrollLeft = spacePanStart.scrollLeft - dx;
		      viewportEl.scrollTop = spacePanStart.scrollTop - dy;
		      event.preventDefault();
		      event.stopPropagation();
		    };
		    const stopSpacePan = (event) => {
		      if (!viewportEl || !spacePanning) return;
		      spacePanning = false;
		      spacePanStart = null;
		      viewportEl.classList.remove('is-grabbing');
		      if (event) {
		        event.preventDefault();
		        event.stopPropagation();
		      }
		    };
		    viewportEl?.addEventListener('mousedown', startSpacePan, true);
		    window.addEventListener('mousemove', moveSpacePan, true);
		    window.addEventListener('mouseup', stopSpacePan, true);

	    commandBar?.addEventListener('click', (event) => {
	      const button = event.target.closest('button');
	      if (!button) return;
      const action = safeText(button.dataset.action);
      if (!action) return;
      handleCanvasAction(action);
    });

    Array.from(document.querySelectorAll('[data-print-style]')).forEach((button) => {
      button.addEventListener('click', () => submitPrintPreview(button.dataset.printStyle || 'uefa'));
    });

	    Array.from(document.querySelectorAll('.resource-strip button[data-add]')).forEach((button) => {
	      registerDraggableButton(button, () => ({ kind: safeText(button.dataset.add) }));
	    });

	    const loadCanvasSnapshotAsync = (rawState) => new Promise((resolve) => {
	      loadCanvasSnapshot(rawState, () => resolve(true));
	    });
	    const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

	    exportPngBtn?.addEventListener('click', async () => {
	      if (exportInFlight) return;
	      exportInFlight = true;
	      stopPlayback(true);
	      try {
	        setStatus('Generando PNG…');
	        await exportCurrentPng(canvas.getWidth());
	      } finally {
	        exportInFlight = false;
	        refreshLivePreview();
	      }
	    });
	    exportPngHdBtn?.addEventListener('click', async () => {
	      if (exportInFlight) return;
	      exportInFlight = true;
	      stopPlayback(true);
	      try {
	        setStatus('Generando PNG (HD)…');
	        await exportCurrentPng(1280);
	      } finally {
	        exportInFlight = false;
	        refreshLivePreview();
	      }
	    });
	    exportJsonBtn?.addEventListener('click', () => {
	      if (exportInFlight) return;
	      stopPlayback(true);
	      exportStateJson();
	    });
	    exportStepsBtn?.addEventListener('click', async () => {
	      if (exportInFlight) return;
	      exportInFlight = true;
	      stopPlayback(true);
	      const saved = serializeState();
	      try {
	        persistActiveStepSnapshot();
	        if (!timeline.length) {
	          setStatus('No hay pasos. Descargando PNG actual…');
	          await exportCurrentPng(1280);
	          return;
	        }
	        const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
	        for (let i = 0; i < timeline.length; i += 1) {
	          const step = timeline[i];
	          setStatus(`Exportando PNG ${i + 1}/${timeline.length}…`);
	          await loadCanvasSnapshotAsync(step.canvas_state);
	          const composite = await buildCompositeCanvas({ maxWidth: 1280 });
	          if (!composite) continue;
	          const blob = await canvasToBlob(composite, 'image/png', 0.92);
	          if (blob) downloadBlob(blob, `${title}_paso_${String(i + 1).padStart(2, '0')}.png`);
	          // Pequeña pausa para que el navegador no bloquee múltiples descargas.
	          await sleep(240);
	        }
	        setStatus('Exportación de pasos completada.');
	      } finally {
	        applySerializedState(saved);
	        exportInFlight = false;
	        refreshLivePreview();
	      }
	    });

	    exportWebmBtn?.addEventListener('click', async () => {
	      if (exportInFlight) return;
	      exportInFlight = true;
	      stopPlayback(true);
	      const saved = serializeState();
	      try {
	        persistActiveStepSnapshot();
	        const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
	        const sourceW = Math.round(canvas.getWidth());
	        const sourceH = Math.round(canvas.getHeight());
	        const outW = 1280;
	        const scale = outW / Math.max(1, sourceW);
	        const outH = Math.max(180, Math.round(sourceH * scale));
	        const exportCanvas = document.createElement('canvas');
	        exportCanvas.width = outW;
	        exportCanvas.height = outH;
	        const ctx = exportCanvas.getContext('2d');
	        if (!ctx) {
	          setStatus('No se pudo iniciar el export de vídeo.', true);
	          return;
	        }

	        if (!('MediaRecorder' in window) || typeof exportCanvas.captureStream !== 'function') {
	          setStatus('Tu navegador no soporta exportar vídeo desde la pizarra.', true);
	          return;
	        }

	        const pickMime = () => {
	          const candidates = [
	            'video/webm;codecs=vp9',
	            'video/webm;codecs=vp8',
	            'video/webm',
	          ];
	          return candidates.find((m) => window.MediaRecorder && window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(m)) || '';
	        };
	        const mimeType = pickMime();

	        // Pre-render del fondo (SVG) para no serializarlo en cada frame.
	        const svgMarkup = new XMLSerializer().serializeToString(svgSurface);
	        const svgBlob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' });
	        const svgUrl = URL.createObjectURL(svgBlob);
	        const pitchImg = new Image();
	        await new Promise((resolve) => {
	          pitchImg.onload = resolve;
	          pitchImg.onerror = resolve;
	          pitchImg.src = svgUrl;
	        });
	        try { URL.revokeObjectURL(svgUrl); } catch (error) { /* ignore */ }

	        const drawFrame = () => {
	          ctx.fillStyle = '#ffffff';
	          ctx.fillRect(0, 0, outW, outH);
	          try {
	            ctx.drawImage(pitchImg, 0, 0, outW, outH);
	          } catch (error) {
	            // ignore
	          }
	          ctx.drawImage(canvas.lowerCanvasEl, 0, 0, outW, outH);
	        };

	        const stream = exportCanvas.captureStream(30);
	        const chunks = [];
	        const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
	        recorder.ondataavailable = (event) => {
	          if (event.data && event.data.size > 0) chunks.push(event.data);
	        };

	        setStatus('Exportando vídeo…');
	        recorder.start(1000);

	        if (!timeline.length) {
	          drawFrame();
	          await sleep(3_000);
	        } else {
	          for (let i = 0; i < timeline.length; i += 1) {
	            const step = timeline[i];
	            setStatus(`Exportando vídeo ${i + 1}/${timeline.length}…`);
	            await loadCanvasSnapshotAsync(step.canvas_state);
	            drawFrame();
	            await sleep(clamp(Number(step.duration) || 3, 1, 20) * 1000);
	          }
	        }

	        const stopPromise = new Promise((resolve) => {
	          recorder.onstop = resolve;
	        });
	        recorder.stop();
	        await stopPromise;

	        const blob = new Blob(chunks, { type: recorder.mimeType || 'video/webm' });
	        downloadBlob(blob, `${title}.webm`);
	        setStatus('Vídeo descargado.');
	      } catch (error) {
	        setStatus('Falló el export de vídeo.', true);
	      } finally {
	        applySerializedState(saved);
	        exportInFlight = false;
	        refreshLivePreview();
	      }
	    });

    presetButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setPreset(button.dataset.preset || 'full_pitch');
        setSurfaceMenuOpen(false);
      });
    });
    presetSelect.addEventListener('change', () => setPreset(presetSelect.value || 'full_pitch'));
    orientationToggle?.addEventListener('click', () => {
      applyPitchOrientation(pitchOrientation === 'portrait' ? 'landscape' : 'portrait', { preserveObjects: true, pushHistory: true });
    });
    zoomOutButton?.addEventListener('click', () => applyPitchZoom(pitchZoom - 0.08));
    zoomInButton?.addEventListener('click', () => applyPitchZoom(pitchZoom + 0.08));
    zoomResetButton?.addEventListener('click', () => {
      zoomTouched = false;
      applyPitchZoom(pitchOrientation === 'portrait' ? 1.15 : 1.0, { silent: true });
      setStatus('Zoom restablecido.');
    });
    surfaceTrigger?.addEventListener('click', () => {
      renderSurfaceThumbs();
      setSurfaceMenuOpen(!surfacePicker?.classList.contains('is-open'));
    });
    document.addEventListener('click', (event) => {
      if (!surfacePicker) return;
      if (surfacePicker.contains(event.target)) return;
      setSurfaceMenuOpen(false);
    });

    const resourceTabs = Array.from(document.querySelectorAll('.resource-tab'));
    const resourcePanels = Array.from(document.querySelectorAll('.resource-panel'));
    let activeResourceKey = '';
    const activateResourcePanel = (key) => {
      const normalized = safeText(key);
      activeResourceKey = normalized;
      resourceTabs.forEach((tab) => tab.classList.toggle('is-active', safeText(tab.dataset.resource) === normalized && !!normalized));
      resourcePanels.forEach((panel) => {
        const visible = !!normalized && safeText(panel.dataset.panel) === normalized;
        panel.hidden = !visible;
        panel.classList.toggle('is-visible', visible);
      });
    };
    resourceTabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = safeText(tab.dataset.resource);
        if (target && target === activeResourceKey) activateResourcePanel('');
        else activateResourcePanel(target);
      });
    });
    if (resourceTabs.length && resourcePanels.length) {
      // Arranca limpio: no mostramos recursos hasta que el usuario pulse una pestaña.
      activateResourcePanel('');
    }

    const panelKeyForObject = (object) => {
      const kind = safeText(object?.data?.kind);
      if (!kind) return 'base';
      if (kind.startsWith('line') || kind.startsWith('arrow')) return 'trazos';
      if (kind.startsWith('shape')) return 'figuras';
      if (kind.startsWith('emoji_')) return 'emoji';
      return 'base';
    };
    const dockInspectorIntoPanel = (panelKey) => {
      if (!selectionToolbar) return;
      const slot = inspectorSlots.get(panelKey);
      if (!slot) return;
      if (selectionToolbar.parentElement !== slot) slot.appendChild(selectionToolbar);
      activateResourcePanel(panelKey);
    };

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        fitCanvas(true);
        renderSurfaceThumbs();
        setPreset(presetSelect.value || 'full_pitch');
      }, 140);
    });

    form.addEventListener('submit', async (event) => {
      if (form.dataset.previewReady === '1') {
        form.dataset.previewReady = '';
        return;
      }
      event.preventDefault();
      persistDraftNow('submit');
      await syncHiddenBuilderFields();
      form.dataset.previewReady = '1';
      form.requestSubmit();
    });
  };
})();
