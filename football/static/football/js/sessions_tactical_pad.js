(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
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

  const PITCH_FORMAT_BY_PRESET = {
    full_pitch: '11v11_full',
    half_pitch: '11v11_half',
    attacking_third: 'specific_zone',
    seven_side: '7v7',
    seven_side_single: '7v7',
    futsal: '5v5',
    blank: 'specific_zone',
  };

  const PRESET_LABEL = {
    full_pitch: 'campo completo',
    half_pitch: 'medio campo',
    attacking_third: 'último tercio',
    seven_side: 'fútbol 7 doble',
    seven_side_single: 'fútbol 7 individual',
    futsal: 'futsal',
    blank: 'superficie libre',
  };

  const COLORS = {
    local: { fill: '#1d4ed8', stroke: '#eff6ff', text: '#ffffff' },
    rival: { fill: '#dc2626', stroke: '#fff7ed', text: '#ffffff' },
    goalkeeper: { fill: '#111827', stroke: '#facc15', text: '#facc15' },
  };
  const RESOURCE_LABELS = {
    ball: 'el balón',
    cone: 'un cono',
    zone: 'una zona',
    text: 'un texto',
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
      const drawOne = (x) => {
        root.appendChild(createSvgNode(doc, 'rect', { x, y: sevenY, width: sevenWidth, height: sevenHeight, fill: 'rgba(34,211,238,0.08)', stroke: '#67e8f9', 'stroke-width': 2.2, 'stroke-dasharray': '8 6' }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x, y1: sevenY + (sevenHeight / 2), x2: x + sevenWidth, y2: sevenY + (sevenHeight / 2), stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + (sevenHeight / 2), r: 5.5 * scaleLocal, fill: 'none', stroke: 'rgba(103,232,249,0.66)', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - areaWidth) / 2, y: sevenY, width: areaWidth, height: areaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - areaWidth) / 2, y: sevenY + sevenHeight - areaDepth, width: areaWidth, height: areaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - goalAreaWidth) / 2, y: sevenY, width: goalAreaWidth, height: goalAreaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'rect', { x: x + (sevenWidth - goalAreaWidth) / 2, y: sevenY + sevenHeight - goalAreaDepth, width: goalAreaWidth, height: goalAreaDepth, fill: 'none', stroke: 'rgba(103,232,249,0.76)', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + spotDist, r: 3.5, fill: '#67e8f9' }));
        root.appendChild(createSvgNode(doc, 'circle', { cx: x + (sevenWidth / 2), cy: sevenY + sevenHeight - spotDist, r: 3.5, fill: '#67e8f9' }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY, x2: x + ((sevenWidth - goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth + goalHeight) / 2), y1: sevenY, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY - goalDepth, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY - goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY + sevenHeight, x2: x + ((sevenWidth - goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth + goalHeight) / 2), y1: sevenY + sevenHeight, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
        root.appendChild(createSvgNode(doc, 'line', { x1: x + ((sevenWidth - goalHeight) / 2), y1: sevenY + sevenHeight + goalDepth, x2: x + ((sevenWidth + goalHeight) / 2), y2: sevenY + sevenHeight + goalDepth, stroke: '#67e8f9', 'stroke-width': 2 }));
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
    else if (preset === 'seven_side') {
      drawFullPitch();
      drawSevenSideOverlay(stage.x, stage.y, stage.width, stage.height);
    }
    else if (preset === 'seven_side_single') drawMiniGame(65, 45, 13, 26, 4.5, 12, 6);
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
    const selectionToolbar = document.getElementById('task-selection-toolbar');
    const selectionSummary = document.getElementById('task-selection-summary');
    const scaleXInput = document.getElementById('task-scale-x');
    const scaleYInput = document.getElementById('task-scale-y');
    const rotationInput = document.getElementById('task-rotation');
    const colorInput = document.getElementById('task-style-color');
    const timelineList = document.getElementById('task-timeline-list');
    const stepTitleInput = document.getElementById('task-step-title');
    const stepDurationInput = document.getElementById('task-step-duration');
    const addStepButton = document.getElementById('task-step-add');
    const duplicateStepButton = document.getElementById('task-step-duplicate');
    const removeStepButton = document.getElementById('task-step-remove');
    const playStepButton = document.getElementById('task-step-play');
    const presetButtons = Array.from(document.querySelectorAll('.surface-option[data-preset]'));
    const surfaceThumbs = Array.from(document.querySelectorAll('[data-surface-thumb]'));
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
    const DRAG_MIME = 'application/x-webstats-tactical-resource';
    let previewRefreshTimer = null;
    let timeline = [];
    let activeStepIndex = -1;
    let playbackTimer = null;
    let playbackRestoreState = null;

    const clampScale = (value) => clamp(Number(value) || 1, 0.4, 2.6);
    const normalizeEditableObject = (object) => {
      if (!object) return object;
      object.set({
        hasControls: true,
        hasBorders: true,
        transparentCorners: false,
        cornerStyle: 'circle',
        cornerColor: '#22d3ee',
        borderColor: '#67e8f9',
        cornerStrokeColor: '#071320',
        padding: 8,
        lockScalingFlip: true,
      });
      return object;
    };
    const isFlexibleKind = (object) => {
      const kind = safeText(object?.data?.kind);
      return kind.startsWith('line') || kind.startsWith('arrow') || kind.startsWith('shape') || kind === 'zone';
    };
    const activeFlexibleObject = () => {
      const active = canvas.getActiveObject();
      return active && isFlexibleKind(active) ? active : null;
    };
    const flexibleObjectColor = (object) => {
      if (!object) return '#22d3ee';
      if (Array.isArray(object._objects) && object._objects.length) {
        for (const child of object._objects) {
          const nested = flexibleObjectColor(child);
          if (nested) return nested;
        }
      }
      const stroke = parseColorToHex(object.stroke, '');
      if (stroke) return stroke;
      const fill = parseColorToHex(object.fill, '');
      if (fill) return fill;
      return '#22d3ee';
    };
    const applyFlexibleObjectColor = (object, colorHex) => {
      if (!object) return;
      const kind = safeText(object?.data?.kind);
      if (Array.isArray(object._objects) && object._objects.length) {
        object._objects.forEach((child) => applyFlexibleObjectColor(child, colorHex));
        object.dirty = true;
        return;
      }
      if (kind === 'zone') {
        object.set({
          stroke: colorHex,
          fill: rgbaFromHex(colorHex, 0.16),
        });
        return;
      }
      if (kind.startsWith('shape')) {
        object.set({
          stroke: colorHex,
          fill: rgbaFromHex(colorHex, 0.12),
        });
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
    const syncInspector = () => {
      if (!selectionToolbar || !selectionSummary || !scaleXInput || !scaleYInput || !rotationInput || !colorInput) return;
      const active = activeFlexibleObject();
      const enabled = !!active;
      selectionToolbar.querySelectorAll('input,button').forEach((node) => {
        node.disabled = !enabled;
      });
      if (!enabled) {
        selectionSummary.textContent = 'Selecciona una línea, flecha o figura para ajustarla.';
        scaleXInput.value = '100';
        scaleYInput.value = '100';
        rotationInput.value = '0';
        colorInput.value = '#22d3ee';
        return;
      }
      selectionSummary.textContent = `Ajustando ${objectLabel(active)} seleccionado.`;
      scaleXInput.value = String(Math.round((Number(active.scaleX) || 1) * 100));
      scaleYInput.value = String(Math.round((Number(active.scaleY) || 1) * 100));
      rotationInput.value = String(Math.round(Number(active.angle) || 0));
      colorInput.value = flexibleObjectColor(active);
    };
    const commitObjectChange = (message) => {
      canvas.requestRenderAll();
      pushHistory();
      syncInspector();
      refreshLivePreview();
      if (message) setStatus(message);
    };
    const applyToActiveFlexibleObject = (callback, message) => {
      const active = activeFlexibleObject();
      if (!active) return;
      callback(active);
      active.setCoords();
      commitObjectChange(message);
    };

    const fitCanvas = () => {
      const width = Math.max(320, Math.round(stage.clientWidth || 960));
      const height = Math.max(220, Math.round(stage.clientHeight || 640));
      canvas.setDimensions({ width, height });
      canvas.calcOffset();
      canvas.requestRenderAll();
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
      if (!history.length || history[history.length - 1] !== snapshot) history.push(snapshot);
      if (history.length > 40) history = history.slice(history.length - 40);
    };

    const setPreset = (presetValue) => {
      const preset = safeText(presetValue, 'full_pitch');
      presetSelect.value = preset;
      if (pitchFormatInput && PITCH_FORMAT_BY_PRESET[preset]) pitchFormatInput.value = PITCH_FORMAT_BY_PRESET[preset];
      presetButtons.forEach((button) => button.classList.toggle('is-active', safeText(button.dataset.preset) === preset));
      if (surfaceTriggerLabel) surfaceTriggerLabel.textContent = PRESET_LABEL[preset] || 'Campo completo';
      svgSurface.innerHTML = buildPitchSvg(preset);
      refreshLivePreview();
      setStatus(`Superficie preparada: ${PRESET_LABEL[preset] || 'campo'}.`);
    };

    const renderSurfaceThumbs = () => {
      surfaceThumbs.forEach((node) => {
        const preset = safeText(node.dataset.surfaceThumb, 'full_pitch');
        node.innerHTML = buildPitchSvg(preset);
      });
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
      canvas.setActiveObject(object);
      canvas.requestRenderAll();
      pushHistory();
      syncInspector();
    };
    const clearPendingPlacement = () => {
      pendingFactory = null;
      Array.from(toolStrip?.querySelectorAll('[data-add]') || []).forEach((button) => button.classList.remove('is-active'));
      Array.from(playerBank?.querySelectorAll('button') || []).forEach((button) => button.classList.remove('is-active'));
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
      const palette = kind === 'goalkeeper_local'
        ? COLORS.goalkeeper
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
      if (kind === 'player_local') {
        const radius = 23;
        const chipClip = new fabric.Circle({
          radius: radius - 1.6,
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 0,
        });
        const baseCircle = new fabric.Circle({
          radius,
          fill: '#ffffff',
          stroke: '#e2e8f0',
          strokeWidth: 3,
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 0,
          shadow: 'rgba(15,23,42,0.28) 0 5px 14px',
        });
        tokenParts.push(baseCircle);
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
        tokenParts.push(new fabric.Text(label, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 0,
          fontSize: 17,
          fontWeight: '900',
          fill: '#ffffff',
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
          new fabric.Path('M -50 22 Q -8 -30 46 10', { stroke: '#22d3ee', fill: '', strokeWidth: 4 }),
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
          fontSize: 22, fill: '#ffffff', fontWeight: '700', data: { kind: 'text' },
        });
      }
      if (EMOJI_LIBRARY[kind]) {
        return (left, top) => new fabric.Text(EMOJI_LIBRARY[kind], {
          left, top, originX: 'center', originY: 'center',
          fontSize: 28, data: { kind },
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
        parsed = JSON.parse(stateInput?.value || '{"version":"5.3.0","objects":[]}');
      } catch (error) {
        parsed = { version: '5.3.0', objects: [] };
      }
      applySerializedState(parsed, { pushHistory: true });
    };

    const renderPlayerBank = () => {
      if (!playerBank) return;
      playerBank.innerHTML = '';
      players.slice(0, 25).forEach((player) => {
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
        number.textContent = player.number ? String(player.number).slice(0, 2) : 'J';
        disk.appendChild(number);
        button.appendChild(name);
        button.appendChild(disk);
        registerDraggableButton(button, () => ({ kind: 'player_local', playerId: String(player.id) }));
        button.addEventListener('click', () => {
          Array.from(playerBank.querySelectorAll('button')).forEach((item) => item.classList.remove('is-active'));
          button.classList.add('is-active');
          activateFactory(playerTokenFactory('player_local', player), safeText(player.name, 'el jugador'));
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
      window.clearTimeout(previewRefreshTimer);
      previewRefreshTimer = window.setTimeout(async () => {
        const dataUrl = await buildPreviewData();
        if (previewInput) previewInput.value = dataUrl;
        applyLivePreview(dataUrl);
      }, 180);
    };
    const syncHiddenBuilderFields = async () => {
      if (legacyPlayersInput && playerCountInput) legacyPlayersInput.value = playerCountInput.value || '';
      if (stateInput) stateInput.value = JSON.stringify(serializeState());
      if (widthInput) widthInput.value = String(Math.round(canvas.getWidth()));
      if (heightInput) heightInput.value = String(Math.round(canvas.getHeight()));
      const dataUrl = await buildPreviewData();
      if (previewInput) previewInput.value = dataUrl;
      applyLivePreview(dataUrl);
      return dataUrl;
    };
    const submitPrintPreview = async (style) => {
      await syncHiddenBuilderFields();
      const actionUrl = form.dataset.pdfPreviewUrl;
      if (!actionUrl) return;
      const tempForm = document.createElement('form');
      tempForm.method = 'post';
      tempForm.action = `${actionUrl}?style=${encodeURIComponent(style || 'uefa')}`;
      tempForm.target = '_blank';
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

    fitCanvas();
    renderSurfaceThumbs();
    setPreset(presetSelect.value || 'full_pitch');
    restoreState();
    renderPlayerBank();
    refreshLivePreview();

    canvas.on('object:modified', () => {
      if (canvas.__loading) return;
      persistActiveStepSnapshot();
      pushHistory();
      syncInspector();
      refreshLivePreview();
    });
    canvas.on('object:added', () => {
      if (!canvas.__loading) {
        persistActiveStepSnapshot();
        pushHistory();
      }
      refreshLivePreview();
    });
    canvas.on('object:removed', () => {
      if (!canvas.__loading) {
        persistActiveStepSnapshot();
        pushHistory();
      }
      refreshLivePreview();
    });
    canvas.on('selection:created', syncInspector);
    canvas.on('selection:updated', syncInspector);
    canvas.on('selection:cleared', syncInspector);
    canvas.on('mouse:down', (event) => {
      if (!pendingFactory || event.target) return;
      const pointer = canvas.getPointer(event.e);
      addObject(objectAtPointer(pendingFactory, pointer));
      clearPendingPlacement();
      setStatus('Elemento colocado.');
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
        applyFlexibleObjectColor(active, colorInput.value || '#22d3ee');
      }, 'Color actualizado.');
    });
    selectionToolbar?.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (!button) return;
      const colorValue = safeText(button.dataset.color);
      if (colorValue) {
        if (colorInput) colorInput.value = colorValue;
        applyToActiveFlexibleObject((active) => {
          applyFlexibleObjectColor(active, colorValue);
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
        applySerializedState(JSON.parse(previous));
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
        syncInspector();
        setStatus('Elemento eliminado.');
        return;
      }
      if (action === 'clear') {
        canvas.getObjects().slice().forEach((item) => canvas.remove(item));
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        pushHistory();
        syncInspector();
        setStatus('Pizarra limpiada.');
        return;
      }
      if (!add) return;
      Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
      button.classList.add('is-active');
      if (add === 'player_local') activateFactory(playerTokenFactory('player_local', null), 'un jugador local');
      else if (add === 'player_rival') activateFactory(playerTokenFactory('player_rival', null), 'un jugador rival');
      else if (add === 'goalkeeper_local') activateFactory(playerTokenFactory('goalkeeper_local', null), 'un portero');
      else activateFactory(simpleFactory(add), RESOURCE_LABELS[add] || add);
    });
    syncInspector();
    Array.from(form.querySelectorAll('[data-print-style]')).forEach((button) => {
      button.addEventListener('click', () => submitPrintPreview(button.dataset.printStyle || 'uefa'));
    });

    Array.from(document.querySelectorAll('.resource-strip button[data-add]')).forEach((button) => {
      registerDraggableButton(button, () => ({ kind: safeText(button.dataset.add) }));
    });

    presetButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setPreset(button.dataset.preset || 'full_pitch');
        setSurfaceMenuOpen(false);
      });
    });
    presetSelect.addEventListener('change', () => setPreset(presetSelect.value || 'full_pitch'));
    surfaceTrigger?.addEventListener('click', () => setSurfaceMenuOpen(!surfacePicker?.classList.contains('is-open')));
    document.addEventListener('click', (event) => {
      if (!surfacePicker) return;
      if (surfacePicker.contains(event.target)) return;
      setSurfaceMenuOpen(false);
    });

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(() => {
        fitCanvas();
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
      await syncHiddenBuilderFields();
      form.dataset.previewReady = '1';
      form.requestSubmit();
    });
  };
})();
