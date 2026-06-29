(function () {
  const safeText = (value, fallback = '') => {
    if (value == null) return fallback;
    const text = String(value).trim();
    return text || fallback;
  };

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const PRESET_METRICS = {
    full_pitch: { width: 105, height: 68, mode: 'full' },
    half_pitch: { width: 52.5, height: 68, mode: 'half' },
    attacking_third: { width: 35, height: 68, mode: 'attacking_third' },
    middle_third: { width: 35, height: 68, mode: 'middle_third' },
    defensive_third: { width: 35, height: 68, mode: 'defensive_third' },
    seven_side: { width: 65, height: 45, mode: 'seven_side' },
    seven_side_single: { width: 65, height: 45, mode: 'seven_side_single' },
    futsal: { width: 40, height: 20, mode: 'futsal' },
    blank: { width: 105, height: 68, mode: 'blank' },
  };

  const GRASS_PRESETS = {
    classic: {
      outer: '#6b8d3f',
      frame: '#a6c15d',
      frameEdge: '#799946',
      base: '#96b758',
      stripeA: '#a7c564',
      stripeB: '#8ab04f',
      textureLight: 'rgba(255,255,255,0.028)',
      textureDark: 'rgba(32,66,24,0.06)',
      shadow: 'rgba(20,41,16,0.16)',
    },
    realistic: {
      outer: '#65883d',
      frame: '#9ab85a',
      frameEdge: '#6f9244',
      base: '#8daf52',
      stripeA: '#9fc062',
      stripeB: '#7ea648',
      textureLight: 'rgba(255,255,255,0.03)',
      textureDark: 'rgba(23,56,18,0.075)',
      shadow: 'rgba(18,36,15,0.17)',
    },
    pro: {
      outer: '#557d3c',
      frame: '#85aa56',
      frameEdge: '#628845',
      base: '#6f9b49',
      stripeA: '#80ab57',
      stripeB: '#5f8d3d',
      textureLight: 'rgba(255,255,255,0.026)',
      textureDark: 'rgba(15,42,19,0.085)',
      shadow: 'rgba(10,28,13,0.18)',
    },
    broadcast: {
      outer: '#346d3f',
      frame: '#62944f',
      frameEdge: '#44733f',
      base: '#2f814c',
      stripeA: '#388f56',
      stripeB: '#266f43',
      textureLight: 'rgba(255,255,255,0.024)',
      textureDark: 'rgba(8,32,17,0.09)',
      shadow: 'rgba(7,21,13,0.19)',
    },
    broadcast_premium: {
      outer: '#224f36',
      frame: '#3d7b4d',
      frameEdge: '#2e623e',
      base: '#165f3b',
      stripeA: '#2a7a4d',
      stripeB: '#104e31',
      textureLight: 'rgba(255,255,255,0.02)',
      textureDark: 'rgba(5,18,10,0.12)',
      shadow: 'rgba(5,14,9,0.22)',
    },
    natural: {
      outer: '#708c42',
      frame: '#a3bd62',
      frameEdge: '#7f9948',
      base: '#8fb158',
      stripeA: '#a4c168',
      stripeB: '#7ea34c',
      textureLight: 'rgba(255,255,255,0.028)',
      textureDark: 'rgba(29,58,18,0.066)',
      shadow: 'rgba(18,36,14,0.16)',
    },
    artificial: {
      outer: '#20825a',
      frame: '#31a26b',
      frameEdge: '#258555',
      base: '#27a066',
      stripeA: '#34b375',
      stripeB: '#1f8f5a',
      textureLight: 'rgba(255,255,255,0.028)',
      textureDark: 'rgba(5,44,25,0.09)',
      shadow: 'rgba(6,33,20,0.18)',
    },
    dry: {
      outer: '#6d8641',
      frame: '#94ae59',
      frameEdge: '#758f45',
      base: '#839f4f',
      stripeA: '#95af5c',
      stripeB: '#728f43',
      textureLight: 'rgba(255,255,255,0.028)',
      textureDark: 'rgba(45,58,21,0.068)',
      shadow: 'rgba(25,33,15,0.16)',
    },
    wet: {
      outer: '#184935',
      frame: '#2a704f',
      frameEdge: '#1c573d',
      base: '#215d45',
      stripeA: '#2d7356',
      stripeB: '#1a4e3b',
      textureLight: 'rgba(255,255,255,0.022)',
      textureDark: 'rgba(4,18,12,0.11)',
      shadow: 'rgba(3,12,9,0.2)',
    },
    uefa_b: {
      outer: '#285f3b',
      frame: '#4e8a54',
      frameEdge: '#366f43',
      base: '#3d7b49',
      stripeA: '#4e9158',
      stripeB: '#2f673d',
      textureLight: 'rgba(255,255,255,0.024)',
      textureDark: 'rgba(7,24,11,0.11)',
      shadow: 'rgba(5,16,8,0.21)',
    },
    coachboard: {
      outer: '#254128',
      frame: '#3f633f',
      frameEdge: '#2f4f31',
      base: '#315934',
      stripeA: '#3b6740',
      stripeB: '#294d2d',
      textureLight: 'rgba(255,255,255,0.024)',
      textureDark: 'rgba(6,18,8,0.12)',
      shadow: 'rgba(4,12,5,0.22)',
    },
    whiteboard: {
      outer: '#d8e0e6',
      frame: '#eef3f6',
      frameEdge: '#cbd6de',
      base: '#e8eef2',
      stripeA: '#eef4f7',
      stripeB: '#dfe8ee',
      textureLight: 'rgba(255,255,255,0.02)',
      textureDark: 'rgba(15,23,42,0.05)',
      shadow: 'rgba(15,23,42,0.12)',
    },
    blackboard: {
      outer: '#0b1320',
      frame: '#152132',
      frameEdge: '#0f1a28',
      base: '#101b29',
      stripeA: '#182536',
      stripeB: '#0d1724',
      textureLight: 'rgba(255,255,255,0.018)',
      textureDark: 'rgba(0,0,0,0.1)',
      shadow: 'rgba(0,0,0,0.26)',
    },
  };

  const buildRect = (x, y, width, height, radius, fill, extra = '') =>
    `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${radius}" ry="${radius}" fill="${fill}" ${extra}/>`;

  const buildLine = (x1, y1, x2, y2, stroke, strokeWidth, extra = '') =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${strokeWidth}" ${extra}/>`;

  const buildCircle = (cx, cy, r, stroke, strokeWidth, fill = 'none', extra = '') =>
    `<circle cx="${cx}" cy="${cy}" r="${r}" stroke="${stroke}" stroke-width="${strokeWidth}" fill="${fill}" ${extra}/>`;

  const buildArcPath = (x1, y1, x2, y2, rx, ry, sweep) =>
    `M ${x1} ${y1} A ${rx} ${ry} 0 0 ${sweep} ${x2} ${y2}`;

  const computePitchRect = (presetKey, sceneW, sceneH) => {
    const preset = PRESET_METRICS[presetKey] || PRESET_METRICS.full_pitch;
    const baseMarginX = preset.mode === 'futsal' ? 118 : 132;
    const baseMarginY = preset.mode === 'futsal' ? 84 : 66;
    const maxW = sceneW - (baseMarginX * 2);
    const maxH = sceneH - (baseMarginY * 2);
    const aspect = preset.width / preset.height;
    let pitchW = maxW;
    let pitchH = pitchW / aspect;
    if (pitchH > maxH) {
      pitchH = maxH;
      pitchW = pitchH * aspect;
    }
    if (preset.mode === 'futsal') pitchH = Math.min(pitchH, maxH * 0.88);
    return {
      x: (sceneW - pitchW) / 2,
      y: (sceneH - pitchH) / 2,
      w: pitchW,
      h: pitchH,
      metrics: preset,
    };
  };

  const buildDefs = (idPrefix, pitch, grass) => `
    <defs>
      <linearGradient id="${idPrefix}-backdrop" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${grass.outer}"/>
        <stop offset="100%" stop-color="${grass.frameEdge}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-frame" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${grass.frame}"/>
        <stop offset="100%" stop-color="${grass.frameEdge}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-frame-sheen" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.18)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
      </linearGradient>
      <clipPath id="${idPrefix}-pitch-clip">
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18"/>
      </clipPath>
      <pattern id="${idPrefix}-grass-noise" width="120" height="120" patternUnits="userSpaceOnUse">
        <path d="M 12 115 L 38 18 M 54 116 L 78 22 M 86 110 L 112 16" stroke="${grass.textureLight}" stroke-width="2" stroke-linecap="round"/>
        <path d="M 20 100 L 28 84 M 65 74 L 72 58 M 96 97 L 105 79 M 82 42 L 90 26" stroke="${grass.textureDark}" stroke-width="1.15" stroke-linecap="round"/>
      </pattern>
      <pattern id="${idPrefix}-goal-net" width="14" height="14" patternUnits="userSpaceOnUse">
        <path d="M 0 0 L 14 14 M 14 0 L 0 14" stroke="rgba(236,242,247,0.62)" stroke-width="0.9"/>
      </pattern>
      <linearGradient id="${idPrefix}-goal-post" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="100%" stop-color="#d8e0e8"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-goal-side" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#d8e0e8"/>
        <stop offset="100%" stop-color="#96a6b7"/>
      </linearGradient>
      <radialGradient id="${idPrefix}-pitch-light" cx="50%" cy="48%" r="66%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.05)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
      </radialGradient>
      <linearGradient id="${idPrefix}-pitch-sheen" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.015)"/>
        <stop offset="35%" stop-color="rgba(255,255,255,0)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.02)"/>
      </linearGradient>
    </defs>
  `;

  const buildBackdrop = (scene, pitch, grass) => {
    const frameInset = 18;
    return `
      <g id="surface-base">
        <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="url(#${pitch.idPrefix}-backdrop)"/>
        <rect x="${pitch.x - frameInset}" y="${pitch.y - frameInset}" width="${pitch.w + frameInset * 2}" height="${pitch.h + frameInset * 2}" rx="32" ry="32" fill="url(#${pitch.idPrefix}-frame)"/>
        <rect x="${pitch.x - frameInset}" y="${pitch.y - frameInset}" width="${pitch.w + frameInset * 2}" height="${pitch.h + frameInset * 2}" rx="32" ry="32" fill="url(#${pitch.idPrefix}-frame-sheen)" opacity="0.28"/>
        <rect x="${pitch.x - 10}" y="${pitch.y - 10}" width="${pitch.w + 20}" height="${pitch.h + 20}" rx="22" ry="22" fill="none" stroke="rgba(255,255,255,0.16)" stroke-width="1.2"/>
        <rect x="${pitch.x - 16}" y="${pitch.y - 16}" width="${pitch.w + 32}" height="${pitch.h + 32}" rx="26" ry="26" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
        <rect x="${pitch.x - 6}" y="${pitch.y + pitch.h + 6}" width="${pitch.w + 12}" height="10" rx="5" ry="5" fill="${grass.shadow}" opacity="0.24"/>
      </g>
    `;
  };

  const buildGrassLayer = (pitch, grass) => {
    const stripes = [];
    const stripeCount = 11;
    const stripeWidth = pitch.w / stripeCount;
    for (let i = 0; i < stripeCount; i += 1) {
      stripes.push(buildRect(
        pitch.x + (i * stripeWidth),
        pitch.y,
        stripeWidth + 1,
        pitch.h,
        0,
        i % 2 === 0 ? grass.stripeA : grass.stripeB,
        `opacity="${i % 2 === 0 ? '0.98' : '0.93'}"`
      ));
    }
    const mowLines = [];
    for (let i = 1; i < 9; i += 1) {
      const y = pitch.y + ((pitch.h / 9) * i);
      mowLines.push(buildLine(pitch.x + 10, y, pitch.x + pitch.w - 10, y, 'rgba(255,255,255,0.024)', 0.9));
    }
    return `
      <g clip-path="url(#${pitch.idPrefix}-pitch-clip)">
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="${grass.base}"/>
        ${stripes.join('')}
        ${mowLines.join('')}
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-grass-noise)"/>
        <ellipse cx="${pitch.x + pitch.w * 0.5}" cy="${pitch.y + pitch.h * 0.5}" rx="${pitch.w * 0.43}" ry="${pitch.h * 0.34}" fill="url(#${pitch.idPrefix}-pitch-light)"/>
        <path d="M ${pitch.x + pitch.w * 0.08} ${pitch.y + pitch.h * 0.94} L ${pitch.x + pitch.w * 0.3} ${pitch.y + pitch.h * 0.08} M ${pitch.x + pitch.w * 0.58} ${pitch.y + pitch.h * 0.98} L ${pitch.x + pitch.w * 0.75} ${pitch.y + pitch.h * 0.06}" stroke="rgba(255,255,255,0.028)" stroke-width="1.1" stroke-linecap="round"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-pitch-sheen)"/>
      </g>
    `;
  };

  const buildFocusZones = (pitch) => {
    const leftCx = pitch.x + (pitch.w * 0.16);
    const rightCx = pitch.x + (pitch.w * 0.84);
    const cy = pitch.y + (pitch.h * 0.5);
    const rx = pitch.w * 0.26;
    const ry = pitch.h * 0.34;
    return `
      <g opacity="0.18">
        <ellipse cx="${leftCx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="rgba(255,255,255,0.04)"/>
        <ellipse cx="${rightCx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="rgba(255,255,255,0.04)"/>
      </g>
    `;
  };

  const buildGoal = (side, pitch, lineWidth, idPrefix) => {
    const mouth = pitch.h * 0.172;
    const depth = Math.max(36, pitch.w * 0.056);
    const y = pitch.y + ((pitch.h - mouth) / 2);
    const post = Math.max(3.2, lineWidth * 0.95);
    const backInset = Math.max(6, post * 1.55);
    const shadowRx = depth * 0.98;
    const shadowRy = mouth * 0.47;
    if (side === 'left') {
      const front = pitch.x;
      const back = pitch.x - depth;
      return `
        <g class="goal-left">
          <ellipse cx="${front - (depth * 0.54)}" cy="${y + mouth / 2}" rx="${shadowRx}" ry="${shadowRy}" fill="rgba(9,18,28,0.12)"/>
          <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net)" opacity="0.96"/>
          <polygon points="${front},${y} ${front - post},${y + post * 0.45} ${front - post},${y + mouth + post * 0.45} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-post)" opacity="0.98"/>
          <polygon points="${front - post},${y + post * 0.45} ${back - post * 0.45},${y + backInset} ${back - post * 0.45},${y + mouth - backInset} ${front - post},${y + mouth + post * 0.45}" fill="url(#${idPrefix}-goal-side)" opacity="0.82"/>
          ${buildLine(front, y, front, y + mouth, '#ffffff', post)}
          ${buildLine(back, y + backInset, back, y + mouth - backInset, 'rgba(226,232,240,0.95)', post * 0.72)}
          ${buildLine(front, y, back, y + backInset, 'rgba(255,255,255,0.9)', post * 0.74)}
          ${buildLine(front, y + mouth, back, y + mouth - backInset, 'rgba(255,255,255,0.9)', post * 0.74)}
        </g>
      `;
    }
    const front = pitch.x + pitch.w;
    const back = pitch.x + pitch.w + depth;
    return `
      <g class="goal-right">
        <ellipse cx="${front + (depth * 0.54)}" cy="${y + mouth / 2}" rx="${shadowRx}" ry="${shadowRy}" fill="rgba(9,18,28,0.12)"/>
        <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net)" opacity="0.96"/>
        <polygon points="${front},${y} ${front + post},${y + post * 0.45} ${front + post},${y + mouth + post * 0.45} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-post)" opacity="0.98"/>
        <polygon points="${front + post},${y + post * 0.45} ${back + post * 0.45},${y + backInset} ${back + post * 0.45},${y + mouth - backInset} ${front + post},${y + mouth + post * 0.45}" fill="url(#${idPrefix}-goal-side)" opacity="0.82"/>
        ${buildLine(front, y, front, y + mouth, '#ffffff', post)}
        ${buildLine(back, y + backInset, back, y + mouth - backInset, 'rgba(226,232,240,0.95)', post * 0.72)}
        ${buildLine(front, y, back, y + backInset, 'rgba(255,255,255,0.9)', post * 0.74)}
        ${buildLine(front, y + mouth, back, y + mouth - backInset, 'rgba(255,255,255,0.9)', post * 0.74)}
      </g>
    `;
  };

  const buildPitchLines = (pitch, mode, stroke, strokeWidth, isTopLayer = false) => {
    const meterX = pitch.w / pitch.metrics.width;
    const meterY = pitch.h / pitch.metrics.height;
    const centerX = pitch.x + (pitch.w / 2);
    const centerY = pitch.y + (pitch.h / 2);
    const centerRadius = 9.15 * Math.min(meterX, meterY);
    const penaltyDepth = 16.5 * meterX;
    const goalAreaDepth = 5.5 * meterX;
    const penaltyWidth = 40.32 * meterY;
    const goalAreaWidth = 18.32 * meterY;
    const penaltyTop = centerY - (penaltyWidth / 2);
    const goalAreaTop = centerY - (goalAreaWidth / 2);
    const penaltySpotOffset = 11 * meterX;
    const arcRadius = 9.15 * Math.min(meterX, meterY);
    const spotRadius = clamp(strokeWidth * (isTopLayer ? 0.9 : 0.78), 2.3, 4.6);
    const cornerRadius = clamp(pitch.h * 0.032, 8, 18);

    const buildPenaltyArc = (spotX, targetX, sweep) => {
      const dx = Math.abs(targetX - spotX);
      const dy = Math.sqrt(Math.max(0, (arcRadius * arcRadius) - (dx * dx)));
      return `<path d="${buildArcPath(targetX, centerY - dy, targetX, centerY + dy, arcRadius, arcRadius, sweep)}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth}"/>`;
    };

    const buildFullSide = (left = true) => {
      const edgeX = left ? pitch.x : pitch.x + pitch.w;
      const sign = left ? 1 : -1;
      const penaltyX = edgeX + (sign * penaltyDepth);
      const spotX = edgeX + (sign * penaltySpotOffset);
      return `
        ${buildRect(left ? pitch.x : pitch.x + pitch.w - penaltyDepth, penaltyTop, penaltyDepth, penaltyWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(left ? pitch.x : pitch.x + pitch.w - goalAreaDepth, goalAreaTop, goalAreaDepth, goalAreaWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildCircle(spotX, centerY, spotRadius, 'none', 0, stroke)}
        ${buildPenaltyArc(spotX, penaltyX, left ? 1 : 0)}
      `;
    };

    if (mode === 'blank') return '';

    if (mode === 'futsal') {
      const areaDepth = 6 * meterX;
      const areaWidth = pitch.h * 0.54;
      const areaTop = pitch.y + ((pitch.h - areaWidth) / 2);
      return `
        ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildLine(centerX, pitch.y, centerX, pitch.y + pitch.h, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, pitch.h * 0.16, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, spotRadius, 'none', 0, stroke)}
        ${buildRect(pitch.x, areaTop, areaDepth, areaWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x + pitch.w - areaDepth, areaTop, areaDepth, areaWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildCircle(pitch.x + pitch.w * 0.16, centerY, spotRadius, 'none', 0, stroke)}
        ${buildCircle(pitch.x + pitch.w * 0.84, centerY, spotRadius, 'none', 0, stroke)}
      `;
    }

    if (mode === 'half') {
      const mx = pitch.w / 52.5;
      const my = pitch.h / 68;
      const penDepth = 16.5 * mx;
      const areaTop = pitch.y + ((pitch.h - (40.32 * my)) / 2);
      const goalTop = pitch.y + ((pitch.h - (18.32 * my)) / 2);
      const spotX = pitch.x + pitch.w - (11 * mx);
      const targetX = pitch.x + pitch.w - penDepth;
      const dx = Math.abs(targetX - spotX);
      const arcDy = Math.sqrt(Math.max(0, (arcRadius * arcRadius) - (dx * dx)));
      return `
        ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x + pitch.w - penDepth, areaTop, penDepth, 40.32 * my, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x + pitch.w - (5.5 * mx), goalTop, 5.5 * mx, 18.32 * my, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildCircle(spotX, centerY, spotRadius, 'none', 0, stroke)}
        <path d="${buildArcPath(targetX, centerY - arcDy, targetX, centerY + arcDy, arcRadius, arcRadius, 0)}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth}"/>
      `;
    }

    if (mode === 'attacking_third' || mode === 'defensive_third') {
      const leftSide = mode === 'defensive_third';
      const mx = pitch.w / 35;
      const my = pitch.h / 68;
      const penDepth = 16.5 * mx;
      const goalDepth = 5.5 * mx;
      const areaTop = pitch.y + ((pitch.h - (40.32 * my)) / 2);
      const goalTop = pitch.y + ((pitch.h - (18.32 * my)) / 2);
      const sideX = leftSide ? pitch.x : pitch.x + pitch.w;
      const spotX = sideX + (leftSide ? 11 * mx : -11 * mx);
      const targetX = leftSide ? pitch.x + penDepth : pitch.x + pitch.w - penDepth;
      const dx = Math.abs(targetX - spotX);
      const arcDy = Math.sqrt(Math.max(0, (arcRadius * arcRadius) - (dx * dx)));
      return `
        ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(leftSide ? pitch.x : pitch.x + pitch.w - penDepth, areaTop, penDepth, 40.32 * my, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(leftSide ? pitch.x : pitch.x + pitch.w - goalDepth, goalTop, goalDepth, 18.32 * my, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildCircle(spotX, centerY, spotRadius, 'none', 0, stroke)}
        <path d="${buildArcPath(targetX, centerY - arcDy, targetX, centerY + arcDy, arcRadius, arcRadius, leftSide ? 1 : 0)}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth}"/>
      `;
    }

    if (mode === 'middle_third') {
      return `
        ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildLine(centerX, pitch.y, centerX, pitch.y + pitch.h, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, centerRadius, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, spotRadius, 'none', 0, stroke)}
      `;
    }

    if (mode === 'seven_side' || mode === 'seven_side_single') {
      const mx = pitch.w / 65;
      const my = pitch.h / 45;
      const areaDepth = 13 * mx;
      const areaWidth = 26 * my;
      const areaTop = pitch.y + ((pitch.h - areaWidth) / 2);
      const smallDepth = 4.5 * mx;
      const smallWidth = 12 * my;
      const smallTop = pitch.y + ((pitch.h - smallWidth) / 2);
      return `
        ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildLine(centerX, pitch.y, centerX, pitch.y + pitch.h, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, pitch.h * 0.17, stroke, strokeWidth)}
        ${buildCircle(centerX, centerY, spotRadius, 'none', 0, stroke)}
        ${buildRect(pitch.x, areaTop, areaDepth, areaWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x + pitch.w - areaDepth, areaTop, areaDepth, areaWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x, smallTop, smallDepth, smallWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildRect(pitch.x + pitch.w - smallDepth, smallTop, smallDepth, smallWidth, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
        ${buildCircle(pitch.x + (9 * mx), centerY, spotRadius, 'none', 0, stroke)}
        ${buildCircle(pitch.x + pitch.w - (9 * mx), centerY, spotRadius, 'none', 0, stroke)}
      `;
    }

    return `
      ${buildRect(pitch.x, pitch.y, pitch.w, pitch.h, 0, 'none', `stroke="${stroke}" stroke-width="${strokeWidth}"`)}
      ${buildLine(centerX, pitch.y, centerX, pitch.y + pitch.h, stroke, strokeWidth)}
      ${buildCircle(centerX, centerY, centerRadius, stroke, strokeWidth)}
      ${buildCircle(centerX, centerY, spotRadius, 'none', 0, stroke)}
      ${buildFullSide(true)}
      ${buildFullSide(false)}
      <path d="M ${pitch.x} ${pitch.y + cornerRadius} A ${cornerRadius} ${cornerRadius} 0 0 1 ${pitch.x + cornerRadius} ${pitch.y}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth * 0.88}"/>
      <path d="M ${pitch.x + pitch.w - cornerRadius} ${pitch.y} A ${cornerRadius} ${cornerRadius} 0 0 1 ${pitch.x + pitch.w} ${pitch.y + cornerRadius}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth * 0.88}"/>
      <path d="M ${pitch.x} ${pitch.y + pitch.h - cornerRadius} A ${cornerRadius} ${cornerRadius} 0 0 0 ${pitch.x + cornerRadius} ${pitch.y + pitch.h}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth * 0.88}"/>
      <path d="M ${pitch.x + pitch.w - cornerRadius} ${pitch.y + pitch.h} A ${cornerRadius} ${cornerRadius} 0 0 0 ${pitch.x + pitch.w} ${pitch.y + pitch.h - cornerRadius}" fill="none" stroke="${stroke}" stroke-width="${strokeWidth * 0.88}"/>
    `;
  };

  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
    const preset = PRESET_METRICS[safeText(presetKey, 'full_pitch')] ? safeText(presetKey, 'full_pitch') : 'full_pitch';
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const normalizedGrass = safeText(grassStyleKey, 'classic').toLowerCase();
    const grass = GRASS_PRESETS[normalizedGrass] || GRASS_PRESETS.classic;
    const sceneLandscape = { sceneW: 1200, sceneH: 820 };
    const sceneW = orientation === 'portrait' ? sceneLandscape.sceneH : sceneLandscape.sceneW;
    const sceneH = orientation === 'portrait' ? sceneLandscape.sceneW : sceneLandscape.sceneH;
    const pitch = computePitchRect(preset, sceneLandscape.sceneW, sceneLandscape.sceneH);
    const idPrefix = `pitch25d-${preset}-${orientation}-${normalizedGrass}`.replace(/[^a-z0-9_-]/gi, '-');
    const lineStroke = normalizedGrass === 'whiteboard' ? 'rgba(15,23,42,0.88)' : '#fdfefe';
    const lineUnderStroke = normalizedGrass === 'whiteboard' ? 'rgba(255,255,255,0.42)' : 'rgba(9,18,28,0.11)';
    const lineWidth = clamp(pitch.h / 150, 2.7, 5.8);
    const leftGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'defensive_third']);
    const rightGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'half', 'attacking_third']);
    pitch.idPrefix = idPrefix;

    const sceneBody = `
      ${buildDefs(idPrefix, pitch, grass)}
      ${buildBackdrop(sceneLandscape, pitch, grass)}
      <g id="pitch">
        ${buildGrassLayer(pitch, grass)}
        ${buildFocusZones(pitch)}
        <rect x="${pitch.x + 5}" y="${pitch.y + 5}" width="${pitch.w - 10}" height="${pitch.h - 10}" rx="14" ry="14" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.1"/>
        ${buildPitchLines(pitch, pitch.metrics.mode, lineUnderStroke, lineWidth + 1.15)}
        ${leftGoalModes.has(pitch.metrics.mode) ? buildGoal('left', pitch, lineWidth + 0.55, idPrefix) : ''}
        ${rightGoalModes.has(pitch.metrics.mode) ? buildGoal('right', pitch, lineWidth + 0.55, idPrefix) : ''}
        ${buildPitchLines(pitch, pitch.metrics.mode, lineStroke, lineWidth, true)}
      </g>
    `;

    const pitchBoxLandscape = `${pitch.x} ${pitch.y} ${pitch.w} ${pitch.h}`;
    let pitchBox = pitchBoxLandscape;
    let content = sceneBody;
    if (orientation === 'portrait') {
      const rotatedX = sceneLandscape.sceneH - (pitch.y + pitch.h);
      const rotatedY = pitch.x;
      pitchBox = `${rotatedX} ${rotatedY} ${pitch.h} ${pitch.w}`;
      content = `<g transform="translate(${sceneLandscape.sceneH} 0) rotate(90)">${sceneBody}</g>`;
    }

    return `
      <svg xmlns="http://www.w3.org/2000/svg"
           viewBox="0 0 ${sceneW} ${sceneH}"
           preserveAspectRatio="xMidYMid meet"
           data-pitch-box="${pitchBox}">
        ${content}
      </svg>
    `.trim();
  };

  window.WebstatsPitch25D = {
    buildPitchSvg,
  };
}());
