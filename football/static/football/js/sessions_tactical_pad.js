(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const escapeHtml = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
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

	  const __grassTextureCache = new Map();
	  const __buildGrassTextureDataUrl = (styleKey) => {
	    const style = safeText(styleKey, 'classic');
	    if (style !== 'realistic') return '';
	    if (__grassTextureCache.has(style)) return __grassTextureCache.get(style);
	    try {
	      const size = 256;
	      const canvas = document.createElement('canvas');
	      canvas.width = size;
	      canvas.height = size;
	      const ctx = canvas.getContext('2d');
	      if (!ctx) return '';
	      ctx.fillStyle = '#4f7f3a';
	      ctx.fillRect(0, 0, size, size);

	      // Base noise: tiny pixels.
	      for (let i = 0; i < 9000; i += 1) {
	        const x = (Math.random() * size) | 0;
	        const y = (Math.random() * size) | 0;
	        const g = 110 + ((Math.random() * 70) | 0);
	        const a = 0.08 + (Math.random() * 0.12);
	        ctx.fillStyle = `rgba(0, ${g}, 0, ${a})`;
	        ctx.fillRect(x, y, 2, 2);
	      }

	      // Subtle blades / streaks.
	      ctx.globalAlpha = 0.12;
	      for (let i = 0; i < 220; i += 1) {
	        const x = Math.random() * size;
	        const y = Math.random() * size;
	        const len = 12 + Math.random() * 44;
	        const angle = (-Math.PI / 3) + (Math.random() * (Math.PI / 5));
	        const x2 = x + Math.cos(angle) * len;
	        const y2 = y + Math.sin(angle) * len;
	        ctx.lineWidth = 1 + Math.random() * 2;
	        const c = 120 + ((Math.random() * 60) | 0);
	        ctx.strokeStyle = `rgb(${30}, ${c}, ${30})`;
	        ctx.beginPath();
	        ctx.moveTo(x, y);
	        ctx.lineTo(x2, y2);
	        ctx.stroke();
	      }
	      ctx.globalAlpha = 1;

	      // Soft vignette (makes it feel less flat when scaled).
	      const grad = ctx.createRadialGradient(size / 2, size / 2, size / 4, size / 2, size / 2, size * 0.9);
	      grad.addColorStop(0, 'rgba(255,255,255,0)');
	      grad.addColorStop(1, 'rgba(0,0,0,0.18)');
	      ctx.fillStyle = grad;
	      ctx.fillRect(0, 0, size, size);

	      const dataUrl = canvas.toDataURL('image/png');
	      __grassTextureCache.set(style, dataUrl);
	      return dataUrl;
	    } catch (error) {
	      return '';
	    }
	  };

		  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
		    const preset = String(presetKey || 'full_pitch').trim();
		    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
		    const grassStyle = safeText(grassStyleKey, 'classic') === 'realistic' ? 'realistic' : 'classic';
		    // Lienzo con proporción real 105x68 (escalado) y un pequeño "bleed" para que el trazo
		    // del borde no se recorte incluso con overflow hidden.
		    const stageW = orientation === 'portrait' ? 680 : 1050;
		    const stageH = orientation === 'portrait' ? 1050 : 680;
		    // Bleed suficiente para que:
		    // - el borde del campo (stroke) no se recorte
		    // - la "parte posterior" de las porterías (que va fuera de la línea de fondo) se vea
		    // Importante: el editor usa `worldWidth/worldHeight` para mapear punteros y viewportTransform.
		    // Si el viewBox cambia entre presets (por bleed diferente) se desincroniza el mapeo y parece
		    // que "no deja colocar jugadores" en ciertas zonas. Mantenemos bleed constante.
		    // En campo completo, el goalDepth típico ronda ~22px; dejamos margen generoso.
		    const bleed = 30;
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

	    let grassFillId = 'pitch-bg';
	    if (grassStyle === 'realistic') {
	      const dataUrl = __buildGrassTextureDataUrl('realistic');
	      if (dataUrl) {
	        grassFillId = 'pitch-grass-img';
	        const pattern = createSvgNode(doc, 'pattern', {
	          id: grassFillId,
	          patternUnits: 'userSpaceOnUse',
	          width: 220,
	          height: 220,
	        });
	        const image = createSvgNode(doc, 'image', {
	          href: dataUrl,
	          x: 0,
	          y: 0,
	          width: 220,
	          height: 220,
	          preserveAspectRatio: 'xMidYMid slice',
	        });
	        pattern.appendChild(image);
	        defs.appendChild(pattern);
	      }
	    }
	    root.appendChild(defs);

    // Fondo:
    // - Para "campo completo" y "F7 sobre F11" rellenamos toda la superficie para que el césped no
    //   quede cortado por bordes/redondeos del contenedor.
    // - Para superficies parciales (medio campo/tercios/futsal/F7 individual) dejamos transparente
    //   el exterior del rectángulo de juego para que no “gaste” página con verde innecesario
    //   (en editor se verá el fondo del panel; en PDF quedará blanco).
    // En el editor rellenamos el exterior con césped para que no parezca que hay “huecos” alrededor.
    // El recorte para PDF/cards ya se hace al exportar la preview (data-pitch-box).
    const fillOutside = `url(#${grassFillId})`;
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
        fill: `url(#${grassFillId})`,
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
          fill: index % 2 === 0 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
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
    const grassStyleInput = document.getElementById('draw-task-pitch-grass-style');
    const orientationToggle = document.getElementById('pitch-orientation-toggle');
    const orientationLabel = document.getElementById('pitch-orientation-label');
    const grassToggle = document.getElementById('pitch-grass-toggle');
    const grassLabel = document.getElementById('pitch-grass-label');
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
				    const drillsStripEl = document.getElementById('task-drills-strip');
				    const drillsInputEl = document.getElementById('draw-task-drills-json');
				    const drillsIconColorInput = document.getElementById('draw-task-drills-icon-color');
				    const drillsPickerEl = document.getElementById('task-drills-picker');
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
		    const tokenStyleActions = document.getElementById('task-token-style-actions');
		    const tokenColorGrid = document.getElementById('task-token-color-grid');
		    const tokenBaseColorInput = document.getElementById('task-token-base-color');
		    const tokenStripeColorInput = document.getElementById('task-token-stripe-color');
		    const tokenPatternActions = document.getElementById('task-token-pattern-actions');
		    const tokenGlobalStyleActions = document.getElementById('task-token-style-global');
				    const commandBar = document.getElementById('task-command-bar');
				    const commandMoreBtn = document.getElementById('task-command-more');
				    const commandMenu = document.getElementById('task-command-menu');
			    const simBtn = document.getElementById('task-sim-btn');
			    const simPopover = document.getElementById('task-sim-popover');
			    const simCloseBtn = document.getElementById('task-sim-close');
			    const simToggleBtn = document.getElementById('task-sim-toggle');
			    const simResetBtn = document.getElementById('task-sim-reset');
			    const simCaptureBtn = document.getElementById('task-sim-capture');
			    const simPlayBtn = document.getElementById('task-sim-play');
			    const simRemoveBtn = document.getElementById('task-sim-remove');
			    const simPrevBtn = document.getElementById('task-sim-prev');
			    const simNextBtn = document.getElementById('task-sim-next');
			    const simDuplicateBtn = document.getElementById('task-sim-duplicate');
			    const simShareBtn = document.getElementById('task-sim-share');
				    const simExportStepBtn = document.getElementById('task-sim-export-step');
				    const simExportAllBtn = document.getElementById('task-sim-export-all');
				    const simRecordBtn = document.getElementById('task-sim-record');
				    const simRecordFormatSelect = document.getElementById('task-sim-record-format');
				    const simRecordTitleInput = document.getElementById('task-sim-record-title');
				    const simView3dBtn = document.getElementById('task-sim-view-3d');
				    const simVideoStudioBtn = document.getElementById('task-sim-video-studio');
				    const simClipSaveBtn = document.getElementById('task-sim-clip-save');
				    const simClipImportBtn = document.getElementById('task-sim-clip-import');
				    const simVideoImportBtn = document.getElementById('task-sim-video-import');
				    const simClipDestWrap = document.getElementById('task-sim-clip-dest-wrap');
				    const simClipDestSelect = document.getElementById('task-sim-clip-dest');
				    const simPackBtn = document.getElementById('task-sim-pack');
				    const simClipFileInput = document.getElementById('task-sim-clip-file');
				    const simVideoFileInput = document.getElementById('task-sim-video-file');
				    const simClipsList = document.getElementById('task-sim-clips');
				    const playbookPaneEl = document.getElementById('task-playbook-pane');
				    const playbookOpenSimBtn = document.getElementById('task-playbook-open-sim');
				    const playbookOpen3dBtn = document.getElementById('task-playbook-open-3d');
				    const playbookOpenVideoBtn = document.getElementById('task-playbook-open-video');
				    const playbookExportPackBtn = document.getElementById('task-playbook-export-pack');
				    const simToScenariosBtn = document.getElementById('task-sim-to-scenarios');
				    const simShareUrlInput = document.getElementById('task-sim-share-url');
				    const simAutoCaptureInput = document.getElementById('task-sim-autocapture');
				    const simProEnabledInput = document.getElementById('task-sim-pro-enabled');
				    const simProPanel = document.getElementById('task-sim-pro-panel');
			    const isTacticsMode = document.body.classList.contains('tactics-mode');

			    const ensurePlaybookDock = () => {
			      if (!playbookPaneEl) return null;
			      let dock = document.getElementById('task-playbook-dock');
			      if (dock) return dock;
			      dock = document.createElement('div');
			      dock.id = 'task-playbook-dock';
			      dock.style.display = 'grid';
			      dock.style.gap = '0.75rem';
			      playbookPaneEl.innerHTML = '';
			      playbookPaneEl.appendChild(dock);
			      return dock;
			    };

			    const ensureDockSection = (dock, id, title) => {
			      if (!dock) return null;
			      let section = document.getElementById(id);
			      if (section) return section;
			      section = document.createElement('div');
			      section.id = id;
			      section.style.display = 'grid';
			      section.style.gap = '0.55rem';
			      if (title) {
			        const h = document.createElement('div');
			        h.className = 'meta';
			        h.style.fontWeight = '900';
			        h.style.letterSpacing = '0.08em';
			        h.style.textTransform = 'uppercase';
			        h.textContent = title;
			        section.appendChild(h);
			      }
			      dock.appendChild(section);
			      return section;
			    };

			    const dockSimPopoverIfNeeded = () => {
			      if (!isTacticsMode) return;
			      if (!playbookPaneEl || !simPopover) return;
			      const dock = ensurePlaybookDock();
			      if (!dock) return;
			      const simHost = ensureDockSection(dock, 'task-playbook-sim-host', 'Simulador');
			      if (!simHost) return;
			      if (simPopover.parentElement !== simHost) {
			        simHost.appendChild(simPopover);
			      }
			      try { simPopover.classList.add('is-docked'); } catch (e) { /* ignore */ }
			      try { simPopover.hidden = true; } catch (e) { /* ignore */ }
			    };
			    try { dockSimPopoverIfNeeded(); } catch (e) { /* ignore */ }

			    // Pictogramas (drills): deben verse como "secuencia" para el entrenador,
			    // pero no forman parte del dibujo del campo. Se renderizan como tira debajo de la pizarra.
			    const cssEscape = (value) => {
			      const raw = String(value || '');
			      if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(raw);
			      return raw.replace(/[^a-zA-Z0-9_-]/g, '\\$&');
			    };
				    const parseJsonList = (value) => {
				      const raw = String(value || '').trim();
				      if (!raw) return [];
				      if (!(raw.startsWith('[') && raw.endsWith(']'))) return [];
			      try {
			        const parsed = JSON.parse(raw);
			        return Array.isArray(parsed) ? parsed.map((v) => safeText(v)).filter(Boolean) : [];
			      } catch (e) {
			        return [];
			      }
				    };
				    // Color de los pictogramas (secuencia calentamiento). Se persiste en hidden input para PDF.
				    let drillsIconColor = (() => {
				      const raw = safeText(drillsIconColorInput?.value);
				      const parsed = parseColorToHex(raw, '#0f7a35');
				      return parsed || '#0f7a35';
				    })();
				    if (drillsIconColorInput) drillsIconColorInput.value = drillsIconColor;
				    const readDrillsIds = () => parseJsonList(drillsInputEl?.value);
			    const drillCardFromDom = (id) => {
			      const safeId = safeText(id);
			      if (!safeId || !drillsPickerEl) return null;
			      const cb = drillsPickerEl.querySelector(`input[type="checkbox"][data-drill-id="${cssEscape(safeId)}"]`);
			      const wrapper = cb?.closest('label');
			      if (!wrapper) return null;
			      const label = safeText(wrapper.getAttribute('data-drill-label')) || safeText(wrapper.textContent).replace(/\s+/g, ' ').trim();
			      const icon = wrapper.querySelector('img.drill-icon')?.getAttribute('src') || '';
			      return { id: safeId, label, icon };
			    };
			    const DRILLS_DRAG_MIME = 'application/x-webstats-tactical-resource';
			    const wireDrillsStripDnD = () => {
			      if (!drillsStripEl) return;
			      Array.from(drillsStripEl.querySelectorAll('button.pitch-drill-chip[data-add]')).forEach((button) => {
			        button.draggable = true;
			        button.addEventListener('dragstart', (event) => {
			          const add = safeText(button.dataset.add);
			          if (!add) {
			            event.preventDefault();
			            return;
			          }
			          const payload = {
			            kind: add,
			            title: safeText(button.dataset.title),
			            desiredSize: 72,
			          };
			          try { event.dataTransfer?.setData(DRILLS_DRAG_MIME, JSON.stringify(payload)); } catch (e) { /* ignore */ }
			          try { event.dataTransfer?.setData('text/plain', JSON.stringify(payload)); } catch (e) { /* ignore */ }
			          if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
			          button.classList.add('is-dragging');
			          setStatus('Suelta el pictograma sobre el campo.');
			        });
			        button.addEventListener('dragend', () => {
			          button.classList.remove('is-dragging');
			          stage.classList.remove('is-drop-target');
			        });
			      });
			    };
				    const renderDrillsStrip = () => {
				      if (!drillsStripEl) return;
				      const ids = readDrillsIds();
				      const cards = ids.map((id) => drillCardFromDom(id)).filter(Boolean);
				      if (!cards.length) {
				        drillsStripEl.innerHTML = '';
				        drillsStripEl.hidden = true;
				        return;
				      }
				      drillsStripEl.hidden = false;
				      try { drillsStripEl.style.setProperty('--drill-icon-color', drillsIconColor); } catch (e) { /* ignore */ }
				      drillsStripEl.innerHTML = [
				        '<span class="pitch-drills-title">Secuencia</span>',
				        '<button type="button" class="pitch-drills-color" data-drills-color title="Cambiar color de pictogramas"><span class="pitch-drills-swatch" aria-hidden="true"></span>Color</button>',
				        ...cards.map((card) => {
				          const icon = safeText(card.icon);
				          const label = safeText(card.label, card.id);
				          const add = icon ? `image_url:${icon}` : '';
				          const safeIcon = icon ? icon.replace(/"/g, '&quot;') : '';
				          return `<button type="button" class="pitch-drill-chip" data-add="${add}" data-title="${label}" title="${label}">${icon ? `<span class="pitch-drill-icon" style="--drill-mask:url(&quot;${safeIcon}&quot;)" aria-hidden="true"></span>` : ''}<span>${label}</span></button>`;
				        }),
				      ].join('');
				      wireDrillsStripDnD();
				    };
				    try { drillsInputEl?.addEventListener('change', renderDrillsStrip); } catch (e) { /* ignore */ }
				    try { drillsPickerEl?.addEventListener('change', renderDrillsStrip); } catch (e) { /* ignore */ }
				    try {
				      const ensureDrillsColorPicker = () => {
				        let picker = document.getElementById('task-drills-color-picker');
				        if (picker) return picker;
				        picker = document.createElement('input');
				        picker.type = 'color';
				        picker.id = 'task-drills-color-picker';
				        picker.style.position = 'fixed';
				        picker.style.left = '-9999px';
				        picker.style.top = '0';
				        picker.style.opacity = '0';
				        document.body.appendChild(picker);
				        return picker;
				      };
				      const setDrillsIconColor = (value) => {
				        const parsed = parseColorToHex(value, '#0f7a35') || '#0f7a35';
				        drillsIconColor = parsed;
				        if (drillsIconColorInput) drillsIconColorInput.value = drillsIconColor;
				        try { drillsStripEl?.style?.setProperty('--drill-icon-color', drillsIconColor); } catch (e) { /* ignore */ }
				      };
				      drillsStripEl?.addEventListener('click', (event) => {
				        const colorBtn = event.target.closest('button[data-drills-color]');
				        if (colorBtn) {
				          event.preventDefault();
				          event.stopPropagation();
				          const picker = ensureDrillsColorPicker();
				          try { picker.value = drillsIconColor; } catch (e) { /* ignore */ }
				          picker.oninput = () => setDrillsIconColor(picker.value);
				          picker.onchange = () => setDrillsIconColor(picker.value);
				          try { picker.click(); } catch (e) { /* ignore */ }
				          return;
				        }
				        const button = event.target.closest('button.pitch-drill-chip[data-add]');
				        if (!button) return;
				        const add = safeText(button.dataset.add);
				        if (!add || !add.startsWith('image_url:')) return;
			        const url = add.slice('image_url:'.length);
			        const title = safeText(button.dataset.title) || 'Pictograma';
				        Array.from(drillsStripEl.querySelectorAll('button.pitch-drill-chip')).forEach((node) => node.classList.remove('is-active'));
				        button.classList.add('is-active');
				        activateFactory((left, top) => buildUrlAssetObject(url, left, top, { desiredSize: 72, title }), 'un pictograma', add);
				      });
				    } catch (e) { /* ignore */ }
			    try { renderDrillsStrip(); } catch (e) { /* ignore */ }
			    const simProScrub = document.getElementById('task-sim-pro-scrub');
			    const simProTimeLabel = document.getElementById('task-sim-pro-time');
			    const simProTotalLabel = document.getElementById('task-sim-pro-total');
			    const simProLoopInput = document.getElementById('task-sim-pro-loop');
			    const simProEasingSelect = document.getElementById('task-sim-pro-easing');
			    const simProKfAddBtn = document.getElementById('task-sim-pro-kf-add');
			    const simProKfDelBtn = document.getElementById('task-sim-pro-kf-del');
			    const simProKfClearBtn = document.getElementById('task-sim-pro-clear');
			    const simProKfList = document.getElementById('task-sim-pro-kf-list');
			    const simTrajectoriesInput = document.getElementById('task-sim-trajectories');
			    const simMagnetsInput = document.getElementById('task-sim-magnets');
			    const simGuidesInput = document.getElementById('task-sim-guides');
			    const simCollisionInput = document.getElementById('task-sim-collision');
			    const simSpeedSelect = document.getElementById('task-sim-speed');
			    const simStepsList = document.getElementById('task-sim-steps');
			    const simMetaPanel = document.getElementById('task-sim-meta');
			    const simStepTitleInput = document.getElementById('task-sim-step-title');
			    const simStepDurationInput = document.getElementById('task-sim-step-duration');
			    const simRoutesPanel = document.getElementById('task-sim-routes-panel');
			    const simRouteToggleBtn = document.getElementById('task-sim-route-toggle');
			    const simRouteUndoBtn = document.getElementById('task-sim-route-undo');
			    const simRouteClearBtn = document.getElementById('task-sim-route-clear');
			    const simRouteSplineInput = document.getElementById('task-sim-route-spline');
			    const simBallFollowBtn = document.getElementById('task-sim-ball-follow');
			    const simBallPassBtn = document.getElementById('task-sim-ball-pass');
			    const playbookListUrlInput = document.getElementById('task-playbook-list-url');
			    const playbookSaveUrlInput = document.getElementById('task-playbook-save-url');
			    const playbookDeleteUrlInput = document.getElementById('task-playbook-delete-url');
			    const playbookFavoriteUrlInput = document.getElementById('task-playbook-favorite-url');
			    const playbookCloneUrlInput = document.getElementById('task-playbook-clone-url');
			    const playbookTeamsUrlInput = document.getElementById('task-playbook-teams-url');
			    const playbookVersionsUrlInput = document.getElementById('task-playbook-versions-url');
			    const playbookShareUrlInput = document.getElementById('task-playbook-share-url');
			    const overlaysPresetSelect = document.getElementById('task-overlays-preset');
			    const scenarioTemplate3Btn = document.getElementById('task-scenario-template-3');
			    const videoStudioModal = document.getElementById('task-video-studio-modal');
			    const videoStudioCloseBtn = document.getElementById('task-video-studio-close');
			    const videoStudioPlayer = document.getElementById('task-video-studio-player');
			    const videoStudioCanvasEl = document.getElementById('task-video-studio-canvas');
			    const videoLoadBtn = document.getElementById('task-video-load');
			    const videoClearBtn = document.getElementById('task-video-clear');
			    const videoFileInput = document.getElementById('task-video-file');
			    const videoStatusEl = document.getElementById('task-video-status');
			    const videoToolPenBtn = document.getElementById('task-video-tool-pen');
			    const videoToolArrowBtn = document.getElementById('task-video-tool-arrow');
				    const videoToolCircleBtn = document.getElementById('task-video-tool-circle');
				    const videoToolRectBtn = document.getElementById('task-video-tool-rect');
				    const videoToolTextBtn = document.getElementById('task-video-tool-text');
				    const videoToolCalloutBtn = document.getElementById('task-video-tool-callout');
				    const videoToolSpotlightBtn = document.getElementById('task-video-tool-spotlight');
				    const videoToolBlurBtn = document.getElementById('task-video-tool-blur');
				    const videoToolFreezeBtn = document.getElementById('task-video-tool-freeze');
				    const videoUndoBtn = document.getElementById('task-video-undo');
				    const videoClearDrawBtn = document.getElementById('task-video-clear-draw');
				    const videoColorInput = document.getElementById('task-video-color');
				    const videoWidthSelect = document.getElementById('task-video-width');
				    const videoExportBtn = document.getElementById('task-video-export');
				    const videoExportFormatSelect = document.getElementById('task-video-export-format');
				    const videoExportQualitySelect = document.getElementById('task-video-export-quality');
				    const videoExportFpsSelect = document.getElementById('task-video-export-fps');
				    const videoExportLenSelect = document.getElementById('task-video-export-len');
				    const videoExportSlidesBtn = document.getElementById('task-video-export-slides');
				    const videoExportPackBtn = document.getElementById('task-video-export-pack');
				    const videoScrubInput = document.getElementById('task-video-scrub');
				    const videoTimeEl = document.getElementById('task-video-time');
				    const videoDurationEl = document.getElementById('task-video-duration');
				    const videoKeyframeAddBtn = document.getElementById('task-video-kf-add');
				    const videoKeyframeDeleteAllBtn = document.getElementById('task-video-kf-delete-all');
				    const videoKeyframeList = document.getElementById('task-video-kf-list');
				    const videoSpotlightEl = document.getElementById('task-video-spotlight');
				    const videoBlurWrapEl = document.getElementById('task-video-blur-wrap');
				    const videoLayerAddBtn = document.getElementById('task-video-layer-add');
				    const videoLayerFromSelectionBtn = document.getElementById('task-video-layer-from-selection');
				    const videoProEnabledInput = document.getElementById('task-video-pro-enabled');
				    const videoShowHandlesInput = document.getElementById('task-video-show-handles');
				    const videoLayerStatusEl = document.getElementById('task-video-layer-status');
				    const videoLayerListEl = document.getElementById('task-video-layer-list');
				    const videoLayerEditorEl = document.getElementById('task-video-layer-editor');
				    const videoLayerNameInput = document.getElementById('task-video-layer-name');
				    const videoLayerInInput = document.getElementById('task-video-layer-in');
				    const videoLayerOutInput = document.getElementById('task-video-layer-out');
				    const videoLayerFadeInInput = document.getElementById('task-video-layer-fadein');
				    const videoLayerFadeOutInput = document.getElementById('task-video-layer-fadeout');
				    const videoLayerSetInBtn = document.getElementById('task-video-layer-set-in');
				    const videoLayerSetOutBtn = document.getElementById('task-video-layer-set-out');
				    const videoLayerStrokeAnimSelect = document.getElementById('task-video-layer-stroke-anim');
				    const videoLayerDeleteBtn = document.getElementById('task-video-layer-delete');
				    const patternPopover = document.getElementById('task-pattern-popover');
				    const patternCloseBtn = document.getElementById('task-pattern-close');
				    const formationPopover = document.getElementById('task-formation-popover');
				    const formationCloseBtn = document.getElementById('task-formation-close');
				    const formationFormatSelect = document.getElementById('task-formation-format');
				    const formationShapeSelect = document.getElementById('task-formation-shape');
				    const formationDirectionSelect = document.getElementById('task-formation-direction');
				    const formationApplyBtn = document.getElementById('task-formation-apply');
				    const formationApplySelectedBtn = document.getElementById('task-formation-apply-selected');
				    const overlaysPopover = document.getElementById('task-overlays-popover');
				    const overlaysCloseBtn = document.getElementById('task-overlays-close');
				    const overlaySnapInput = document.getElementById('task-overlay-snap');
				    const overlayLanesInput = document.getElementById('task-overlay-lanes');
				    const overlaySectorsInput = document.getElementById('task-overlay-sectors');
				    const overlayPassLinesInput = document.getElementById('task-overlay-passlines');
				    const overlaySuperioritiesInput = document.getElementById('task-overlay-superiorities');
				    const overlaysApplyBtn = document.getElementById('task-overlays-apply');
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
		    const simStorageKey = (() => {
		      const base = safeText(draftKey) || safeText(draftNewKey) || 'webstats:tpad:draft:unknown';
		      return `${base}:simsteps_v1`;
		    })();
		    const clipsStorageKey = (() => {
		      const scope = safeText(form?.dataset?.scopeKey) || 'coach';
		      return `webstats:tpad:clips_v1:${scope}`;
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
	      try { window.localStorage.removeItem(simStorageKey); } catch (error) { /* ignore */ }
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

	    // Estilo global de fichas (para nuevos jugadores colocados en la pizarra).
	    const TOKEN_STYLE_STORAGE_KEY = 'webstats:tpad:token-style';
	    const normalizeTokenStyle = (value) => {
	      const v = safeText(value).trim().toLowerCase();
	      if (v === 'jersey' || v === 'photo') return v;
	      return 'disk';
	    };
	    const normalizeTokenPattern = (value) => {
	      const v = safeText(value).trim().toLowerCase();
	      if (v === 'solid') return 'solid';
	      return 'striped';
	    };
	    let tokenGlobalStyle = 'disk';
	    try { tokenGlobalStyle = normalizeTokenStyle(window.localStorage?.getItem(TOKEN_STYLE_STORAGE_KEY)); } catch (e) { /* ignore */ }
	    const syncTokenGlobalStyleUi = () => {
	      if (!tokenGlobalStyleActions) return;
	      Array.from(tokenGlobalStyleActions.querySelectorAll('button[data-global-token-style]') || []).forEach((btn) => {
	        const style = normalizeTokenStyle(btn.dataset.globalTokenStyle);
	        btn.classList.toggle('is-active', style === tokenGlobalStyle);
	        try { btn.setAttribute('aria-pressed', style === tokenGlobalStyle ? 'true' : 'false'); } catch (e) { /* ignore */ }
	      });
	    };
	    syncTokenGlobalStyleUi();
	    tokenGlobalStyleActions?.addEventListener('click', (event) => {
	      const btn = event.target.closest('button[data-global-token-style]');
	      if (!btn) return;
	      event.preventDefault();
	      tokenGlobalStyle = normalizeTokenStyle(btn.dataset.globalTokenStyle);
	      try { window.localStorage?.setItem(TOKEN_STYLE_STORAGE_KEY, tokenGlobalStyle); } catch (e) { /* ignore */ }
	      syncTokenGlobalStyleUi();
	      setStatus(`Estilo de fichas: ${tokenGlobalStyle === 'disk' ? 'chapa' : (tokenGlobalStyle === 'jersey' ? 'camiseta' : 'foto')}.`);
	      // Refresca el banco de jugadores para que el estilo se vea inmediatamente.
	      runWhenIdle(() => {
	        try { renderPlayerBank(); } catch (e) { /* ignore */ }
	      }, 120);
	    });

	    // Assets extraídos de PDFs importados. El catálogo de iconos se ha eliminado,
	    // pero seguimos renderizando cualquier `pdf_asset:<id>` existente en tareas previas.
	    const pdfAssetImages = new Map();
	    const pdfAssetLoading = new Set();
	    const pdfAssetPendingRefresh = new Set();
	    const normalizePdfAssetId = (value) => String(value ?? '').trim();
	    const buildPdfAssetUrl = (assetId) => {
	      const id = normalizePdfAssetId(assetId);
	      if (!id) return '';
	      return `/media/pdf-assets/${encodeURIComponent(id)}/`;
	    };
		    const ensurePdfAssetLoaded = (assetId) => {
	      const id = normalizePdfAssetId(assetId);
	      if (!id || pdfAssetImages.has(id) || pdfAssetLoading.has(id)) return;
	      const url = buildPdfAssetUrl(id);
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
	    // Apple Pencil: palm rejection en “Pencil Pro” (bloquea touch hacia Fabric cuando está dibujando).
	    // Además, “Ruta animada” captura el trazo y lo convierte en Timeline Pro.
	    try {
	      const upper = canvas.upperCanvasEl;
	      const isTouch = (ev) => safeText(ev?.pointerType) === 'touch';
	      const isPen = (ev) => safeText(ev?.pointerType) === 'pen';
	      const stopEv = (ev) => {
	        try { ev.preventDefault(); } catch (e) { /* ignore */ }
	        try { ev.stopPropagation(); } catch (e) { /* ignore */ }
	        try { ev.stopImmediatePropagation?.(); } catch (e) { /* ignore */ }
	      };
	      const dist = (a, b) => Math.hypot((Number(a?.x) || 0) - (Number(b?.x) || 0), (Number(a?.y) || 0) - (Number(b?.y) || 0));
	      const clearAnimPathOverlay = () => {
	        if (!animPathOverlay) return;
	        try { canvas.remove(animPathOverlay); } catch (e) { /* ignore */ }
	        animPathOverlay = null;
	      };
	      const buildAnimPathOverlay = (points) => {
	        const pts = Array.isArray(points) ? points : [];
	        if (pts.length < 2) return null;
	        const poly = new fabric.Polyline(pts, {
	          fill: 'transparent',
	          stroke: 'rgba(250,204,21,0.95)',
	          strokeWidth: 4,
	          strokeDashArray: [10, 8],
	          selectable: false,
	          evented: false,
	          excludeFromExport: true,
	          objectCaching: false,
	          data: { base: true, kind: 'anim-path-preview' },
	        });
	        try { poly.strokeUniform = true; } catch (e) { /* ignore */ }
	        return poly;
	      };
	      const samplePolyline = (pts, sampleCount) => {
	        const points = (Array.isArray(pts) ? pts : []).map((p) => ({ x: Number(p?.x) || 0, y: Number(p?.y) || 0 }));
	        if (points.length <= 2) return points;
	        const n = clamp(Number(sampleCount) || 8, 3, 18);
	        const segs = [];
	        let total = 0;
	        for (let i = 0; i < points.length - 1; i += 1) {
	          const len = dist(points[i], points[i + 1]);
	          segs.push(len);
	          total += len;
	        }
	        if (total <= 0.001) return [points[0], points[points.length - 1]];
	        const out = [points[0]];
	        for (let s = 1; s < n - 1; s += 1) {
	          const target = (total * s) / (n - 1);
	          let acc = 0;
	          let idx = 0;
	          while (idx < segs.length && acc + segs[idx] < target) {
	            acc += segs[idx];
	            idx += 1;
	          }
	          const a = points[idx] || points[0];
	          const b = points[idx + 1] || points[points.length - 1];
	          const span = Math.max(1e-6, segs[idx] || 1);
	          const t = clamp((target - acc) / span, 0, 1);
	          out.push({ x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t) });
	        }
	        out.push(points[points.length - 1]);
	        return out;
	      };
	      const applyAnimPathToSelectedToken = (points) => {
	        if (!points || points.length < 2) return false;
	        if (!isSimulating) simulationProEnabled = true;
	        try { ensureLayerUidsOnCanvas(); } catch (e) { /* ignore */ }
	        const active = canvas.getActiveObject();
	        const uid = safeText(active?.data?.layer_uid) || safeText(animPathTargetUid);
	        if (!uid) return false;
	        const startMs = clamp(Number(simulationProTimeMs) || 0, 0, 3_600_000);
	        const durationMs = 2800;
	        const sampled = samplePolyline(points, 10);
	        const base = animPathTargetSnapshot || {
	          angle: Number(active?.angle) || 0,
	          scaleX: Number(active?.scaleX) || 1,
	          scaleY: Number(active?.scaleY) || 1,
	          opacity: active?.opacity == null ? 1 : Number(active?.opacity),
	        };
	        const kfs = sampled.map((p, idx) => {
	          const t = sampled.length <= 1 ? 0 : idx / (sampled.length - 1);
	          return {
	            t_ms: Math.round(startMs + (t * durationMs)),
	            easing: 'linear',
	            props: {
	              left: Number(p.x) || 0,
	              top: Number(p.y) || 0,
	              angle: Number(base.angle) || 0,
	              scaleX: clampScale(Number(base.scaleX) || 1),
	              scaleY: clampScale(Number(base.scaleY) || 1),
	              opacity: base.opacity == null ? 1 : Number(base.opacity),
	            },
	          };
	        });
	        simulationProTracks = simulationProTracks || {};
	        const existing = Array.isArray(simulationProTracks[uid]) ? simulationProTracks[uid] : [];
	        const endMs = startMs + durationMs;
	        const kept = existing.filter((kf) => {
	          const t = Number(kf?.t_ms) || 0;
	          return t < startMs || t > endMs;
	        });
	        const merged = kept.concat(kfs).sort((a, b) => (Number(a?.t_ms) || 0) - (Number(b?.t_ms) || 0)).slice(0, 120);
	        simulationProTracks[uid] = merged;
	        simulationProUpdatedAt = Date.now();
	        simulationProCaches = new Map();
	        try { persistSimulationProToStorage(); } catch (e) { /* ignore */ }
	        try { renderSimulationAtTimeMs(startMs); } catch (e) { /* ignore */ }
	        try { syncSimProUi(); } catch (e) { /* ignore */ }
	        return true;
	      };

	      upper?.addEventListener('pointerdown', (ev) => {
	        if (!ev) return;
	        if (penOnlyDraw && freeDrawMode && isTouch(ev)) {
	          stopEv(ev);
	          return;
	        }
	        if (!animPathMode) return;
	        if (!isPen(ev) && safeText(ev?.pointerType) !== 'mouse') return;
	        const active = canvas.getActiveObject();
	        if (!active || active?.data?.base || isBackgroundShape(active)) {
	          setStatus('Selecciona una ficha para dibujar su ruta animada.', true);
	          stopEv(ev);
	          return;
	        }
	        animPathCapturing = true;
	        animPathPointerId = ev.pointerId;
	        animPathTargetUid = safeText(active?.data?.layer_uid);
	        animPathTargetSnapshot = {
	          angle: Number(active?.angle) || 0,
	          scaleX: Number(active?.scaleX) || 1,
	          scaleY: Number(active?.scaleY) || 1,
	          opacity: active?.opacity == null ? 1 : Number(active?.opacity),
	        };
	        animPathPoints = [];
	        clearAnimPathOverlay();
	        const raw = canvas.getPointer(ev);
	        const p = { x: Number(raw?.x) || 0, y: Number(raw?.y) || 0 };
	        animPathPoints.push(p);
	        animPathOverlay = buildAnimPathOverlay(animPathPoints);
	        if (animPathOverlay) {
	          canvas.add(animPathOverlay);
	          try { canvas.bringToFront(animPathOverlay); } catch (e) { /* ignore */ }
	          try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        }
	        stopEv(ev);
	      }, { capture: true, passive: false });

	      upper?.addEventListener('pointermove', (ev) => {
	        if (!animPathCapturing) return;
	        if (animPathPointerId != null && ev.pointerId !== animPathPointerId) return;
	        const raw = canvas.getPointer(ev);
	        const p = { x: Number(raw?.x) || 0, y: Number(raw?.y) || 0 };
	        const last = animPathPoints[animPathPoints.length - 1];
	        if (last && dist(last, p) < 9) {
	          stopEv(ev);
	          return;
	        }
	        animPathPoints.push(p);
	        if (animPathOverlay) {
	          try { animPathOverlay.set({ points: animPathPoints }); } catch (e) { /* ignore */ }
	          try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        }
	        stopEv(ev);
	      }, { capture: true, passive: false });

	      const endAnim = (ev) => {
	        if (!animPathCapturing) return;
	        if (animPathPointerId != null && ev && ev.pointerId !== animPathPointerId) return;
	        const ok = applyAnimPathToSelectedToken(animPathPoints);
	        animPathCapturing = false;
	        animPathPointerId = null;
	        animPathTargetUid = '';
	        animPathTargetSnapshot = null;
	        animPathPoints = [];
	        clearAnimPathOverlay();
	        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
	        setStatus(ok ? 'Ruta aplicada a Timeline Pro.' : 'No se pudo aplicar la ruta.', !ok);
	        if (ev) stopEv(ev);
	      };
	      upper?.addEventListener('pointerup', endAnim, { capture: true, passive: false });
	      upper?.addEventListener('pointercancel', endAnim, { capture: true, passive: false });
	      upper?.addEventListener('lostpointercapture', endAnim, { capture: true, passive: false });
	    } catch (e) {
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

		    // Imágenes por URL (mismo origen) para catálogos estáticos (PPT) u otros recursos internos.
		    const urlAssetImages = new Map();
		    const urlAssetLoading = new Set();
		    const urlAssetPendingRefresh = new Set();
		    const normalizeUrlAsset = (value) => safeText(value || '');
		    const ensureUrlAssetLoaded = (url) => {
		      const key = normalizeUrlAsset(url);
		      if (!key || urlAssetImages.has(key) || urlAssetLoading.has(key)) return;
		      urlAssetLoading.add(key);
		      try {
		        const img = new Image();
		        try { img.crossOrigin = 'anonymous'; } catch (e) { /* ignore */ }
		        img.onload = () => {
		          urlAssetImages.set(key, img);
		          urlAssetLoading.delete(key);
		          urlAssetPendingRefresh.add(key);
		        };
		        img.onerror = () => {
		          urlAssetLoading.delete(key);
		        };
		        img.src = key;
		      } catch (error) {
		        urlAssetLoading.delete(key);
		      }
		    };
		    syncGridUi({ silent: true });

		    // Overlays tácticos (carriles/sectores, líneas de pase, superioridades) + snap.
		    const tacticalPrefsKey = 'tpad_tactical_overlays_v1';
		    const readTacticalPrefs = () => {
		      if (!canUseStorage) return {};
		      try { return JSON.parse(window.localStorage.getItem(tacticalPrefsKey) || '{}') || {}; } catch (e) { return {}; }
		    };
		    const writeTacticalPrefs = (prefs) => {
		      if (!canUseStorage) return;
		      try { window.localStorage.setItem(tacticalPrefsKey, JSON.stringify(prefs || {})); } catch (e) { /* ignore */ }
		    };
		    const initialTacticalPrefs = readTacticalPrefs();
		    let tacticalSnapEnabled = !!initialTacticalPrefs.snap;
		    let tacticalLanesVisible = !!initialTacticalPrefs.lanes;
		    let tacticalSectorsVisible = !!initialTacticalPrefs.sectors;
		    let tacticalPassLinesVisible = !!initialTacticalPrefs.pass_lines;
		    let tacticalSuperioritiesVisible = !!initialTacticalPrefs.superiorities;

		    let tacticalOverlayObjects = [];
		    let tacticalOverlayFrame = null;
		    let tacticalOverlayDirty = false;

		    const syncTacticalOverlaysUi = () => {
		      if (overlaySnapInput) overlaySnapInput.checked = !!tacticalSnapEnabled;
		      if (overlayLanesInput) overlayLanesInput.checked = !!tacticalLanesVisible;
		      if (overlaySectorsInput) overlaySectorsInput.checked = !!tacticalSectorsVisible;
		      if (overlayPassLinesInput) overlayPassLinesInput.checked = !!tacticalPassLinesVisible;
		      if (overlaySuperioritiesInput) overlaySuperioritiesInput.checked = !!tacticalSuperioritiesVisible;
		    };
		    const persistTacticalPrefs = () => {
		      writeTacticalPrefs({
		        snap: !!tacticalSnapEnabled,
		        lanes: !!tacticalLanesVisible,
		        sectors: !!tacticalSectorsVisible,
		        pass_lines: !!tacticalPassLinesVisible,
		        superiorities: !!tacticalSuperioritiesVisible,
		      });
		    };
		    // Sincroniza el UI inicial con las prefs persistidas.
		    try { syncTacticalOverlaysUi(); } catch (e) { /* ignore */ }

		    const clearTacticalOverlays = () => {
		      tacticalOverlayDirty = false;
		      if (!tacticalOverlayObjects.length) return;
		      const prevLoading = canvas.__loading;
		      canvas.__loading = true;
		      try {
		        tacticalOverlayObjects.forEach((obj) => {
		          try { if (obj) canvas.remove(obj); } catch (e) { /* ignore */ }
		        });
		      } catch (e) { /* ignore */ }
		      canvas.__loading = prevLoading;
		      tacticalOverlayObjects = [];
		    };

		    const makeOverlayLine = (points, opts = {}) => {
		      const line = new fabric.Line(points, {
		        stroke: opts.stroke || 'rgba(226,232,240,0.36)',
		        strokeWidth: opts.strokeWidth || 2,
		        strokeDashArray: opts.dash || undefined,
		        selectable: false,
		        evented: false,
		        excludeFromExport: true,
		        opacity: Number.isFinite(Number(opts.opacity)) ? Number(opts.opacity) : 1,
		      });
		      line.data = { base: true, kind: 'tactical-overlay', overlay: safeText(opts.overlay || '') };
		      try { line.strokeUniform = true; } catch (e) { /* ignore */ }
		      return line;
		    };

		    const collectTokensOnCanvas = () => {
		      const objects = canvas.getObjects?.() || [];
		      return objects
		        .filter((obj) => obj && obj.visible !== false && safeText(obj?.data?.kind) === 'token' && !(obj?.data?.base))
		        .slice(0, 60);
		    };

		    const isRivalToken = (token) => {
		      const tk = safeText(token?.data?.token_kind).toLowerCase();
		      return tk.includes('rival') || tk === 'player_rival';
		    };

		    const buildLaneSectorOverlays = () => {
		      const overlays = [];
		      const { w, h } = worldSize();
		      if (!w || !h) return overlays;
		      if (tacticalLanesVisible) {
		        // 5 carriles => 4 líneas horizontales (y).
		        for (let i = 1; i <= 4; i += 1) {
		          const y = (h * i) / 5;
		          overlays.push(makeOverlayLine([0, y, w, y], { overlay: 'lanes', dash: [10, 10], opacity: 0.75 }));
		        }
		      }
		      if (tacticalSectorsVisible) {
		        // 3 sectores => 2 líneas verticales (x).
		        for (let i = 1; i <= 2; i += 1) {
		          const x = (w * i) / 3;
		          overlays.push(makeOverlayLine([x, 0, x, h], { overlay: 'sectors', dash: [10, 10], opacity: 0.75 }));
		        }
		      }
		      return overlays;
		    };

		    const buildPassingLinesOverlays = () => {
		      if (!tacticalPassLinesVisible) return [];
		      const tokens = collectTokensOnCanvas();
		      const locals = tokens.filter((t) => !isRivalToken(t));
		      if (locals.length < 2) return [];
		      const overlays = [];
		      const used = new Set();
		      const centers = locals.map((t) => ({ t, c: t.getCenterPoint() }));
		      centers.forEach((a) => {
		        const neighbors = centers
		          .filter((b) => b !== a)
		          .map((b) => ({ b, d: Math.hypot((b.c.x - a.c.x), (b.c.y - a.c.y)) }))
		          .sort((x, y) => x.d - y.d)
		          .slice(0, 2);
		        neighbors.forEach(({ b, d }) => {
		          if (!Number.isFinite(d) || d < 18 || d > 340) return;
		          const ua = safeText(a.t?.data?.layer_uid) || safeText(a.t?.data?.playerId) || safeText(a.t?.data?.playerNumber);
		          const ub = safeText(b.t?.data?.layer_uid) || safeText(b.t?.data?.playerId) || safeText(b.t?.data?.playerNumber);
		          const key = [ua || String(a.c.x), ub || String(b.c.x)].sort().join('::');
		          if (used.has(key)) return;
		          used.add(key);
		          overlays.push(makeOverlayLine([a.c.x, a.c.y, b.c.x, b.c.y], { overlay: 'pass', stroke: 'rgba(34,211,238,0.65)', strokeWidth: 3, opacity: 0.95 }));
		        });
		      });
		      return overlays.slice(0, 80);
		    };

		    const buildSuperioritiesOverlays = () => {
		      if (!tacticalSuperioritiesVisible) return [];
		      const tokens = collectTokensOnCanvas();
		      if (!tokens.length) return [];
		      const overlays = [];
		      const { w, h } = worldSize();
		      if (!w || !h) return overlays;
		      const sectorXs = [0, w / 3, (2 * w) / 3, w];
		      const laneYs = [0, h / 5, (2 * h) / 5, (3 * h) / 5, (4 * h) / 5, h];

		      const counts = Array.from({ length: 3 }, () => Array.from({ length: 5 }, () => ({ l: 0, r: 0 })));
		      tokens.forEach((t) => {
		        const c = t.getCenterPoint();
		        const sx = clamp(Math.floor((c.x / w) * 3), 0, 2);
		        const ly = clamp(Math.floor((c.y / h) * 5), 0, 4);
		        if (isRivalToken(t)) counts[sx][ly].r += 1;
		        else counts[sx][ly].l += 1;
		      });

		      const buildBadge = (x, y, text, color, opacity) => {
		        const rect = new fabric.Rect({
		          left: x,
		          top: y,
		          originX: 'center',
		          originY: 'center',
		          width: 72,
		          height: 26,
		          rx: 10,
		          ry: 10,
		          fill: color,
		          opacity,
		          selectable: false,
		          evented: false,
		          excludeFromExport: true,
		        });
		        rect.data = { base: true, kind: 'tactical-overlay', overlay: 'badge' };
		        const label = new fabric.Text(text, {
		          left: x,
		          top: y,
		          originX: 'center',
		          originY: 'center',
		          fontSize: 12,
		          fontWeight: '800',
		          fill: '#0f172a',
		          selectable: false,
		          evented: false,
		          excludeFromExport: true,
		        });
		        label.data = { base: true, kind: 'tactical-overlay', overlay: 'badge-text' };
		        const group = new fabric.Group([rect, label], {
		          left: x,
		          top: y,
		          originX: 'center',
		          originY: 'center',
		          selectable: false,
		          evented: false,
		          excludeFromExport: true,
		        });
		        group.data = { base: true, kind: 'tactical-overlay', overlay: 'badge-group' };
		        try { group.objectCaching = false; } catch (e) { /* ignore */ }
		        return group;
		      };

		      for (let sx = 0; sx < 3; sx += 1) {
		        for (let ly = 0; ly < 5; ly += 1) {
		          const cell = counts[sx][ly];
		          const total = (cell.l || 0) + (cell.r || 0);
		          if (!total) continue;
		          const diff = (cell.l || 0) - (cell.r || 0);
		          const txt = diff === 0 ? `${cell.l}-${cell.r}` : `${diff > 0 ? '+' : ''}${diff}`;
		          const fill = diff > 0 ? 'rgba(34,197,94,0.90)' : (diff < 0 ? 'rgba(239,68,68,0.90)' : 'rgba(226,232,240,0.85)');
		          const cx = (sectorXs[sx] + sectorXs[sx + 1]) / 2;
		          const cy = (laneYs[ly] + laneYs[ly + 1]) / 2;
		          overlays.push(buildBadge(cx, cy, txt, fill, 0.92));
		        }
		      }
		      return overlays.slice(0, 30);
		    };

		    const renderTacticalOverlays = () => {
		      clearTacticalOverlays();
		      if (!(tacticalLanesVisible || tacticalSectorsVisible || tacticalPassLinesVisible || tacticalSuperioritiesVisible)) {
		        canvas.requestRenderAll();
		        return;
		      }
		      const overlays = [
		        ...buildLaneSectorOverlays(),
		        ...buildPassingLinesOverlays(),
		        ...buildSuperioritiesOverlays(),
		      ];
		      if (!overlays.length) return;
		      const prevLoading = canvas.__loading;
		      canvas.__loading = true;
		      overlays.forEach((obj) => {
		        try { canvas.add(obj); } catch (e) { /* ignore */ }
		        tacticalOverlayObjects.push(obj);
		      });
		      canvas.__loading = prevLoading;
		      // Envía líneas al fondo para no tapar chapas.
		      try {
		        tacticalOverlayObjects.forEach((obj) => {
		          if (!obj) return;
		          const overlay = safeText(obj?.data?.overlay);
		          if (overlay === 'lanes' || overlay === 'sectors') {
		            try { canvas.sendToBack(obj); } catch (e) { /* ignore */ }
		          }
		        });
		      } catch (e) { /* ignore */ }
		      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
		    };

		    const scheduleTacticalOverlayRefresh = () => {
		      if (!(tacticalPassLinesVisible || tacticalSuperioritiesVisible || tacticalLanesVisible || tacticalSectorsVisible)) return;
		      tacticalOverlayDirty = true;
		      if (tacticalOverlayFrame) return;
		      tacticalOverlayFrame = window.requestAnimationFrame(() => {
		        tacticalOverlayFrame = null;
		        if (!tacticalOverlayDirty) return;
		        tacticalOverlayDirty = false;
		        try { renderTacticalOverlays(); } catch (e) { /* ignore */ }
		      });
		    };

		    const snapPointToLanesSectors = (point) => {
		      const { w, h } = worldSize();
		      if (!w || !h) return { x: point.x, y: point.y, snappedX: false, snappedY: false };
		      const tolerance = 26;
		      const baseX = Number(point?.x) || 0;
		      const baseY = Number(point?.y) || 0;
		      const laneCenters = [0, 1, 2, 3, 4].map((i) => ((i + 0.5) * h) / 5);
		      const sectorCenters = [0, 1, 2].map((i) => ((i + 0.5) * w) / 3);
		      let bestY = baseY;
		      let bestDy = tolerance + 1;
		      laneCenters.forEach((y) => {
		        const dy = Math.abs(y - baseY);
		        if (dy < bestDy) {
		          bestDy = dy;
		          bestY = y;
		        }
		      });
		      let bestX = baseX;
		      let bestDx = tolerance + 1;
		      sectorCenters.forEach((x) => {
		        const dx = Math.abs(x - baseX);
		        if (dx < bestDx) {
		          bestDx = dx;
		          bestX = x;
		        }
		      });
		      const snappedY = bestDy <= tolerance;
		      const snappedX = bestDx <= tolerance;
		      const outX = snappedX ? bestX : baseX;
		      const outY = snappedY ? bestY : baseY;
		      return { x: clamp(outX, 0, w), y: clamp(outY, 0, h), snappedX, snappedY };
		    };

			    let history = [];
		      let historyIndex = -1;
					    let pendingFactory = null;
					    let pendingKind = '';
					    let isSimulating = false;
					    let simulationBaselineSnapshot = null;
						    let simulationSteps = [];
						    let simulationActiveIndex = -1;
					    let simulationPlaying = false;
						    let simulationPlayTimer = null;
						    let simulationAnimToken = 0;
					    let simulationAnimFrame = null;
					    let simulationAutoCapture = false;
					    let simulationSpeed = 1.0;
					    let simulationLastAutoCaptureAt = 0;
					    let simulationMagnets = true;
					    let simulationGuides = true;
					    let simulationCollision = false;
						    let simulationTrajectories = true;
						    let simulationProEnabled = false;
						    let simulationProPlaying = false;
						    let simulationProAnimFrame = null;
						    let simulationProTimeMs = 0;
						    let simulationProLoop = true;
						    let simulationProTracks = {};
						    let simulationProUpdatedAt = 0;
						    let simulationProCaches = new Map(); // stepIndex -> { startMs, endMs, startMap, endMap }
						    // Persistencia (fase 9): guardamos los pasos del simulador junto a la tarea
						    // sin mezclarlos con el historial/undo del editor.
						    let simulationSavedSteps = [];
						    let simulationSavedUpdatedAt = 0;
						    let simGuideX = null;
						    let simGuideY = null;
						    let simMoveOverlays = [];
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
			    const GRASS_STYLE_LABEL = {
			      classic: 'Clásico',
			      realistic: 'Realista',
			    };
			    let pitchGrassStyle = safeText(grassStyleInput?.value, 'classic').toLowerCase();
			    if (!['classic', 'realistic'].includes(pitchGrassStyle)) pitchGrassStyle = 'classic';
			    const syncGrassUi = () => {
			      if (grassStyleInput) grassStyleInput.value = pitchGrassStyle;
			      if (grassLabel) grassLabel.textContent = GRASS_STYLE_LABEL[pitchGrassStyle] || 'Clásico';
			    };
			    syncGrassUi();
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
		    let freeDrawMode = false;
		    // Apple Pencil “Pro”: solo pen dibuja (palma/finger no pintan).
		    let pencilProMode = false;
		    let penOnlyDraw = false;
		    // Ruta dibujada → animación (Timeline Pro).
		    let animPathMode = false;
		    // Smart ink: convierte trazos a recursos limpios.
		    let smartInkMode = 'off'; // off | arrow | shapes
		    const setSmartInkMode = (mode) => {
		      const next = safeText(mode, 'off').toLowerCase();
		      smartInkMode = (next === 'arrow' || next === 'shapes') ? next : 'off';
		      try {
		        Array.from(document.querySelectorAll('button[data-action="smart_arrow"]')).forEach((btn) => {
		          btn.classList.toggle('is-active', smartInkMode === 'arrow');
		          try { btn.setAttribute('aria-pressed', smartInkMode === 'arrow' ? 'true' : 'false'); } catch (e) { /* ignore */ }
		        });
		      } catch (e) { /* ignore */ }
		      try {
		        Array.from(document.querySelectorAll('button[data-action="smart_shapes"]')).forEach((btn) => {
		          btn.classList.toggle('is-active', smartInkMode === 'shapes');
		          try { btn.setAttribute('aria-pressed', smartInkMode === 'shapes' ? 'true' : 'false'); } catch (e) { /* ignore */ }
		        });
		      } catch (e) { /* ignore */ }
		    };
		    let animPathCapturing = false;
		    let animPathPointerId = null;
		    let animPathPoints = [];
		    let animPathOverlay = null;
		    let animPathTargetUid = '';
		    let animPathTargetSnapshot = null;
	    const useViewportMapping = (() => {
	      const flag = safeText(urlParams?.get('tpad_vpt'));
	      if (flag === '0') return false;
	      return true;
	    })();

	    let worldWidth = parseIntSafe(widthInput?.value) || 0;
	    let worldHeight = parseIntSafe(heightInput?.value) || 0;

	    if (!Number.isFinite(pitchZoom)) pitchZoom = 1.0;
	    pitchZoom = clamp(pitchZoom, 0.8, 1.6);

		    const clampScale = (value, maxScale = 2.6) => clamp(Number(value) || 1, 0.4, Number(maxScale) || 2.6);
		    const isLongStrokeObject = (obj) => {
		      const kind = safeText(obj?.data?.kind).toLowerCase();
		      if (!kind) return false;
		      return kind === 'line'
		        || kind.startsWith('line-')
		        || kind.startsWith('line_')
		        || kind === 'arrow'
		        || kind.startsWith('arrow-')
		        || kind.startsWith('arrow_');
		    };
		    const maxScaleForObject = (obj) => (isLongStrokeObject(obj) ? 12.0 : 2.6);
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
		      // Compat: el selector de color "único" sigue asignando `data.color`.
		      // Para fichas a rayas, este color representa el color de la franja principal.
		      setObjectData(group, { color: colorHex, token_stripe_color: colorHex });
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

	    const walkTokenObjects = (group, fn) => {
	      const walk = (node) => {
	        if (!node) return;
	        try { fn(node); } catch (e) { /* ignore */ }
	        if (Array.isArray(node?._objects)) node._objects.forEach((child) => walk(child));
	      };
	      walk(group);
	    };

	    const tokenHasStripeRoles = (group) => {
	      let found = false;
	      walkTokenObjects(group, (child) => {
	        if (found) return;
	        const role = safeText(child?.data?.role);
	        if (role === 'token_stripe' || role === 'token_stripe_base' || role === 'token_stripes') found = true;
	      });
	      return found;
	    };

	    const applyTokenPalette = (group, options = {}) => {
	      if (!group) return false;
	      const kind = safeText(group?.data?.kind);
	      if (kind !== 'token') return false;

	      const tokenKind = safeText(group?.data?.token_kind);
	      const baseHex = parseColorToHex(options.base, parseColorToHex(group?.data?.token_base_color, '#ffffff')) || '#ffffff';
	      const stripeHex = parseColorToHex(options.stripe, parseColorToHex(group?.data?.token_stripe_color, baseHex)) || baseHex;
	      const pattern = normalizeTokenPattern(options.pattern || group?.data?.token_pattern);

	      setObjectData(group, { token_base_color: baseHex, token_stripe_color: stripeHex, token_pattern: pattern });

	      // Tokens sin franjas: la base es el color del disco/camiseta.
	      if (!tokenHasStripeRoles(group) || tokenKind === 'player_away' || tokenKind === 'player_rival') {
	        applyTokenColor(group, baseHex);
	        setObjectData(group, { token_base_color: baseHex });
	        return true;
	      }

	      const stripeNodes = [];
	      const baseStripeNodes = [];
	      const baseNodes = [];
	      walkTokenObjects(group, (child) => {
	        if (!child) return;
	        const role = safeText(child?.data?.role);
	        if (role === 'token_base' || role === 'token_fill') baseNodes.push(child);
	        if (role === 'token_stripe') stripeNodes.push(child);
	        if (role === 'token_stripe_base') baseStripeNodes.push(child);
	        // Compat: stripes "blancas" antiguas sin role.
	        if (!role && child.type === 'rect') {
	          const current = parseColorToHex(child.fill, '');
	          if (current === '#f8fafc' || current === '#ffffff') baseStripeNodes.push(child);
	        }
	      });

	      const effectiveBase = pattern === 'solid' ? stripeHex : baseHex;
	      baseNodes.forEach((node) => { try { node.set({ fill: effectiveBase }); } catch (e) { /* ignore */ } });
	      stripeNodes.forEach((node) => { try { node.set({ fill: stripeHex }); } catch (e) { /* ignore */ } });
	      baseStripeNodes.forEach((node) => { try { node.set({ fill: effectiveBase }); } catch (e) { /* ignore */ } });

	      group.dirty = true;
	      return true;
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
		        try {
		          if (scaleXInput) scaleXInput.max = '260';
		          if (scaleYInput) scaleYInput.max = '260';
		        } catch (e) { /* ignore */ }
		        scaleXInput.value = '100';
		        scaleYInput.value = '100';
	        rotationInput.value = '0';
	        colorInput.value = '#22d3ee';
		        if (strokeWidthRow) strokeWidthRow.hidden = true;
		        if (strokePresetsRow) strokePresetsRow.hidden = true;
		        if (strokeWidthInput) strokeWidthInput.value = '3';
		        if (tokenStyleActions) tokenStyleActions.hidden = true;
		        if (tokenColorGrid) tokenColorGrid.hidden = true;
		        if (tokenPatternActions) tokenPatternActions.hidden = true;
		        return;
		      }
	      selectionToolbar.hidden = false;
	      const canColor = isColorizableObject(active);
	      selectionToolbar.querySelectorAll('input,button').forEach((node) => { node.disabled = false; });
	      colorInput.disabled = !canColor;
	      selectionToolbar.querySelectorAll('button[data-color]').forEach((node) => { node.disabled = !canColor; });
	      selectionSummary.textContent = `Ajustando ${objectLabel(active)} seleccionado.`;
	      try {
	        const longStroke = isLongStrokeObject(active);
	        if (scaleXInput) scaleXInput.max = longStroke ? '1200' : '260';
	        if (scaleYInput) scaleYInput.max = longStroke ? '520' : '260';
	      } catch (e) { /* ignore */ }
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
		      if (tokenStyleActions) tokenStyleActions.hidden = !isToken;
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

		    const resolvePlayerForToken = (tokenGroup) => {
		      const playerId = safeText(tokenGroup?.data?.playerId);
		      if (playerId) {
		        const found = players.find((item) => String(item.id) === String(playerId));
		        if (found) return found;
		      }
		      return {
		        id: playerId,
		        name: safeText(tokenGroup?.data?.playerName) || safeText(tokenGroup?.data?.name) || 'Jugador',
		        number: safeText(tokenGroup?.data?.playerNumber) || safeText(tokenGroup?.data?.number) || '',
		        position: '',
		        photo_url: safeText(tokenGroup?.data?.playerPhotoUrl) || safeText(tokenGroup?.data?.photo_url) || '',
		      };
		    };

		    const setActiveTokenStyle = (rawStyle) => {
		      const active = activeInspectableObject();
		      if (!active || !isTokenGroup(active)) return;
		      if (active?.data?.locked) {
		        setStatus('Elemento bloqueado. Usa “Desbloquear” para editarlo.', true);
		        return;
		      }
		      const nextStyle = normalizeTokenStyle(rawStyle);
		      const tokenKind = safeText(active?.data?.token_kind);
		      const center = active.getCenterPoint ? active.getCenterPoint() : { x: Number(active.left) || 0, y: Number(active.top) || 0 };
		      const player = resolvePlayerForToken(active);
		      const palette = {
		        base: safeText(active?.data?.token_base_color) || '#ffffff',
		        stripe: safeText(active?.data?.token_stripe_color) || safeText(active?.data?.color) || '#0f7a35',
		        pattern: safeText(active?.data?.token_pattern) || 'striped',
		        photoUrl: safeText(active?.data?.playerPhotoUrl) || safeText(player?.photo_url),
		      };
		      const factory = playerTokenFactory(tokenKind || 'player_local', player, { style: nextStyle, ...palette });
		      if (typeof factory !== 'function') return;
		      const fresh = factory(center.x, center.y);
		      if (!fresh) return;

		      const prevData = active.data || {};
		      const objects = canvas.getObjects() || [];
		      const index = objects.indexOf(active);
		      canvas.remove(active);
		      canvas.insertAt(fresh, index >= 0 ? index : objects.length, false);
		      fresh.set({
		        angle: Number(active.angle) || 0,
		        scaleX: clampScale(Number(active.scaleX) || 1),
		        scaleY: clampScale(Number(active.scaleY) || 1),
		        opacity: active.opacity == null ? 1 : active.opacity,
		      });
		      fresh.data = { ...(fresh.data || {}), layer_uid: safeText(prevData.layer_uid), locked: prevData.locked, token_size: safeText(prevData.token_size, 'm') };
		      // Respeta nombre/dorsal editados manualmente.
		      updateTokenAppearance(fresh, { name: safeText(prevData.playerName), number: safeText(prevData.playerNumber) });
		      applyTokenPalette(fresh, palette);
		      canvas.setActiveObject(fresh);
		      commitObjectChange(`Token: ${nextStyle === 'disk' ? 'chapa' : (nextStyle === 'jersey' ? 'camiseta' : 'foto')}.`);
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

			    const setFormationPopoverOpen = (open) => {
			      if (!formationPopover) return;
			      formationPopover.hidden = !open;
			    };
			    const closeFormationPopover = () => setFormationPopoverOpen(false);

			    const setOverlaysPopoverOpen = (open) => {
			      if (!overlaysPopover) return;
			      overlaysPopover.hidden = !open;
			    };
			    const closeOverlaysPopover = () => setOverlaysPopoverOpen(false);

			    const FORMATION_PRESETS = {
			      f11: [
			        '4-3-3',
			        '4-2-3-1',
			        '4-4-2',
			        '3-4-3',
			        '3-5-2',
			        '5-3-2',
			      ],
			      f7: [
			        '2-3-1',
			        '3-2-1',
			        '2-2-2',
			        '1-3-2',
			      ],
			      futsal: [
			        '1-2-1',
			        '2-1-1',
			        '1-1-2',
			      ],
			    };

			    const fillSelectOptions = (selectEl, values, selected) => {
			      if (!selectEl) return;
			      const wanted = safeText(selected);
			      const list = Array.isArray(values) ? values : [];
			      selectEl.innerHTML = list.map((v) => {
			        const sel = wanted ? (safeText(v) === wanted) : false;
			        return `<option value="${safeText(v)}"${sel ? ' selected' : ''}>${safeText(v)}</option>`;
			      }).join('');
			      if (!wanted && list.length) {
			        try { selectEl.value = safeText(list[0]); } catch (e) { /* ignore */ }
			      }
			    };

			    const syncFormationShapeOptions = () => {
			      const format = safeText(formationFormatSelect?.value, 'f11');
			      const shapes = FORMATION_PRESETS[format] || FORMATION_PRESETS.f11;
			      fillSelectOptions(formationShapeSelect, shapes, safeText(formationShapeSelect?.value) || safeText(shapes[0]));
			    };

			    const parseFormationLineCounts = (shape) => safeText(shape)
			      .split('-')
			      .map((piece) => Number.parseInt(piece, 10))
			      .filter((n) => Number.isFinite(n) && n > 0)
			      .slice(0, 6);

			    const formationExpectedCount = (format, lineCounts) => {
			      const outfield = (Array.isArray(lineCounts) ? lineCounts : []).reduce((acc, n) => acc + (Number(n) || 0), 0);
			      const normalized = safeText(format, 'f11');
			      if (normalized === 'futsal') return 1 + outfield; // 5 (1 GK + 4)
			      return 1 + outfield; // f11/f7 igual: 1 GK + outfield
			    };

			    const evenRatios = (count, margin = 0.12) => {
			      const n = clamp(Number(count) || 0, 1, 20);
			      if (n === 1) return [0.5];
			      const top = clamp(Number(margin) || 0.12, 0.02, 0.22);
			      const bottom = 1 - top;
			      const step = (bottom - top) / Math.max(1, n - 1);
			      return Array.from({ length: n }, (_, i) => clamp(top + (step * i), 0.02, 0.98));
			    };

			    const formationLineXRatios = (format, lineCount) => {
			      const normalized = safeText(format, 'f11');
			      const n = clamp(Number(lineCount) || 3, 2, 5);
			      if (normalized === 'f7') {
			        if (n === 4) return [0.26, 0.46, 0.66, 0.84];
			        if (n === 2) return [0.34, 0.78];
			        return [0.30, 0.58, 0.82];
			      }
			      if (normalized === 'futsal') {
			        if (n === 2) return [0.40, 0.80];
			        return [0.36, 0.64, 0.84];
			      }
			      // f11
			      if (n === 4) return [0.22, 0.42, 0.62, 0.82];
			      if (n === 2) return [0.34, 0.78];
			      return [0.23, 0.50, 0.78];
			    };

			    const buildFormationTargets = (format, shape, direction) => {
			      const { w, h } = worldSize();
			      if (!w || !h) return [];
			      const normalizedFormat = safeText(format, 'f11');
			      const counts = parseFormationLineCounts(shape);
			      if (!counts.length) return [];
			      const lineXs = formationLineXRatios(normalizedFormat, counts.length);
			      const attackDir = safeText(direction, 'right') === 'left' ? 'left' : 'right';
			      const xFromOwn = (ratio) => {
			        const r = clamp(Number(ratio) || 0, 0.02, 0.98);
			        // "own" está en el lado opuesto a la dirección de ataque.
			        return attackDir === 'right' ? (w * r) : (w * (1 - r));
			      };
			      const yFromRatio = (ratio) => h * clamp(Number(ratio) || 0.5, 0.02, 0.98);

			      const targets = [];
			      // GK
			      targets.push({ role: 'gk', kind: 'goalkeeper_local', x: xFromOwn(0.08), y: yFromRatio(0.50) });
			      counts.forEach((playersInLine, idx) => {
			        const xRatio = lineXs[idx] || (0.22 + (idx * 0.18));
			        const margin = playersInLine >= 5 ? 0.08 : (playersInLine === 4 ? 0.10 : 0.12);
			        evenRatios(playersInLine, margin).forEach((yr) => {
			          targets.push({ role: 'field', kind: 'player_local', x: xFromOwn(xRatio), y: yFromRatio(yr) });
			        });
			      });
			      return targets;
			    };

			    const isLocalFormationToken = (obj) => {
			      if (!obj || safeText(obj?.data?.kind) !== 'token') return false;
			      if (obj?.data?.base) return false;
			      return !isRivalToken(obj);
			    };

			    const tokensForFormation = (onlySelected = false) => {
			      const selected = getSelectionObjects().filter(isLocalFormationToken);
			      if (onlySelected) return selected;
			      return (canvas.getObjects() || []).filter(isLocalFormationToken);
			    };

			    const applyFormationTargets = (targets, options = {}) => {
			      if (!Array.isArray(targets) || !targets.length) {
			        setStatus('Formación no válida.', true);
			        return;
			      }
			      if (isSimulating) {
			        setStatus('Modo simulación: sal para editar la formación.', true);
			        return;
			      }
			      const onlySelected = !!options.onlySelected;
			      const tokens = tokensForFormation(onlySelected).filter((t) => t && !t?.data?.locked);
			      const expected = targets.length;
			      if (onlySelected && !tokens.length) {
			        setStatus('Selecciona al menos una chapa para aplicar la formación.', true);
			        return;
			      }

			      const gkTokens = tokens.filter((t) => safeText(t?.data?.token_kind) === 'goalkeeper_local');
			      const fieldTokens = tokens.filter((t) => safeText(t?.data?.token_kind) !== 'goalkeeper_local');

			      const attackDir = safeText(formationDirectionSelect?.value, 'right') === 'left' ? 'left' : 'right';
			      const sortFactor = attackDir === 'right' ? 1 : -1;
			      fieldTokens.sort((a, b) => {
			        const ca = a.getCenterPoint();
			        const cb = b.getCenterPoint();
			        const dx = ((ca.x || 0) - (cb.x || 0)) * sortFactor;
			        if (Math.abs(dx) > 2) return dx;
			        return (ca.y || 0) - (cb.y || 0);
			      });

			      const arranged = [];
			      const created = [];

			      const needsGk = (!gkTokens.length && !onlySelected);
			      const expectedField = Math.max(0, expected - 1);
			      const needField = Math.max(0, expectedField - fieldTokens.length);
			      if (!onlySelected && needField > 0 && typeof playerTokenFactory === 'function') {
			        for (let i = 0; i < needField; i += 1) {
			          const factory = playerTokenFactory('player_local', null, { style: normalizeTokenStyle(tokenGlobalStyle) });
			          if (typeof factory !== 'function') break;
			          const seed = targets[Math.min(targets.length - 1, 1 + i)];
			          const fresh = factory(seed.x, seed.y);
			          if (!fresh) continue;
			          normalizeEditableObject(fresh);
			          canvas.add(fresh);
			          created.push(fresh);
			        }
			      }

			      // Recalcula listas con creados.
			      const allField = fieldTokens.concat(created);
			      const gk = gkTokens[0] || null;
			      const fieldIt = allField[Symbol.iterator]();

			      targets.forEach((target) => {
			        let token = null;
			        if (target.role === 'gk') {
			          token = gk;
			          if (!token && needsGk && typeof playerTokenFactory === 'function') {
			            const factory = playerTokenFactory('goalkeeper_local', null, { style: normalizeTokenStyle(tokenGlobalStyle) });
			            if (typeof factory === 'function') {
			              const fresh = factory(target.x, target.y);
			              if (fresh) {
			                normalizeEditableObject(fresh);
			                canvas.add(fresh);
			                token = fresh;
			                created.push(fresh);
			              }
			            }
			          }
			        } else {
			          const next = fieldIt.next();
			          token = next && !next.done ? next.value : null;
			        }
			        if (!token) return;
			        arranged.push(token);
			        try {
			          token.setPositionByOrigin(new fabric.Point(target.x, target.y), 'center', 'center');
			          token.setCoords();
			        } catch (e) { /* ignore */ }
			      });

			      if (!arranged.length) {
			        setStatus('No se pudo aplicar la formación.', true);
			        return;
			      }

			      canvas.discardActiveObject();
			      if (arranged.length === 1) canvas.setActiveObject(arranged[0]);
			      else canvas.setActiveObject(new fabric.ActiveSelection(arranged, { canvas }));
			      canvas.requestRenderAll();
			      try { persistActiveStepSnapshot(); } catch (e) { /* ignore */ }
			      pushHistory();
			      syncInspector();
			      renderLayers();
			      refreshLivePreview();
			      schedulePlayerBankUpdate();
			      scheduleDraftSave('formation');
			      scheduleTacticalOverlayRefresh();

			      const extras = Math.max(0, tokens.length - expected);
			      const createdCount = created.length;
			      setStatus(`Formación aplicada.${createdCount ? ` (+${createdCount} chapas)` : ''}${extras ? ` (sobran ${extras})` : ''}`);
			    };
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
			      closeFormationPopover();
			      closeOverlaysPopover();
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

			    const openFormationPopover = () => {
			      setCommandMenuOpen(false);
			      closePatternPopover();
			      closeOverlaysPopover();
			      syncFormationShapeOptions();
			      setFormationPopoverOpen(true);
			      window.setTimeout(() => {
			        try { formationShapeSelect?.focus(); } catch (e) { /* ignore */ }
			      }, 0);
			    };

			    const openOverlaysPopover = () => {
			      setCommandMenuOpen(false);
			      closePatternPopover();
			      closeFormationPopover();
			      try { syncTacticalOverlaysUi(); } catch (e) { /* ignore */ }
			      setOverlaysPopoverOpen(true);
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
			      else if (command === 'formation') openFormationPopover();
			      else if (command === 'tactical_overlays') openOverlaysPopover();
			      else if (command === 'lane_snap_toggle') {
			        tacticalSnapEnabled = !tacticalSnapEnabled;
			        persistTacticalPrefs();
			        syncTacticalOverlaysUi();
			        setStatus(tacticalSnapEnabled ? 'Snap carriles/sectores activado (Shift lo desactiva temporalmente).' : 'Snap carriles/sectores desactivado.');
			      }
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

		    formationCloseBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      closeFormationPopover();
		    });
		    formationFormatSelect?.addEventListener('change', () => {
		      syncFormationShapeOptions();
		    });
		    formationApplyBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      const format = safeText(formationFormatSelect?.value, 'f11');
		      const shape = safeText(formationShapeSelect?.value, '');
		      const direction = safeText(formationDirectionSelect?.value, 'right');
		      const targets = buildFormationTargets(format, shape, direction);
		      closeFormationPopover();
		      applyFormationTargets(targets, { onlySelected: false });
		    });
		    formationApplySelectedBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      const format = safeText(formationFormatSelect?.value, 'f11');
		      const shape = safeText(formationShapeSelect?.value, '');
		      const direction = safeText(formationDirectionSelect?.value, 'right');
		      const targets = buildFormationTargets(format, shape, direction);
		      closeFormationPopover();
		      applyFormationTargets(targets, { onlySelected: true });
		    });
		    formationPopover?.addEventListener('keydown', (event) => {
		      const key = String(event.key || '').toLowerCase();
		      if (key === 'escape') {
		        event.preventDefault();
		        closeFormationPopover();
		        return;
		      }
		      if (key === 'enter') {
		        event.preventDefault();
		        try { formationApplyBtn?.click(); } catch (e) { /* ignore */ }
		      }
		    });

		    overlaysCloseBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      closeOverlaysPopover();
		    });
		    overlaysApplyBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      tacticalSnapEnabled = !!overlaySnapInput?.checked;
		      tacticalLanesVisible = !!overlayLanesInput?.checked;
		      tacticalSectorsVisible = !!overlaySectorsInput?.checked;
		      tacticalPassLinesVisible = !!overlayPassLinesInput?.checked;
		      tacticalSuperioritiesVisible = !!overlaySuperioritiesInput?.checked;
		      persistTacticalPrefs();
		      syncTacticalOverlaysUi();
		      closeOverlaysPopover();
		      renderTacticalOverlays();
		      setStatus('Overlays actualizados.');
		    });
		    const OVERLAY_PRESETS = {
		      clean: { snap: false, lanes: false, sectors: false, passlines: false, superiorities: false },
		      grid: { snap: true, lanes: true, sectors: true, passlines: false, superiorities: false },
		      analysis: { snap: false, lanes: false, sectors: false, passlines: true, superiorities: true },
		      full: { snap: true, lanes: true, sectors: true, passlines: true, superiorities: true },
		    };
		    overlaysPresetSelect?.addEventListener('change', () => {
		      const key = safeText(overlaysPresetSelect.value, 'custom');
		      if (key === 'custom') return;
		      const preset = OVERLAY_PRESETS[key];
		      if (!preset) return;
		      if (overlaySnapInput) overlaySnapInput.checked = !!preset.snap;
		      if (overlayLanesInput) overlayLanesInput.checked = !!preset.lanes;
		      if (overlaySectorsInput) overlaySectorsInput.checked = !!preset.sectors;
		      if (overlayPassLinesInput) overlayPassLinesInput.checked = !!preset.passlines;
		      if (overlaySuperioritiesInput) overlaySuperioritiesInput.checked = !!preset.superiorities;
		      try { overlaysApplyBtn?.click?.(); } catch (e) { /* ignore */ }
		      setStatus('Preset aplicado.');
		    });
		    overlaysPopover?.addEventListener('keydown', (event) => {
		      const key = String(event.key || '').toLowerCase();
		      if (key === 'escape') {
		        event.preventDefault();
		        closeOverlaysPopover();
		        return;
		      }
		      if (key === 'enter') {
		        event.preventDefault();
		        try { overlaysApplyBtn?.click(); } catch (e) { /* ignore */ }
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
					      if (simCaptureBtn) simCaptureBtn.hidden = !isSimulating;
					      if (simPlayBtn) simPlayBtn.hidden = !isSimulating;
					      if (simRemoveBtn) simRemoveBtn.hidden = !isSimulating;
					      if (simStepsList) simStepsList.hidden = !isSimulating;
						      if (simPrevBtn) simPrevBtn.hidden = !isSimulating;
						      if (simNextBtn) simNextBtn.hidden = !isSimulating;
					      if (simDuplicateBtn) simDuplicateBtn.hidden = !isSimulating;
					      if (simToScenariosBtn) simToScenariosBtn.hidden = !isSimulating;
					      if (simShareBtn) simShareBtn.hidden = !isSimulating;
						      if (simExportStepBtn) simExportStepBtn.hidden = !isSimulating;
						      if (simExportAllBtn) simExportAllBtn.hidden = !isSimulating;
						      if (simRecordBtn) simRecordBtn.hidden = !isSimulating;
						      if (simView3dBtn) simView3dBtn.hidden = !isSimulating;
						      if (simVideoStudioBtn) simVideoStudioBtn.hidden = !isSimulating;
							      if (simClipSaveBtn) simClipSaveBtn.hidden = !isSimulating;
							      if (simClipImportBtn) simClipImportBtn.hidden = !isSimulating;
							      if (simVideoImportBtn) simVideoImportBtn.hidden = !isSimulating;
							      if (simClipDestWrap) simClipDestWrap.hidden = !isSimulating;
						      if (simPackBtn) simPackBtn.hidden = !isSimulating;
						      if (simClipsList) simClipsList.hidden = !isSimulating;
						      if (simMetaPanel) simMetaPanel.hidden = !isSimulating;
						      if (simRoutesPanel) simRoutesPanel.hidden = !isSimulating;
						      if (simAutoCaptureInput) simAutoCaptureInput.checked = !!simulationAutoCapture;
						      if (simProEnabledInput) simProEnabledInput.checked = !!simulationProEnabled;
						      if (simProPanel) simProPanel.hidden = !isSimulating || !simulationProEnabled;
						      if (simTrajectoriesInput) simTrajectoriesInput.checked = !!simulationTrajectories;
					      if (simMagnetsInput) simMagnetsInput.checked = !!simulationMagnets;
					      if (simGuidesInput) simGuidesInput.checked = !!simulationGuides;
					      if (simCollisionInput) simCollisionInput.checked = !!simulationCollision;
						      if (simSpeedSelect) simSpeedSelect.value = String(simulationSpeed);
						      if (simPlayBtn) simPlayBtn.textContent = (simulationProEnabled ? simulationProPlaying : simulationPlaying) ? 'Parar' : 'Reproducir';
						      if (simRecordBtn) simRecordBtn.disabled = !canRecord2d();
					    };

					    // Video Studio (telestración): carga un vídeo y dibuja encima con keyframes.
					    const canRecordVideoStudio = () => {
					      try {
					        if (typeof window.MediaRecorder === 'undefined') return false;
					        if (typeof HTMLCanvasElement === 'undefined') return false;
					        const probe = document.createElement('canvas');
					        return typeof probe.captureStream === 'function';
					      } catch (e) {
					        return false;
					      }
					    };

					    const formatClock = (seconds) => {
					      const s = Math.max(0, Number(seconds) || 0);
					      const mm = Math.floor(s / 60);
					      const ss = Math.floor(s % 60);
					      return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
					    };

					    const videoStudioStorageKey = (() => {
					      const base = safeText(draftKey) || safeText(draftNewKey) || 'webstats:tpad:draft:unknown';
					      return `${base}:video_studio_v1`;
					    })();

					    let videoStudioUrl = '';
					    let videoStudioCanvas = null;
					    let videoStudioTool = 'pen';
						    let videoStudioHistory = [];
						    let videoStudioHistoryIndex = -1;
						    let videoStudioKeyframes = [];
						    let videoStudioActiveKeyframe = -1;
						    let videoStudioMasterJson = null;
						    let videoStudioLayers = [];
						    let videoStudioActiveLayerId = '';
						    let videoStudioCalloutSeq = 1;
						    let videoStudioProEnabled = true;
						    let videoStudioShowHandles = false;
						    let videoStudioExporting = false;
						    let videoStudioExportFrame = null;
						    let videoStudioHandlersInstalled = false;
						    let videoStudioToolsInstalled = false;
						    let videoStudioMasterLoaded = false;
						    let videoStudioSaveTimer = null;

						    const readVideoStudioState = () => {
						      if (!canUseStorage) return;
						      try {
						        const raw = safeText(window.localStorage.getItem(videoStudioStorageKey));
						        const parsed = raw ? JSON.parse(raw) : null;
						        const keyframes = Array.isArray(parsed?.keyframes) ? parsed.keyframes : [];
						        const layersRaw = Array.isArray(parsed?.layers) ? parsed.layers : [];
						        const masterRaw = (parsed?.master_json && typeof parsed.master_json === 'object') ? parsed.master_json : null;
						        const calloutSeq = Number(parsed?.callout_seq);
						        const proEnabled = parsed?.pro_enabled;
						        const showHandles = parsed?.show_handles;
						        videoStudioKeyframes = keyframes
						          .map((kf) => ({
						            id: safeText(kf?.id) || `kf_${Date.now()}_${Math.random().toString(16).slice(2)}`,
						            t: Math.max(0, Number(kf?.t) || 0),
						            title: safeText(kf?.title),
						            json: (kf?.json && typeof kf.json === 'object') ? kf.json : null,
						          }))
						          .filter((kf) => !!kf.json)
						          .sort((a, b) => (a.t - b.t))
						          .slice(0, 220);
						        videoStudioMasterJson = masterRaw;
						        videoStudioLayers = layersRaw
						          .map((layer) => {
						            const type = safeText(layer?.type, 'draw');
						            const start = Math.max(0, Number(layer?.start) || 0);
						            const endRaw = Number(layer?.end);
						            const end = Number.isFinite(endRaw) ? Math.max(0, endRaw) : null;
						            const fadeIn = Math.max(0, Number(layer?.fade_in) || 0);
						            const fadeOut = Math.max(0, Number(layer?.fade_out) || 0);
						            const opacity = clamp(Number(layer?.opacity) || 1, 0, 1);
						            const strokeAnim = safeText(layer?.stroke_anim, 'none');
						            const params = (layer?.params && typeof layer.params === 'object') ? layer.params : {};
						            return {
						              id: safeText(layer?.id) || `ly_${Date.now()}_${Math.random().toString(16).slice(2)}`,
						              type,
						              name: safeText(layer?.name) || '',
						              enabled: layer?.enabled !== false,
						              start,
						              end,
						              fade_in: fadeIn,
						              fade_out: fadeOut,
						              opacity,
						              stroke_anim: strokeAnim,
						              params,
						              order: Number(layer?.order) || 0,
						            };
						          })
						          .slice(0, 120);
						        videoStudioLayers.sort((a, b) => ((a.order || 0) - (b.order || 0)) || (a.start - b.start));
						        if (Number.isFinite(calloutSeq) && calloutSeq >= 1) videoStudioCalloutSeq = clamp(calloutSeq, 1, 999);
						        if (typeof proEnabled === 'boolean') videoStudioProEnabled = proEnabled;
						        if (typeof showHandles === 'boolean') videoStudioShowHandles = showHandles;
						      } catch (e) { /* ignore */ }
						    };

						    const writeVideoStudioState = () => {
						      if (!canUseStorage) return;
						      try {
						        const payload = {
						          v: 1,
						          updated_at: new Date().toISOString(),
						          pro_enabled: !!videoStudioProEnabled,
						          show_handles: !!videoStudioShowHandles,
						          callout_seq: clamp(Number(videoStudioCalloutSeq) || 1, 1, 999),
						          master_json: videoStudioMasterJson,
						          layers: (videoStudioLayers || []).slice(0, 120),
						          keyframes: videoStudioKeyframes.slice(0, 220),
						        };
						        window.localStorage.setItem(videoStudioStorageKey, JSON.stringify(payload));
						      } catch (e) { /* ignore */ }
						    };

						    const scheduleVideoStudioSave = () => {
						      if (!canUseStorage) return;
						      if (videoStudioSaveTimer) {
						        try { window.clearTimeout(videoStudioSaveTimer); } catch (e) { /* ignore */ }
						        videoStudioSaveTimer = null;
						      }
						      videoStudioSaveTimer = window.setTimeout(() => {
						        videoStudioSaveTimer = null;
						        try { writeVideoStudioState(); } catch (e) { /* ignore */ }
						      }, 450);
						    };

					    const setVideoStudioToolActive = (tool) => {
					      videoStudioTool = safeText(tool, 'pen');
					      const setActive = (btn, on) => {
					        if (!btn) return;
					        btn.classList.toggle('is-active', !!on);
					      };
					      setActive(videoToolPenBtn, videoStudioTool === 'pen');
					      setActive(videoToolArrowBtn, videoStudioTool === 'arrow');
						      setActive(videoToolCircleBtn, videoStudioTool === 'circle');
						      setActive(videoToolRectBtn, videoStudioTool === 'rect');
						      setActive(videoToolTextBtn, videoStudioTool === 'text');
						      setActive(videoToolCalloutBtn, videoStudioTool === 'callout');
						      if (videoStudioCanvas) {
						        const isPen = videoStudioTool === 'pen';
						        videoStudioCanvas.isDrawingMode = !!isPen;
					        if (isPen) {
					          try {
					            videoStudioCanvas.freeDrawingBrush.color = safeText(videoColorInput?.value, '#facc15');
					            videoStudioCanvas.freeDrawingBrush.width = clamp(Number(videoWidthSelect?.value) || 5, 1, 20);
					          } catch (e) { /* ignore */ }
					        }
					      }
					    };

							    const pushVideoStudioHistory = () => {
							      if (!videoStudioCanvas) return;
							      let json = null;
							      try { json = videoStudioCanvas.toDatalessJSON(['data']); } catch (e) { json = null; }
							      if (!json) return;
							      // Guarda siempre el "estado autoría" (sin opacidades temporales del timeline).
							      try {
							        const walk = (node) => {
							          if (!node || typeof node !== 'object') return;
							          const data = (node.data && typeof node.data === 'object') ? node.data : null;
							          if (data) {
							            if (typeof data.vs_base_opacity === 'number') node.opacity = clamp(Number(data.vs_base_opacity) || 1, 0, 1);
							            if (data.vs_dash_base && typeof data.vs_dash_base === 'object') {
							              node.strokeDashArray = Array.isArray(data.vs_dash_base.dashArray) ? data.vs_dash_base.dashArray.slice(0) : null;
							              node.strokeDashOffset = Number(data.vs_dash_base.dashOffset) || 0;
							            }
							            node.visible = true;
							          }
							          if (Array.isArray(node.objects)) node.objects.forEach(walk);
							          if (node.clipPath) walk(node.clipPath);
							        };
							        if (Array.isArray(json.objects)) json.objects.forEach(walk);
							      } catch (e) { /* ignore */ }
							      videoStudioMasterJson = json;
							      scheduleVideoStudioSave();
							      // Recorta si el usuario ha hecho undo y luego crea nuevos cambios.
							      if (videoStudioHistoryIndex < videoStudioHistory.length - 1) {
							        videoStudioHistory = videoStudioHistory.slice(0, videoStudioHistoryIndex + 1);
						      }
					      videoStudioHistory.push(json);
					      videoStudioHistoryIndex = videoStudioHistory.length - 1;
					      if (videoUndoBtn) videoUndoBtn.disabled = videoStudioHistoryIndex <= 0;
					      if (videoClearDrawBtn) videoClearDrawBtn.disabled = !videoStudioCanvas.getObjects().length;
					    };

					    const loadVideoStudioHistory = async (idx) => {
					      if (!videoStudioCanvas) return;
					      const index = clamp(Number(idx) || 0, 0, Math.max(0, videoStudioHistory.length - 1));
					      const json = videoStudioHistory[index];
					      if (!json) return;
					      videoStudioHistoryIndex = index;
					      if (videoUndoBtn) videoUndoBtn.disabled = videoStudioHistoryIndex <= 0;
					      try {
					        videoStudioCanvas.__loading = true;
					        await new Promise((resolve) => {
					          videoStudioCanvas.loadFromJSON(json, () => {
					            resolve(true);
					          });
					        });
					      } catch (e) { /* ignore */ }
					      try { videoStudioCanvas.renderAll(); } catch (e) { /* ignore */ }
					      try { videoStudioCanvas.__loading = false; } catch (e) { /* ignore */ }
					      if (videoClearDrawBtn) videoClearDrawBtn.disabled = !videoStudioCanvas.getObjects().length;
					    };

					    const clearVideoStudioCanvas = () => {
					      if (!videoStudioCanvas) return;
					      try {
					        const objs = videoStudioCanvas.getObjects() || [];
					        objs.forEach((o) => { try { videoStudioCanvas.remove(o); } catch (e) { /* ignore */ } });
					      } catch (e) { /* ignore */ }
					      try { videoStudioCanvas.renderAll(); } catch (e) { /* ignore */ }
					      pushVideoStudioHistory();
					    };

					    const renderVideoKeyframes = () => {
					      if (!videoKeyframeList) return;
					      videoKeyframeList.innerHTML = '';
					      if (!videoStudioKeyframes.length) {
					        videoKeyframeList.innerHTML = '<div class="timeline-empty">No hay keyframes todavía.</div>';
					      } else {
					        videoStudioKeyframes.slice(0, 220).forEach((kf) => {
					          const row = document.createElement('div');
					          row.className = 'video-kf-item';
					          const label = safeText(kf.title) ? `${formatClock(kf.t)} · ${safeText(kf.title)}` : `${formatClock(kf.t)}`;
					          row.innerHTML = `
					            <div>
					              <strong>${label}</strong>
					              <div class="meta" style="opacity:0.85;">Dibujo guardado</div>
					            </div>
					            <div>
					              <button type="button" class="button" data-video-kf-go="${kf.id}">Ir</button>
					              <button type="button" class="button" data-video-kf-load="${kf.id}">Cargar</button>
					              <button type="button" class="button danger" data-video-kf-del="${kf.id}">Borrar</button>
					            </div>
					          `;
					          videoKeyframeList.appendChild(row);
					        });
					      }
					      const has = !!videoStudioKeyframes.length;
					      if (videoKeyframeDeleteAllBtn) videoKeyframeDeleteAllBtn.disabled = !has;
					    };

					    const findKeyframeIndexForTime = (t) => {
					      const time = Math.max(0, Number(t) || 0);
					      if (!videoStudioKeyframes.length) return -1;
					      let best = -1;
					      for (let i = 0; i < videoStudioKeyframes.length; i += 1) {
					        if (videoStudioKeyframes[i].t <= time + 0.001) best = i;
					        else break;
					      }
					      return best;
					    };

						    const loadKeyframeAtIndex = async (index) => {
						      if (!videoStudioCanvas) return;
						      const idx = clamp(Number(index) || -1, -1, Math.max(-1, videoStudioKeyframes.length - 1));
						      if (idx === -1) {
						        clearVideoStudioCanvas();
					        videoStudioActiveKeyframe = -1;
					        return;
					      }
					      const kf = videoStudioKeyframes[idx];
					      if (!kf?.json) return;
					      videoStudioActiveKeyframe = idx;
					      try {
					        videoStudioCanvas.__loading = true;
					        await new Promise((resolve) => {
					          videoStudioCanvas.loadFromJSON(kf.json, () => resolve(true));
					        });
					      } catch (e) { /* ignore */ }
					      try { videoStudioCanvas.renderAll(); } catch (e) { /* ignore */ }
					      try { videoStudioCanvas.__loading = false; } catch (e) { /* ignore */ }
						      pushVideoStudioHistory();
						    };

						    const layerTypeLabel = (typeRaw) => {
						      const type = safeText(typeRaw, 'draw').toLowerCase();
						      if (type === 'spotlight') return 'Spotlight';
						      if (type === 'blur') return 'Blur';
						      if (type === 'freeze') return 'Freeze';
						      if (type === 'callout') return 'Callout';
						      return 'Dibujo';
						    };

						    const layerTypeIcon = (typeRaw) => {
						      const type = safeText(typeRaw, 'draw').toLowerCase();
						      if (type === 'spotlight') return '🎯';
						      if (type === 'blur') return '🫧';
						      if (type === 'freeze') return '⏸';
						      if (type === 'callout') return '#';
						      return '✏️';
						    };

						    const findVideoLayerIndex = (id) => (videoStudioLayers || []).findIndex((l) => safeText(l?.id) === safeText(id));
						    const activeVideoLayer = () => {
						      const id = safeText(videoStudioActiveLayerId);
						      if (!id) return null;
						      return (videoStudioLayers || []).find((l) => safeText(l?.id) === id) || null;
						    };

						    const computeVideoLayerState = (layer, timeRaw) => {
						      const t = Math.max(0, Number(timeRaw) || 0);
						      const start = Math.max(0, Number(layer?.start) || 0);
						      const end = (layer?.end == null) ? Infinity : Math.max(0, Number(layer?.end) || 0);
						      if (layer?.enabled === false) return { on: false, opacity: 0, progress: 0 };
						      if (t < start - 0.001 || t > end + 0.001) return { on: false, opacity: 0, progress: 0 };
						      const fadeIn = Math.max(0, Number(layer?.fade_in) || 0);
						      const fadeOut = Math.max(0, Number(layer?.fade_out) || 0);
						      const base = clamp(Number(layer?.opacity) || 1, 0, 1);
						      let alphaIn = 1;
						      if (fadeIn > 0.001) alphaIn = clamp((t - start) / fadeIn, 0, 1);
						      let alphaOut = 1;
						      if (fadeOut > 0.001 && Number.isFinite(end)) alphaOut = clamp((end - t) / fadeOut, 0, 1);
						      const opacity = base * Math.min(alphaIn, alphaOut);
						      const progress = clamp((t - start) / Math.max(0.001, (end - start)), 0, 1);
						      return { on: true, opacity, progress };
						    };

						    const setActiveVideoLayer = (id) => {
						      videoStudioActiveLayerId = safeText(id);
						      renderVideoLayers();
						      syncVideoLayerEditor();
						    };

						    const ensureVideoStudioDefaultLayer = () => {
						      if ((videoStudioLayers || []).length) {
						        if (!safeText(videoStudioActiveLayerId)) videoStudioActiveLayerId = safeText(videoStudioLayers[0]?.id);
						        return safeText(videoStudioActiveLayerId) || safeText(videoStudioLayers[0]?.id);
						      }
						      const now = Math.max(0, Number(videoStudioPlayer?.currentTime) || 0);
						      const layer = {
						        id: `ly_${Date.now()}_${Math.random().toString(16).slice(2)}`,
						        type: 'draw',
						        name: 'Capa 1',
						        enabled: true,
						        start: now,
						        end: null,
						        fade_in: 0.2,
						        fade_out: 0.2,
						        opacity: 1,
						        stroke_anim: 'none',
						        params: {},
						        order: 1,
						      };
						      videoStudioLayers = [layer];
						      videoStudioActiveLayerId = layer.id;
						      scheduleVideoStudioSave();
						      return layer.id;
						    };

						    const createVideoStudioLayer = (partial) => {
						      const now = Math.max(0, Number(videoStudioPlayer?.currentTime) || 0);
						      const nextIndex = (videoStudioLayers || []).length + 1;
						      const type = safeText(partial?.type, 'draw');
						      const layer = {
						        id: `ly_${Date.now()}_${Math.random().toString(16).slice(2)}`,
						        type,
						        name: safeText(partial?.name) || `${layerTypeLabel(type)} ${nextIndex}`,
						        enabled: partial?.enabled !== false,
						        start: Math.max(0, Number(partial?.start) || now),
						        end: (partial?.end == null) ? null : Math.max(0, Number(partial?.end) || 0),
						        fade_in: Math.max(0, Number(partial?.fade_in) || 0.25),
						        fade_out: Math.max(0, Number(partial?.fade_out) || 0.25),
						        opacity: clamp(Number(partial?.opacity) || 1, 0, 1),
						        stroke_anim: safeText(partial?.stroke_anim, 'none'),
						        params: (partial?.params && typeof partial.params === 'object') ? partial.params : {},
						        order: Number(partial?.order) || (nextIndex * 10),
						      };
						      videoStudioLayers = (videoStudioLayers || []).concat([layer]).slice(0, 120);
						      videoStudioLayers.sort((a, b) => ((a.order || 0) - (b.order || 0)) || (a.start - b.start));
						      videoStudioActiveLayerId = layer.id;
						      scheduleVideoStudioSave();
						      return layer;
						    };

						    const assignVideoStudioObjectsToLayer = (objs, layerId) => {
						      if (!videoStudioCanvas) return;
						      const id = safeText(layerId) || ensureVideoStudioDefaultLayer();
						      const list = Array.isArray(objs) ? objs : [];
						      list.forEach((obj) => {
						        if (!obj) return;
						        obj.data = (obj.data && typeof obj.data === 'object') ? obj.data : {};
						        obj.data.vs_layer_id = id;
						        if (typeof obj.data.vs_base_opacity !== 'number') obj.data.vs_base_opacity = clamp(Number(obj.opacity) || 1, 0, 1);
						      });
						      pushVideoStudioHistory();
						    };

						    const gatherActiveVideoStudioObjects = () => {
						      const c = videoStudioCanvas;
						      if (!c) return [];
						      const active = c.getActiveObject();
						      if (!active) return [];
						      if (active.type === 'activeSelection' && typeof active.getObjects === 'function') {
						        return (active.getObjects() || []).slice(0, 50);
						      }
						      return [active];
						    };

						    const syncVideoLayerEditor = () => {
						      const layer = activeVideoLayer();
						      if (!videoLayerEditorEl) return;
						      const on = !!layer;
						      videoLayerEditorEl.hidden = !on;
						      if (!on) return;
						      if (videoLayerNameInput) videoLayerNameInput.value = safeText(layer.name);
						      if (videoLayerInInput) videoLayerInInput.value = String(Number(layer.start) || 0);
						      if (videoLayerOutInput) videoLayerOutInput.value = layer.end == null ? '' : String(Number(layer.end) || 0);
						      if (videoLayerFadeInInput) videoLayerFadeInInput.value = String(Number(layer.fade_in) || 0);
						      if (videoLayerFadeOutInput) videoLayerFadeOutInput.value = String(Number(layer.fade_out) || 0);
						      if (videoLayerStrokeAnimSelect) videoLayerStrokeAnimSelect.value = safeText(layer.stroke_anim, 'none') || 'none';
						    };

						    const renderVideoLayers = () => {
						      if (!videoLayerListEl) return;
						      const layers = (videoStudioLayers || []).slice(0, 120);
						      videoLayerListEl.innerHTML = '';
						      if (!layers.length) {
						        videoLayerListEl.innerHTML = '<div class="timeline-empty">No hay capas todavía.</div>';
						      } else {
						        layers.forEach((layer) => {
						          const row = document.createElement('div');
						          const id = safeText(layer?.id);
						          row.className = 'video-layer-item';
						          if (id && id === safeText(videoStudioActiveLayerId)) row.classList.add('is-active');
						          const start = Math.max(0, Number(layer?.start) || 0);
						          const end = layer?.end == null ? null : Math.max(0, Number(layer?.end) || 0);
						          const label = safeText(layer?.name) || `${layerTypeLabel(layer?.type)}`;
						          const enabled = layer?.enabled !== false;
						          const meta = `${formatClock(start)} → ${end == null ? '—' : formatClock(end)} · fade ${Number(layer?.fade_in) || 0}/${Number(layer?.fade_out) || 0}`;
						          row.innerHTML = `
						            <div>
						              <strong>${layerTypeIcon(layer?.type)} ${label}</strong>
						              <div class="video-layer-meta">${meta}</div>
						            </div>
						            <div style="display:flex; gap:0.45rem; flex-wrap:wrap; justify-content:flex-end;">
						              <button type="button" class="button" data-vs-layer-go="${id}">Ir</button>
						              <button type="button" class="button ${enabled ? '' : 'danger'}" data-vs-layer-toggle="${id}">${enabled ? 'On' : 'Off'}</button>
						            </div>
						          `;
						          row.setAttribute('data-vs-layer', id);
						          videoLayerListEl.appendChild(row);
						        });
						      }
						      if (videoLayerStatusEl) {
						        const active = activeVideoLayer();
						        const activeLabel = active ? `${layerTypeIcon(active.type)} ${safeText(active.name) || layerTypeLabel(active.type)}` : '—';
						        videoLayerStatusEl.textContent = layers.length ? `Capas: ${layers.length} · Activa: ${activeLabel}` : '—';
						      }
						      syncVideoLayerEditor();
						    };

						    const applyProgressiveStrokeToObject = (obj, layer, time) => {
						      if (!obj || !layer) return;
						      if (safeText(layer.stroke_anim, 'none') !== 'draw') {
						        // Restaura dash si lo tocamos antes.
						        const restoreDash = (target) => {
						          if (!target) return;
						          target.data = (target.data && typeof target.data === 'object') ? target.data : {};
						          if (!target.data.vs_dash_base) return;
						          try {
						            target.set({
						              strokeDashArray: target.data.vs_dash_base.dashArray || null,
						              strokeDashOffset: target.data.vs_dash_base.dashOffset || 0,
						            });
						          } catch (e) { /* ignore */ }
						        };
						        if (obj.type === 'group' && obj?._objects?.length) {
						          (obj._objects || []).forEach(restoreDash);
						        } else {
						          restoreDash(obj);
						        }
						        return;
						      }
						      const drawDur = Math.max(0.15, Number(layer?.params?.draw_dur) || 0.9);
						      const start = Math.max(0, Number(layer?.start) || 0);
						      const progress = clamp((Math.max(0, Number(time) || 0) - start) / drawDur, 0, 1);
						      if (obj.type === 'group' && safeText(obj?.data?.kind).includes('video-arrow') && obj?._objects?.length) {
						        const line = (obj._objects || []).find((o) => o?.type === 'line') || null;
						        if (!line) return;
						        const x1 = Number(line.x1) || 0;
						        const y1 = Number(line.y1) || 0;
						        const x2 = Number(line.x2) || 0;
						        const y2 = Number(line.y2) || 0;
						        const len = Math.max(1, Math.hypot(x2 - x1, y2 - y1));
						        line.data = (line.data && typeof line.data === 'object') ? line.data : {};
						        if (!line.data.vs_dash_base) {
						          line.data.vs_dash_base = {
						            dashArray: Array.isArray(line.strokeDashArray) ? line.strokeDashArray.slice(0) : null,
						            dashOffset: Number(line.strokeDashOffset) || 0,
						          };
						        }
						        try {
						          line.set({
						            strokeDashArray: [len, len],
						            strokeDashOffset: Math.round(len * (1 - progress)),
						  });
						        } catch (e) { /* ignore */ }
						      }
						    };

						    const applyVideoStudioTimeline = (timeRaw, opts = {}) => {
						      const c = videoStudioCanvas;
						      if (!c) return;
						      const time = Math.max(0, Number(timeRaw) || Number(videoStudioPlayer?.currentTime) || 0);
						      const pro = !!videoStudioProEnabled && !!(videoStudioLayers || []).length;
						      const showHandles = opts?.for_export ? false : (!!videoStudioShowHandles || !pro);
						      const w = Number(c.getWidth?.()) || 1280;
						      const h = Number(c.getHeight?.()) || 720;

						      let spotlightLayer = null;
						      const blurLayers = [];
						      const freezeLayers = [];
						      (videoStudioLayers || []).forEach((layer) => {
						        const type = safeText(layer?.type, 'draw').toLowerCase();
						        if (!pro) return;
						        const st = computeVideoLayerState(layer, time);
						        if (!st.on || st.opacity <= 0.001) return;
						        if (type === 'spotlight') spotlightLayer = layer;
						        if (type === 'blur') blurLayers.push(layer);
						        if (type === 'freeze') freezeLayers.push(layer);
						      });

						      // DOM FX (preview)
						      if (videoSpotlightEl) {
						        if (pro && spotlightLayer) {
						          const st = computeVideoLayerState(spotlightLayer, time);
						          const p = spotlightLayer.params || {};
						          const cx = clamp(Number(p.x) || (w / 2), 0, w);
						          const cy = clamp(Number(p.y) || (h / 2), 0, h);
						          const r = Math.max(10, Number(p.r) || 160);
						          const feather = Math.max(0, Number(p.feather) || 40);
						          const dim = clamp(Number(p.dim) || 0.55, 0, 0.95) * clamp(Number(st.opacity) || 0, 0, 1);
						          videoSpotlightEl.style.setProperty('--spot-x', `${Math.round((cx / w) * 1000) / 10}%`);
						          videoSpotlightEl.style.setProperty('--spot-y', `${Math.round((cy / h) * 1000) / 10}%`);
						          videoSpotlightEl.style.setProperty('--spot-r', `${Math.round(r)}px`);
						          videoSpotlightEl.style.setProperty('--spot-feather', `${Math.round(feather)}px`);
						          videoSpotlightEl.style.background = `rgba(2, 6, 23, ${dim})`;
						          videoSpotlightEl.hidden = false;
						        } else {
						          videoSpotlightEl.hidden = true;
						        }
						      }
						      if (videoBlurWrapEl) {
						        if (pro && blurLayers.length) {
						          videoBlurWrapEl.hidden = false;
						          videoBlurWrapEl.innerHTML = '';
						          blurLayers.slice(0, 6).forEach((layer) => {
						            const st = computeVideoLayerState(layer, time);
						            const p = layer.params || {};
						            const x = clamp(Number(p.x) || (w * 0.25), 0, w);
						            const y = clamp(Number(p.y) || (h * 0.25), 0, h);
						            const bw = clamp(Number(p.w) || (w * 0.25), 10, w);
						            const bh = clamp(Number(p.h) || (h * 0.18), 10, h);
						            const blur = clamp(Number(p.blur) || 12, 1, 30) * clamp(Number(st.opacity) || 0, 0.05, 1);
						            const el = document.createElement('div');
						            el.className = 'video-studio-blur-rect';
						            el.style.opacity = String(clamp(Number(st.opacity) || 0, 0, 1));
						            el.style.left = `${(x / w) * 100}%`;
						            el.style.top = `${(y / h) * 100}%`;
						            el.style.width = `${(bw / w) * 100}%`;
						            el.style.height = `${(bh / h) * 100}%`;
						            el.style.setProperty('--blur', `${blur}px`);
						            videoBlurWrapEl.appendChild(el);
						          });
						        } else {
						          videoBlurWrapEl.hidden = true;
						          videoBlurWrapEl.innerHTML = '';
						        }
						      }

						      // Objetos (overlay)
						      try {
						        (c.getObjects() || []).forEach((obj) => {
						          obj.data = (obj.data && typeof obj.data === 'object') ? obj.data : {};
						          const layerId = safeText(obj.data.vs_layer_id);
						          const isHandle = !!obj.data.vs_handle;
						          if (!pro) {
						            obj.visible = true;
						            if (typeof obj.data.vs_base_opacity === 'number') obj.opacity = obj.data.vs_base_opacity;
						            else obj.data.vs_base_opacity = clamp(Number(obj.opacity) || 1, 0, 1);
						            if (isHandle && !videoStudioShowHandles) obj.visible = false;
						            return;
						          }
						          if (isHandle) {
						            obj.visible = showHandles;
						            obj.opacity = showHandles ? 0.85 : 0;
						            return;
						          }
						          const layer = layerId ? (videoStudioLayers || []).find((l) => safeText(l?.id) === layerId) : null;
						          if (!layer) {
						            obj.visible = true;
						            if (typeof obj.data.vs_base_opacity !== 'number') obj.data.vs_base_opacity = clamp(Number(obj.opacity) || 1, 0, 1);
						            obj.opacity = obj.data.vs_base_opacity;
						            return;
						          }
						          const st = computeVideoLayerState(layer, time);
						          const baseOpacity = (typeof obj.data.vs_base_opacity === 'number') ? clamp(Number(obj.data.vs_base_opacity) || 1, 0, 1) : clamp(Number(obj.opacity) || 1, 0, 1);
						          obj.data.vs_base_opacity = baseOpacity;
						          obj.visible = st.on && st.opacity > 0.001;
						          obj.opacity = baseOpacity * st.opacity;
						          applyProgressiveStrokeToObject(obj, layer, time);
						        });
						      } catch (e) { /* ignore */ }
						      try { c.renderAll(); } catch (e) { /* ignore */ }

						      if (opts?.for_export) return { spotlightLayer, blurLayers, freezeLayers, w, h, pro };
						      return null;
						    };

						    const syncVideoScrubUi = () => {
						      const vid = videoStudioPlayer;
						      if (!vid) return;
						      const dur = Number(vid.duration) || 0;
					      const cur = Number(vid.currentTime) || 0;
					      if (videoTimeEl) videoTimeEl.textContent = formatClock(cur);
					      if (videoDurationEl) videoDurationEl.textContent = formatClock(dur);
					      if (videoScrubInput) {
					        const max = Number(videoScrubInput.max) || 1000;
					        const next = dur > 0 ? Math.round((cur / dur) * max) : 0;
					        if (!videoScrubInput.__dragging) videoScrubInput.value = String(clamp(next, 0, max));
					      }
					    };

					    const setVideoStudioStatus = (text, isErr = false) => {
					      if (!videoStatusEl) return;
					      videoStatusEl.textContent = safeText(text, '—');
					      videoStatusEl.style.color = isErr ? 'rgba(248,113,113,0.92)' : '';
					    };

						    const setVideoStudioLoadedUi = (loaded) => {
						      const on = !!loaded;
						      if (videoClearBtn) videoClearBtn.disabled = !on;
						      if (videoKeyframeAddBtn) videoKeyframeAddBtn.disabled = !on;
						      if (videoClearDrawBtn) videoClearDrawBtn.disabled = !on || !(videoStudioCanvas?.getObjects()?.length);
						      if (videoToolCalloutBtn) videoToolCalloutBtn.disabled = !on;
						      if (videoToolSpotlightBtn) videoToolSpotlightBtn.disabled = !on;
						      if (videoToolBlurBtn) videoToolBlurBtn.disabled = !on;
						      if (videoToolFreezeBtn) videoToolFreezeBtn.disabled = !on;
						      if (videoLayerAddBtn) videoLayerAddBtn.disabled = !on;
						      if (videoLayerFromSelectionBtn) videoLayerFromSelectionBtn.disabled = !on;
						      if (videoExportBtn) videoExportBtn.disabled = !on || !canRecordVideoStudio();
						      if (videoExportFormatSelect) videoExportFormatSelect.disabled = !on || !canRecordVideoStudio();
						      if (videoExportQualitySelect) videoExportQualitySelect.disabled = !on || !canRecordVideoStudio();
						      if (videoExportFpsSelect) videoExportFpsSelect.disabled = !on || !canRecordVideoStudio();
						      if (videoExportLenSelect) videoExportLenSelect.disabled = !on || !canRecordVideoStudio();
						      if (videoExportSlidesBtn) videoExportSlidesBtn.disabled = !on;
						      if (videoExportPackBtn) videoExportPackBtn.disabled = !on;
						      if (videoKeyframeDeleteAllBtn) videoKeyframeDeleteAllBtn.disabled = !on || !videoStudioKeyframes.length;
						      if (videoUndoBtn) videoUndoBtn.disabled = !on || videoStudioHistoryIndex <= 0;
						    };

					    const revokeVideoStudioUrl = () => {
					      if (!videoStudioUrl) return;
					      try { URL.revokeObjectURL(videoStudioUrl); } catch (e) { /* ignore */ }
					      videoStudioUrl = '';
					    };

						    const ensureVideoStudioCanvas = () => {
						      if (!videoStudioCanvasEl || !window.fabric) return null;
						      if (videoStudioCanvas) return videoStudioCanvas;
						      videoStudioCanvas = new window.fabric.Canvas(videoStudioCanvasEl, {
						        preserveObjectStacking: true,
						        selection: true,
						      });
						      try { videoStudioCanvas.setDimensions({ width: 1280, height: 720 }, { cssOnly: false }); } catch (e) { /* ignore */ }
						      try {
						        videoStudioCanvas.freeDrawingBrush = new window.fabric.PencilBrush(videoStudioCanvas);
						        videoStudioCanvas.freeDrawingBrush.color = safeText(videoColorInput?.value, '#facc15');
						        videoStudioCanvas.freeDrawingBrush.width = clamp(Number(videoWidthSelect?.value) || 5, 1, 20);
						      } catch (e) { /* ignore */ }
						      pushVideoStudioHistory();
						      return videoStudioCanvas;
						    };

						    const loadVideoStudioMasterIfNeeded = async () => {
						      if (!videoStudioCanvas) return;
						      if (videoStudioMasterLoaded) return;
						      videoStudioMasterLoaded = true;
						      if (!videoStudioMasterJson) return;
						      try {
						        videoStudioCanvas.__loading = true;
						        await new Promise((resolve) => {
						          videoStudioCanvas.loadFromJSON(videoStudioMasterJson, () => resolve(true));
						        });
						      } catch (e) { /* ignore */ }
						      try { videoStudioCanvas.renderAll(); } catch (e) { /* ignore */ }
						      try { videoStudioCanvas.__loading = false; } catch (e) { /* ignore */ }
						      pushVideoStudioHistory();
						    };

					    const installVideoStudioTools = () => {
					      if (videoStudioToolsInstalled) return;
					      const c = ensureVideoStudioCanvas();
					      if (!c) return;
					      videoStudioToolsInstalled = true;
					      let temp = null;
					      let start = null;

					      const strokeColor = () => safeText(videoColorInput?.value, '#facc15');
					      const strokeWidth = () => clamp(Number(videoWidthSelect?.value) || 5, 1, 20);
					      const applyStroke = (obj) => {
					        try {
					          obj.set({
					            stroke: strokeColor(),
					            strokeWidth: strokeWidth(),
					            strokeLineCap: 'round',
					            strokeLineJoin: 'round',
					          });
					        } catch (e) { /* ignore */ }
					      };

					      const cleanupTemp = () => {
					        if (temp) {
					          try { c.remove(temp); } catch (e) { /* ignore */ }
					          temp = null;
					        }
					      };

						      c.on('mouse:down', (opt) => {
						        if (videoStudioExporting) return;
						        if (!videoStudioPlayer || !Number.isFinite(Number(videoStudioPlayer.duration) || 0)) return;
						        const tool = videoStudioTool;
						        if (tool === 'pen') return;
						        const ptr = c.getPointer(opt.e);
						        start = { x: Number(ptr.x) || 0, y: Number(ptr.y) || 0 };
						        const layerId = ensureVideoStudioDefaultLayer();

						        if (tool === 'callout') {
						          const num = clamp(Number(videoStudioCalloutSeq) || 1, 1, 999);
						          videoStudioCalloutSeq = clamp(num + 1, 1, 999);
						          scheduleVideoStudioSave();
						          const circ = new window.fabric.Circle({
						            left: start.x,
						            top: start.y,
						            originX: 'center',
						            originY: 'center',
						            radius: 22,
						            fill: 'rgba(250,204,21,0.92)',
						            stroke: 'rgba(15,23,42,0.55)',
						            strokeWidth: 2,
						          });
						          const label = new window.fabric.Text(String(num), {
						            left: start.x,
						            top: start.y + 1,
						            originX: 'center',
						            originY: 'center',
						            fill: 'rgba(15,23,42,0.94)',
						            fontSize: 22,
						            fontWeight: 900,
						          });
						          const group = new window.fabric.Group([circ, label], { selectable: true, evented: true });
						          group.data = { kind: 'video-callout', vs_layer_id: layerId, vs_base_opacity: 1 };
						          c.add(group);
						          c.setActiveObject(group);
						          try { c.renderAll(); } catch (e) { /* ignore */ }
						          pushVideoStudioHistory();
						          start = null;
						          return;
						        }

						        if (tool === 'arrow') {
						          const line = new window.fabric.Line([start.x, start.y, start.x, start.y], { fill: '', selectable: false, evented: false });
						          applyStroke(line);
						          temp = line;
						          c.add(line);
						        } else if (tool === 'circle') {
						          const circ = new window.fabric.Circle({ left: start.x, top: start.y, radius: 1, fill: 'rgba(0,0,0,0)', originX: 'center', originY: 'center', selectable: false, evented: false });
						          applyStroke(circ);
						          circ.data = { kind: 'video-circle', vs_layer_id: layerId, vs_base_opacity: 1 };
						          temp = circ;
						          c.add(circ);
						        } else if (tool === 'rect') {
						          const rect = new window.fabric.Rect({ left: start.x, top: start.y, width: 1, height: 1, fill: 'rgba(0,0,0,0)', originX: 'left', originY: 'top', selectable: false, evented: false });
						          applyStroke(rect);
						          rect.data = { kind: 'video-rect', vs_layer_id: layerId, vs_base_opacity: 1 };
						          temp = rect;
						          c.add(rect);
						        } else if (tool === 'text') {
						          const text = window.prompt('Texto:', ''); // eslint-disable-line no-alert
						          if (text == null) { start = null; return; }
						          const txt = new window.fabric.Textbox(safeText(text), { left: start.x, top: start.y, originX: 'left', originY: 'top', fill: strokeColor(), fontSize: 34, fontWeight: 900 });
						          txt.data = { kind: 'video-text', vs_layer_id: layerId, vs_base_opacity: 1 };
						          c.add(txt);
						          c.setActiveObject(txt);
						          try { c.renderAll(); } catch (e) { /* ignore */ }
						          pushVideoStudioHistory();
						          start = null;
						        }
						      });

					      c.on('mouse:move', (opt) => {
					        if (!start || !temp) return;
					        const tool = videoStudioTool;
					        const ptr = c.getPointer(opt.e);
					        const x = Number(ptr.x) || 0;
					        const y = Number(ptr.y) || 0;
					        if (tool === 'arrow' && temp.type === 'line') {
					          temp.set({ x2: x, y2: y });
					        } else if (tool === 'circle' && temp.type === 'circle') {
					          const dx = x - start.x;
					          const dy = y - start.y;
					          const r = Math.max(1, Math.hypot(dx, dy));
					          temp.set({ radius: r });
					        } else if (tool === 'rect' && temp.type === 'rect') {
					          temp.set({ width: x - start.x, height: y - start.y });
					        }
					        try { c.renderAll(); } catch (e) { /* ignore */ }
					      });

						      c.on('mouse:up', () => {
						        if (!start) return;
						        const tool = videoStudioTool;
						        const layerId = ensureVideoStudioDefaultLayer();
						        if (tool === 'arrow' && temp && temp.type === 'line') {
						          const line = temp;
						          const x1 = Number(line.x1) || 0;
						          const y1 = Number(line.y1) || 0;
						          const x2 = Number(line.x2) || 0;
					          const y2 = Number(line.y2) || 0;
					          const dx = x2 - x1;
					          const dy = y2 - y1;
					          const len = Math.hypot(dx, dy) || 0;
					          if (len >= 10) {
					            const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
					            const head = new window.fabric.Triangle({
					              width: 18,
					              height: 18,
					              fill: strokeColor(),
					              left: x2,
					              top: y2,
					              originX: 'center',
					              originY: 'center',
					              angle: angle + 90,
					              selectable: false,
					              evented: false,
					            });
						            const group = new window.fabric.Group([line, head], { selectable: true, evented: true });
						            group.data = { kind: 'video-arrow', vs_layer_id: layerId, vs_base_opacity: 1 };
						            try { c.remove(line); } catch (e) { /* ignore */ }
						            c.add(group);
						            c.setActiveObject(group);
						          } else {
						            cleanupTemp();
					          }
					        }
						        start = null;
						        if (temp && (temp.type === 'circle' || temp.type === 'rect')) {
						          try { temp.set({ selectable: true, evented: true }); } catch (e) { /* ignore */ }
						        }
						        temp = null;
						        try { c.renderAll(); } catch (e) { /* ignore */ }
						        pushVideoStudioHistory();
						      });

						      c.on('path:created', (ev) => {
						        const path = ev?.path;
						        if (!path) return;
						        const layerId = ensureVideoStudioDefaultLayer();
						        path.data = (path.data && typeof path.data === 'object') ? path.data : {};
						        path.data.kind = safeText(path.data.kind) || 'video-pen';
						        path.data.vs_layer_id = layerId;
						        if (typeof path.data.vs_base_opacity !== 'number') path.data.vs_base_opacity = clamp(Number(path.opacity) || 1, 0, 1);
						        pushVideoStudioHistory();
						      });

						      c.on('object:modified', (ev) => {
						        if (c.__loading) return;
						        const target = ev?.target;
						        if (target?.data?.vs_handle) {
						          const layerId = safeText(target?.data?.vs_layer_id);
						          const layer = layerId ? (videoStudioLayers || []).find((l) => safeText(l?.id) === layerId) : null;
						          if (layer) {
						            layer.params = (layer.params && typeof layer.params === 'object') ? layer.params : {};
						            const kind = safeText(target?.data?.kind);
						            if (kind === 'vs-spotlight-handle' && target.type === 'circle') {
						              const cx = Number(target.left) || 0;
						              const cy = Number(target.top) || 0;
						              const scale = Math.max(0.05, Number(target.scaleX) || 1);
						              const r = Math.max(10, (Number(target.radius) || 10) * scale);
						              layer.params.x = cx;
						              layer.params.y = cy;
						              layer.params.r = r;
						              // Resetea la escala para que la edición sea consistente.
						              try { target.set({ scaleX: 1, scaleY: 1, radius: r }); } catch (e) { /* ignore */ }
						            }
						            if (kind === 'vs-blur-handle' && target.type === 'rect') {
						              const x = Number(target.left) || 0;
						              const y = Number(target.top) || 0;
						              const w = Math.max(10, (Number(target.width) || 10) * Math.max(0.05, Number(target.scaleX) || 1));
						              const h = Math.max(10, (Number(target.height) || 10) * Math.max(0.05, Number(target.scaleY) || 1));
						              layer.params.x = x;
						              layer.params.y = y;
						              layer.params.w = w;
						              layer.params.h = h;
						              try { target.set({ scaleX: 1, scaleY: 1, width: w, height: h }); } catch (e) { /* ignore */ }
						            }
						            scheduleVideoStudioSave();
						          }
						        }
						        pushVideoStudioHistory();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });
					      c.on('selection:created', () => {
					        if (videoClearDrawBtn) videoClearDrawBtn.disabled = !c.getObjects().length;
					      });
					      c.on('selection:updated', () => {
					        if (videoClearDrawBtn) videoClearDrawBtn.disabled = !c.getObjects().length;
					      });
					      c.on('selection:cleared', () => {
					        if (videoClearDrawBtn) videoClearDrawBtn.disabled = !c.getObjects().length;
					      });
					    };

						    const ensureVideoStudioHandlers = () => {
						      if (videoStudioHandlersInstalled) return;
						      if (!videoStudioModal) return;
						      videoStudioHandlersInstalled = true;

						      readVideoStudioState();
						      renderVideoKeyframes();
						      renderVideoLayers();
						      if (videoProEnabledInput) videoProEnabledInput.checked = !!videoStudioProEnabled;
						      if (videoShowHandlesInput) videoShowHandlesInput.checked = !!videoStudioShowHandles;

						      videoToolPenBtn?.addEventListener('click', () => setVideoStudioToolActive('pen'));
						      videoToolArrowBtn?.addEventListener('click', () => setVideoStudioToolActive('arrow'));
						      videoToolCircleBtn?.addEventListener('click', () => setVideoStudioToolActive('circle'));
						      videoToolRectBtn?.addEventListener('click', () => setVideoStudioToolActive('rect'));
						      videoToolTextBtn?.addEventListener('click', () => setVideoStudioToolActive('text'));
						      videoToolCalloutBtn?.addEventListener('click', () => setVideoStudioToolActive('callout'));

						      videoProEnabledInput?.addEventListener('change', () => {
						        videoStudioProEnabled = !!videoProEnabledInput.checked;
						        scheduleVideoStudioSave();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						        renderVideoLayers();
						      });
						      videoShowHandlesInput?.addEventListener('change', () => {
						        videoStudioShowHandles = !!videoShowHandlesInput.checked;
						        scheduleVideoStudioSave();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });

						      videoColorInput?.addEventListener('change', () => {
						        if (videoStudioCanvas && videoStudioCanvas.freeDrawingBrush) {
						          try { videoStudioCanvas.freeDrawingBrush.color = safeText(videoColorInput.value, '#facc15'); } catch (e) { /* ignore */ }
					        }
					      });
					      videoWidthSelect?.addEventListener('change', () => {
					        if (videoStudioCanvas && videoStudioCanvas.freeDrawingBrush) {
					          try { videoStudioCanvas.freeDrawingBrush.width = clamp(Number(videoWidthSelect.value) || 5, 1, 20); } catch (e) { /* ignore */ }
					        }
					      });

					      videoUndoBtn?.addEventListener('click', () => {
					        if (videoStudioHistoryIndex <= 0) return;
					        void loadVideoStudioHistory(videoStudioHistoryIndex - 1);
					      });
					      videoClearDrawBtn?.addEventListener('click', () => {
					        const ok = window.confirm('¿Limpiar todos los dibujos?'); // eslint-disable-line no-alert
					        if (!ok) return;
					        clearVideoStudioCanvas();
					      });

						      videoLoadBtn?.addEventListener('click', () => {
						        try { videoFileInput?.click?.(); } catch (e) { /* ignore */ }
						      });
						      videoExportFormatSelect?.addEventListener('change', () => {
						        const fmt = safeText(videoExportFormatSelect.value, 'auto');
						        const picked = pickVideoStudioMime(fmt);
						        if (fmt === 'mp4' && !picked) {
						          window.alert('MP4 no está disponible en este navegador. Se exportará en WebM si es posible.'); // eslint-disable-line no-alert
						        }
						      });
					      videoClearBtn?.addEventListener('click', () => {
					        const ok = window.confirm('¿Quitar el vídeo? (Los keyframes se mantienen.)'); // eslint-disable-line no-alert
					        if (!ok) return;
					        revokeVideoStudioUrl();
					        if (videoStudioPlayer) {
					          try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
					          videoStudioPlayer.removeAttribute('src');
					          try { videoStudioPlayer.load(); } catch (e) { /* ignore */ }
					        }
					        setVideoStudioStatus('—');
					        setVideoStudioLoadedUi(false);
					        syncVideoScrubUi();
					      });

					      videoFileInput?.addEventListener('change', () => {
					        const file = videoFileInput.files && videoFileInput.files[0];
					        if (!file) return;
					        revokeVideoStudioUrl();
					        videoStudioUrl = URL.createObjectURL(file);
					        if (videoStudioPlayer) {
					          videoStudioPlayer.src = videoStudioUrl;
					          try { videoStudioPlayer.load(); } catch (e) { /* ignore */ }
					        }
					        setVideoStudioStatus(`${safeText(file.name, 'video')}`);
					        setVideoStudioLoadedUi(true);
					      });

						      videoStudioPlayer?.addEventListener('loadedmetadata', () => {
						        syncVideoScrubUi();
						        setVideoStudioLoadedUi(true);
						        ensureVideoStudioDefaultLayer();
						        renderVideoLayers();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });
						      videoStudioPlayer?.addEventListener('timeupdate', () => {
						        syncVideoScrubUi();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						        if (videoStudioPlayer?.paused) return;
						        if (videoStudioProEnabled && (videoStudioLayers || []).length) return;
						        const idx = findKeyframeIndexForTime(videoStudioPlayer.currentTime);
						        if (idx !== videoStudioActiveKeyframe) void loadKeyframeAtIndex(idx);
						      });
						      videoStudioPlayer?.addEventListener('pause', () => {
						        syncVideoScrubUi();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });
						      videoStudioPlayer?.addEventListener('play', () => {
						        syncVideoScrubUi();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });

						      if (videoScrubInput) {
						        videoScrubInput.addEventListener('pointerdown', () => { videoScrubInput.__dragging = true; });
						        videoScrubInput.addEventListener('pointerup', () => { videoScrubInput.__dragging = false; });
					        videoScrubInput.addEventListener('input', () => {
					          if (!videoStudioPlayer) return;
					          const max = Number(videoScrubInput.max) || 1000;
					          const dur = Number(videoStudioPlayer.duration) || 0;
					          const frac = clamp((Number(videoScrubInput.value) || 0) / max, 0, 1);
						          if (dur > 0) {
						            try { videoStudioPlayer.currentTime = frac * dur; } catch (e) { /* ignore */ }
						          }
						          syncVideoScrubUi();
						          applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						        });
						      }

						      videoLayerAddBtn?.addEventListener('click', () => {
						        if (!videoStudioPlayer) return;
						        const now = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        createVideoStudioLayer({ type: 'draw', start: now, end: null, fade_in: 0.2, fade_out: 0.2, stroke_anim: 'none' });
						        renderVideoLayers();
						        applyVideoStudioTimeline(now);
						      });
						      videoLayerFromSelectionBtn?.addEventListener('click', () => {
						        if (!videoStudioPlayer || !videoStudioCanvas) return;
						        const objs = gatherActiveVideoStudioObjects();
						        if (!objs.length) {
						          window.alert('Selecciona un objeto/dibujo primero.'); // eslint-disable-line no-alert
						          return;
						        }
						        const now = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        const layer = createVideoStudioLayer({ type: 'draw', start: now, end: null, fade_in: 0.2, fade_out: 0.2 });
						        assignVideoStudioObjectsToLayer(objs, layer.id);
						        renderVideoLayers();
						        applyVideoStudioTimeline(now);
						      });

						      videoLayerListEl?.addEventListener('click', (event) => {
						        const target = event.target instanceof Element ? event.target : null;
						        if (!target) return;
						        const goId = safeText(target.getAttribute('data-vs-layer-go'));
						        const toggleId = safeText(target.getAttribute('data-vs-layer-toggle'));
						        const row = target.closest?.('[data-vs-layer]');
						        const rowId = safeText(row?.getAttribute?.('data-vs-layer'));
						        if (goId && videoStudioPlayer) {
						          const idx = findVideoLayerIndex(goId);
						          if (idx >= 0) {
						            try { videoStudioPlayer.currentTime = Math.max(0, Number(videoStudioLayers[idx]?.start) || 0); } catch (e) { /* ignore */ }
						            try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
						            syncVideoScrubUi();
						            applyVideoStudioTimeline(Number(videoStudioPlayer.currentTime) || 0);
						          }
						          return;
						        }
						        if (toggleId) {
						          const idx = findVideoLayerIndex(toggleId);
						          if (idx >= 0) {
						            videoStudioLayers[idx].enabled = videoStudioLayers[idx].enabled === false;
						            scheduleVideoStudioSave();
						            renderVideoLayers();
						            applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						          }
						          return;
						        }
						        if (rowId) {
						          setActiveVideoLayer(rowId);
						          applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						        }
						      });

						      const applyEditorToLayer = () => {
						        const layer = activeVideoLayer();
						        if (!layer) return;
						        if (videoLayerNameInput) layer.name = safeText(videoLayerNameInput.value);
						        if (videoLayerInInput) layer.start = Math.max(0, Number(videoLayerInInput.value) || 0);
						        if (videoLayerOutInput) {
						          const raw = safeText(videoLayerOutInput.value);
						          layer.end = raw ? Math.max(0, Number(raw) || 0) : null;
						        }
						        if (videoLayerFadeInInput) layer.fade_in = Math.max(0, Number(videoLayerFadeInInput.value) || 0);
						        if (videoLayerFadeOutInput) layer.fade_out = Math.max(0, Number(videoLayerFadeOutInput.value) || 0);
						        if (videoLayerStrokeAnimSelect) layer.stroke_anim = safeText(videoLayerStrokeAnimSelect.value, 'none') || 'none';
						        if (layer.end != null && layer.end < layer.start) layer.end = layer.start;
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      };
						      [videoLayerNameInput, videoLayerInInput, videoLayerOutInput, videoLayerFadeInInput, videoLayerFadeOutInput, videoLayerStrokeAnimSelect]
						        .forEach((el) => el?.addEventListener?.('change', applyEditorToLayer));

						      videoLayerSetInBtn?.addEventListener('click', () => {
						        if (!videoStudioPlayer) return;
						        const layer = activeVideoLayer();
						        if (!layer) return;
						        layer.start = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        if (layer.end != null && layer.end < layer.start) layer.end = layer.start;
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        syncVideoLayerEditor();
						        applyVideoStudioTimeline(layer.start);
						      });
						      videoLayerSetOutBtn?.addEventListener('click', () => {
						        if (!videoStudioPlayer) return;
						        const layer = activeVideoLayer();
						        if (!layer) return;
						        layer.end = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        if (layer.end < layer.start) layer.start = layer.end;
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        syncVideoLayerEditor();
						        applyVideoStudioTimeline(Number(videoStudioPlayer.currentTime) || 0);
						      });

						      videoLayerDeleteBtn?.addEventListener('click', () => {
						        const layer = activeVideoLayer();
						        if (!layer || !videoStudioCanvas) return;
						        const ok = window.confirm('¿Borrar la capa y sus elementos?'); // eslint-disable-line no-alert
						        if (!ok) return;
						        const id = safeText(layer.id);
						        // Elimina objetos ligados a la capa.
						        try {
						          (videoStudioCanvas.getObjects() || []).forEach((obj) => {
						            if (safeText(obj?.data?.vs_layer_id) === id) {
						              try { videoStudioCanvas.remove(obj); } catch (e) { /* ignore */ }
						            }
						          });
						        } catch (e) { /* ignore */ }
						        const idx = findVideoLayerIndex(id);
						        if (idx >= 0) videoStudioLayers.splice(idx, 1);
						        videoStudioActiveLayerId = safeText(videoStudioLayers[0]?.id);
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        pushVideoStudioHistory();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      });

						      // FX tools (one-shot layers)
						      const createSpotlightLayer = () => {
						        if (!videoStudioCanvas || !videoStudioPlayer || !window.fabric) return;
						        const now = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        const w = Number(videoStudioCanvas.getWidth?.()) || 1280;
						        const h = Number(videoStudioCanvas.getHeight?.()) || 720;
						        const layer = createVideoStudioLayer({
						          type: 'spotlight',
						          start: now,
						          end: now + 3,
						          fade_in: 0.2,
						          fade_out: 0.2,
						          params: { x: w / 2, y: h / 2, r: 170, feather: 45, dim: 0.55 },
						        });
						        const handle = new window.fabric.Circle({
						          left: w / 2,
						          top: h / 2,
						          originX: 'center',
						          originY: 'center',
						          radius: 170,
						          fill: 'rgba(0,0,0,0)',
						          stroke: 'rgba(250,204,21,0.85)',
						          strokeWidth: 3,
						          strokeDashArray: [10, 8],
						          selectable: true,
						          evented: true,
						        });
						        handle.data = { vs_handle: true, kind: 'vs-spotlight-handle', vs_layer_id: layer.id, vs_base_opacity: 1 };
						        videoStudioCanvas.add(handle);
						        videoStudioShowHandles = true;
						        if (videoShowHandlesInput) videoShowHandlesInput.checked = true;
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        applyVideoStudioTimeline(now);
						      };
						      const createBlurLayer = () => {
						        if (!videoStudioCanvas || !videoStudioPlayer || !window.fabric) return;
						        const now = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        const w = Number(videoStudioCanvas.getWidth?.()) || 1280;
						        const h = Number(videoStudioCanvas.getHeight?.()) || 720;
						        const layer = createVideoStudioLayer({
						          type: 'blur',
						          start: now,
						          end: now + 3,
						          fade_in: 0.2,
						          fade_out: 0.2,
						          params: { x: w * 0.34, y: h * 0.34, w: w * 0.32, h: h * 0.22, blur: 12 },
						        });
						        const handle = new window.fabric.Rect({
						          left: w * 0.34,
						          top: h * 0.34,
						          width: w * 0.32,
						          height: h * 0.22,
						          fill: 'rgba(0,0,0,0)',
						          stroke: 'rgba(59,130,246,0.85)',
						          strokeWidth: 3,
						          strokeDashArray: [10, 8],
						          selectable: true,
						          evented: true,
						        });
						        handle.data = { vs_handle: true, kind: 'vs-blur-handle', vs_layer_id: layer.id, vs_base_opacity: 1 };
						        videoStudioCanvas.add(handle);
						        videoStudioShowHandles = true;
						        if (videoShowHandlesInput) videoShowHandlesInput.checked = true;
						        scheduleVideoStudioSave();
						        renderVideoLayers();
						        applyVideoStudioTimeline(now);
						      };
						      const createFreezeLayer = () => {
						        if (!videoStudioPlayer) return;
						        const now = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
						        createVideoStudioLayer({ type: 'freeze', start: now, end: now + 2.5, fade_in: 0, fade_out: 0, params: {} });
						        renderVideoLayers();
						        applyVideoStudioTimeline(now);
						      };
						      videoToolSpotlightBtn?.addEventListener('click', () => { createSpotlightLayer(); });
						      videoToolBlurBtn?.addEventListener('click', () => { createBlurLayer(); });
						      videoToolFreezeBtn?.addEventListener('click', () => { createFreezeLayer(); });

						      videoKeyframeAddBtn?.addEventListener('click', () => {
						        if (!videoStudioCanvas || !videoStudioPlayer) return;
						        let json = null;
						        try { json = videoStudioCanvas.toDatalessJSON(['data']); } catch (e) { json = null; }
					        if (!json) return;
					        const t = Math.max(0, Number(videoStudioPlayer.currentTime) || 0);
					        const title = window.prompt('Nombre (opcional):', ''); // eslint-disable-line no-alert
					        const kf = {
					          id: `kf_${Date.now()}_${Math.random().toString(16).slice(2)}`,
					          t,
					          title: safeText(title),
					          json,
					        };
					        videoStudioKeyframes.push(kf);
					        videoStudioKeyframes.sort((a, b) => (a.t - b.t));
					        videoStudioKeyframes = videoStudioKeyframes.slice(0, 220);
					        writeVideoStudioState();
					        renderVideoKeyframes();
					        setStatus('Keyframe guardado.');
					      });

					      videoKeyframeDeleteAllBtn?.addEventListener('click', () => {
					        const ok = window.confirm('¿Borrar TODOS los keyframes guardados?'); // eslint-disable-line no-alert
					        if (!ok) return;
					        videoStudioKeyframes = [];
					        videoStudioActiveKeyframe = -1;
					        writeVideoStudioState();
					        renderVideoKeyframes();
					        setStatus('Keyframes borrados.');
					      });

					      videoKeyframeList?.addEventListener('click', (event) => {
					        const target = event.target;
					        const id = safeText(target?.getAttribute?.('data-video-kf-go') || target?.getAttribute?.('data-video-kf-load') || target?.getAttribute?.('data-video-kf-del'));
					        if (!id) return;
					        const idx = videoStudioKeyframes.findIndex((kf) => kf.id === id);
					        if (idx < 0) return;
					        if (target?.hasAttribute?.('data-video-kf-go')) {
					          if (videoStudioPlayer) {
					            try { videoStudioPlayer.currentTime = videoStudioKeyframes[idx].t; } catch (e) { /* ignore */ }
					            try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
					          }
					          syncVideoScrubUi();
					          return;
					        }
					        if (target?.hasAttribute?.('data-video-kf-load')) {
					          void loadKeyframeAtIndex(idx);
					          if (videoStudioPlayer) {
					            try { videoStudioPlayer.currentTime = videoStudioKeyframes[idx].t; } catch (e) { /* ignore */ }
					            try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
					          }
					          syncVideoScrubUi();
					          return;
					        }
					        if (target?.hasAttribute?.('data-video-kf-del')) {
					          const ok = window.confirm('¿Borrar este keyframe?'); // eslint-disable-line no-alert
					          if (!ok) return;
					          videoStudioKeyframes.splice(idx, 1);
					          videoStudioKeyframes.sort((a, b) => (a.t - b.t));
					          writeVideoStudioState();
					          renderVideoKeyframes();
					        }
					      });

						      const drawContain = (ctx, video, outW, outH) => {
						        const vw = Number(video?.videoWidth) || 0;
						        const vh = Number(video?.videoHeight) || 0;
						        if (!vw || !vh) return;
						        const scale = Math.min(outW / vw, outH / vh);
						        const w = Math.round(vw * scale);
						        const h = Math.round(vh * scale);
						        const dx = Math.round((outW - w) / 2);
						        const dy = Math.round((outH - h) / 2);
						        try { ctx.drawImage(video, dx, dy, w, h); } catch (e) { /* ignore */ }
						      };

						      const pickVideoStudioMime = (formatPref) => {
						        const pref = safeText(formatPref, 'auto').toLowerCase();
						        const candidates = [];
						        if (pref === 'mp4') {
						          candidates.push(
						            'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
						            'video/mp4;codecs=avc1.4D401E,mp4a.40.2',
						            'video/mp4'
						          );
						        }
						        if (pref === 'webm') {
						          candidates.push(
						            'video/webm;codecs=vp9,opus',
						            'video/webm;codecs=vp8,opus',
						            'video/webm'
						          );
						        }
						        if (pref === 'auto') {
						          candidates.push(
						            'video/webm;codecs=vp9,opus',
						            'video/webm;codecs=vp8,opus',
						            'video/webm',
						            'video/mp4;codecs=avc1.42E01E,mp4a.40.2',
						            'video/mp4'
						          );
						        }
						        let picked = '';
						        candidates.some((mt) => {
						          try {
						            if (window.MediaRecorder && window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(mt)) {
						              picked = mt;
						              return true;
						            }
						          } catch (e) { /* ignore */ }
						          return false;
						        });
						        return picked;
						      };

						      const computeExportSize = (qualityPref) => {
						        const pref = safeText(qualityPref, 'fast').toLowerCase();
						        const baseW = Math.max(640, Math.round(videoStudioCanvas?.getWidth?.() || 1280));
						        const baseH = Math.max(360, Math.round(videoStudioCanvas?.getHeight?.() || 720));
						        const vw = Math.max(1, Number(videoStudioPlayer?.videoWidth) || baseW);
						        const vh = Math.max(1, Number(videoStudioPlayer?.videoHeight) || baseH);
						        if (pref === 'pro') return { w: 1920, h: 1080 };
						        if (pref === 'source') {
						          const maxW = 2200;
						          const maxH = 1400;
						          const scale = Math.min(maxW / vw, maxH / vh, 1);
						          return { w: Math.round(vw * scale), h: Math.round(vh * scale) };
						        }
						        return { w: baseW, h: baseH };
						      };

						      const seekVideoStudio = async (t) => {
						        if (!videoStudioPlayer) return false;
						        const time = Math.max(0, Number(t) || 0);
						        try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
						        const done = await new Promise((resolve) => {
						          let timer = null;
						          const cleanup = () => {
						            if (timer) window.clearTimeout(timer);
						            timer = null;
						            try { videoStudioPlayer.removeEventListener('seeked', onSeeked); } catch (e) { /* ignore */ }
						            resolve(true);
						          };
						          const onSeeked = () => cleanup();
						          try { videoStudioPlayer.addEventListener('seeked', onSeeked, { once: true }); } catch (e) { /* ignore */ }
						          timer = window.setTimeout(() => cleanup(), 900);
						          try { videoStudioPlayer.currentTime = time; } catch (e) { cleanup(); }
						        });
						        return !!done;
						      };

						      const captureVideoStudioFrame = async (t, size) => {
						        if (!videoStudioPlayer || !videoStudioCanvas) return null;
						        const outW = Math.max(640, Math.round(size?.w || 1280));
						        const outH = Math.max(360, Math.round(size?.h || 720));
						        const out = document.createElement('canvas');
						        out.width = outW;
						        out.height = outH;
						        const ctx = out.getContext('2d');
						        if (!ctx) return null;
						        await seekVideoStudio(t);
						        applyVideoStudioTimeline(t, { for_export: true });
						        let fx = null;
						        try { fx = applyVideoStudioTimeline(t, { for_export: true }) || {}; } catch (e) { fx = {}; }
						        try {
						          ctx.fillStyle = 'rgba(2,6,23,1)';
						          ctx.fillRect(0, 0, outW, outH);
						          drawContain(ctx, videoStudioPlayer, outW, outH);
						          // blur/spotlight like export tick
						          if (fx?.pro && Array.isArray(fx.blurLayers) && fx.blurLayers.length) {
						            const baseW = Number(fx.w) || (Number(videoStudioCanvas.getWidth?.()) || 1280);
						            const baseH = Number(fx.h) || (Number(videoStudioCanvas.getHeight?.()) || 720);
						            const sx = outW / Math.max(1, baseW);
						            const sy = outH / Math.max(1, baseH);
						            fx.blurLayers.slice(0, 8).forEach((layer) => {
						              const st = computeVideoLayerState(layer, t);
						              if (!st.on || st.opacity <= 0.01) return;
						              const p = layer.params || {};
						              const x = clamp(Number(p.x) || 0, 0, baseW);
						              const y = clamp(Number(p.y) || 0, 0, baseH);
						              const bw = clamp(Number(p.w) || (baseW * 0.25), 10, baseW);
						              const bh = clamp(Number(p.h) || (baseH * 0.18), 10, baseH);
						              const blur = clamp(Number(p.blur) || 12, 1, 40) * st.opacity;
						              ctx.save();
						              ctx.globalAlpha = st.opacity;
						              ctx.filter = `blur(${Math.round(blur)}px)`;
						              ctx.beginPath();
						              ctx.rect(x * sx, y * sy, bw * sx, bh * sy);
						              ctx.clip();
						              drawContain(ctx, videoStudioPlayer, outW, outH);
						              ctx.restore();
						            });
						          }
						          if (fx?.pro && fx?.spotlightLayer) {
						            const st = computeVideoLayerState(fx.spotlightLayer, t);
						            if (st.on && st.opacity > 0.01) {
						              const baseW = Number(fx.w) || (Number(videoStudioCanvas.getWidth?.()) || 1280);
						              const baseH = Number(fx.h) || (Number(videoStudioCanvas.getHeight?.()) || 720);
						              const sx = outW / Math.max(1, baseW);
						              const sy = outH / Math.max(1, baseH);
						              const p = fx.spotlightLayer.params || {};
						              const cx = clamp(Number(p.x) || (baseW / 2), 0, baseW) * sx;
						              const cy = clamp(Number(p.y) || (baseH / 2), 0, baseH) * sy;
						              const r = Math.max(10, Number(p.r) || 160) * Math.min(sx, sy);
						              const feather = Math.max(0, Number(p.feather) || 40) * Math.min(sx, sy);
						              const dim = clamp(Number(p.dim) || 0.55, 0, 0.95) * st.opacity;
						              ctx.save();
						              ctx.fillStyle = `rgba(2,6,23,${dim})`;
						              ctx.fillRect(0, 0, outW, outH);
						              ctx.globalCompositeOperation = 'destination-out';
						              const g = ctx.createRadialGradient(cx, cy, Math.max(1, r - feather), cx, cy, r + feather);
						              g.addColorStop(0, 'rgba(0,0,0,1)');
						              g.addColorStop(0.72, 'rgba(0,0,0,1)');
						              g.addColorStop(1, 'rgba(0,0,0,0)');
						              ctx.fillStyle = g;
						              ctx.beginPath();
						              ctx.arc(cx, cy, r + feather, 0, Math.PI * 2);
						              ctx.fill();
						              ctx.restore();
						            }
						          }
						          ctx.drawImage(videoStudioCanvas.lowerCanvasEl, 0, 0, outW, outH);
						        } catch (e) { /* ignore */ }
						        let url = null;
						        try { url = out.toDataURL('image/png'); } catch (e) { url = null; }
						        // restore preview
						        applyVideoStudioTimeline(Number(videoStudioPlayer.currentTime) || 0);
						        return url;
						      };

						      const collectVideoStudioSlideTimes = () => {
						        const times = [];
						        const add = (t) => {
						          const v = Math.max(0, Number(t) || 0);
						          if (!Number.isFinite(v)) return;
						          times.push(Math.round(v * 1000) / 1000);
						        };
						        const usePro = !!videoStudioProEnabled && (videoStudioLayers || []).length;
						        if (usePro) {
						          (videoStudioLayers || []).forEach((layer) => {
						            if (layer?.enabled === false) return;
						            add(layer.start);
						            if (safeText(layer.type).toLowerCase() === 'freeze') add(layer.start);
						          });
						        } else {
						          (videoStudioKeyframes || []).forEach((kf) => add(kf.t));
						        }
						        add(Number(videoStudioPlayer?.currentTime) || 0);
						        const uniq = Array.from(new Set(times)).sort((a, b) => a - b);
						        return uniq.slice(0, 60);
						      };

						      const buildVideoStudioSlidesHtml = (meta, slides) => {
						        const title = safeText(meta?.title, 'Telestración');
						        const subtitle = safeText(meta?.subtitle, '');
						        const created = safeText(meta?.created, new Date().toISOString());
						        const cover = safeText(meta?.cover, '');
						        const rows = slides.map((s, idx) => {
						          const t = safeText(s?.time_label, '');
						          const img = safeText(s?.img, '');
						          const id = `slide_${idx + 1}`;
						          return `
						            <section class="slide" id="${id}">
						              <div class="slide-head">
						                <div class="badge">#${idx + 1}</div>
						                <div class="t">${t}</div>
						              </div>
						              <img class="frame" src="${img}" alt="frame ${idx + 1}" />
						            </section>
						          `;
						        }).join('\n');
						        const thumbs = slides.map((s, idx) => {
						          const t = safeText(s?.time_label, '');
						          const img = safeText(s?.thumb, s?.img || '');
						          const id = `slide_${idx + 1}`;
						          return `
						            <a class="thumb" href="#${id}">
						              <img src="${img}" alt="thumb ${idx + 1}" />
						              <div class="thumb-meta">#${idx + 1} · ${t}</div>
						            </a>
						          `;
						        }).join('\n');
						        return `<!doctype html>
						<html lang="es">
						<head>
						  <meta charset="utf-8" />
						  <meta name="viewport" content="width=device-width, initial-scale=1" />
						  <title>${title}</title>
						  <style>
						    :root { color-scheme: light; }
						    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #0f172a; background: #f8fafc; }
						    .wrap { max-width: 980px; margin: 0 auto; padding: 18px 18px 48px; }
						    .cover { display: grid; grid-template-columns: 1fr; gap: 12px; align-items: start; background: #ffffff; border: 1px solid rgba(15,23,42,0.10); border-radius: 16px; overflow: hidden; }
						    .cover-top { padding: 18px 18px 0; }
						    .kicker { font-weight: 900; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(2,6,23,0.55); font-size: 12px; }
						    h1 { margin: 6px 0 0; font-size: 28px; }
						    .sub { margin: 6px 0 0; color: rgba(15,23,42,0.7); font-weight: 600; }
						    .meta { margin: 10px 0 16px; color: rgba(15,23,42,0.6); font-size: 13px; }
						    .cover img { width: 100%; height: auto; display: block; background: #0b1220; }
						    .index { margin-top: 14px; background: #ffffff; border: 1px solid rgba(15,23,42,0.10); border-radius: 16px; padding: 14px; }
						    .index h2 { margin: 0 0 10px; font-size: 16px; }
						    .thumbs { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
						    .thumb { display: grid; gap: 6px; text-decoration: none; color: inherit; padding: 10px; border: 1px solid rgba(15,23,42,0.10); border-radius: 12px; background: rgba(248,250,252,0.9); }
						    .thumb img { width: 100%; height: auto; border-radius: 10px; background: #0b1220; }
						    .thumb-meta { font-size: 12px; color: rgba(15,23,42,0.72); font-weight: 700; }
						    .slide { break-before: page; margin-top: 18px; background: #ffffff; border: 1px solid rgba(15,23,42,0.10); border-radius: 16px; overflow: hidden; }
						    .slide-head { display:flex; align-items:center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid rgba(15,23,42,0.08); }
						    .badge { display:inline-flex; align-items:center; justify-content:center; width: 30px; height: 30px; border-radius: 999px; background: #16a34a; color: #ffffff; font-weight: 900; font-size: 13px; }
						    .t { font-weight: 900; color: rgba(15,23,42,0.75); }
						    .frame { width: 100%; height: auto; display:block; background: #0b1220; }
						    @media print {
						      body { background: #fff; }
						      .wrap { max-width: none; padding: 0; }
						      .index { break-before: page; }
						      .thumb { break-inside: avoid; }
						      a { color: inherit; text-decoration: none; }
						    }
						  </style>
						</head>
						<body>
						  <div class="wrap">
						    <section class="cover">
						      <div class="cover-top">
						        <div class="kicker">2J · Video Studio</div>
						        <h1>${title}</h1>
						        ${subtitle ? `<div class="sub">${subtitle}</div>` : ``}
						        <div class="meta">Generado: ${created}</div>
						      </div>
						      ${cover ? `<img src="${cover}" alt="cover" />` : ``}
						    </section>
						    <section class="index">
						      <h2>Índice</h2>
						      <div class="thumbs">${thumbs}</div>
						    </section>
						    ${rows}
						  </div>
						</body>
						</html>`;
						      };

						      const downloadTextFile = (name, text, mime = 'text/plain') => {
						        const blob = new Blob([text], { type: mime });
						        const url = URL.createObjectURL(blob);
						        const a = document.createElement('a');
						        a.href = url;
						        a.download = name;
						        document.body.appendChild(a);
						        a.click();
						        a.remove();
						        window.setTimeout(() => { try { URL.revokeObjectURL(url); } catch (e) { /* ignore */ } }, 2000);
						      };

						      const exportVideoStudioSlides = async (mode) => {
						        if (!videoStudioPlayer || !videoStudioCanvas) return;
						        const dur = Number(videoStudioPlayer.duration) || 0;
						        if (!(dur > 0)) return;
						        const times = collectVideoStudioSlideTimes();
						        if (!times.length) {
						          window.alert('No hay tiempos para slides. Crea keyframes o capas.'); // eslint-disable-line no-alert
						          return;
						        }
						        const prevPaused = !!videoStudioPlayer.paused;
						        const prevTime = Number(videoStudioPlayer.currentTime) || 0;
						        videoStudioExporting = true;
						        setVideoStudioStatus('Generando slides…');
						        const size = computeExportSize('fast');
						        const slides = [];
						        for (let i = 0; i < times.length; i += 1) {
						          const t = clamp(times[i], 0, Math.max(0, dur - 0.001));
						          const img = await captureVideoStudioFrame(t, size);
						          if (!img) continue;
						          slides.push({
						            t,
						            time_label: formatClock(t),
						            img,
						            thumb: img,
						          });
						        }
						        const cover = slides[0]?.img || '';
						        const title = 'Telestración · Slides';
						        const html = buildVideoStudioSlidesHtml({
						          title,
						          subtitle: safeText(videoStatusEl?.textContent),
						          created: new Date().toLocaleString(),
						          cover,
						        }, slides);
						        videoStudioExporting = false;
						        setVideoStudioStatus('Slides listos.');
						        try { videoStudioPlayer.currentTime = prevTime; } catch (e) { /* ignore */ }
						        if (!prevPaused) { try { videoStudioPlayer.play(); } catch (e) { /* ignore */ } }
						        if (mode === 'pack') {
						          const stamp = Date.now();
						          downloadTextFile(`telestracion_pack_${stamp}.html`, html, 'text/html');
						          downloadTextFile(`telestracion_pack_${stamp}.json`, JSON.stringify({ v: 1, created_at: new Date().toISOString(), slides: slides.map((s) => ({ t: s.t, label: s.time_label })) }, null, 2), 'application/json');
						          return;
						        }
						        const w = window.open('', '_blank');
						        if (!w) {
						          window.alert('Tu navegador ha bloqueado la ventana. Permite popups para imprimir el PDF.'); // eslint-disable-line no-alert
						          return;
						        }
						        w.document.open();
						        w.document.write(html);
						        w.document.close();
						        w.focus();
						        // Espera a que carguen imágenes y lanza print.
						        window.setTimeout(() => { try { w.print(); } catch (e) { /* ignore */ } }, 600);
						      };

						      const exportVideoStudio = async () => {
						        if (!videoStudioPlayer || !videoStudioCanvas) return;
						        if (videoStudioExporting) return;
						        if (!canRecordVideoStudio()) {
						          window.alert('Tu navegador no soporta exportación de vídeo aquí.'); // eslint-disable-line no-alert
					          return;
					        }
					        const dur = Number(videoStudioPlayer.duration) || 0;
					        if (!(dur > 0)) return;
					        const lenRaw = safeText(videoExportLenSelect?.value, '10');
					        const startTime = clamp(Number(videoStudioPlayer.currentTime) || 0, 0, Math.max(0, dur - 0.1));
					        const clipLen = (lenRaw === 'full') ? (dur - startTime) : clamp(Number(lenRaw) || 10, 3, 600);
						        if (clipLen <= 0.25) return;

						        videoStudioExporting = true;
						        if (videoExportBtn) videoExportBtn.disabled = true;
						        setVideoStudioStatus('Exportando…');

						        const size = computeExportSize(videoExportQualitySelect?.value);
						        const outW = Math.max(640, Math.round(size.w || 1280));
						        const outH = Math.max(360, Math.round(size.h || 720));
						        const out = document.createElement('canvas');
						        out.width = outW;
						        out.height = outH;
						        const ctx = out.getContext('2d');
					        if (!ctx) {
					          videoStudioExporting = false;
					          setVideoStudioStatus('No se pudo exportar.', true);
					          setVideoStudioLoadedUi(true);
					          return;
					        }

						        const fps = clamp(Number(videoExportFpsSelect?.value) || 30, 12, 60);
						        let stream = null;
						        try { stream = out.captureStream(fps); } catch (e) { stream = null; }
						        if (!stream) {
						          videoStudioExporting = false;
						          setVideoStudioStatus('No se pudo exportar.', true);
						          setVideoStudioLoadedUi(true);
					          return;
					        }
					        // Audio (si el navegador lo permite).
					        try {
					          const vstream = typeof videoStudioPlayer.captureStream === 'function' ? videoStudioPlayer.captureStream() : null;
					          const atrack = vstream?.getAudioTracks?.()?.[0] || null;
					          if (atrack) stream.addTrack(atrack);
					        } catch (e) { /* ignore */ }

						        const mimeType = pickVideoStudioMime(videoExportFormatSelect?.value);
						        let recorder = null;
						        try { recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : undefined); } catch (e) { recorder = null; }
						        if (!recorder) {
						          videoStudioExporting = false;
					          setVideoStudioStatus('No se pudo exportar.', true);
					          setVideoStudioLoadedUi(true);
					          return;
					        }

					        const chunks = [];
					        recorder.ondataavailable = (ev) => { if (ev?.data && ev.data.size > 0) chunks.push(ev.data); };
						        recorder.onstop = () => {
						          const blob = new Blob(chunks, { type: recorder?.mimeType || 'video/webm' });
						          const url = URL.createObjectURL(blob);
						          const link = document.createElement('a');
						          link.href = url;
						          const ext = (safeText(recorder?.mimeType).includes('mp4')) ? 'mp4' : 'webm';
						          link.download = `telestracion_${Date.now()}.${ext}`;
						          document.body.appendChild(link);
						          link.click();
						          link.remove();
					          window.setTimeout(() => {
					            try { URL.revokeObjectURL(url); } catch (e) { /* ignore */ }
					          }, 2500);
					        };

					        const prevPaused = !!videoStudioPlayer.paused;
					        const prevTime = Number(videoStudioPlayer.currentTime) || 0;
					        try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
					        try { videoStudioPlayer.currentTime = startTime; } catch (e) { /* ignore */ }
					        await new Promise((r) => window.setTimeout(r, 120));

						        const startedAt = window.performance?.now?.() || Date.now();
						        const stopAtMs = clipLen * 1000;
						        let freezeHold = null;
						        try { recorder.start(250); } catch (e) { /* ignore */ }
						        try { videoStudioPlayer.play(); } catch (e) { /* ignore */ }

						        const tick = (nowRaw) => {
						          const now = Number(nowRaw) || (window.performance?.now?.() || Date.now());
						          const elapsed = now - startedAt;
						          const vtime = startTime + Math.max(0, elapsed / 1000);
						          const fx = applyVideoStudioTimeline(vtime, { for_export: true }) || {};
						          const freezeOn = !!(fx?.freezeLayers && fx.freezeLayers.length);
						          if (freezeOn) {
						            if (freezeHold == null) freezeHold = Number(videoStudioPlayer.currentTime) || vtime;
						            try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
						          } else if (freezeHold != null) {
						            freezeHold = null;
						            try { videoStudioPlayer.currentTime = vtime; } catch (e) { /* ignore */ }
						            try { videoStudioPlayer.play(); } catch (e) { /* ignore */ }
						          } else {
						            const cur = Number(videoStudioPlayer.currentTime) || 0;
						            if (Math.abs(cur - vtime) > 0.12) {
						              try { videoStudioPlayer.currentTime = vtime; } catch (e) { /* ignore */ }
						            }
						          }
						          try {
						            ctx.fillStyle = 'rgba(2,6,23,1)';
						            ctx.fillRect(0, 0, outW, outH);
						            drawContain(ctx, videoStudioPlayer, outW, outH);
						            // Blur (regiones)
						            if (fx?.pro && Array.isArray(fx.blurLayers) && fx.blurLayers.length) {
						              const baseW = Number(fx.w) || (Number(videoStudioCanvas.getWidth?.()) || 1280);
						              const baseH = Number(fx.h) || (Number(videoStudioCanvas.getHeight?.()) || 720);
						              const sx = outW / Math.max(1, baseW);
						              const sy = outH / Math.max(1, baseH);
						              fx.blurLayers.slice(0, 8).forEach((layer) => {
						                const st = computeVideoLayerState(layer, vtime);
						                if (!st.on || st.opacity <= 0.01) return;
						                const p = layer.params || {};
						                const x = clamp(Number(p.x) || 0, 0, baseW);
						                const y = clamp(Number(p.y) || 0, 0, baseH);
						                const bw = clamp(Number(p.w) || (baseW * 0.25), 10, baseW);
						                const bh = clamp(Number(p.h) || (baseH * 0.18), 10, baseH);
						                const blur = clamp(Number(p.blur) || 12, 1, 40) * st.opacity;
						                ctx.save();
						                ctx.globalAlpha = st.opacity;
						                ctx.filter = `blur(${Math.round(blur)}px)`;
						                ctx.beginPath();
						                ctx.rect(x * sx, y * sy, bw * sx, bh * sy);
						                ctx.clip();
						                drawContain(ctx, videoStudioPlayer, outW, outH);
						                ctx.restore();
						              });
						            }
						            // Spotlight (oscurecer fuera de foco)
						            if (fx?.pro && fx?.spotlightLayer) {
						              const st = computeVideoLayerState(fx.spotlightLayer, vtime);
						              if (st.on && st.opacity > 0.01) {
						                const baseW = Number(fx.w) || (Number(videoStudioCanvas.getWidth?.()) || 1280);
						                const baseH = Number(fx.h) || (Number(videoStudioCanvas.getHeight?.()) || 720);
						                const sx = outW / Math.max(1, baseW);
						                const sy = outH / Math.max(1, baseH);
						                const p = fx.spotlightLayer.params || {};
						                const cx = clamp(Number(p.x) || (baseW / 2), 0, baseW) * sx;
						                const cy = clamp(Number(p.y) || (baseH / 2), 0, baseH) * sy;
						                const r = Math.max(10, Number(p.r) || 160) * Math.min(sx, sy);
						                const feather = Math.max(0, Number(p.feather) || 40) * Math.min(sx, sy);
						                const dim = clamp(Number(p.dim) || 0.55, 0, 0.95) * st.opacity;
						                ctx.save();
						                ctx.fillStyle = `rgba(2,6,23,${dim})`;
						                ctx.fillRect(0, 0, outW, outH);
						                ctx.globalCompositeOperation = 'destination-out';
						                const g = ctx.createRadialGradient(cx, cy, Math.max(1, r - feather), cx, cy, r + feather);
						                g.addColorStop(0, 'rgba(0,0,0,1)');
						                g.addColorStop(0.72, 'rgba(0,0,0,1)');
						                g.addColorStop(1, 'rgba(0,0,0,0)');
						                ctx.fillStyle = g;
						                ctx.beginPath();
						                ctx.arc(cx, cy, r + feather, 0, Math.PI * 2);
						                ctx.fill();
						                ctx.restore();
						              }
						            }
						            ctx.drawImage(videoStudioCanvas.lowerCanvasEl, 0, 0, outW, outH);
						          } catch (e) { /* ignore */ }
						          if (elapsed >= stopAtMs || vtime >= (startTime + clipLen - 0.01)) {
						            videoStudioExportFrame = null;
						            try { videoStudioPlayer.pause(); } catch (e) { /* ignore */ }
						            try { recorder.stop(); } catch (e) { /* ignore */ }
						            videoStudioExporting = false;
						            setVideoStudioStatus('Exportado.');
					            setVideoStudioLoadedUi(true);
					            try { stream.getTracks().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
					            try { videoStudioPlayer.currentTime = prevTime; } catch (e) { /* ignore */ }
					            if (!prevPaused) { try { videoStudioPlayer.play(); } catch (e) { /* ignore */ } }
					            return;
					          }
					          videoStudioExportFrame = window.requestAnimationFrame(tick);
					        };
					        videoStudioExportFrame = window.requestAnimationFrame(tick);
					      };

						      videoExportBtn?.addEventListener('click', () => { void exportVideoStudio(); });
						      videoExportSlidesBtn?.addEventListener('click', () => { void exportVideoStudioSlides('pdf'); });
						      videoExportPackBtn?.addEventListener('click', () => { void exportVideoStudioSlides('pack'); });
						    };

					    const setVideoStudioOpen = (open) => {
					      if (!videoStudioModal) return;
					      const shouldOpen = !!open;
						      videoStudioModal.hidden = !shouldOpen;
						      if (shouldOpen) {
						        ensureVideoStudioCanvas();
						        void loadVideoStudioMasterIfNeeded();
						        ensureVideoStudioDefaultLayer();
						        installVideoStudioTools();
						        ensureVideoStudioHandlers();
						        setVideoStudioToolActive(videoStudioTool);
						        syncVideoScrubUi();
						        setVideoStudioLoadedUi(!!safeText(videoStudioPlayer?.src));
						        renderVideoLayers();
						        syncVideoLayerEditor();
						        applyVideoStudioTimeline(Number(videoStudioPlayer?.currentTime) || 0);
						      } else {
					        if (videoStudioExportFrame) {
					          try { window.cancelAnimationFrame(videoStudioExportFrame); } catch (e) { /* ignore */ }
					          videoStudioExportFrame = null;
					        }
					        videoStudioExporting = false;
					        try { videoStudioPlayer?.pause?.(); } catch (e) { /* ignore */ }
					      }
					    };

					    simVideoStudioBtn?.addEventListener('click', () => {
					      if (!isSimulating) return;
					      setVideoStudioOpen(true);
					    });
					    videoStudioCloseBtn?.addEventListener('click', () => setVideoStudioOpen(false));
					    videoStudioModal?.addEventListener('click', (event) => {
					      if (event.target === videoStudioModal) setVideoStudioOpen(false);
					    });
					    videoStudioModal?.addEventListener('keydown', (event) => {
					      if (String(event.key || '').toLowerCase() === 'escape') setVideoStudioOpen(false);
					    });

				    // Rutas editables por jugador (waypoints) + pase / balón pegado.
				    let simRouteAddMode = false;
				    let simRouteOverlays = [];
				    const clearSimRouteOverlays = () => {
				      try {
				        (simRouteOverlays || []).forEach((obj) => {
				          try { canvas.remove(obj); } catch (e) { /* ignore */ }
				        });
				      } catch (e) { /* ignore */ }
				      simRouteOverlays = [];
				    };
				    const activeSimulationStep = () => {
				      const idx = clamp(simulationActiveIndex, 0, Math.max(0, simulationSteps.length - 1));
				      return simulationSteps[idx] || null;
				    };
				    const ensureStepRoutes = (step) => {
				      if (!step || typeof step !== 'object') return null;
				      if (!step.routes || typeof step.routes !== 'object') step.routes = {};
				      if (typeof step.ball_follow_uid !== 'string') step.ball_follow_uid = safeText(step.ball_follow_uid);
				      return step.routes;
				    };
				    const activeRouteTarget = () => {
				      const active = canvas.getActiveObject();
				      if (!active) return null;
				      const pick = (obj) => {
				        if (!obj || obj?.data?.base) return null;
				        const uid = safeText(obj?.data?.layer_uid);
				        if (!uid) return null;
				        return { uid, kind: safeText(obj?.data?.kind) };
				      };
				      if (active.type === 'activeSelection' && typeof active.getObjects === 'function') {
				        const objs = active.getObjects() || [];
				        return pick(objs[0]) || null;
				      }
				      return pick(active);
				    };
				    const routeColorForObject = (obj) => {
				      const kind = safeText(obj?.data?.kind);
				      if (kind === 'ball') return 'rgba(250,204,21,0.92)';
				      if (safeText(obj?.data?.token_kind).toLowerCase().includes('rival')) return 'rgba(248,113,113,0.88)';
				      return 'rgba(34,197,94,0.88)';
				    };
				    const renderSimRoutesForStep = (step) => {
				      clearSimRouteOverlays();
				      if (!isSimulating) return;
				      const routes = step && typeof step === 'object' ? step.routes : null;
				      if (!routes || typeof routes !== 'object') return;
				      const liveByUid = new Map();
				      (canvas.getObjects?.() || []).forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (uid && !obj?.data?.base) liveByUid.set(uid, obj);
				      });
				      Object.entries(routes).slice(0, 50).forEach(([uid, route]) => {
				        const points = Array.isArray(route?.points) ? route.points : [];
				        if (points.length < 2) return;
				        const obj = liveByUid.get(uid);
				        const stroke = routeColorForObject(obj);
				        const poly = new fabric.Polyline(points.map((p) => ({ x: Number(p.x) || 0, y: Number(p.y) || 0 })), {
				          left: 0,
				          top: 0,
				          originX: 'left',
				          originY: 'top',
				          stroke,
				          strokeWidth: 3,
				          strokeDashArray: route?.spline ? [6, 6] : [10, 8],
				          fill: '',
				          selectable: false,
				          evented: false,
				          excludeFromExport: true,
				          opacity: 0.9,
				          objectCaching: false,
				          data: { base: true, kind: 'sim-route' },
				        });
				        canvas.add(poly);
				        try { canvas.sendToBack(poly); } catch (e) { /* ignore */ }
				        simRouteOverlays.push(poly);
				        points.slice(0, 20).forEach((pt) => {
				          const dot = new fabric.Circle({
				            left: Number(pt.x) || 0,
				            top: Number(pt.y) || 0,
				            originX: 'center',
				            originY: 'center',
				            radius: 4,
				            fill: stroke,
				            stroke: 'rgba(15,23,42,0.55)',
				            strokeWidth: 1,
				            selectable: false,
				            evented: false,
				            excludeFromExport: true,
				            opacity: 0.95,
				            data: { base: true, kind: 'sim-route-dot' },
				          });
				          canvas.add(dot);
				          simRouteOverlays.push(dot);
				        });
				      });
				      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				    };
				    const setRouteAddMode = (enabled) => {
				      simRouteAddMode = !!enabled;
				      if (simRouteToggleBtn) {
				        simRouteToggleBtn.textContent = simRouteAddMode ? 'Parar waypoints' : 'Añadir waypoints';
				        simRouteToggleBtn.classList.toggle('primary', simRouteAddMode);
				      }
				      setStatus(simRouteAddMode ? 'Ruta: toca el campo para añadir waypoints (sobre el seleccionado).' : 'Ruta: modo edición desactivado.');
				    };
				    const addRoutePointAt = (uid, point) => {
				      const step = activeSimulationStep();
				      if (!step) return false;
				      const routes = ensureStepRoutes(step);
				      if (!routes) return false;
				      const list = routes[uid]?.points;
				      const points = Array.isArray(list) ? list.slice(0, 60) : [];
				      points.push({ x: clamp(Number(point.x) || 0, 0, worldSize().w || 1280), y: clamp(Number(point.y) || 0, 0, worldSize().h || 720) });
				      const spline = routes[uid]?.spline === true;
				      routes[uid] = { points: points.slice(0, 40), spline };
				      try { renderSimRoutesForStep(step); } catch (e) { /* ignore */ }
				      try { scheduleDraftSave('sim-route'); } catch (e) { /* ignore */ }
				      return true;
				    };
				    const undoRoutePoint = (uid) => {
				      const step = activeSimulationStep();
				      if (!step || !step.routes) return;
				      const route = step.routes[uid];
				      const points = Array.isArray(route?.points) ? route.points.slice() : [];
				      points.pop();
				      if (points.length < 2) delete step.routes[uid];
				      else step.routes[uid] = { points, spline: !!route?.spline };
				      renderSimRoutesForStep(step);
				      try { scheduleDraftSave('sim-route-undo'); } catch (e) { /* ignore */ }
				    };
				    const clearRoute = (uid) => {
				      const step = activeSimulationStep();
				      if (!step || !step.routes) return;
				      delete step.routes[uid];
				      renderSimRoutesForStep(step);
				      try { scheduleDraftSave('sim-route-clear'); } catch (e) { /* ignore */ }
				    };
				    const setRouteSpline = (uid, spline) => {
				      const step = activeSimulationStep();
				      if (!step) return;
				      const routes = ensureStepRoutes(step);
				      if (!routes) return;
				      if (!routes[uid]) routes[uid] = { points: [], spline: !!spline };
				      routes[uid].spline = !!spline;
				      renderSimRoutesForStep(step);
				      try { scheduleDraftSave('sim-route-spline'); } catch (e) { /* ignore */ }
				    };
				    const setBallFollow = (followUid) => {
				      const step = activeSimulationStep();
				      if (!step) return;
				      step.ball_follow_uid = safeText(followUid);
				      if (step.ball_follow_uid) setStatus('Balón pegado activado para este paso.');
				      else setStatus('Balón pegado desactivado.');
				      try { scheduleDraftSave('sim-ball-follow'); } catch (e) { /* ignore */ }
				    };
				    const findBallUid = () => {
				      const objects = (canvas.getObjects?.() || []).filter((obj) => obj && !obj?.data?.base);
				      const ball = objects.find((obj) => safeText(obj?.data?.kind) === 'ball');
				      return safeText(ball?.data?.layer_uid);
				    };
				    const ensureBallRoutePass = (fromUid, toUid) => {
				      const step = activeSimulationStep();
				      if (!step) return;
				      const ballUid = findBallUid();
				      if (!ballUid) {
				        setStatus('No hay balón en la pizarra (añade uno).', true);
				        return;
				      }
				      const objByUid = new Map();
				      (canvas.getObjects?.() || []).forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (uid && !obj?.data?.base) objByUid.set(uid, obj);
				      });
				      const fromObj = objByUid.get(fromUid);
				      const toObj = objByUid.get(toUid);
				      if (!fromObj || !toObj) {
				        setStatus('Selecciona 2 fichas (origen y destino).', true);
				        return;
				      }
				      const from = fromObj.getCenterPoint();
				      const to = toObj.getCenterPoint();
				      const mid = {
				        x: (from.x + to.x) / 2,
				        y: (from.y + to.y) / 2 - 60,
				      };
				      const routes = ensureStepRoutes(step);
				      routes[ballUid] = { points: [from, mid, to].map((p) => ({ x: Number(p.x) || 0, y: Number(p.y) || 0 })), spline: true };
				      step.ball_follow_uid = '';
				      renderSimRoutesForStep(step);
				      setStatus('Ruta de pase creada (balón).');
				      try { scheduleDraftSave('sim-ball-pass'); } catch (e) { /* ignore */ }
				    };
				    const setSimPopoverOpen = (open) => {
				      if (!simPopover) return;
				      simPopover.hidden = !open;
				      if (open) syncSimUi();
				    };

				    // Accesos directos desde la pestaña Playbook (modo táctica).
				    // Importante (iPad): el usuario puede pulsar estos botones mientras el JS aún está
				    // inicializando (antes de que `enterSimulation` exista). Evitamos TDZ/ReferenceError
				    // haciendo cola y ejecutando cuando el simulador esté listo.
				    let playbookPendingAction = '';
				    let playbookSimReady = false;
				    const queuePlaybookAction = (action) => {
				      playbookPendingAction = safeText(action);
				      try { setSimPopoverOpen(true); } catch (e) { /* ignore */ }
				      try { setStatus('Cargando simulador…'); } catch (e) { /* ignore */ }
				    };
				    const runPlaybookActionNow = (action) => {
				      const kind = safeText(action);
				      try { if (!isSimulating) enterSimulation(); } catch (e) { /* ignore */ }
				      try { setSimPopoverOpen(true); } catch (e) { /* ignore */ }
				      if (kind === '3d') { try { simView3dBtn?.click(); } catch (e) { /* ignore */ } }
				      if (kind === 'video') { try { simVideoStudioBtn?.click(); } catch (e) { /* ignore */ } }
				      if (kind === 'pack') { try { simPackBtn?.click(); } catch (e) { /* ignore */ } }
				      try {
				        const msg = kind === '3d'
				          ? 'Simulador + Vista 3D abierto.'
				          : kind === 'video'
				            ? 'Simulador + Video Studio abierto.'
				            : kind === 'pack'
				              ? 'Simulador + Pack abierto.'
				              : 'Simulador abierto (usa “Capturar paso” para crear la secuencia).';
				        setStatus(msg);
				      } catch (e) { /* ignore */ }
				      try { document.getElementById('task-sim-toggle')?.focus?.(); } catch (e) { /* ignore */ }
				    };
				    const requestPlaybookAction = (action) => {
				      if (!playbookSimReady) return queuePlaybookAction(action);
				      return runPlaybookActionNow(action);
				    };
				    playbookOpenSimBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      requestPlaybookAction('sim');
				    });
				    playbookOpen3dBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      requestPlaybookAction('3d');
				    });
				    playbookOpenVideoBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      requestPlaybookAction('video');
				    });
				    playbookExportPackBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      requestPlaybookAction('pack');
				    });

				    // Grabación de vídeo (2D) del simulador (pitch + fichas).
				    let simRecordActive = false;
				    let simRecordCanvas = null;
				    let simRecordCtx = null;
				    let simRecordBgImg = null;
				    let simRecordStream = null;
					    let simRecordMedia = null;
					    let simRecordChunks = [];
					    let simRecordFrame = null;
					    let simRecordLayout = null;
					    let simRecordShowTitle = true;
					    let simRecordTitleText = '';

				    const canRecord2d = () => {
				      try {
				        return typeof window.MediaRecorder !== 'undefined'
				          && typeof document?.createElement === 'function'
				          && typeof HTMLCanvasElement !== 'undefined';
				      } catch (e) { return false; }
				    };
					    const simFileSafeSlug = (value) => safeText(value || '')
					      .toLowerCase()
					      .replace(/[^a-z0-9]+/g, '-')
					      .replace(/^-+|-+$/g, '')
					      .slice(0, 60) || 'tactica';
					    const simFitContainRect = (srcW, srcH, dstW, dstH) => {
					      const sw = Math.max(1, Number(srcW) || 1);
					      const sh = Math.max(1, Number(srcH) || 1);
					      const dw = Math.max(1, Number(dstW) || 1);
					      const dh = Math.max(1, Number(dstH) || 1);
					      const scale = Math.min(dw / sw, dh / sh);
					      const w = Math.max(1, Math.round(sw * scale));
					      const h = Math.max(1, Math.round(sh * scale));
					      return { x: Math.round((dw - w) / 2), y: Math.round((dh - h) / 2), w, h };
					    };
					    const simComputeRecordFormat = () => {
					      const raw = safeText(simRecordFormatSelect?.value);
					      if (raw === 'ig_4_5' || raw === 'ig_9_16' || raw === 'match') return raw;
					      return 'match';
					    };
					    const simComputeOutputSize = (format, sourceW, sourceH) => {
					      if (format === 'ig_4_5') return { w: 1080, h: 1350 };
					      if (format === 'ig_9_16') return { w: 1080, h: 1920 };
					      return { w: Math.max(1, Math.round(sourceW)), h: Math.max(1, Math.round(sourceH)) };
					    };

					    const simRecordPrefsKey = (() => {
					      const scope = safeText(form?.dataset?.scopeKey) || 'coach';
					      return `webstats:tpad:simrecord_prefs_v1:${scope}`;
					    })();
					    const simReadRecordPrefs = () => {
					      if (!canUseStorage) return null;
					      try {
					        const raw = safeText(window.localStorage.getItem(simRecordPrefsKey));
					        if (!raw) return null;
					        const parsed = JSON.parse(raw);
					        if (!parsed || typeof parsed !== 'object') return null;
					        return parsed;
					      } catch (e) {
					        return null;
					      }
					    };
					    const simWriteRecordPrefs = (prefs) => {
					      if (!canUseStorage) return;
					      try { window.localStorage.setItem(simRecordPrefsKey, JSON.stringify(prefs || {})); } catch (e) { /* ignore */ }
					    };
					    const simApplyRecordPrefsToUi = () => {
					      const stored = simReadRecordPrefs() || {};
					      const format = safeText(stored?.format) || '';
					      const showTitle = stored?.title !== false;
					      if (simRecordFormatSelect && (format === 'ig_4_5' || format === 'ig_9_16' || format === 'match')) {
					        simRecordFormatSelect.value = format;
					      }
					      if (simRecordTitleInput) simRecordTitleInput.checked = !!showTitle;
					    };
					    const simPersistRecordPrefsFromUi = () => {
					      const prefs = {
					        v: 1,
					        updated_at: new Date().toISOString(),
					        format: simComputeRecordFormat(),
					        title: simRecordTitleInput ? !!simRecordTitleInput.checked : true,
					      };
					      simWriteRecordPrefs(prefs);
					    };
					    simApplyRecordPrefsToUi();
					    const simDownloadBlob = (blob, filename) => {
					      if (!blob) return;
					      const url = URL.createObjectURL(blob);
					      const link = document.createElement('a');
				      link.href = url;
				      link.download = filename || `tactical_${Date.now()}.webm`;
				      document.body.appendChild(link);
				      link.click();
				      link.remove();
				      window.setTimeout(() => {
				        try { URL.revokeObjectURL(url); } catch (e) { /* ignore */ }
				      }, 2500);
				    };

				    const setSimRecordUi = (on) => {
				      simRecordActive = !!on;
				      if (!simRecordBtn) return;
				      simRecordBtn.textContent = simRecordActive ? 'Parar' : 'Grabar vídeo';
				      simRecordBtn.classList.toggle('danger', simRecordActive);
				    };

				    const buildPitchBackgroundImage = async () => {
				      try {
				        if (!svgSurface) return null;
				        const svgMarkup = new XMLSerializer().serializeToString(svgSurface);
				        const blob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' });
				        const blobUrl = URL.createObjectURL(blob);
				        const img = new Image();
				        await new Promise((resolve) => {
				          img.onload = resolve;
				          img.onerror = resolve;
				          img.src = blobUrl;
				        });
				        try { URL.revokeObjectURL(blobUrl); } catch (e) { /* ignore */ }
				        return img;
				      } catch (e) {
				        return null;
				      }
				    };

				    const stopSimRecording = () => {
				      if (simRecordFrame) {
				        try { window.cancelAnimationFrame(simRecordFrame); } catch (e) { /* ignore */ }
				        simRecordFrame = null;
				      }
				      try { simRecordMedia?.stop?.(); } catch (e) { /* ignore */ }
				    };

				    const startSimRecording = async () => {
				      if (!isSimulating) return;
				      if (!canRecord2d()) {
				        window.alert('Tu navegador no soporta grabación aquí. Prueba en Chrome/desktop.');
				        return;
				      }
				      if (!simRecordBtn) return;
				      const base = canvas?.lowerCanvasEl;
					      if (!base) {
					        window.alert('No se pudo iniciar la grabación.');
					        return;
					      }
					      const sourceW = Math.max(1, Math.round(base.width || canvas.getWidth() || 1280));
					      const sourceH = Math.max(1, Math.round(base.height || canvas.getHeight() || 720));
					      const format = simComputeRecordFormat();
					      const out = simComputeOutputSize(format, sourceW, sourceH);
					      const w = out.w;
					      const h = out.h;
					      simRecordShowTitle = simRecordTitleInput ? !!simRecordTitleInput.checked : true;
					      simRecordTitleText = safeText(document.querySelector('[name="draw_task_title"]')?.value || '').replace(/\s+/g, ' ').trim();
					      if (simRecordTitleText.length > 64) simRecordTitleText = `${simRecordTitleText.slice(0, 61)}…`;
					      simRecordLayout = null;
					      if (format === 'ig_4_5' || format === 'ig_9_16') {
					        const margin = Math.round(w * 0.06);
					        const titleH = simRecordShowTitle ? Math.min(260, Math.max(140, Math.round(h * 0.11))) : 0;
					        const availW = Math.max(1, w - margin * 2);
					        const availH = Math.max(1, h - margin * 2 - titleH);
					        const rect = simFitContainRect(sourceW, sourceH, availW, availH);
					        simRecordLayout = {
					          format,
					          margin,
					          titleH,
					          pitchX: margin + rect.x,
					          pitchY: margin + titleH + rect.y,
					          pitchW: rect.w,
					          pitchH: rect.h,
					        };
					      }
				      simRecordCanvas = document.createElement('canvas');
				      simRecordCanvas.width = w;
				      simRecordCanvas.height = h;
				      simRecordCtx = simRecordCanvas.getContext('2d');
				      if (!simRecordCtx) {
				        window.alert('No se pudo iniciar la grabación.');
				        simRecordCanvas = null;
				        return;
				      }
				      simRecordBgImg = await buildPitchBackgroundImage();

				      try {
				        if (typeof simRecordCanvas.captureStream !== 'function') throw new Error('no captureStream');
				        simRecordStream = simRecordCanvas.captureStream(30);
				      } catch (e) {
				        simRecordStream = null;
				      }
				      if (!simRecordStream) {
				        window.alert('No se pudo iniciar la captura de vídeo.');
				        simRecordCanvas = null;
				        simRecordCtx = null;
				        simRecordBgImg = null;
				        return;
				      }

					      const mimeCandidates = [
					        'video/mp4;codecs=h264,aac',
					        'video/mp4',
					        'video/webm;codecs=vp9,opus',
					        'video/webm;codecs=vp8,opus',
					        'video/webm',
					      ];
				      let mimeType = '';
				      mimeCandidates.some((mt) => {
				        try {
				          if (window.MediaRecorder.isTypeSupported(mt)) {
				            mimeType = mt;
				            return true;
				          }
				        } catch (e) { /* ignore */ }
				        return false;
				      });
				      try {
				        simRecordMedia = new window.MediaRecorder(simRecordStream, mimeType ? { mimeType } : undefined);
				      } catch (e) {
				        simRecordMedia = null;
				      }
				      if (!simRecordMedia) {
				        window.alert('No se pudo crear el grabador de vídeo.');
				        try { simRecordStream?.getTracks?.().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
				        simRecordStream = null;
				        simRecordCanvas = null;
				        simRecordCtx = null;
				        simRecordBgImg = null;
				        return;
				      }

				      simRecordChunks = [];
				      simRecordMedia.ondataavailable = (ev) => {
				        if (ev?.data && ev.data.size > 0) simRecordChunks.push(ev.data);
				      };
					      simRecordMedia.onstop = () => {
					        const blob = new Blob(simRecordChunks, { type: simRecordMedia?.mimeType || 'video/webm' });
					        const title = simFileSafeSlug(document.querySelector('[name=\"draw_task_title\"]')?.value || 'tactica');
					        const ext = String(simRecordMedia?.mimeType || '').includes('mp4') ? 'mp4' : 'webm';
					        simDownloadBlob(blob, `${title}-2d.${ext}`);
					        try { simRecordStream?.getTracks?.().forEach((t) => t.stop()); } catch (e) { /* ignore */ }
					        simRecordStream = null;
					        simRecordMedia = null;
				        simRecordChunks = [];
				        simRecordCanvas = null;
				        simRecordCtx = null;
				        simRecordBgImg = null;
				        setSimRecordUi(false);
				      };

					      const drawFrame = () => {
					        if (!simRecordActive || !simRecordCtx || !simRecordCanvas) return;
					        try {
					          const cw = simRecordCanvas.width;
					          const ch = simRecordCanvas.height;
					          simRecordCtx.clearRect(0, 0, cw, ch);
					          // Fondo negro para formatos verticales (estilo IG / presentaciones).
					          simRecordCtx.fillStyle = simRecordLayout ? '#000000' : '#14532d';
					          simRecordCtx.fillRect(0, 0, cw, ch);
					          const drawPitch = (dx, dy, dw, dh) => {
					            if (simRecordBgImg) {
					              simRecordCtx.drawImage(simRecordBgImg, dx, dy, dw, dh);
					            } else {
					              simRecordCtx.fillStyle = '#14532d';
					              simRecordCtx.fillRect(dx, dy, dw, dh);
					            }
					            simRecordCtx.drawImage(base, dx, dy, dw, dh);
					          };
					          if (simRecordLayout) {
					            if (simRecordShowTitle && simRecordTitleText) {
					              const titleY = simRecordLayout.margin + Math.round(simRecordLayout.titleH * 0.62);
					              const maxW = Math.max(1, cw - simRecordLayout.margin * 2);
					              simRecordCtx.save();
					              simRecordCtx.textAlign = 'center';
					              simRecordCtx.textBaseline = 'middle';
					              simRecordCtx.fillStyle = '#ffffff';
					              const baseSize = Math.min(56, Math.max(34, Math.round(ch * 0.038)));
					              let fontSize = baseSize;
					              const measure = () => {
					                simRecordCtx.font = `700 ${fontSize}px system-ui, -apple-system, Segoe UI, Roboto, Arial`;
					                return simRecordCtx.measureText(simRecordTitleText).width;
					              };
					              while (fontSize > 22 && measure() > maxW) fontSize -= 2;
					              simRecordCtx.font = `700 ${fontSize}px system-ui, -apple-system, Segoe UI, Roboto, Arial`;
					              simRecordCtx.fillText(simRecordTitleText, Math.round(cw / 2), titleY, maxW);
					              simRecordCtx.restore();
					            }
					            drawPitch(simRecordLayout.pitchX, simRecordLayout.pitchY, simRecordLayout.pitchW, simRecordLayout.pitchH);
					          } else {
					            drawPitch(0, 0, cw, ch);
					          }
					        } catch (e) { /* ignore */ }
					        simRecordFrame = window.requestAnimationFrame(drawFrame);
					      };

					      try { simRecordMedia.start(250); } catch (e) {
					        window.alert('No se pudo iniciar la grabación.');
				        try { simRecordStream?.getTracks?.().forEach((t) => t.stop()); } catch (err) { /* ignore */ }
				        simRecordStream = null;
				        simRecordMedia = null;
				        simRecordCanvas = null;
				        simRecordCtx = null;
				        simRecordBgImg = null;
					        return;
					      }
					      try { simPersistRecordPrefsFromUi(); } catch (e) { /* ignore */ }
					      setSimRecordUi(true);
					      simRecordFrame = window.requestAnimationFrame(drawFrame);
					    };

				    const toggleSimRecording = async () => {
				      if (simRecordActive) return stopSimRecording();
				      return await startSimRecording();
				    };

				    // Playbook (server): clips guardados por equipo/sistema.
				    const playbookListUrl = safeText(playbookListUrlInput?.value);
				    const playbookSaveUrl = safeText(playbookSaveUrlInput?.value);
				    const playbookDeleteUrl = safeText(playbookDeleteUrlInput?.value);
				    const playbookFavoriteUrl = safeText(playbookFavoriteUrlInput?.value);
				    const playbookCloneUrl = safeText(playbookCloneUrlInput?.value);
				    const playbookTeamsUrl = safeText(playbookTeamsUrlInput?.value);
				    const playbookVersionsUrl = safeText(playbookVersionsUrlInput?.value);
				    const playbookShareUrl = safeText(playbookShareUrlInput?.value);
				    let playbookClips = [];
				    let playbookLoading = false;
				    let playbookLoadedAt = 0;
				    let playbookTeams = [];
				    let playbookTeamsLoadedAt = 0;
				    const playbookFilters = { q: '', folder: '', tag: '', favorites: false, latest: true, version_group: '' };
				    let playbookFilterTimer = null;

					    const TACTICAL_TEMPLATES = [
					      // ABP (acciones a balón parado)
					      {
					        id: 'abp_corner_attack_near',
					        title: 'Córner ofensivo · 1º palo',
					        folder: 'ABP · Córners',
					        tags: ['template', 'abp', 'corner', 'attack'],
					        preset: 'attacking_third',
					        orientation: 'landscape',
					        sequence: [
					          { title: 'Córner ofensivo · 1º palo (inicio)', durationSec: 2 },
					          {
					            title: 'Córner ofensivo · 1º palo (finalización)',
					            durationSec: 4,
					            items: [
					              { type: 'player', slot: 'P1', kind: 'player_local', x: 0.90, y: 0.44 },
					              { type: 'player', slot: 'P2', kind: 'player_local', x: 0.92, y: 0.50 },
					              { type: 'player', slot: 'P3', kind: 'player_local', x: 0.90, y: 0.58 },
					              { type: 'ball', x: 0.88, y: 0.50 },
					            ],
					          },
					        ],
					        items: [
					          { type: 'player', slot: 'GK', kind: 'goalkeeper_local', x: 0.12, y: 0.52 },
					          { type: 'player', slot: 'CB1', kind: 'player_local', x: 0.22, y: 0.48 },
				          { type: 'player', slot: 'CB2', kind: 'player_local', x: 0.22, y: 0.58 },
				          { type: 'player', slot: 'P1', kind: 'player_local', x: 0.78, y: 0.44 },
				          { type: 'player', slot: 'P2', kind: 'player_local', x: 0.84, y: 0.50 },
				          { type: 'player', slot: 'P3', kind: 'player_local', x: 0.80, y: 0.58 },
				          { type: 'player', slot: 'P4', kind: 'player_local', x: 0.70, y: 0.50 },
				          { type: 'rival', label: 'R1', x: 0.86, y: 0.40 },
				          { type: 'rival', label: 'R2', x: 0.88, y: 0.50 },
				          { type: 'rival', label: 'R3', x: 0.86, y: 0.60 },
				          { type: 'ball', x: 0.95, y: 0.20 },
				        ],
				      },
					      {
					        id: 'abp_freekick_wall',
					        title: 'Falta directa · Barrera + portero',
				        folder: 'ABP · Faltas',
				        tags: ['template', 'abp', 'freekick', 'defense'],
				        preset: 'attacking_third',
				        orientation: 'landscape',
				        items: [
				          { type: 'player', slot: 'GK', kind: 'goalkeeper_local', x: 0.10, y: 0.50 },
				          { type: 'player', slot: 'W1', kind: 'player_local', x: 0.26, y: 0.44 },
				          { type: 'player', slot: 'W2', kind: 'player_local', x: 0.26, y: 0.50 },
				          { type: 'player', slot: 'W3', kind: 'player_local', x: 0.26, y: 0.56 },
				          { type: 'rival', label: 'TIRADOR', x: 0.48, y: 0.50 },
				          { type: 'ball', x: 0.44, y: 0.50 },
					        ],
					      },
					      {
					        id: 'abp_corner_defense_zonal',
					        title: 'Córner defensivo · Zonal (base)',
					        folder: 'ABP · Córners',
					        tags: ['template', 'abp', 'corner', 'defense'],
					        preset: 'attacking_third',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'GK', kind: 'goalkeeper_local', x: 0.08, y: 0.50 },
					          { type: 'player', slot: 'Z1', kind: 'player_local', x: 0.76, y: 0.40 },
					          { type: 'player', slot: 'Z2', kind: 'player_local', x: 0.76, y: 0.50 },
					          { type: 'player', slot: 'Z3', kind: 'player_local', x: 0.76, y: 0.60 },
					          { type: 'player', slot: 'P1', kind: 'player_local', x: 0.66, y: 0.46 },
					          { type: 'player', slot: 'P2', kind: 'player_local', x: 0.66, y: 0.54 },
					          { type: 'rival', label: 'R1', x: 0.84, y: 0.40 },
					          { type: 'rival', label: 'R2', x: 0.86, y: 0.50 },
					          { type: 'rival', label: 'R3', x: 0.84, y: 0.60 },
					          { type: 'ball', x: 0.95, y: 0.20 },
					        ],
					      },
					      {
					        id: 'abp_throwin_attack_wide',
					        title: 'Saque de banda · Progresión por carril',
					        folder: 'ABP · Saques',
					        tags: ['template', 'abp', 'throwin', 'attack'],
					        preset: 'half_pitch',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'SB', kind: 'player_local', x: 0.18, y: 0.12 },
					          { type: 'player', slot: 'R1', kind: 'player_local', x: 0.28, y: 0.20 },
					          { type: 'player', slot: 'R2', kind: 'player_local', x: 0.34, y: 0.14 },
					          { type: 'player', slot: 'R3', kind: 'player_local', x: 0.40, y: 0.22 },
					          { type: 'rival', label: 'D1', x: 0.32, y: 0.18 },
					          { type: 'rival', label: 'D2', x: 0.38, y: 0.16 },
					          { type: 'ball', x: 0.14, y: 0.10 },
					        ],
					      },

					      // Salidas / presión / transiciones
					      {
					        id: 'buildout_basic_3',
					        title: 'Salida de balón · 3 + portero (base)',
				        folder: 'Fases · Salida',
				        tags: ['template', 'buildout'],
				        preset: 'defensive_third',
				        orientation: 'landscape',
				        items: [
				          { type: 'player', slot: 'GK', kind: 'goalkeeper_local', x: 0.12, y: 0.50 },
				          { type: 'player', slot: 'CB1', kind: 'player_local', x: 0.24, y: 0.40 },
				          { type: 'player', slot: 'CB2', kind: 'player_local', x: 0.24, y: 0.60 },
				          { type: 'player', slot: 'PIV', kind: 'player_local', x: 0.38, y: 0.50 },
				          { type: 'rival', label: 'R1', x: 0.50, y: 0.44 },
				          { type: 'rival', label: 'R2', x: 0.50, y: 0.56 },
				          { type: 'ball', x: 0.12, y: 0.50 },
				        ],
				      },
					      {
					        id: 'press_high_2v2',
					        title: 'Presión alta · 2v2 (disparo a 1 lado)',
				        folder: 'Fases · Presión',
				        tags: ['template', 'pressing'],
				        preset: 'attacking_third',
				        orientation: 'landscape',
				        items: [
				          { type: 'player', slot: 'ST1', kind: 'player_local', x: 0.70, y: 0.46 },
				          { type: 'player', slot: 'ST2', kind: 'player_local', x: 0.70, y: 0.54 },
				          { type: 'rival', label: 'CB', x: 0.84, y: 0.46 },
				          { type: 'rival', label: 'CB', x: 0.84, y: 0.54 },
				          { type: 'ball', x: 0.84, y: 0.46 },
				        ],
				      },
					      {
					        id: 'transition_3v2',
					        title: 'Transición · 3v2 (contra)',
				        folder: 'Fases · Transición',
				        tags: ['template', 'transition'],
				        preset: 'half_pitch',
				        orientation: 'landscape',
				        items: [
				          { type: 'player', slot: 'A1', kind: 'player_local', x: 0.34, y: 0.50 },
				          { type: 'player', slot: 'A2', kind: 'player_local', x: 0.38, y: 0.40 },
				          { type: 'player', slot: 'A3', kind: 'player_local', x: 0.38, y: 0.60 },
				          { type: 'rival', label: 'D1', x: 0.58, y: 0.46 },
				          { type: 'rival', label: 'D2', x: 0.58, y: 0.54 },
				          { type: 'ball', x: 0.34, y: 0.50 },
					        ],
					      },
					      {
					        id: 'buildout_4_2',
					        title: 'Salida de balón · 4 + 2 (base)',
					        folder: 'Fases · Salida',
					        tags: ['template', 'buildout', 'structure'],
					        preset: 'defensive_third',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'GK', kind: 'goalkeeper_local', x: 0.10, y: 0.50 },
					          { type: 'player', slot: 'LB', kind: 'player_local', x: 0.22, y: 0.22 },
					          { type: 'player', slot: 'CB1', kind: 'player_local', x: 0.22, y: 0.42 },
					          { type: 'player', slot: 'CB2', kind: 'player_local', x: 0.22, y: 0.58 },
					          { type: 'player', slot: 'RB', kind: 'player_local', x: 0.22, y: 0.78 },
					          { type: 'player', slot: 'PIV1', kind: 'player_local', x: 0.38, y: 0.44 },
					          { type: 'player', slot: 'PIV2', kind: 'player_local', x: 0.38, y: 0.56 },
					          { type: 'rival', label: 'R1', x: 0.52, y: 0.42 },
					          { type: 'rival', label: 'R2', x: 0.52, y: 0.58 },
					          { type: 'ball', x: 0.10, y: 0.50 },
					        ],
					      },
					      {
					        id: 'press_midblock_442',
					        title: 'Bloque medio · 4-4-2 (base)',
					        folder: 'Fases · Presión',
					        tags: ['template', 'pressing', 'block', '442'],
					        preset: 'half_pitch',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'ST1', kind: 'player_local', x: 0.55, y: 0.44 },
					          { type: 'player', slot: 'ST2', kind: 'player_local', x: 0.55, y: 0.56 },
					          { type: 'player', slot: 'LM', kind: 'player_local', x: 0.46, y: 0.26 },
					          { type: 'player', slot: 'CM1', kind: 'player_local', x: 0.46, y: 0.44 },
					          { type: 'player', slot: 'CM2', kind: 'player_local', x: 0.46, y: 0.56 },
					          { type: 'player', slot: 'RM', kind: 'player_local', x: 0.46, y: 0.74 },
					          { type: 'player', slot: 'LB', kind: 'player_local', x: 0.34, y: 0.26 },
					          { type: 'player', slot: 'CB1', kind: 'player_local', x: 0.34, y: 0.44 },
					          { type: 'player', slot: 'CB2', kind: 'player_local', x: 0.34, y: 0.56 },
					          { type: 'player', slot: 'RB', kind: 'player_local', x: 0.34, y: 0.74 },
					          { type: 'rival', label: 'MC', x: 0.64, y: 0.50 },
					          { type: 'ball', x: 0.72, y: 0.50 },
					        ],
					      },
					      {
					        id: 'attack_overload_wide_3',
					        title: 'Ataque · Superioridad 3v2 en banda (base)',
					        folder: 'Fases · Ataque',
					        tags: ['template', 'attack', 'overload', 'wide'],
					        preset: 'attacking_third',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'W', kind: 'player_local', x: 0.70, y: 0.18 },
					          { type: 'player', slot: 'FB', kind: 'player_local', x: 0.62, y: 0.26 },
					          { type: 'player', slot: 'CM', kind: 'player_local', x: 0.58, y: 0.34 },
					          { type: 'rival', label: 'D1', x: 0.78, y: 0.26 },
					          { type: 'rival', label: 'D2', x: 0.74, y: 0.34 },
					          { type: 'ball', x: 0.70, y: 0.18 },
					        ],
					      },
					      {
					        id: 'counterpress_5s',
					        title: 'Tras pérdida · Contra-presión 5s (base)',
					        folder: 'Fases · Transición',
					        tags: ['template', 'transition', 'counterpress'],
					        preset: 'half_pitch',
					        orientation: 'landscape',
					        items: [
					          { type: 'player', slot: 'P1', kind: 'player_local', x: 0.52, y: 0.46 },
					          { type: 'player', slot: 'P2', kind: 'player_local', x: 0.54, y: 0.56 },
					          { type: 'player', slot: 'P3', kind: 'player_local', x: 0.44, y: 0.54 },
					          { type: 'player', slot: 'P4', kind: 'player_local', x: 0.44, y: 0.44 },
					          { type: 'rival', label: 'R', x: 0.50, y: 0.50 },
					          { type: 'ball', x: 0.50, y: 0.50 },
					        ],
					      },
					    ];

				    const templateById = (id) => (TACTICAL_TEMPLATES || []).find((t) => safeText(t?.id) === safeText(id));
				    const templateGroups = () => {
				      const groups = new Map();
				      (TACTICAL_TEMPLATES || []).forEach((t) => {
				        const folder = safeText(t?.folder, 'Plantillas');
				        if (!groups.has(folder)) groups.set(folder, []);
				        groups.get(folder).push(t);
				      });
				      Array.from(groups.values()).forEach((arr) => arr.sort((a, b) => safeText(a?.title).localeCompare(safeText(b?.title))));
				      return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
				    };

				    const categorizePlayerForTemplate = (player) => {
				      const pos = safeText(player?.position).toLowerCase();
				      if (!pos) return 'any';
				      if (pos.includes('portero') || pos === 'gk' || pos.includes('goalkeeper')) return 'gk';
				      if (pos.includes('defen') || pos.includes('central') || pos.includes('lateral') || pos.includes('back')) return 'def';
				      if (pos.includes('medio') || pos.includes('centrocamp') || pos.includes('mid')) return 'mid';
				      if (pos.includes('extremo') || pos.includes('banda') || pos.includes('wing')) return 'wing';
				      if (pos.includes('delant') || pos.includes('punta') || pos.includes('striker') || pos.includes('forward')) return 'fwd';
				      return 'any';
				    };
				    const sortRosterForTemplate = (roster) => {
				      const list = Array.isArray(roster) ? roster.slice() : [];
				      list.sort((a, b) => {
				        const na = Number.parseInt(String(a?.number || ''), 10);
				        const nb = Number.parseInt(String(b?.number || ''), 10);
				        if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
				        if (Number.isFinite(na)) return -1;
				        if (Number.isFinite(nb)) return 1;
				        return safeText(a?.name).localeCompare(safeText(b?.name));
				      });
				      return list;
				    };
				    const pickPlayerForSlot = (slot, roster, usedIds) => {
				      const key = safeText(slot).toUpperCase();
				      const list = sortRosterForTemplate(roster);
				      const isUsed = (p) => usedIds && usedIds.has(String(p?.id));
				      const markUsed = (p) => { try { usedIds.add(String(p?.id)); } catch (e) { /* ignore */ } };
				      const byNumber = (() => {
				        const n = Number.parseInt(key, 10);
				        if (!Number.isFinite(n)) return null;
				        return list.find((p) => !isUsed(p) && Number.parseInt(String(p?.number || ''), 10) === n) || null;
				      })();
				      if (byNumber) { markUsed(byNumber); return byNumber; }
				      if (key.includes('GK') || key === 'POR') {
				        const gk = list.find((p) => !isUsed(p) && categorizePlayerForTemplate(p) === 'gk') || list.find((p) => !isUsed(p)) || null;
				        if (gk) markUsed(gk);
				        return gk;
				      }
				      const desired = (() => {
				        if (key.includes('CB') || key.includes('LB') || key.includes('RB') || key.includes('DEF')) return 'def';
				        if (key.includes('DM') || key.includes('CM') || key.includes('MID') || key.includes('PIV')) return 'mid';
				        if (key.includes('LW') || key.includes('RW') || key.includes('W')) return 'wing';
				        if (key.includes('ST') || key.includes('FW') || key.includes('DEL') || key.includes('A')) return 'fwd';
				        return 'any';
				      })();
				      const match = desired === 'any'
				        ? (list.find((p) => !isUsed(p)) || null)
				        : (list.find((p) => !isUsed(p) && categorizePlayerForTemplate(p) === desired) || list.find((p) => !isUsed(p)) || null);
				      if (match) markUsed(match);
				      return match;
				    };
				    const clearCanvasNonBaseObjects = () => {
				      try {
				        (canvas.getObjects?.() || []).slice().forEach((obj) => {
				          if (!obj) return;
				          if (obj?.data?.base) return;
				          try { canvas.remove(obj); } catch (e) { /* ignore */ }
				        });
				      } catch (e) { /* ignore */ }
				      try { canvas.discardActiveObject(); } catch (e) { /* ignore */ }
				      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				      try { schedulePlayerBankUpdate(); } catch (e) { /* ignore */ }
				    };
					    const applyTacticalTemplate = async (template, options = {}) => {
					      const tpl = template && typeof template === 'object' ? template : null;
					      if (!tpl) return;
				      // Asegura simulación.
				      if (!isSimulating) {
				        try { enterSimulation(); } catch (e) { /* ignore */ }
				        await sleep(80);
				      }
				      if (!isSimulating) {
				        setStatus('Activa el modo simulación para aplicar plantillas.', true);
				        return;
				      }
				      try { stopSimulationPlayback(); } catch (e) { /* ignore */ }
				      // Resetea pasos previos y limpia canvas.
				      try {
				        simulationSteps = [];
				        simulationActiveIndex = -1;
				        simulationProCaches = new Map();
				      } catch (e) { /* ignore */ }
				      try { clearCanvasNonBaseObjects(); } catch (e) { /* ignore */ }
				      try {
				        const preset = safeText(tpl?.preset);
				        if (preset) setPreset(preset);
				        const orient = safeText(tpl?.orientation);
				        if (orient && orient !== pitchOrientation) applyPitchOrientation(orient, { preserveObjects: true, pushHistory: false });
				      } catch (e) { /* ignore */ }
				      await sleep(50);

					      const { w, h } = worldSize();
					      const roster = sortRosterForTemplate(players);
					      const used = new Set();
					      const placed = [];

					      const keyForPlaceholder = (value) => safeText(value).trim().toUpperCase();
					      const findPlaceholderOnCanvas = (placeholderKey) => {
					        if (!placeholderKey) return null;
					        const list = (canvas.getObjects?.() || []).filter((obj) => obj && !(obj?.data?.base));
					        return list.find((obj) => keyForPlaceholder(obj?.data?.placeholder_slot) === placeholderKey) || null;
					      };

					      const applyTemplateItems = (items, { reuse = false } = {}) => {
					        (Array.isArray(items) ? items : []).forEach((entry) => {
					          const type = safeText(entry?.type);
					          const x = clamp(Number(entry?.x) || 0.5, 0.03, 0.97) * Math.max(1, Number(w) || 1);
					          const y = clamp(Number(entry?.y) || 0.5, 0.03, 0.97) * Math.max(1, Number(h) || 1);
					          if (type === 'player') {
					            const slot = safeText(entry?.slot, 'P');
					            const placeholderKey = keyForPlaceholder(slot);
					            if (reuse) {
					              const existing = findPlaceholderOnCanvas(placeholderKey);
					              if (existing) {
					                try { existing.set({ left: x, top: y }); } catch (e) { /* ignore */ }
					                try { existing.setCoords?.(); } catch (e) { /* ignore */ }
					                placed.push(existing);
					                return;
					              }
					            }
					            const player = pickPlayerForSlot(slot, roster, used);
					            const kind = safeText(entry?.kind, 'player_local');
					            const factory = playerTokenFactory(kind, player || { name: slot, number: slot }, { style: normalizeTokenStyle(tokenGlobalStyle) });
					            const obj = factory(x, y);
					            if (obj) {
					              obj.data = { ...(obj.data || {}), placeholder_slot: slot };
					              try { canvas.add(obj); } catch (e) { /* ignore */ }
					              placed.push(obj);
					            }
					            return;
					          }
					          if (type === 'rival') {
					            const label = safeText(entry?.label, 'R');
					            const placeholderKey = keyForPlaceholder(label);
					            if (reuse) {
					              const existing = findPlaceholderOnCanvas(placeholderKey);
					              if (existing) {
					                try { existing.set({ left: x, top: y }); } catch (e) { /* ignore */ }
					                try { existing.setCoords?.(); } catch (e) { /* ignore */ }
					                placed.push(existing);
					                return;
					              }
					            }
					            const factory = playerTokenFactory('player_rival', { name: 'Rival', number: label }, { style: 'disk' });
					            const obj = factory(x, y);
					            if (obj) {
					              obj.data = { ...(obj.data || {}), placeholder_slot: label };
					              try { canvas.add(obj); } catch (e) { /* ignore */ }
					              placed.push(obj);
					            }
					            return;
					          }
					          if (type === 'ball') {
					            const placeholderKey = 'BALL';
					            if (reuse) {
					              const existing = findPlaceholderOnCanvas(placeholderKey);
					              if (existing) {
					                try { existing.set({ left: x, top: y }); } catch (e) { /* ignore */ }
					                try { existing.setCoords?.(); } catch (e) { /* ignore */ }
					                placed.push(existing);
					                return;
					              }
					            }
					            try {
					              const f = simpleFactory('ball');
					              const obj = typeof f === 'function' ? f(x, y) : null;
					              if (obj) {
					                obj.data = { ...(obj.data || {}), placeholder_slot: 'BALL' };
					                try { canvas.add(obj); } catch (e) { /* ignore */ }
					                placed.push(obj);
					              }
					            } catch (e) { /* ignore */ }
					          }
					        });
					      };

					      const seq = (Array.isArray(tpl.sequence) ? tpl.sequence : []).filter((s) => s && typeof s === 'object').slice(0, 8);
					      const frames = seq.length ? seq : [{ title: safeText(tpl.title, 'Plantilla'), durationSec: Number(options.durationSec) || 5, items: Array.isArray(tpl.items) ? tpl.items : [] }];
					      for (let i = 0; i < frames.length; i += 1) {
					        const frame = frames[i] || {};
					        const frameItems = Array.isArray(frame.items) ? frame.items : (Array.isArray(tpl.items) ? tpl.items : []);
					        applyTemplateItems(frameItems, { reuse: i > 0 });
					        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
					        try { ensureLayerUidsOnCanvas(); } catch (e) { /* ignore */ }
					        try { captureSimulationStep(); } catch (e) { /* ignore */ }
					        try {
					          if (simulationSteps.length) {
					            const idx = simulationSteps.length - 1;
					            simulationSteps[idx].title = safeText(frame.title, safeText(tpl.title, simulationSteps[idx].title));
					            simulationSteps[idx].duration = clamp(Number(frame.durationSec) || Number(options.durationSec) || 5, 1, 20);
					            simulationActiveIndex = idx;
					            renderSimulationSteps();
					            // eslint-disable-next-line no-await-in-loop
					            await selectSimulationStep(idx);
					          }
					        } catch (e) { /* ignore */ }
					      }

					      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
					      try { ensureLayerUidsOnCanvas(); } catch (e) { /* ignore */ }
					      try { renderClipsLibrary(); } catch (e) { /* ignore */ }
					      setStatus(`Plantilla aplicada: ${safeText(tpl.title)}`);
					      return { ok: true, placed: placed.length };
					    };

				    const fetchPlaybookClips = async (options = {}) => {
				      if (!playbookListUrl) return [];
				      if (playbookLoading) return playbookClips || [];
				      const now = Date.now();
				      const ttl = clamp(Number(options.ttlMs) || 20_000, 5_000, 120_000);
				      if (!options.force && playbookLoadedAt && (now - playbookLoadedAt) < ttl) return playbookClips || [];
				      playbookLoading = true;
				      try {
				        const url = new URL(playbookListUrl, window.location.origin);
				        url.searchParams.set('scope', 'team');
				        url.searchParams.set('include_system', '1');
				        const q = safeText(options.q ?? playbookFilters.q);
				        const folder = safeText(options.folder ?? playbookFilters.folder);
				        const tag = safeText(options.tag ?? playbookFilters.tag);
				        const favorites = !!(options.favorites ?? playbookFilters.favorites);
				        const latest = (options.latest ?? playbookFilters.latest);
				        const versionGroup = safeText(options.version_group ?? playbookFilters.version_group);
				        if (q) url.searchParams.set('q', q.slice(0, 120));
				        if (folder) url.searchParams.set('folder', folder.slice(0, 80));
				        if (tag) url.searchParams.set('tag', tag.slice(0, 32));
				        if (favorites) url.searchParams.set('favorites', '1');
				        url.searchParams.set('latest', (latest === false) ? '0' : '1');
				        if (versionGroup) url.searchParams.set('version_group', versionGroup);
				        const resp = await fetch(url.toString(), { credentials: 'same-origin' });
				        const data = await resp.json().catch(() => ({}));
				        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo cargar Playbook.');
				        const items = Array.isArray(data?.items) ? data.items : [];
				        playbookClips = items.slice(0, 120);
				        playbookLoadedAt = Date.now();
				        return playbookClips;
				      } catch (e) {
				        if (!options.silent) setStatus(e?.message || 'Error al cargar Playbook.', true);
				        playbookClips = [];
				        playbookLoadedAt = Date.now();
				        return [];
				      } finally {
				        playbookLoading = false;
				      }
				    };

				    const fetchPlaybookTeams = async (options = {}) => {
				      if (!playbookTeamsUrl) return [];
				      const now = Date.now();
				      const ttl = clamp(Number(options.ttlMs) || 60_000, 10_000, 300_000);
				      if (!options.force && playbookTeamsLoadedAt && (now - playbookTeamsLoadedAt) < ttl) return playbookTeams || [];
				      try {
				        const resp = await fetch(playbookTeamsUrl, { credentials: 'same-origin' });
				        const data = await resp.json().catch(() => ({}));
				        if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo cargar equipos.');
				        playbookTeams = Array.isArray(data?.items) ? data.items : [];
				        playbookTeamsLoadedAt = Date.now();
				        return playbookTeams;
				      } catch (e) {
				        playbookTeams = [];
				        playbookTeamsLoadedAt = Date.now();
				        if (!options.silent) setStatus(e?.message || 'Error al cargar equipos.', true);
				        return [];
				      }
				    };

				    const savePlaybookClip = async (payload) => {
				      if (!playbookSaveUrl) throw new Error('Playbook no disponible.');
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      const resp = await fetch(playbookSaveUrl, {
				        method: 'POST',
				        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
				        credentials: 'same-origin',
				        body: JSON.stringify(payload || {}),
				      });
				      const data = await resp.json().catch(() => ({}));
				      if (resp.status === 409 && safeText(data?.error) === 'exists') {
				        const okOverwrite = window.confirm('Ya existe un clip con ese nombre en el Playbook. ¿Sobrescribir?');
				        if (okOverwrite) return await savePlaybookClip({ ...(payload || {}), overwrite: 1 });
				        const okVersion = window.confirm('¿Guardar como nueva versión (v2/v3) sin sobrescribir?');
				        if (!okVersion) return { ok: false, canceled: true };
				        return await savePlaybookClip({ ...(payload || {}), new_version: 1 });
				      }
				      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo guardar.');
				      return data;
				    };

				    const togglePlaybookFavorite = async (id) => {
				      if (!playbookFavoriteUrl) throw new Error('Favoritos no disponible.');
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      const resp = await fetch(playbookFavoriteUrl, {
				        method: 'POST',
				        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
				        credentials: 'same-origin',
				        body: JSON.stringify({ id: Number(id) || 0 }),
				      });
				      const data = await resp.json().catch(() => ({}));
				      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo actualizar.');
				      return data;
				    };

				    const createPlaybookShareLink = async (id) => {
				      if (!playbookShareUrl) throw new Error('Compartir no disponible.');
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      const body = new URLSearchParams();
				      body.set('id', String(Number(id) || 0));
				      body.set('valid_days', '30');
				      const resp = await fetch(playbookShareUrl, {
				        method: 'POST',
				        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
				        credentials: 'same-origin',
				        body: body.toString(),
				      });
				      const data = await resp.json().catch(() => ({}));
				      if (!resp.ok || !data?.ok || !data?.url) throw new Error(data?.error || 'No se pudo crear el enlace.');
				      return data;
				    };

				    const clonePlaybookClip = async (id, toTeamId, options = {}) => {
				      if (!playbookCloneUrl) throw new Error('Clonar no disponible.');
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      const resp = await fetch(playbookCloneUrl, {
				        method: 'POST',
				        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
				        credentials: 'same-origin',
				        body: JSON.stringify({ id: Number(id) || 0, to_team_id: Number(toTeamId) || 0, ...(options || {}) }),
				      });
				      const data = await resp.json().catch(() => ({}));
				      if (resp.status === 409 && safeText(data?.error) === 'exists') {
				        const okOverwrite = window.confirm('Ya existe un clip con ese nombre en el equipo destino. ¿Sobrescribir?');
				        if (okOverwrite) return await clonePlaybookClip(id, toTeamId, { overwrite: 1 });
				        const okVersion = window.confirm('¿Clonar como nueva versión (v2/v3) sin sobrescribir?');
				        if (!okVersion) return { ok: false, canceled: true };
				        return await clonePlaybookClip(id, toTeamId, { new_version: 1 });
				      }
				      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo clonar.');
				      return data;
				    };

				    const deletePlaybookClip = async (id, scope) => {
				      if (!playbookDeleteUrl) throw new Error('Playbook no disponible.');
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      const resp = await fetch(playbookDeleteUrl, {
				        method: 'POST',
				        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
				        credentials: 'same-origin',
				        body: JSON.stringify({ id: Number(id) || 0, scope: safeText(scope || 'team') }),
				      });
				      const data = await resp.json().catch(() => ({}));
				      if (!resp.ok || !data?.ok) throw new Error(data?.error || 'No se pudo borrar.');
				      return data;
				    };

				    const readClipsLibrary = () => {
				      if (!canUseStorage) return [];
				      try {
				        const raw = safeText(window.localStorage.getItem(clipsStorageKey));
				        const parsed = raw ? JSON.parse(raw) : null;
				        const items = Array.isArray(parsed?.items) ? parsed.items : [];
				        return items.filter((it) => it && typeof it === 'object').slice(0, 40);
				      } catch (e) {
				        return [];
				      }
				    };
				    const writeClipsLibrary = (items) => {
				      if (!canUseStorage) return;
				      try {
				        const safeItems = Array.isArray(items) ? items.slice(0, 40) : [];
				        window.localStorage.setItem(clipsStorageKey, JSON.stringify({ v: 1, updated_at: new Date().toISOString(), items: safeItems }));
				      } catch (e) { /* ignore */ }
				    };

				    // Si existe la pestaña lateral Playbook (modo táctica), hacemos que la librería de clips
				    // viva ahí (en lugar de quedar "escondida" dentro del simulador).
				    // Reutilizamos el mismo contenedor (`simClipsList`) para no duplicar DOM ni listeners.
				    try {
				      if (playbookPaneEl && simClipsList && isTacticsMode) {
				        dockSimPopoverIfNeeded();
				        const dock = ensurePlaybookDock();
				        const clipsHost = ensureDockSection(dock, 'task-playbook-clips-host', 'Clips');
				        if (clipsHost && simClipsList.parentElement !== clipsHost) {
				          clipsHost.appendChild(simClipsList);
				        }
				        simClipsList.hidden = false;
				      } else if (playbookPaneEl && simClipsList && simClipsList.parentElement !== playbookPaneEl) {
				        playbookPaneEl.innerHTML = '';
				        playbookPaneEl.appendChild(simClipsList);
				        simClipsList.hidden = false;
				      }
				    } catch (e) { /* ignore */ }
					    const renderClipsLibrary = () => {
					      if (!simClipsList) return;
					      const clips = readClipsLibrary();
					      const applyClipPro = (clip) => {
					        simulationProTracks = {};
					        simulationProEnabled = false;
					        simulationProLoop = true;
					        simulationProTimeMs = 0;
					        simulationProUpdatedAt = Date.now();
					        simulationProCaches = new Map();
					        const pro = clip?.pro && typeof clip.pro === 'object' ? clip.pro : null;
					        if (pro) {
					          simulationProEnabled = pro.enabled !== false;
					          simulationProLoop = pro.loop !== false;
					          const tracks = pro.tracks && typeof pro.tracks === 'object' ? pro.tracks : {};
					          const safeTracks = {};
					          Object.entries(tracks).slice(0, 240).forEach(([uid, list]) => {
					            if (!uid) return;
					            if (!Array.isArray(list)) return;
					            const cleaned = list
					              .map((kf) => {
					                const t_ms = clamp(Number(kf?.t_ms) || 0, 0, 3_600_000);
					                const props = kf?.props && typeof kf.props === 'object' ? kf.props : null;
					                if (!props) return null;
					                return {
					                  t_ms,
					                  easing: normalizeEasing(kf?.easing),
					                  props: {
					                    left: Number(props.left) || 0,
					                    top: Number(props.top) || 0,
					                    angle: Number(props.angle) || 0,
					                    scaleX: clampScale(Number(props.scaleX) || 1),
					                    scaleY: clampScale(Number(props.scaleY) || 1),
					                    opacity: props.opacity == null ? 1 : Number(props.opacity),
					                  },
					                };
					              })
					              .filter(Boolean)
					              .sort((a, b) => (a.t_ms - b.t_ms))
					              .slice(0, 240);
					            if (cleaned.length) safeTracks[uid] = cleaned;
					          });
					          simulationProTracks = safeTracks;
					        }
					        try { persistSimulationProToStorage(); } catch (e) { /* ignore */ }
					      };
				      const templatesSection = (() => {
				        const groups = templateGroups();
				        if (!groups.length) return '';
				        const optionsHtml = groups.map(([folder, items]) => `
				          <optgroup label="${escapeHtml(folder)}">
				            ${(items || []).map((t) => `<option value="${escapeHtml(t.id)}">${escapeHtml(t.title)}</option>`).join('')}
				          </optgroup>
				        `).join('');
				        return `
				          <div class="timeline-empty" style="opacity:0.92; margin:0.55rem 0 0.35rem;">Plantillas tácticas (ABP / fases)</div>
				          <div style="display:flex; flex-wrap:wrap; gap:0.45rem; align-items:center; margin:0.3rem 0 0.75rem;">
				            <select id="task-template-select" style="flex:1; min-width:220px; padding:0.55rem 0.75rem; border-radius:999px; border:1px solid rgba(148,163,184,0.18); background:rgba(255,255,255,0.04); color:#e7ebf3;">
				              ${optionsHtml}
				            </select>
				            <button type="button" class="button" id="task-template-apply">Aplicar</button>
				            <button type="button" class="button" id="task-template-save">Guardar → Playbook</button>
				          </div>
				          <div class="meta" style="margin:-0.3rem 0 0.6rem; opacity:0.88;">Rellena automáticamente con tu plantilla (dorsales/posiciones) y deja rivales genéricos.</div>
				        `;
				      })();
				      const playbookRows = (() => {
				        if (!Array.isArray(playbookClips) || !playbookClips.length) return '';
				        const folders = Array.from(new Set(playbookClips.map((c) => safeText(c?.folder)).filter(Boolean))).slice(0, 24);
				        const tags = (() => {
				          const acc = new Set();
				          playbookClips.forEach((c) => {
				            const ts = Array.isArray(c?.tags) ? c.tags : [];
				            ts.forEach((t) => {
				              const tt = safeText(t).trim();
				              if (tt) acc.add(tt);
				            });
				          });
				          return Array.from(acc).slice(0, 36);
				        })();
				        const controls = `
				          <div style="display:flex; flex-wrap:wrap; gap:0.45rem; align-items:center; margin:0.55rem 0 0.55rem;">
				            <input type="search" id="task-playbook-q" placeholder="Buscar…" value="${escapeHtml(playbookFilters.q || '')}" style="flex:1; min-width:180px; padding:0.55rem 0.75rem; border-radius:999px; border:1px solid rgba(148,163,184,0.18); background:rgba(255,255,255,0.04); color:#e7ebf3;" />
				            <select id="task-playbook-folder" style="padding:0.55rem 0.75rem; border-radius:999px; border:1px solid rgba(148,163,184,0.18); background:rgba(255,255,255,0.04); color:#e7ebf3;">
				              <option value="">Carpeta</option>
				              ${folders.map((f) => `<option value="${escapeHtml(f)}" ${f === playbookFilters.folder ? 'selected' : ''}>${escapeHtml(f)}</option>`).join('')}
				            </select>
				            <select id="task-playbook-tag" style="padding:0.55rem 0.75rem; border-radius:999px; border:1px solid rgba(148,163,184,0.18); background:rgba(255,255,255,0.04); color:#e7ebf3;">
				              <option value="">Tag</option>
				              ${tags.map((t) => `<option value="${escapeHtml(t)}" ${t === playbookFilters.tag ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
				            </select>
				            <label style="display:flex; gap:0.35rem; align-items:center; font-weight:900; letter-spacing:0.02em; opacity:0.9;">
				              <input type="checkbox" id="task-playbook-favorites" ${playbookFilters.favorites ? 'checked' : ''} />
				              Fav
				            </label>
				            <label style="display:flex; gap:0.35rem; align-items:center; font-weight:900; letter-spacing:0.02em; opacity:0.9;">
				              <input type="checkbox" id="task-playbook-latest" ${playbookFilters.latest ? 'checked' : ''} />
				              Última
				            </label>
				            <button type="button" class="button" id="task-playbook-refresh">Actualizar</button>
				            ${playbookFilters.version_group ? `<button type="button" class="button" id="task-playbook-clear-group">← Grupo</button>` : ''}
				          </div>
				        `;
				        const rows = playbookClips.slice(0, 80).map((clip) => {
				          const pid = Number(clip?.id) || 0;
				          if (!pid) return '';
				          const name = safeText(clip?.name, `Clip ${pid}`);
				          const scope = safeText(clip?.scope, 'team');
				          const when = safeText(clip?.updated_at || clip?.created_at, '');
				          const canDel = !!clip?.can_delete;
				          const canEdit = !!clip?.can_edit;
				          const isFav = !!clip?.is_favorite;
				          const scopeLabel = scope === 'system' ? 'Sistema' : 'Equipo';
				          const folderLabel = safeText(clip?.folder);
				          const tagLabels = (Array.isArray(clip?.tags) ? clip.tags : []).slice(0, 6).map((t) => safeText(t)).filter(Boolean);
				          const vNum = Number(clip?.version_number) || 1;
				          const vCount = Number(clip?.version_count) || 1;
				          const vLabel = vCount > 1 ? `v${vNum}/${vCount}` : `v${vNum}`;
				          const group = safeText(clip?.version_group);
				          return `
				            <div class="sim-step" style="display:flex; align-items:center; justify-content:space-between; gap:0.75rem;">
				              <div style="display:flex; flex-direction:column; gap:0.1rem;">
				                <strong>${name}</strong>
				                <span>
				                  ${scopeLabel}${when ? ` · ${when.slice(0, 10)}` : ''} · <span style="opacity:0.9; font-weight:900;">${vLabel}</span>
				                  ${folderLabel ? ` · <span style="opacity:0.8;">${escapeHtml(folderLabel)}</span>` : ''}
				                  ${tagLabels.length ? ` · <span style="opacity:0.75;">${tagLabels.map((t) => `#${escapeHtml(t)}`).join(' ')}</span>` : ''}
				                </span>
				              </div>
				              <div style="display:flex; gap:0.4rem; flex-wrap:wrap;">
				                <button type="button" class="button" data-playbook-fav="${pid}" title="Favorito">${isFav ? '★' : '☆'}</button>
				                <button type="button" class="button" data-playbook-load="${pid}">Cargar</button>
				                <button type="button" class="button" data-playbook-export="${pid}">Export</button>
				                <button type="button" class="button" data-playbook-share="${pid}">Link</button>
				                <button type="button" class="button" data-playbook-clone="${pid}">Clonar</button>
				                ${(vCount > 1 && group) ? `<button type="button" class="button" data-playbook-group="${escapeHtml(group)}">Versiones</button>` : ''}
				                ${canEdit ? `<button type="button" class="button" data-playbook-edit="${pid}">Editar</button>` : ''}
				                ${canDel ? `<button type="button" class="button danger" data-playbook-delete="${pid}" data-playbook-scope="${scope}">Borrar</button>` : ''}
				              </div>
				            </div>
				          `;
				        }).filter(Boolean).join('');
				        if (!rows) return '';
				        return `
				          <div class="timeline-empty" style="opacity:0.92; margin:0.85rem 0 0.35rem;">Playbook (equipo/sistema)</div>
				          ${controls}
				          ${rows}
				        `;
				      })();

				      if (!clips.length && !playbookRows) {
				        simClipsList.innerHTML = `
				          ${templatesSection}
				          <div class="timeline-empty" style="opacity:0.92; margin:0.75rem 0 0.35rem;">Clips: todavía no hay ninguno.</div>
				          <div class="meta" style="opacity:0.88; margin:0 0 0.6rem;">
				            Para crear el primero: <strong>Simulador</strong> → <strong>Entrar en simulación</strong> → <strong>Capturar paso</strong> → <strong>Guardar clip</strong>.
				          </div>
				          <div style="display:flex; gap:0.45rem; flex-wrap:wrap; align-items:center; margin:0.2rem 0 0.85rem;">
				            <button type="button" class="button primary" id="task-playbook-first-open">Abrir simulador</button>
				            <button type="button" class="button" id="task-playbook-first-capture">Capturar paso</button>
				            <button type="button" class="button" id="task-playbook-first-save">Guardar clip</button>
				          </div>
				        `;
				        const firstOpen = simClipsList.querySelector('#task-playbook-first-open');
				        const firstCapture = simClipsList.querySelector('#task-playbook-first-capture');
				        const firstSave = simClipsList.querySelector('#task-playbook-first-save');
				        const openSim = () => {
				          try {
				            if (!isSimulating) enterSimulation();
				          } catch (e) { /* ignore */ }
				          try { setSimPopoverOpen(true); } catch (e) { /* ignore */ }
				        };
				        firstOpen?.addEventListener('click', () => openSim());
				        firstCapture?.addEventListener('click', () => { openSim(); try { simCaptureBtn?.click(); } catch (e) { /* ignore */ } });
				        firstSave?.addEventListener('click', () => { openSim(); try { simClipSaveBtn?.click(); } catch (e) { /* ignore */ } });
				        return;
				      }
				      const rows = clips.map((clip, index) => {
				        const name = safeText(clip?.name, `Clip ${index + 1}`);
				        const when = safeText(clip?.created_at, '');
				        return `
				          <div class="sim-step" style="display:flex; align-items:center; justify-content:space-between; gap:0.75rem;">
				            <div style="display:flex; flex-direction:column; gap:0.1rem;">
				              <strong>${name}</strong>
				              <span>${when ? when.slice(0, 10) : ''}</span>
				            </div>
				            <div style="display:flex; gap:0.4rem; flex-wrap:wrap;">
				              <button type="button" class="button" data-clip-load="${index}">Cargar</button>
				              <button type="button" class="button" data-clip-export="${index}">Export</button>
				              <button type="button" class="button danger" data-clip-delete="${index}">Borrar</button>
				            </div>
				          </div>
				        `;
				      }).join('');
				      simClipsList.innerHTML = `
				        ${templatesSection}
				        <div class="timeline-empty" style="opacity:0.92; margin-bottom:0.35rem;">Clips guardados (local)</div>
				        ${rows}
				        ${playbookRows}
				      `;
				      const templateSelect = simClipsList.querySelector('#task-template-select');
				      const templateApplyBtn = simClipsList.querySelector('#task-template-apply');
				      const templateSaveBtn = simClipsList.querySelector('#task-template-save');
				      templateApplyBtn?.addEventListener('click', async () => {
				        const id = safeText(templateSelect?.value);
				        const tpl = templateById(id) || templateById('abp_corner_attack_near');
				        try { await applyTacticalTemplate(tpl, { durationSec: 6 }); } catch (e) { /* ignore */ }
				      });
				      templateSaveBtn?.addEventListener('click', async () => {
				        const id = safeText(templateSelect?.value);
				        const tpl = templateById(id) || templateById('abp_corner_attack_near');
				        if (!tpl) return;
				        try {
				          await applyTacticalTemplate(tpl, { durationSec: 6 });
				          const name = safeText(window.prompt('Nombre del clip', safeText(tpl.title, 'Plantilla')));
				          if (!name) return;
				          const payloadSteps = Array.isArray(simulationSteps) ? simulationSteps.slice() : [];
				          if (!payloadSteps.length) {
				            setStatus('No hay pasos para guardar.', true);
				            return;
				          }
				          const scope = 'team';
				          const folder = safeText(tpl.folder, '').slice(0, 80);
				          const tags = (Array.isArray(tpl.tags) ? tpl.tags : []).slice(0, 12);
				          await savePlaybookClip({ scope, name: name.slice(0, 160), folder, tags, steps: payloadSteps });
				          await fetchPlaybookClips({ force: true, silent: true });
				          renderClipsLibrary();
				          setStatus('Plantilla guardada en Playbook.');
				        } catch (e) {
				          setStatus(e?.message || 'No se pudo guardar.', true);
				        }
				      });
				      Array.from(simClipsList.querySelectorAll('[data-clip-load]')).forEach((btn) => {
				        btn.addEventListener('click', () => {
				          const idx = clamp(Number(btn.getAttribute('data-clip-load') || 0), 0, Math.max(0, clips.length - 1));
				          const clip = clips[idx];
				          const steps = Array.isArray(clip?.steps) ? clip.steps : [];
				          if (!steps.length) return;
					          if (simulationPlaying) stopSimulationPlayback();
					          try { simulationSavedSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSavedSteps = steps.slice(); }
					          simulationSavedUpdatedAt = Date.now();
					          try { simulationSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSteps = steps.slice(); }
					          try { applyClipPro(clip); } catch (e) { /* ignore */ }
					          simulationActiveIndex = clamp(0, 0, Math.max(0, simulationSteps.length - 1));
					          renderSimulationSteps();
					          void selectSimulationStep(simulationActiveIndex);
					          try {
					            if (simulationProEnabled) {
					              renderSimulationAtTimeMs(0);
					              syncSimProUi();
					            }
					          } catch (e) { /* ignore */ }
					          syncSimUi();
					          setStatus(`Clip cargado: ${safeText(clip?.name, '')}`);
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-clip-delete]')).forEach((btn) => {
				        btn.addEventListener('click', () => {
				          const idx = clamp(Number(btn.getAttribute('data-clip-delete') || 0), 0, Math.max(0, clips.length - 1));
				          const name = safeText(clips[idx]?.name);
				          const ok = window.confirm(`¿Borrar el clip “${name || 'sin nombre'}”?`);
				          if (!ok) return;
				          const next = clips.slice();
				          next.splice(idx, 1);
				          writeClipsLibrary(next);
				          renderClipsLibrary();
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-clip-export]')).forEach((btn) => {
				        btn.addEventListener('click', () => {
					          const idx = clamp(Number(btn.getAttribute('data-clip-export') || 0), 0, Math.max(0, clips.length - 1));
					          const clip = clips[idx];
					          const payload = { v: 1, name: safeText(clip?.name), created_at: safeText(clip?.created_at), steps: clip?.steps || [], pro: clip?.pro || null };
					          const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
					          downloadBlob(blob, `${fileSafeSlug(payload.name || 'clip')}.json`);
				        });
				      });

				      Array.from(simClipsList.querySelectorAll('[data-playbook-load]')).forEach((btn) => {
				        btn.addEventListener('click', () => {
				          const id = Number(btn.getAttribute('data-playbook-load') || 0);
				          const clip = (playbookClips || []).find((it) => Number(it?.id) === id);
				          const steps = Array.isArray(clip?.steps) ? clip.steps : [];
				          if (!steps.length) return;
				          if (simulationPlaying) stopSimulationPlayback();
				          try { simulationSavedSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSavedSteps = steps.slice(); }
				          simulationSavedUpdatedAt = Date.now();
				          try { simulationSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSteps = steps.slice(); }
				          simulationActiveIndex = clamp(0, 0, Math.max(0, simulationSteps.length - 1));
				          renderSimulationSteps();
				          void selectSimulationStep(simulationActiveIndex);
				          syncSimUi();
				          setStatus(`Clip cargado (Playbook): ${safeText(clip?.name, '')}`);
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-delete]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const id = Number(btn.getAttribute('data-playbook-delete') || 0);
				          const scope = safeText(btn.getAttribute('data-playbook-scope') || 'team');
				          const clip = (playbookClips || []).find((it) => Number(it?.id) === id);
				          const name = safeText(clip?.name);
				          const ok = window.confirm(`¿Borrar el clip del Playbook “${name || id}”?`);
				          if (!ok) return;
				          try {
				            await deletePlaybookClip(id, scope);
				            await fetchPlaybookClips({ force: true, silent: true });
				            renderClipsLibrary();
				            setStatus('Clip borrado (Playbook).');
				          } catch (e) {
				            setStatus(e?.message || 'No se pudo borrar.', true);
				          }
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-export]')).forEach((btn) => {
				        btn.addEventListener('click', () => {
				          const id = Number(btn.getAttribute('data-playbook-export') || 0);
				          const clip = (playbookClips || []).find((it) => Number(it?.id) === id);
				          const steps = clip?.steps || [];
				          if (!Array.isArray(steps) || !steps.length) return;
				          const payload = { v: 1, name: safeText(clip?.name), created_at: safeText(clip?.created_at), updated_at: safeText(clip?.updated_at), steps };
				          const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
				          downloadBlob(blob, `${fileSafeSlug(payload.name || 'clip')}.json`);
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-fav]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const id = Number(btn.getAttribute('data-playbook-fav') || 0);
				          if (!id) return;
				          try {
				            const res = await togglePlaybookFavorite(id);
				            const isFav = !!res?.is_favorite;
				            playbookClips = (playbookClips || []).map((c) => (Number(c?.id) === id ? { ...(c || {}), is_favorite: isFav } : c));
				            renderClipsLibrary();
				          } catch (e) {
				            setStatus(e?.message || 'No se pudo actualizar favorito.', true);
				          }
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-share]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const id = Number(btn.getAttribute('data-playbook-share') || 0);
				          if (!id) return;
				          try {
				            const res = await createPlaybookShareLink(id);
				            const url = safeText(res?.url);
				            try { await navigator.clipboard?.writeText(url); } catch (e) { /* ignore */ }
				            window.prompt('Enlace de solo lectura (copiado si es posible):', url);
				          } catch (e) {
				            setStatus(e?.message || 'No se pudo crear enlace.', true);
				          }
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-clone]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const id = Number(btn.getAttribute('data-playbook-clone') || 0);
				          if (!id) return;
				          try {
				            const teams = await fetchPlaybookTeams({ force: false, silent: true });
				            const list = (teams || []).map((t) => `${Number(t?.id) || ''}: ${safeText(t?.name)}`).filter(Boolean).join('\\n');
				            const defId = Number((teams || []).find((t) => !!t?.is_default)?.id) || Number((teams || [])[0]?.id) || 0;
				            const raw = window.prompt(`Clonar a equipo (id):\\n${list}`, defId ? String(defId) : '');
				            const toId = Number(raw || 0);
				            if (!toId) return;
				            const res = await clonePlaybookClip(id, toId, {});
				            if (res?.canceled) return;
				            setStatus('Clip clonado.');
				          } catch (e) {
				            setStatus(e?.message || 'No se pudo clonar.', true);
				          }
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-edit]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const id = Number(btn.getAttribute('data-playbook-edit') || 0);
				          const clip = (playbookClips || []).find((it) => Number(it?.id) === id);
				          if (!clip) return;
				          const folder = safeText(window.prompt('Carpeta (opcional)', safeText(clip?.folder))).slice(0, 80);
				          const tagsRaw = safeText(window.prompt('Tags (coma separada)', (Array.isArray(clip?.tags) ? clip.tags.join(', ') : ''))).slice(0, 160);
				          const tags = tagsRaw.split(',').map((t) => safeText(t).trim()).filter(Boolean).slice(0, 12);
				          try {
				            await savePlaybookClip({ scope: safeText(clip?.scope || 'team'), id, name: safeText(clip?.name).slice(0, 160), folder, tags, steps: clip?.steps || [] });
				            await fetchPlaybookClips({ force: true, silent: true });
				            renderClipsLibrary();
				            setStatus('Clip actualizado.');
				          } catch (e) {
				            setStatus(e?.message || 'No se pudo actualizar.', true);
				          }
				        });
				      });
				      Array.from(simClipsList.querySelectorAll('[data-playbook-group]')).forEach((btn) => {
				        btn.addEventListener('click', async () => {
				          const group = safeText(btn.getAttribute('data-playbook-group') || '');
				          if (!group) return;
				          playbookFilters.version_group = group;
				          playbookFilters.latest = false;
				          try {
				            await fetchPlaybookClips({ force: true, silent: true });
				            renderClipsLibrary();
				          } catch (e) { /* ignore */ }
				        });
				      });
				      const qInput = simClipsList.querySelector('#task-playbook-q');
				      const folderSelect = simClipsList.querySelector('#task-playbook-folder');
				      const tagSelect = simClipsList.querySelector('#task-playbook-tag');
				      const favInput = simClipsList.querySelector('#task-playbook-favorites');
				      const latestInput = simClipsList.querySelector('#task-playbook-latest');
				      const refreshBtn = simClipsList.querySelector('#task-playbook-refresh');
				      const clearGroupBtn = simClipsList.querySelector('#task-playbook-clear-group');
				      const scheduleFetch = () => {
				        if (playbookFilterTimer) window.clearTimeout(playbookFilterTimer);
				        playbookFilterTimer = window.setTimeout(async () => {
				          try {
				            await fetchPlaybookClips({ force: true, silent: true });
				            renderClipsLibrary();
				          } catch (e) { /* ignore */ }
				        }, 250);
				      };
				      qInput?.addEventListener('input', () => {
				        playbookFilters.q = safeText(qInput.value);
				        scheduleFetch();
				      });
				      folderSelect?.addEventListener('change', () => {
				        playbookFilters.folder = safeText(folderSelect.value);
				        scheduleFetch();
				      });
				      tagSelect?.addEventListener('change', () => {
				        playbookFilters.tag = safeText(tagSelect.value);
				        scheduleFetch();
				      });
				      favInput?.addEventListener('change', () => {
				        playbookFilters.favorites = !!favInput.checked;
				        scheduleFetch();
				      });
				      latestInput?.addEventListener('change', () => {
				        playbookFilters.latest = !!latestInput.checked;
				        scheduleFetch();
				      });
				      refreshBtn?.addEventListener('click', () => {
				        void fetchPlaybookClips({ force: true, silent: true }).then(() => renderClipsLibrary());
				      });
				      clearGroupBtn?.addEventListener('click', () => {
				        playbookFilters.version_group = '';
				        playbookFilters.latest = true;
				        void fetchPlaybookClips({ force: true, silent: true }).then(() => renderClipsLibrary());
				      });
				    };

				    // Si el módulo se está usando como "Táctica", precargamos el Playbook para que
				    // la pestaña lateral muestre contenido sin necesidad de entrar al simulador.
				    if (playbookPaneEl) {
				      try { renderClipsLibrary(); } catch (e) { /* ignore */ }
				      try {
				        void fetchPlaybookClips({ silent: true }).then(() => {
				          try { renderClipsLibrary(); } catch (err) { /* ignore */ }
				        });
				      } catch (e) { /* ignore */ }
				    }

				    const restoreSimulationBaseline = () => {
				      if (!simulationBaselineSnapshot) return;
				      let parsed = null;
				      try { parsed = JSON.parse(simulationBaselineSnapshot); } catch (error) { parsed = null; }
				      if (!parsed) return;
				      const { w, h } = worldSize();
				      applySerializedState(parsed, { sourceWidth: Math.round(w || 0), sourceHeight: Math.round(h || 0) });
				    };
				    const stopSimulationPlayback = () => {
				      simulationPlaying = false;
				      simulationProPlaying = false;
				      if (simulationPlayTimer) window.clearTimeout(simulationPlayTimer);
				      simulationPlayTimer = null;
				      simulationAnimToken += 1;
				      if (simulationAnimFrame) {
				        try { window.cancelAnimationFrame(simulationAnimFrame); } catch (error) { /* ignore */ }
				        simulationAnimFrame = null;
				      }
				      if (simulationProAnimFrame) {
				        try { window.cancelAnimationFrame(simulationProAnimFrame); } catch (error) { /* ignore */ }
				        simulationProAnimFrame = null;
				      }
				      clearSimMoveOverlays();
				      clearSimRouteOverlays();
				      syncSimUi();
				    };
				    const ensureLayerUidsOnCanvas = () => {
				      const objects = (canvas.getObjects?.() || []).filter((obj) => obj && !(obj?.data?.base));
				      const used = new Set();
				      objects.forEach((obj) => {
				        obj.data = obj.data || {};
				        const current = safeText(obj?.data?.layer_uid);
				        if (!current || used.has(current)) {
				          obj.data.layer_uid = `layer_${Date.now()}_${layerUidCounter++}`;
				        }
				        used.add(safeText(obj?.data?.layer_uid));
				      });
				    };

				    const clampInt = (value, min, max) => Math.max(min, Math.min(max, Math.floor(Number(value) || 0)));

				    const computeSimulationTotalMs = () => {
				      const steps = Array.isArray(simulationSteps) ? simulationSteps : [];
				      const total = steps.reduce((acc, step) => acc + (clamp(Number(step?.duration) || 3, 1, 20) * 1000), 0);
				      return Math.max(0, Math.round(total || 0));
				    };

				    const computeSimulationStepStartsMs = () => {
				      const starts = [];
				      let cursor = 0;
				      (Array.isArray(simulationSteps) ? simulationSteps : []).forEach((step) => {
				        starts.push(cursor);
				        cursor += clamp(Number(step?.duration) || 3, 1, 20) * 1000;
				      });
				      return starts;
				    };

				    const mapFromCanvasState = (rawState) => {
				      const state = sanitizeLoadedState(rawState);
				      const objects = Array.isArray(state?.objects) ? state.objects : [];
				      const map = new Map();
				      objects.forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (!uid) return;
				        map.set(uid, {
				          left: Number(obj.left) || 0,
				          top: Number(obj.top) || 0,
				          angle: Number(obj.angle) || 0,
				          scaleX: clampScale(Number(obj.scaleX) || 1),
				          scaleY: clampScale(Number(obj.scaleY) || 1),
				          opacity: obj.opacity == null ? 1 : Number(obj.opacity),
				        });
				      });
				      return map;
				    };

				    const normalizeEasing = (value) => {
				      const v = safeText(value, 'ease').toLowerCase();
				      if (v === 'linear') return 'linear';
				      if (v === 'hold') return 'hold';
				      return 'ease';
				    };

				    const easeFor = (easing, t) => {
				      const v = normalizeEasing(easing);
				      if (v === 'linear') return clamp(t, 0, 1);
				      if (v === 'hold') return 0;
				      return easeInOut(clamp(t, 0, 1));
				    };

				    const proKeyframesForUid = (uid) => {
				      const list = simulationProTracks?.[uid];
				      return Array.isArray(list) ? list : [];
				    };

				    const evalProTrackAtTime = (uid, timeMs) => {
				      const kfs = proKeyframesForUid(uid);
				      if (!kfs.length) return null;
				      const t = Math.max(0, Number(timeMs) || 0);
				      if (t <= (Number(kfs[0]?.t_ms) || 0)) return { props: kfs[0]?.props || null };
				      const last = kfs[kfs.length - 1];
				      if (t >= (Number(last?.t_ms) || 0)) return { props: last?.props || null };
				      for (let i = 0; i < kfs.length - 1; i += 1) {
				        const a = kfs[i];
				        const b = kfs[i + 1];
				        const ta = Number(a?.t_ms) || 0;
				        const tb = Number(b?.t_ms) || 0;
				        if (t < ta || t > tb) continue;
				        const span = Math.max(1, tb - ta);
				        const raw = (t - ta) / span;
				        const eased = easeFor(a?.easing, raw);
				        const pa = a?.props || {};
				        const pb = b?.props || {};
				        return {
				          props: {
				            left: lerp(pa.left, pb.left, eased),
				            top: lerp(pa.top, pb.top, eased),
				            angle: lerpAngle(pa.angle, pb.angle, eased),
				            scaleX: lerp(pa.scaleX, pb.scaleX, eased),
				            scaleY: lerp(pa.scaleY, pb.scaleY, eased),
				            opacity: lerp(pa.opacity, pb.opacity, eased),
				          },
				        };
				      }
				      return { props: last?.props || null };
				    };

				    const renderSimulationAtTimeMs = (timeMs) => {
				      if (!isSimulating) return;
				      if (!Array.isArray(simulationSteps) || !simulationSteps.length) return;
				      ensureLayerUidsOnCanvas();
				      const totalMs = computeSimulationTotalMs();
				      const t = clamp(Number(timeMs) || 0, 0, Math.max(0, totalMs));
				      simulationProTimeMs = t;
				      const starts = computeSimulationStepStartsMs();
				      let segIndex = 0;
				      for (let i = 0; i < starts.length - 1; i += 1) {
				        if (t >= starts[i] && t < starts[i + 1]) {
				          segIndex = i;
				          break;
				        }
				        if (t >= starts[starts.length - 1]) segIndex = starts.length - 1;
				      }
				      const startStep = simulationSteps[segIndex];
				      const endStep = simulationSteps[Math.min(simulationSteps.length - 1, segIndex + 1)];
				      const segStartMs = starts[segIndex] || 0;
				      const segEndMs = (segIndex + 1 < starts.length) ? starts[segIndex + 1] : totalMs;
				      const segDur = Math.max(1, segEndMs - segStartMs);
				      const rawAlpha = (segIndex === simulationSteps.length - 1) ? 1 : ((t - segStartMs) / segDur);
				      const alpha = clamp(rawAlpha, 0, 1);

				      const cacheKey = `${segIndex}`;
				      let cache = simulationProCaches.get(cacheKey);
				      if (!cache || cache.startMs !== segStartMs || cache.endMs !== segEndMs) {
				        cache = {
				          startMs: segStartMs,
				          endMs: segEndMs,
				          startMap: mapFromCanvasState(startStep?.canvas_state),
				          endMap: mapFromCanvasState(endStep?.canvas_state),
				        };
				        simulationProCaches.set(cacheKey, cache);
				      }
				      const startMap = cache.startMap;
				      const endMap = cache.endMap;
				      const endRoutes = (endStep?.routes && typeof endStep.routes === 'object') ? endStep.routes : {};

				      const liveObjects = (canvas.getObjects?.() || []).filter((obj) => obj && !(obj?.data?.base));
				      const liveByUid = new Map();
				      liveObjects.forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (uid) liveByUid.set(uid, obj);
				      });

				      const applyProps = (obj, props) => {
				        if (!obj || !props) return;
				        obj.set({
				          left: Number(props.left) || 0,
				          top: Number(props.top) || 0,
				          angle: Number(props.angle) || 0,
				          scaleX: clampScale(Number(props.scaleX) || 1, maxScaleForObject(obj)),
				          scaleY: clampScale(Number(props.scaleY) || 1, maxScaleForObject(obj)),
				          opacity: props.opacity == null ? 1 : Number(props.opacity),
				        });
				        obj.setCoords();
				      };

				      liveByUid.forEach((obj, uid) => {
				        const trackEval = simulationProEnabled ? evalProTrackAtTime(uid, t) : null;
				        if (trackEval?.props) {
				          applyProps(obj, trackEval.props);
				          return;
				        }
				        const sp = startMap.get(uid);
				        const ep = endMap.get(uid);
				        if (!sp || !ep) return;
				        let left = lerp(sp.left, ep.left, alpha);
				        let top = lerp(sp.top, ep.top, alpha);
				        const route = endRoutes?.[uid];
				        const routePoints = Array.isArray(route?.points) ? route.points.slice(0, 60) : null;
				        if (routePoints && routePoints.length >= 2) {
				          const combined = (() => {
				            const startPt = { x: sp.left, y: sp.top };
				            const endPt = { x: ep.left, y: ep.top };
				            const pts = routePoints.map((p) => routePoint(p)).filter(Boolean);
				            if (!pts.length) return [startPt, endPt];
				            const first = pts[0];
				            const last = pts[pts.length - 1];
				            const out = pts.slice();
				            if (Math.hypot((first.x - startPt.x), (first.y - startPt.y)) > 6) out.unshift(startPt);
				            if (Math.hypot((last.x - endPt.x), (last.y - endPt.y)) > 6) out.push(endPt);
				            return out;
				          })();
				          const sampled = sampleRoute(combined, alpha, !!route?.spline);
				          left = Number.isFinite(sampled?.x) ? sampled.x : left;
				          top = Number.isFinite(sampled?.y) ? sampled.y : top;
				        }
				        applyProps(obj, {
				          left,
				          top,
				          angle: lerpAngle(sp.angle, ep.angle, alpha),
				          scaleX: lerp(sp.scaleX, ep.scaleX, alpha),
				          scaleY: lerp(sp.scaleY, ep.scaleY, alpha),
				          opacity: lerp(sp.opacity, ep.opacity, alpha),
				        });
				      });

				      // Balón pegado (segmento): usa ball_follow_uid del endStep (si no hay track del balón).
				      try {
				        const followUid = safeText(endStep?.ball_follow_uid);
				        if (followUid) {
				          const ballUid = findBallUid();
				          const ballObj = ballUid ? liveByUid.get(ballUid) : null;
				          const followObj = liveByUid.get(followUid);
				          const ballHasTrack = ballUid && Array.isArray(simulationProTracks?.[ballUid]) && simulationProTracks[ballUid].length >= 1;
				          const ballHasRoute = ballUid && endRoutes?.[ballUid] && Array.isArray(endRoutes?.[ballUid]?.points) && endRoutes[ballUid].points.length >= 2;
				          if (ballObj && followObj && !ballHasRoute && !ballHasTrack) {
				            ballObj.set({ left: Number(followObj.left) || 0, top: Number(followObj.top) || 0 });
				            ballObj.setCoords();
				          }
				        }
				      } catch (e) { /* ignore */ }

				      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				    };

				    const syncSimProUi = () => {
				      if (!simProPanel) return;
				      const totalMs = computeSimulationTotalMs();
				      if (simProTotalLabel) simProTotalLabel.textContent = formatClock(totalMs / 1000);
				      if (simProTimeLabel) simProTimeLabel.textContent = formatClock((simulationProTimeMs || 0) / 1000);
				      if (simProLoopInput) simProLoopInput.checked = !!simulationProLoop;
				      if (simProScrub) {
				        const max = 1000;
				        simProScrub.max = String(max);
				        const value = totalMs > 0 ? Math.round((clamp(simulationProTimeMs, 0, totalMs) / totalMs) * max) : 0;
				        if (!simProScrub.__dragging) simProScrub.value = String(clampInt(value, 0, max));
				      }
				      if (simProKfList) simProKfList.hidden = true;
				      if (simProKfDelBtn) simProKfDelBtn.disabled = false;
				      if (simProKfAddBtn) simProKfAddBtn.disabled = false;
				    };

				    const persistSimulationProToStorage = () => {
				      if (!canUseStorage) return;
				      try {
				        const raw = safeText(window.localStorage.getItem(simStorageKey));
				        const parsedStore = raw ? JSON.parse(raw) : null;
				        const base = (parsedStore && typeof parsedStore === 'object') ? parsedStore : {};
				        base.v = base.v || 1;
				        base.updated_at = new Date().toISOString();
				        base.pro = {
				          v: 1,
				          enabled: !!simulationProEnabled,
				          loop: !!simulationProLoop,
				          updated_at: new Date().toISOString(),
				          tracks: simulationProTracks || {},
				        };
				        window.localStorage.setItem(simStorageKey, JSON.stringify(base));
				      } catch (e) { /* ignore */ }
				    };

				    const restoreSimulationProFromStorage = () => {
				      simulationProTracks = {};
				      simulationProEnabled = false;
				      simulationProLoop = true;
				      simulationProTimeMs = 0;
				      simulationProUpdatedAt = 0;
				      simulationProCaches = new Map();
				      if (!canUseStorage) return;
				      try {
				        const raw = safeText(window.localStorage.getItem(simStorageKey));
				        const parsedStore = raw ? JSON.parse(raw) : null;
				        const pro = parsedStore && typeof parsedStore === 'object' ? parsedStore.pro : null;
				        if (!pro || typeof pro !== 'object') return;
				        simulationProEnabled = !!pro.enabled;
				        simulationProLoop = pro.loop !== false;
				        const tracks = pro.tracks && typeof pro.tracks === 'object' ? pro.tracks : {};
				        const safeTracks = {};
				        Object.entries(tracks).slice(0, 240).forEach(([uid, list]) => {
				          if (!uid) return;
				          if (!Array.isArray(list)) return;
				          const cleaned = list
				            .map((kf) => {
				              const t_ms = clamp(Number(kf?.t_ms) || 0, 0, 3_600_000);
				              const props = kf?.props && typeof kf.props === 'object' ? kf.props : null;
				              if (!props) return null;
				              return {
				                t_ms,
				                easing: normalizeEasing(kf?.easing),
				                props: {
				                  left: Number(props.left) || 0,
				                  top: Number(props.top) || 0,
				                  angle: Number(props.angle) || 0,
				                  scaleX: clampScale(Number(props.scaleX) || 1),
				                  scaleY: clampScale(Number(props.scaleY) || 1),
				                  opacity: props.opacity == null ? 1 : Number(props.opacity),
				                },
				              };
				            })
				            .filter(Boolean)
				            .sort((a, b) => (a.t_ms - b.t_ms))
				            .slice(0, 120);
				          if (cleaned.length) safeTracks[uid] = cleaned;
				        });
				        simulationProTracks = safeTracks;
				        simulationProUpdatedAt = Date.now();
				      } catch (e) { /* ignore */ }
				    };
				    const clearSimGuides = () => {
				      try { if (simGuideX) canvas.remove(simGuideX); } catch (e) { /* ignore */ }
				      try { if (simGuideY) canvas.remove(simGuideY); } catch (e) { /* ignore */ }
				      simGuideX = null;
				      simGuideY = null;
				    };
				    const clearSimMoveOverlays = () => {
				      try {
				        (simMoveOverlays || []).forEach((obj) => {
				          try { canvas.remove(obj); } catch (e) { /* ignore */ }
				        });
				      } catch (error) { /* ignore */ }
				      simMoveOverlays = [];
				    };
				    const hideSimGuides = () => {
				      if (simGuideX) simGuideX.visible = false;
				      if (simGuideY) simGuideY.visible = false;
				    };
				    const ensureSimGuide = (axis) => {
				      const kind = axis === 'x' ? 'sim-guide-x' : 'sim-guide-y';
				      const line = new fabric.Line([0, 0, 10, 10], {
				        stroke: 'rgba(250,204,21,0.82)',
				        strokeWidth: 2,
				        strokeDashArray: [10, 8],
				        selectable: false,
				        evented: false,
				        excludeFromExport: true,
				        opacity: 0.95,
				        visible: false,
				        data: { base: true, kind },
				      });
				      try { line.strokeUniform = true; } catch (e) { /* ignore */ }
				      canvas.add(line);
				      try { canvas.sendToBack(line); } catch (e) { /* ignore */ }
				      return line;
				    };
				    const updateSimGuides = (snapInfo, options = {}) => {
				      if (!isSimulating || !simulationGuides) {
				        hideSimGuides();
				        return;
				      }
				      const { w, h } = worldSize();
				      const showX = !!(snapInfo?.snappedX);
				      const showY = !!(snapInfo?.snappedY);
				      if (showX) {
				        if (!simGuideX) simGuideX = ensureSimGuide('x');
				        const x = Number(snapInfo?.x) || 0;
				        simGuideX.set({ x1: x, y1: 0, x2: x, y2: h, visible: true });
				      } else if (simGuideX) {
				        simGuideX.visible = false;
				      }
				      if (showY) {
				        if (!simGuideY) simGuideY = ensureSimGuide('y');
				        const y = Number(snapInfo?.y) || 0;
				        simGuideY.set({ x1: 0, y1: y, x2: w, y2: y, visible: true });
				      } else if (simGuideY) {
				        simGuideY.visible = false;
				      }
				      if (options.render !== false) {
				        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				      }
				    };
				    const resolveSoftCollision = (target, desiredCenter) => {
				      if (!isSimulating || !simulationCollision) return desiredCenter;
				      if (!target || safeText(target?.data?.kind) !== 'token') return desiredCenter;
				      if (target.type === 'activeSelection') return desiredCenter;
				      const tokens = (canvas.getObjects?.() || [])
				        .filter((obj) => obj && obj !== target && safeText(obj?.data?.kind) === 'token' && obj.visible !== false);
				      if (!tokens.length) return desiredCenter;
				      const baseX = Number(desiredCenter?.x) || 0;
				      const baseY = Number(desiredCenter?.y) || 0;
				      const rA = Math.max(Number(target.getScaledWidth?.() || 0), Number(target.getScaledHeight?.() || 0)) / 2 || 26;
				      let pushX = 0;
				      let pushY = 0;
				      tokens.forEach((other) => {
				        if (!other?.getCenterPoint) return;
				        const c = other.getCenterPoint();
				        const rB = Math.max(Number(other.getScaledWidth?.() || 0), Number(other.getScaledHeight?.() || 0)) / 2 || 26;
				        const minDist = rA + rB + 4;
				        const dx = baseX - (Number(c.x) || 0);
				        const dy = baseY - (Number(c.y) || 0);
				        const dist = Math.hypot(dx, dy) || 0;
				        if (dist >= minDist) return;
				        const overlap = minDist - Math.max(1, dist);
				        const nx = dist ? (dx / dist) : 1;
				        const ny = dist ? (dy / dist) : 0;
				        pushX += nx * overlap;
				        pushY += ny * overlap;
				      });
				      const mag = Math.hypot(pushX, pushY) || 0;
				      if (mag < 0.5) return desiredCenter;
				      const cap = 26;
				      const scale = mag > cap ? (cap / mag) : 1;
				      const { w, h } = worldSize();
				      const nextX = clamp(baseX + pushX * scale, rA, Math.max(rA, w - rA));
				      const nextY = clamp(baseY + pushY * scale, rA, Math.max(rA, h - rA));
				      return { x: nextX, y: nextY };
				    };
				    const extractTokenPositionsFromState = (canvasState) => {
				      const out = new Map();
				      const state = sanitizeLoadedState(canvasState);
				      const objects = Array.isArray(state.objects) ? state.objects : [];
				      objects.forEach((obj) => {
				        if (safeText(obj?.data?.kind) !== 'token') return;
				        const uid = safeText(obj?.data?.layer_uid);
				        if (!uid) return;
				        const left = Number(obj.left);
				        const top = Number(obj.top);
				        if (!Number.isFinite(left) || !Number.isFinite(top)) return;
				        out.set(uid, { x: left, y: top, angle: Number(obj.angle) || 0 });
				      });
				      return out;
				    };
				    const computeMovesBetweenStates = (fromState, toState) => {
				      const from = extractTokenPositionsFromState(fromState);
				      const to = extractTokenPositionsFromState(toState);
				      const moves = [];
				      to.forEach((end, uid) => {
				        const start = from.get(uid);
				        if (!start) return;
				        const dx = (end.x || 0) - (start.x || 0);
				        const dy = (end.y || 0) - (start.y || 0);
				        const dist = Math.hypot(dx, dy) || 0;
				        if (dist < 10) return;
				        moves.push({ uid, from: { x: start.x, y: start.y }, to: { x: end.x, y: end.y } });
				      });
				      return moves;
				    };
				    const addSimMoveArrow = (from, to) => {
				      const x1 = Number(from?.x) || 0;
				      const y1 = Number(from?.y) || 0;
				      const x2 = Number(to?.x) || 0;
				      const y2 = Number(to?.y) || 0;
				      const dx = x2 - x1;
				      const dy = y2 - y1;
				      const len = Math.hypot(dx, dy) || 0;
				      if (len < 8) return null;
				      const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
				      const head = 14;
				      const line = new fabric.Line([0, 0, Math.max(6, len - head), 0], {
				        stroke: 'rgba(250,204,21,0.9)',
				        strokeWidth: 4,
				        strokeDashArray: [10, 8],
				        strokeLineCap: 'round',
				        selectable: false,
				        evented: false,
				        excludeFromExport: true,
				        data: { base: true, kind: 'sim-move-line' },
				      });
				      try { line.strokeUniform = true; } catch (e) { /* ignore */ }
				      const tri = new fabric.Triangle({
				        width: head,
				        height: head,
				        fill: 'rgba(250,204,21,0.9)',
				        left: Math.max(6, len - head),
				        top: 0,
				        originX: 'center',
				        originY: 'center',
				        angle: 90,
				        selectable: false,
				        evented: false,
				        excludeFromExport: true,
				        data: { base: true, kind: 'sim-move-head' },
				      });
				      const group = new fabric.Group([line, tri], {
				        left: x1,
				        top: y1,
				        originX: 'left',
				        originY: 'center',
				        angle,
				        selectable: false,
				        evented: false,
				        excludeFromExport: true,
				        opacity: 0.92,
				        data: { base: true, kind: 'sim-move' },
				      });
				      try { group.objectCaching = false; } catch (e) { /* ignore */ }
				      try { group.noScaleCache = true; } catch (e) { /* ignore */ }
				      canvas.add(group);
				      try { canvas.sendToBack(group); } catch (e) { /* ignore */ }
				      return group;
				    };
				    const renderSimMovesForStep = (step, options = {}) => {
				      clearSimMoveOverlays();
				      if (!isSimulating || !simulationTrajectories) return;
				      const moves = Array.isArray(step?.moves) ? step.moves : [];
				      if (!moves.length) return;
				      moves.slice(0, 60).forEach((move) => {
				        const arrow = addSimMoveArrow(move.from, move.to);
				        if (arrow) simMoveOverlays.push(arrow);
				      });
				      if (options.render !== false) {
				        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				      }
				    };
				    const lerp = (a, b, t) => (Number(a) || 0) + ((Number(b) || 0) - (Number(a) || 0)) * t;
				    const easeInOut = (t) => (t < 0.5 ? (2 * t * t) : (1 - Math.pow(-2 * t + 2, 2) / 2));
				    const lerpAngle = (a, b, t) => {
				      const from = Number(a) || 0;
				      let to = Number(b) || 0;
				      let delta = ((to - from + 540) % 360) - 180;
				      if (!Number.isFinite(delta)) delta = to - from;
				      to = from + delta;
				      return from + (to - from) * t;
				    };
				    const routePoint = (p, fallback) => {
				      const x = Number(p?.x);
				      const y = Number(p?.y);
				      if (Number.isFinite(x) && Number.isFinite(y)) return { x, y };
				      return fallback || { x: 0, y: 0 };
				    };
				    const catmullRom = (p0, p1, p2, p3, t) => {
				      const tt = t * t;
				      const ttt = tt * t;
				      const a0 = (-0.5 * ttt) + (tt) - (0.5 * t);
				      const a1 = (1.5 * ttt) - (2.5 * tt) + 1;
				      const a2 = (-1.5 * ttt) + (2 * tt) + (0.5 * t);
				      const a3 = (0.5 * ttt) - (0.5 * tt);
				      return {
				        x: (p0.x * a0) + (p1.x * a1) + (p2.x * a2) + (p3.x * a3),
				        y: (p0.y * a0) + (p1.y * a1) + (p2.y * a2) + (p3.y * a3),
				      };
				    };
				    const sampleRoutePolyline = (points, t) => {
				      const pts = Array.isArray(points) ? points.map((p) => routePoint(p)).filter(Boolean) : [];
				      if (pts.length <= 1) return pts[0] || { x: 0, y: 0 };
				      const segs = [];
				      let total = 0;
				      for (let i = 0; i < pts.length - 1; i += 1) {
				        const a = pts[i];
				        const b = pts[i + 1];
				        const len = Math.hypot((b.x - a.x), (b.y - a.y)) || 0;
				        segs.push({ a, b, len });
				        total += len;
				      }
				      if (total <= 0.01) return pts[pts.length - 1];
				      let dist = clamp(Number(t) || 0, 0, 1) * total;
				      for (const seg of segs) {
				        if (dist <= seg.len || seg.len <= 0.01) {
				          const local = seg.len <= 0.01 ? 0 : (dist / seg.len);
				          return { x: lerp(seg.a.x, seg.b.x, local), y: lerp(seg.a.y, seg.b.y, local) };
				        }
				        dist -= seg.len;
				      }
				      return pts[pts.length - 1];
				    };
				    const sampleRouteSpline = (points, t) => {
				      const pts = Array.isArray(points) ? points.map((p) => routePoint(p)).filter(Boolean) : [];
				      if (pts.length <= 1) return pts[0] || { x: 0, y: 0 };
				      const n = pts.length;
				      const scaled = clamp(Number(t) || 0, 0, 1) * (n - 1);
				      const i = clamp(Math.floor(scaled), 0, n - 2);
				      const localT = scaled - i;
				      const p0 = pts[Math.max(0, i - 1)];
				      const p1 = pts[i];
				      const p2 = pts[i + 1];
				      const p3 = pts[Math.min(n - 1, i + 2)];
				      return catmullRom(p0, p1, p2, p3, localT);
				    };
				    const sampleRoute = (points, t, spline) => (spline ? sampleRouteSpline(points, t) : sampleRoutePolyline(points, t));
				    const renderSimulationSteps = () => {
				      if (!simStepsList) return;
				      simStepsList.innerHTML = '';
				      if (!simulationSteps.length) {
				        simStepsList.innerHTML = '<div class="timeline-empty">Todavía no hay pasos. Pulsa “Capturar paso”.</div>';
				        if (simStepTitleInput) simStepTitleInput.value = '';
				        if (simStepDurationInput) simStepDurationInput.value = '3';
				        return;
				      }
				      simulationSteps.forEach((step, index) => {
				        const button = document.createElement('button');
				        button.type = 'button';
				        button.className = `sim-step${index === simulationActiveIndex ? ' is-active' : ''}`;
				        button.dataset.simStepIndex = String(index);
				        button.draggable = true;
				        const title = safeText(step?.title, `Paso ${index + 1}`);
				        const duration = clamp(Number(step?.duration) || 3, 1, 20);
				        button.innerHTML = `
				          <div>
				            <strong>${title}</strong>
				            <span>${duration}s · paso ${index + 1}</span>
				          </div>
				          <span>${index === simulationActiveIndex ? 'Viendo' : 'Abrir'}</span>
				        `;
				        simStepsList.appendChild(button);
				      });
				      const active = simulationSteps[simulationActiveIndex] || null;
				      if (active) {
				        if (simStepTitleInput) simStepTitleInput.value = safeText(active.title, `Paso ${simulationActiveIndex + 1}`);
				        if (simStepDurationInput) simStepDurationInput.value = String(clamp(Number(active.duration) || 3, 1, 20));
				      }
				    };
				    const seedSimulationStepsFromCurrent = () => {
				      const { w, h } = worldSize();
				      ensureLayerUidsOnCanvas();
				      simulationSteps = [{
				        title: 'Inicio',
				        duration: 3,
				        canvas_state: serializeCanvasOnly(),
				        canvas_width: Math.round(w || 0),
				        canvas_height: Math.round(h || 0),
				        moves: [],
				        routes: {},
				        ball_follow_uid: '',
				      }];
				      simulationActiveIndex = 0;
				      renderSimulationSteps();
				    };
				    const selectSimulationStep = async (index, options = {}) => {
				      const idx = clamp(Number(index) || 0, 0, Math.max(0, simulationSteps.length - 1));
				      const step = simulationSteps[idx];
				      if (!step) return;
				      if (!options.keepPlaying) stopSimulationPlayback();
				      simulationActiveIndex = idx;
				      ensureStepRoutes(step);
				      const sourceWidth = parseIntSafe(step.canvas_width) || 0;
				      const sourceHeight = parseIntSafe(step.canvas_height) || 0;
				      if (typeof loadCanvasSnapshotAsync === 'function') {
				        await loadCanvasSnapshotAsync(step.canvas_state, { sourceWidth, sourceHeight });
				      } else {
				        loadCanvasSnapshot(step.canvas_state, null, { sourceWidth, sourceHeight });
				      }
				      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
				      try { syncInspector(); } catch (e) { /* ignore */ }
				      try { renderLayers(); } catch (e) { /* ignore */ }
				      clearSimMoveOverlays();
				      renderSimRoutesForStep(step);
				      renderSimulationSteps();
				    };
				    const transitionToSimulationStep = async (index, options = {}) => {
				      const idx = clamp(Number(index) || 0, 0, Math.max(0, simulationSteps.length - 1));
				      const step = simulationSteps[idx];
				      if (!step) return false;
				      if (!options.keepPlaying) stopSimulationPlayback();

				      ensureLayerUidsOnCanvas();
				      const endState = sanitizeLoadedState(step.canvas_state);
				      const endObjects = Array.isArray(endState.objects) ? endState.objects : [];
				      const endMap = new Map();
				      endObjects.forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (uid) endMap.set(uid, obj);
				      });
				      const liveObjects = (canvas.getObjects?.() || []).filter((obj) => obj && !(obj?.data?.base));
				      const liveByUid = new Map();
				      liveObjects.forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (uid) liveByUid.set(uid, obj);
				      });
				      const stepRoutes = (step.routes && typeof step.routes === 'object') ? step.routes : {};
				      const animTargets = [];
				      liveObjects.forEach((obj) => {
				        const uid = safeText(obj?.data?.layer_uid);
				        if (!uid) return;
				        const endObj = endMap.get(uid);
				        if (!endObj) return;
				        const route = stepRoutes?.[uid];
				        const routePoints = Array.isArray(route?.points) ? route.points.slice(0, 60) : null;
				        const routeSpline = !!route?.spline;
				        animTargets.push({
				          obj,
				          start: {
				            left: Number(obj.left) || 0,
				            top: Number(obj.top) || 0,
				            angle: Number(obj.angle) || 0,
				            scaleX: Number(obj.scaleX) || 1,
				            scaleY: Number(obj.scaleY) || 1,
				            opacity: obj.opacity == null ? 1 : Number(obj.opacity),
				          },
				          end: {
				            left: Number(endObj.left) || 0,
				            top: Number(endObj.top) || 0,
				            angle: Number(endObj.angle) || 0,
				            scaleX: clampScale(Number(endObj.scaleX) || 1),
				            scaleY: clampScale(Number(endObj.scaleY) || 1),
				            opacity: endObj.opacity == null ? 1 : Number(endObj.opacity),
				          },
				          routePoints,
				          routeSpline,
				        });
				      });

				      // Si no hay nada que animar, salta directo.
				      if (!animTargets.length) {
				        await selectSimulationStep(idx, { keepPlaying: !!options.keepPlaying });
				        return true;
				      }

				      const transitionMs = clamp(Number(options.transitionMs) || 650, 180, 1200);
				      const token = (simulationAnimToken += 1);
				      const startTs = (window.performance?.now?.() || Date.now());

				      return await new Promise((resolve) => {
				        const tick = (nowRaw) => {
				          const now = Number(nowRaw) || (window.performance?.now?.() || Date.now());
				          if (!isSimulating) return resolve(false);
				          if (simulationAnimToken !== token) return resolve(false);
				          if (options.keepPlaying && !simulationPlaying) return resolve(false);
				          const t = clamp((now - startTs) / Math.max(1, transitionMs), 0, 1);
				          const eased = easeInOut(t);
				          animTargets.forEach(({ obj, start, end, routePoints, routeSpline }) => {
				            try {
				              let left = lerp(start.left, end.left, eased);
				              let top = lerp(start.top, end.top, eased);
				              if (routePoints && routePoints.length >= 2) {
				                const combined = (() => {
				                  const startPt = { x: start.left, y: start.top };
				                  const endPt = { x: end.left, y: end.top };
				                  const pts = routePoints.map((p) => routePoint(p)).filter(Boolean);
				                  if (!pts.length) return [startPt, endPt];
				                  const first = pts[0];
				                  const last = pts[pts.length - 1];
				                  const out = pts.slice();
				                  if (Math.hypot((first.x - startPt.x), (first.y - startPt.y)) > 6) out.unshift(startPt);
				                  if (Math.hypot((last.x - endPt.x), (last.y - endPt.y)) > 6) out.push(endPt);
				                  return out;
				                })();
				                const sampled = sampleRoute(combined, eased, !!routeSpline);
				                left = Number.isFinite(sampled?.x) ? sampled.x : left;
				                top = Number.isFinite(sampled?.y) ? sampled.y : top;
				              }
				              obj.set({
				                left,
				                top,
				                angle: lerpAngle(start.angle, end.angle, eased),
				                scaleX: lerp(start.scaleX, end.scaleX, eased),
				                scaleY: lerp(start.scaleY, end.scaleY, eased),
				                opacity: lerp(start.opacity, end.opacity, eased),
				              });
				              obj.setCoords();
				            } catch (error) { /* ignore */ }
				          });
				          // Balón pegado: si se configuró para este paso, sigue al objetivo (si no hay ruta propia del balón).
				          try {
				            const followUid = safeText(step?.ball_follow_uid);
				            if (followUid) {
				              const ballUid = findBallUid();
				              const ballObj = ballUid ? liveByUid.get(ballUid) : null;
				              const followObj = liveByUid.get(followUid);
				              const ballHasRoute = ballUid && stepRoutes?.[ballUid] && Array.isArray(stepRoutes?.[ballUid]?.points) && stepRoutes[ballUid].points.length >= 2;
				              if (ballObj && followObj && !ballHasRoute) {
				                ballObj.set({ left: Number(followObj.left) || 0, top: Number(followObj.top) || 0 });
				                ballObj.setCoords();
				              }
				            }
				          } catch (e) { /* ignore */ }
				          try { canvas.requestRenderAll(); } catch (error) { /* ignore */ }
				          if (t < 1) {
				            simulationAnimFrame = window.requestAnimationFrame(tick);
				            return;
				          }
				          simulationAnimFrame = null;
				          // Asegura estado exacto al final de la transición.
				          void selectSimulationStep(idx, { keepPlaying: !!options.keepPlaying }).finally(() => resolve(true));
				        };
				        simulationAnimFrame = window.requestAnimationFrame(tick);
				      });
				    };
				    const captureSimulationStep = () => {
				      if (!isSimulating) return;
				      stopSimulationPlayback();
				      const { w, h } = worldSize();
				      ensureLayerUidsOnCanvas();
				      const index = simulationSteps.length + 1;
				      const prev = simulationSteps.length ? simulationSteps[simulationSteps.length - 1] : null;
				      const prevState = prev?.canvas_state || null;
				      const nextState = serializeCanvasOnly();
				      const moves = prevState ? computeMovesBetweenStates(prevState, nextState) : [];
				      simulationSteps.push({
				        title: `Paso ${index}`,
				        duration: 3,
				        canvas_state: nextState,
				        canvas_width: Math.round(w || 0),
				        canvas_height: Math.round(h || 0),
				        moves,
				        routes: {},
				        ball_follow_uid: '',
				      });
				      simulationProCaches = new Map();
				      simulationActiveIndex = simulationSteps.length - 1;
				      renderSimulationSteps();
				      setStatus('Paso capturado.');
				    };
				    const removeSimulationStep = () => {
				      if (!isSimulating) return;
				      if (simulationSteps.length <= 1) {
				        setStatus('No se puede eliminar el paso inicial.', true);
				        return;
				      }
				      stopSimulationPlayback();
				      const idx = clamp(simulationActiveIndex, 0, simulationSteps.length - 1);
				      simulationSteps.splice(idx, 1);
				      simulationProCaches = new Map();
				      simulationActiveIndex = clamp(idx - 1, 0, simulationSteps.length - 1);
				      renderSimulationSteps();
				      void selectSimulationStep(simulationActiveIndex);
				      setStatus('Paso eliminado.');
				    };
				    const duplicateSimulationStep = () => {
				      if (!isSimulating) return;
				      const step = simulationSteps[simulationActiveIndex];
				      if (!step) return;
				      stopSimulationPlayback();
				      let clonedState = null;
				      try { clonedState = JSON.parse(JSON.stringify(step.canvas_state)); } catch (e) { clonedState = sanitizeLoadedState(step.canvas_state); }
				      const moves = Array.isArray(step.moves) ? JSON.parse(JSON.stringify(step.moves)) : [];
				      const routes = (() => {
				        try { return step.routes ? JSON.parse(JSON.stringify(step.routes)) : {}; } catch (e) { return {}; }
				      })();
				      const clone = {
				        title: `${safeText(step.title, `Paso ${simulationActiveIndex + 1}`)} copia`,
				        duration: clamp(Number(step.duration) || 3, 1, 20),
				        canvas_state: clonedState,
				        canvas_width: parseIntSafe(step.canvas_width) || 0,
				        canvas_height: parseIntSafe(step.canvas_height) || 0,
				        moves,
				        routes,
				        ball_follow_uid: safeText(step.ball_follow_uid),
				      };
				      const insertAt = clamp(simulationActiveIndex + 1, 0, simulationSteps.length);
				      simulationSteps.splice(insertAt, 0, clone);
				      simulationProCaches = new Map();
				      simulationActiveIndex = insertAt;
				      renderSimulationSteps();
				      void selectSimulationStep(simulationActiveIndex);
				      setStatus('Paso duplicado.');
				    };
				    const reorderSimulationSteps = (fromIndex, toIndex) => {
				      const from = Number(fromIndex);
				      const to = Number(toIndex);
				      if (!Number.isFinite(from) || !Number.isFinite(to)) return;
				      if (from === to) return;
				      if (from < 0 || from >= simulationSteps.length) return;
				      if (to < 0 || to >= simulationSteps.length) return;
				      const [moved] = simulationSteps.splice(from, 1);
				      simulationSteps.splice(to, 0, moved);
				      simulationProCaches = new Map();
				      if (simulationActiveIndex === from) simulationActiveIndex = to;
				      else if (simulationActiveIndex > from && simulationActiveIndex <= to) simulationActiveIndex -= 1;
				      else if (simulationActiveIndex < from && simulationActiveIndex >= to) simulationActiveIndex += 1;
				      renderSimulationSteps();
				      setStatus('Pasos reordenados.');
				    };
				    const playSimulationSteps = async () => {
				      if (!isSimulating) return;
				      if (!simulationSteps.length) return;
				      if (simulationProEnabled) {
				        if (simulationProPlaying) {
				          stopSimulationPlayback();
				          setStatus('Reproducción detenida.');
				          return;
				        }
				        const totalMs = computeSimulationTotalMs();
				        if (totalMs <= 0) return;
				        simulationProPlaying = true;
				        syncSimUi();
				        const startAt = window.performance?.now?.() || Date.now();
				        const startTimeMs = clamp(Number(simulationProTimeMs) || 0, 0, totalMs);
				        const speed = clamp(Number(simulationSpeed) || 1, 0.25, 3);
				        const tick = (nowRaw) => {
				          const now = Number(nowRaw) || (window.performance?.now?.() || Date.now());
				          if (!simulationProPlaying) return;
				          const elapsed = (now - startAt) * speed;
				          let next = startTimeMs + elapsed;
				          if (next >= totalMs) {
				            if (simulationProLoop) {
				              next = next % totalMs;
				            } else {
				              next = totalMs;
				              simulationProPlaying = false;
				              syncSimUi();
				            }
				          }
				          renderSimulationAtTimeMs(next);
				          syncSimProUi();
				          if (simulationProPlaying) {
				            simulationProAnimFrame = window.requestAnimationFrame(tick);
				          } else {
				            simulationProAnimFrame = null;
				          }
				        };
				        setStatus('Reproduciendo (Timeline Pro)…');
				        simulationProAnimFrame = window.requestAnimationFrame(tick);
				        return;
				      }
				      if (simulationPlaying) {
				        stopSimulationPlayback();
				        setStatus('Reproducción detenida.');
				        return;
				      }
				      simulationPlaying = true;
				      syncSimUi();
				      const startIndex = clamp(simulationActiveIndex, 0, simulationSteps.length - 1);
				      let cursor = startIndex;
				      const advance = async () => {
				        if (!simulationPlaying) return;
				        try { renderSimMovesForStep(simulationSteps[cursor]); } catch (e) { /* ignore */ }
				        try { renderSimRoutesForStep(simulationSteps[cursor]); } catch (e) { /* ignore */ }
				        const duration = clamp(Number(simulationSteps[cursor]?.duration) || 3, 1, 20);
				        const speed = clamp(Number(simulationSpeed) || 1, 0.25, 3);
				        const scaledDuration = Math.max(0.25, duration / speed);
				        const transitionMs = clamp(Math.round(scaledDuration * 1000 * 0.35), 220, 900);
				        await transitionToSimulationStep(cursor, { keepPlaying: true, transitionMs });
				        if (!simulationPlaying) return;
				        const holdMs = Math.max(120, Math.round(scaledDuration * 1000 - transitionMs));
				        simulationPlayTimer = window.setTimeout(() => {
				          clearSimMoveOverlays();
				          cursor = (cursor + 1) % simulationSteps.length;
				          void advance();
				        }, holdMs);
				      };
				      setStatus('Reproduciendo pasos…');
				      void advance();
				    };
					    const setSimulationUiLocked = (locked) => {
					      const setDisabled = (node) => {
					        if (!node) return;
					        if ('disabled' in node) node.disabled = !!locked;
				        try { node.classList.toggle('is-disabled', !!locked); } catch (error) { /* ignore */ }
				      };
				      [presetSelect, surfaceTrigger, orientationToggle, grassToggle, zoomOutButton, zoomInButton, zoomResetButton, stageSizeDownButton, stageSizeUpButton, stageSizeFitButton, pitchFormatInput]
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
					      try {
					        [exportPngBtn, exportPngHdBtn, exportJsonBtn, exportStepsBtn].forEach(setDisabled);
					        Array.from(document.querySelectorAll('[data-print-style]')).forEach(setDisabled);
					        Array.from(form.querySelectorAll('button[type=\"submit\"], input[type=\"submit\"]')).forEach(setDisabled);
					      } catch (error) { /* ignore */ }
					      try { if (locked && resourceDetails) resourceDetails.open = false; } catch (error) { /* ignore */ }
					    };
				    const enterSimulation = () => {
				      if (isSimulating) return;
				      try { simulationBaselineSnapshot = JSON.stringify(serializeState()); } catch (error) { simulationBaselineSnapshot = null; }
				      clearPendingPlacement();
				      stopSimulationPlayback();
				      clearSimGuides();
				      simRouteAddMode = false;
				      if (simRouteToggleBtn) {
				        simRouteToggleBtn.textContent = 'Añadir waypoints';
				        simRouteToggleBtn.classList.remove('primary');
				      }
				      simulationAutoCapture = true;
				      simulationSpeed = 1.0;
				      simulationLastAutoCaptureAt = 0;
				      simulationMagnets = true;
				      simulationGuides = true;
				      simulationCollision = false;
				      simulationTrajectories = true;
				      restoreSimulationProFromStorage();
				      isSimulating = true;
				      setSimulationUiLocked(true);
				      if (Array.isArray(simulationSavedSteps) && simulationSavedSteps.length) {
				        stopSimulationPlayback();
				        let cloned = [];
				        try { cloned = JSON.parse(JSON.stringify(simulationSavedSteps)); } catch (error) { cloned = simulationSavedSteps.slice(); }
				        simulationSteps = cloned;
				        simulationActiveIndex = clamp(0, 0, Math.max(0, simulationSteps.length - 1));
				        renderSimulationSteps();
				        void selectSimulationStep(simulationActiveIndex);
				      } else {
				        seedSimulationStepsFromCurrent();
				      }
				      // Ajusta playhead pro al inicio del paso activo (si aplica).
				      try {
				        const starts = computeSimulationStepStartsMs();
				        simulationProTimeMs = clamp(Number(starts?.[simulationActiveIndex] || 0), 0, computeSimulationTotalMs());
				      } catch (e) { /* ignore */ }
				      syncSimProUi();
					      syncSimUi();
					      setStatus(simulationSavedSteps.length ? 'Modo simulación activado (rehidratado). Mueve elementos: no se guardan cambios.' : 'Modo simulación activado. Mueve elementos: no se guardan cambios.');
					      try {
					        void fetchPlaybookClips({ silent: true }).then(() => {
					          try { renderClipsLibrary(); } catch (e) { /* ignore */ }
					        });
					      } catch (e) { /* ignore */ }
				      try { renderClipsLibrary(); } catch (e) { /* ignore */ }
				    };
				    // Ahora el simulador está listo: si el usuario pulsó un botón de Playbook mientras
				    // se inicializaba el JS, ejecutamos esa acción pendiente.
				    try {
				      playbookSimReady = true;
				      if (playbookPendingAction) {
				        const action = playbookPendingAction;
				        playbookPendingAction = '';
				        runPlaybookActionNow(action);
				      }
				    } catch (e) { /* ignore */ }
				    const exitSimulation = () => {
				      if (!isSimulating) return;
				      stopSimulationPlayback();
				      simRouteAddMode = false;
				      if (simRouteToggleBtn) {
				        simRouteToggleBtn.textContent = 'Añadir waypoints';
				        simRouteToggleBtn.classList.remove('primary');
				      }
				      if (simRecordActive) {
				        try { stopSimRecording(); } catch (e) { /* ignore */ }
				      }
				      // Persiste los pasos capturados para guardarlos con la tarea (fase 9).
				      try {
				        if (Array.isArray(simulationSteps) && simulationSteps.length) {
				          simulationSavedSteps = JSON.parse(JSON.stringify(simulationSteps));
				          simulationSavedUpdatedAt = Date.now();
				          try {
				            if (canUseStorage) window.localStorage.setItem(simStorageKey, JSON.stringify({ v: 1, updated_at: new Date().toISOString(), steps: simulationSavedSteps, pro: { v: 1, enabled: !!simulationProEnabled, loop: !!simulationProLoop, updated_at: new Date().toISOString(), tracks: simulationProTracks || {} } }));
				          } catch (err) { /* ignore */ }
				        }
				      } catch (error) { /* ignore */ }
				      isSimulating = false;
				      setSimulationUiLocked(false);
				      syncSimUi();
				      clearSimGuides();
				      restoreSimulationBaseline();
				      simulationBaselineSnapshot = null;
				      simulationSteps = [];
				      simulationActiveIndex = -1;
				      simulationAutoCapture = false;
				      simulationSpeed = 1.0;
				      simulationMagnets = true;
				      simulationGuides = true;
				      simulationCollision = false;
				      simulationTrajectories = true;
				      simulationProEnabled = false;
				      simulationProPlaying = false;
				      simulationProTimeMs = 0;
				      simulationProLoop = true;
				      simulationProTracks = {};
				      simulationProUpdatedAt = 0;
				      simulationProCaches = new Map();
				      try { scheduleDraftSave('simulation-exit'); } catch (error) { /* ignore */ }
				      setStatus('Simulación finalizada. Volviste al editor.');
				    };
						    const resetSimulation = () => {
						      if (!isSimulating) return;
						      stopSimulationPlayback();
						      simRouteAddMode = false;
						      if (simRouteToggleBtn) {
						        simRouteToggleBtn.textContent = 'Añadir waypoints';
						        simRouteToggleBtn.classList.remove('primary');
						      }
						      if (simRecordActive) {
						        try { stopSimRecording(); } catch (e) { /* ignore */ }
						      }
						      clearSimGuides();
						      simulationSavedSteps = [];
						      simulationSavedUpdatedAt = Date.now();
						      try { if (canUseStorage) window.localStorage.removeItem(simStorageKey); } catch (error) { /* ignore */ }
						      restoreSimulationBaseline();
						      seedSimulationStepsFromCurrent();
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
		      if (formationPopover && !formationPopover.hidden) {
		        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-formation-popover');
		        if (!inside) closeFormationPopover();
		      }
		      if (overlaysPopover && !overlaysPopover.hidden) {
		        const inside = resolveClosest(target, '#task-command-bar') || resolveClosest(target, '#task-overlays-popover');
		        if (!inside) closeOverlaysPopover();
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
			      if (formationPopover && !formationPopover.hidden) closeFormationPopover();
			      if (overlaysPopover && !overlaysPopover.hidden) closeOverlaysPopover();
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
			    simCaptureBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      captureSimulationStep();
			    });
			    simPlayBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      void playSimulationSteps();
			    });
			    simRecordBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      void toggleSimRecording();
			    });
			    simRemoveBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      removeSimulationStep();
			    });
			    simDuplicateBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      duplicateSimulationStep();
			    });
			    simPrevBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      const idx = clamp(simulationActiveIndex - 1, 0, Math.max(0, simulationSteps.length - 1));
			      void selectSimulationStep(idx).then(() => {
			        if (!simulationProEnabled) return;
			        const starts = computeSimulationStepStartsMs();
			        simulationProCaches = new Map();
			        renderSimulationAtTimeMs(Number(starts?.[idx] || 0));
			        syncSimProUi();
			      });
			    });
			    simNextBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      const idx = clamp(simulationActiveIndex + 1, 0, Math.max(0, simulationSteps.length - 1));
			      void selectSimulationStep(idx).then(() => {
			        if (!simulationProEnabled) return;
			        const starts = computeSimulationStepStartsMs();
			        simulationProCaches = new Map();
			        renderSimulationAtTimeMs(Number(starts?.[idx] || 0));
			        syncSimProUi();
			      });
			    });
				    simAutoCaptureInput?.addEventListener('change', () => {
				      simulationAutoCapture = !!simAutoCaptureInput.checked;
				      setStatus(simulationAutoCapture ? 'Auto-captura activada.' : 'Auto-captura desactivada.');
				    });
				    simRecordFormatSelect?.addEventListener('change', () => {
				      try { simPersistRecordPrefsFromUi(); } catch (e) { /* ignore */ }
				      setStatus('Formato de vídeo guardado.');
				    });
				    simRecordTitleInput?.addEventListener('change', () => {
				      try { simPersistRecordPrefsFromUi(); } catch (e) { /* ignore */ }
				      setStatus(simRecordTitleInput?.checked ? 'Título en vídeo activado.' : 'Título en vídeo desactivado.');
				    });
				    simProEnabledInput?.addEventListener('change', async () => {
				      if (!isSimulating) return;
				      stopSimulationPlayback();
			      simulationProEnabled = !!simProEnabledInput.checked;
			      if (simulationProEnabled) {
			        try {
			          const starts = computeSimulationStepStartsMs();
			          simulationProTimeMs = clamp(Number(starts?.[simulationActiveIndex] || 0), 0, computeSimulationTotalMs());
			        } catch (e) { /* ignore */ }
			        simulationProCaches = new Map();
			        renderSimulationAtTimeMs(simulationProTimeMs);
			        syncSimProUi();
			        persistSimulationProToStorage();
			        setStatus('Timeline Pro activado.');
			      } else {
			        // Volvemos al modo por pasos: recarga el paso activo para restaurar el snapshot exacto.
			        try { await selectSimulationStep(simulationActiveIndex); } catch (e) { /* ignore */ }
			        persistSimulationProToStorage();
			        setStatus('Timeline Pro desactivado.');
			      }
			      syncSimUi();
			    });
			    simProLoopInput?.addEventListener('change', () => {
			      simulationProLoop = !!simProLoopInput.checked;
			      persistSimulationProToStorage();
			    });
			    if (simProScrub) {
			      simProScrub.addEventListener('pointerdown', () => { simProScrub.__dragging = true; });
			      simProScrub.addEventListener('pointerup', () => { simProScrub.__dragging = false; });
			      simProScrub.addEventListener('input', () => {
			        if (!isSimulating || !simulationProEnabled) return;
			        stopSimulationPlayback();
			        const totalMs = computeSimulationTotalMs();
			        const max = Number(simProScrub.max) || 1000;
			        const frac = clamp((Number(simProScrub.value) || 0) / Math.max(1, max), 0, 1);
			        const nextMs = Math.round(frac * totalMs);
			        simulationProCaches = new Map();
			        renderSimulationAtTimeMs(nextMs);
			        syncSimProUi();
			      });
			    }

			    const selectedUidsForPro = () => {
			      const objs = getSelectionObjects().filter((obj) => obj && !obj?.data?.base);
			      const uids = objs.map((obj) => safeText(obj?.data?.layer_uid)).filter(Boolean);
			      return Array.from(new Set(uids)).slice(0, 12);
			    };

			    const renderProKeyframesForUid = (uid) => {
			      if (!simProKfList) return;
			      const list = proKeyframesForUid(uid);
			      if (!list.length) {
			        simProKfList.innerHTML = '<div class="timeline-empty">Sin keyframes para esta selección.</div>';
			        simProKfList.hidden = false;
			        return;
			      }
			      const rows = list.slice(0, 80).map((kf, index) => {
			        const label = formatClock((Number(kf.t_ms) || 0) / 1000);
			        const isNear = Math.abs((Number(kf.t_ms) || 0) - (Number(simulationProTimeMs) || 0)) <= 180;
			        const easing = safeText(kf.easing, 'ease');
			        return `
			          <button type="button" class="sim-step${isNear ? ' is-active' : ''}" data-pro-kf-uid="${uid}" data-pro-kf-index="${index}">
			            <div>
			              <strong>${label}</strong>
			              <span>${easing.toUpperCase()}</span>
			            </div>
			            <span>${isNear ? 'Actual' : 'Ir'}</span>
			          </button>
			        `;
			      }).join('');
			      simProKfList.innerHTML = rows;
			      simProKfList.hidden = false;
			    };

			    simProKfList?.addEventListener('click', (event) => {
			      const btn = event.target.closest('button[data-pro-kf-uid][data-pro-kf-index]');
			      if (!btn) return;
			      if (!simulationProEnabled) return;
			      const uid = safeText(btn.getAttribute('data-pro-kf-uid'));
			      const idx = Number(btn.getAttribute('data-pro-kf-index') || 0);
			      const kfs = proKeyframesForUid(uid);
			      const kf = kfs[idx];
			      if (!kf) return;
			      stopSimulationPlayback();
			      simulationProCaches = new Map();
			      renderSimulationAtTimeMs(Number(kf.t_ms) || 0);
			      syncSimProUi();
			      renderProKeyframesForUid(uid);
			    });

			    const upsertProKeyframeForUid = (uid, timeMs, props, easing) => {
			      const t_ms = clamp(Math.round(Number(timeMs) || 0), 0, 3_600_000);
			      const next = Array.isArray(simulationProTracks?.[uid]) ? simulationProTracks[uid].slice() : [];
			      const threshold = 140;
			      const existingIndex = next.findIndex((kf) => Math.abs((Number(kf?.t_ms) || 0) - t_ms) <= threshold);
			      const entry = { t_ms, easing: normalizeEasing(easing), props };
			      if (existingIndex >= 0) next.splice(existingIndex, 1, entry);
			      else next.push(entry);
			      next.sort((a, b) => (a.t_ms - b.t_ms));
			      simulationProTracks = simulationProTracks || {};
			      simulationProTracks[uid] = next.slice(0, 120);
			    };

			    const deleteNearestProKeyframeForUid = (uid, timeMs) => {
			      const list = Array.isArray(simulationProTracks?.[uid]) ? simulationProTracks[uid].slice() : [];
			      if (!list.length) return false;
			      const t = Number(timeMs) || 0;
			      let best = -1;
			      let bestDx = 999999;
			      list.forEach((kf, idx) => {
			        const dx = Math.abs((Number(kf?.t_ms) || 0) - t);
			        if (dx < bestDx) { bestDx = dx; best = idx; }
			      });
			      if (best < 0 || bestDx > 220) return false;
			      list.splice(best, 1);
			      if (!list.length) {
			        try { delete simulationProTracks[uid]; } catch (e) { /* ignore */ }
			      } else {
			        simulationProTracks[uid] = list;
			      }
			      return true;
			    };

			    simProKfAddBtn?.addEventListener('click', () => {
			      if (!isSimulating || !simulationProEnabled) return;
			      stopSimulationPlayback();
			      const uids = selectedUidsForPro();
			      if (!uids.length) {
			        setStatus('Selecciona una o varias fichas para guardar keyframe.', true);
			        return;
			      }
			      const easing = safeText(simProEasingSelect?.value, 'ease');
			      uids.forEach((uid) => {
			        const obj = (canvas.getObjects?.() || []).find((o) => safeText(o?.data?.layer_uid) === uid);
			        if (!obj) return;
			        const props = {
			          left: Number(obj.left) || 0,
			          top: Number(obj.top) || 0,
			          angle: Number(obj.angle) || 0,
			          scaleX: clampScale(Number(obj.scaleX) || 1),
			          scaleY: clampScale(Number(obj.scaleY) || 1),
			          opacity: obj.opacity == null ? 1 : Number(obj.opacity),
			        };
			        upsertProKeyframeForUid(uid, simulationProTimeMs, props, easing);
			      });
			      persistSimulationProToStorage();
			      simulationProUpdatedAt = Date.now();
			      simulationProCaches = new Map();
			      syncSimProUi();
			      if (uids.length === 1) renderProKeyframesForUid(uids[0]);
			      setStatus('Keyframe guardado.');
			    });

			    simProKfDelBtn?.addEventListener('click', () => {
			      if (!isSimulating || !simulationProEnabled) return;
			      stopSimulationPlayback();
			      const uids = selectedUidsForPro();
			      if (!uids.length) {
			        setStatus('Selecciona una ficha para borrar su keyframe.', true);
			        return;
			      }
			      let removed = 0;
			      uids.forEach((uid) => {
			        if (deleteNearestProKeyframeForUid(uid, simulationProTimeMs)) removed += 1;
			      });
			      if (!removed) {
			        setStatus('No hay keyframe cercano a este tiempo.', true);
			        return;
			      }
			      persistSimulationProToStorage();
			      simulationProUpdatedAt = Date.now();
			      simulationProCaches = new Map();
			      renderSimulationAtTimeMs(simulationProTimeMs);
			      syncSimProUi();
			      if (uids.length === 1) renderProKeyframesForUid(uids[0]);
			      setStatus('Keyframe borrado.');
			    });

			    simProKfClearBtn?.addEventListener('click', () => {
			      if (!isSimulating || !simulationProEnabled) return;
			      const ok = window.confirm('¿Borrar TODOS los keyframes (Timeline Pro)?');
			      if (!ok) return;
			      simulationProTracks = {};
			      persistSimulationProToStorage();
			      simulationProUpdatedAt = Date.now();
			      simulationProCaches = new Map();
			      renderSimulationAtTimeMs(simulationProTimeMs);
			      syncSimProUi();
			      if (simProKfList) {
			        simProKfList.innerHTML = '<div class="timeline-empty">Keyframes borrados.</div>';
			        simProKfList.hidden = false;
			      }
			      setStatus('Keyframes borrados.');
			    });
			    simMagnetsInput?.addEventListener('change', () => {
			      simulationMagnets = !!simMagnetsInput.checked;
			      updateSimGuides(null);
			      setStatus(simulationMagnets ? 'Imanes activados.' : 'Imanes desactivados.');
			    });
			    simGuidesInput?.addEventListener('change', () => {
			      simulationGuides = !!simGuidesInput.checked;
			      if (!simulationGuides) {
			        hideSimGuides();
			        try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
			      }
			      setStatus(simulationGuides ? 'Guías activadas.' : 'Guías desactivadas.');
			    });
			    simCollisionInput?.addEventListener('change', () => {
			      simulationCollision = !!simCollisionInput.checked;
			      setStatus(simulationCollision ? 'Colisión suave activada.' : 'Colisión suave desactivada.');
			    });
			    simTrajectoriesInput?.addEventListener('change', () => {
			      simulationTrajectories = !!simTrajectoriesInput.checked;
			      if (!simulationTrajectories) clearSimMoveOverlays();
			      setStatus(simulationTrajectories ? 'Trayectorias activadas.' : 'Trayectorias desactivadas.');
			    });
			    simRouteToggleBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      setRouteAddMode(!simRouteAddMode);
			    });
			    simRouteUndoBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      const target = activeRouteTarget();
			      if (!target) return setStatus('Selecciona una ficha (o el balón) para editar su ruta.', true);
			      undoRoutePoint(target.uid);
			    });
			    simRouteClearBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      const target = activeRouteTarget();
			      if (!target) return setStatus('Selecciona una ficha (o el balón) para limpiar su ruta.', true);
			      clearRoute(target.uid);
			    });
			    simRouteSplineInput?.addEventListener('change', () => {
			      if (!isSimulating) return;
			      const target = activeRouteTarget();
			      if (!target) return;
			      setRouteSpline(target.uid, !!simRouteSplineInput.checked);
			    });
			    simBallFollowBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      const target = activeRouteTarget();
			      if (!target) return setStatus('Selecciona 1 ficha para pegarle el balón.', true);
			      setBallFollow(target.uid);
			    });
			    simBallPassBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      const objects = getSelectionObjects().filter((obj) => safeText(obj?.data?.kind) === 'token' && !obj?.data?.base);
			      if (objects.length < 2) {
			        setStatus('Selecciona 2 fichas (origen y destino) para crear un pase.', true);
			        return;
			      }
			      const u1 = safeText(objects[0]?.data?.layer_uid);
			      const u2 = safeText(objects[1]?.data?.layer_uid);
			      if (!u1 || !u2) {
			        setStatus('No se pudo leer la selección.', true);
			        return;
			      }
			      ensureBallRoutePass(u1, u2);
			    });
			    simSpeedSelect?.addEventListener('change', () => {
			      const val = Number(simSpeedSelect.value);
			      simulationSpeed = Number.isFinite(val) ? clamp(val, 0.5, 2) : 1.0;
			      setStatus(`Velocidad: ${simulationSpeed}×.`);
			    });
			    const syncSimulationMetaFromInputs = () => {
			      const step = simulationSteps[simulationActiveIndex];
			      if (!step) return;
			      step.title = safeText(simStepTitleInput?.value, step.title || `Paso ${simulationActiveIndex + 1}`);
			      step.duration = clamp(Number(simStepDurationInput?.value) || step.duration || 3, 1, 20);
			      renderSimulationSteps();
			      if (simulationProEnabled) {
			        simulationProCaches = new Map();
			        syncSimProUi();
			        persistSimulationProToStorage();
			      }
			    };
			    simStepTitleInput?.addEventListener('input', () => {
			      if (!isSimulating) return;
			      if (simulationPlaying) return;
			      syncSimulationMetaFromInputs();
			    });
			    simStepDurationInput?.addEventListener('change', () => {
			      if (!isSimulating) return;
			      if (simulationPlaying) return;
			      syncSimulationMetaFromInputs();
			    });
			    simStepsList?.addEventListener('click', (event) => {
			      const btn = event.target.closest('button[data-sim-step-index]');
			      if (!btn) return;
			      const idx = Number(btn.dataset.simStepIndex);
			      if (!Number.isFinite(idx)) return;
			      void selectSimulationStep(idx).then(() => {
			        if (!simulationProEnabled) return;
			        const starts = computeSimulationStepStartsMs();
			        simulationProCaches = new Map();
			        renderSimulationAtTimeMs(Number(starts?.[idx] || 0));
			        syncSimProUi();
			      });
			    });
			    simStepsList?.addEventListener('dragstart', (event) => {
			      const btn = event.target.closest('button[data-sim-step-index]');
			      if (!btn) return;
			      const idx = safeText(btn.dataset.simStepIndex);
			      event.dataTransfer?.setData('text/plain', idx);
			      if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
			      btn.classList.add('is-dragging');
			    });
			    simStepsList?.addEventListener('dragend', (event) => {
			      const btn = event.target.closest('button[data-sim-step-index]');
			      if (!btn) return;
			      btn.classList.remove('is-dragging');
			    });
			    simStepsList?.addEventListener('dragover', (event) => {
			      if (!event.dataTransfer) return;
			      event.preventDefault();
			      event.dataTransfer.dropEffect = 'move';
			    });
			    simStepsList?.addEventListener('drop', (event) => {
			      event.preventDefault();
			      const raw = safeText(event.dataTransfer?.getData('text/plain'));
			      const from = Number(raw);
			      if (!Number.isFinite(from)) return;
			      const targetBtn = event.target.closest('button[data-sim-step-index]');
			      if (!targetBtn) return;
			      const to = Number(safeText(targetBtn.dataset.simStepIndex));
			      if (!Number.isFinite(to)) return;
			      reorderSimulationSteps(from, to);
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
			          try { applyPitchSurface(presetSelect.value || 'full_pitch', pitchOrientation, pitchGrassStyle); } catch (error) { /* ignore */ }
		          try { canvas.calcOffset(); } catch (error) { /* ignore */ }
		        });
		      } catch (error) {
		        try { fitCanvas(true); } catch (e) { /* ignore */ }
			        try { applyPitchSurface(presetSelect.value || 'full_pitch', pitchOrientation, pitchGrassStyle); } catch (e) { /* ignore */ }
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
	            const factory = playerTokenFactory(tokenKind, legacyPlayer, { style: 'disk' });
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

		    const applyPitchSurface = (presetValue, orientationValue, grassStyleValue) => {
		      // Evita SVG anidados (innerHTML con <svg> completo) que luego rompen la previsualización y el PDF.
		      const markup = buildPitchSvg(presetValue, orientationValue, grassStyleValue);
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
	      applyPitchSurface(preset, pitchOrientation, pitchGrassStyle);
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
		      const out = { version: raw.version || '5.3.0', objects };
		      if (raw.pencilkit && typeof raw.pencilkit === 'object') out.pencilkit = raw.pencilkit;
		      return out;
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
				      const title = safeText(options?.title);
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
				          data: { kind: 'pdf_asset', asset_id: id, title },
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
				        data: { kind: 'pdf_asset', asset_id: id, placeholder: true, desiredSize: desired, title },
				      });
			      try { group.objectCaching = false; } catch (e) { /* ignore */ }
			      try { group.noScaleCache = true; } catch (e) { /* ignore */ }
				      return group;
				    };

				    const buildUrlAssetObject = (url, left, top, options = {}) => {
				      const key = normalizeUrlAsset(url);
				      const img = urlAssetImages.get(key);
				      const title = safeText(options?.title);
				      const desired = clamp(Number(options.desiredSize) || 56, 28, 220);
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
				          data: { kind: 'url_asset', url: key, title },
				        });
				        try { imageObj.objectCaching = false; } catch (e) { /* ignore */ }
				        try { imageObj.noScaleCache = true; } catch (e) { /* ignore */ }
				        return imageObj;
				      }
				      ensureUrlAssetLoaded(key);
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
				        stroke: 'rgba(244,180,0,0.55)',
				        strokeWidth: 2,
				      });
				      const label = new fabric.Text('IMG', {
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
				        data: { kind: 'url_asset', url: key, placeholder: true, desiredSize: desired, title },
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
				    const replaceUrlAssetPlaceholders = (url) => {
				      const key = normalizeUrlAsset(url);
				      const img = urlAssetImages.get(key);
				      if (!img) return;
				      const objects = canvas.getObjects().slice();
				      objects.forEach((obj) => {
				        if (!obj || !obj.data) return;
				        if (safeText(obj.data.kind) !== 'url_asset') return;
				        if (safeText(obj.data.url) !== key) return;
				        if (!obj.data.placeholder) return;
				        const center = obj.getCenterPoint();
				        const desired = clamp(Number(obj.data.desiredSize) || 56, 28, 220);
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
				          data: { kind: 'url_asset', url: key, title: safeText(obj.data.title) },
				        });
				        try { next.objectCaching = false; } catch (e) { /* ignore */ }
				        try { next.noScaleCache = true; } catch (e) { /* ignore */ }
				        normalizeEditableObject(next);
				        canvas.remove(obj);
				        canvas.add(next);
				      });
				      canvas.requestRenderAll();
				    };
				    const flushUrlAssetPendingRefresh = () => {
				      if (!urlAssetPendingRefresh.size) return;
				      const urls = Array.from(urlAssetPendingRefresh);
				      urlAssetPendingRefresh.clear();
				      urls.forEach((url) => {
				        try { replaceUrlAssetPlaceholders(url); } catch (error) { /* ignore */ }
				      });
				    };
				    // Revisa en background por si las imágenes terminan de cargar después de añadirlas.
				    try { window.setInterval(flushPdfAssetPendingRefresh, 650); } catch (e) { /* ignore */ }
				    try { window.setInterval(flushUrlAssetPendingRefresh, 650); } catch (e) { /* ignore */ }
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
		      // DragEvent (HTML5 DnD) no es un evento “nativo” de Fabric y en iOS a veces devuelve punteros 0,0.
		      // Para drop usamos boundingClientRect + viewportTransform (si aplica) para obtener coordenadas fiables.
		      let clientX = Number(event?.clientX);
		      let clientY = Number(event?.clientY);
		      if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) {
		        const touch = event?.touches?.[0] || event?.changedTouches?.[0];
		        clientX = Number(touch?.clientX);
		        clientY = Number(touch?.clientY);
		      }
		      const rectSource = canvas?.upperCanvasEl || canvas?.lowerCanvasEl || stage;
		      const rect = rectSource?.getBoundingClientRect?.() || stage.getBoundingClientRect();
		      const safeWidth = Math.max(1, Number(rect?.width) || 1);
		      const safeHeight = Math.max(1, Number(rect?.height) || 1);
		      const rawScreenX = ((clientX - rect.left) / safeWidth) * (Number(canvas.getWidth?.()) || 0);
		      const rawScreenY = ((clientY - rect.top) / safeHeight) * (Number(canvas.getHeight?.()) || 0);
		      let x = rawScreenX;
		      let y = rawScreenY;
		      if (useViewportMapping) {
		        const vpt = canvas.viewportTransform || [1, 0, 0, 1, 0, 0];
		        const scale = Number(vpt[0]) || 1;
		        const offsetX = Number(vpt[4]) || 0;
		        const offsetY = Number(vpt[5]) || 0;
		        x = (rawScreenX - offsetX) / scale;
		        y = (rawScreenY - offsetY) / scale;
		      }
		      const { w, h } = worldSize();
		      if (!Number.isFinite(x) || !Number.isFinite(y)) {
		        x = (Number(w) || 0) / 2;
		        y = (Number(h) || 0) / 2;
		      }
		      return {
		        x: clamp(x, 24, w - 24),
		        y: clamp(y, 24, h - 24),
		      };
		    };
		    const createFactoryFromPayload = (payload) => {
		      if (!payload || typeof payload !== 'object') return null;
		      const rawKind = safeText(payload.kind);
		      if (rawKind.startsWith('image_url:')) {
		        const url = rawKind.slice('image_url:'.length);
		        const desired = clamp(Number(payload.desiredSize) || 56, 28, 220);
		        const title = safeText(payload.title);
		        return {
		          factory: (left, top) => buildUrlAssetObject(url, left, top, { desiredSize: desired, title }),
		          label: title || 'una imagen',
		        };
		      }
		      if (rawKind.startsWith('pdf_asset:')) {
		        const assetId = rawKind.split(':')[1] || '';
		        const desired = clamp(Number(payload.desiredSize) || 56, 28, 180);
		        const title = safeText(payload.title);
		        return {
		          factory: (left, top) => buildPdfAssetObject(assetId, left, top, { desiredSize: desired, title }),
		          label: title || 'un recurso gráfico',
		        };
		      }
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

		    const applyAssistantBoardTemplate = (detail = {}) => {
		      if (isSimulating) {
		        setStatus('Modo simulación: no se puede aplicar una plantilla. Sal del simulador.', true);
		        return false;
		      }
		      const items = Array.isArray(detail?.items) ? detail.items : [];
		      const shouldClear = detail?.clear === true;
		      const { w, h } = worldSize();
		      const toAbs = (value, max) => {
		        const num = Number(value);
		        if (!Number.isFinite(num)) return null;
		        if (num >= 0 && num <= 1) return clamp(num * max, 24, max - 24);
		        return clamp(num, 24, max - 24);
		      };

		      try { clearPendingPlacement(); } catch (e) { /* ignore */ }
		      pendingFactory = null;
		      backgroundPickMode = false;
		      if (freeDrawMode) {
		        freeDrawMode = false;
		        try { canvas.isDrawingMode = false; } catch (e) { /* ignore */ }
		      }

		      if (shouldClear) {
		        const existing = (canvas.getObjects?.() || []).slice().filter((obj) => obj && !(obj?.data?.base));
		        existing.forEach((obj) => {
		          try { canvas.remove(obj); } catch (e) { /* ignore */ }
		        });
		        try { canvas.discardActiveObject(); } catch (e) { /* ignore */ }
		      }

		      const added = [];
		      items.slice(0, 64).forEach((item) => {
		        const payload = item?.payload;
		        if (!payload) return;
		        const x = toAbs(item?.x, w);
		        const y = toAbs(item?.y, h);
		        if (x == null || y == null) return;
		        const resolved = createFactoryFromPayload(payload);
		        if (!resolved?.factory) return;
			        try {
			          const obj = objectAtPointer(resolved.factory, { x, y });
			          if (!obj) return;
			          const angle = Number(item?.angle);
			          const scale = Number(item?.scale);
			          const scaleX = Number(item?.scaleX);
			          const scaleY = Number(item?.scaleY);
			          const opacity = Number(item?.opacity);
			          try {
			            const next = {};
			            if (Number.isFinite(angle)) next.angle = angle;
			            if (Number.isFinite(opacity)) next.opacity = clamp(opacity, 0.05, 1);
			            if (Number.isFinite(scale)) {
			              next.scaleX = clampScale(scale, 12);
			              next.scaleY = clampScale(scale, 12);
			            } else {
			              if (Number.isFinite(scaleX)) next.scaleX = clampScale(scaleX, 12);
			              if (Number.isFinite(scaleY)) next.scaleY = clampScale(scaleY, 12);
			            }
			            if (Object.keys(next).length) obj.set(next);
			          } catch (e) { /* ignore */ }
			          // Evita el coste de addObject() por cada elemento; añadimos en batch.
			          if (isBackgroundShape(obj)) {
			            obj.data = obj.data || {};
			            obj.data.background_edit = true;
			          }
		          normalizeEditableObject(obj);
		          canvas.add(obj);
		          if (isBackgroundShape(obj)) canvas.sendToBack(obj);
		          added.push(obj);
		        } catch (e) { /* ignore */ }
		      });

		      if (!added.length && !shouldClear) return false;
		      try { canvas.discardActiveObject(); } catch (e) { /* ignore */ }
		      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
		      pushHistory();
		      syncInspector();
		      setStatus(added.length ? `Plantilla aplicada (${added.length} elementos).` : 'Plantilla aplicada.');
		      return true;
		    };
		    const registerDraggableButton = (button, payloadBuilder) => {
		      if (!button) return;
		      button.draggable = true;
      // iPad/iOS: HTML5 drag & drop es poco fiable. Añadimos “drag” por pointer events
      // para poder arrastrar recursos desde la biblioteca al campo.
      let touchDrag = null;
      let touchDragConsumedClick = false;
      const isTouchLikePointer = (event) => {
        const pt = safeText(event?.pointerType);
        if (pt === 'touch' || pt === 'pen') return true;
        try { return (Number(navigator.maxTouchPoints) || 0) > 0; } catch (e) { return false; }
      };
      let dragIndicator = null;
      const ensureDragIndicator = () => {
        if (dragIndicator) return dragIndicator;
        try {
          dragIndicator = document.createElement('div');
          dragIndicator.className = 'tpad-drag-indicator';
          dragIndicator.style.position = 'absolute';
          dragIndicator.style.left = '0';
          dragIndicator.style.top = '0';
          dragIndicator.style.width = '18px';
          dragIndicator.style.height = '18px';
          dragIndicator.style.borderRadius = '999px';
          dragIndicator.style.border = '2px solid rgba(244, 180, 0, 0.95)';
          dragIndicator.style.background = 'rgba(244, 180, 0, 0.18)';
          dragIndicator.style.boxShadow = '0 14px 26px rgba(2, 6, 23, 0.32)';
          dragIndicator.style.transform = 'translate(-50%, -50%)';
          dragIndicator.style.pointerEvents = 'none';
          dragIndicator.style.zIndex = '120';
          dragIndicator.hidden = true;
          stage?.appendChild?.(dragIndicator);
        } catch (e) {
          dragIndicator = null;
        }
        return dragIndicator;
      };
      const setIndicatorAt = (clientX, clientY, visible) => {
        const el = ensureDragIndicator();
        if (!el) return;
        if (!visible) {
          el.hidden = true;
          return;
        }
        const rect = stage?.getBoundingClientRect?.();
        if (!rect) return;
        const x = clamp((Number(clientX) || 0) - rect.left, 0, rect.width || 0);
        const y = clamp((Number(clientY) || 0) - rect.top, 0, rect.height || 0);
        el.style.left = `${x}px`;
        el.style.top = `${y}px`;
        el.hidden = false;
      };
      const clearTouchDrag = () => {
        touchDrag = null;
        try { button.classList.remove('is-dragging'); } catch (e) { /* ignore */ }
        try { stage.classList.remove('is-drop-target'); } catch (e) { /* ignore */ }
        try { setIndicatorAt(0, 0, false); } catch (e) { /* ignore */ }
        try { window.removeEventListener('pointermove', onTouchDragMove, true); } catch (e) { /* ignore */ }
        try { window.removeEventListener('pointerup', onTouchDragEnd, true); } catch (e) { /* ignore */ }
        try { window.removeEventListener('pointercancel', onTouchDragEnd, true); } catch (e) { /* ignore */ }
      };
      const onTouchDragMove = (event) => {
        if (!touchDrag || (touchDrag.pointerId != null && event.pointerId !== touchDrag.pointerId)) return;
        if (!event) return;
        const dx = (Number(event.clientX) || 0) - (Number(touchDrag.startX) || 0);
        const dy = (Number(event.clientY) || 0) - (Number(touchDrag.startY) || 0);
        const dist = Math.sqrt((dx * dx) + (dy * dy));
        if (!touchDrag.active) {
          if (dist < 10) return;
          touchDrag.active = true;
          touchDragConsumedClick = true;
          try { button.classList.add('is-dragging'); } catch (e) { /* ignore */ }
          setStatus('Suelta el recurso sobre el campo.');
        }
        try {
          const rect = stage?.getBoundingClientRect?.();
          const inside = rect
            && (Number(event.clientX) >= rect.left)
            && (Number(event.clientX) <= rect.right)
            && (Number(event.clientY) >= rect.top)
            && (Number(event.clientY) <= rect.bottom);
          stage.classList.toggle('is-drop-target', !!inside);
          setIndicatorAt(event.clientX, event.clientY, !!inside);
        } catch (e) { /* ignore */ }
        try {
          // Mientras arrastras, evitamos que el navegador haga scroll/zoom.
          event.preventDefault();
          event.stopPropagation();
        } catch (e) { /* ignore */ }
      };
      const onTouchDragEnd = (event) => {
        if (!touchDrag) return;
        const active = !!touchDrag.active;
        const payload = touchDrag.payload;
        clearTouchDrag();
        if (!active || !payload) return;
        try {
          const rect = stage?.getBoundingClientRect?.();
          const inside = rect
            && (Number(event?.clientX) >= rect.left)
            && (Number(event?.clientX) <= rect.right)
            && (Number(event?.clientY) >= rect.top)
            && (Number(event?.clientY) <= rect.bottom);
          if (!inside) return;
        } catch (e) { /* ignore */ }
        try {
          addPayloadAtPointer(payload, pointerFromStageEvent(event));
        } catch (e) { /* ignore */ }
        try {
          event?.preventDefault?.();
          event?.stopPropagation?.();
        } catch (e) { /* ignore */ }
      };
      // Si se ha hecho un drag por pointer, anulamos el click (si no, se activaría la colocación “por click”).
      button.addEventListener('click', (event) => {
        if (!touchDragConsumedClick) return;
        touchDragConsumedClick = false;
        try {
          event.preventDefault();
          event.stopPropagation();
        } catch (e) { /* ignore */ }
      }, true);

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

      button.addEventListener('pointerdown', (event) => {
        // Solo activamos el drag por pointer en touch/pen (en desktop ya tenemos HTML5 DnD).
        if (!isTouchLikePointer(event)) return;
        if (!event || (event.button != null && event.button !== 0)) return;
        const payload = payloadBuilder();
        if (!payload) return;
        touchDrag = {
          payload,
          startX: Number(event.clientX) || 0,
          startY: Number(event.clientY) || 0,
          pointerId: event.pointerId,
          active: false,
        };
        try { button.setPointerCapture(event.pointerId); } catch (e) { /* ignore */ }
        try { window.addEventListener('pointermove', onTouchDragMove, { capture: true, passive: false }); } catch (e) { /* ignore */ }
        try { window.addEventListener('pointerup', onTouchDragEnd, { capture: true, passive: false }); } catch (e) { /* ignore */ }
        try { window.addEventListener('pointercancel', onTouchDragEnd, { capture: true, passive: false }); } catch (e) { /* ignore */ }
      }, { passive: true });
    };

		    // Acciones rápidas (ideal iPad): deshacer/rehacer/duplicar/borrar siempre arriba.
		    const quickTools = document.getElementById('task-pitch-quick-tools');
			    quickTools?.addEventListener('click', (event) => {
			      const btn = event.target.closest('button[data-action]');
			      if (!btn) return;
			      const action = safeText(btn.dataset.action);
			      if (!action) return;
			      event.preventDefault();
			      try { handleCanvasAction(action); } catch (e) { /* ignore */ }
			    });

			    const resolvePlayerPhotoUrl = (candidate) => {
			      const url = safeText(candidate);
			      if (!url) return '';
			      if (url.startsWith('data:')) return url;
			      if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('/')) return url;
			      return url;
			    };
			    const loadPhotoIntoGroup = (group, url, radius) => {
			      const src = resolvePlayerPhotoUrl(url);
			      if (!group || !src) return;
			      try {
			        const shouldUseAnonymousCors = (() => {
			          try {
			            const resolved = new URL(src, window.location.href);
			            return resolved.origin !== window.location.origin;
			          } catch (e) {
			            return false;
			          }
			        })();
			        const img = new Image();
			        // Solo forzamos CORS anónimo si la imagen es cross-origin; en same-origin
			        // dejamos que el navegador envíe credenciales (p.ej. /media/ protegidos).
			        if (shouldUseAnonymousCors) {
			          try { img.crossOrigin = 'anonymous'; } catch (e) { /* ignore */ }
			        }
			        img.onload = () => {
			          try {
			            const naturalW = Number(img.naturalWidth || img.width || 1);
			            const naturalH = Number(img.naturalHeight || img.height || 1);
			            const targetSize = Math.max(1, radius * 2);
			            const scale = targetSize / Math.max(1, Math.min(naturalW, naturalH));
			            const photo = new fabric.Image(img, {
			              left: 0,
			              top: 0,
			              originX: 'center',
			              originY: 'center',
			              selectable: false,
			              evented: false,
			              scaleX: scale,
			              scaleY: scale,
			            });
			            photo.clipPath = new fabric.Circle({
			              radius,
			              originX: 'center',
			              originY: 'center',
			              left: 0,
			              top: 0,
			            });
			            photo.data = { role: 'token_photo' };
			            group.addWithUpdate(photo);
			            group.dirty = true;
			            canvas?.requestRenderAll?.();
			          } catch (e) { /* ignore */ }
			        };
			        img.onerror = () => { /* ignore */ };
			        img.src = src;
			      } catch (e) { /* ignore */ }
			    };

				    const playerTokenFactory = (kind, player, options = {}) => (left, top) => {
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
		      const style = normalizeTokenStyle(options?.style || player?.token_style || tokenGlobalStyle);
		      const pattern = normalizeTokenPattern(options?.pattern || player?.token_pattern || 'striped');
		      const defaultBase = kind === 'player_away' ? '#facc15' : '#ffffff';
		      const defaultStripe = kind === 'player_local' ? '#0f7a35' : palette.fill;
		      const baseColor = parseColorToHex(options?.base, parseColorToHex(player?.token_base_color, defaultBase)) || defaultBase;
		      const stripeColor = parseColorToHex(options?.stripe, parseColorToHex(player?.token_stripe_color, defaultStripe)) || defaultStripe;
		      const photoUrl = resolvePlayerPhotoUrl(options?.photoUrl || player?.photo_url);
		      const effectiveBase = pattern === 'solid' ? stripeColor : baseColor;
		      // Estilo "chapa" (igual que en la plantilla de abajo): disco con dorsal centrado y nombre simple.
		      // Evitamos el "jersey" y los cartuchos para que dentro del campo se vea igual que fuera.
		      if (kind === 'player_local' || kind === 'player_away' || kind === 'goalkeeper_local') {
		        const radius = 22;
		        baseRadius = radius;
		        const isAway = kind === 'player_away';
		        const isGoalkeeper = kind === 'goalkeeper_local';
		        if (style === 'photo') {
		          const border = new fabric.Circle({
		            radius,
		            fill: effectiveBase,
		            stroke: 'rgba(255,255,255,0.92)',
		            strokeWidth: 2,
		            originX: 'center',
		            originY: 'center',
		            left: 0,
		            top: 0,
		            shadow: 'rgba(15,23,42,0.28) 0 6px 14px',
		          });
		          border.data = { role: 'token_base' };
		          tokenParts.push(border);
		          const placeholder = new fabric.Circle({
		            radius: radius - 2.5,
		            fill: 'rgba(15,23,42,0.22)',
		            originX: 'center',
		            originY: 'center',
		            left: 0,
		            top: 0,
		            strokeWidth: 0,
		          });
		          placeholder.data = { role: 'token_photo_bg' };
		          tokenParts.push(placeholder);
		          const initialsText = new fabric.Text(initials, {
		            originX: 'center',
		            originY: 'center',
		            left: 0,
		            top: 0,
		            fontSize: 13,
		            fontWeight: '800',
		            fill: '#e2e8f0',
		          });
		          initialsText.data = { role: 'token_initials' };
		          tokenParts.push(initialsText);

		          const numberText = new fabric.Text(isGoalkeeper ? 'GK' : label, {
		            originX: 'center',
		            originY: 'center',
		            left: 0,
		            top: 18,
		            fontSize: 10,
		            fontWeight: '800',
		            fill: '#ffffff',
		            backgroundColor: 'rgba(15,23,42,0.92)',
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
		        } else if (style === 'jersey') {
		          const shirtDef = 'M -22 -18 L -10 -18 L -6 -26 L 6 -26 L 10 -18 L 22 -18 L 16 -2 L 16 22 L -16 22 L -16 -2 Z';
		          const shirtPath = new fabric.Path(shirtDef, {
		            left: 0,
		            top: 0,
		            originX: 'center',
		            originY: 'center',
		            fill: effectiveBase,
		            stroke: 'rgba(255,255,255,0.92)',
		            strokeWidth: 2,
		            shadow: 'rgba(15,23,42,0.28) 0 6px 14px',
		          });
		          shirtPath.data = { role: 'token_base' };
		          tokenParts.push(shirtPath);
		          if (!isAway && !isGoalkeeper) {
		            const stripeWidth = 8;
		            const stripeCount = 7;
		            const start = -24 + (stripeWidth / 2);
		            const stripes = [];
		            for (let i = 0; i < stripeCount; i += 1) {
		              const isStripe = i % 2 === 0;
		              const stripe = new fabric.Rect({
		                left: start + (i * stripeWidth),
		                top: 0,
		                width: stripeWidth,
		                height: 64,
		                fill: isStripe ? stripeColor : effectiveBase,
		                originX: 'center',
		                originY: 'center',
		              });
		              stripe.data = { role: isStripe ? 'token_stripe' : 'token_stripe_base' };
		              stripes.push(stripe);
		            }
		            const stripeGroup = new fabric.Group(stripes, {
		              originX: 'center',
		              originY: 'center',
		              left: 0,
		              top: 0,
		              selectable: false,
		              evented: false,
		            });
		            stripeGroup.clipPath = new fabric.Path(shirtDef, {
		              left: 0,
		              top: 0,
		              originX: 'center',
		              originY: 'center',
		            });
		            stripeGroup.data = { role: 'token_stripes' };
		            tokenParts.push(stripeGroup);
		          }
		          const numberText = new fabric.Text(isGoalkeeper ? 'GK' : label, {
		            originX: 'center',
		            originY: 'center',
		            left: 0,
		            top: -2,
		            fontSize: 14,
		            fontWeight: '800',
		            fill: '#ffffff',
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
		          const baseCircle = new fabric.Circle({
		            radius,
		            fill: isAway ? stripeColor : effectiveBase,
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
		              fill: isGreen ? stripeColor : effectiveBase,
		              originX: 'center',
		              originY: 'center',
		            });
		            stripe.data = { role: isGreen ? 'token_stripe' : 'token_stripe_base' };
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
		        }
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
			          token_style: style,
			          token_pattern: pattern,
			          token_base_color: baseColor,
			          token_stripe_color: stripeColor,
			          color: kind === 'player_local' ? stripeColor : (kind === 'player_away' ? stripeColor : palette.fill),
			          playerId: player?.id || '',
			          playerName,
			          playerNumber: safeText(label),
			          playerPhotoUrl: photoUrl,
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
			      if (style === 'photo' && photoUrl) {
			        try { loadPhotoIntoGroup(group, photoUrl, 19.2); } catch (e) { /* ignore */ }
			      }
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
		      if (normalized.startsWith('image_url:')) {
		        const url = normalized.slice('image_url:'.length);
		        return (left, top) => buildUrlAssetObject(url, left, top);
		      }
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
		        return (left, top) => new fabric.Line([-220, 0, 220, 0], {
		          left, top, originX: 'center', originY: 'center',
		          stroke: '#f8fafc', strokeWidth: 3, data: { kind: 'line' },
		        });
		      }
		      if (kind === 'line_thick') {
		        return (left, top) => new fabric.Line([-240, 0, 240, 0], {
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
		        return (left, top) => new fabric.Line([-220, 0, 220, 0], {
		          left, top, originX: 'center', originY: 'center',
		          stroke: '#f8fafc', strokeWidth: 3, strokeDashArray: [12, 8], data: { kind: 'line-dash' },
		        });
		      }
		      if (kind === 'line_dot') {
		        return (left, top) => new fabric.Line([-220, 0, 220, 0], {
		          left, top, originX: 'center', originY: 'center',
		          stroke: '#f8fafc', strokeWidth: 3, strokeDashArray: [2, 9], strokeLineCap: 'round', data: { kind: 'line-dot' },
		        });
		      }
	      if (kind === 'line_double') {
	        return (left, top) => new fabric.Group([
	          new fabric.Line([-220, -10, 220, -10], { stroke: '#f8fafc', strokeWidth: 3 }),
	          new fabric.Line([-220, 10, 220, 10], { stroke: '#f8fafc', strokeWidth: 3 }),
	        ], { left, top, originX: 'center', originY: 'center', data: { kind: 'line-double' } });
	      }
	      const buildArrowGroup = (left, top, options = {}) => {
	        const stroke = safeText(options.stroke, '#22d3ee');
	        const strokeWidth = clamp(Number(options.strokeWidth) || 4, 2, 18);
	        const dash = Array.isArray(options.dash) ? options.dash : null;
	        const cap = safeText(options.cap, 'round') || 'round';
	        const headSize = clamp(Number(options.headSize) || (strokeWidth >= 7 ? 28 : 18), 14, 44);
	        const headOffset = clamp(Number(options.headOffset) || (headSize / 2 + 6), 14, 60);
		        const baseLen = clamp(Number(options.baseLen) || 320, 60, 520);
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

		    // Integración: permite que el Asistente (en la plantilla HTML) coloque recursos de forma programática
		    // sin exponer el canvas globalmente.
		    window.addEventListener('webstats:tpad:assistant-board', (event) => {
		      try { applyAssistantBoardTemplate(event?.detail || {}); } catch (e) { /* ignore */ }
		    });

			    const restoreState = () => {
		      let parsed = { version: '5.3.0', objects: [] };
	      try {
	        parsed = JSON.parse(stateInput?.value || '{"version":"5.3.0","objects":[]}');
	      } catch (error) {
	        parsed = { version: '5.3.0', objects: [] };
	      }
		      // Fase 9: rehidrata simulación guardada (si existe) desde el canvas_state.
		    const normalizeSimulationSteps = (raw) => {
		        if (!Array.isArray(raw)) return [];
		        return raw
		          .map((step, index) => {
		            if (!step || typeof step !== 'object') return null;
		            const state = step.canvas_state;
		            if (!state || typeof state !== 'object') return null;
		            const title = safeText(step.title, `Paso ${index + 1}`);
		            const duration = clamp(Number(step.duration) || 3, 1, 20);
		            const width = parseIntSafe(step.canvas_width) || 0;
		            const height = parseIntSafe(step.canvas_height) || 0;
		            const moves = Array.isArray(step.moves) ? step.moves.slice(0, 80) : [];
		            const routes = (step.routes && typeof step.routes === 'object') ? step.routes : {};
		            const ballFollowUid = safeText(step.ball_follow_uid);
		            return {
		              title,
		              duration,
		              canvas_state: sanitizeLoadedState(state),
		              canvas_width: width,
		              canvas_height: height,
		              moves,
		              routes,
		              ball_follow_uid: ballFollowUid,
		            };
		          })
		          .filter(Boolean)
		          .slice(0, 24);
		      };
		      try {
		        const saved = parsed && typeof parsed === 'object' ? parsed.simulation : null;
		        const steps = saved && typeof saved === 'object' ? saved.steps : null;
		        const normalized = normalizeSimulationSteps(steps);
			        if (normalized.length) {
			          simulationSavedSteps = normalized;
			          simulationSavedUpdatedAt = Date.now();
			          // Espejo local (por si el usuario todavía no guarda la tarea).
			          try {
			            if (canUseStorage) {
			              const proFromCanvas = (saved && typeof saved === 'object' && saved.pro && typeof saved.pro === 'object') ? saved.pro : null;
			              const payload = { v: 1, updated_at: new Date().toISOString(), steps: normalized };
			              if (proFromCanvas) payload.pro = proFromCanvas;
			              window.localStorage.setItem(simStorageKey, JSON.stringify(payload));
			              if (proFromCanvas) restoreSimulationProFromStorage();
			            }
			          } catch (err) { /* ignore */ }
			        } else {
		          // Fallback: si no viene en canvas_state, intenta restaurar desde localStorage.
		          try {
		            if (canUseStorage) {
		              const raw = safeText(window.localStorage.getItem(simStorageKey));
		              const parsedStore = raw ? JSON.parse(raw) : null;
		              const storedSteps = parsedStore && typeof parsedStore === 'object' ? parsedStore.steps : null;
		              const storedPro = parsedStore && typeof parsedStore === 'object' ? parsedStore.pro : null;
		              const restored = normalizeSimulationSteps(storedSteps);
		              if (restored.length) {
		                simulationSavedSteps = restored;
		                simulationSavedUpdatedAt = Date.now();
		                if (storedPro && typeof storedPro === 'object') {
		                  try {
		                    // Reusa la lógica oficial de restore pro.
		                    window.localStorage.setItem(simStorageKey, JSON.stringify({ ...(parsedStore || {}), pro: storedPro, steps: restored }));
		                    restoreSimulationProFromStorage();
		                  } catch (e) { /* ignore */ }
		                }
		              }
		            }
		          } catch (err) { /* ignore */ }
		        }
		      } catch (error) { /* ignore */ }

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
	        const style = normalizeTokenStyle(tokenGlobalStyle);
	        const badge = document.createElement('span');
	        const number = document.createElement('span');
	        number.className = 'token-number';
	        number.textContent = kind === 'goalkeeper_local' ? 'GK' : (player.number ? String(player.number).slice(0, 2) : 'J');

	        if (style === 'jersey') {
	          const clipId = `tpad-shirt-clip-${String(player.id || '').replace(/[^a-zA-Z0-9_-]/g, '') || 'x'}`;
	          const gkGradId = `tpad-gk-grad-${String(player.id || '').replace(/[^a-zA-Z0-9_-]/g, '') || 'x'}`;
	          badge.className = 'token-jersey';
	          if (kind === 'goalkeeper_local') badge.classList.add('is-goalkeeper');
	          badge.innerHTML = `
	            <svg class="token-jersey-svg" viewBox="-26 -30 52 60" aria-hidden="true" focusable="false">
	              <defs>
	                <clipPath id="${clipId}">
	                  <path d="M -22 -18 L -10 -18 L -6 -26 L 6 -26 L 10 -18 L 22 -18 L 16 -2 L 16 22 L -16 22 L -16 -2 Z"></path>
	                </clipPath>
	                <linearGradient id="${gkGradId}" x1="0" y1="0" x2="1" y2="1">
	                  <stop offset="0" stop-color="#1d4ed8"></stop>
	                  <stop offset="1" stop-color="#0ea5e9"></stop>
	                </linearGradient>
	              </defs>
	              <g clip-path="url(#${clipId})">
	                <rect x="-28" y="-32" width="56" height="64" fill="${kind === 'goalkeeper_local' ? `url(#${gkGradId})` : '#f8fafc'}"></rect>
	                ${kind === 'goalkeeper_local' ? '' : `
	                  <g>
	                    <rect x="-28" y="-32" width="8" height="64" fill="#0f7a35"></rect>
	                    <rect x="-20" y="-32" width="8" height="64" fill="#f8fafc"></rect>
	                    <rect x="-12" y="-32" width="8" height="64" fill="#0f7a35"></rect>
	                    <rect x="-4" y="-32" width="8" height="64" fill="#f8fafc"></rect>
	                    <rect x="4" y="-32" width="8" height="64" fill="#0f7a35"></rect>
	                    <rect x="12" y="-32" width="8" height="64" fill="#f8fafc"></rect>
	                    <rect x="20" y="-32" width="8" height="64" fill="#0f7a35"></rect>
	                  </g>
	                `}
	              </g>
	              <path d="M -22 -18 L -10 -18 L -6 -26 L 6 -26 L 10 -18 L 22 -18 L 16 -2 L 16 22 L -16 22 L -16 -2 Z"
	                    fill="none" stroke="rgba(255,255,255,0.92)" stroke-width="2"></path>
	            </svg>
	          `.trim();
	          badge.appendChild(number);
	        } else if (style === 'photo') {
	          badge.className = 'token-photo';
	          if (kind === 'goalkeeper_local') badge.classList.add('is-goalkeeper');
	          const photoUrl = resolvePlayerPhotoUrl(player?.photo_url);
	          if (photoUrl) {
	            badge.style.backgroundImage = `url("${photoUrl.replace(/"/g, '\\"')}")`;
	          } else {
	            const initials = document.createElement('span');
	            initials.className = 'token-initials';
	            initials.textContent = computeInitials(player?.name, number.textContent);
	            badge.appendChild(initials);
	          }
	          badge.appendChild(number);
	        } else {
	          badge.className = 'token-disk';
	          if (kind === 'goalkeeper_local') badge.classList.add('is-goalkeeper');
	          badge.appendChild(number);
	        }

	        button.appendChild(name);
	        button.appendChild(badge);
	        registerDraggableButton(button, () => ({ kind, playerId: String(player.id) }));
			        button.addEventListener('click', () => {
			          if (freeDrawMode) handleCanvasAction('draw_free');
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
			      if (exportInFlight || isSimulating) return;
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
			      const buildCanvasStateForSave = () => {
			        const state = serializeState();
			        try {
			          if (Array.isArray(simulationSavedSteps) && simulationSavedSteps.length) {
			            state.simulation = {
			              v: 1,
			              updated_at: simulationSavedUpdatedAt ? new Date(simulationSavedUpdatedAt).toISOString() : '',
			              steps: simulationSavedSteps,
			            };
			            try {
			              const hasTracks = simulationProTracks && typeof simulationProTracks === 'object' && Object.keys(simulationProTracks || {}).length >= 1;
			              if (hasTracks || simulationProEnabled) {
			                state.simulation.pro = {
			                  v: 1,
			                  enabled: !!simulationProEnabled,
			                  loop: !!simulationProLoop,
			                  updated_at: new Date().toISOString(),
			                  tracks: simulationProTracks || {},
			                };
			              }
			            } catch (err) { /* ignore */ }
			          } else {
			            delete state.simulation;
			          }
			        } catch (error) { /* ignore */ }
			        return state;
			      };
			      const stateObj = buildCanvasStateForSave();
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

	      const isCapacitor = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
	      const isStandalone = (() => {
	        try {
	          if (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) return true;
	          if (window.matchMedia && window.matchMedia('(display-mode: fullscreen)').matches) return true;
	        } catch (e) { /* ignore */ }
	        try {
	          if (typeof navigator !== 'undefined' && navigator && navigator.standalone) return true;
	        } catch (e) { /* ignore */ }
	        return false;
	      })();
	      const isMobileLike = (() => {
	        try {
	          if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) return true;
	        } catch (e) { /* ignore */ }
	        try {
	          return Math.min(window.innerWidth || 9999, window.innerHeight || 9999) < 820;
	        } catch (e) {
	          return false;
	        }
	      })();
	      const shouldUseOverlay = isCapacitor || isStandalone || isMobileLike;
      const ensurePdfOverlay = () => {
        let overlay = document.getElementById('tpad-pdf-overlay');
        if (overlay) return overlay;
        overlay = document.createElement('div');
        overlay.id = 'tpad-pdf-overlay';
        overlay.style.cssText = [
          'position:fixed',
          'inset:0',
          'z-index:2147483647',
          'background:rgba(2,6,23,0.78)',
          'display:none',
          'flex-direction:column',
        ].join(';');
        overlay.innerHTML = `
          <div style="display:flex;align-items:center;gap:0.6rem;padding:0.65rem 0.75rem;background:rgba(7,16,30,0.96);border-bottom:1px solid rgba(255,255,255,0.12);">
            <button type="button" id="tpad-pdf-close" style="appearance:none;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.06);color:rgba(245,247,250,0.92);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;cursor:pointer;">Cerrar</button>
            <button type="button" id="tpad-pdf-print" style="appearance:none;border:1px solid rgba(244,180,0,0.22);background:rgba(244,180,0,0.10);color:rgba(255,249,232,0.95);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;cursor:pointer;">Imprimir</button>
            <a id="tpad-pdf-download" href="#" style="margin-left:auto;appearance:none;border:1px solid rgba(70,211,255,0.22);background:rgba(70,211,255,0.10);color:rgba(230,236,255,0.95);border-radius:999px;padding:0.5rem 0.9rem;font-weight:900;letter-spacing:0.08em;text-transform:uppercase;font-size:0.72rem;text-decoration:none;">Descargar</a>
          </div>
          <iframe id="tpad-pdf-frame" title="PDF" style="flex:1;border:0;width:100%;background:#ffffff;"></iframe>
        `;
        document.body.appendChild(overlay);

        const close = () => {
          const frame = document.getElementById('tpad-pdf-frame');
          try {
            const currentUrl = frame?.dataset?.blobUrl || '';
            if (currentUrl && currentUrl.startsWith('blob:')) URL.revokeObjectURL(currentUrl);
          } catch (e) { /* ignore */ }
          if (frame) {
            try { frame.removeAttribute('src'); } catch (e) { /* ignore */ }
            try { frame.removeAttribute('srcdoc'); } catch (e) { /* ignore */ }
            try { frame.dataset.blobUrl = ''; } catch (e) { /* ignore */ }
          }
          overlay.style.display = 'none';
        };
        overlay.querySelector('#tpad-pdf-close')?.addEventListener('click', close);
        overlay.addEventListener('click', (ev) => {
          if (ev.target === overlay) close();
        });
        document.addEventListener('keydown', (ev) => {
          if (ev.key === 'Escape' && overlay.style.display !== 'none') close();
        });
        overlay.querySelector('#tpad-pdf-print')?.addEventListener('click', () => {
          const frame = document.getElementById('tpad-pdf-frame');
          try {
            frame?.contentWindow?.focus?.();
            frame?.contentWindow?.print?.();
          } catch (e) {
            // ignore
          }
        });
        return overlay;
      };
      const openPdfOverlay = ({ blobUrl = '', filename = '' } = {}) => {
        const overlay = ensurePdfOverlay();
        const frame = overlay.querySelector('#tpad-pdf-frame');
        const download = overlay.querySelector('#tpad-pdf-download');
        if (download) {
          download.setAttribute('href', blobUrl || '#');
          try {
            if (filename) download.setAttribute('download', filename);
          } catch (e) { /* ignore */ }
        }
        if (frame) {
          try { frame.dataset.blobUrl = blobUrl || ''; } catch (e) { /* ignore */ }
          if (blobUrl) frame.setAttribute('src', blobUrl);
        }
        overlay.style.display = 'flex';
      };

			      await syncHiddenBuilderFields({
			        // PNG para mantener líneas nítidas y sin artefactos JPEG en el PDF.
			        previewOptions: { maxWidth: 4096, mime: 'image/png', quality: 0.98 },
			        applyLivePreview: false,
			      });
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

      // iOS/Capacitor: `window.open` crea una vista sin navegación ("página en blanco" sin salida).
      // En ese caso, descargamos el PDF por fetch y lo mostramos en un overlay con botón Cerrar.
	      if (shouldUseOverlay) {
        const payload = new FormData(form);
        // Evita enviar ficheros por error.
        Array.from(payload.entries()).forEach(([key, value]) => {
          if (value instanceof File) payload.delete(key);
        });
        let resp = null;
        try {
          resp = await fetch(resolvedAction, { method: 'POST', body: payload, credentials: 'include' });
        } catch (error) {
          setStatus('No se pudo conectar para generar el PDF.', true);
          return;
        }
        const ct = String(resp.headers.get('content-type') || '').toLowerCase();
        if (!resp.ok) {
          const text = await resp.text();
          setStatus(text || `No se pudo generar el PDF (HTTP ${resp.status}).`, true);
          return;
        }
        if (ct.includes('application/pdf')) {
          const blob = await resp.blob();
          const blobUrl = URL.createObjectURL(blob);
          const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value) || 'tarea';
          const filename = `${title}_${targetStyle}.pdf`;
          openPdfOverlay({ blobUrl, filename });
          return;
        }
        // Fallback HTML (servidor sin WeasyPrint/pydyf): mostrar en overlay para permitir salir.
        const html = await resp.text();
        const overlay = ensurePdfOverlay();
        const frame = overlay.querySelector('#tpad-pdf-frame');
        if (frame) {
          try { frame.removeAttribute('src'); } catch (e) { /* ignore */ }
          try { frame.srcdoc = html; } catch (e) { /* ignore */ }
        }
        overlay.style.display = 'flex';
        return;
      }

      // Desktop / navegadores con navegación: abrir una pestaña y enviar POST.
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
      const tempForm = document.createElement('form');
      tempForm.method = 'post';
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
		    // Si la tarea es nueva (sin objetos guardados), aseguramos que el "mundo" (canvas_width/height)
		    // coincide con el viewBox del SVG. Si no, el viewportTransform crea barras/offsets y los punteros
		    // quedan desincronizados: parece que no se pueden colocar chapas en todo el campo.
		    try {
		      const shouldNormalizeWorld = (() => {
		        if (!useViewportMapping) return false;
		        const rawState = safeText(stateInput?.value);
		        if (!rawState) return true;
		        try {
		          const parsed = JSON.parse(rawState);
		          const objects = Array.isArray(parsed?.objects) ? parsed.objects : [];
		          const hasObjects = objects.some((obj) => obj && typeof obj === 'object' && !(obj?.data?.base));
		          const tl = Array.isArray(parsed?.timeline) ? parsed.timeline : [];
		          const hasTimelineObjects = tl.some((step) => {
		            const st = step?.canvas_state;
		            const stepObjects = Array.isArray(st?.objects) ? st.objects : [];
		            return stepObjects.some((obj) => obj && typeof obj === 'object' && !(obj?.data?.base));
		          });
		          return !(hasObjects || hasTimelineObjects);
		        } catch (e) {
		          return true;
		        }
		      })();
		      if (shouldNormalizeWorld && widthInput && heightInput) {
		        const vbRaw = safeText(svgSurface?.getAttribute('viewBox'));
		        const parts = vbRaw.split(/\s+/).map((v) => Number(v)).filter((n) => Number.isFinite(n));
		        if (parts.length >= 4) {
		          const vbW = Math.round(parts[2]);
		          const vbH = Math.round(parts[3]);
		          const curW = parseIntSafe(widthInput.value) || 0;
		          const curH = parseIntSafe(heightInput.value) || 0;
		          if (vbW > 0 && vbH > 0 && (Math.abs(curW - vbW) > 6 || Math.abs(curH - vbH) > 6)) {
		            widthInput.value = String(vbW);
		            heightInput.value = String(vbH);
		            worldWidth = vbW;
		            worldHeight = vbH;
		          }
		        }
		      }
		    } catch (e) { /* ignore */ }
		    restoreState();
		    try { scheduleTacticalOverlayRefresh(); } catch (e) { /* ignore */ }
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
	      const isTacticsMode = (() => {
	        try { return safeText(form?.dataset?.tacticsMode) === '1'; } catch (e) { return false; }
	      })();
	      // En Táctica necesitamos ver pizarra + panel lateral a la vez. El toggle (Pizarra/Contenido)
	      // oculta uno de los paneles (modo board/text), lo que rompe "Simulador" porque el popover
	      // vive en el panel de la pizarra. Por eso lo desactivamos aquí.
	      if (isTacticsMode) {
	        try { tabs.style.display = 'none'; } catch (e) { /* ignore */ }
	        try {
	          document.body.classList.remove('task-mode-ready', 'task-mode-board', 'task-mode-text', 'task-mode-both');
	        } catch (e) { /* ignore */ }
	        try { window.localStorage.removeItem(storageKey); } catch (e) { /* ignore */ }
	        return;
	      }
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

			    canvas.on('object:modified', (event) => {
			      if (canvas.__loading) return;
			      if (event?.target?.data?.base) return;
			      if (isSimulating) {
			        hideSimGuides();
			        if (simulationAutoCapture && !simulationPlaying) {
			          const now = Date.now();
			          if (now - simulationLastAutoCaptureAt >= 450) {
			            simulationLastAutoCaptureAt = now;
			            captureSimulationStep();
			          }
			        }
			        return;
			      }
			      persistActiveStepSnapshot();
			      pushHistory();
			      syncInspector();
			      renderLayers();
			      refreshLivePreview();
			      scheduleTacticalOverlayRefresh();
			      schedulePlayerBankUpdate();
			      scheduleDraftSave('canvas');
			    });
		    canvas.on('object:added', (event) => {
		      if (event?.target?.data?.base) return;
		      const target = event?.target;
		      const deferSmartInkPath = (!canvas.__loading)
		        && freeDrawMode
		        && smartInkMode !== 'off'
		        && target
		        && target.type === 'path';
		      if (!canvas.__loading && !deferSmartInkPath) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		      }
		      refreshLivePreview();
		      scheduleTacticalOverlayRefresh();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		    });
		    canvas.on('object:removed', (event) => {
		      if (event?.target?.data?.base) return;
		      if (!canvas.__loading) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		      }
		      refreshLivePreview();
		      scheduleTacticalOverlayRefresh();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		    });

		    // Smart ink (Auto flecha): convierte un trazo a mano alzada en una flecha limpia y editable.
		    const extractCanvasPointsFromPath = (pathObj) => {
		      const path = pathObj?.path || pathObj?._path || pathObj?.get?.('path');
		      if (!Array.isArray(path) || !path.length) return [];
		      const fabric = window.fabric;
		      const out = [];
		      const offset = pathObj?.pathOffset || { x: 0, y: 0 };
		      const matrix = (typeof pathObj?.calcTransformMatrix === 'function') ? pathObj.calcTransformMatrix() : null;
		      const pushPoint = (x, y) => {
		        const rawX = Number(x);
		        const rawY = Number(y);
		        if (!Number.isFinite(rawX) || !Number.isFinite(rawY)) return;
		        let px = rawX - (Number(offset.x) || 0);
		        let py = rawY - (Number(offset.y) || 0);
		        if (fabric && matrix && fabric.util && typeof fabric.util.transformPoint === 'function' && fabric.Point) {
		          try {
		            const p = fabric.util.transformPoint(new fabric.Point(px, py), matrix);
		            px = Number(p?.x) || px;
		            py = Number(p?.y) || py;
		          } catch (e) { /* ignore */ }
		        }
		        out.push({ x: px, y: py });
		      };
		      path.forEach((seg) => {
		        if (!Array.isArray(seg) || !seg.length) return;
		        const cmd = safeText(seg[0]).toUpperCase();
		        if (cmd === 'M' || cmd === 'L') {
		          pushPoint(seg[1], seg[2]);
		          return;
		        }
		        if (cmd === 'Q') {
		          pushPoint(seg[3], seg[4]);
		          return;
		        }
		        if (cmd === 'C') {
		          pushPoint(seg[5], seg[6]);
		          return;
		        }
		      });
		      return out;
		    };
		    const maxDistanceToLine = (points, a, b) => {
		      const ax = Number(a?.x) || 0;
		      const ay = Number(a?.y) || 0;
		      const bx = Number(b?.x) || 0;
		      const by = Number(b?.y) || 0;
		      const dx = bx - ax;
		      const dy = by - ay;
		      const denom = Math.hypot(dx, dy) || 1;
		      let max = 0;
		      for (let i = 0; i < points.length; i += 1) {
		        const px = Number(points[i]?.x) || 0;
		        const py = Number(points[i]?.y) || 0;
		        const dist = Math.abs((dy * px) - (dx * py) + (bx * ay) - (by * ax)) / denom;
		        if (dist > max) max = dist;
		      }
		      return max;
		    };
		    const hexToRgb = (hex) => {
		      const raw = safeText(hex).trim().replace('#', '');
		      if (!raw) return null;
		      const full = raw.length === 3 ? raw.split('').map((c) => `${c}${c}`).join('') : raw;
		      if (full.length !== 6) return null;
		      const n = Number.parseInt(full, 16);
		      if (!Number.isFinite(n)) return null;
		      // eslint-disable-next-line no-bitwise
		      return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
		    };
		    const rgbaFromHex = (hex, alpha = 0.12) => {
		      const rgb = hexToRgb(hex);
		      if (!rgb) return `rgba(34,211,238,${clamp(Number(alpha) || 0.12, 0, 1)})`;
		      return `rgba(${rgb.r},${rgb.g},${rgb.b},${clamp(Number(alpha) || 0.12, 0, 1)})`;
		    };
		    const boundsForPoints = (points) => {
		      let minX = Infinity;
		      let minY = Infinity;
		      let maxX = -Infinity;
		      let maxY = -Infinity;
		      (points || []).forEach((p) => {
		        const x = Number(p?.x);
		        const y = Number(p?.y);
		        if (!Number.isFinite(x) || !Number.isFinite(y)) return;
		        if (x < minX) minX = x;
		        if (y < minY) minY = y;
		        if (x > maxX) maxX = x;
		        if (y > maxY) maxY = y;
		      });
		      if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
		        return { minX: 0, minY: 0, maxX: 0, maxY: 0, w: 0, h: 0, cx: 0, cy: 0, diag: 0 };
		      }
		      const w = Math.max(0, maxX - minX);
		      const h = Math.max(0, maxY - minY);
		      return { minX, minY, maxX, maxY, w, h, cx: minX + (w / 2), cy: minY + (h / 2), diag: Math.hypot(w, h) || 0 };
		    };
		    const polygonArea = (points) => {
		      if (!Array.isArray(points) || points.length < 3) return 0;
		      let sum = 0;
		      for (let i = 0; i < points.length; i += 1) {
		        const a = points[i];
		        const b = points[(i + 1) % points.length];
		        const ax = Number(a?.x) || 0;
		        const ay = Number(a?.y) || 0;
		        const bx = Number(b?.x) || 0;
		        const by = Number(b?.y) || 0;
		        sum += (ax * by) - (bx * ay);
		      }
		      return Math.abs(sum) / 2;
		    };
		    const polyLength = (points) => {
		      if (!Array.isArray(points) || points.length < 2) return 0;
		      let len = 0;
		      for (let i = 1; i < points.length; i += 1) {
		        const a = points[i - 1];
		        const b = points[i];
		        len += Math.hypot((Number(b?.x) || 0) - (Number(a?.x) || 0), (Number(b?.y) || 0) - (Number(a?.y) || 0)) || 0;
		      }
		      return len;
		    };
		    const isClosedStroke = (points) => {
		      if (!Array.isArray(points) || points.length < 3) return false;
		      const start = points[0];
		      const end = points[points.length - 1];
		      const b = boundsForPoints(points);
		      const dist = Math.hypot((Number(end?.x) || 0) - (Number(start?.x) || 0), (Number(end?.y) || 0) - (Number(start?.y) || 0)) || 0;
		      const tol = Math.max(18, (b.diag || 0) * 0.12);
		      return dist <= tol;
		    };
		    const classifySmartShape = (points) => {
		      const pts = Array.isArray(points) ? points : [];
		      if (pts.length < 2) return null;
		      const b = boundsForPoints(pts);
		      if (b.w < 24 && b.h < 24) return null;
		      const start = pts[0];
		      const end = pts[pts.length - 1];
		      const len = Math.hypot((Number(end?.x) || 0) - (Number(start?.x) || 0), (Number(end?.y) || 0) - (Number(start?.y) || 0)) || 0;
		      const wobble = maxDistanceToLine(pts, start, end);
		      if (len >= 70 && (wobble / Math.max(1, len)) <= 0.12) {
		        return { kind: 'line_solid', start, end };
		      }
		      const closed = isClosedStroke(pts);
		      if (!closed) return null;
		      const safeW = Math.max(1, b.w);
		      const safeH = Math.max(1, b.h);
		      const aspect = safeW / safeH;
		      const area = polygonArea(pts);
		      const perimeter = polyLength(pts) + Math.hypot((Number(pts[0]?.x) || 0) - (Number(pts[pts.length - 1]?.x) || 0), (Number(pts[0]?.y) || 0) - (Number(pts[pts.length - 1]?.y) || 0));
		      const circularity = perimeter > 0 ? (4 * Math.PI * area) / (perimeter * perimeter) : 0;
		      const boxArea = safeW * safeH;
		      const fillRatio = boxArea > 0 ? (area / boxArea) : 0;

		      if (circularity >= 0.72 && aspect >= 0.75 && aspect <= 1.33) {
		        return { kind: 'shape_circle', bounds: b };
		      }
		      if (fillRatio >= 0.68 && circularity <= 0.68) {
		        if (aspect >= 0.86 && aspect <= 1.18) return { kind: 'shape_square', bounds: b };
		        if (aspect >= 2.05 || aspect <= 0.49) return { kind: 'shape_rect_long', bounds: b };
		        return { kind: 'shape_rect', bounds: b };
		      }
		      return null;
		    };
		    const applySmartShapeStyle = (obj, stroke, strokeWidth) => {
		      if (!obj) return;
		      const fill = rgbaFromHex(stroke, 0.12);
		      try {
		        if (obj.type === 'circle' || obj.type === 'rect' || obj.type === 'triangle' || obj.type === 'path') {
		          obj.set({ stroke, strokeWidth, fill });
		        }
		        if (obj.type === 'line') {
		          obj.set({ stroke, strokeWidth });
		        }
		      } catch (e) { /* ignore */ }
		    };
		    const buildSmartArrowGroup = (start, end, options = {}) => {
		      const fabric = window.fabric;
		      if (!fabric) return null;
		      const sx = Number(start?.x) || 0;
		      const sy = Number(start?.y) || 0;
		      const ex = Number(end?.x) || 0;
		      const ey = Number(end?.y) || 0;
		      const dx = ex - sx;
		      const dy = ey - sy;
		      const len = Math.hypot(dx, dy) || 0;
		      if (len < 30) return null;
		      const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
		      const stroke = safeText(options.stroke, '#22d3ee') || '#22d3ee';
		      const strokeWidth = clamp(Number(options.strokeWidth) || 4, 1, 26);
		      const headSize = clamp(strokeWidth >= 7 ? 28 : 18, 14, 44);
		      const headOffset = clamp((headSize / 2) + 6, 14, 60);
		      // Ajusta para que el inicio y el fin coincidan con el gesto.
		      const baseLen = clamp(len - headOffset, 30, 2200);
		      const ux = (len > 0) ? (dx / len) : 1;
		      const uy = (len > 0) ? (dy / len) : 0;
		      const center = { x: sx + (ux * (baseLen / 2)), y: sy + (uy * (baseLen / 2)) };

		      const line = new fabric.Line([-(baseLen / 2), 0, (baseLen / 2) - (headSize / 2), 0], {
		        stroke,
		        strokeWidth,
		        strokeLineCap: 'round',
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
		      const group = new fabric.Group([line, head], {
		        left: center.x,
		        top: center.y,
		        originX: 'center',
		        originY: 'center',
		        angle,
		        data: { kind: 'arrow', stroke_color: stroke },
		      });
		      try { group.objectCaching = false; } catch (e) { /* ignore */ }
		      try { group.noScaleCache = true; } catch (e) { /* ignore */ }
		      return group;
		    };
		    const replacePathWithSmartObject = (pathObj, replacement) => {
		      if (!pathObj || !replacement) return false;
		      if (isSimulating) return false;
		      let prevLoading = false;
		      try { prevLoading = !!canvas.__loading; } catch (e) { prevLoading = false; }
		      try {
		        canvas.__loading = true;
		        try { canvas.remove(pathObj); } catch (e) { /* ignore */ }
		        normalizeEditableObject(replacement);
		        try { canvas.add(replacement); } catch (e) { /* ignore */ }
		      } finally {
		        try { canvas.__loading = prevLoading; } catch (e) { /* ignore */ }
		      }
		      try { canvas.setActiveObject(replacement); } catch (e) { /* ignore */ }
		      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
		      persistActiveStepSnapshot();
		      pushHistory();
		      syncInspector();
		      renderLayers();
		      refreshLivePreview();
		      scheduleTacticalOverlayRefresh();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		      return true;
		    };

		    // UI: mini barra “Convertir a…” (muy ligera) para cambiar rápidamente el tipo
		    // sin tapar el lienzo. Se oculta sola o al tocar fuera.
		    const smartInkUi = {
		      bar: null,
		      picker: null,
		      hideTimer: null,
		      src: null,
		      activeObj: null,
		      currentKind: '',
		    };
		    const clearSmartInkUiTimer = () => {
		      if (!smartInkUi.hideTimer) return;
		      try { window.clearTimeout(smartInkUi.hideTimer); } catch (e) { /* ignore */ }
		      smartInkUi.hideTimer = null;
		    };
		    const hideSmartInkBar = () => {
		      clearSmartInkUiTimer();
		      if (smartInkUi.bar) smartInkUi.bar.hidden = true;
		    };
		    const hideSmartInkPicker = () => {
		      if (smartInkUi.picker) smartInkUi.picker.hidden = true;
		    };
		    const hideSmartInkAll = () => {
		      hideSmartInkBar();
		      hideSmartInkPicker();
		      smartInkUi.src = null;
		      smartInkUi.activeObj = null;
		      smartInkUi.currentKind = '';
		    };
		    const ensureSmartInkBar = () => {
		      if (smartInkUi.bar) return smartInkUi.bar;
		      if (!stage) return null;
		      const el = document.createElement('div');
		      el.className = 'tpad-smart-ink-bar';
		      el.hidden = true;
		      el.style.position = 'absolute';
		      el.style.zIndex = '140';
		      el.style.display = 'flex';
		      el.style.gap = '6px';
		      el.style.padding = '6px';
		      el.style.borderRadius = '999px';
		      el.style.border = '1px solid rgba(148,163,184,0.22)';
		      el.style.background = 'rgba(2,6,23,0.62)';
		      el.style.backdropFilter = 'blur(10px)';
		      el.style.boxShadow = '0 18px 34px rgba(2,6,23,0.35)';
		      el.style.pointerEvents = 'auto';
		      el.style.transform = 'translate(-18%, -112%)';
		      el.addEventListener('pointerdown', (ev) => {
		        ev.stopPropagation();
		      }, true);
		      stage.appendChild(el);
		      smartInkUi.bar = el;
		      return el;
		    };
		    const ensureSmartInkPicker = () => {
		      if (smartInkUi.picker) return smartInkUi.picker;
		      if (!stage) return null;
		      const wrap = document.createElement('div');
		      wrap.className = 'tpad-smart-ink-picker';
		      wrap.hidden = true;
		      wrap.style.position = 'absolute';
		      wrap.style.right = '12px';
		      wrap.style.bottom = '12px';
		      wrap.style.zIndex = '150';
		      wrap.style.width = '260px';
		      wrap.style.maxWidth = '80vw';
		      wrap.style.maxHeight = '44vh';
		      wrap.style.display = 'flex';
		      wrap.style.flexDirection = 'column';
		      wrap.style.gap = '10px';
		      wrap.style.padding = '12px';
		      wrap.style.borderRadius = '16px';
		      wrap.style.border = '1px solid rgba(148,163,184,0.22)';
		      wrap.style.background = 'rgba(2,6,23,0.78)';
		      wrap.style.backdropFilter = 'blur(12px)';
		      wrap.style.boxShadow = '0 24px 44px rgba(2,6,23,0.45)';
		      wrap.style.pointerEvents = 'auto';
		      wrap.addEventListener('pointerdown', (ev) => ev.stopPropagation(), true);

		      const header = document.createElement('div');
		      header.style.display = 'flex';
		      header.style.alignItems = 'center';
		      header.style.justifyContent = 'space-between';
		      header.style.gap = '10px';
		      const title = document.createElement('div');
		      title.textContent = 'Convertir a…';
		      title.style.fontWeight = '800';
		      title.style.fontSize = '12px';
		      title.style.letterSpacing = '0.08em';
		      title.style.textTransform = 'uppercase';
		      title.style.color = 'rgba(226,232,240,0.92)';
		      const close = document.createElement('button');
		      close.type = 'button';
		      close.textContent = '✕';
		      close.title = 'Cerrar';
		      close.style.border = '1px solid rgba(148,163,184,0.22)';
		      close.style.background = 'rgba(15,23,42,0.55)';
		      close.style.color = 'rgba(226,232,240,0.92)';
		      close.style.borderRadius = '10px';
		      close.style.padding = '6px 10px';
		      close.style.fontWeight = '900';
		      close.addEventListener('click', () => hideSmartInkPicker());
		      header.appendChild(title);
		      header.appendChild(close);

		      const search = document.createElement('input');
		      search.type = 'search';
		      search.placeholder = 'Buscar recurso…';
		      search.autocomplete = 'off';
		      search.style.width = '100%';
		      search.style.padding = '10px 12px';
		      search.style.borderRadius = '12px';
		      search.style.border = '1px solid rgba(148,163,184,0.22)';
		      search.style.background = 'rgba(15,23,42,0.42)';
		      search.style.color = 'rgba(226,232,240,0.96)';
		      search.style.outline = 'none';

		      const list = document.createElement('div');
		      list.className = 'tpad-smart-ink-picker-list';
		      list.style.display = 'grid';
		      list.style.gridTemplateColumns = '1fr';
		      list.style.gap = '8px';
		      list.style.overflow = 'auto';
		      list.style.paddingRight = '2px';

		      wrap.appendChild(header);
		      wrap.appendChild(search);
		      wrap.appendChild(list);
		      stage.appendChild(wrap);
		      smartInkUi.picker = wrap;

		      wrap.__searchEl = search;
		      wrap.__listEl = list;
		      return wrap;
		    };
		    const worldPointToStageXY = (pt) => {
		      const fabric = window.fabric;
		      if (!fabric || !pt || !stage) return null;
		      const vpt = canvas?.viewportTransform || [1, 0, 0, 1, 0, 0];
		      let px = Number(pt.x) || 0;
		      let py = Number(pt.y) || 0;
		      try {
		        const p = fabric.util.transformPoint(new fabric.Point(px, py), vpt);
		        px = Number(p?.x) || px;
		        py = Number(p?.y) || py;
		      } catch (e) { /* ignore */ }
		      const stageRect = stage.getBoundingClientRect();
		      const canvasRect = (canvas?.upperCanvasEl || canvasEl)?.getBoundingClientRect?.();
		      if (!stageRect || !canvasRect) return null;
		      const x = (canvasRect.left - stageRect.left) + px;
		      const y = (canvasRect.top - stageRect.top) + py;
		      return { x, y, w: stageRect.width || 0, h: stageRect.height || 0 };
		    };
		    const smartBuildFromKind = (kindRaw, src) => {
		      const kind = safeText(kindRaw).trim();
		      if (!kind || !src) return null;
		      const stroke = safeText(src.stroke, '#22d3ee') || '#22d3ee';
		      const strokeWidth = clamp(Number(src.strokeWidth) || 4, 1, 26);
		      const bounds = src.bounds || boundsForPoints(src.points || []);
		      const center = { x: Number(bounds.cx) || 0, y: Number(bounds.cy) || 0 };
		      const start = src.start || (src.points && src.points[0]) || center;
		      const end = src.end || (src.points && src.points[src.points.length - 1]) || center;

		      if (kind === 'arrow' || kind === 'arrow_solid') return buildSmartArrowGroup(start, end, { stroke, strokeWidth });

		      if (kind === 'line' || kind === 'line_solid') {
		        const factory = simpleFactory('line_solid');
		        if (!factory) return null;
		        const obj = factory(center.x, center.y);
		        try {
		          const dx = (Number(end?.x) || 0) - (Number(start?.x) || 0);
		          const dy = (Number(end?.y) || 0) - (Number(start?.y) || 0);
		          const len = Math.hypot(dx, dy) || 0;
		          const ang = (Math.atan2(dy, dx) * 180) / Math.PI;
		          obj.set({ angle: ang });
		          const baseLen = 440;
		          const scale = clamp(len / baseLen, 0.15, 12);
		          obj.set({ scaleX: scale, scaleY: scale });
		        } catch (e) { /* ignore */ }
		        applySmartShapeStyle(obj, stroke, strokeWidth);
		        return obj;
		      }

		      const factory = simpleFactory(kind);
		      if (!factory) return null;
		      const obj = factory(center.x, center.y);
		      applySmartShapeStyle(obj, stroke, strokeWidth);

		      // Intenta adaptar el tamaño al gesto (si hay bounds razonables).
		      try {
		        const target = clamp(Math.max(60, Number(bounds.diag) || 0), 60, 260);
		        const rect = (typeof obj.getBoundingRect === 'function') ? obj.getBoundingRect(true, true) : null;
		        const base = rect ? Math.max(1, Math.max(Number(rect.width) || 1, Number(rect.height) || 1)) : Math.max(1, Math.max(Number(obj.width) || 1, Number(obj.height) || 1));
		        const s = clamp(target / base, 0.18, 12);
		        obj.set({ scaleX: (Number(obj.scaleX) || 1) * s, scaleY: (Number(obj.scaleY) || 1) * s });
		      } catch (e) { /* ignore */ }
		      return obj;
		    };
		    const replaceSmartActiveObject = (replacement) => {
		      if (!replacement || !smartInkUi.activeObj) return false;
		      if (isSimulating) return false;
		      let prevLoading = false;
		      try { prevLoading = !!canvas.__loading; } catch (e) { prevLoading = false; }
		      try {
		        canvas.__loading = true;
		        try { canvas.remove(smartInkUi.activeObj); } catch (e) { /* ignore */ }
		        normalizeEditableObject(replacement);
		        try { canvas.add(replacement); } catch (e) { /* ignore */ }
		      } finally {
		        try { canvas.__loading = prevLoading; } catch (e) { /* ignore */ }
		      }
		      smartInkUi.activeObj = replacement;
		      try { canvas.setActiveObject(replacement); } catch (e) { /* ignore */ }
		      try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
		      persistActiveStepSnapshot();
		      pushHistory();
		      syncInspector();
		      renderLayers();
		      refreshLivePreview();
		      scheduleTacticalOverlayRefresh();
		      schedulePlayerBankUpdate();
		      scheduleDraftSave('canvas');
		      return true;
		    };
		    const showSmartInkPicker = () => {
		      const picker = ensureSmartInkPicker();
		      if (!picker) return;
		      const listEl = picker.__listEl;
		      const searchEl = picker.__searchEl;
		      if (!listEl || !searchEl) return;
		      picker.hidden = false;
		      try { searchEl.focus(); } catch (e) { /* ignore */ }
		      const all = Object.entries(RESOURCE_LABELS || {})
		        .map(([kind, label]) => ({ kind, label: safeText(label, kind) }))
		        .filter((item) => !!safeText(item.kind));
		      const render = () => {
		        const q = safeText(searchEl.value).toLowerCase().trim();
		        const items = all
		          .filter((it) => {
		            if (!q) return true;
		            return safeText(it.kind).toLowerCase().includes(q) || safeText(it.label).toLowerCase().includes(q);
		          })
		          .slice(0, 60);
		        listEl.innerHTML = items.map((it) => {
		          const k = safeText(it.kind).replace(/"/g, '&quot;');
		          const l = safeText(it.label).replace(/</g, '&lt;').replace(/>/g, '&gt;');
		          return `<button type="button" class="tpad-smart-ink-item" data-kind="${k}" title="${l}" style="text-align:left;border:1px solid rgba(148,163,184,0.20);background:rgba(15,23,42,0.42);color:rgba(226,232,240,0.92);border-radius:12px;padding:10px 12px;font-weight:800;font-size:13px;">${l}</button>`;
		        }).join('');
		      };
		      render();
		      searchEl.oninput = render;
		      listEl.onclick = (ev) => {
		        const btn = ev.target.closest('button[data-kind]');
		        if (!btn) return;
		        const kind = safeText(btn.dataset.kind);
		        const replacement = smartBuildFromKind(kind, smartInkUi.src);
		        if (!replacement) {
		          setStatus('Ese recurso no se puede generar desde un trazo (todavía).', true);
		          return;
		        }
		        if (replaceSmartActiveObject(replacement)) {
		          hideSmartInkPicker();
		          setStatus('Recurso convertido.');
		        }
		      };
		    };
		    const showSmartInkBar = (anchorWorldPoint, options = []) => {
		      const bar = ensureSmartInkBar();
		      if (!bar) return;
		      const pos = worldPointToStageXY(anchorWorldPoint);
		      if (!pos) return;
		      clearSmartInkUiTimer();
		      hideSmartInkPicker();
		      const safeX = clamp((Number(pos.x) || 0), 16, Math.max(16, (Number(pos.w) || 0) - 16));
		      const safeY = clamp((Number(pos.y) || 0), 16, Math.max(16, (Number(pos.h) || 0) - 16));
		      bar.style.left = `${safeX}px`;
		      bar.style.top = `${safeY}px`;
		      bar.hidden = false;
		      bar.innerHTML = options.map((opt) => {
		        const key = safeText(opt.key);
		        const label = safeText(opt.label, key);
		        const icon = safeText(opt.icon, label);
		        const active = !!opt.active;
		        const cls = active ? 'tpad-smart-ink-btn is-active' : 'tpad-smart-ink-btn';
		        const border = active ? 'rgba(244,180,0,0.65)' : 'rgba(148,163,184,0.22)';
		        const bg = active ? 'rgba(244,180,0,0.12)' : 'rgba(15,23,42,0.20)';
		        return `<button type="button" class="${cls}" data-smart="${key}" title="${label}" style="appearance:none;cursor:pointer;border:1px solid ${border};background:${bg};color:rgba(226,232,240,0.95);border-radius:999px;padding:6px 10px;font-weight:950;letter-spacing:0.02em;font-size:12px;line-height:1;">${icon}</button>`;
		      }).join('');
		      bar.onclick = (ev) => {
		        const btn = ev.target.closest('button[data-smart]');
		        if (!btn) return;
		        const key = safeText(btn.dataset.smart);
		        if (key === '__picker__') {
		          hideSmartInkBar();
		          showSmartInkPicker();
		          return;
		        }
		        if (!key) return;
		        if (key === smartInkUi.currentKind) {
		          hideSmartInkBar();
		          return;
		        }
		        const replacement = smartBuildFromKind(key, smartInkUi.src);
		        if (!replacement) {
		          setStatus('No se puede convertir a ese recurso desde el trazo.', true);
		          return;
		        }
		        if (replaceSmartActiveObject(replacement)) {
		          smartInkUi.currentKind = key;
		          hideSmartInkBar();
		          setStatus('Convertido.');
		        }
		      };
		      // Auto-oculta rápido (no debe estorbar).
		      smartInkUi.hideTimer = window.setTimeout(() => hideSmartInkBar(), 1600);
		    };
		    // Oculta al tocar fuera.
		    stage?.addEventListener('pointerdown', (ev) => {
		      const t = ev.target;
		      if (smartInkUi.bar && !smartInkUi.bar.hidden && t && smartInkUi.bar.contains(t)) return;
		      if (smartInkUi.picker && !smartInkUi.picker.hidden && t && smartInkUi.picker.contains(t)) return;
		      hideSmartInkAll();
		    }, true);

		    canvas.on('path:created', (event) => {
		      if (canvas.__loading) return;
		      if (!freeDrawMode) return;
		      if (smartInkMode === 'off') return;
		      const pathObj = event?.path;
		      if (!pathObj) return;
		      if (isSimulating) return;

		      const points = extractCanvasPointsFromPath(pathObj);
		      const stroke = safeText(pathObj.stroke, colorInput?.value || '#22d3ee') || '#22d3ee';
		      const strokeWidth = clamp(Number(pathObj.strokeWidth) || Number(strokeWidthInput?.value) || 4, 1, 26);
		      if (points.length < 2) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		        return;
		      }

		      const src = {
		        points,
		        bounds: boundsForPoints(points),
		        start: points[0],
		        end: points[points.length - 1],
		        stroke,
		        strokeWidth,
		      };

		      if (smartInkMode === 'shapes') {
		        const match = classifySmartShape(points);
		        if (!match) {
		          persistActiveStepSnapshot();
		          pushHistory();
		          renderLayers();
		          return;
		        }
		        let replacement = null;
		        let currentKind = safeText(match.kind);
		        if (match.kind === 'line_solid') {
		          const factory = simpleFactory('line_solid');
		          if (factory) {
		            const a = match.start;
		            const b = match.end;
		            src.start = a;
		            src.end = b;
		            const cx = ((Number(a?.x) || 0) + (Number(b?.x) || 0)) / 2;
		            const cy = ((Number(a?.y) || 0) + (Number(b?.y) || 0)) / 2;
		            replacement = factory(cx, cy);
		            try {
		              const dx = (Number(b?.x) || 0) - (Number(a?.x) || 0);
		              const dy = (Number(b?.y) || 0) - (Number(a?.y) || 0);
		              const l = Math.hypot(dx, dy) || 0;
		              const ang = (Math.atan2(dy, dx) * 180) / Math.PI;
		              replacement.set({ angle: ang });
		              const baseLen = 440;
		              const scale = clamp(l / baseLen, 0.15, 8);
		              replacement.set({ scaleX: scale, scaleY: scale });
		            } catch (e) { /* ignore */ }
		            applySmartShapeStyle(replacement, stroke, strokeWidth);
		          }
		        } else {
		          const b = match.bounds || boundsForPoints(points);
		          src.bounds = b;
		          const factory = simpleFactory(match.kind);
		          if (factory) replacement = factory(b.cx, b.cy);
		          if (replacement) {
		            applySmartShapeStyle(replacement, stroke, strokeWidth);
		            try {
		              const w = Math.max(10, Number(b.w) || 0);
		              const h = Math.max(10, Number(b.h) || 0);
		              if (replacement.type === 'circle') {
		                const d0 = Math.max(1, (Number(replacement.radius) || 46) * 2);
		                const s = clamp(Math.min(w, h) / d0, 0.18, 12);
		                replacement.set({ scaleX: s, scaleY: s });
		              } else if (replacement.type === 'rect') {
		                const w0 = Math.max(1, Number(replacement.width) || 96);
		                const h0 = Math.max(1, Number(replacement.height) || 96);
		                const sx = clamp(w / w0, 0.15, 12);
		                const sy = clamp(h / h0, 0.15, 12);
		                replacement.set({ scaleX: sx, scaleY: sy });
		              }
		            } catch (e) { /* ignore */ }
		          }
		        }
		        if (!replacement || !replacePathWithSmartObject(pathObj, replacement)) {
		          persistActiveStepSnapshot();
		          pushHistory();
		          renderLayers();
		          return;
		        }
		        smartInkUi.src = src;
		        smartInkUi.activeObj = replacement;
		        smartInkUi.currentKind = currentKind;
		        const anchor = (match.kind === 'line_solid') ? src.end : { x: src.bounds.maxX, y: src.bounds.minY };
		        showSmartInkBar(anchor, [
		          { key: currentKind, label: 'Mantener', icon: '✓', active: true },
		          { key: 'arrow', label: 'Flecha', icon: '↗︎' },
		          { key: 'line_solid', label: 'Línea', icon: '—' },
		          { key: 'cone', label: 'Cono', icon: '▲' },
		          { key: '__picker__', label: 'Más…', icon: '…' },
		        ]);
		        setStatus('Forma convertida.');
		        return;
		      }

		      // smartInkMode === 'arrow'
		      const start = points[0];
		      // Soporta “flecha con punta” dibujada en un único trazo: usa la punta (punto más lejano).
		      let farIdx = points.length - 1;
		      let farDist = -1;
		      for (let i = 1; i < points.length; i += 1) {
		        const ddx = (Number(points[i]?.x) || 0) - (Number(start?.x) || 0);
		        const ddy = (Number(points[i]?.y) || 0) - (Number(start?.y) || 0);
		        const d = Math.hypot(ddx, ddy) || 0;
		        if (d > farDist) { farDist = d; farIdx = i; }
		      }
		      const minIdxForTip = Math.floor(points.length * 0.55);
		      const tipIdx = (farIdx >= minIdxForTip) ? farIdx : (points.length - 1);
		      const end = points[tipIdx];
		      const mainPoints = points.slice(0, tipIdx + 1);
		      const len = Math.hypot((Number(end?.x) || 0) - (Number(start?.x) || 0), (Number(end?.y) || 0) - (Number(start?.y) || 0)) || 0;
		      if (len < 70) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		        return;
		      }
		      const wobble = maxDistanceToLine(mainPoints, start, end);
		      if (wobble / Math.max(1, len) > 0.14) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		        return;
		      }
		      const arrow = buildSmartArrowGroup(start, end, { stroke, strokeWidth });
		      if (!arrow || !replacePathWithSmartObject(pathObj, arrow)) {
		        persistActiveStepSnapshot();
		        pushHistory();
		        renderLayers();
		        return;
		      }
		      src.start = start;
		      src.end = end;
		      smartInkUi.src = src;
		      smartInkUi.activeObj = arrow;
		      smartInkUi.currentKind = 'arrow';
		      showSmartInkBar(end, [
		        { key: 'arrow', label: 'Mantener flecha', icon: '✓', active: true },
		        { key: 'line_solid', label: 'Línea', icon: '—' },
		        { key: 'shape_circle', label: 'Círculo', icon: '○' },
		        { key: 'cone', label: 'Cono', icon: '▲' },
		        { key: '__picker__', label: 'Más…', icon: '…' },
		      ]);
		      setStatus('Flecha convertida.');
		    });
				    canvas.on('object:moving', (event) => {
			      const target = event?.target;
			      const rawEvent = event?.e;
			      if (!target || !rawEvent) return;
			      if (target?.data?.base) return;
			      const targetCenter = target.getCenterPoint();
			      const isMod = !!(rawEvent.ctrlKey || rawEvent.metaKey);
			      const useMagnets = isMod || (isSimulating && simulationMagnets);
			      const snapGrid = shouldSnapToGridForEvent(rawEvent);
			      const allowTacticalSnap = !!(tacticalSnapEnabled && !rawEvent.shiftKey && !useMagnets);
			      const tokenLike = safeText(target?.data?.kind) === 'token'
			        || (target?.type === 'activeSelection' && typeof target.getObjects === 'function' && (target.getObjects() || []).some((obj) => safeText(obj?.data?.kind) === 'token'));
			      let next = { x: targetCenter.x, y: targetCenter.y };
			      let didMove = false;
			      let snapInfo = null;
			      if (useMagnets) {
			        const snapped = snapPointToCenters(next, target, 10);
			        snapInfo = snapped;
			        if (snapped.snappedX || snapped.snappedY) {
			          next = { x: snapped.x, y: snapped.y };
			          didMove = true;
			        }
			      } else if (snapGrid) {
			        next = snapPointToGrid(next);
			        didMove = true;
			      }
			      if (allowTacticalSnap && tokenLike) {
			        const snapped = snapPointToLanesSectors(next);
			        if (snapped.snappedX || snapped.snappedY) {
			          next = { x: snapped.x, y: snapped.y };
			          didMove = true;
			        }
			      }

			      if (isSimulating) {
			        if (simulationGuides) updateSimGuides(snapInfo);
			        else hideSimGuides();
			        const collided = resolveSoftCollision(target, next);
			        if (Math.abs((collided.x || 0) - (next.x || 0)) > 0.5 || Math.abs((collided.y || 0) - (next.y || 0)) > 0.5) {
			          next = collided;
			          didMove = true;
			        }
			        if (!didMove) return;
			        target.setPositionByOrigin(new fabric.Point(next.x, next.y), 'center', 'center');
			        target.setCoords();
			        return;
			      }

			      if (!didMove) return;
			      target.setPositionByOrigin(new fabric.Point(next.x, next.y), 'center', 'center');
			      target.setCoords();
			      if (tokenLike) scheduleTacticalOverlayRefresh();
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

		    const dataUrlToBlob = async (dataUrl) => {
		      const url = safeText(dataUrl);
		      if (!url.startsWith('data:')) return null;
		      try {
		        const resp = await fetch(url);
		        if (!resp.ok) return null;
		        return await resp.blob();
		      } catch (error) {
		        return null;
		      }
		    };

	    const fileSafeSlug = (value) => safeText(value || '')
	      .toLowerCase()
	      .replace(/[^a-z0-9]+/g, '-')
	      .replace(/^-+|-+$/g, '')
	      .slice(0, 60) || 'tarea';

	    const htmlEscape = (value) => safeText(value || '')
	      .replace(/&/g, '&amp;')
	      .replace(/</g, '&lt;')
	      .replace(/>/g, '&gt;')
	      .replace(/"/g, '&quot;')
	      .replace(/'/g, '&#39;');

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
		      const payload = (() => {
		        const base = serializeState();
		        try {
		          if (Array.isArray(simulationSavedSteps) && simulationSavedSteps.length) {
		            base.simulation = { v: 1, updated_at: simulationSavedUpdatedAt ? new Date(simulationSavedUpdatedAt).toISOString() : '', steps: simulationSavedSteps };
		          }
		        } catch (error) { /* ignore */ }
		        return base;
		      })();
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
	    const syncSimRouteUiForSelection = () => {
	      if (!isSimulating) return;
	      const step = activeSimulationStep();
	      if (!step) return;
	      ensureStepRoutes(step);
	      const target = activeRouteTarget();
	      if (!target) {
	        if (simRouteSplineInput) simRouteSplineInput.checked = false;
	        return;
	      }
	      const route = step.routes?.[target.uid];
	      if (simRouteSplineInput) simRouteSplineInput.checked = !!route?.spline;
	    };
	    canvas.on('selection:created', syncSimRouteUiForSelection);
	    canvas.on('selection:updated', syncSimRouteUiForSelection);
	    canvas.on('selection:cleared', syncSimRouteUiForSelection);
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
		      } else if (tacticalSnapEnabled && e && !e.shiftKey) {
		        const kind = safeText(pendingKind).toLowerCase();
		        const shouldSnap = kind.includes('player') || kind.includes('goalkeeper') || kind.includes('token');
		        if (shouldSnap) {
		          const snapped = snapPointToLanesSectors(base);
		          if (snapped.snappedX || snapped.snappedY) pointer = { x: snapped.x, y: snapped.y };
		        }
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
	      if (isSimulating && simulationPlaying) {
	        stopSimulationPlayback();
	        setStatus('Reproducción detenida (interacción).');
	      }
	      if (isSimulating && simRouteAddMode && e && !pendingFactory) {
	        const targetObj = event?.target;
	        // Si el usuario pulsa sobre una ficha, dejamos que seleccione/mueva; si pulsa campo/fondo, añadimos waypoint.
	        const clickedTokenLike = targetObj && !isBackgroundShape(targetObj) && !targetObj?.data?.base;
	        if (!clickedTokenLike) {
	          const target = activeRouteTarget();
	          if (!target) {
	            setStatus('Selecciona una ficha (o el balón) para añadir waypoints.', true);
	            return;
	          }
	          const raw = canvas.getPointer(e);
	          const pointer = { x: Number(raw?.x) || 0, y: Number(raw?.y) || 0 };
	          const ok = addRoutePointAt(target.uid, pointer);
	          if (ok) setStatus('Waypoint añadido.');
	          return;
	        }
	      }
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
    scenarioTemplate3Btn?.addEventListener('click', async () => {
      if (isSimulating) {
        setStatus('Sal del simulador para usar plantillas de escenarios.', true);
        return;
      }
      const willReplace = !!timeline.length;
      if (willReplace) {
        const ok = window.confirm('Esto reemplazará los escenarios actuales. ¿Continuar?');
        if (!ok) return;
      }
      persistActiveStepSnapshot();
      const { w, h } = worldSize();
      const base = serializeCanvasOnly();
      const mk = (title) => ({
        title,
        duration: 3,
        canvas_state: sanitizeLoadedState(base),
        canvas_width: Math.round(w || 0),
        canvas_height: Math.round(h || 0),
      });
      timeline = [mk('Inicio'), mk('Desarrollo'), mk('Final')];
      activeStepIndex = 0;
      try { await loadCanvasSnapshotAsync(timeline[0].canvas_state, { sourceWidth: timeline[0].canvas_width, sourceHeight: timeline[0].canvas_height }); } catch (e) { /* ignore */ }
      renderTimeline();
      syncStepInputs();
      pushHistory();
      refreshLivePreview();
      setStatus('Plantilla de 3 escenarios creada.');
    });
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
	        active.scaleX = clampScale(Number(scaleXInput.value) / 100, maxScaleForObject(active));
	      }, 'Longitud actualizada.');
	    });
	    scaleYInput?.addEventListener('input', () => {
	      applyToActiveFlexibleObject((active) => {
	        active.scaleY = clampScale(Number(scaleYInput.value) / 100, maxScaleForObject(active));
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
		      if (freeDrawMode && canvas && canvas.freeDrawingBrush) {
		        try { canvas.freeDrawingBrush.color = colorInput.value || '#22d3ee'; } catch (e) { /* ignore */ }
		      }
		    });
		    tokenBaseColorInput?.addEventListener('input', () => {
		      applyToActiveFlexibleObject((active) => {
		        if (!isTokenGroup(active)) return;
		        applyTokenPalette(active, { base: tokenBaseColorInput.value });
		      }, 'Base actualizada.');
		    });
		    tokenStripeColorInput?.addEventListener('input', () => {
		      applyToActiveFlexibleObject((active) => {
		        if (!isTokenGroup(active)) return;
		        applyTokenPalette(active, { stripe: tokenStripeColorInput.value });
		      }, 'Franjas actualizadas.');
		    });
		    strokeWidthInput?.addEventListener('input', () => {
		      applyToActiveFlexibleObject((active) => {
		        applyObjectStrokeWidth(active, Number(strokeWidthInput.value) || 3);
		      }, 'Grosor actualizado.');
	      if (freeDrawMode && canvas && canvas.freeDrawingBrush) {
	        try { canvas.freeDrawingBrush.width = clamp(Number(strokeWidthInput.value) || 4, 1, 26); } catch (e) { /* ignore */ }
	      }
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
			      const tokenStyle = safeText(button.dataset.tokenStyle);
			      if (tokenStyle) {
			        setActiveTokenStyle(tokenStyle);
			        return;
			      }
			      const tokenPattern = safeText(button.dataset.tokenPattern);
			      if (tokenPattern) {
			        applyToActiveFlexibleObject((active) => {
			          if (!isTokenGroup(active)) return;
			          applyTokenPalette(active, { pattern: tokenPattern });
			        }, `Patrón: ${normalizeTokenPattern(tokenPattern) === 'solid' ? 'sólido' : 'rayas'}.`);
			        return;
			      }
			      const scalePreset = Number(button.dataset.scalePreset);
			      if (!Number.isNaN(scalePreset) && button.dataset.scalePreset !== undefined) {
			        const active = activeInspectableObject();
			        const next = clampScale(scalePreset / 100, maxScaleForObject(active));
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
	      const setFreeDrawMode = (enabled) => {
	        freeDrawMode = !!enabled;
	        try {
	          canvas.isDrawingMode = freeDrawMode;
	          canvas.selection = !freeDrawMode;
	        } catch (e) { /* ignore */ }
	        try {
	          Array.from(document.querySelectorAll('button[data-action="draw_free"]')).forEach((btn) => {
	            btn.classList.toggle('is-active', freeDrawMode && !pencilProMode && smartInkMode === 'off');
	          });
	        } catch (e) { /* ignore */ }
	        if (freeDrawMode) {
	          try { clearPendingPlacement(); } catch (e) { /* ignore */ }
	          pendingFactory = null;
	          backgroundPickMode = false;
	          try { canvas.discardActiveObject(); } catch (e) { /* ignore */ }
	          try { canvas.requestRenderAll(); } catch (e) { /* ignore */ }
	          try {
	            const brush = canvas.freeDrawingBrush || new fabric.PencilBrush(canvas);
	            brush.color = colorInput?.value || '#22d3ee';
	            brush.width = clamp(Number(strokeWidthInput?.value) || 4, 1, 26);
	            try { brush.decimate = penOnlyDraw ? 4 : 2; } catch (e) { /* ignore */ }
	            canvas.freeDrawingBrush = brush;
	          } catch (e) { /* ignore */ }
	          // Muestra un mini-inspector para poder cambiar color/grosor sin seleccionar nada.
	          try {
	            if (selectionToolbar && selectionSummary) {
	              selectionToolbar.hidden = false;
	              selectionToolbar.querySelectorAll('input,button').forEach((node) => { node.disabled = false; });
	              selectionSummary.textContent = 'Dibujo libre: ajusta color y grosor.';
	              if (scaleXInput) scaleXInput.disabled = true;
	              if (scaleYInput) scaleYInput.disabled = true;
	              if (rotationInput) rotationInput.disabled = true;
	              if (scalePresetsRow) scalePresetsRow.hidden = true;
	              if (tokenSizePresetsRow) tokenSizePresetsRow.hidden = true;
	              if (tokenMetaRow) tokenMetaRow.hidden = true;
	            }
	          } catch (e) { /* ignore */ }
	          if (strokeWidthRow) strokeWidthRow.hidden = false;
	          if (strokePresetsRow) strokePresetsRow.hidden = false;
	          setStatus(penOnlyDraw ? 'Pencil Pro activo: dibuja solo con Apple Pencil (el dedo sirve para pan/zoom).' : 'Dibujo libre activado. Dibuja sobre el campo (pulsa “Dibujo libre” o Esc para salir).');
	        } else {
	          try { syncInspector(); } catch (e) { /* ignore */ }
	          setStatus('Dibujo libre desactivado.');
	        }
	      };
	      if (action === 'select') {
	        animPathMode = false;
	        setSmartInkMode('off');
	        pencilProMode = false;
	        penOnlyDraw = false;
	        setFreeDrawMode(false);
	        pendingFactory = null;
	        Array.from(document.querySelectorAll('.resource-section [data-add]') || []).forEach((item) => item.classList.remove('is-active'));
	        Array.from(playerBank?.querySelectorAll('button') || []).forEach((item) => item.classList.remove('is-active'));
	        setStatus('Modo selección activo.');
	        return true;
	      }
	      if (action === 'draw_free') {
	        // Modo clásico: permite dedo/ratón.
	        animPathMode = false;
	        setSmartInkMode('off');
	        pencilProMode = false;
	        penOnlyDraw = false;
	        setFreeDrawMode(!freeDrawMode);
	        return true;
	      }
	      if (action === 'smart_arrow') {
	        animPathMode = false;
	        pencilProMode = false;
	        penOnlyDraw = false;
	        const willEnable = smartInkMode !== 'arrow';
	        setSmartInkMode(willEnable ? 'arrow' : 'off');
	        setFreeDrawMode(willEnable ? true : freeDrawMode);
	        setStatus(willEnable ? 'Auto flecha activa: dibuja una flecha y se convertirá en flecha limpia.' : 'Auto flecha desactivada.');
	        return true;
	      }
	      if (action === 'smart_shapes') {
	        animPathMode = false;
	        pencilProMode = false;
	        penOnlyDraw = false;
	        const willEnable = smartInkMode !== 'shapes';
	        setSmartInkMode(willEnable ? 'shapes' : 'off');
	        setFreeDrawMode(willEnable ? true : freeDrawMode);
	        setStatus(willEnable ? 'Auto formas activa: dibuja círculo/rectángulo/línea y se convertirá en forma limpia.' : 'Auto formas desactivada.');
	        return true;
	      }
	      if (action === 'pencil_pro') {
	        // Pencil Pro: dibuja solo con pen (palm rejection por bloqueo touch).
	        animPathMode = false;
	        setSmartInkMode('off');
	        pencilProMode = !pencilProMode;
	        penOnlyDraw = pencilProMode;
	        try {
	          Array.from(document.querySelectorAll('button[data-action="pencil_pro"]')).forEach((btn) => {
	            btn.classList.toggle('is-active', pencilProMode);
	            try { btn.setAttribute('aria-pressed', pencilProMode ? 'true' : 'false'); } catch (e) { /* ignore */ }
	          });
	        } catch (e) { /* ignore */ }
	        setFreeDrawMode(pencilProMode);
	        return true;
	      }
	      if (action === 'draw_anim_path') {
	        // Ruta animada: captura stroke y lo convierte en Timeline Pro para la ficha seleccionada.
	        setFreeDrawMode(false);
	        setSmartInkMode('off');
	        pencilProMode = true;
	        penOnlyDraw = true;
	        animPathMode = !animPathMode;
	        try {
	          Array.from(document.querySelectorAll('button[data-action="pencil_pro"]')).forEach((btn) => {
	            btn.classList.toggle('is-active', pencilProMode);
	            try { btn.setAttribute('aria-pressed', pencilProMode ? 'true' : 'false'); } catch (e) { /* ignore */ }
	          });
	        } catch (e) { /* ignore */ }
	        try {
	          Array.from(document.querySelectorAll('button[data-action="draw_anim_path"]')).forEach((btn) => {
	            btn.classList.toggle('is-active', animPathMode);
	            try { btn.setAttribute('aria-pressed', animPathMode ? 'true' : 'false'); } catch (e) { /* ignore */ }
	          });
	        } catch (e) { /* ignore */ }
	        setStatus(animPathMode ? 'Ruta animada activa: selecciona una ficha y dibuja su recorrido con el Apple Pencil.' : 'Ruta animada desactivada.');
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
					      if (freeDrawMode) handleCanvasAction('draw_free');
					      if (add.startsWith('image_url:')) {
				        const url = add.slice('image_url:'.length);
				        const label = 'una imagen';
				        Array.from(toolStrip.querySelectorAll('[data-add]')).forEach((item) => item.classList.remove('is-active'));
				        button.classList.add('is-active');
				        activateFactory((left, top) => buildUrlAssetObject(url, left, top), label, add);
				        return;
				      }
					      if (add.startsWith('pdf_asset:')) {
				        const assetId = add.split(':')[1] || '';
				        const label = 'un recurso gráfico';
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
	
				    // Clicks en otros paneles de recursos (líneas, figuras, etc.).
				    // Históricamente solo se atendía `#task-basic-tools`; esto hacía que "líneas" fuese poco usable.
				    const resourceSection = document.querySelector('.resource-section');
				    resourceSection?.addEventListener('click', (event) => {
				      const button = event.target.closest('.resource-panel button');
				      if (!button) return;
				      if (button.closest('#task-basic-tools')) return;
				      if (button.closest('#task-command-bar') || button.closest('#task-command-menu')) return;
				      if (button.closest('#task-selection-toolbar')) return;
				      const action = safeText(button.dataset.action);
				      const add = safeText(button.dataset.add);
				      if (action && handleCanvasAction(action)) return;
					      if (!add) return;
					      if (freeDrawMode) handleCanvasAction('draw_free');
					      Array.from(document.querySelectorAll('.resource-section [data-add]') || []).forEach((item) => item.classList.remove('is-active'));
					      button.classList.add('is-active');
					      if (add.startsWith('image_url:')) {
					        const url = add.slice('image_url:'.length);
					        activateFactory((left, top) => buildUrlAssetObject(url, left, top), 'una imagen', add);
					        return;
					      }
					      if (add.startsWith('pdf_asset:')) {
					        const assetId = add.split(':')[1] || '';
					        activateFactory((left, top) => buildPdfAssetObject(assetId, left, top), 'un recurso gráfico', add);
					        return;
					      }
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
					      if (freeDrawMode) handleCanvasAction('draw_free');
					      if (add.startsWith('image_url:')) {
				        const url = add.slice('image_url:'.length);
				        const label = 'una imagen';
				        Array.from(libraryPane.querySelectorAll('button[data-add]')).forEach((item) => item.classList.remove('is-active'));
				        button.classList.add('is-active');
				        activateFactory((left, top) => buildUrlAssetObject(url, left, top), label, add);
				        return;
				      }
					      if (add.startsWith('pdf_asset:')) {
				        const assetId = add.split(':')[1] || '';
				        const label = 'un recurso gráfico';
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
						        if (freeDrawMode) {
						          handleCanvasAction('draw_free');
						          event.preventDefault();
						          return;
						        }
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

		    const buildPitchSvgMarkupForShare = () => {
		      try {
		        const clone = svgSurface.cloneNode(true);
		        clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');
		        const { w, h } = worldSize();
		        const outW = Math.max(320, Math.round(w || canvas.getWidth() || 0));
		        const outH = Math.max(180, Math.round(h || canvas.getHeight() || 0));
		        clone.setAttribute('width', String(outW));
		        clone.setAttribute('height', String(outH));
		        return new XMLSerializer().serializeToString(clone);
		      } catch (error) {
		        try {
		          return new XMLSerializer().serializeToString(svgSurface);
		        } catch (err) {
		          return '';
		        }
		      }

		      if (isToken) {
		        const style = normalizeTokenStyle(active?.data?.token_style);
		        if (tokenStyleActions) {
		          Array.from(tokenStyleActions.querySelectorAll('button[data-token-style]') || []).forEach((btn) => {
		            const btnStyle = normalizeTokenStyle(btn.dataset.tokenStyle);
		            btn.classList.toggle('is-active', btnStyle === style);
		            try { btn.setAttribute('aria-pressed', btnStyle === style ? 'true' : 'false'); } catch (e) { /* ignore */ }
		          });
		        }
		        const hasStripes = tokenHasStripeRoles(active);
		        if (tokenColorGrid) tokenColorGrid.hidden = !hasStripes || style === 'photo';
		        if (tokenPatternActions) tokenPatternActions.hidden = !hasStripes || style === 'photo';
		        if (tokenBaseColorInput) {
		          try { tokenBaseColorInput.value = parseColorToHex(active?.data?.token_base_color, '#ffffff'); } catch (e) { /* ignore */ }
		        }
		        if (tokenStripeColorInput) {
		          try { tokenStripeColorInput.value = parseColorToHex(active?.data?.token_stripe_color, objectPreferredColor(active)); } catch (e) { /* ignore */ }
		        }
		        if (tokenPatternActions) {
		          const pattern = normalizeTokenPattern(active?.data?.token_pattern);
		          Array.from(tokenPatternActions.querySelectorAll('button[data-token-pattern]') || []).forEach((btn) => {
		            const btnPattern = normalizeTokenPattern(btn.dataset.tokenPattern);
		            btn.classList.toggle('is-active', btnPattern === pattern);
		            try { btn.setAttribute('aria-pressed', btnPattern === pattern ? 'true' : 'false'); } catch (e) { /* ignore */ }
		          });
		        }
		      } else {
		        if (tokenStyleActions) tokenStyleActions.hidden = true;
		        if (tokenColorGrid) tokenColorGrid.hidden = true;
		        if (tokenPatternActions) tokenPatternActions.hidden = true;
		      }
		    };

		    const exportSimulationCurrentStepPng = async () => {
		      if (!isSimulating) return;
		      if (exportInFlight) return;
		      exportInFlight = true;
		      stopSimulationPlayback();
		      try {
		        const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
		        const stepTitle = safeText(simulationSteps[simulationActiveIndex]?.title, `paso_${simulationActiveIndex + 1}`);
		        setStatus('Generando PNG del paso…');
		        const dataUrl = await buildPreviewData({ maxWidth: 1600, mime: 'image/png', quality: 0.92 });
		        const blob = await dataUrlToBlob(dataUrl);
		        if (!blob) {
		          setStatus('No se pudo generar el PNG del paso.', true);
		          return;
		        }
		        downloadBlob(blob, `${title}_sim_${String(simulationActiveIndex + 1).padStart(2, '0')}_${fileSafeSlug(stepTitle)}.png`);
		        setStatus('PNG del paso descargado.');
		      } finally {
		        exportInFlight = false;
		      }
		    };

		    const exportSimulationAllStepsPng = async () => {
		      if (!isSimulating) return;
		      if (exportInFlight) return;
		      exportInFlight = true;
		      stopSimulationPlayback();
		      const startIndex = clamp(simulationActiveIndex, 0, Math.max(0, simulationSteps.length - 1));
		      try {
		        if (!simulationSteps.length) {
		          setStatus('No hay pasos para exportar.', true);
		          return;
		        }
		        const title = fileSafeSlug(form.querySelector('[name="draw_task_title"]')?.value);
		        for (let i = 0; i < simulationSteps.length; i += 1) {
		          const step = simulationSteps[i];
		          setStatus(`Exportando PNG ${i + 1}/${simulationSteps.length}…`);
		          await selectSimulationStep(i);
		          const stepTitle = safeText(step?.title, `paso_${i + 1}`);
		          const dataUrl = await buildPreviewData({ maxWidth: 1600, mime: 'image/png', quality: 0.92 });
		          const blob = await dataUrlToBlob(dataUrl);
		          if (blob) {
		            downloadBlob(blob, `${title}_sim_${String(i + 1).padStart(2, '0')}_${fileSafeSlug(stepTitle)}.png`);
		          }
		          await sleep(240);
		        }
		        setStatus('Exportación de pasos completada.');
		      } finally {
		        try { await selectSimulationStep(startIndex); } catch (error) { /* ignore */ }
		        exportInFlight = false;
		      }
		    };

		    const exportSimulationPresentationPack = async () => {
		      if (!isSimulating) return;
		      if (exportInFlight) return;
		      exportInFlight = true;
		      stopSimulationPlayback();
		      const startIndex = clamp(simulationActiveIndex, 0, Math.max(0, simulationSteps.length - 1));
		      try {
		        if (!simulationSteps.length) {
		          setStatus('No hay pasos para exportar.', true);
		          return;
		        }
		        const maxSlides = 20;
		        const count = Math.min(maxSlides, simulationSteps.length);
		        if (simulationSteps.length > maxSlides) {
		          setStatus(`Pack: exportando ${count}/${simulationSteps.length} pasos (límite ${maxSlides}).`);
		        } else {
		          setStatus(`Pack: exportando ${count} pasos…`);
		        }
		        const title = safeText(form.querySelector('[name="draw_task_title"]')?.value, 'Presentación');
		        const slides = [];
		        for (let i = 0; i < count; i += 1) {
		          const step = simulationSteps[i];
		          setStatus(`Pack: render ${i + 1}/${count}…`);
		          await selectSimulationStep(i);
		          const img = await buildPreviewData({ maxWidth: 1600, mime: 'image/jpeg', quality: 0.88 });
		          slides.push({
		            i,
		            title: safeText(step?.title, `Paso ${i + 1}`),
		            duration: clamp(Number(step?.duration) || 3, 1, 20),
		            img: safeText(img),
		          });
		          await sleep(120);
		        }
		        const payload = {
		          v: 1,
		          title: safeText(title),
		          created_at: new Date().toISOString(),
		          slides,
		        };
		        const safeJson = htmlEscape(JSON.stringify(payload));
		        const htmlDoc = `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${htmlEscape(safeText(title, 'Presentación'))}</title>
  <style>
    :root{color-scheme:dark;--bg:#020617;--panel:#0f172a;--muted:rgba(226,232,240,.78);--accent:#22c55e}
    body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;background:radial-gradient(circle at 30% 20%, rgba(34,197,94,.12), var(--bg) 55%);color:#f8fafc}
    header{padding:16px 18px;border-bottom:1px solid rgba(255,255,255,.10);background:rgba(2,6,23,.72);backdrop-filter:blur(10px);position:sticky;top:0}
    header h1{margin:0;font-size:18px;letter-spacing:.02em}
    header .meta{margin-top:4px;color:var(--muted);font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:.14em}
    main{display:grid;grid-template-columns:1fr;gap:12px;padding:14px}
    .stage{border:1px solid rgba(255,255,255,.12);border-radius:16px;overflow:hidden;background:rgba(15,23,42,.68);box-shadow:rgba(0,0,0,.45) 0 18px 50px}
    .stage img{display:block;width:100%;height:auto;background:#000}
    .bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between;padding:10px 12px;border-top:1px solid rgba(255,255,255,.10);background:rgba(2,6,23,.55)}
    .bar strong{font-size:14px}
    .bar span{color:var(--muted);font-weight:800;font-size:12px}
    .controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    button{appearance:none;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:#f8fafc;border-radius:12px;padding:8px 10px;font-weight:900;cursor:pointer}
    button.primary{background:rgba(34,197,94,.18);border-color:rgba(34,197,94,.35)}
    input[type=range]{width:min(620px, 62vw)}
  </style>
</head>
<body>
  <header>
    <h1>${htmlEscape(safeText(title, 'Presentación'))}</h1>
    <div class="meta">2J · Tactical Board · Pack</div>
  </header>
  <main>
    <div class="stage">
      <img id="slideImg" alt="slide" />
      <div class="bar">
        <div>
          <strong id="slideTitle">—</strong><br />
          <span id="slideMeta">—</span>
        </div>
        <div class="controls">
          <button id="prevBtn">Anterior</button>
          <button id="playBtn" class="primary">Play</button>
          <button id="nextBtn">Siguiente</button>
          <input id="scrub" type="range" min="0" max="0" value="0" />
        </div>
      </div>
    </div>
  </main>
  <script id="pack-data" type="application/json">${safeJson}</script>
  <script>
  (function(){
    const dataEl=document.getElementById('pack-data');
    let pack=null;
    try{pack=JSON.parse(dataEl.textContent||'{}')}catch(e){pack=null}
    const slides=Array.isArray(pack&&pack.slides)?pack.slides:[];
    let idx=0;
    let timer=null;
    const img=document.getElementById('slideImg');
    const title=document.getElementById('slideTitle');
    const meta=document.getElementById('slideMeta');
    const scrub=document.getElementById('scrub');
    const playBtn=document.getElementById('playBtn');
    const prevBtn=document.getElementById('prevBtn');
    const nextBtn=document.getElementById('nextBtn');
    scrub.max=String(Math.max(0, slides.length-1));
    const render=()=>{
      const s=slides[idx]||null;
      if(!s){title.textContent='(sin slides)';meta.textContent='';img.removeAttribute('src');return}
      img.src=s.img||'';
      title.textContent=s.title||('Paso '+(idx+1));
      meta.textContent=(idx+1)+' / '+slides.length+' · '+(s.duration||3)+'s';
      scrub.value=String(idx);
    };
    const stop=()=>{ if(timer){clearTimeout(timer);timer=null} playBtn.textContent='Play'; };
    const play=()=>{ stop(); playBtn.textContent='Stop'; const tick=()=>{ const s=slides[idx]||{}; const ms=Math.max(800, (Number(s.duration)||3)*1000); timer=setTimeout(()=>{ idx=(idx+1)%slides.length; render(); if(timer){tick()} }, ms); }; timer=true; tick(); };
    playBtn.addEventListener('click',()=>{ if(timer){ stop(); } else { play(); }});
    prevBtn.addEventListener('click',()=>{ stop(); idx=Math.max(0, idx-1); render(); });
    nextBtn.addEventListener('click',()=>{ stop(); idx=Math.min(slides.length-1, idx+1); render(); });
    scrub.addEventListener('input',()=>{ stop(); idx=Math.max(0, Math.min(slides.length-1, Number(scrub.value)||0)); render(); });
    render();
  })();
  </script>
</body>
</html>`;
		        const blob = new Blob([htmlDoc], { type: 'text/html;charset=utf-8' });
		        downloadBlob(blob, `${fileSafeSlug(title)}_pack.html`);
		        setStatus('Pack descargado.');
		      } finally {
		        try { await selectSimulationStep(startIndex); } catch (error) { /* ignore */ }
		        exportInFlight = false;
		      }
		    };

			    const shareSimulationLink = async () => {
		      if (!isSimulating) return;
		      const shareUrl = safeText(simShareUrlInput?.value);
		      if (!shareUrl) {
		        setStatus('Compartir simulación no disponible.', true);
		        return;
		      }
		      if (!simulationSteps.length) {
		        setStatus('No hay pasos de simulación para compartir.', true);
		        return;
		      }
		      if (exportInFlight) return;
		      exportInFlight = true;
			      stopSimulationPlayback();
			      try {
			        const password = window.prompt('Contraseña (opcional, deja vacío si no quieres):', '') || '';
			        const taskId = parseIntSafe(form?.dataset?.taskId) || 0;
			        const scopeKey = safeText(form?.dataset?.scopeKey);
			        const taskKind = scopeKey === 'task_studio' ? 'task_studio' : 'session';
			        const payload = {
			          title: safeText(form.querySelector('[name="draw_task_title"]')?.value, 'Simulación'),
			          pitch_svg: buildPitchSvgMarkupForShare(),
			          steps: simulationSteps,
			          task_kind: taskId ? taskKind : '',
			          task_id: taskId || 0,
			        };
		        const jsonPayload = JSON.stringify(payload);
		        if (jsonPayload.length > 1_200_000) {
		          setStatus('La simulación es demasiado grande para compartir (reduce pasos).', true);
		          return;
		        }
		        const body = new URLSearchParams();
		        body.set('payload', jsonPayload);
		        body.set('valid_days', '30');
		        if (password) body.set('password', password);
		        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
		        const resp = await fetch(shareUrl, {
		          method: 'POST',
		          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
		          credentials: 'same-origin',
		          body: body.toString(),
		        });
		        const data = await resp.json().catch(() => ({}));
		        if (!resp.ok || !data?.url) throw new Error(data?.error || 'No se pudo crear el enlace.');
		        try { await navigator.clipboard?.writeText(data.url); } catch (e) { /* ignore */ }
		        window.prompt('Enlace público (copiado si el navegador lo permite):', data.url);
		        setStatus('Enlace de simulación generado.');
		      } catch (error) {
		        setStatus(error?.message || 'Error al crear enlace.', true);
		      } finally {
		        exportInFlight = false;
			      }
			    };

			    const convertSimulationToScenarios = async () => {
			      if (!isSimulating) return;
			      if (!simulationSteps.length) {
			        setStatus('No hay pasos en el simulador.', true);
			        return;
			      }
			      if (simulationPlaying) stopSimulationPlayback();
			      const willReplace = !!timeline.length;
			      if (willReplace) {
			        const ok = window.confirm('Ya hay escenarios (multipizarra). ¿Quieres reemplazarlos por los pasos del simulador?');
			        if (!ok) return;
			      }
			      let stepsCopy = [];
			      try { stepsCopy = JSON.parse(JSON.stringify(simulationSteps)); } catch (error) { stepsCopy = simulationSteps.slice(); }
			      // Sal del simulador primero, para que el cambio persista (exitSimulation restaura el baseline).
			      exitSimulation();
			      await sleep(50);
			      // Convertimos (máx 16) para no saturar la multipizarra/PDF.
			      const limit = Math.min(16, stepsCopy.length);
			      const nextTimeline = stepsCopy.slice(0, limit).map((step, index) => ({
			        title: safeText(step?.title, `Escenario ${index + 1}`),
			        duration: clamp(Number(step?.duration) || 3, 1, 20),
			        canvas_state: sanitizeLoadedState(step?.canvas_state),
			        canvas_width: parseIntSafe(step?.canvas_width) || 0,
			        canvas_height: parseIntSafe(step?.canvas_height) || 0,
			      }));
			      timeline = nextTimeline;
			      activeStepIndex = timeline.length ? 0 : -1;
			      try {
			        if (timeline.length) {
			          await loadCanvasSnapshotAsync(timeline[0].canvas_state, { sourceWidth: timeline[0].canvas_width, sourceHeight: timeline[0].canvas_height });
			        }
			      } catch (error) { /* ignore */ }
			      renderTimeline();
			      try { pushHistory(); } catch (error) { /* ignore */ }
			      try { refreshLivePreview(); } catch (error) { /* ignore */ }
			      setStatus('Multipizarra creada desde el simulador.');
			    };

		    simExportStepBtn?.addEventListener('click', (event) => {
		      event.preventDefault();
		      void exportSimulationCurrentStepPng();
		    });
			    simExportAllBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      void exportSimulationAllStepsPng();
			    });
			    simPackBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      void exportSimulationPresentationPack();
			    });
			    simClipSaveBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      if (!isSimulating) return;
			      if (!Array.isArray(simulationSteps) || !simulationSteps.length) {
			        setStatus('No hay pasos para guardar. Captura al menos 1 paso.', true);
			        return;
			      }
			      const defaultName = safeText(form.querySelector('[name="draw_task_title"]')?.value, 'Clip');
			      const name = safeText(window.prompt('Nombre del clip', defaultName));
			      if (!name) return;
			      const folder = safeText(window.prompt('Carpeta (opcional)', '')).slice(0, 80);
			      const tagsRaw = safeText(window.prompt('Tags (coma separada)', '')).slice(0, 200);
			      const tags = tagsRaw.split(',').map((t) => safeText(t).trim()).filter(Boolean).slice(0, 12);
			      let steps = [];
			      try { steps = JSON.parse(JSON.stringify(simulationSteps)); } catch (e) { steps = simulationSteps.slice(); }
			      const dest = safeText(simClipDestSelect?.value, 'local');
				      if (dest !== 'local') {
				        const scope = dest === 'system' ? 'system' : 'team';
				        (async () => {
			          try {
			            const res = await savePlaybookClip({ scope, name: name.slice(0, 160), folder, tags, steps });
			            if (res?.canceled) return;
			            await fetchPlaybookClips({ force: true, silent: true });
			            renderClipsLibrary();
			            setStatus(`Clip guardado en Playbook (${scope === 'system' ? 'sistema' : 'equipo'}).`);
			          } catch (e) {
			            setStatus(e?.message || 'No se pudo guardar en Playbook.', true);
			          }
			        })();
				        return;
				      }
				      let pro = null;
				      try {
				        const hasTracks = simulationProTracks && typeof simulationProTracks === 'object' && Object.keys(simulationProTracks).length >= 1;
				        if (hasTracks || simulationProEnabled) {
				          pro = {
				            v: 1,
				            enabled: !!simulationProEnabled,
				            loop: !!simulationProLoop,
				            updated_at: new Date().toISOString(),
				            tracks: simulationProTracks || {},
				          };
				        }
				      } catch (e) { /* ignore */ }
				      const clip = { name: name.slice(0, 120), created_at: new Date().toISOString(), steps, pro };
				      const prev = readClipsLibrary();
				      const next = [clip, ...prev].slice(0, 40);
				      writeClipsLibrary(next);
			      renderClipsLibrary();
			      setStatus('Clip guardado (local).');
			    });
				    simClipImportBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      if (!isSimulating) return;
				      if (!simClipFileInput) return;
				      try { simClipFileInput.value = ''; } catch (e) {}
				      simClipFileInput.click();
				    });
				    simVideoImportBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      if (!isSimulating) return;
				      if (!simVideoFileInput) return;
				      try { simVideoFileInput.value = ''; } catch (e) {}
				      simVideoFileInput.click();
				    });
				    simClipFileInput?.addEventListener('change', async () => {
				      if (!isSimulating) return;
				      const file = simClipFileInput.files?.[0];
				      if (!file) return;
			      let text = '';
			      try { text = await file.text(); } catch (e) { text = ''; }
			      if (!text) {
			        setStatus('No se pudo leer el archivo.', true);
			        return;
			      }
			      let parsed = null;
			      try { parsed = JSON.parse(text); } catch (e) { parsed = null; }
			      const steps = Array.isArray(parsed?.steps) ? parsed.steps : [];
			      if (!steps.length) {
			        setStatus('El JSON no contiene pasos.', true);
			        return;
			      }
				      const name = safeText(parsed?.name, file.name.replace(/\\.json$/i, '')).slice(0, 120) || 'Clip importado';
				      const pro = (parsed?.pro && typeof parsed.pro === 'object') ? parsed.pro : null;
				      const clip = { name, created_at: new Date().toISOString(), steps, pro };
				      const prev = readClipsLibrary();
				      writeClipsLibrary([clip, ...prev].slice(0, 40));
				      renderClipsLibrary();
				      setStatus('Clip importado (local).');
				    });
				    simVideoFileInput?.addEventListener('change', async () => {
				      if (!isSimulating) return;
				      const file = simVideoFileInput.files?.[0];
				      if (!file) return;
				      const actionUrl = safeText(form?.dataset?.videoImportUrl);
				      if (!actionUrl) {
				        setStatus('No se encontró la ruta de importación de vídeo.', true);
				        return;
				      }
				      const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
				      if (!csrf) {
				        setStatus('Falta CSRF. Recarga la página.', true);
				        return;
				      }
				      setStatus('Procesando vídeo… (puede tardar 10–30s)');

				      const setNamedValue = (name, value) => {
				        const key = safeText(name);
				        if (!key) return;
				        const el = form.querySelector(`[name="${CSS.escape(key)}"]`);
				        if (!el) return;
				        el.value = value == null ? '' : String(value);
				      };
				      const setRichHtmlValue = (plainName, htmlValue) => {
				        const key = safeText(plainName);
				        if (!key) return;
				        const wrapper = form.querySelector(`[data-rich-editor][data-rich-name="${CSS.escape(key)}"]`);
				        if (!wrapper) return;
				        const htmlName = safeText(wrapper.dataset.richHtmlName);
				        const area = wrapper.querySelector('[data-rich-area]');
				        const plainField = form.querySelector(`[name="${CSS.escape(key)}"]`);
				        const htmlField = htmlName ? form.querySelector(`[name="${CSS.escape(htmlName)}"]`) : null;
				        if (!area || !plainField || !htmlField) return;
				        const rawHtml = String(htmlValue || '').trim();
				        htmlField.value = rawHtml;
				        // innerText para campo plano (sin estilos).
				        try {
				          const tmp = document.createElement('div');
				          tmp.innerHTML = rawHtml;
				          plainField.value = safeText(tmp.innerText || tmp.textContent || '');
				        } catch (e) {
				          plainField.value = safeText(rawHtml.replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
				        }
				        area.innerHTML = rawHtml || '';
				      };

				      try {
				        const fd = new FormData();
				        fd.append('video', file);
				        fd.append('name', safeText(file.name).replace(/\.[a-z0-9]+$/i, '').slice(0, 120));
				        const resp = await fetch(actionUrl, {
				          method: 'POST',
				          credentials: 'same-origin',
				          headers: { 'X-CSRFToken': csrf },
				          body: fd,
				        });
				        const data = await resp.json().catch(() => ({}));
				        if (!resp.ok || !data?.ok) {
				          setStatus(safeText(data?.error, 'No se pudo importar el vídeo.'), true);
				          return;
				        }
				        const clipData = data?.clip && typeof data.clip === 'object' ? data.clip : null;
				        const steps = Array.isArray(clipData?.steps) ? clipData.steps : [];
				        if (!clipData || !steps.length) {
				          setStatus('El vídeo no generó pasos.', true);
				          return;
				        }
				        const clip = {
				          name: safeText(clipData?.name, safeText(file.name).replace(/\.[a-z0-9]+$/i, '')).slice(0, 120) || 'Clip importado',
				          created_at: safeText(clipData?.created_at) || new Date().toISOString(),
				          steps,
				          pro: (clipData?.pro && typeof clipData.pro === 'object') ? clipData.pro : null,
				        };

				        // Guardar en librería local.
				        const prev = readClipsLibrary();
				        writeClipsLibrary([clip, ...prev].slice(0, 40));
				        renderClipsLibrary();

				        // Cargar inmediatamente.
				        if (simulationPlaying) stopSimulationPlayback();
				        try { simulationSavedSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSavedSteps = steps.slice(); }
				        simulationSavedUpdatedAt = Date.now();
				        try { simulationSteps = JSON.parse(JSON.stringify(steps)); } catch (e) { simulationSteps = steps.slice(); }
				        // Aplica Pro (tracks) si vienen en el clip.
				        try {
				          simulationProTracks = {};
				          simulationProEnabled = false;
				          simulationProLoop = true;
				          simulationProTimeMs = 0;
				          simulationProUpdatedAt = Date.now();
				          simulationProCaches = new Map();
				          const pro = clip.pro && typeof clip.pro === 'object' ? clip.pro : null;
				          if (pro) {
				            simulationProEnabled = pro.enabled !== false;
				            simulationProLoop = pro.loop !== false;
				            const tracks = pro.tracks && typeof pro.tracks === 'object' ? pro.tracks : {};
				            const safeTracks = {};
				            Object.entries(tracks).slice(0, 240).forEach(([uid, list]) => {
				              if (!uid) return;
				              if (!Array.isArray(list)) return;
				              const cleaned = list
				                .map((kf) => {
				                  const t_ms = clamp(Number(kf?.t_ms) || 0, 0, 3_600_000);
				                  const props = kf?.props && typeof kf.props === 'object' ? kf.props : null;
				                  if (!props) return null;
				                  return {
				                    t_ms,
				                    easing: normalizeEasing(kf?.easing),
				                    props: {
				                      left: Number(props.left) || 0,
				                      top: Number(props.top) || 0,
				                      angle: Number(props.angle) || 0,
				                      scaleX: clampScale(Number(props.scaleX) || 1),
				                      scaleY: clampScale(Number(props.scaleY) || 1),
				                      opacity: props.opacity == null ? 1 : Number(props.opacity),
				                    },
				                  };
				                })
				                .filter(Boolean)
				                .sort((a, b) => (a.t_ms - b.t_ms))
				                .slice(0, 240);
				              if (cleaned.length) safeTracks[uid] = cleaned;
				            });
				            simulationProTracks = safeTracks;
				          }
				          persistSimulationProToStorage();
				        } catch (e) { /* ignore */ }
				        simulationActiveIndex = clamp(0, 0, Math.max(0, simulationSteps.length - 1));
				        renderSimulationSteps();
				        void selectSimulationStep(simulationActiveIndex);
				        try {
				          if (simulationProEnabled) {
				            renderSimulationAtTimeMs(0);
				            syncSimProUi();
				          }
				        } catch (e) { /* ignore */ }
				        syncSimUi();

				        // Aplicar sugerencias a la ficha si vienen.
				        const suggested = data?.suggested && typeof data.suggested === 'object' ? data.suggested : null;
				        if (suggested) {
				          if (suggested.title) setNamedValue('draw_task_title', suggested.title);
				          if (suggested.objective) setNamedValue('draw_task_objective', suggested.objective);
				          if (suggested.player_count) setNamedValue('draw_task_player_count', suggested.player_count);
				          if (suggested.dimensions) setNamedValue('draw_task_dimensions', suggested.dimensions);
				          if (suggested.minutes) setNamedValue('draw_task_minutes', suggested.minutes);
				          if (suggested.description_html) setRichHtmlValue('draw_task_description', suggested.description_html);
				          if (suggested.rules_html) setRichHtmlValue('draw_task_confrontation_rules', suggested.rules_html);
				          if (suggested.coaching_html) setRichHtmlValue('draw_task_coaching_points', suggested.coaching_html);
				          if (suggested.progression_html) setRichHtmlValue('draw_task_progression', suggested.progression_html);
				          try { syncRichEditorsNow(); } catch (e) { /* ignore */ }
				        }

				        setStatus('Vídeo importado: clip + ficha (si había texto).');
				      } catch (err) {
				        setStatus('No se pudo importar el vídeo.', true);
				      }
				    });
				    simShareBtn?.addEventListener('click', (event) => {
				      event.preventDefault();
				      void shareSimulationLink();
				    });
			    simToScenariosBtn?.addEventListener('click', (event) => {
			      event.preventDefault();
			      void convertSimulationToScenarios();
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
	    grassToggle?.addEventListener('click', () => {
	      pitchGrassStyle = pitchGrassStyle === 'realistic' ? 'classic' : 'realistic';
	      syncGrassUi();
	      try { applyPitchSurface(presetSelect.value || 'full_pitch', pitchOrientation, pitchGrassStyle); } catch (e) { /* ignore */ }
	      refreshLivePreview();
	      setStatus(`Césped: ${GRASS_STYLE_LABEL[pitchGrassStyle] || pitchGrassStyle}.`);
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
		      try { applyPitchSurface(baseline.preset, baseline.orientation, pitchGrassStyle); } catch (e) { /* ignore */ }
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
