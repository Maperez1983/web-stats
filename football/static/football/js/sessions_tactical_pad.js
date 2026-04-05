(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const parseIntSafe = (value, fallback = 0) => {
    const parsed = Number.parseInt(String(value ?? '').trim(), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
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
		    cone_striped: 'un cono (rayas)',
		    pole_marker: 'una pica',
		    ring: 'un aro',
		    zone: 'una zona',
		    text: 'un texto',
		    goal: 'una portería',
		    goal_posts: 'una portería (marco)',
		    goal_3d: 'una portería 3D',
		    goal_mini: 'una mini portería',
		    token: 'un jugador',
		    line: 'una línea',
		    arrow: 'una flecha',
		    line_solid: 'una línea continua',
	    line_thick: 'una línea gruesa',
	    line_dash: 'una línea discontinua',
	    line_dot: 'una línea de puntos',
	    line_double: 'una línea doble',
	    line_curve: 'una curva',
	    line_wave: 'una línea ondulada',
	    arrow_solid: 'una flecha continua',
	    arrow_thick: 'una flecha gruesa',
	    arrow_dash: 'una flecha discontinua',
	    arrow_dot: 'una flecha de puntos',
	    arrow_curve: 'una flecha curva',
	    shape_circle: 'un círculo',
	    shape_square: 'un cuadrado',
	    shape_rect: 'un rectángulo',
	    shape_rect_long: 'un rectángulo largo',
	    shape_triangle: 'un triángulo',
	    shape_diamond: 'un rombo',
	    shape_u: 'una U',
	    shape_lane_3: 'una zona (3 carriles)',
	    shape_lane_4: 'una zona (4 carriles)',
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
    // Lienzo con proporción real 105x68 (escalado) y un pequeño "bleed" para que el trazo
    // del borde no se recorte incluso con overflow hidden.
    const stageW = orientation === 'portrait' ? 680 : 1050;
    const stageH = orientation === 'portrait' ? 1050 : 680;
    const bleed = 2;
    const drawW = 1100;
    const drawH = 748;
    const doc = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg', null);
    const root = doc.documentElement;
    root.setAttribute('viewBox', `${-bleed} ${-bleed} ${stageW + (bleed * 2)} ${stageH + (bleed * 2)}`);
    // En vertical, algunos contenedores (y navegadores) pueden acabar con una ligera
    // desincronización de ratio, generando "barras" arriba/abajo. Usamos `slice` para
    // priorizar llenar el viewport y minimizar esos márgenes.
    root.setAttribute('preserveAspectRatio', orientation === 'portrait' ? 'xMidYMid slice' : 'xMidYMid meet');

    const defs = createSvgNode(doc, 'defs');
    const gradient = createSvgNode(doc, 'linearGradient', { id: 'pitch-bg', x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '0%', 'stop-color': '#5f8f42' }));
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '100%', 'stop-color': '#557f3c' }));
    defs.appendChild(gradient);
    root.appendChild(defs);

    // Fondo:
    // - Para "campo completo" y "F7 sobre F11" rellenamos toda la superficie para que el césped no
    //   quede cortado por bordes/redondeos del contenedor.
    // - Para superficies parciales (medio campo/tercios/futsal/F7 individual) dejamos transparente
    //   el exterior del rectángulo de juego para que no “gaste” página con verde innecesario
    //   (en editor se verá el fondo del panel; en PDF quedará blanco).
    // En el editor rellenamos el exterior con césped para que no parezca que hay “huecos” alrededor.
    // El recorte para PDF/cards ya se hace al exportar la preview (data-pitch-box).
    const fillOutside = 'url(#pitch-bg)';
    root.appendChild(createSvgNode(doc, 'rect', {
      x: -bleed,
      y: -bleed,
      width: stageW + (bleed * 2),
      height: stageH + (bleed * 2),
      fill: preset === 'blank' ? 'transparent' : fillOutside,
    }));
    const drawRoot = createSvgNode(doc, 'g');
    if (orientation === 'portrait') {
      drawRoot.setAttribute('transform', `translate(${stageW} 0) rotate(90)`);
    }
    root.appendChild(drawRoot);

    const createStage = (orientation, desiredAspect = 105 / 68, fitMode = 'contain') => {
      // En vertical, el grupo se rota 90 grados: el sistema de coordenadas "dibuja"
      // sobre un lienzo efectivo de (stageH x stageW). Mantenemos proporción real 105x68.
      // Deja margen suficiente para que el trazo del borde no se recorte en miniaturas / contenedores con overflow hidden.
      // Margen de seguridad para que los bordes no se recorten con overflow hidden,
      // pero lo más pequeño posible para que el campo ocupe pantalla.
      const margin = 0;
      const portrait = orientation === 'portrait';
      const effectiveW = portrait ? stageH : stageW;
      const effectiveH = portrait ? stageW : stageH;
      const availableWidth = effectiveW - margin * 2;
      const availableHeight = effectiveH - margin * 2;

      const fit = safeText(fitMode, 'contain') === 'cover' ? 'cover' : 'contain';
      let width = availableWidth;
      let height = width / desiredAspect;
      if (fit === 'contain') {
        if (height > availableHeight) {
          height = availableHeight;
          width = height * desiredAspect;
        }
      } else {
        // Cover: llena el alto disponible (evita barras arriba/abajo en superficies muy anchas como futsal),
        // recortando por laterales si hace falta.
        height = availableHeight;
        width = height * desiredAspect;
        if (width < availableWidth) {
          width = availableWidth;
          height = width / desiredAspect;
        }
      }
      const offsetX = (effectiveW - width) / 2;
      const offsetY = (effectiveH - height) / 2;
      return { x: offsetX, y: offsetY, width, height };
    };
    let stage = createStage(orientation);
    // Caja del rectángulo de juego dentro del viewBox, para poder recortar previews/PDF
    // y evitar márgenes vacíos enormes en superficies parciales (tercios, medio campo, futsal, etc).
    let pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
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
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
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
      pitchBox = { x: pitch.x, y: pitch.y, width: pitch.width, height: pitch.height };
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
      pitchBox = { x: pitch.x, y: pitch.y, width: pitch.width, height: pitch.height };
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
      pitchBox = { x: pitch.x, y: pitch.y, width: pitch.width, height: pitch.height };
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
      // Superficies muy anchas (p.ej. futsal 40x20) quedan con demasiado "aire" arriba/abajo en modo contain.
      // En esos casos usamos cover para que el césped rellene mejor el viewport y se reduzca el scroll.
      const pitch = createStage(orientation, metersW / metersH, (metersW / metersH) > (105 / 68) ? 'cover' : 'contain');
      pitchBox = { x: pitch.x, y: pitch.y, width: pitch.width, height: pitch.height };
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

    // Guarda el bounding box del rectángulo de juego en coordenadas del root viewBox.
    // En vertical el grupo se rota 90º, así que convertimos la caja antes de exportar.
    try {
      let box = pitchBox;
      if (orientation === 'portrait') {
        box = {
          x: stageW - (box.y + box.height),
          y: box.x,
          width: box.height,
          height: box.width,
        };
      }
      root.setAttribute('data-pitch-box', `${box.x} ${box.y} ${box.width} ${box.height}`);
    } catch (error) {
      // ignore
    }

    return new XMLSerializer().serializeToString(doc);
  };

  window.initSessionsTacticalPad = function initSessionsTacticalPad() {
    const form = document.getElementById('task-builder-form');
    if (!form) return;
    const canvasEl = document.getElementById('create-task-canvas');
    const stage = document.getElementById('task-pitch-stage');
	    const svgSurface = document.getElementById('task-pitch-surface');
	    const presetSelect = document.getElementById('draw-task-preset');
	    const surfacePicker = document.getElementById('surface-picker');
	    const surfaceTrigger = document.getElementById('surface-trigger');
	    const surfaceMenu = document.getElementById('surface-menu');
	    const surfaceTriggerLabel = document.getElementById('surface-trigger-label');
	    const pitchResizeHandle = document.getElementById('pitch-resize-handle');
    const orientationInput = document.getElementById('draw-task-pitch-orientation');
    const orientationToggle = document.getElementById('pitch-orientation-toggle');
    const orientationLabel = document.getElementById('pitch-orientation-label');
    const viewportEl = document.getElementById('task-pitch-viewport');
    const zoomInput = document.getElementById('draw-task-pitch-zoom');
	    const zoomOutButton = document.getElementById('pitch-zoom-out');
	    const zoomInButton = document.getElementById('pitch-zoom-in');
	    const zoomResetButton = document.getElementById('pitch-zoom-reset');
	    const zoomLabel = document.getElementById('pitch-zoom-label');
	    const stageSizeDownButton = document.getElementById('pitch-size-down');
	    const stageSizeUpButton = document.getElementById('pitch-size-up');
	    const stageSizeFitButton = document.getElementById('pitch-size-fit');
	    const stageSizeLabel = document.getElementById('pitch-size-label');
	    const pitchFormatInput = document.getElementById('draw-task-pitch-format');
    const stateInput = document.getElementById('draw-canvas-state');
    const widthInput = document.getElementById('draw-canvas-width');
    const heightInput = document.getElementById('draw-canvas-height');
	    const previewInput = document.getElementById('draw-canvas-preview-data');
	    const timelinePreviewsInput = document.getElementById('draw-canvas-timeline-previews');
    const livePreviewImg = document.getElementById('task-live-preview');
    const livePreviewPlaceholder = document.getElementById('task-live-preview-placeholder');
    const playerCountInput = form.querySelector('[name="draw_task_player_count"]');
    const legacyPlayersInput = form.querySelector('[name="draw_task_players"]');
		    const statusEl = document.getElementById('task-builder-status');
		    const toolStrip = document.getElementById('task-basic-tools');
		    const playerBank = document.getElementById('task-player-bank');
		    const hideUsedPlayersToggle = document.getElementById('task-hide-used-players');
		    const libraryPane = document.querySelector('.side-pane[data-pane="biblioteca"]');
		    const selectionToolbar = document.getElementById('task-selection-toolbar');
    const selectionSummary = document.getElementById('task-selection-summary');
    const scaleXInput = document.getElementById('task-scale-x');
    const scaleYInput = document.getElementById('task-scale-y');
	    const rotationInput = document.getElementById('task-rotation');
	    const colorInput = document.getElementById('task-style-color');
	    const scalePresetsRow = document.getElementById('task-scale-presets');
	    const tokenSizePresetsRow = document.getElementById('task-token-size-presets');
	    const strokeWidthRow = document.getElementById('task-stroke-width-row');
		    const strokeWidthInput = document.getElementById('task-stroke-width');
		    const strokePresetsRow = document.getElementById('task-stroke-presets');
		    const tokenMetaRow = document.getElementById('task-token-meta');
		    const tokenNameInput = document.getElementById('task-token-name');
		    const tokenNumberInput = document.getElementById('task-token-number');
			    const commandBar = document.getElementById('task-command-bar');
			    const commandMoreBtn = document.getElementById('task-command-more');
			    const commandMenu = document.getElementById('task-command-menu');
			    const simBtn = document.getElementById('task-sim-btn');
			    const simPopover = document.getElementById('task-sim-popover');
			    const simCloseBtn = document.getElementById('task-sim-close');
			    const simToggleBtn = document.getElementById('task-sim-toggle');
			    const simResetBtn = document.getElementById('task-sim-reset');
			    const patternPopover = document.getElementById('task-pattern-popover');
			    const patternCloseBtn = document.getElementById('task-pattern-close');
		    const layersBtn = document.getElementById('task-layers-btn');
		    const layersPopover = document.getElementById('task-layers-popover');
		    const layersCloseBtn = document.getElementById('task-layers-close');
		    const scenariosBtn = document.getElementById('task-scenarios-btn');
		    const scenariosPopover = document.getElementById('task-scenarios-popover');
		    const scenariosCloseBtn = document.getElementById('task-scenarios-close');
		    const scenarioAddBtn = document.getElementById('task-scenario-add');
		    const scenarioDuplicateBtn = document.getElementById('task-scenario-duplicate');
		    const scenarioRemoveBtn = document.getElementById('task-scenario-remove');
		    const scenarioTitleInput = document.getElementById('task-scenario-title-pop');
		    const scenarioDurationInput = document.getElementById('task-scenario-duration-pop');
		    const patternTitle = document.getElementById('task-pattern-title');
		    const patternFieldsLine = document.getElementById('task-pattern-fields-line');
		    const patternFieldsGrid = document.getElementById('task-pattern-fields-grid');
		    const patternCountInput = document.getElementById('task-pattern-count');
		    const patternSpacingInput = document.getElementById('task-pattern-spacing');
		    const patternRowsInput = document.getElementById('task-pattern-rows');
		    const patternColsInput = document.getElementById('task-pattern-cols');
		    const patternSpacingXInput = document.getElementById('task-pattern-spacing-x');
		    const patternSpacingYInput = document.getElementById('task-pattern-spacing-y');
		    const patternCenterInput = document.getElementById('task-pattern-center');
		    const patternInvertXInput = document.getElementById('task-pattern-invert-x');
		    const patternInvertYInput = document.getElementById('task-pattern-invert-y');
		    const patternApplyBtn = document.getElementById('task-pattern-apply');
		    const patternCancelBtn = document.getElementById('task-pattern-cancel');
		    const layersList = document.getElementById('task-layers-list');
		    const layersListPopover = document.getElementById('task-layers-list-popover');
		    const timelineList = document.getElementById('task-timeline-list');
		    const timelineListPopover = document.getElementById('task-timeline-list-popover');
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
    if (!window.fabric || !form || !canvasEl || !stage || !svgSurface || !presetSelect) return;

    const draftAlert = document.getElementById('task-builder-draft-alert');
    const draftText = document.getElementById('task-builder-draft-text');
    const draftClearBtn = document.getElementById('task-builder-draft-clear');
    const keepaliveUrl = safeText(form.dataset.keepaliveUrl);
    const saveSuccess = safeText(form.dataset.saveSuccess) === '1';
    const draftKey = safeText(form.dataset.draftKey);
    const draftNewKey = safeText(form.dataset.draftNewKey);
    const currentDraftUrl = `${window.location.pathname}${window.location.search || ''}`;
    const urlParams = (() => {
      try {
        return new URLSearchParams(window.location.search || '');
      } catch (error) {
        return new URLSearchParams();
      }
    })();
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
      if (draftText) {
        draftText.textContent = text;
      } else {
        draftAlert.textContent = text;
      }
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
	      // Rehidrata los editores enriquecidos desde los campos hidden aplicados.
	      // Importante: el initRichEditors() sincroniza "área -> hidden" al cargar; si no
	      // actualizamos el área aquí, se perdería el borrador restaurado.
	      try {
	        const wrappers = Array.from(form.querySelectorAll('[data-rich-editor]'));
	        wrappers.forEach((wrapper) => {
	          const plainName = safeText(wrapper.dataset.richName);
	          const htmlName = safeText(wrapper.dataset.richHtmlName);
	          const area = wrapper.querySelector('[data-rich-area]');
	          if (!plainName || !htmlName || !area) return;
	          const plainField = form.querySelector(`[name="${CSS.escape(plainName)}"]`);
	          const htmlField = form.querySelector(`[name="${CSS.escape(htmlName)}"]`);
	          if (!plainField || !htmlField) return;
	          const htmlValue = String(htmlField.value || '');
	          if (htmlValue) {
	            area.innerHTML = htmlValue;
	            return;
	          }
	          const textValue = String(plainField.value || '');
	          area.textContent = textValue;
	          // Convierte saltos de línea a <br> para mantener la estructura básica.
	          area.innerHTML = area.innerHTML.replace(/\n/g, '<br>');
	        });
	      } catch (error) {
	        // ignore
	      }
	      return true;
	    };

    if (saveSuccess) {
      clearDraftKeys();
      setDraftAlert('');
    } else if (draftKey) {
      const ignoreDraft = urlParams.get('nodraft') === '1' || urlParams.get('reset') === '1';
      if (urlParams.get('cleardraft') === '1') {
        clearDraftKeys();
        setDraftAlert('Borrador local borrado. Recarga la página.');
      }
      if (ignoreDraft) {
        setDraftAlert('');
      } else {
      const draft = readDraft(draftKey);
      const matchesUrl = !draft?.url || safeText(draft.url) === currentDraftUrl;
      if (draft && matchesUrl && applyDraftToForm(draft)) {
        const stamp = safeText(draft.updated_at);
        setDraftAlert(stamp ? `Borrador local recuperado (${stamp}).` : 'Borrador local recuperado.');
      } else {
        setDraftAlert('');
      }
      }
    }
    if (draftClearBtn) {
      draftClearBtn.addEventListener('click', () => {
        clearDraftKeys();
        setDraftAlert('Borrador local borrado. Recargando…');
        try { window.location.reload(); } catch (error) { /* ignore */ }
      });
    }

	    const setStatus = (message, isError = false) => {
	      if (!statusEl) return;
	      statusEl.textContent = message;
	      statusEl.style.color = isError ? '#fca5a5' : 'rgba(226,232,240,0.72)';
	    };

			    let syncRichEditorsNow = () => {};
			    const initRichEditors = () => {
			      const wrappers = Array.from(form.querySelectorAll('[data-rich-editor]'));
			      if (!wrappers.length) return;
			      const syncFns = [];

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

				        // Fuerza alineación a la izquierda y evita estilos heredados/inline que pueden
				        // acabar centrando el texto (sobre todo al rehidratar HTML guardado).
				        //
				        // Importante (rendimiento): el "deep cleanup" (querySelectorAll + execCommand)
				        // es caro y NO debe ejecutarse en cada tecla, porque genera delay al escribir.
				        const forceLeftAlignment = (deep = false) => {
				          // Fast path: asegura el estilo base del editor (casi gratis).
				          try {
				            area.style.setProperty('text-align', 'left', 'important');
				            area.style.setProperty('display', 'block');
				            area.style.setProperty('justify-content', 'flex-start');
				            area.style.setProperty('align-items', 'stretch');
				          } catch (error) { /* ignore */ }
				          if (!deep) return;
				          // Slow path: limpia nodos con estilos heredados / alineación inline.
				          try {
				            const nodes = area.querySelectorAll('[style], [align]');
				            nodes.forEach((node) => {
				              try { node.removeAttribute('align'); } catch (error) { /* ignore */ }
				              try { node.style.setProperty('text-align', 'left', 'important'); } catch (error) { /* ignore */ }
				              try { node.style.removeProperty('justify-content'); } catch (error) { /* ignore */ }
				              try { node.style.removeProperty('align-items'); } catch (error) { /* ignore */ }
				            });
				          } catch (error) { /* ignore */ }
				          // Safari/iOS: puede mantener el estado de justificación. Forzamos left para el bloque actual.
				          try { document.execCommand('justifyLeft', false, null); } catch (error) { /* ignore */ }
				        };
				        forceLeftAlignment(true);

		        const normalizePlain = (value) => String(value || '')
		          .replace(/\u00a0/g, ' ')
		          .replace(/[ \t]+\n/g, '\n')
		          .replace(/\n{3,}/g, '\n\n')
		          .trim();

				        let richSyncTimer = null;
				        const syncFields = () => {
				          htmlField.value = String(area.innerHTML || '').trim();
				          plainField.value = normalizePlain(area.innerText || area.textContent || '');
				        };
				        const scheduleSyncFields = () => {
				          window.clearTimeout(richSyncTimer);
				          // Debounce suave: reduce lecturas de innerText/innerHTML por tecla.
				          richSyncTimer = window.setTimeout(syncFields, 120);
				        };
				        const syncDeep = () => {
				          window.clearTimeout(richSyncTimer);
				          // Solo en acciones "puntuales" (blur/toolbar), hacemos limpieza profunda.
				          forceLeftAlignment(true);
				          syncFields();
				        };
				        syncFns.push(syncDeep);

				        area.addEventListener('input', scheduleSyncFields);
				        area.addEventListener('focus', () => {
				          forceLeftAlignment(false);
				        });
				        area.addEventListener('blur', () => {
				          syncDeep();
				        });
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
		          // Pegado es texto plano, no hace falta limpieza profunda aquí.
		          forceLeftAlignment(false);
		          window.clearTimeout(richSyncTimer);
		          syncFields();
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
		            syncDeep();
		            return;
		          }
		          try {
		            document.execCommand(cmd, false, null);
		          } catch (error) {
		            // ignore
		          }
		          syncDeep();
		        });

			        // Inicializa hidden fields al cargar (para el caso de que vengan con HTML).
			        syncDeep();
			      });
	      syncRichEditorsNow = () => {
	        syncFns.forEach((fn) => {
	          try { fn(); } catch (error) { /* ignore */ }
	        });
	      };
	    };
	    initRichEditors();

	    let players = [];
	    try {
	      players = JSON.parse(document.getElementById('tpad-players-catalog')?.textContent || '[]');
	    } catch (error) {
      players = [];
    }
    if (!Array.isArray(players)) players = [];

	    // Assets extraídos de PDFs (misma origin vía endpoint Django).
	    let pdfAssets = [];
	    try {
	      const raw = window.TPAD_PDF_ASSETS;
	      pdfAssets = Array.isArray(raw) ? raw : [];
	    } catch (error) {
	      pdfAssets = [];
	    }
	    const pdfAssetMeta = new Map();
	    const pdfAssetImages = new Map();
	    const pdfAssetLoading = new Set();
	    const pdfAssetPendingRefresh = new Set();
	    const normalizePdfAssetId = (value) => String(value ?? '').trim();
	    pdfAssets.forEach((item) => {
	      const id = normalizePdfAssetId(item?.id);
	      if (!id) return;
	      pdfAssetMeta.set(id, {
	        id,
	        title: safeText(item?.title),
	        url: safeText(item?.url),
	        width: Number(item?.width) || 0,
	        height: Number(item?.height) || 0,
	      });
	    });
	    const ensurePdfAssetLoaded = (assetId) => {
	      const id = normalizePdfAssetId(assetId);
	      if (!id || pdfAssetImages.has(id) || pdfAssetLoading.has(id)) return;
	      const meta = pdfAssetMeta.get(id);
	      const url = safeText(meta?.url);
	      if (!url) return;
	      pdfAssetLoading.add(id);
	      try {
	        const img = new Image();
	        try { img.crossOrigin = 'anonymous'; } catch (e) { /* ignore */ }
	        img.onload = () => {
	          pdfAssetImages.set(id, img);
	          pdfAssetLoading.delete(id);
	          pdfAssetPendingRefresh.add(id);
	        };
	        img.onerror = () => {
	          pdfAssetLoading.delete(id);
	        };
	        img.src = url;
	      } catch (error) {
	        pdfAssetLoading.delete(id);
	      }
	    };
	    pdfAssetMeta.forEach((meta) => ensurePdfAssetLoaded(meta.id));

	    const assetUploadInput = document.getElementById('tpad-pdf-assets-upload');
	    const assetUploadUrl = safeText(window.TPAD_PDF_ASSET_UPLOAD_URL);
	    const scopeKey = safeText(window.TPAD_SCOPE_KEY, 'coach');
	    const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
	    const appendPdfAssetButton = (asset) => {
	      const tools = document.getElementById('task-pdf-assets-tools');
	      if (!tools) return;
	      const id = normalizePdfAssetId(asset?.id);
	      const url = safeText(asset?.url);
	      if (!id || !url) return;
	      // Si había placeholder de "Aún no hay iconos", quítalo.
	      Array.from(tools.querySelectorAll('span.meta')).forEach((node) => node.remove());
	      const btn = document.createElement('button');
	      btn.type = 'button';
	      btn.className = 'pdf-asset-btn';
	      btn.dataset.add = `pdf_asset:${id}`;
	      btn.setAttribute('aria-label', `Recurso ${id}`);
	      btn.title = safeText(asset?.title || '');
	      const img = document.createElement('img');
	      img.src = url;
	      img.alt = '';
	      img.loading = 'lazy';
	      btn.appendChild(img);
	      tools.appendChild(btn);
	      // Habilita drag&drop como resto de recursos.
	      try {
	        registerDraggableButton(btn, () => ({ kind: safeText(btn.dataset.add) }));
	      } catch (error) { /* ignore */ }
	    };

	    assetUploadInput?.addEventListener('change', async () => {
	      const files = Array.from(assetUploadInput.files || []);
	      if (!files.length) return;
	      if (!assetUploadUrl) {
	        setStatus('No se pudo subir: falta URL de subida.', true);
	        return;
	      }
	      try {
	        setStatus('Subiendo iconos…');
	        const data = new FormData();
	        data.append('scope_key', scopeKey);
	        files.slice(0, 40).forEach((file) => data.append('assets', file));
	        const resp = await fetch(assetUploadUrl, {
	          method: 'POST',
	          headers: csrfToken ? { 'X-CSRFToken': csrfToken } : undefined,
	          credentials: 'same-origin',
	          body: data,
	        });
	        const payload = await resp.json().catch(() => ({}));
	        if (!resp.ok || !payload?.ok) throw new Error(payload?.error || 'No se pudo subir.');
	        const list = Array.isArray(payload.saved) ? payload.saved : [];
	        list.forEach((asset) => {
	          const id = normalizePdfAssetId(asset?.id);
	          if (!id) return;
	          pdfAssetMeta.set(id, {
	            id,
	            title: safeText(asset?.title),
	            url: safeText(asset?.url),
	            width: Number(asset?.width) || 0,
	            height: Number(asset?.height) || 0,
	          });
	          ensurePdfAssetLoaded(id);
	          appendPdfAssetButton(asset);
	        });
	        const msg = list.length ? `Iconos añadidos: ${list.length}.` : 'No había iconos nuevos (ya existían).';
	        setStatus(msg);
	      } catch (error) {
	        setStatus(error?.message || 'Error al subir iconos.', true);
	      } finally {
	        try { assetUploadInput.value = ''; } catch (e) { /* ignore */ }
	      }
	    });

		    const canvas = new fabric.Canvas(canvasEl, {
		      preserveObjectStacking: true,
		      selection: true,
		      enableRetinaScaling: true,
		    });
	    // iPad/Safari: si el canvas no tiene touch-action:none, el navegador intercepta el gesto
	    // y Fabric no recibe bien los eventos (parece que "no se puede mover nada").
	    try {
	      if (canvasEl && canvasEl.style) canvasEl.style.touchAction = 'none';
	      if (canvas.upperCanvasEl && canvas.upperCanvasEl.style) canvas.upperCanvasEl.style.touchAction = 'none';
	      if (canvas.lowerCanvasEl && canvas.lowerCanvasEl.style) canvas.lowerCanvasEl.style.touchAction = 'none';
	    } catch (error) {
	      // ignore
	    }
	    // Si el viewport es scrollable (zoom/orientación), el offset del canvas cambia y Fabric
	    // necesita recalcularlo para que clicks/drag coincidan con la posición real.
	    const scheduleCanvasOffset = () => {
	      try {
	        window.requestAnimationFrame(() => {
	          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
	        });
	      } catch (error) {
	        try { canvas.calcOffset(); } catch (e) { /* ignore */ }
	      }
	    };
	    viewportEl?.addEventListener('scroll', scheduleCanvasOffset, { passive: true });
	    window.addEventListener('scroll', scheduleCanvasOffset, { passive: true });

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
		      const { w: boundW, h: boundH } = worldSize();
		      return {
		        x: clamp(snappedX, 0, boundW),
		        y: clamp(snappedY, 0, boundH),
		      };
		    };
	    syncGridUi({ silent: true });

			    let history = [];
		      let historyIndex = -1;
				    let pendingFactory = null;
				    let pendingKind = '';
				    let isSimulating = false;
				    let simulationBaselineSnapshot = null;
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
		    // Tamaño del stage (solo UI): ajusta cuánto ocupa el campo en pantalla, sin tocar posiciones.
		    const STAGE_SIZE_KEY_PORTRAIT = 'tpad_stage_size_portrait_v1';
		    const STAGE_SIZE_KEY_LANDSCAPE = 'tpad_stage_size_landscape_v1';
		    const readStageFactor = (key, fallback) => {
		      try {
		        const raw = safeText(window.localStorage.getItem(key));
		        const val = Number.parseFloat(raw);
		        if (Number.isFinite(val)) return clamp(val, 0.55, 1.15);
		      } catch (error) { /* ignore */ }
		      return fallback;
		    };
		    let stageFactorPortrait = readStageFactor(STAGE_SIZE_KEY_PORTRAIT, 0.82);
		    let stageFactorLandscape = readStageFactor(STAGE_SIZE_KEY_LANDSCAPE, 1.0);
	    let spacePanArmed = false;
	    let spacePanning = false;
	    let spacePanStart = null;
	    let backgroundPickMode = false;
	    const useViewportMapping = (() => {
	      const flag = safeText(urlParams?.get('tpad_vpt'));
	      if (flag === '0') return false;
	      return true;
	    })();

	    let worldWidth = parseIntSafe(widthInput?.value) || 0;
	    let worldHeight = parseIntSafe(heightInput?.value) || 0;

	    if (!Number.isFinite(pitchZoom)) pitchZoom = 1.0;
	    pitchZoom = clamp(pitchZoom, 0.8, 1.6);

	    const clampScale = (value) => clamp(Number(value) || 1, 0.4, 2.6);
	    const worldSize = () => {
	      const w = Number(worldWidth) || 0;
	      const h = Number(worldHeight) || 0;
	      if (w > 0 && h > 0) return { w, h };
	      return { w: Math.round(canvas.getWidth() || 0), h: Math.round(canvas.getHeight() || 0) };
	    };
	    // Pan del viewport (en px de canvas) cuando se usa viewportTransform (sin scrollbars).
	    let viewportPanX = 0;
	    let viewportPanY = 0;
	    const syncWorldFromInputs = () => {
	      const nextW = parseIntSafe(widthInput?.value);
	      const nextH = parseIntSafe(heightInput?.value);
	      if (nextW > 0 && nextH > 0) {
	        worldWidth = nextW;
	        worldHeight = nextH;
	      }
	    };
	    const applyViewportTransformToWorld = () => {
	      if (!useViewportMapping) {
	        canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
	        return;
	      }
	      const { w: fromW, h: fromH } = worldSize();
	      const toW = Math.round(canvas.getWidth() || 0);
	      const toH = Math.round(canvas.getHeight() || 0);
	      if (fromW <= 0 || fromH <= 0 || toW <= 0 || toH <= 0) return;
	      const baseScale = Math.min(toW / fromW, toH / fromH);
	      const zoom = clamp(Number(pitchZoom) || 1, 0.8, 1.6);
	      const scale = baseScale * zoom;
	      const scaledW = fromW * scale;
	      const scaledH = fromH * scale;
	      const baseOffsetX = (toW - scaledW) / 2;
	      const baseOffsetY = (toH - scaledH) / 2;
	      const maxPanX = scaledW > toW ? (scaledW - toW) / 2 : 0;
	      const maxPanY = scaledH > toH ? (scaledH - toH) / 2 : 0;
	      if (maxPanX <= 0) viewportPanX = 0;
	      else viewportPanX = clamp(viewportPanX, -maxPanX, maxPanX);
	      if (maxPanY <= 0) viewportPanY = 0;
	      else viewportPanY = clamp(viewportPanY, -maxPanY, maxPanY);
	      const offsetX = baseOffsetX + viewportPanX;
	      const offsetY = baseOffsetY + viewportPanY;
	      canvas.setViewportTransform([scale, 0, 0, scale, offsetX, offsetY]);
	    };
		    const normalizeEditableObject = (object) => {
		      if (!object) return object;
		      const rawLocked = object?.data?.locked;
		      // Compat: algunos estados antiguos pueden traer locked como string ('false'/'true').
		      const locked = rawLocked === true
		        || rawLocked === 1
		        || rawLocked === '1'
		        || String(rawLocked || '').toLowerCase() === 'true';
		      const kind = safeText(object?.data?.kind);
		      // Figuras de fondo (zonas/figuras/porterías): por defecto dejan pasar los clicks
		      // para que no bloqueen mover fichas o trazos colocados encima.
		      // Se pueden editar desde el panel "Capas" (activa background_edit temporalmente).
		      const isBackground = isBackgroundShape(object);
		      if (isBackground) {
		        object.data = object.data || {};
		        if (object.data.background !== true) object.data.background = true;
		      }
		      const backgroundEdit = !!object?.data?.background_edit;
		      // Emojis: oculta el halo/círculo legacy si viene en Group antiguo.
		      if (kind && kind.startsWith('emoji_') && Array.isArray(object._objects)) {
		        const circle = object._objects.find((child) => child && child.type === 'circle');
		        if (circle) {
	          circle.set({
	            opacity: 0,
	            strokeWidth: 0,
	            stroke: 'rgba(0,0,0,0)',
	            fill: 'rgba(0,0,0,0)',
	          });
	        }
	      }

		      // Líneas/flechas: evita que al escalar se engorde el trazo (Fabric por defecto escala strokeWidth).
		      // Flechas: además, evita que la punta (triángulo) se haga enorme al escalar el grupo.
		      const applyStrokeUniformRecursively = (obj) => {
		        if (!obj) return;
		        try {
		          if (obj.strokeWidth !== undefined) obj.strokeUniform = true;
		        } catch (error) { /* ignore */ }
		        if (Array.isArray(obj._objects)) obj._objects.forEach(applyStrokeUniformRecursively);
		      };
		      const normalizeArrowHead = (group) => {
		        if (!group || !Array.isArray(group._objects)) return;
		        const sx = Number(group.scaleX) || 1;
		        const sy = Number(group.scaleY) || 1;
		        const tri = group._objects.find((child) => child && child.type === 'triangle');
		        if (!tri) return;
		        // Cancelamos la escala del grupo para que la punta mantenga tamaño constante.
		        // Esto se guarda en JSON y corrige flechas antiguas que ya estaban “gordas”.
		        try { tri.set({ scaleX: sx ? (1 / sx) : 1, scaleY: sy ? (1 / sy) : 1 }); } catch (error) { /* ignore */ }
		      };
		      if (kind && (kind.startsWith('line') || kind.startsWith('arrow') || kind.startsWith('shape') || kind === 'zone')) {
		        applyStrokeUniformRecursively(object);
		      }
		      if (kind && kind.startsWith('arrow')) {
		        normalizeArrowHead(object);
		      }
		      object.set({
		        hasControls: !locked,
		        hasBorders: true,
		        transparentCorners: false,
		        cornerStyle: 'circle',
		        cornerColor: '#22d3ee',
		        borderColor: '#67e8f9',
		        cornerStrokeColor: '#071320',
		        padding: isBackground ? (backgroundEdit ? 14 : 10) : 8,
		        cornerSize: isBackground ? (backgroundEdit ? 30 : 22) : 18,
		        lockScalingFlip: true,
		      });
		      try {
		        // Fabric 5: en pantallas táctiles aumenta el área de agarre.
		        if (typeof object.touchCornerSize !== 'undefined') {
		          object.touchCornerSize = isBackground ? (backgroundEdit ? 46 : 36) : 30;
		        }
		      } catch (error) { /* ignore */ }
		      try {
		        // Fabric 5: tolerancia extra al seleccionar (especialmente útil con trackpad/touch).
		        if (typeof object.targetFindTolerance !== 'undefined') {
		          object.targetFindTolerance = isBackground ? (backgroundEdit ? 14 : 10) : 8;
		        }
		      } catch (error) { /* ignore */ }
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
			      if (!locked && isBackground) {
			        object.set({
			          selectable: true,
			          // Importante: mantenemos `evented` activo incluso fuera de background_edit,
			          // pero hacemos "pasar a través" en los handlers (clic normal) para no
			          // bloquear colocar/mover elementos encima. Así la figura se puede seleccionar
			          // fácilmente (p.ej. con Shift, o clic en zona vacía) sin quedar “ineditable”.
			          evented: true,
			          hoverCursor: backgroundEdit ? 'move' : 'default',
			          moveCursor: backgroundEdit ? 'move' : 'default',
			        });
			      }

		      // Nitidez: por defecto Fabric cachea en bitmap muchos objetos al escalar/rotar,
		      // lo que provoca blur perceptible (especialmente en iPad y al hacer zoom).
		      // Para nuestro editor, priorizamos fidelidad visual sobre micro-optimizaciones.
		      try { object.objectCaching = false; } catch (error) { /* ignore */ }
		      try { object.noScaleCache = true; } catch (error) { /* ignore */ }
		      try {
		        if (Array.isArray(object._objects)) {
		          object._objects.forEach((child) => {
		            if (!child) return;
		            try { child.objectCaching = false; } catch (e) { /* ignore */ }
		            try { child.noScaleCache = true; } catch (e) { /* ignore */ }
		          });
		        }
		      } catch (error) { /* ignore */ }
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

    const setBackgroundEditMode = (object, enabled, options = {}) => {
      if (!object || !isBackgroundShape(object)) return false;
      object.data = object.data || {};
      const next = !!enabled;
      const prev = !!object.data.background_edit;
      if (prev === next && !options.force) return false;
      object.data.background_edit = next;
      normalizeEditableObject(object);
      try { object.setCoords(); } catch (error) { /* ignore */ }
      if (next) {
        // Durante la edición lo subimos arriba para que sea fácil agarrarlo/ajustarlo.
        try { canvas.bringToFront(object); } catch (error) { /* ignore */ }
      }
      if (!next) {
        // Al salir de edición, vuelve atrás para que no bloquee otros elementos.
        try { canvas.sendToBack(object); } catch (error) { /* ignore */ }
      }
      try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
      return true;
    };

    const findBackgroundShapeAtPoint = (point) => {
      if (!point) return null;
      const objects = (canvas.getObjects() || []).slice();
      for (let i = objects.length - 1; i >= 0; i -= 1) {
        const obj = objects[i];
        if (!obj || !isBackgroundShape(obj) || obj.visible === false) continue;
        let hit = false;
        try {
          if (typeof obj.containsPoint === 'function') hit = !!obj.containsPoint(point);
        } catch (err) {
          hit = false;
        }
        if (!hit) {
          try {
            const rect = obj.getBoundingRect(true, true);
            hit = point.x >= rect.left && point.x <= (rect.left + rect.width) && point.y >= rect.top && point.y <= (rect.top + rect.height);
          } catch (err) {
            hit = false;
          }
        }
        if (hit) return obj;
      }
      return null;
    };

    const pickBackgroundFromEvent = (e) => {
      if (!e) return null;
      try {
        const pointer = canvas.getPointer(e);
        const point = new fabric.Point(Number(pointer?.x) || 0, Number(pointer?.y) || 0);
        return findBackgroundShapeAtPoint(point);
      } catch (error) {
        return null;
      }
    };

    const disableBackgroundEditExcept = (keepObject) => {
      let changed = false;
      (canvas.getObjects() || []).forEach((obj) => {
        if (!obj || !isBackgroundShape(obj)) return;
        if (obj === keepObject) return;
        if (!obj?.data?.background_edit) return;
        changed = setBackgroundEditMode(obj, false, { force: true }) || changed;
      });
      return changed;
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
      const walkObjects = (node, fn) => {
        if (!node) return;
        try { if (fn(node)) return; } catch (e) { /* ignore */ }
        if (Array.isArray(node?._objects)) node._objects.forEach((child) => walkObjects(child, fn));
      };
      if (kind === 'token' && Array.isArray(object._objects)) {
        // Local token: devuelve el color de la franja si existe.
        let stripeFill = '';
        walkObjects(object, (child) => {
          if (!child) return false;
          if (child.type !== 'rect') return false;
          const role = safeText(child?.data?.role);
          if (role === 'token_stripe') {
            stripeFill = parseColorToHex(child.fill, '') || '';
            return true;
          }
          const width = Number(child.width) || 0;
          const height = Number(child.height) || 0;
          const fill = parseColorToHex(child.fill, '');
          if (width > 0 && height > 0 && width <= 14 && height >= 40 && fill && fill !== '#f8fafc') {
            stripeFill = fill;
            return true;
          }
          return false;
        });
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
	      const walkObjects = (node, fn) => {
	        if (!node) return;
	        try { fn(node); } catch (e) { /* ignore */ }
	        if (Array.isArray(node?._objects)) node._objects.forEach((child) => walkObjects(child, fn));
	      };
	      const stripeRects = [];
	      const paintableStripes = [];
	      walkObjects(group, (child) => {
	        if (!child) return;
	        if (child.type !== 'rect') return;
	        const height = Number(child.height) || 0;
	        if (height < 30) return;
	        stripeRects.push(child);
	        if (safeText(child?.data?.role) === 'token_stripe') paintableStripes.push(child);
	      });
	      const treatAsLocal = tokenKind === 'player_local' || tokenKind === 'goalkeeper_local' || (!tokenKind && paintableStripes.length >= 2);
	      if (treatAsLocal) {
	        if (paintableStripes.length) {
	          paintableStripes.forEach((child) => child.set({ fill: colorHex }));
	        } else if (stripeRects.length) {
	          // Compat: tareas creadas antes de que marcásemos las franjas verdes con role=token_stripe.
	          // Recoloreamos solo las franjas "no blancas".
	          stripeRects.forEach((child) => {
	            const current = parseColorToHex(child.fill, '');
	            if (!current || current === '#f8fafc') return;
	            child.set({ fill: colorHex });
	          });
	        } else {
	          // Portero u otros tokens sin franjas: intentamos recolorear el círculo principal.
	          const circles = [];
	          walkObjects(group, (child) => { if (child?.type === 'circle') circles.push(child); });
	          const target = circles.length > 1 ? circles[1] : circles[0];
	          if (target) target.set({ fill: colorHex });
	        }
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
    const applyEmojiColor = (emojiObject, colorHex) => {
      if (!emojiObject) return;
      setObjectData(emojiObject, { color: colorHex });
      const glow = `${rgbaFromHex(colorHex, 0.55)} 0 0 10px`;
      if (emojiObject.type === 'text') {
        emojiObject.set({ shadow: glow });
        emojiObject.dirty = true;
        return;
      }
      if (Array.isArray(emojiObject._objects)) {
        const circle = emojiObject._objects.find((child) => child && child.type === 'circle');
        if (circle) {
          circle.set({
            opacity: 0,
            strokeWidth: 0,
            stroke: 'rgba(0,0,0,0)',
            fill: 'rgba(0,0,0,0)',
          });
        }
        const text = emojiObject._objects.find((child) => child && child.type === 'text');
        if (text) text.set({ shadow: glow });
        emojiObject.dirty = true;
      }
    };
	    const applyObjectColor = (object, colorHex) => {
	      if (!object) return;
	      const kind = safeText(object?.data?.kind);
	      if (kind) setObjectData(object, { color: colorHex });
	      if (kind === 'token') {
	        applyTokenColor(object, colorHex);
	        return;
	      }
	      if (kind.startsWith('emoji_')) {
	        applyEmojiColor(object, colorHex);
	        return;
	      }
	      if (kind === 'cone-striped' && Array.isArray(object._objects) && object._objects.length) {
	        const triangle = object._objects.find((child) => child && child.type === 'triangle');
	        if (triangle) {
	          triangle.set({ fill: colorHex, stroke: darkenHex(colorHex, 0.55) });
	        }
	        object.dirty = true;
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
	      if (kind === 'shape-u') {
	        object.set({ stroke: colorHex });
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
	      const layerTargets = [layersList, layersListPopover].filter(Boolean);
	      if (!layerTargets.length) return;
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

	      const ordered = objects.slice().reverse();
	      const renderInto = (container) => {
	        if (!container) return;
	        container.textContent = '';
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
	          const customName = safeText(obj?.data?.layer_name);
	          if (customName) {
	            subtitle = subtitle ? `${subtitle} · ${title}` : title;
	            title = customName;
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

	          container.appendChild(row);
	        });
	      };
	      layerTargets.forEach(renderInto);
	    };
	    const syncInspector = () => {
	      if (!selectionToolbar || !selectionSummary || !scaleXInput || !scaleYInput || !rotationInput || !colorInput) return;
	      const active = activeInspectableObject();
	      const enabled = !!active;
	      if (!enabled) {
	        selectionToolbar.hidden = true;
	        selectionToolbar.querySelectorAll('input,button').forEach((node) => { node.disabled = true; });
	        if (tokenMetaRow) tokenMetaRow.hidden = true;
	        if (tokenSizePresetsRow) tokenSizePresetsRow.hidden = true;
	        if (scalePresetsRow) scalePresetsRow.hidden = false;
	        if (tokenNameInput) tokenNameInput.value = '';
	        if (tokenNumberInput) tokenNumberInput.value = '';
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
	      const isToken = safeText(active?.data?.kind) === 'token';
	      if (tokenSizePresetsRow) tokenSizePresetsRow.hidden = !isToken;
	      if (scalePresetsRow) scalePresetsRow.hidden = !!isToken;
	      if (tokenMetaRow && tokenNameInput && tokenNumberInput) {
	        tokenMetaRow.hidden = !isToken;
	        if (isToken) {
	          const storedName = safeText(active?.data?.playerName, '');
	          const storedNumber = safeText(active?.data?.playerNumber, '');
	          tokenNameInput.value = storedName || safeText(findTokenChild(active, 'token_name', (child) => child?.type === 'text' && Math.abs((Number(child.top) || 0) + 35) <= 5)?.text, '');
	          tokenNumberInput.value = storedNumber || safeText(findTokenChild(active, 'token_number', (child) => child?.type === 'text' && (Number(child.fontSize) || 0) >= 8)?.text, '');
	        } else {
	          tokenNameInput.value = '';
	          tokenNumberInput.value = '';
	        }
	      }
	    };
    const commitObjectChange = (message) => {
      canvas.requestRenderAll();
      pushHistory();
      syncInspector();
      refreshLivePreview();
      if (message) setStatus(message);
    };

	    const isTokenGroup = (object) => safeText(object?.data?.kind) === 'token';
	    const getTokenBaseRadius = (group) => {
	      const stored = Number(group?.data?.token_base_radius);
	      if (Number.isFinite(stored) && stored > 0) return stored;
	      const objects = Array.isArray(group?._objects) ? group._objects : (typeof group?.getObjects === 'function' ? group.getObjects() : []);
	      let candidate = 0;
	      let preferred = 0;
	      objects.forEach((child) => {
	        if (!child || child.type !== 'circle') return;
	        const r = Number(child.radius) || 0;
	        if (r <= 0) return;
	        const role = safeText(child?.data?.role);
	        if (role === 'token_base' || role === 'token_fill') preferred = Math.max(preferred, r);
	        candidate = Math.max(candidate, r);
	      });
	      return preferred || candidate || 22;
	    };
	    const setTokenStandardSize = (group, presetKey) => {
	      if (!group || !isTokenGroup(group)) return false;
	      const key = safeText(presetKey, 'm').toLowerCase();
	      const targetRadius = key === 's' ? 18 : (key === 'l' ? 26 : 22);
	      const baseRadius = getTokenBaseRadius(group);
	      const next = clampScale(targetRadius / Math.max(1, baseRadius));
	      group.set({ scaleX: next, scaleY: next });
	      group.data = group.data || {};
	      group.data.token_size = key;
	      group.setCoords();
	      return true;
	    };
	    const sanitizeTokenNumber = (raw, fallback) => {
	      const cleaned = safeText(raw).toUpperCase().replace(/[^0-9A-Z]/g, '').slice(0, 2);
	      return cleaned || safeText(fallback).toUpperCase().slice(0, 2);
	    };
	    const computeInitials = (name, fallback) => {
	      const base = safeText(name);
	      if (!base) return safeText(fallback);
	      const letters = base
	        .split(/\s+/)
	        .map((piece) => safeText(piece)[0] || '')
	        .join('')
	        .toUpperCase()
	        .slice(0, 2);
	      return letters || safeText(fallback);
	    };
	    const findTokenChild = (group, role, fallbackFinder) => {
	      if (!group) return null;
	      const objects = Array.isArray(group._objects) ? group._objects : (typeof group.getObjects === 'function' ? group.getObjects() : []);
	      const wanted = safeText(role);
	      if (wanted) {
	        const byRole = objects.find((child) => safeText(child?.data?.role) === wanted);
	        if (byRole) return byRole;
	      }
	      if (typeof fallbackFinder === 'function') {
	        return objects.find((child) => fallbackFinder(child)) || null;
	      }
	      return null;
	    };
		    const updateTokenAppearance = (group, { name, number }) => {
		      if (!group || !isTokenGroup(group)) return;
		      const tokenKind = safeText(group?.data?.token_kind);
		      const defaultNumber = tokenKind === 'goalkeeper_local' ? 'GK' : 'J';
		      const nextNumber = sanitizeTokenNumber(number, defaultNumber);
		      const nextName = safeText(name);
	      const displayName = shortPlayerName(
	        nextName || (tokenKind === 'goalkeeper_local' ? 'Portero' : (tokenKind === 'player_rival' ? 'Rival' : 'Jugador')),
	      );

	      group.data = group.data || {};
	      group.data.playerName = nextName;
	      group.data.playerNumber = nextNumber;

		      const isLocalStyle = tokenKind === 'player_local' || tokenKind === 'player_away' || tokenKind === 'goalkeeper_local';
		      const numberText = findTokenChild(
		        group,
		        'token_number',
		        (child) => child?.type === 'text'
		          && Math.abs((Number(child.top) || 0) - (isLocalStyle ? 0 : 26)) <= (isLocalStyle ? 4 : 8)
		          && (Number(child.fontSize) || 0) >= (isLocalStyle ? 14 : 8),
		      );
	      if (numberText && typeof numberText.set === 'function') numberText.set('text', nextNumber);

	      const nameText = findTokenChild(
	        group,
	        'token_name',
	        (child) => child?.type === 'text' && Math.abs((Number(child.top) || 0) + 35) <= 5 && (Number(child.fontSize) || 0) <= 12,
	      );
	      if (nameText && typeof nameText.set === 'function') nameText.set('text', displayName);

	      const nameBg = findTokenChild(
	        group,
	        'token_name_bg',
	        (child) => child?.type === 'rect' && Math.abs((Number(child.top) || 0) + 35) <= 5 && (Number(child.height) || 0) >= 16,
	      );
	      if (nameBg && typeof nameBg.set === 'function') {
	        const width = Math.max(42, Math.min(110, (displayName.length * 6.4) + 14));
	        nameBg.set('width', width);
	      }

	      const initialsText = findTokenChild(
	        group,
	        'token_initials',
	        (child) => child?.type === 'text' && Math.abs((Number(child.top) || 0) - 0) <= 4 && (Number(child.fontSize) || 0) >= 10 && (Number(child.fontSize) || 0) <= 14,
	      );
	      if (initialsText && typeof initialsText.set === 'function') initialsText.set('text', computeInitials(nextName, nextNumber));

	      try {
	        if (typeof group._calcBounds === 'function') group._calcBounds();
	        if (typeof group._updateObjectsCoords === 'function') group._updateObjectsCoords();
	      } catch (error) { /* ignore */ }
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

	    const applyTokenMetaFromUi = () => {
	      if (!tokenNameInput || !tokenNumberInput) return;
	      applyToActiveFlexibleObject((active) => {
	        if (!isTokenGroup(active)) return;
	        updateTokenAppearance(active, { name: tokenNameInput.value, number: tokenNumberInput.value });
	      }, 'Etiqueta actualizada.');
	    };
	    tokenNameInput?.addEventListener('blur', applyTokenMetaFromUi);
	    tokenNumberInput?.addEventListener('blur', applyTokenMetaFromUi);
	    const handleTokenInputKeydown = (event) => {
	      const key = String(event.key || '').toLowerCase();
	      if (key === 'enter') {
	        event.preventDefault();
	        applyTokenMetaFromUi();
	      }
	      if (key === 'escape') {
	        event.preventDefault();
	        syncInspector();
	      }
	    };
	    tokenNameInput?.addEventListener('keydown', handleTokenInputKeydown);
	    tokenNumberInput?.addEventListener('keydown', handleTokenInputKeydown);
	    tokenNumberInput?.addEventListener('input', () => {
	      if (!tokenNumberInput) return;
	      const raw = String(tokenNumberInput.value || '');
	      const cleaned = raw.toUpperCase().replace(/[^0-9A-Z]/g, '').slice(0, 2);
	      if (raw !== cleaned) tokenNumberInput.value = cleaned;
	    });

	    const getSelectionObjects = () => {
	      const active = canvas.getActiveObject();
	      if (!active) return [];
	      if (active.type === 'activeSelection' && typeof active.getObjects === 'function') return active.getObjects() || [];
	      return [active];
	    };
		    const selectionCenter = () => {
		      const active = canvas.getActiveObject();
		      if (active && typeof active.getCenterPoint === 'function') return active.getCenterPoint();
		      const { w, h } = worldSize();
		      return new fabric.Point(w / 2, h / 2);
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
		    const patternDuplicateGrid = async (options = {}) => {
		      const sources = getSelectionObjects();
		      if (!sources.length) {
		        setStatus('Selecciona uno o varios elementos para crear un patrón.', true);
		        return;
		      }
		      const rows = clamp(Number.parseInt(String(options.rows || ''), 10) || 0, 1, 12);
		      const cols = clamp(Number.parseInt(String(options.cols || ''), 10) || 0, 1, 12);
		      const spacingX = clamp(Number.parseInt(String(options.spacingX || ''), 10) || 0, 8, 400);
		      const spacingY = clamp(Number.parseInt(String(options.spacingY || ''), 10) || 0, 8, 400);
		      const center = !!options.center;
		      const invertX = !!options.invertX;
		      const invertY = !!options.invertY;
		      if (!rows || !cols || !spacingX || !spacingY) {
		        setStatus('Valores de patrón no válidos.', true);
		        return;
		      }
		      const xSign = invertX ? -1 : 1;
		      const ySign = invertY ? -1 : 1;
		      const xIndices = [];
		      const yIndices = [];
		      if (center) {
		        const left = Math.floor((cols - 1) / 2);
		        const right = (cols - 1) - left;
		        for (let x = -left; x <= right; x += 1) xIndices.push(x);
		        const up = Math.floor((rows - 1) / 2);
		        const down = (rows - 1) - up;
		        for (let y = -up; y <= down; y += 1) yIndices.push(y);
		      } else {
		        for (let x = 0; x < cols; x += 1) xIndices.push(x);
		        for (let y = 0; y < rows; y += 1) yIndices.push(y);
		      }

		      const added = [];
		      for (const yIndex of yIndices) {
		        for (const xIndex of xIndices) {
		          if (xIndex === 0 && yIndex === 0) continue;
		          const offsetX = xIndex * spacingX * xSign;
		          const offsetY = yIndex * spacingY * ySign;
		          const clones = await Promise.all(sources.map((obj) => cloneObjectAsync(obj)));
		          clones.filter(Boolean).forEach((cloned) => {
		            cloned.set({
		              left: (Number(cloned.left) || 0) + offsetX,
		              top: (Number(cloned.top) || 0) + offsetY,
		            });
		            normalizeEditableObject(cloned);
		            if (Array.isArray(cloned._objects)) cloned._objects.forEach((obj) => normalizeEditableObject(obj));
		            canvas.add(cloned);
		            if (isBackgroundShape(cloned)) canvas.sendToBack(cloned);
		            cloned.setCoords();
		            added.push(cloned);
		          });
		        }
		      }

		      if (!added.length) {
		        setStatus('No se pudo crear el patrón en rejilla.', true);
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
		      setStatus('Patrón en rejilla creado.');
		    };
		    const patternDuplicate = async (axis, options = {}) => {
		      const active = canvas.getActiveObject();
		      if (!active) {
		        setStatus('Selecciona un elemento para crear un patrón.', true);
		        return;
		      }

		      const bounds = typeof active.getBoundingRect === 'function' ? active.getBoundingRect(true, true) : null;
		      const defaultSpacing = axis === 'x'
		        ? clamp(Math.round((bounds?.width || 40) + 12), 12, 320)
		        : clamp(Math.round((bounds?.height || 40) + 12), 12, 320);

		      let count = clamp(Number.parseInt(String(options?.count ?? ''), 10) || 0, 0, 25);
		      if (!count) {
		        const countRaw = window.prompt('¿Cuántas copias quieres añadir?', '4');
		        if (countRaw === null) return;
		        count = clamp(Number.parseInt(String(countRaw), 10) || 0, 1, 25);
		      }
		      if (!count) {
		        setStatus('Número de copias no válido.', true);
		        return;
		      }

		      let spacing = clamp(Number.parseInt(String(options?.spacing ?? ''), 10) || 0, 0, 400);
		      if (!spacing) {
		        const spacingRaw = window.prompt('Separación (px) entre copias:', String(defaultSpacing));
		        if (spacingRaw === null) return;
		        spacing = clamp(Number.parseInt(String(spacingRaw), 10) || 0, 8, 400);
		      }
		      spacing = clamp(spacing, 8, 400);
		      if (!spacing) {
		        setStatus('Separación no válida.', true);
		        return;
		      }

		      const center = !!options?.center;
		      const invertX = !!options?.invertX;
		      const invertY = !!options?.invertY;
		      const sign = axis === 'x' ? (invertX ? -1 : 1) : (invertY ? -1 : 1);
		      const offsets = [];
		      if (center) {
		        const left = Math.floor(count / 2);
		        const right = count - left;
		        for (let i = -left; i <= right; i += 1) {
		          if (i === 0) continue;
		          offsets.push(i);
		        }
		      } else {
		        for (let i = 1; i <= count; i += 1) offsets.push(i);
		      }
		      const dx = axis === 'x' ? spacing * sign : 0;
		      const dy = axis === 'y' ? spacing * sign : 0;
		      const sources = getSelectionObjects();
		      if (!sources.length) return;

		      const added = [];
		      for (const step of offsets) {
		        const clones = await Promise.all(sources.map((obj) => cloneObjectAsync(obj)));
		        clones.filter(Boolean).forEach((cloned) => {
		          cloned.set({
		            left: (Number(cloned.left) || 0) + (dx * step),
		            top: (Number(cloned.top) || 0) + (dy * step),
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
		    let patternMode = 'line';
		    let patternAxis = 'x';
		    const setPatternPopoverOpen = (open) => {
		      if (!patternPopover) return;
		      patternPopover.hidden = !open;
		    };
		    const closePatternPopover = () => setPatternPopoverOpen(false);
		    const suggestPatternSpacing = (axis) => {
		      const active = canvas.getActiveObject();
		      if (!active || typeof active.getBoundingRect !== 'function') return 40;
		      const bounds = active.getBoundingRect(true, true);
		      const base = axis === 'x' ? (bounds?.width || 40) : (bounds?.height || 40);
		      return clamp(Math.round(Number(base || 40) + 12), 12, 320);
		    };
		    const setPatternUiMode = (mode) => {
		      patternMode = mode === 'grid' ? 'grid' : 'line';
		      if (patternFieldsLine) patternFieldsLine.hidden = patternMode !== 'line';
		      if (patternFieldsGrid) patternFieldsGrid.hidden = patternMode !== 'grid';
		      const showXInvert = patternMode === 'grid' || patternAxis === 'x';
		      const showYInvert = patternMode === 'grid' || patternAxis === 'y';
		      if (patternInvertXInput?.parentElement) patternInvertXInput.parentElement.hidden = !showXInvert;
		      if (patternInvertYInput?.parentElement) patternInvertYInput.parentElement.hidden = !showYInvert;
		    };
		    const openPatternPopover = (axisOrGrid) => {
		      const active = canvas.getActiveObject();
		      if (!active) {
		        setStatus('Selecciona un elemento para aplicar un patrón.', true);
		        return;
		      }
		      // Evita doble overlay (menú + popover) tapando el campo.
		      setCommandMenuOpen(false);
		      if (axisOrGrid === 'grid') {
		        patternAxis = 'x';
		        if (patternTitle) patternTitle.textContent = 'Patrón en rejilla';
		        setPatternUiMode('grid');
		        if (patternSpacingXInput) patternSpacingXInput.value = String(suggestPatternSpacing('x'));
		        if (patternSpacingYInput) patternSpacingYInput.value = String(suggestPatternSpacing('y'));
		      } else {
		        patternAxis = axisOrGrid === 'y' ? 'y' : 'x';
		        if (patternTitle) patternTitle.textContent = patternAxis === 'x' ? 'Patrón en fila' : 'Patrón en columna';
		        setPatternUiMode('line');
		        if (patternSpacingInput) patternSpacingInput.value = String(suggestPatternSpacing(patternAxis));
		      }
		      setPatternPopoverOpen(true);
		      window.setTimeout(() => {
		        try {
		          const target = patternMode === 'grid' ? patternRowsInput : patternCountInput;
		          target?.focus();
		          target?.select?.();
		        } catch (error) { /* ignore */ }
		      }, 0);
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
		      else if (command === 'pattern_row') openPatternPopover('x');
		      else if (command === 'pattern_col') openPatternPopover('y');
		      else if (command === 'pattern_grid') openPatternPopover('grid');
		      else if (command === 'front') setSelectionLayer('front');
		      else if (command === 'back') setSelectionLayer('back');
		      else if (command === 'lock') toggleLockSelection();
		      else if (command === 'grid_toggle') toggleGridVisible();
		      else if (command === 'grid_snap') toggleGridSnap();
		      else if (command === 'grid_size') cycleGridSize();
		      else if (command === 'group') groupSelection();
		      else if (command === 'ungroup') ungroupSelection();
		      else if (command === 'clear') handleCanvasAction('clear');
		    });
		    patternCancelBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      closePatternPopover();
		    });
		    patternCloseBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      closePatternPopover();
		    });
		    const applyPatternFromUi = async () => {
		      const center = !!patternCenterInput?.checked;
		      const invertX = !!patternInvertXInput?.checked;
		      const invertY = !!patternInvertYInput?.checked;
		      if (patternMode === 'grid') {
		        const rows = clamp(Number.parseInt(String(patternRowsInput?.value || ''), 10) || 0, 1, 12);
		        const cols = clamp(Number.parseInt(String(patternColsInput?.value || ''), 10) || 0, 1, 12);
		        const spacingX = clamp(Number.parseInt(String(patternSpacingXInput?.value || ''), 10) || 0, 8, 400);
		        const spacingY = clamp(Number.parseInt(String(patternSpacingYInput?.value || ''), 10) || 0, 8, 400);
		        if (!rows || !cols || !spacingX || !spacingY) {
		          setStatus('Valores de patrón no válidos.', true);
		          return;
		        }
		        closePatternPopover();
		        await patternDuplicateGrid({ rows, cols, spacingX, spacingY, center, invertX, invertY });
		        return;
		      }

		      const count = clamp(Number.parseInt(String(patternCountInput?.value || ''), 10) || 0, 1, 25);
		      const spacing = clamp(Number.parseInt(String(patternSpacingInput?.value || ''), 10) || 0, 8, 400);
		      if (!count || !spacing) {
		        setStatus('Valores de patrón no válidos.', true);
		        return;
		      }
		      closePatternPopover();
		      await patternDuplicate(patternAxis, { count, spacing, center, invertX, invertY });
		    };
		    patternApplyBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      applyPatternFromUi();
		    });
		    patternPopover?.addEventListener('keydown', (event) => {
		      const key = String(event.key || '').toLowerCase();
		      if (key === 'escape') {
		        event.preventDefault();
		        closePatternPopover();
		        return;
		      }
		      if (key === 'enter') {
		        event.preventDefault();
		        applyPatternFromUi();
		      }
		    });
		    const resolveClosest = (node, selector) => {
		      if (!node || !selector) return null;
		      const element = node instanceof Element ? node : node?.parentElement;
		      if (!element || typeof element.closest !== 'function') return null;
		      return element.closest(selector);
		    };
		    const setLayersPopoverOpen = (open) => {
		      if (!layersPopover) return;
		      layersPopover.hidden = !open;
		      if (open) {
		        // Asegura que el contenido está actualizado al abrir.
		        try { renderLayers(); } catch (error) { /* ignore */ }
		      }
		    };
			    const setScenariosPopoverOpen = (open) => {
			      if (!scenariosPopover) return;
			      scenariosPopover.hidden = !open;
			      if (open) {
			        try { renderTimeline(); } catch (error) { /* ignore */ }
			        try { syncStepInputs(); } catch (error) { /* ignore */ }
			      }
			    };
			    const syncSimUi = () => {
			      document.body.classList.toggle('is-simulating', !!isSimulating);
			      simBtn?.classList.toggle('is-simulating', !!isSimulating);
			      if (simToggleBtn) {
			        simToggleBtn.textContent = isSimulating ? 'Salir de simulación' : 'Entrar en simulación';
			        simToggleBtn.classList.toggle('danger', !!isSimulating);
			        simToggleBtn.classList.toggle('primary', !isSimulating);
			      }
			      if (simResetBtn) simResetBtn.hidden = !isSimulating;
			    };
			    const setSimPopoverOpen = (open) => {
			      if (!simPopover) return;
			      simPopover.hidden = !open;
			      if (open) syncSimUi();
			    };
				    const restoreSimulationBaseline = () => {
				      if (!simulationBaselineSnapshot) return;
				      let parsed = null;
				      try { parsed = JSON.parse(simulationBaselineSnapshot); } catch (error) { parsed = null; }
				      if (!parsed) return;
				      const { w, h } = worldSize();
				      applySerializedState(parsed, { sourceWidth: Math.round(w || 0), sourceHeight: Math.round(h || 0) });
				    };
				    const setSimulationUiLocked = (locked) => {
				      const setDisabled = (node) => {
				        if (!node) return;
				        if ('disabled' in node) node.disabled = !!locked;
				        try { node.classList.toggle('is-disabled', !!locked); } catch (error) { /* ignore */ }
				      };
				      [presetSelect, surfaceTrigger, orientationToggle, zoomOutButton, zoomInButton, zoomResetButton, stageSizeDownButton, stageSizeUpButton, stageSizeFitButton, pitchFormatInput]
				        .forEach(setDisabled);
				      try { (presetButtons || []).forEach(setDisabled); } catch (error) { /* ignore */ }
				      try { if (pitchResizeHandle) pitchResizeHandle.style.pointerEvents = locked ? 'none' : ''; } catch (error) { /* ignore */ }
				      try { if (surfaceMenu) surfaceMenu.style.pointerEvents = locked ? 'none' : ''; } catch (error) { /* ignore */ }
				      try { if (surfacePicker) surfacePicker.style.pointerEvents = locked ? 'none' : ''; } catch (error) { /* ignore */ }
				      try {
				        Array.from(toolStrip?.querySelectorAll('button') || []).forEach((btn) => { btn.disabled = !!locked; });
				        Array.from(playerBank?.querySelectorAll('button') || []).forEach((btn) => { btn.disabled = !!locked; });
				        Array.from(libraryPane?.querySelectorAll('button') || []).forEach((btn) => { btn.disabled = !!locked; });
				      } catch (error) { /* ignore */ }
				      try { if (locked && resourceDetails) resourceDetails.open = false; } catch (error) { /* ignore */ }
				    };
				    const enterSimulation = () => {
				      if (isSimulating) return;
				      try { simulationBaselineSnapshot = JSON.stringify(serializeState()); } catch (error) { simulationBaselineSnapshot = null; }
				      clearPendingPlacement();
				      isSimulating = true;
				      setSimulationUiLocked(true);
				      syncSimUi();
				      setStatus('Modo simulación activado. Mueve elementos: no se guardan cambios.');
				    };
				    const exitSimulation = () => {
				      if (!isSimulating) return;
				      isSimulating = false;
				      setSimulationUiLocked(false);
				      syncSimUi();
				      restoreSimulationBaseline();
				      simulationBaselineSnapshot = null;
				      setStatus('Simulación finalizada. Volviste al editor.');
				    };
			    const resetSimulation = () => {
			      if (!isSimulating) return;
			      restoreSimulationBaseline();
			      setStatus('Simulación reseteada.');
			    };
			    const handleOutsideFloatingMenus = (event) => {
			      const target = event?.target;
			      if (commandMenu && !commandMenu.hidden) {
			        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-command-menu');
			        if (!inside) setCommandMenuOpen(false);
		      }
		      if (patternPopover && !patternPopover.hidden) {
		        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-pattern-popover');
		        if (!inside) closePatternPopover();
		      }
		      if (layersPopover && !layersPopover.hidden) {
		        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-layers-popover');
		        if (!inside) setLayersPopoverOpen(false);
		      }
			      if (scenariosPopover && !scenariosPopover.hidden) {
			        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-scenarios-popover');
			        if (!inside) setScenariosPopoverOpen(false);
			      }
			      if (simPopover && !simPopover.hidden) {
			        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-sim-popover');
			        if (!inside) setSimPopoverOpen(false);
			      }
			    };
		    // Cerrar menús aunque Fabric/otros handlers hagan stopPropagation.
		    // Usamos eventos en fase de captura para que no se queden "pegados" tapando el campo (Safari/iPad incluido).
		    window.addEventListener('pointerdown', handleOutsideFloatingMenus, true);
		    window.addEventListener('mousedown', handleOutsideFloatingMenus, true);
		    window.addEventListener('touchstart', handleOutsideFloatingMenus, true);
			    window.addEventListener('keydown', (event) => {
			      const key = String(event?.key || '').toLowerCase();
			      if (key !== 'escape') return;
			      if (commandMenu && !commandMenu.hidden) setCommandMenuOpen(false);
			      if (patternPopover && !patternPopover.hidden) closePatternPopover();
			      if (layersPopover && !layersPopover.hidden) setLayersPopoverOpen(false);
			      if (scenariosPopover && !scenariosPopover.hidden) setScenariosPopoverOpen(false);
			      if (simPopover && !simPopover.hidden) setSimPopoverOpen(false);
			    }, true);

		    layersBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      // Cierra otros overlays para no apilar menús.
		      try { setCommandMenuOpen(false); } catch (error) { /* ignore */ }
		      try { closePatternPopover(); } catch (error) { /* ignore */ }
		      setLayersPopoverOpen(!!layersPopover?.hidden);
		    });
		    layersCloseBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      setLayersPopoverOpen(false);
		    });

		    scenariosBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      // Cierra otros overlays para no apilar menús.
		      try { setCommandMenuOpen(false); } catch (error) { /* ignore */ }
		      try { closePatternPopover(); } catch (error) { /* ignore */ }
		      try { setLayersPopoverOpen(false); } catch (error) { /* ignore */ }
		      setScenariosPopoverOpen(!!scenariosPopover?.hidden);
		    });
			    scenariosCloseBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      setScenariosPopoverOpen(false);
			    });

			    simBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      // Cierra otros overlays para no apilar menús.
			      try { setCommandMenuOpen(false); } catch (error) { /* ignore */ }
			      try { closePatternPopover(); } catch (error) { /* ignore */ }
			      try { setLayersPopoverOpen(false); } catch (error) { /* ignore */ }
			      try { setScenariosPopoverOpen(false); } catch (error) { /* ignore */ }
			      setSimPopoverOpen(!!simPopover?.hidden);
			    });
			    simCloseBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      setSimPopoverOpen(false);
			    });
			    simToggleBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (isSimulating) exitSimulation();
			      else enterSimulation();
			      syncSimUi();
			    });
			    simResetBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      resetSimulation();
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
		    const bindLayersList = (listEl) => {
		      if (!listEl) return;
		      listEl.addEventListener('click', (event) => {
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
		          // Si es una figura de fondo, al seleccionarla desde "Capas" permitimos edición temporal.
		          if (isBackgroundShape(obj)) {
		            disableBackgroundEditExcept(obj);
		            setBackgroundEditMode(obj, true, { force: true });
		          } else {
		            disableBackgroundEditExcept(null);
		          }
		          canvas.setActiveObject(obj);
		          canvas.requestRenderAll();
		          syncInspector();
		          renderLayers();
		          if (isBackgroundShape(obj)) setStatus('Fondo en modo edición (desde Capas). Pulsa Esc para volver a modo “pasar a través”.');
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
		          if (obj.data.locked) obj.data.background_edit = false;
		          normalizeEditableObject(obj);
		          obj.setCoords();
		          commitLayerChange(obj.data.locked ? 'Elemento bloqueado.' : 'Elemento desbloqueado.');
		        }
		      });
		      listEl.addEventListener('dblclick', (event) => {
		        const targetUid = safeText(event.target.closest('.layer-row')?.dataset?.layerUid);
		        if (!targetUid) return;
		        const obj = findObjectByLayerUid(targetUid);
		        if (!obj) return;
		        obj.data = obj.data || {};
		        const current = safeText(obj.data.layer_name) || objectLabel(obj);
		        const next = window.prompt('Nombre de capa:', current);
		        if (next === null) return;
		        const cleaned = safeText(next).slice(0, 60);
		        if (!cleaned) {
		          delete obj.data.layer_name;
		          commitLayerChange('Nombre eliminado.');
		          return;
		        }
		        obj.data.layer_name = cleaned;
		        commitLayerChange('Nombre actualizado.');
		      });
		    };
		    bindLayersList(layersList);
		    bindLayersList(layersListPopover);

		    const fitCanvas = (preserveObjects = false) => {
		      const previousWidth = canvas.getWidth() || 0;
		      const previousHeight = canvas.getHeight() || 0;
	      // En iPad/rotación, clientWidth puede no reflejar el tamaño renderizado real (viewport scaling).
	      // Usamos getBoundingClientRect para mantener punteros/targets coherentes.
	      const stageRect = stage?.getBoundingClientRect?.() || { width: stage?.clientWidth || 960, height: stage?.clientHeight || 640 };
	      const width = Math.max(320, Math.round(stageRect.width || 960));
	      const height = Math.max(220, Math.round(stageRect.height || 640));
	      canvas.setDimensions({ width, height });
	      if (!useViewportMapping && preserveObjects && previousWidth > 0 && previousHeight > 0) {
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
	      if (useViewportMapping) {
	        syncWorldFromInputs();
	        applyViewportTransformToWorld();
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
	    const stageBaseMaxWidth = () => (pitchOrientation === 'portrait' ? 560 : 1500);
	    const getStageFactor = () => (pitchOrientation === 'portrait' ? stageFactorPortrait : stageFactorLandscape);
	    const writeStageFactor = (value) => {
	      const factor = clamp(Number(value) || 1, 0.55, 1.15);
	      if (pitchOrientation === 'portrait') stageFactorPortrait = factor;
	      else stageFactorLandscape = factor;
	      try {
	        window.localStorage.setItem(
	          pitchOrientation === 'portrait' ? STAGE_SIZE_KEY_PORTRAIT : STAGE_SIZE_KEY_LANDSCAPE,
	          String(factor),
	        );
	      } catch (error) { /* ignore */ }
	      return factor;
	    };
	    const applyStageSizeUi = (options = {}) => {
	      if (!stage) return;
	      const factor = getStageFactor();
	      const base = stageBaseMaxWidth();
	      const maxW = Math.round(base * factor);
	      try { stage.style.maxWidth = `${maxW}px`; } catch (error) { /* ignore */ }
	      if (stageSizeLabel) stageSizeLabel.textContent = `Campo ${Math.round(factor * 100)}%`;
	      if (options.noFit) return;
	      try {
	        window.requestAnimationFrame(() => {
	          try { fitCanvas(!useViewportMapping); } catch (error) { /* ignore */ }
	          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
	          try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
	        });
	      } catch (error) {
	        try { fitCanvas(!useViewportMapping); } catch (e) { /* ignore */ }
	        try { canvas.calcOffset(); } catch (e) { /* ignore */ }
	      }
	    };

	    // Redimensionado libre (drag) del campo en pantalla.
	    // Esto NO toca posiciones ni escala objetos: solo cambia el tamaño del stage/canvas.
	    // En modo viewportTransform (por defecto), los objetos mantienen su tamaño relativo.
	    const initPitchResizer = () => {
	      if (!pitchResizeHandle || !stage) return;
	      let resizing = false;
	      let start = null;
	      let raf = 0;
	      const stopRaf = () => {
	        if (raf) {
	          try { window.cancelAnimationFrame(raf); } catch (error) { /* ignore */ }
	          raf = 0;
	        }
	      };
	      const scheduleFit = () => {
	        if (raf) return;
	        raf = window.requestAnimationFrame(() => {
	          raf = 0;
	          try { fitCanvas(!useViewportMapping); } catch (error) { /* ignore */ }
	          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
	          try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
	        });
	      };
	      const onMove = (event) => {
	        if (!resizing || !start) return;
	        const dx = (Number(event.clientX) || 0) - start.x;
	        // Solo controlamos el ancho (mantiene aspect ratio vía CSS).
	        const desiredW = clamp(start.width + dx, 320, 2400);
	        const base = stageBaseMaxWidth();
	        const next = writeStageFactor(desiredW / Math.max(1, base));
	        // Actualiza sin reflow pesado: set maxWidth directo.
	        try { stage.style.maxWidth = `${Math.round(base * next)}px`; } catch (error) { /* ignore */ }
	        if (stageSizeLabel) stageSizeLabel.textContent = `Campo ${Math.round(next * 100)}%`;
	        scheduleFit();
	        try { event.preventDefault(); } catch (error) { /* ignore */ }
	      };
	      const end = () => {
	        if (!resizing) return;
	        resizing = false;
	        start = null;
	        stopRaf();
	        // Ajuste final + preview.
	        try { applyStageSizeUi(); } catch (error) { /* ignore */ }
	        try { refreshLivePreview(); } catch (error) { /* ignore */ }
	        try { setStatus('Tamaño de campo actualizado.'); } catch (error) { /* ignore */ }
	      };
	      pitchResizeHandle.addEventListener('pointerdown', (event) => {
	        try { event.preventDefault(); } catch (error) { /* ignore */ }
	        try { event.stopPropagation(); } catch (error) { /* ignore */ }
	        try { pitchResizeHandle.setPointerCapture(event.pointerId); } catch (error) { /* ignore */ }
	        const rect = stage.getBoundingClientRect();
	        resizing = true;
	        start = {
	          x: Number(event.clientX) || 0,
	          width: Number(rect?.width) || stage.clientWidth || 800,
	        };
	      });
	      pitchResizeHandle.addEventListener('pointermove', onMove);
	      pitchResizeHandle.addEventListener('pointerup', end);
	      pitchResizeHandle.addEventListener('pointercancel', end);
	      pitchResizeHandle.addEventListener('lostpointercapture', end);
	      window.addEventListener('blur', end);
	    };
		    const syncZoomUi = () => {
		      if (zoomInput) zoomInput.value = String(pitchZoom.toFixed(2));
		      if (zoomLabel) zoomLabel.textContent = `${Math.round(pitchZoom * 100)}%`;
		      viewportEl?.classList.toggle('is-zoomed', pitchZoom > 1.02);
		      // En modo viewportTransform, el zoom no cambia el tamaño del stage: cambia la escala del viewport.
		      if (useViewportMapping) {
		        try { applyViewportTransformToWorld(); } catch (error) { /* ignore */ }
		        try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
		        try { canvas.calcOffset(); } catch (error) { /* ignore */ }
		        return;
		      }
		      // Fallback legacy: el zoom cambia tamaño del stage.
		      stage.style.setProperty('--pitch-zoom', String(pitchZoom));
		      try {
		        window.requestAnimationFrame(() => {
		          try { fitCanvas(true); } catch (error) { /* ignore */ }
		          try { applyPitchSurface(presetSelect.value || 'full_pitch', pitchOrientation); } catch (error) { /* ignore */ }
		          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
		        });
		      } catch (error) {
		        try { fitCanvas(true); } catch (e) { /* ignore */ }
		        try { applyPitchSurface(presetSelect.value || 'full_pitch', pitchOrientation); } catch (e) { /* ignore */ }
		        try { canvas.calcOffset(); } catch (e) { /* ignore */ }
		      }
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
            canvas_width: parseIntSafe(item.canvas_width) || 0,
            canvas_height: parseIntSafe(item.canvas_height) || 0,
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
		      if (isSimulating) return;
		      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
		      persistActiveStepMeta();
		      timeline[activeStepIndex].canvas_state = serializeCanvasOnly();
		      const { w, h } = worldSize();
		      timeline[activeStepIndex].canvas_width = Math.round(w || 0);
		      timeline[activeStepIndex].canvas_height = Math.round(h || 0);
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
        if (scenarioTitleInput) {
          scenarioTitleInput.value = '';
          scenarioTitleInput.disabled = true;
        }
        if (scenarioDurationInput) {
          scenarioDurationInput.value = '3';
          scenarioDurationInput.disabled = true;
        }
        return;
      }
      if (stepTitleInput) stepTitleInput.value = active.title || `Paso ${activeStepIndex + 1}`;
      if (stepDurationInput) stepDurationInput.value = String(active.duration || 3);
      if (scenarioTitleInput) {
        scenarioTitleInput.disabled = false;
        scenarioTitleInput.value = active.title || `Escenario ${activeStepIndex + 1}`;
      }
      if (scenarioDurationInput) {
        scenarioDurationInput.disabled = false;
        scenarioDurationInput.value = String(active.duration || 3);
      }
    };
    const renderTimeline = () => {
      const targets = [timelineList, timelineListPopover].filter(Boolean);
      if (!targets.length) return;
      if (!timeline.length) {
        targets.forEach((node) => {
          node.innerHTML = '<div class="timeline-empty">Todavía no hay escenarios. Diseña el primer escenario y pulsa “+ Escenario”.</div>';
        });
        syncStepInputs();
        return;
      }
      targets.forEach((node) => { node.innerHTML = ''; });
      timeline.forEach((step, index) => {
        targets.forEach((node) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = `timeline-step${index === activeStepIndex ? ' is-active' : ''}`;
          button.dataset.stepIndex = String(index);
          button.innerHTML = `
            <div>
              <strong>${step.title || `Escenario ${index + 1}`}</strong>
              <span>${step.duration || 3} s · escenario ${index + 1}</span>
            </div>
            <span>${index === activeStepIndex ? 'Editando' : 'Abrir'}</span>
          `;
          node.appendChild(button);
        });
      });
      syncStepInputs();
    };
    const scaleLoadedObjects = (sourceWidth, sourceHeight) => {
      const fromW = Number(sourceWidth) || 0;
      const fromH = Number(sourceHeight) || 0;
      const toW = Number(canvas.getWidth()) || 0;
      const toH = Number(canvas.getHeight()) || 0;
      if (fromW <= 0 || fromH <= 0 || toW <= 0 || toH <= 0) return false;
      if (Math.abs(fromW - toW) < 2 && Math.abs(fromH - toH) < 2) return false;
      const scaleX = toW / fromW;
      const scaleY = toH / fromH;
      const uniformScale = Math.min(scaleX, scaleY);
      canvas.getObjects().forEach((item) => {
        if (!item) return;
        item.set({
          left: (Number(item.left) || 0) * scaleX,
          top: (Number(item.top) || 0) * scaleY,
          scaleX: clampScale((Number(item.scaleX) || 1) * uniformScale),
          scaleY: clampScale((Number(item.scaleY) || 1) * uniformScale),
        });
        item.setCoords();
      });
      return true;
    };
	    const loadCanvasSnapshot = (rawState, callback, options = {}) => {
	      const parsed = sanitizeLoadedState(rawState);
	      const sourceWidth = Number(options?.sourceWidth) || 0;
	      const sourceHeight = Number(options?.sourceHeight) || 0;
	      if (sourceWidth > 0 && sourceHeight > 0) {
	        worldWidth = sourceWidth;
	        worldHeight = sourceHeight;
	      }
	      canvas.__loading = true;
	      canvas.loadFromJSON(parsed, () => {
	        if (!useViewportMapping) {
	          // Compat: si el canvas se creó en otra resolución, reescalamos los objetos cargados
	          // para que las tareas guardadas no cambien de posición al adaptar el editor.
	          scaleLoadedObjects(sourceWidth, sourceHeight);
	        } else {
	          // En modo viewport, NO mutamos coordenadas: ajustamos el viewport para encajar el "mundo" guardado.
	          try { syncWorldFromInputs(); } catch (e) { /* ignore */ }
	          try { applyViewportTransformToWorld(); } catch (e) { /* ignore */ }
	        }
	        // Compat: algunas tareas antiguas guardaron chapas tipo "camiseta". Al abrirlas,
	        // las convertimos a estilo "disco" para que se parezcan a la plantilla disponible.
        // Solo afecta a objetos con data.kind='token' y token_kind de jugadores.
        try {
          const playerTokenKinds = new Set(['player_local', 'player_away', 'player_rival', 'goalkeeper_local']);
          const current = canvas.getObjects().slice();
          const active = canvas.getActiveObject();
          const replacementMap = new Map();
          const hasRole = (obj, expected) =>
            Array.isArray(obj?._objects)
            && obj._objects.some((child) => safeText(child?.data?.role) === expected);
          const hasTokenRoles = (obj) =>
            Array.isArray(obj?._objects)
            && obj._objects.some((child) => {
              const role = safeText(child?.data?.role);
              return role && role.startsWith('token_');
            });
          const shouldConvertToken = (obj, tokenKind) => {
            // player_local: siempre convertimos si NO lleva el grupo de stripes nuevo.
            // Esto arregla tareas existentes creadas con el clip por-rect (que se veía como "camiseta")
            // sin tocar el estilo ya migrado.
            if (tokenKind === 'player_local') return !hasRole(obj, 'token_stripes');
            // Otros: convertimos solo si no es el estilo nuevo (por roles).
            return !hasTokenRoles(obj);
          };
          const resolvePlayerForLegacy = (obj) => {
            const playerId = safeText(obj?.data?.playerId);
            if (playerId) {
              const found = players.find((item) => String(item.id) === String(playerId));
              if (found) return found;
            }
            const playerName = safeText(obj?.data?.playerName) || safeText(obj?.data?.name);
            const playerNumber = safeText(obj?.data?.playerNumber) || safeText(obj?.data?.number);
            if (!playerName && !playerNumber) return null;
            return { id: playerId, name: playerName, number: playerNumber, position: '' };
          };
          current.forEach((obj, index) => {
            const kind = safeText(obj?.data?.kind);
            if (kind !== 'token') return;
            const tokenKind = safeText(obj?.data?.token_kind);
            if (!playerTokenKinds.has(tokenKind)) return;
            if (!shouldConvertToken(obj, tokenKind)) return; // ya es el estilo nuevo
            const center = obj.getCenterPoint ? obj.getCenterPoint() : { x: Number(obj.left) || 0, y: Number(obj.top) || 0 };
            const legacyPlayer = resolvePlayerForLegacy(obj);
            if (typeof playerTokenFactory !== 'function') return;
            const factory = playerTokenFactory(tokenKind, legacyPlayer);
            if (typeof factory !== 'function') return;
            const fresh = factory(center.x, center.y);
            if (!fresh) return;
            const locked = obj?.data?.locked;
            fresh.set({
              angle: Number(obj.angle) || 0,
              scaleX: clampScale(Number(obj.scaleX) || 1),
              scaleY: clampScale(Number(obj.scaleY) || 1),
              opacity: obj.opacity == null ? 1 : obj.opacity,
            });
            fresh.data = { ...(fresh.data || {}), locked };
            replacementMap.set(obj, fresh);
            canvas.remove(obj);
            canvas.insertAt(fresh, index, false);
          });
          if (active && replacementMap.has(active)) {
            canvas.setActiveObject(replacementMap.get(active));
          }
        } catch (error) {
          // ignore conversion errors
        }
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
      const fallbackWidth = parseIntSafe(options.sourceWidth) || 0;
      const fallbackHeight = parseIntSafe(options.sourceHeight) || 0;
      if (timeline.length && (fallbackWidth || fallbackHeight)) {
        timeline = timeline.map((step) => ({
          ...step,
          canvas_width: step.canvas_width || fallbackWidth,
          canvas_height: step.canvas_height || fallbackHeight,
        }));
      }
      const nextIndex = timeline.length
        ? clamp(Number(parsed.active_step_index) || 0, 0, timeline.length - 1)
        : -1;
      activeStepIndex = nextIndex;
      const sourceState = activeStepIndex >= 0 ? timeline[activeStepIndex].canvas_state : parsed;
      const sourceWidth = (activeStepIndex >= 0 ? parseIntSafe(timeline[activeStepIndex]?.canvas_width) : 0) || parseIntSafe(options.sourceWidth) || 0;
      const sourceHeight = (activeStepIndex >= 0 ? parseIntSafe(timeline[activeStepIndex]?.canvas_height) : 0) || parseIntSafe(options.sourceHeight) || 0;
      loadCanvasSnapshot(sourceState, () => {
        renderTimeline();
        if (options.pushHistory) pushHistory();
      }, { sourceWidth, sourceHeight });
    };
	    const pushHistory = () => {
	      if (isSimulating) return;
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
		      const syncStageAspectFromSvg = () => {
		        try {
		          const viewBoxRaw = safeText(svgSurface.getAttribute('viewBox'));
		          const parts = viewBoxRaw.split(/\s+/).map((v) => Number(v)).filter((n) => Number.isFinite(n));
		          if (parts.length >= 4) {
		            const vbW = parts[2];
		            const vbH = parts[3];
		            if (vbW > 0 && vbH > 0) {
		              // Fuerza ratio exacto del contenedor al del SVG para evitar "barras" (sobre todo en vertical
		              // cuando por CSS/clases no coincide el aspect-ratio).
		              stage.style.aspectRatio = `${vbW} / ${vbH}`;
		            }
		          }
		        } catch (error) { /* ignore */ }
		      };
		      const applyFromRoot = (root) => {
		        svgSurface.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
		        svgSurface.setAttribute('viewBox', root.getAttribute('viewBox') || '-2 -2 1054 684');
		        svgSurface.setAttribute('preserveAspectRatio', root.getAttribute('preserveAspectRatio') || 'xMidYMid meet');
		        const pitchBox = root.getAttribute('data-pitch-box') || '';
		        if (pitchBox) svgSurface.setAttribute('data-pitch-box', pitchBox);
		        else svgSurface.removeAttribute('data-pitch-box');
		        while (svgSurface.firstChild) svgSurface.removeChild(svgSurface.firstChild);
		        Array.from(root.childNodes).forEach((child) => {
		          svgSurface.appendChild(svgSurface.ownerDocument.importNode(child, true));
		        });
		        syncStageAspectFromSvg();
		      };

	      // 1) Ruta normal: DOMParser + import de nodos (evita <svg> anidado).
	      try {
	        const parsed = new DOMParser().parseFromString(markup, 'image/svg+xml');
	        const rootTag = parsed.documentElement;
	        let root = rootTag;
	        if (root && root.tagName && root.tagName.toLowerCase() !== 'svg') {
	          // Safari/Edge pueden devolver <parsererror> como documentElement; buscamos el primer <svg>.
	          const candidate = parsed.querySelector && parsed.querySelector('svg');
	          if (candidate) root = candidate;
	        }
	        if (root && root.tagName && root.tagName.toLowerCase() === 'svg') {
	          applyFromRoot(root);
	          return;
	        }
	      } catch (error) {
	        // sigue al fallback
	      }

	      // 2) Fallback robusto: extrae el contenido interior del <svg> serializado y lo inserta dentro del <svg> existente.
	      // Esto evita que aparezca el campo "pequeñísimo" con grandes márgenes (por <svg> anidado con tamaño por defecto 300x150).
	      try {
	        const openMatch = markup.match(/<svg\b([^>]*)>/i);
	        const closeIndex = markup.lastIndexOf('</svg>');
	        if (openMatch && closeIndex > 0) {
	          const openIndex = openMatch.index || 0;
	          const openEnd = markup.indexOf('>', openIndex);
	          if (openEnd > openIndex) {
	            const attrs = openMatch[1] || '';
	            const inner = markup.slice(openEnd + 1, closeIndex);
	            const readAttr = (name) => {
	              const re = new RegExp(`\\b${name}\\s*=\\s*["']([^"']+)["']`, 'i');
	              const m = attrs.match(re);
	              return m ? safeText(m[1]) : '';
	            };
	            const viewBox = readAttr('viewBox') || '-2 -2 1054 684';
	            const preserve = readAttr('preserveAspectRatio') || 'xMidYMid meet';
	            const pitchBox = readAttr('data-pitch-box');
		            svgSurface.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
		            svgSurface.setAttribute('viewBox', viewBox);
		            svgSurface.setAttribute('preserveAspectRatio', preserve);
		            if (pitchBox) svgSurface.setAttribute('data-pitch-box', pitchBox);
		            else svgSurface.removeAttribute('data-pitch-box');
		            svgSurface.innerHTML = inner;
		            syncStageAspectFromSvg();
		            return;
		          }
		        }
		      } catch (error) {
	        // ignore
	      }

	      // Último recurso: si no podemos parsear, dejamos el contenido vacío (mejor que romper el layout con <svg> anidado).
	      svgSurface.innerHTML = '';
	    };

    const setPreset = (presetValue) => {
      const preset = safeText(presetValue, 'full_pitch');
      presetSelect.value = preset;
      if (pitchFormatInput && PITCH_FORMAT_BY_PRESET[preset]) pitchFormatInput.value = PITCH_FORMAT_BY_PRESET[preset];
      presetButtons.forEach((button) => button.classList.toggle('is-active', safeText(button.dataset.preset) === preset));
      if (surfaceTriggerLabel) surfaceTriggerLabel.textContent = PRESET_LABEL[preset] || 'Campo completo';
      applyPitchSurface(preset, pitchOrientation);
      // Al cambiar de superficie cambia el aspect-ratio del stage. Si no reajustamos el canvas,
      // los punteros quedan desincronizados y “parece” que las chapas no se dibujan (se colocan fuera de vista).
      try {
        window.requestAnimationFrame(() => {
          try { fitCanvas(!useViewportMapping); } catch (error) { /* ignore */ }
          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
          try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
        });
      } catch (error) {
        try { fitCanvas(!useViewportMapping); } catch (e) { /* ignore */ }
        try { canvas.calcOffset(); } catch (e) { /* ignore */ }
      }
      refreshLivePreview();
      setStatus(`Superficie preparada: ${PRESET_LABEL[preset] || 'campo'} en ${ORIENTATION_LABEL[pitchOrientation]}.`);
    };
				    const applyPitchOrientation = (nextOrientation, options = {}) => {
				      const normalized = safeText(nextOrientation, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
				      if (normalized === pitchOrientation && !options.force) return;
				      const fromOrientation = pitchOrientation;
				      const fromWorld = worldSize();
				      const toWorld = (normalized !== fromOrientation)
				        ? { w: Math.max(1, Number(fromWorld.h) || 0), h: Math.max(1, Number(fromWorld.w) || 0) }
				        : { w: Math.max(1, Number(fromWorld.w) || 0), h: Math.max(1, Number(fromWorld.h) || 0) };
				      const remapPoint = (x, y) => {
				        const fromW = Math.max(1, Number(fromWorld.w) || 1);
				        const fromH = Math.max(1, Number(fromWorld.h) || 1);
				        const toW = Math.max(1, Number(toWorld.w) || 1);
				        const toH = Math.max(1, Number(toWorld.h) || 1);
				        const rx = clamp(Number(x) / fromW, 0, 1);
				        const ry = clamp(Number(y) / fromH, 0, 1);
				        if (fromOrientation === 'landscape' && normalized === 'portrait') {
				          // Rotación 90º CCW: derecha -> arriba.
				          return { x: ry * toW, y: (1 - rx) * toH };
				        }
				        if (fromOrientation === 'portrait' && normalized === 'landscape') {
				          // Rotación 90º CW: arriba -> derecha.
				          return { x: (1 - ry) * toW, y: rx * toH };
				        }
				        return { x: rx * toW, y: ry * toH };
				      };
				      const shouldRotateAngle = (objLike) => {
				        const kind = safeText(objLike?.data?.kind);
				        if (!kind) {
				          const t = safeText(objLike?.type);
				          if (t === 'text' || t === 'i-text') return false;
				          return true;
				        }
				        if (kind === 'token' || kind === 'text') return false;
				        if (kind.startsWith('emoji_')) return false;
				        return true;
				      };
				      const deltaAngle = (fromOrientation === 'landscape' && normalized === 'portrait') ? -90 : 90;
				      const remapCanvasObjects = () => {
				        if (!options.preserveObjects) return false;
				        if (normalized === fromOrientation) return false;
				        const objects = canvas.getObjects() || [];
				        if (!objects.length) return false;
				        // Evita “activeSelection” inconsistente durante el remapeo.
				        try { canvas.discardActiveObject(); } catch (error) { /* ignore */ }
				        objects.forEach((obj) => {
				          if (!obj) return;
				          const center = obj.getCenterPoint ? obj.getCenterPoint() : { x: Number(obj.left) || 0, y: Number(obj.top) || 0 };
				          const mapped = remapPoint(center.x, center.y);
				          try {
				            if (typeof obj.setPositionByOrigin === 'function' && window.fabric) {
				              obj.setPositionByOrigin(new fabric.Point(mapped.x, mapped.y), 'center', 'center');
				            } else {
				              obj.set({ left: mapped.x, top: mapped.y, originX: 'center', originY: 'center' });
				            }
				          } catch (error) {
				            obj.set({ left: mapped.x, top: mapped.y });
				          }
				          if (shouldRotateAngle(obj)) {
				            obj.set({ angle: (Number(obj.angle) || 0) + deltaAngle });
				          }
				          try { obj.setCoords(); } catch (error) { /* ignore */ }
				        });
				        // Mantén los fondos detrás si no están en modo edición.
				        try {
				          canvas.getObjects().forEach((obj) => {
				            if (!obj || !isBackgroundShape(obj) || obj?.data?.background_edit) return;
				            canvas.sendToBack(obj);
				          });
				        } catch (error) { /* ignore */ }
				        return true;
				      };
				      const remapSerializedState = (state) => {
				        if (!state || typeof state !== 'object') return state;
				        const objects = Array.isArray(state.objects) ? state.objects : [];
				        if (!objects.length) return state;
				        const nextObjects = objects.map((obj) => {
				          if (!obj || typeof obj !== 'object') return obj;
				          const left = Number(obj.left);
				          const top = Number(obj.top);
				          if (!Number.isFinite(left) || !Number.isFinite(top)) return obj;
				          const mapped = remapPoint(left, top);
				          const next = { ...obj, left: mapped.x, top: mapped.y };
				          if (normalized !== fromOrientation && shouldRotateAngle(obj)) {
				            const a = Number(obj.angle) || 0;
				            next.angle = a + deltaAngle;
				          }
				          return next;
				        });
				        return { ...state, objects: nextObjects };
				      };
				      const remapTimelineSnapshots = () => {
				        if (!options.preserveObjects) return false;
				        if (normalized === fromOrientation) return false;
				        if (!Array.isArray(timeline) || !timeline.length) return false;
				        timeline = timeline.map((step) => {
				          if (!step || typeof step !== 'object') return step;
				          return {
				            ...step,
				            canvas_state: remapSerializedState(step.canvas_state),
				            canvas_width: toWorld.w,
				            canvas_height: toWorld.h,
				          };
				        });
				        return true;
				      };

				      // 1) Remapea el contenido a la nueva orientación (para que no “se descoloque”).
				      const didRemapCanvas = remapCanvasObjects();
				      const didRemapTimeline = remapTimelineSnapshots();

				      // 2) Actualiza el tamaño del “mundo” (viewBox) para que el lienzo y el SVG del campo
				      // compartan el mismo sistema de coordenadas.
				      if (widthInput) widthInput.value = String(Math.round(toWorld.w || 0));
				      if (heightInput) heightInput.value = String(Math.round(toWorld.h || 0));
				      worldWidth = Math.round(toWorld.w || 0);
				      worldHeight = Math.round(toWorld.h || 0);
				      viewportPanX = 0;
				      viewportPanY = 0;

				      pitchOrientation = normalized;
				      syncOrientationUi();
				      applyStageSizeUi({ noFit: true });
				      if (!zoomTouched) {
				        pitchZoom = 1.0;
				        syncZoomUi();
				      }
				      fitCanvas(!useViewportMapping && options.preserveObjects !== false);
				      setPreset(presetSelect.value || 'full_pitch');
				      if (!options.silent) setStatus(`Campo en ${ORIENTATION_LABEL[pitchOrientation]}.`);
				      if (options.pushHistory) {
				        if (didRemapCanvas || didRemapTimeline) {
				          try { persistActiveStepSnapshot(); } catch (error) { /* ignore */ }
				        }
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
	      const { w, h } = worldSize();
	      const left = clamp(pointer.x || 0, 24, w - 24);
	      const top = clamp(pointer.y || 0, 24, h - 24);
	      return factory(left, top);
	    };

			    const addObject = (object) => {
			      if (!object) return;
			      // Figuras de fondo: al crearlas queremos permitir edición inmediata (mover/escala).
			      // Luego se desactiva automáticamente al seleccionar otra cosa o con Escape.
			      if (isBackgroundShape(object)) {
			        object.data = object.data || {};
			        object.data.background_edit = true;
			      }
			      normalizeEditableObject(object);
			      canvas.add(object);
		      if (isBackgroundShape(object)) canvas.sendToBack(object);
		      canvas.setActiveObject(object);
		      canvas.requestRenderAll();
		      pushHistory();
		      syncInspector();
			      if (isBackgroundShape(object)) {
			        setStatus('Fondo añadido en modo edición. Ajusta tamaño/posición y pulsa Esc (o selecciona otro elemento) para volver a modo “pasar a través”.');
			      }
			    };

			    const buildPdfAssetObject = (assetId, left, top, options = {}) => {
			      const id = normalizePdfAssetId(assetId);
			      const img = pdfAssetImages.get(id);
			      const meta = pdfAssetMeta.get(id);
			      const desired = clamp(Number(options.desiredSize) || 56, 28, 180);
			      if (img && (img.naturalWidth || img.width)) {
			        const naturalW = Number(img.naturalWidth || img.width || 1);
			        const naturalH = Number(img.naturalHeight || img.height || 1);
			        const baseScale = desired / Math.max(1, Math.max(naturalW, naturalH));
			        const imageObj = new fabric.Image(img, {
			          left,
			          top,
			          originX: 'center',
			          originY: 'center',
			          scaleX: baseScale,
			          scaleY: baseScale,
			          data: { kind: 'pdf_asset', asset_id: id, title: safeText(meta?.title) },
			        });
			        try { imageObj.objectCaching = false; } catch (e) { /* ignore */ }
			        try { imageObj.noScaleCache = true; } catch (e) { /* ignore */ }
			        return imageObj;
			      }
			      // Placeholder: se reemplaza cuando la imagen termine de cargar.
			      ensurePdfAssetLoaded(id);
			      const box = new fabric.Rect({
			        left: 0,
			        top: 0,
			        originX: 'center',
			        originY: 'center',
			        width: desired,
			        height: desired,
			        rx: 10,
			        ry: 10,
			        fill: 'rgba(255,255,255,0.08)',
			        stroke: 'rgba(34,211,238,0.50)',
			        strokeWidth: 2,
			      });
			      const label = new fabric.Text('PDF', {
			        left: 0,
			        top: 0,
			        originX: 'center',
			        originY: 'center',
			        fontSize: 14,
			        fontWeight: '800',
			        fill: 'rgba(226,232,240,0.9)',
			      });
			      const group = new fabric.Group([box, label], {
			        left,
			        top,
			        originX: 'center',
			        originY: 'center',
			        data: { kind: 'pdf_asset', asset_id: id, placeholder: true, desiredSize: desired, title: safeText(meta?.title) },
			      });
			      try { group.objectCaching = false; } catch (e) { /* ignore */ }
			      try { group.noScaleCache = true; } catch (e) { /* ignore */ }
			      return group;
			    };

			    const replacePdfAssetPlaceholders = (assetId) => {
			      const id = normalizePdfAssetId(assetId);
			      const img = pdfAssetImages.get(id);
			      if (!img) return;
			      const objects = canvas.getObjects().slice();
			      objects.forEach((obj) => {
			        if (!obj || !obj.data) return;
			        if (safeText(obj.data.kind) !== 'pdf_asset') return;
			        if (safeText(obj.data.asset_id) !== id) return;
			        if (!obj.data.placeholder) return;
			        const center = obj.getCenterPoint();
			        const desired = clamp(Number(obj.data.desiredSize) || 56, 28, 180);
			        const naturalW = Number(img.naturalWidth || img.width || 1);
			        const naturalH = Number(img.naturalHeight || img.height || 1);
			        const baseScale = desired / Math.max(1, Math.max(naturalW, naturalH));
			        const next = new fabric.Image(img, {
			          left: center.x,
			          top: center.y,
			          originX: 'center',
			          originY: 'center',
			          angle: Number(obj.angle) || 0,
			          scaleX: baseScale * (Number(obj.scaleX) || 1),
			          scaleY: baseScale * (Number(obj.scaleY) || 1),
			          data: { kind: 'pdf_asset', asset_id: id, title: safeText(obj.data.title) },
			        });
			        try { next.objectCaching = false; } catch (e) { /* ignore */ }
			        try { next.noScaleCache = true; } catch (e) { /* ignore */ }
			        normalizeEditableObject(next);
			        canvas.remove(obj);
			        canvas.add(next);
			      });
			      canvas.requestRenderAll();
			    };
			    const flushPdfAssetPendingRefresh = () => {
			      if (!pdfAssetPendingRefresh.size) return;
			      const ids = Array.from(pdfAssetPendingRefresh);
			      pdfAssetPendingRefresh.clear();
			      ids.forEach((id) => {
			        try { replacePdfAssetPlaceholders(id); } catch (error) { /* ignore */ }
			      });
			    };
			    // Revisa en background por si las imágenes terminan de cargar después de añadirlas.
			    try { window.setInterval(flushPdfAssetPendingRefresh, 650); } catch (e) { /* ignore */ }
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
	      const screenX = ((event.clientX - rect.left) / rect.width) * canvas.getWidth();
	      const screenY = ((event.clientY - rect.top) / rect.height) * canvas.getHeight();
	      let x = screenX;
	      let y = screenY;
	      if (useViewportMapping) {
	        const vpt = canvas.viewportTransform || [1, 0, 0, 1, 0, 0];
	        const scale = Number(vpt[0]) || 1;
	        const offsetX = Number(vpt[4]) || 0;
	        const offsetY = Number(vpt[5]) || 0;
	        x = (screenX - offsetX) / scale;
	        y = (screenY - offsetY) / scale;
	      }
	      const { w, h } = worldSize();
	      return {
	        x: clamp(x, 24, w - 24),
	        y: clamp(y, 24, h - 24),
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
	      if (isSimulating) {
	        setStatus('Modo simulación: no se pueden añadir recursos. Sal del simulador para editar.', true);
	        return false;
	      }
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
      const playerName = safeText(
        player?.name,
        kind === 'goalkeeper_local' ? 'Portero' : (kind === 'player_rival' ? 'Rival' : 'Jugador'),
      );
      const displayName = shortPlayerName(playerName);
      const initials = safeText(playerName, kind === 'player_rival' ? 'Rival' : 'Jugador')
        .split(/\s+/)
        .map((piece) => piece[0] || '')
        .join('')
        .slice(0, 2)
        .toUpperCase() || label;
	      const tokenParts = [];
	      let baseRadius = 22;
	      // Estilo "chapa" (igual que en la plantilla de abajo): disco con dorsal centrado y nombre simple.
	      // Evitamos el "jersey" y los cartuchos para que dentro del campo se vea igual que fuera.
	      if (kind === 'player_local' || kind === 'player_away' || kind === 'goalkeeper_local') {
	        const radius = 22;
	        baseRadius = radius;
	        const isAway = kind === 'player_away';
	        const isGoalkeeper = kind === 'goalkeeper_local';
	        const baseCircle = new fabric.Circle({
	          radius,
	          fill: isAway ? '#facc15' : '#ffffff',
	          stroke: 'rgba(255,255,255,0.92)',
	          strokeWidth: 2,
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: 0,
	          shadow: 'rgba(15,23,42,0.28) 0 6px 14px',
	        });
	        baseCircle.data = { role: isAway ? 'token_fill' : 'token_base' };
	        tokenParts.push(baseCircle);
	        if (isGoalkeeper) {
	          // Portero: disco azul con brillo suave (aproxima el gradiente CSS del bank).
	          const gkBg = new fabric.Circle({
	            radius: radius - 1,
	            originX: 'center',
	            originY: 'center',
	            left: 0,
	            top: 0,
	            strokeWidth: 0,
	            fill: new fabric.Gradient({
	              type: 'linear',
	              gradientUnits: 'percentage',
	              coords: { x1: 0, y1: 0, x2: 1, y2: 1 },
	              colorStops: [
	                { offset: 0, color: '#1d4ed8' },
	                { offset: 1, color: '#0ea5e9' },
	              ],
	            }),
	          });
	          gkBg.data = { role: 'token_fill' };
	          tokenParts.push(gkBg);
	          const highlight = new fabric.Circle({
	            radius: 10,
	            originX: 'center',
	            originY: 'center',
	            left: -7,
	            top: -10,
	            fill: 'rgba(255,255,255,0.28)',
	            strokeWidth: 0,
	          });
	          highlight.data = { role: 'token_highlight' };
	          tokenParts.push(highlight);
	        } else if (!isAway) {
	          const stripeWidth = 8;
	          const stripeHeight = 46;
	          const stripeCount = Math.ceil((radius * 2) / stripeWidth) + 1;
	          const start = (-radius) + (stripeWidth / 2);
	          const stripes = [];
	          for (let i = 0; i < stripeCount; i += 1) {
	            const isGreen = i % 2 === 0;
	            const stripe = new fabric.Rect({
	              left: start + (i * stripeWidth),
	              top: 0,
	              width: stripeWidth,
	              height: stripeHeight,
	              fill: isGreen ? '#0f7a35' : '#f8fafc',
	              originX: 'center',
	              originY: 'center',
	            });
	            if (isGreen) stripe.data = { role: 'token_stripe' };
	            stripes.push(stripe);
	          }
	          // Clip a nivel de grupo (más robusto que aplicar el mismo clipPath a cada rect).
	          const stripeGroup = new fabric.Group(stripes, {
	            originX: 'center',
	            originY: 'center',
	            left: 0,
	            top: 0,
	            selectable: false,
	            evented: false,
	          });
	          stripeGroup.clipPath = new fabric.Circle({
	            radius: radius - 1.2,
	            originX: 'center',
	            originY: 'center',
	            left: 0,
	            top: 0,
	          });
	          stripeGroup.data = { role: 'token_stripes' };
	          tokenParts.push(stripeGroup);
	        }
	        const numberText = new fabric.Text(isGoalkeeper ? 'GK' : label, {
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: 0,
	          fontSize: 15,
	          fontWeight: '800',
	          fill: isAway ? '#0b1220' : '#ffffff',
	          shadow: 'rgba(15,23,42,0.65) 0 1px 2px',
	        });
	        numberText.data = { role: 'token_number' };
	        tokenParts.push(numberText);
	        const nameText = new fabric.Text(displayName, {
	          originX: 'center',
	          originY: 'center',
	          left: 0,
	          top: -34,
	          fontSize: 10,
	          fontWeight: '700',
	          fill: '#e2e8f0',
	          shadow: 'rgba(15,23,42,0.55) 0 1px 2px',
	        });
	        nameText.data = { role: 'token_name' };
	        tokenParts.push(nameText);
	      } else {
	        baseRadius = kind === 'goalkeeper_local' ? 24 : 21;
	        const circle = new fabric.Circle({
	          radius: baseRadius,
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
        const initialsText = new fabric.Text(initials, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 0,
          fontSize: 12,
          fontWeight: '700',
          fill: palette.text,
        });
        initialsText.data = { role: 'token_initials' };
        tokenParts.push(initialsText);
        const labelText = new fabric.Text(label, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: 26,
          fontSize: 10,
          fontWeight: '700',
          fill: '#ffffff',
          backgroundColor: 'rgba(15,23,42,0.92)',
        });
        labelText.data = { role: 'token_number' };
        tokenParts.push(labelText);
        const nameBg = new fabric.Rect({
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
        });
        nameBg.data = { role: 'token_name_bg' };
	        tokenParts.push(nameBg);
	        const nameText = new fabric.Text(displayName, {
          originX: 'center',
          originY: 'center',
          left: 0,
          top: -35,
          fontSize: 10,
          fontWeight: '700',
          fill: '#f8fafc',
        });
        nameText.data = { role: 'token_name' };
	        tokenParts.push(nameText);
	      }
		      const group = new fabric.Group(tokenParts, {
	        left,
	        top,
	        originX: 'center',
	        originY: 'center',
		        data: {
		          kind: 'token',
		          token_kind: kind,
		          token_base_radius: baseRadius,
		          token_size: 'm',
		          color: kind === 'player_local' ? '#1f7a38' : (kind === 'player_away' ? '#facc15' : palette.fill),
		          playerId: player?.id || '',
		          playerName,
		          playerNumber: safeText(label),
		        },
		      });
		      // Evita blur por cache rasterizado al escalar/zoomear; los tokens son vectoriales.
		      try { group.objectCaching = false; } catch (error) { /* ignore */ }
		      try { group.noScaleCache = true; } catch (error) { /* ignore */ }
		      try {
		        tokenParts.forEach((part) => {
		          if (!part) return;
		          try { part.objectCaching = false; } catch (e) { /* ignore */ }
		          try { part.noScaleCache = true; } catch (e) { /* ignore */ }
		        });
		      } catch (error) { /* ignore */ }
			      return group;
			    };

	    const buildGoalGroup = (left, top, style = 'net', options = {}) => {
	      const stroke = safeText(options.stroke, '#f8fafc') || '#f8fafc';
	      const strokeWidth = clamp(Number(options.strokeWidth) || 3, 2, 8);
	      const baseW = Number(options.width) || 128;
	      const baseH = Number(options.height) || 74;
	      const w = clamp(baseW, 60, 260);
	      const h = clamp(baseH, 40, 200);

	      const parts = [];
	      const frameRx = style === 'posts' ? 2 : 8;
	      const front = new fabric.Rect({
	        left: 0,
	        top: 0,
	        originX: 'center',
	        originY: 'center',
	        width: w,
	        height: h,
	        rx: frameRx,
	        ry: frameRx,
	        fill: '',
	        stroke,
	        strokeWidth,
	      });
	      parts.push(front);

	      const addNetGrid = (gridW, gridH, offsetX = 0, offsetY = 0, stepX = 18, stepY = 16, opacity = 0.22) => {
	        const strokeLocal = `rgba(248,250,252,${opacity})`;
	        for (let x = -gridW / 2 + 14; x <= gridW / 2 - 14; x += stepX) {
	          parts.push(new fabric.Line([x + offsetX, -gridH / 2 + 10 + offsetY, x + offsetX, gridH / 2 - 10 + offsetY], {
	            stroke: strokeLocal,
	            strokeWidth: 1,
	            originX: 'center',
	            originY: 'center',
	            selectable: false,
	            evented: false,
	          }));
	        }
	        for (let y = -gridH / 2 + 10; y <= gridH / 2 - 10; y += stepY) {
	          parts.push(new fabric.Line([-gridW / 2 + 12 + offsetX, y + offsetY, gridW / 2 - 12 + offsetX, y + offsetY], {
	            stroke: strokeLocal,
	            strokeWidth: 1,
	            originX: 'center',
	            originY: 'center',
	            selectable: false,
	            evented: false,
	          }));
	        }
	      };

	      if (style === 'net') {
	        addNetGrid(w, h, 0, 0, 18, 16, 0.22);
	      } else if (style === '3d') {
	        const depthX = Math.max(10, Math.round(w * 0.11));
	        const depthY = Math.max(8, Math.round(h * 0.12));
	        const backW = Math.max(52, Math.round(w * 0.84));
	        const backH = Math.max(38, Math.round(h * 0.84));
	        const back = new fabric.Rect({
	          left: depthX,
	          top: depthY,
	          originX: 'center',
	          originY: 'center',
	          width: backW,
	          height: backH,
	          rx: 6,
	          ry: 6,
	          fill: '',
	          stroke: 'rgba(248,250,252,0.72)',
	          strokeWidth: Math.max(2, strokeWidth - 1),
	          selectable: false,
	          evented: false,
	        });
	        parts.push(back);

	        const frontLeft = { x: -w / 2, y: -h / 2 };
	        const frontRight = { x: w / 2, y: -h / 2 };
	        const frontBottomLeft = { x: -w / 2, y: h / 2 };
	        const frontBottomRight = { x: w / 2, y: h / 2 };
	        const backLeft = { x: depthX - (backW / 2), y: depthY - (backH / 2) };
	        const backRight = { x: depthX + (backW / 2), y: depthY - (backH / 2) };
	        const backBottomLeft = { x: depthX - (backW / 2), y: depthY + (backH / 2) };
	        const backBottomRight = { x: depthX + (backW / 2), y: depthY + (backH / 2) };

	        [
	          [frontLeft, backLeft],
	          [frontRight, backRight],
	          [frontBottomLeft, backBottomLeft],
	          [frontBottomRight, backBottomRight],
	        ].forEach(([a, b]) => {
	          parts.push(new fabric.Line([a.x, a.y, b.x, b.y], {
	            stroke: 'rgba(248,250,252,0.55)',
	            strokeWidth: Math.max(2, strokeWidth - 1),
	            selectable: false,
	            evented: false,
	          }));
	        });
	        addNetGrid(backW, backH, depthX, depthY, 16, 14, 0.18);
	        for (let i = 0; i < 5; i += 1) {
	          const t = (i + 1) / 6;
	          const x1 = backLeft.x + (backW * t);
	          const y1 = backLeft.y;
	          const x2 = backBottomLeft.x;
	          const y2 = backBottomLeft.y - (backH * t);
	          parts.push(new fabric.Line([x1, y1, x2, y2], {
	            stroke: 'rgba(248,250,252,0.14)',
	            strokeWidth: 1,
	            selectable: false,
	            evented: false,
	          }));
	        }
	      } else if (style === 'mini') {
	        addNetGrid(w, h, 0, 0, 22, 18, 0.16);
	      } else if (style === 'posts') {
	        // Solo marco: nada de red.
	      }

	      const group = new fabric.Group(parts, {
	        left,
	        top,
	        originX: 'center',
	        originY: 'center',
	        data: { kind: 'goal', goal_style: style, color: stroke, stroke_width: strokeWidth },
	      });
	      try { group.objectCaching = false; } catch (error) { /* ignore */ }
	      try { group.noScaleCache = true; } catch (error) { /* ignore */ }
	      try {
	        parts.forEach((part) => {
	          if (!part) return;
	          try { part.objectCaching = false; } catch (e) { /* ignore */ }
	          try { part.noScaleCache = true; } catch (e) { /* ignore */ }
	        });
	      } catch (error) { /* ignore */ }
	      return group;
	    };

		    const simpleFactory = (kind) => {
	      const normalized = safeText(kind);
	      if (normalized.startsWith('pdf_asset:')) {
	        const assetId = normalized.split(':')[1] || '';
	        return (left, top) => buildPdfAssetObject(assetId, left, top);
	      }
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
	      if (kind === 'cone_striped') {
	        return (left, top) => {
	          const fill = '#ef4444';
	          const stroke = '#7f1d1d';
	          const tri = new fabric.Triangle({
	            left: 0,
	            top: 0,
	            originX: 'center',
	            originY: 'center',
	            width: 26,
	            height: 26,
	            fill,
	            stroke,
	            strokeWidth: 1.5,
	            selectable: false,
	            evented: false,
	          });
	          const stripe1 = new fabric.Line([-10, -2, 10, -2], {
	            stroke: 'rgba(255,255,255,0.92)',
	            strokeWidth: 4,
	            strokeLineCap: 'round',
	            selectable: false,
	            evented: false,
	          });
	          const stripe2 = new fabric.Line([-8, 7, 8, 7], {
	            stroke: 'rgba(255,255,255,0.92)',
	            strokeWidth: 4,
	            strokeLineCap: 'round',
	            selectable: false,
	            evented: false,
	          });
	          const group = new fabric.Group([tri, stripe1, stripe2], {
	            left,
	            top,
	            originX: 'center',
	            originY: 'center',
	            data: { kind: 'cone-striped', color: fill, stroke_color: stroke },
	          });
	          try { group.objectCaching = false; } catch (e) { /* ignore */ }
	          try { group.noScaleCache = true; } catch (e) { /* ignore */ }
	          return group;
	        };
	      }
	      if (kind === 'pole_marker') {
	        return (left, top) => {
	          const stroke = '#22d3ee';
	          const pole = new fabric.Line([0, -26, 0, 16], {
	            stroke,
	            strokeWidth: 4,
	            strokeLineCap: 'round',
	            selectable: false,
	            evented: false,
	          });
	          const base = new fabric.Triangle({
	            left: 0,
	            top: 28,
	            originX: 'center',
	            originY: 'center',
	            width: 22,
	            height: 22,
	            angle: 180,
	            fill: stroke,
	            stroke: darkenHex(stroke, 0.45),
	            strokeWidth: 1.2,
	            selectable: false,
	            evented: false,
	          });
	          const group = new fabric.Group([pole, base], {
	            left,
	            top,
	            originX: 'center',
	            originY: 'center',
	            data: { kind: 'pole-marker', color: stroke },
	          });
	          try { group.objectCaching = false; } catch (e) { /* ignore */ }
	          try { group.noScaleCache = true; } catch (e) { /* ignore */ }
	          return group;
	        };
	      }
	      if (kind === 'ring') {
	        return (left, top) => new fabric.Circle({
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          radius: 22,
	          fill: '',
	          stroke: '#ef4444',
	          strokeWidth: 4,
	          data: { kind: 'ring', color: '#ef4444' },
	        });
	      }
		      if (kind === 'zone') {
		        return (left, top) => new fabric.Rect({
		          left, top, originX: 'center', originY: 'center',
		          width: 130, height: 84, fill: 'rgba(34,211,238,0.16)', stroke: '#22d3ee', strokeWidth: 3,
	          rx: 12, ry: 12, data: { kind: 'zone', color: '#22d3ee' },
	        });
	      }
	      if (kind === 'goal') return (left, top) => buildGoalGroup(left, top, 'net');
	      if (kind === 'goal_posts') return (left, top) => buildGoalGroup(left, top, 'posts');
	      if (kind === 'goal_3d') return (left, top) => buildGoalGroup(left, top, '3d');
	      if (kind === 'goal_mini') return (left, top) => buildGoalGroup(left, top, 'mini', { width: 96, height: 56 });
	      if (kind === 'line' || kind === 'line_solid') {
	        return (left, top) => new fabric.Line([-55, 0, 55, 0], {
	          left, top, originX: 'center', originY: 'center',
	          stroke: '#f8fafc', strokeWidth: 3, data: { kind: 'line' },
	        });
	      }
	      if (kind === 'line_thick') {
	        return (left, top) => new fabric.Line([-65, 0, 65, 0], {
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          stroke: '#f8fafc',
	          strokeWidth: 7,
	          data: { kind: 'line-thick' },
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
	      const buildArrowGroup = (left, top, options = {}) => {
	        const stroke = safeText(options.stroke, '#22d3ee');
	        const strokeWidth = clamp(Number(options.strokeWidth) || 4, 2, 18);
	        const dash = Array.isArray(options.dash) ? options.dash : null;
	        const cap = safeText(options.cap, 'round') || 'round';
	        const headSize = clamp(Number(options.headSize) || (strokeWidth >= 7 ? 28 : 18), 14, 44);
	        const headOffset = clamp(Number(options.headOffset) || (headSize / 2 + 6), 14, 60);
	        const baseLen = clamp(Number(options.baseLen) || 90, 60, 160);
	        const kind = safeText(options.kind, 'arrow');

	        const line = new fabric.Line([-(baseLen / 2), 0, (baseLen / 2) - (headSize / 2), 0], {
	          stroke,
	          strokeWidth,
	          strokeDashArray: dash || undefined,
	          strokeLineCap: cap,
	          originX: 'center',
	          originY: 'center',
	          selectable: false,
	          evented: false,
	        });
	        const head = new fabric.Triangle({
	          left: (baseLen / 2) - (headSize / 2) + headOffset,
	          top: 0,
	          width: headSize,
	          height: headSize,
	          angle: 90,
	          fill: stroke,
	          originX: 'center',
	          originY: 'center',
	          selectable: false,
	          evented: false,
	        });
	        const group = new fabric.Group([line, head], { left, top, originX: 'center', originY: 'center', data: { kind } });
	        try { group.objectCaching = false; } catch (e) { /* ignore */ }
	        try { group.noScaleCache = true; } catch (e) { /* ignore */ }
	        return group;
	      };

	      if (kind === 'arrow' || kind === 'arrow_solid') {
	        return (left, top) => buildArrowGroup(left, top, { kind: 'arrow' });
	      }
	      if (kind === 'arrow_thick') {
	        return (left, top) => buildArrowGroup(left, top, { kind: 'arrow-thick', stroke: '#f8fafc', strokeWidth: 9, headSize: 30, baseLen: 110 });
	      }
	      if (kind === 'arrow_dash') {
	        return (left, top) => buildArrowGroup(left, top, { kind: 'arrow-dash', dash: [12, 8] });
	      }
	      if (kind === 'arrow_dot') {
	        return (left, top) => buildArrowGroup(left, top, { kind: 'arrow-dot', dash: [2, 10], cap: 'round' });
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
	      if (kind === 'shape_rect_long') {
	        return (left, top) => new fabric.Rect({
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          width: 190,
	          height: 52,
	          rx: 10,
	          ry: 10,
	          fill: 'rgba(34,211,238,0.08)',
	          stroke: '#22d3ee',
	          strokeWidth: 3,
	          data: { kind: 'shape-rect-long' },
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
	      if (kind === 'shape_u') {
	        return (left, top) => new fabric.Path('M -60 -34 L -60 34 L 60 34 L 60 -34', {
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          stroke: '#22d3ee',
	          fill: '',
	          strokeWidth: 4,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          data: { kind: 'shape-u' },
	        });
	      }
	      const buildLaneShape = (left, top, columns = 3) => {
	        const colCount = clamp(Number(columns) || 3, 2, 6);
	        const width = 192;
	        const height = 52;
	        const stroke = '#22d3ee';
	        const outer = new fabric.Rect({
	          left: 0,
	          top: 0,
	          originX: 'center',
	          originY: 'center',
	          width,
	          height,
	          rx: 8,
	          ry: 8,
	          fill: 'rgba(34,211,238,0.06)',
	          stroke,
	          strokeWidth: 3,
	          selectable: false,
	          evented: false,
	        });
	        const lines = [];
	        for (let i = 1; i < colCount; i += 1) {
	          const x = -width / 2 + (width * (i / colCount));
	          lines.push(new fabric.Line([x, -height / 2, x, height / 2], {
	            stroke,
	            strokeWidth: 3,
	            selectable: false,
	            evented: false,
	          }));
	        }
	        const group = new fabric.Group([outer, ...lines], {
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          data: { kind: `shape-lane-${colCount}` },
	        });
	        try { group.objectCaching = false; } catch (e) { /* ignore */ }
	        try { group.noScaleCache = true; } catch (e) { /* ignore */ }
	        return group;
	      };
	      if (kind === 'shape_lane_3') return (left, top) => buildLaneShape(left, top, 3);
	      if (kind === 'shape_lane_4') return (left, top) => buildLaneShape(left, top, 4);

	      if (kind === 'line_curve') {
	        return (left, top) => new fabric.Path('M -70 22 Q 0 -34 70 22', {
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          stroke: '#f8fafc',
	          fill: '',
	          strokeWidth: 4,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          data: { kind: 'line-curve' },
	        });
	      }
	      if (kind === 'line_wave') {
	        return (left, top) => new fabric.Path('M -72 0 C -56 -22 -38 22 -22 0 S 12 -22 28 0 S 62 22 72 0', {
	          left,
	          top,
	          originX: 'center',
	          originY: 'center',
	          stroke: '#f8fafc',
	          fill: '',
	          strokeWidth: 4,
	          strokeLineCap: 'round',
	          strokeLineJoin: 'round',
	          data: { kind: 'line-wave' },
	        });
	      }
	      if (kind === 'text') {
	        return (left, top) => new fabric.IText('Texto', {
	          left, top, originX: 'center', originY: 'center',
	          fontSize: 22, fill: '#ffffff', fontWeight: '700', data: { kind: 'text', color: '#ffffff' },
	        });
	      }
      if (EMOJI_LIBRARY[kind]) {
        return (left, top) => new fabric.Text(EMOJI_LIBRARY[kind], {
          left,
          top,
          originX: 'center',
          originY: 'center',
          fontSize: 30,
          shadow: 'rgba(15,23,42,0.62) 0 1px 2px',
          fontFamily: 'Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, system-ui, sans-serif',
          data: { kind, color: '#0f172a' },
        });
      }
      return null;
    };

		    const activateFactory = (factory, label, kind = '') => {
		      if (isSimulating) {
		        clearPendingPlacement();
		        setStatus('Modo simulación: no se pueden añadir recursos. Sal del simulador para editar.', true);
		        return;
		      }
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
	      const sourceWidth = Number.parseInt(String(widthInput?.value || ''), 10) || 0;
	      const sourceHeight = Number.parseInt(String(heightInput?.value || ''), 10) || 0;
	      applySerializedState(parsed, { pushHistory: true, sourceWidth, sourceHeight });
	      schedulePlayerBankUpdate();
		    };

		    const isGoalkeeperPlayer = (player) => {
		      const pos = safeText(player?.position, '').toLowerCase();
		      if (!pos) return false;
		      return pos.includes('portero') || pos === 'gk' || pos.includes('goalkeeper');
		    };

		    // Plantilla: ocultar jugadores ya usados (para no duplicar chapas).
		    const collectPlayerIdsFromFabricObjects = (objects, outSet) => {
		      const list = Array.isArray(objects) ? objects : [];
		      list.forEach((obj) => {
		        if (!obj) return;
		        const kind = safeText(obj?.data?.kind);
		        if (kind === 'token') {
		          const pid = Number.parseInt(String(obj?.data?.playerId || ''), 10);
		          if (Number.isFinite(pid) && pid > 0) outSet.add(String(pid));
		        }
		        // Nota: no es necesario bajar a hijos del group; el `playerId` vive en el group.
		      });
		    };
		    const collectPlayerIdsFromCanvasState = (canvasState, outSet) => {
		      if (!canvasState || typeof canvasState !== 'object') return;
		      const objects = Array.isArray(canvasState.objects) ? canvasState.objects : [];
		      objects.forEach((obj) => {
		        if (safeText(obj?.data?.kind) !== 'token') return;
		        const pid = Number.parseInt(String(obj?.data?.playerId || ''), 10);
		        if (Number.isFinite(pid) && pid > 0) outSet.add(String(pid));
		      });
		    };
		    const computeUsedPlayerIds = () => {
		      const used = new Set();
		      // Preferimos leer del canvas en vivo: es más fiable que la serialización y
		      // reacciona instantáneamente a "añadir/quitar" chapas.
		      try { collectPlayerIdsFromFabricObjects(canvas.getObjects?.() || [], used); } catch (error) { /* ignore */ }
		      // Compatibilidad: además, incorporamos lo que esté en las escenas/timeline para no permitir duplicados entre pasos.
		      try {
		        try { persistActiveStepSnapshot(); } catch (error) { /* ignore */ }
		        try { collectPlayerIdsFromCanvasState(serializeCanvasOnly(), used); } catch (error) { /* ignore */ }
		        (Array.isArray(timeline) ? timeline : []).forEach((step) => collectPlayerIdsFromCanvasState(step?.canvas_state, used));
		      } catch (error) { /* ignore */ }
		      return used;
		    };
		    const HIDE_USED_KEY = 'webstats:tpad:hide_used_players';
		    const readHideUsedPref = () => {
		      try {
		        const raw = safeText(window.localStorage?.getItem(HIDE_USED_KEY));
		        if (raw === '0') return false;
		        if (raw === '1') return true;
		      } catch (error) { /* ignore */ }
		      return true;
		    };
		    let hideUsedPlayersEnabled = readHideUsedPref();
		    if (hideUsedPlayersToggle) {
		      hideUsedPlayersToggle.checked = hideUsedPlayersEnabled;
		      hideUsedPlayersToggle.addEventListener('change', () => {
		        hideUsedPlayersEnabled = !!hideUsedPlayersToggle.checked;
		        try { window.localStorage?.setItem(HIDE_USED_KEY, hideUsedPlayersEnabled ? '1' : '0'); } catch (error) { /* ignore */ }
		        schedulePlayerBankUpdate();
		      });
		    }
		    let playerBankUpdateTimer = null;
		    const updatePlayerBankVisibility = () => {
		      if (!playerBank) return;
		      const used = hideUsedPlayersEnabled ? computeUsedPlayerIds() : new Set();
		      Array.from(playerBank.querySelectorAll('button.player-token-bank')).forEach((btn) => {
		        const pid = safeText(btn.dataset.playerId);
		        btn.hidden = !!(hideUsedPlayersEnabled && pid && used.has(pid));
		      });
		    };
		    const schedulePlayerBankUpdate = () => {
		      window.clearTimeout(playerBankUpdateTimer);
		      playerBankUpdateTimer = window.setTimeout(updatePlayerBankVisibility, 120);
		    };

		    const renderPlayerBank = () => {
		      if (!playerBank) return;
		      playerBank.innerHTML = '';
		      const roster = (Array.isArray(players) ? players.slice() : []);
		      roster.sort((a, b) => {
		        const na = Number.parseInt(String(a?.number || ''), 10);
		        const nb = Number.parseInt(String(b?.number || ''), 10);
		        if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
		        if (Number.isFinite(na)) return -1;
		        if (Number.isFinite(nb)) return 1;
		        return safeText(a?.name).localeCompare(safeText(b?.name));
		      });
		      roster.forEach((player) => {
		        const kind = isGoalkeeperPlayer(player) ? 'goalkeeper_local' : 'player_local';
		        const button = document.createElement('button');
		        button.type = 'button';
		        button.className = 'player-token-bank';
		        button.dataset.playerId = String(player.id || '');
		        const name = document.createElement('span');
		        name.className = 'token-name';
		        name.textContent = shortPlayerName(player.name);
	        const disk = document.createElement('span');
	        disk.className = 'token-disk';
	        if (kind === 'goalkeeper_local') disk.classList.add('is-goalkeeper');
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
		      schedulePlayerBankUpdate();
		    };
	    const selectTimelineStep = (index) => {
	      if (index < 0 || index >= timeline.length) return;
	      if (playbackTimer) return;
	      persistActiveStepSnapshot();
	      activeStepIndex = index;
	      loadCanvasSnapshot(timeline[index].canvas_state, () => {
	        renderTimeline();
	        setStatus(`Editando ${timeline[index].title}.`);
	        schedulePlayerBankUpdate();
	      }, { sourceWidth: parseIntSafe(timeline[index].canvas_width), sourceHeight: parseIntSafe(timeline[index].canvas_height) });
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
	        canvas_width: Math.round(worldSize().w || 0),
	        canvas_height: Math.round(worldSize().h || 0),
	      });
      activeStepIndex = insertionIndex;
	      renderTimeline();
	      pushHistory();
	      setStatus(duplicateCurrent ? 'Paso duplicado.' : 'Paso añadido.');
	      schedulePlayerBankUpdate();
	    };
	    const removeTimelineStep = () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline.splice(activeStepIndex, 1);
	      if (!timeline.length) {
	        activeStepIndex = -1;
	        renderTimeline();
	        pushHistory();
	        setStatus('Paso eliminado.');
	        schedulePlayerBankUpdate();
	        return;
	      }
      activeStepIndex = clamp(activeStepIndex, 0, timeline.length - 1);
	      loadCanvasSnapshot(timeline[activeStepIndex].canvas_state, () => {
	        renderTimeline();
	        pushHistory();
	        setStatus('Paso eliminado.');
	        schedulePlayerBankUpdate();
	      }, { sourceWidth: parseIntSafe(timeline[activeStepIndex].canvas_width), sourceHeight: parseIntSafe(timeline[activeStepIndex].canvas_height) });
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
        }, { sourceWidth: parseIntSafe(timeline[playIndex].canvas_width), sourceHeight: parseIntSafe(timeline[playIndex].canvas_height) });
      };
      runNext();
    };

				    const buildPreviewData = (options = {}) => new Promise((resolve) => {
			      const sourceWidth = Math.round(canvas.getWidth());
			      const sourceHeight = Math.round(canvas.getHeight());
			      // En iPad conviene limitar el tamaño para que no bloquee el hilo principal.
			      const maxPreviewWidth = clamp(Number(options.maxWidth) || 720, 480, 4096);
			      // Para PDF necesitamos HD real: si el lienzo en pantalla mide 1200-1800px, queremos
			      // generar una imagen de 3200-4096px (ratio > 1). Con Fabric, usamos `multiplier`
			      // para renderizar nítido (no un simple upscale).
			      const ratio = clamp((maxPreviewWidth / Math.max(1, sourceWidth)), 0.25, 4);
			      const mime = safeText(options.mime, 'image/png').toLowerCase();
			      const quality = clamp(Number(options.quality) || 0.92, 0.5, 0.98);
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

	      // Renderiza la capa Fabric en alta resolución (sin perder nitidez).
	      let overlayUrl = '';
	      try {
	        // Siempre generamos la capa como PNG para conservar transparencia (si la hacemos JPEG,
	        // la pizarra pierde alpha y tapa el césped al componer).
	        const format = 'png';
	        overlayUrl = canvas.toDataURL({
	          format,
	          quality,
	          multiplier: ratio,
	          enableRetinaScaling: false,
	        });
	      } catch (error) {
	        overlayUrl = '';
	      }

		      // Clona el SVG y fija width/height al tamaño final de exportación.
		      // Importante: en el editor, el SVG en vertical usa `slice` para evitar “barras”, pero en exportación
		      // necesitamos `meet` para NO recortar el campo. Luego recortamos de forma controlada con data-pitch-box.
		      let svgMarkup = '';
		      let exportPreserveAspectRatio = safeText(svgSurface.getAttribute('preserveAspectRatio'));
		      try {
		        const clone = svgSurface.cloneNode(true);
		        // En exportación, evita recortes por `slice` (vertical) y deja que el recorte lo haga data-pitch-box.
		        clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');
		        exportPreserveAspectRatio = safeText(clone.getAttribute('preserveAspectRatio')) || exportPreserveAspectRatio;
		        const viewBoxRaw = safeText(clone.getAttribute('viewBox'));
		        const vbParts = viewBoxRaw.split(/\s+/).map((v) => Number(v)).filter((n) => Number.isFinite(n));
		        if (vbParts.length >= 4) {
		          const vbW = vbParts[2];
		          const vbH = vbParts[3];
		          if (vbW > 0 && vbH > 0) {
		            // Importantísimo: el editor puede tener un canvas "apaisado" incluso en orientación vertical.
		            // Si forzamos `preserveAspectRatio="none"` + escalado no uniforme, el recorte por pitchBox
		            // acaba convirtiendo el campo vertical en una imagen horizontal (y el PDF lo recorta).
		            // Exportamos el SVG al mismo tamaño final, manteniendo su preserveAspectRatio original.
		            clone.setAttribute('width', String(Math.round(output.width)));
		            clone.setAttribute('height', String(Math.round(output.height)));
		          }
		        }
		        svgMarkup = new XMLSerializer().serializeToString(clone);
		      } catch (error) {
		        svgMarkup = new XMLSerializer().serializeToString(svgSurface);
		      }
		      const blob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' });
		      const blobUrl = URL.createObjectURL(blob);
		      const pitchImage = new Image();
		      const overlayImage = new Image();
		      let pitchLoaded = false;
		      let overlayLoaded = false;
		      let overlayFailed = false;
			      const finish = () => {
			        if (!pitchLoaded) return;
			        if (overlayUrl && !overlayLoaded && !overlayFailed) return;
			        if (pitchImage && pitchImage.complete) {
			          try { context.drawImage(pitchImage, 0, 0, output.width, output.height); } catch (error) { /* ignore */ }
			        }
			        if (overlayUrl && overlayLoaded && overlayImage && overlayImage.complete) {
			          try { context.drawImage(overlayImage, 0, 0, output.width, output.height); } catch (error) { /* ignore */ }
			        } else {
			          // Fallback: si no pudimos generar HD con Fabric, usamos el canvas visible.
			          try { context.drawImage(canvas.lowerCanvasEl, 0, 0, output.width, output.height); } catch (error) { /* ignore */ }
			        }
			        URL.revokeObjectURL(blobUrl);
			        // Calcula bounding box del overlay (alpha>0) para evitar recortes agresivos.
			        // Esto cubre casos donde hay elementos colocados fuera del rectángulo de juego
			        // (p.ej. chapas/porterías auxiliares), y no queremos que el preview/PDF los corte.
			        const overlayBounds = (() => {
			          if (!overlayUrl || !overlayLoaded || !overlayImage || !overlayImage.complete) return null;
			          try {
			            const sampleW = clamp(Math.round(output.width / 8), 240, 640);
			            const sampleH = Math.max(1, Math.round(output.height * (sampleW / Math.max(1, output.width))));
			            const sample = document.createElement('canvas');
			            sample.width = sampleW;
			            sample.height = sampleH;
			            const sctx = sample.getContext('2d', { willReadFrequently: true });
			            if (!sctx) return null;
			            sctx.clearRect(0, 0, sampleW, sampleH);
			            sctx.drawImage(overlayImage, 0, 0, sampleW, sampleH);
			            const data = sctx.getImageData(0, 0, sampleW, sampleH).data;
			            let minX = sampleW;
			            let minY = sampleH;
			            let maxX = -1;
			            let maxY = -1;
			            for (let y = 0; y < sampleH; y += 1) {
			              const row = y * sampleW * 4;
			              for (let x = 0; x < sampleW; x += 1) {
			                const a = data[row + (x * 4) + 3];
			                if (a > 10) {
			                  if (x < minX) minX = x;
			                  if (y < minY) minY = y;
			                  if (x > maxX) maxX = x;
			                  if (y > maxY) maxY = y;
			                }
			              }
			            }
			            if (maxX < 0 || maxY < 0) return null;
			            const scaleX = output.width / sampleW;
			            const scaleY = output.height / sampleH;
			            return {
			              x: minX * scaleX,
			              y: minY * scaleY,
			              w: (maxX - minX + 1) * scaleX,
			              h: (maxY - minY + 1) * scaleY,
			            };
			          } catch (error) {
			            return null;
			          }
			        })();
				        // Recorta a la caja real del rectángulo de juego (evita grandes márgenes vacíos
				        // en superficies parciales que luego hacen que en el PDF el campo salga "pequeñísimo").
				        try {
				          const pitchBoxRaw = safeText(svgSurface.getAttribute('data-pitch-box'));
				          const viewBoxRaw = safeText(svgSurface.getAttribute('viewBox'));
			          const boxParts = pitchBoxRaw.split(/\s+/).map((v) => Number(v)).filter((n) => Number.isFinite(n));
			          const vbParts = viewBoxRaw.split(/\s+/).map((v) => Number(v)).filter((n) => Number.isFinite(n));
			          if (boxParts.length >= 4 && vbParts.length >= 4) {
			            const [boxX, boxY, boxW, boxH] = boxParts;
			            const [vbX, vbY, vbW, vbH] = vbParts;
			            if (vbW > 0 && vbH > 0 && boxW > 0 && boxH > 0) {
				              const preserveRaw = exportPreserveAspectRatio || safeText(svgSurface.getAttribute('preserveAspectRatio'));
				              const isNone = /\bnone\b/i.test(preserveRaw);
				              const isSlice = /\bslice\b/i.test(preserveRaw);
				              const outW = Math.max(1, Number(output.width || 1));
				              const outH = Math.max(1, Number(output.height || 1));

				              // Mapea pitchBox (coordenadas viewBox) a píxeles de la imagen exportada.
				              // Si el SVG usa meet/slice, el escalado es UNIFORME + offsets (xMidYMid).
				              // Si fuese none (no debería), caemos a escalado no uniforme por compat.
				              let baseX = 0;
				              let baseY = 0;
				              let baseW = 0;
				              let baseH = 0;
				              if (isNone) {
				                const scaleX = outW / vbW;
				                const scaleY = outH / vbH;
				                baseX = (boxX - vbX) * scaleX;
				                baseY = (boxY - vbY) * scaleY;
				                baseW = boxW * scaleX;
				                baseH = boxH * scaleY;
				              } else {
				                const scale = (isSlice ? Math.max(outW / vbW, outH / vbH) : Math.min(outW / vbW, outH / vbH));
				                const offsetX = (outW - (vbW * scale)) / 2;
				                const offsetY = (outH - (vbH * scale)) / 2;
				                baseX = offsetX + ((boxX - vbX) * scale);
				                baseY = offsetY + ((boxY - vbY) * scale);
				                baseW = boxW * scale;
				                baseH = boxH * scale;
				              }

				              // Recorte base = rectángulo real del campo.
				              let uX = baseX;
				              let uY = baseY;
				              let uW = baseW;
				              let uH = baseH;

				              // Permitimos algo de “overflow” fuera del campo para no cortar etiquetas/flechas,
				              // pero lo capamos para que no salga un “mar verde” que empequeñece la tarea.
				              const maxExtra = Math.max(18, Math.round(Math.min(baseW, baseH) * 0.12));

				              // Unión con overlayBounds (para no cortar elementos colocados ligeramente fuera del campo).
				              if (overlayBounds && overlayBounds.w > 6 && overlayBounds.h > 6) {
				                const extraPad = Math.max(10, Math.round(Math.min(baseW, baseH) * 0.03));
				                const minUx = Math.min(uX, overlayBounds.x - extraPad);
				                const minUy = Math.min(uY, overlayBounds.y - extraPad);
				                const maxUx = Math.max(uX + uW, overlayBounds.x + overlayBounds.w + extraPad);
				                const maxUy = Math.max(uY + uH, overlayBounds.y + overlayBounds.h + extraPad);
				                uX = minUx;
				                uY = minUy;
				                uW = maxUx - minUx;
				                uH = maxUy - minUy;
				              }

				              const allowedMinX = Math.max(0, Math.floor(baseX - maxExtra));
				              const allowedMinY = Math.max(0, Math.floor(baseY - maxExtra));
				              const allowedMaxX = Math.min(output.width, Math.ceil(baseX + baseW + maxExtra));
				              const allowedMaxY = Math.min(output.height, Math.ceil(baseY + baseH + maxExtra));

				              // Normaliza unión dentro de los límites permitidos.
				              uX = clamp(uX, allowedMinX, Math.max(allowedMinX, allowedMaxX - 120));
				              uY = clamp(uY, allowedMinY, Math.max(allowedMinY, allowedMaxY - 80));
				              uW = clamp(uW, 120, Math.max(120, allowedMaxX - uX));
				              uH = clamp(uH, 80, Math.max(80, allowedMaxY - uY));

				              // Padding final controlado.
				              let pad = Math.max(10, Math.round(Math.min(baseW, baseH) * 0.035));
				              pad = Math.min(pad, Math.round(maxExtra * 0.6));

				              let cropX = Math.max(0, Math.floor(uX - pad));
				              let cropY = Math.max(0, Math.floor(uY - pad));
				              let cropW = Math.min(output.width - cropX, Math.ceil(uW + pad * 2));
				              let cropH = Math.min(output.height - cropY, Math.ceil(uH + pad * 2));

				              // Clamp final dentro de los límites permitidos.
				              cropX = clamp(cropX, allowedMinX, Math.max(allowedMinX, allowedMaxX - 120));
				              cropY = clamp(cropY, allowedMinY, Math.max(allowedMinY, allowedMaxY - 80));
				              cropW = clamp(cropW, 120, Math.max(120, allowedMaxX - cropX));
				              cropH = clamp(cropH, 80, Math.max(80, allowedMaxY - cropY));
				              if (cropW > 120 && cropH > 80 && cropW < output.width && cropH < output.height) {
				                const cropped = document.createElement('canvas');
				                cropped.width = Math.round(cropW);
				                cropped.height = Math.round(cropH);
			                const cctx = cropped.getContext('2d');
		                if (cctx) {
		                  cctx.fillStyle = '#ffffff';
		                  cctx.fillRect(0, 0, cropped.width, cropped.height);
		                  cctx.drawImage(output, -cropX, -cropY);
		                  try {
		                    resolve(cropped.toDataURL(mime === 'image/jpeg' ? 'image/jpeg' : 'image/png', quality));
		                    return;
		                  } catch (error) {
		                    resolve(cropped.toDataURL('image/png', 0.92));
		                    return;
		                  }
		                }
		              }
		            }
		          }
			        } catch (error) { /* ignore */ }
			        try {
			          resolve(output.toDataURL(mime === 'image/jpeg' ? 'image/jpeg' : 'image/png', quality));
			        } catch (error) {
			          resolve(output.toDataURL('image/png', 0.92));
			        }
		      };
		      pitchImage.onload = () => { pitchLoaded = true; finish(); };
		      pitchImage.onerror = () => { pitchLoaded = true; finish(); };
		      if (overlayUrl) {
		        overlayImage.onload = () => { overlayLoaded = true; finish(); };
		        overlayImage.onerror = () => { overlayFailed = true; finish(); };
		        overlayImage.src = overlayUrl;
		      } else {
		        overlayFailed = true;
		      }
		      pitchImage.src = blobUrl;
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
		      // Importante (rendimiento): `canvas.toDataURL()` puede ser costoso, sobre todo si
		      // hay imágenes grandes en la pizarra. Lo movemos a "tiempo ocioso" para que no
		      // meta tirones mientras el usuario sigue editando.
		      previewRefreshTimer = window.setTimeout(() => {
		        runWhenIdle(async () => {
		          if (previewBuildInFlight) return;
		          previewBuildInFlight = true;
		          try {
		            const dataUrl = await buildPreviewData();
		            if (previewInput) previewInput.value = dataUrl;
		            applyLivePreview(dataUrl);
		          } finally {
		            previewBuildInFlight = false;
		          }
		        }, 1800);
		      }, 950);
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
		    const syncHiddenBuilderFields = async (options = {}) => {
		      try { syncRichEditorsNow(); } catch (error) { /* ignore */ }
		      if (legacyPlayersInput && playerCountInput) legacyPlayersInput.value = playerCountInput.value || '';
		      if (useViewportMapping) syncWorldFromInputs();
		      const stateObj = serializeState();
		      syncAssignedPlayersHidden(stateObj);
		      if (stateInput) stateInput.value = JSON.stringify(stateObj);
		      if (widthInput || heightInput) {
		        if (!useViewportMapping) {
		          worldWidth = Math.round(canvas.getWidth() || 0);
		          worldHeight = Math.round(canvas.getHeight() || 0);
		        }
		        const { w, h } = worldSize();
		        if (widthInput) widthInput.value = String(Math.round(w || 0));
		        if (heightInput) heightInput.value = String(Math.round(h || 0));
		      }
		      const previewOptions = options && typeof options === 'object' ? (options.previewOptions || {}) : {};
		      const applyLive = !(options && typeof options === 'object' && options.applyLivePreview === false);
		      const dataUrl = await buildPreviewData(previewOptions);
	      if (previewInput) previewInput.value = dataUrl;
	      if (applyLive) applyLivePreview(dataUrl);
	      if (timelinePreviewsInput) timelinePreviewsInput.value = '';
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

			      await syncHiddenBuilderFields({
			        // PNG para mantener líneas nítidas y sin artefactos JPEG en el PDF.
			        previewOptions: { maxWidth: 4096, mime: 'image/png', quality: 0.98 },
			        applyLivePreview: false,
			      });
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
		    applyStageSizeUi({ noFit: true });
		    fitCanvas();
		    initPitchResizer();
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
	      // Asegura que los campos hidden de texto enriquecido estén sincronizados antes de serializar.
	      try { syncRichEditorsNow?.(); } catch (error) { /* ignore */ }
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
	        if (!useViewportMapping) {
	          worldWidth = Math.round(canvas.getWidth() || 0);
	          worldHeight = Math.round(canvas.getHeight() || 0);
	        }
	        const { w, h } = worldSize();
	        fields.draw_canvas_width = String(Math.round(w || 0));
	        fields.draw_canvas_height = String(Math.round(h || 0));
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
	      if (!canUseStorage || !draftKey || saveSuccess || isSimulating) return;
	      window.clearTimeout(draftSaveTimer);
	      draftSaveTimer = window.setTimeout(() => persistDraftNow(reason || 'auto'), 900);
	    };

    if (canUseStorage && draftKey && !saveSuccess) {
      form.addEventListener('input', () => scheduleDraftSave('input'));
      form.addEventListener('change', () => scheduleDraftSave('change'));
    }

    const initTaskModeTabs = () => {
      const tabs = document.getElementById('task-mode-tabs');
      if (!tabs) return;
      const buttons = Array.from(tabs.querySelectorAll('button[data-task-mode]'));
      if (!buttons.length) return;
      const storageKey = 'tpad_task_mode_v1';
      const isNarrow = () => {
        try { return window.matchMedia('(max-width: 1160px)').matches; } catch (error) { return true; }
      };
      const readMode = () => {
        try {
          const stored = safeText(window.localStorage.getItem(storageKey));
          if (stored === 'text' || stored === 'board') return stored;
        } catch (error) { /* ignore */ }
        return 'board';
      };
      const writeMode = (mode) => {
        try { window.localStorage.setItem(storageKey, mode); } catch (error) { /* ignore */ }
      };
      const apply = (mode, options = {}) => {
        const next = mode === 'text' ? 'text' : 'board';
        document.body.classList.toggle('task-mode-board', next === 'board');
        document.body.classList.toggle('task-mode-text', next === 'text');
        document.body.classList.toggle('task-mode-both', false);
        document.body.classList.toggle('task-mode-ready', true);
        buttons.forEach((btn) => {
          const active = safeText(btn.dataset.taskMode) === next;
          btn.classList.toggle('is-active', active);
          btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        if (!options.silent) writeMode(next);
        if (next === 'text') {
          try { syncRichEditorsNow?.(); } catch (error) { /* ignore */ }
          try { persistDraftNow('mode-switch'); } catch (error) { /* ignore */ }
          if (!options.silent) setStatus('Vista: Contenido.');
          return;
        }
        window.setTimeout(() => {
          try { fitCanvas(); } catch (error) { /* ignore */ }
          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
          try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
        }, 50);
        if (!options.silent) setStatus('Vista: Pizarra.');
      };

      // Importante: solo después de inicializar el canvas para evitar tamaños 0.
      apply(readMode(), { silent: true });

      buttons.forEach((btn) => {
        btn.addEventListener('click', () => {
          const mode = safeText(btn.dataset.taskMode);
          apply(mode);
        });
      });

      window.addEventListener('resize', () => {
        apply(readMode(), { silent: true });
      }, { passive: true });
    };
    initTaskModeTabs();

    let pingKeepalive = null;
    if (keepaliveUrl) {
      pingKeepalive = async () => {
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
        pingKeepalive?.();
      }, 25_000);
      const keepaliveTimer = window.setInterval(async () => {
        const ok = await pingKeepalive?.();
        if (!ok) window.clearInterval(keepaliveTimer);
      }, 240_000);
    }

    // El submit real se gestiona al final del fichero (unificado con el sync de campos ocultos + preview HD).
    // Aquí solo mantenemos pingKeepalive para reutilizarlo en ese handler.

		    canvas.on('object:modified', () => {
		      if (canvas.__loading) return;
		      persistActiveStepSnapshot();
		      pushHistory();
		      syncInspector();
		      renderLayers();
		      refreshLivePreview();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		    });
		    canvas.on('object:added', () => {
		      if (!canvas.__loading) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		      }
		      refreshLivePreview();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		    });
		    canvas.on('object:removed', () => {
		      if (!canvas.__loading) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		      }
		      refreshLivePreview();
		      schedulePlayerBankUpdate();
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
    const autoDisableBackgroundEdits = () => {
      const active = canvas.getActiveObject();
      const keep = (active && isBackgroundShape(active) && active?.data?.background_edit) ? active : null;
      const changed = disableBackgroundEditExcept(keep);
      if (!changed) return;
      try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
      syncInspector();
      renderLayers();
    };
    canvas.on('selection:created', autoDisableBackgroundEdits);
    canvas.on('selection:updated', autoDisableBackgroundEdits);
    canvas.on('selection:cleared', autoDisableBackgroundEdits);
			    canvas.on('mouse:down', (event) => {
			      if (!pendingFactory) return;
			      // Permitir colocar encima de figuras de fondo (zonas/figuras/porterías) sin que
			      // el fondo intercepte el click. Si el fondo está en background_edit, sí bloquea.
			      const target = event?.target;
			      if (target) {
			        const isBg = isBackgroundShape(target) && !target?.data?.background_edit;
			        if (!isBg) return;
			      }
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
      const e = event?.e;
      if (backgroundPickMode && e && !pendingFactory) {
        const candidate = pickBackgroundFromEvent(e);
        backgroundPickMode = false;
        if (candidate) {
          setBackgroundEditMode(candidate, true, { force: true });
          canvas.setActiveObject(candidate);
          canvas.requestRenderAll();
          syncInspector();
          renderLayers();
          setStatus('Figura en modo edición. Pulsa Esc o selecciona otro elemento para salir.');
        } else {
          setStatus('No se encontró una figura en ese punto.', true);
        }
        return;
      }
      if (e && e.altKey && !pendingFactory) {
        try {
          const candidate = pickBackgroundFromEvent(e);
          if (candidate) {
            setBackgroundEditMode(candidate, true, { force: true });
            canvas.setActiveObject(candidate);
            canvas.requestRenderAll();
            syncInspector();
            renderLayers();
            setStatus('Figura en modo edición (Alt). Pulsa Esc o selecciona otro elemento para salir.');
            return;
          }
        } catch (error) {
          // ignore
        }
      }
      const target = event.target;
      if (!target || !isBackgroundShape(target) || !event.e || event.e.shiftKey) return;
      if (target?.data?.background_edit) return;
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

    [timelineList, timelineListPopover].filter(Boolean).forEach((listEl) => {
      listEl.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-step-index]');
        if (!button) return;
        selectTimelineStep(Number(button.dataset.stepIndex));
      });
    });
    addStepButton?.addEventListener('click', () => addTimelineStep(false));
    duplicateStepButton?.addEventListener('click', () => addTimelineStep(true));
    removeStepButton?.addEventListener('click', removeTimelineStep);
    playStepButton?.addEventListener('click', playTimeline);
    scenarioAddBtn?.addEventListener('click', () => addTimelineStep(false));
    scenarioDuplicateBtn?.addEventListener('click', () => addTimelineStep(true));
    scenarioRemoveBtn?.addEventListener('click', removeTimelineStep);
    stepTitleInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(stepTitleInput.value, `Paso ${activeStepIndex + 1}`);
      if (scenarioTitleInput) scenarioTitleInput.value = timeline[activeStepIndex].title || '';
      renderTimeline();
    });
    stepTitleInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(stepTitleInput.value, `Paso ${activeStepIndex + 1}`);
      pushHistory();
    });
    scenarioTitleInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(scenarioTitleInput.value, `Escenario ${activeStepIndex + 1}`);
      if (stepTitleInput) stepTitleInput.value = timeline[activeStepIndex].title || '';
      renderTimeline();
    });
    scenarioTitleInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].title = safeText(scenarioTitleInput.value, `Escenario ${activeStepIndex + 1}`);
      if (stepTitleInput) stepTitleInput.value = timeline[activeStepIndex].title || '';
      pushHistory();
    });
    stepDurationInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(stepDurationInput.value) || 3, 1, 20);
      if (scenarioDurationInput) scenarioDurationInput.value = String(timeline[activeStepIndex].duration || 3);
      renderTimeline();
    });
    stepDurationInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(stepDurationInput.value) || 3, 1, 20);
      pushHistory();
    });
    scenarioDurationInput?.addEventListener('input', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(scenarioDurationInput.value) || 3, 1, 20);
      if (stepDurationInput) stepDurationInput.value = String(timeline[activeStepIndex].duration || 3);
      renderTimeline();
    });
    scenarioDurationInput?.addEventListener('change', () => {
      if (activeStepIndex < 0 || !timeline[activeStepIndex]) return;
      timeline[activeStepIndex].duration = clamp(Number(scenarioDurationInput.value) || 3, 1, 20);
      if (stepDurationInput) stepDurationInput.value = String(timeline[activeStepIndex].duration || 3);
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
		      const tokenSize = safeText(button.dataset.tokenSize);
		      if (tokenSize) {
		        applyToActiveFlexibleObject((active) => {
		          if (!isTokenGroup(active)) return;
		          setTokenStandardSize(active, tokenSize);
		        }, `Chapa: ${tokenSize.toUpperCase()}.`);
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
	          const { w, h } = worldSize();
	          active.left = clamp((Number(active.left) || 0) + (Number.isNaN(nudgeX) ? 0 : nudgeX), 12, w - 12);
	          active.top = clamp((Number(active.top) || 0) + (Number.isNaN(nudgeY) ? 0 : nudgeY), 12, h - 12);
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
	        if (!active) {
	          setStatus('No hay elemento seleccionado para borrar.', true);
	          return false;
	        }
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
      if (action === 'edit_bg') {
        const active = canvas.getActiveObject();
        if (active && isBackgroundShape(active)) {
          const next = !(active?.data?.background_edit);
          setBackgroundEditMode(active, next, { force: true });
          if (!next) canvas.discardActiveObject();
          canvas.requestRenderAll();
          pushHistory();
          syncInspector();
          renderLayers();
          backgroundPickMode = false;
          setStatus(next ? 'Figura: modo edición activado.' : 'Figura: modo edición desactivado.');
          return true;
        }
        backgroundPickMode = !backgroundPickMode;
        if (backgroundPickMode) {
          clearPendingPlacement();
          pendingFactory = null;
          setStatus('Toca una figura/zona/portería para editarla (o pulsa de nuevo para cancelar).');
        } else {
          setStatus('Modo edición de figuras cancelado.');
        }
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
		      if (add.startsWith('pdf_asset:')) {
		        const assetId = add.split(':')[1] || '';
		        const meta = pdfAssetMeta.get(normalizePdfAssetId(assetId));
		        const label = meta?.title ? `el recurso PDF “${safeText(meta.title)}”` : 'un recurso PDF';
		        Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
		        button.classList.add('is-active');
		        activateFactory((left, top) => buildPdfAssetObject(assetId, left, top), label, add);
		        return;
		      }
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
		      if (add.startsWith('pdf_asset:')) {
		        const assetId = add.split(':')[1] || '';
		        const meta = pdfAssetMeta.get(normalizePdfAssetId(assetId));
		        const label = meta?.title ? `el recurso PDF “${safeText(meta.title)}”` : 'un recurso PDF';
		        Array.from(libraryPane.querySelectorAll('button[data-add]')).forEach((item) => item.classList.remove('is-active'));
		        button.classList.add('is-active');
		        activateFactory((left, top) => buildPdfAssetObject(assetId, left, top), label, add);
		        return;
		      }
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
					      if (key === 'escape') {
					        if (!commandMenu?.hidden) {
					          setCommandMenuOpen(false);
					          event.preventDefault();
					          return;
					        }
					        const active = canvas.getActiveObject();
					        if (active && isBackgroundShape(active) && active?.data?.background_edit) {
					          setBackgroundEditMode(active, false, { force: true });
					          syncInspector();
					          renderLayers();
					          setStatus('Fondo: modo edición desactivado.');
					          event.preventDefault();
					          return;
					        }
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
		      // Solo tiene sentido si el viewport puede desplazarse o si hay zoom/pan por viewportTransform.
		      const canPan = (() => {
		        if (useViewportMapping) {
		          const { w: fromW, h: fromH } = worldSize();
		          const toW = Math.round(canvas.getWidth() || 0);
		          const toH = Math.round(canvas.getHeight() || 0);
		          if (fromW <= 0 || fromH <= 0 || toW <= 0 || toH <= 0) return false;
		          const baseScale = Math.min(toW / fromW, toH / fromH);
		          const scale = baseScale * clamp(Number(pitchZoom) || 1, 0.8, 1.6);
		          return (fromW * scale) > (toW + 2) || (fromH * scale) > (toH + 2);
		        }
		        return viewportEl.scrollWidth > viewportEl.clientWidth || viewportEl.scrollHeight > viewportEl.clientHeight;
		      })();
		      if (!canPan) return;
		      spacePanning = true;
		      spacePanStart = {
		        x: Number(event.clientX) || 0,
		        y: Number(event.clientY) || 0,
		        scrollLeft: viewportEl.scrollLeft,
		        scrollTop: viewportEl.scrollTop,
		        panX: viewportPanX,
		        panY: viewportPanY,
		      };
		      viewportEl.classList.add('is-grabbing');
		      event.preventDefault();
		      event.stopPropagation();
		    };
		    const moveSpacePan = (event) => {
		      if (!viewportEl || !spacePanning || !spacePanStart) return;
		      const dx = (Number(event.clientX) || 0) - spacePanStart.x;
		      const dy = (Number(event.clientY) || 0) - spacePanStart.y;
		      if (useViewportMapping) {
		        viewportPanX = (Number(spacePanStart.panX) || 0) + dx;
		        viewportPanY = (Number(spacePanStart.panY) || 0) + dy;
		        try { applyViewportTransformToWorld(); } catch (error) { /* ignore */ }
		        try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
		      } else {
		        viewportEl.scrollLeft = spacePanStart.scrollLeft - dx;
		        viewportEl.scrollTop = spacePanStart.scrollTop - dy;
		      }
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

			    // Touch: pan con 2 dedos cuando el viewport es scrollable (zoom/orientación vertical),
			    // sin romper el drag normal (1 dedo) para mover fichas.
				    let touchPanActive = false;
				    let touchPanStart = null;
				    const canViewportScroll = () => {
				      if (!viewportEl) return false;
				      if (useViewportMapping) {
				        const { w: fromW, h: fromH } = worldSize();
				        const toW = Math.round(canvas.getWidth() || 0);
				        const toH = Math.round(canvas.getHeight() || 0);
				        if (fromW <= 0 || fromH <= 0 || toW <= 0 || toH <= 0) return false;
				        const baseScale = Math.min(toW / fromW, toH / fromH);
				        const scale = baseScale * clamp(Number(pitchZoom) || 1, 0.8, 1.6);
				        return (fromW * scale) > (toW + 2) || (fromH * scale) > (toH + 2);
				      }
				      return viewportEl.scrollWidth > viewportEl.clientWidth || viewportEl.scrollHeight > viewportEl.clientHeight;
				    };
			    const touchCenter = (touches) => {
			      const t0 = touches?.[0];
			      const t1 = touches?.[1];
			      if (!t0 || !t1) return null;
			      return {
			        x: ((Number(t0.clientX) || 0) + (Number(t1.clientX) || 0)) / 2,
			        y: ((Number(t0.clientY) || 0) + (Number(t1.clientY) || 0)) / 2,
			      };
			    };
				    const startTouchPan = (event) => {
				      if (!viewportEl) return;
				      if (!canViewportScroll()) return;
				      if (!event.touches || event.touches.length !== 2) return;
			      const c = touchCenter(event.touches);
			      if (!c) return;
				      touchPanActive = true;
				      touchPanStart = {
				        x: c.x,
				        y: c.y,
				        scrollLeft: viewportEl.scrollLeft,
				        scrollTop: viewportEl.scrollTop,
				        panX: viewportPanX,
				        panY: viewportPanY,
				      };
				      event.preventDefault();
				    };
				    const moveTouchPan = (event) => {
				      if (!viewportEl || !touchPanActive || !touchPanStart) return;
				      if (!event.touches || event.touches.length !== 2) return;
				      const c = touchCenter(event.touches);
				      if (!c) return;
				      const dx = c.x - touchPanStart.x;
				      const dy = c.y - touchPanStart.y;
				      if (useViewportMapping) {
				        viewportPanX = (Number(touchPanStart.panX) || 0) + dx;
				        viewportPanY = (Number(touchPanStart.panY) || 0) + dy;
				        try { applyViewportTransformToWorld(); } catch (error) { /* ignore */ }
				        try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
				      } else {
				        viewportEl.scrollLeft = touchPanStart.scrollLeft - dx;
				        viewportEl.scrollTop = touchPanStart.scrollTop - dy;
				      }
				      event.preventDefault();
				      event.stopPropagation();
				    };
			    const stopTouchPan = () => {
			      touchPanActive = false;
			      touchPanStart = null;
			    };
			    viewportEl?.addEventListener('touchstart', startTouchPan, { capture: true, passive: false });
			    viewportEl?.addEventListener('touchmove', moveTouchPan, { capture: true, passive: false });
			    viewportEl?.addEventListener('touchend', stopTouchPan, { capture: true, passive: true });
			    viewportEl?.addEventListener('touchcancel', stopTouchPan, { capture: true, passive: true });

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

	    const loadCanvasSnapshotAsync = (rawState, options = {}) => new Promise((resolve) => {
	      loadCanvasSnapshot(rawState, () => resolve(true), options);
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
	          await loadCanvasSnapshotAsync(step.canvas_state, { sourceWidth: parseIntSafe(step.canvas_width), sourceHeight: parseIntSafe(step.canvas_height) });
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
		      applyPitchZoom(1.0, { silent: true });
		      setStatus('Zoom restablecido.');
		    });
	    stageSizeDownButton?.addEventListener('click', () => {
	      const next = writeStageFactor(getStageFactor() - 0.06);
	      applyStageSizeUi();
	      setStatus(`Campo: ${Math.round(next * 100)}%.`);
	    });
	    stageSizeUpButton?.addEventListener('click', () => {
	      const next = writeStageFactor(getStageFactor() + 0.06);
	      applyStageSizeUi();
	      setStatus(`Campo: ${Math.round(next * 100)}%.`);
	    });
	    stageSizeFitButton?.addEventListener('click', () => {
	      // Ajuste rápido para minimizar scroll de página: intentamos que el alto del campo
	      // quepa en la ventana actual (sin tocar posiciones/objetos).
	      try {
	        const rect = stage.getBoundingClientRect();
	        const top = Math.max(0, Number(rect.top) || 0);
	        const room = Math.max(260, window.innerHeight - top - 240);
	        const aspect = pitchOrientation === 'portrait' ? (684 / 1054) : (1054 / 684); // width/height
	        const desiredW = room * aspect;
	        const base = stageBaseMaxWidth();
	        const next = writeStageFactor(desiredW / Math.max(1, base));
	        applyStageSizeUi();
	        setStatus('Campo ajustado a pantalla.');
	      } catch (error) {
	        const next = writeStageFactor(0.82);
	        applyStageSizeUi();
	        setStatus(`Campo: ${Math.round(next * 100)}%.`);
	      }
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
		    const resourceDetails = document.getElementById('task-resource-details');
		    const resourceSummaryLabel = document.getElementById('task-resource-summary-label');
		    const resourceSelect = document.getElementById('task-resource-select');
		    const resourceHelper = document.querySelector('.resource-helper');
		    const getDeviceMode = () => {
		      const raw = safeText(document.body?.dataset?.deviceMode);
		      if (raw === 'desktop' || raw === 'tablet') return raw;
		      return 'auto';
		    };
		    const isDesktopUi = () => {
		      if (getDeviceMode() === 'desktop') return true;
		      if (getDeviceMode() === 'tablet') return false;
		      try { return !!(window.matchMedia && window.matchMedia('(min-width: 980px)').matches); } catch (error) { return true; }
		    };
		    const isWideUi = () => {
		      if (getDeviceMode() === 'desktop') return true;
		      if (getDeviceMode() === 'tablet') return false;
		      try { return !!(window.matchMedia && window.matchMedia('(min-width: 761px)').matches); } catch (error) { return true; }
		    };
		    const isSmallUi = () => {
		      if (getDeviceMode() === 'tablet') return true;
		      if (getDeviceMode() === 'desktop') return false;
		      try { return !!(window.matchMedia && window.matchMedia('(max-width: 979px)').matches); } catch (error) { return false; }
		    };
		    // En escritorio ocultamos el <summary> y mostramos las pestañas siempre vía CSS
		    // (sin necesidad de abrir el <details>, que podía superponer el contenido).
		    try {
		      if (resourceDetails && isDesktopUi()) {
		        resourceDetails.open = false;
		      }
		    } catch (error) { /* ignore */ }
		    let activeResourceKey = '';
    const resourceLabelForKey = (key) => {
      const normalized = safeText(key);
      const match = resourceTabs.find((tab) => safeText(tab.dataset.resource) === normalized);
      return safeText(match?.textContent, normalized);
    };
	    const activateResourcePanel = (key) => {
	      const normalized = safeText(key);
	      activeResourceKey = normalized;
	      resourceTabs.forEach((tab) => tab.classList.toggle('is-active', safeText(tab.dataset.resource) === normalized && !!normalized));
	      resourcePanels.forEach((panel) => {
	        const visible = !!normalized && safeText(panel.dataset.panel) === normalized;
	        panel.hidden = !visible;
	        panel.classList.toggle('is-visible', visible);
	      });
	      if (resourceSelect) {
	        resourceSelect.value = normalized || '';
	      }
	      if (resourceSummaryLabel) {
	        resourceSummaryLabel.textContent = normalized ? resourceLabelForKey(normalized) : 'Selecciona…';
	      }
	      if (resourceHelper) {
	        resourceHelper.hidden = !!normalized;
	      }
	    };
	    resourceTabs.forEach((tab) => {
	      tab.addEventListener('click', () => {
	        const target = safeText(tab.dataset.resource);
	        if (target && target === activeResourceKey) activateResourcePanel('');
	        else activateResourcePanel(target);
	        // En móvil/tablet, cerrar el desplegable al elegir una pestaña.
	        try {
	          if (resourceDetails && resourceDetails.open && isSmallUi()) {
	            resourceDetails.open = false;
	          }
	        } catch (error) { /* ignore */ }
	      });
	    });
	    resourceSelect?.addEventListener('change', () => {
	      const key = safeText(resourceSelect.value);
	      activateResourcePanel(key);
	    });
		    if (resourceTabs.length && resourcePanels.length) {
	      // En escritorio mostramos por defecto "Recursos base" (más rápido).
	      // En pantallas pequeñas arrancamos cerrado para dejar más espacio al campo.
	      let initialResource = '';
	      try {
	        initialResource = isWideUi() ? 'base' : '';
	      } catch (error) {
	        initialResource = 'base';
	      }
		      activateResourcePanel(initialResource);
		    }
		    // Permite alternar el modo (Ordenador/iPad/Auto) sin recargar ni perder trabajo.
		    try {
		      window.addEventListener('webstats:tpad:device-change', () => {
		        try {
		          if (resourceDetails && isDesktopUi()) resourceDetails.open = false;
		          if (!activeResourceKey) activateResourcePanel(isWideUi() ? 'base' : '');
		          else activateResourcePanel(activeResourceKey);
		        } catch (error) { /* ignore */ }
		      });
		    } catch (error) { /* ignore */ }

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
	    let resizeBaseline = null;
	    let resizeFinalizeTimer = null;
	    const captureResizeBaseline = () => {
	      if (resizeBaseline) return resizeBaseline;
	      resizeBaseline = {
	        width: Math.round(canvas.getWidth() || 0),
	        height: Math.round(canvas.getHeight() || 0),
	        canvas_state: serializeCanvasOnly(),
	        preset: presetSelect.value || 'full_pitch',
	        orientation: pitchOrientation,
	        zoom: pitchZoom,
	      };
	      return resizeBaseline;
	    };
	    const clearResizeBaseline = () => { resizeBaseline = null; };
		    const applyResizeFromBaseline = () => {
		      const baseline = captureResizeBaseline();
		      const stageRect = stage?.getBoundingClientRect?.() || { width: stage?.clientWidth || 960, height: stage?.clientHeight || 640 };
		      const width = Math.max(320, Math.round(stageRect.width || 960));
		      const height = Math.max(220, Math.round(stageRect.height || 640));
		      if (width <= 0 || height <= 0) return;
		      if (Math.abs(width - (canvas.getWidth() || 0)) < 2 && Math.abs(height - (canvas.getHeight() || 0)) < 2) return;
		      canvas.setDimensions({ width, height });
		      canvas.calcOffset();
		      if (!useViewportMapping) {
		        // Reescalado "sin acumulación": siempre desde el snapshot capturado al inicio del resize.
		        loadCanvasSnapshot(
		          baseline.canvas_state,
		          () => {
		            try { persistActiveStepSnapshot(); } catch (e) { /* ignore */ }
		            try { syncInspector(); } catch (e) { /* ignore */ }
		            try { refreshLivePreview(); } catch (e) { /* ignore */ }
		          },
		          { sourceWidth: baseline.width, sourceHeight: baseline.height },
		        );
		      } else {
		        // En modo viewport, nunca reescalamos/reescribimos objetos al girar o hacer resize:
		        // solo reajustamos el encuadre.
		        try { applyViewportTransformToWorld(); } catch (e) { /* ignore */ }
		        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
		        try { persistActiveStepSnapshot(); } catch (e) { /* ignore */ }
		        try { syncInspector(); } catch (e) { /* ignore */ }
		        try { refreshLivePreview(); } catch (e) { /* ignore */ }
		      }
		      // El SVG del césped depende del preset/orientación, lo reinyectamos por seguridad sin tocar objetos.
		      try { applyPitchSurface(baseline.preset, baseline.orientation); } catch (e) { /* ignore */ }
		      try { syncZoomUi(); } catch (e) { /* ignore */ }
		    };
		    const scheduleResize = () => {
	      window.clearTimeout(resizeTimer);
	      window.clearTimeout(resizeFinalizeTimer);
	      captureResizeBaseline();
		      resizeTimer = window.setTimeout(() => {
		        applyResizeFromBaseline();
		        renderSurfaceThumbs();
		      }, 200);
	      // Si durante la rotación/resize hay varios eventos, cerramos la sesión cuando se estabilice.
	      resizeFinalizeTimer = window.setTimeout(() => {
	        clearResizeBaseline();
	      }, 900);
	    };
	    window.addEventListener('resize', scheduleResize);
	    window.addEventListener('orientationchange', scheduleResize);
	    try {
	      window.visualViewport?.addEventListener('resize', scheduleResize);
	    } catch (error) { /* ignore */ }

		    let isSubmitting = false;
			    form.addEventListener('submit', async (event) => {
	      // Segunda pasada: dejamos que el navegador envíe el POST (evita bucles con requestSubmit()).
		      if (form.dataset.previewReady === '1') {
		        form.dataset.previewReady = '';
		        return;
		      }
		      if (isSubmitting) return;
		      if (isSimulating) {
		        event.preventDefault();
		        setStatus('Modo simulación: sal del simulador para guardar la tarea.', true);
		        try { window.alert('Estás en modo simulación. Sal del simulador para poder guardar la tarea.'); } catch (error) { /* ignore */ }
		        return;
		      }
			      event.preventDefault();
		      try { syncRichEditorsNow(); } catch (error) { /* ignore */ }
			      try { persistDraftNow('submit'); } catch (error) { /* ignore */ }
	      if (pingKeepalive) {
	        const ok = await pingKeepalive();
	        if (!ok) {
	          // Asegura mensaje visible incluso si el usuario está scrolleado abajo.
	          try { window.alert('Sesión caducada. Se guardó un borrador local; inicia sesión y vuelve a esta pestaña.'); } catch (error) { /* ignore */ }
	          try {
	            const next = encodeURIComponent(window.location.pathname + window.location.search);
	            window.location.href = `/login/?next=${next}`;
	          } catch (error) { /* ignore */ }
	          return;
	        }
	      }
		      isSubmitting = true;
					      // Enviar preview HD al guardar (se usa también en la card y en el PDF).
					      // Usamos PNG para evitar artefactos en líneas/flechas dentro del PDF.
					      await syncHiddenBuilderFields({
					        previewOptions: { maxWidth: 4096, mime: 'image/png', quality: 0.98 },
					        applyLivePreview: false,
					      });
			      form.dataset.previewReady = '1';
		      isSubmitting = false;
			      form.requestSubmit();
			    });
		    // Rotación con snap (Shift): útil para flechas/líneas rectas delimitando zonas.
		    const shouldSnapRotation = (obj) => {
		      const kind = safeText(obj?.data?.kind).toLowerCase();
		      return kind.startsWith('line') || kind.startsWith('arrow') || kind === 'zone' || kind.startsWith('shape');
		    };
		    canvas.on('object:rotating', (opt) => {
		      const target = opt?.target;
		      const e = opt?.e;
		      if (!target || !e || !e.shiftKey) return;
		      if (!shouldSnapRotation(target)) return;
		      const step = 45;
		      const raw = Number(target.angle) || 0;
		      const snapped = Math.round(raw / step) * step;
		      try { target.rotate(snapped); } catch (error) { /* ignore */ }
		      try { target.setCoords(); } catch (error) { /* ignore */ }
		    });

		    // Flechas: al escalar, mantenemos la punta constante y el trazo con `strokeUniform`.
		    canvas.on('object:scaling', (opt) => {
		      const target = opt?.target;
		      if (!target) return;
		      const kind = safeText(target?.data?.kind);
		      if (!kind || !kind.startsWith('arrow')) return;
		      if (!Array.isArray(target._objects)) return;
		      const sx = Number(target.scaleX) || 1;
		      const sy = Number(target.scaleY) || 1;
		      const tri = target._objects.find((child) => child && child.type === 'triangle');
		      if (tri) {
		        try { tri.set({ scaleX: sx ? (1 / sx) : 1, scaleY: sy ? (1 / sy) : 1 }); } catch (error) { /* ignore */ }
		      }
		      target._objects.forEach((child) => {
		        if (!child) return;
		        try { if (child.strokeWidth !== undefined) child.strokeUniform = true; } catch (e) { /* ignore */ }
		      });
		    });
	  };
})();
