(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const createSvgNode = (doc, tag, attrs) => {
    const node = doc.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  };

  const __grassTextureCache = new Map();
  const __buildGrassTextureDataUrl = (styleKey) => {
    const style = safeText(styleKey, 'classic').toLowerCase();
    const allowed = new Set(['realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'broadcast']);
    if (!allowed.has(style)) return '';
    if (__grassTextureCache.has(style)) return __grassTextureCache.get(style);
    try {
      if (typeof document === 'undefined') return '';
      if (style === 'uefa_b') {
        const fromWindow = (() => {
          try { return safeText(window.__WEBSTATS_GRASS_TILES && window.__WEBSTATS_GRASS_TILES.uefa_b); } catch (e) { return ''; }
        })();
        const dataUrl = fromWindow && fromWindow.startsWith('data:image/') ? fromWindow : '';
        const href = dataUrl || '/static/football/images/surfaces/grass_uefa_b_tile.png';
        __grassTextureCache.set(style, href);
        return href;
      }
      const size = 256;
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) return '';
      const baseByStyle = {
        realistic: '#4f7f3a',
        pro: '#2f6a3a',
        broadcast: '#155e3a',
        artificial: '#2fb46d',
        dry: '#6b8a3a',
        wet: '#1f5a46',
      };
      ctx.fillStyle = baseByStyle[style] || '#4f7f3a';
      ctx.fillRect(0, 0, size, size);

      // Subtle mowing bands.
      ctx.globalAlpha = style === 'broadcast' ? 0.10 : 0.08;
      ctx.fillStyle = '#ffffff';
      const band = style === 'broadcast' ? 36 : 44;
      for (let y = 0; y < size; y += band) {
        ctx.fillRect(0, y, size, band / 2);
      }
      ctx.globalAlpha = 1;

      // Texture speckles.
      ctx.globalAlpha = style === 'wet' ? 0.22 : 0.18;
      ctx.fillStyle = style === 'wet' ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.45)';
      for (let i = 0; i < 120; i += 1) {
        const x = Math.random() * size;
        const y = Math.random() * size;
        const r = 0.6 + Math.random() * 1.4;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;

      // Soft vignette.
      const grad = ctx.createRadialGradient(size / 2, size / 2, size / 4, size / 2, size / 2, size * 0.9);
      grad.addColorStop(0, 'rgba(255,255,255,0)');
      grad.addColorStop(1, style === 'wet' ? 'rgba(0,0,0,0.26)' : 'rgba(0,0,0,0.18)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, size, size);

      const dataUrl = canvas.toDataURL('image/png');
      __grassTextureCache.set(style, dataUrl);
      return dataUrl;
    } catch (error) {
      return '';
    }
  };

  const buildEmergencyPitchSvg = (orientationKey = 'landscape') => {
    const portrait = safeText(orientationKey, 'landscape') === 'portrait';
    const viewW = 1200;
    const viewH = 820;
    const pitchW = 900;
    const pitchH = 584;
    const x = (viewW - pitchW) / 2;
    const y = (viewH - pitchH) / 2;
    const cx = x + pitchW / 2;
    const cy = y + pitchH / 2;
    const goalW = pitchH * 0.172;
    const goalY = cy - goalW / 2;
    const goalDepth = 42;
    const line = '#fdfefe';
    const stripes = Array.from({ length: 12 }, (_, index) => {
      const width = pitchW / 12;
      return `<rect x="${x + index * width}" y="${y}" width="${width + 1}" height="${pitchH}" fill="${index % 2 === 0 ? '#a7c564' : '#8ab04f'}" opacity="0.96"/>`;
    }).join('');
    const grain = Array.from({ length: 7 }, (_, index) => {
      const yy = y + ((pitchH / 8) * (index + 1));
      return `<line x1="${x + 10}" y1="${yy}" x2="${x + pitchW - 10}" y2="${yy}" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>`;
    }).join('');
    const net = (left) => {
      const frontX = left ? x : x + pitchW;
      const backX = left ? x - goalDepth : x + pitchW + goalDepth;
      const points = left
        ? `${frontX},${goalY} ${backX},${goalY + 9} ${backX},${goalY + goalW - 9} ${frontX},${goalY + goalW}`
        : `${frontX},${goalY} ${backX},${goalY + 9} ${backX},${goalY + goalW - 9} ${frontX},${goalY + goalW}`;
      return `<ellipse cx="${left ? frontX - goalDepth * 0.54 : frontX + goalDepth * 0.54}" cy="${cy}" rx="${goalDepth * 0.9}" ry="${goalW * 0.42}" fill="rgba(9,18,28,0.12)"/><polygon points="${points}" fill="url(#fallback-net)" opacity="0.88"/><line x1="${frontX}" y1="${goalY}" x2="${backX}" y2="${goalY + 9}" stroke="rgba(248,251,255,0.95)" stroke-width="3"/><line x1="${frontX}" y1="${goalY + goalW}" x2="${backX}" y2="${goalY + goalW - 9}" stroke="rgba(248,251,255,0.95)" stroke-width="3"/><line x1="${backX}" y1="${goalY + 9}" x2="${backX}" y2="${goalY + goalW - 9}" stroke="rgba(226,232,240,0.92)" stroke-width="2.4"/><line x1="${frontX}" y1="${goalY}" x2="${frontX}" y2="${goalY + goalW}" stroke="#ffffff" stroke-width="3.4"/>`;
    };
    const scene = `<defs><linearGradient id="fallback-bg" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#6b8d3f"/><stop offset="100%" stop-color="#799946"/></linearGradient><radialGradient id="fallback-light" cx="50%" cy="48%" r="66%"><stop offset="0%" stop-color="rgba(255,255,255,0.08)"/><stop offset="100%" stop-color="rgba(255,255,255,0)"/></radialGradient><pattern id="fallback-net" width="14" height="14" patternUnits="userSpaceOnUse"><path d="M 0 0 L 14 14 M 14 0 L 0 14" stroke="rgba(248,251,255,0.56)" stroke-width="0.9"/></pattern></defs><rect width="${viewW}" height="${viewH}" fill="#6b8d3f"/><rect x="${x - 26}" y="${y - 26}" width="${pitchW + 52}" height="${pitchH + 52}" rx="30" ry="30" fill="#a6c15d"/><rect x="${x - 12}" y="${y - 12}" width="${pitchW + 24}" height="${pitchH + 24}" rx="22" ry="22" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="1.4"/><rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="#96b758"/>${stripes}${grain}<ellipse cx="${x + pitchW * 0.16}" cy="${cy}" rx="${pitchW * 0.26}" ry="${pitchH * 0.34}" fill="rgba(255,255,255,0.05)"/><ellipse cx="${x + pitchW * 0.84}" cy="${cy}" rx="${pitchW * 0.26}" ry="${pitchH * 0.34}" fill="rgba(255,255,255,0.05)"/><rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="url(#fallback-light)"/><rect x="${x + 6}" y="${y + 6}" width="${pitchW - 12}" height="${pitchH - 12}" rx="12" ry="12" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.2"/><rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="6.1"/><line x1="${cx}" y1="${y}" x2="${cx}" y2="${y + pitchH}" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/><circle cx="${cx}" cy="${cy}" r="${pitchH * 0.145}" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/><rect x="${x}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/><rect x="${x}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/><rect x="${x + pitchW - pitchW * 0.205}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/><rect x="${x + pitchW - pitchW * 0.092}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="rgba(9,18,28,0.11)" stroke-width="5.5"/>${net(true)}${net(false)}<rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="none" stroke="${line}" stroke-width="4.7"/><line x1="${cx}" y1="${y}" x2="${cx}" y2="${y + pitchH}" stroke="${line}" stroke-width="4.1"/><circle cx="${cx}" cy="${cy}" r="${pitchH * 0.145}" fill="none" stroke="${line}" stroke-width="4.1"/><circle cx="${cx}" cy="${cy}" r="4.8" fill="${line}"/><rect x="${x}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="${line}" stroke-width="4.1"/><rect x="${x}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="${line}" stroke-width="4.1"/><rect x="${x + pitchW - pitchW * 0.205}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="${line}" stroke-width="4.1"/><rect x="${x + pitchW - pitchW * 0.092}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="${line}" stroke-width="4.1"/><circle cx="${x + pitchW * 0.165}" cy="${cy}" r="4.2" fill="${line}"/><circle cx="${x + pitchW * 0.835}" cy="${cy}" r="4.2" fill="${line}"/><path d="M ${x + 2} ${y + 16} A 14 14 0 0 1 ${x + 16} ${y + 2}" fill="none" stroke="${line}" stroke-width="3"/><path d="M ${x + pitchW - 16} ${y + 2} A 14 14 0 0 1 ${x + pitchW - 2} ${y + 16}" fill="none" stroke="${line}" stroke-width="3"/><path d="M ${x + 16} ${y + pitchH - 2} A 14 14 0 0 1 ${x + 2} ${y + pitchH - 16}" fill="none" stroke="${line}" stroke-width="3"/><path d="M ${x + pitchW - 2} ${y + pitchH - 16} A 14 14 0 0 1 ${x + pitchW - 16} ${y + pitchH - 2}" fill="none" stroke="${line}" stroke-width="3"/></svg>`;
    if (!portrait) return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewW} ${viewH}" preserveAspectRatio="xMidYMid meet">${scene}`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewH} ${viewW}" preserveAspectRatio="xMidYMid meet"><g transform="translate(${viewH} 0) rotate(90)">${scene}</g></svg>`;
  };

  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
    if (window.WebstatsPitch25D && typeof window.WebstatsPitch25D.buildPitchSvg === 'function') {
      return window.WebstatsPitch25D.buildPitchSvg(presetKey, orientationKey, grassStyleKey);
    }
    return buildEmergencyPitchSvg(orientationKey);
    const preset = String(presetKey || 'full_pitch').trim();
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const normalizedGrass = safeText(grassStyleKey, 'classic').toLowerCase();
    const grassStyle = ([
      'classic',
      'realistic',
      'pro',
      'broadcast',
      'broadcast_premium',
      'stadium_top',
      'stadium_top_h',
      'stadium_top_v',
      'artificial',
      'dry',
      'wet',
      'uefa_b',
      'coachboard',
      'whiteboard',
      'blackboard',
    ].includes(normalizedGrass))
      ? normalizedGrass
      : 'classic';
    const isStadiumTopFamily = ['stadium_top', 'stadium_top_h', 'stadium_top_v'].includes(grassStyle);
    const renderStadiumOverlay = preset !== 'blank' && !['coachboard', 'whiteboard', 'blackboard'].includes(grassStyle);

    const stageW = orientation === 'portrait' ? 680 : 1050;
    const stageH = orientation === 'portrait' ? 1050 : 680;
    const bleed = 30;

    const doc = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg', null);
    const root = doc.documentElement;
    try {
      root.setAttributeNS('http://www.w3.org/2000/xmlns/', 'xmlns:xlink', 'http://www.w3.org/1999/xlink');
    } catch (e) {
      root.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
    }
    root.setAttribute('viewBox', `${-bleed} ${-bleed} ${stageW + (bleed * 2)} ${stageH + (bleed * 2)}`);
    root.setAttribute('preserveAspectRatio', orientation === 'portrait' ? 'xMidYMid slice' : 'xMidYMid meet');

    const resolvePitch3dOverlayImageHref = () => {
      const forcePortrait = grassStyle === 'stadium_top_v';
      const forceLandscape = grassStyle === 'stadium_top_h';
      const usePortraitImage = forcePortrait || (!forceLandscape && orientation === 'portrait');
      try {
        const globalImages = window.__WEBSTATS_PITCH3D_OVERLAY_IMAGES || {};
        const preferred = usePortraitImage ? safeText(globalImages.v) : safeText(globalImages.h);
        if (preferred) return preferred;
      } catch (e) { /* ignore */ }
      try {
        const formEl = document.getElementById('task-builder-form');
        const preferred = usePortraitImage
          ? safeText(formEl?.dataset?.pitch3dStadiumOverlayVSrc)
          : safeText(formEl?.dataset?.pitch3dStadiumOverlayHSrc);
        if (preferred) return preferred;
      } catch (e) { /* ignore */ }
      return usePortraitImage
        ? '/static/football/images/pitch3d/stadium_taskboard_overlay_v.png'
        : '/static/football/images/pitch3d/stadium_taskboard_overlay_h.png';
    };
    const defs = createSvgNode(doc, 'defs');
    const gradient = createSvgNode(doc, 'linearGradient', { id: 'pitch-bg', x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
    const gradientStopsByStyle = {
      classic: ['#5f8f42', '#557f3c'],
      realistic: ['#4f7f3a', '#3f6e35'],
      pro: ['#2f6a3a', '#245934'],
      broadcast: ['#155e3a', '#0f4d2f'],
      broadcast_premium: ['#0f5a39', '#0a4029'],
      stadium_top: ['#194b34', '#102e22'],
      artificial: ['#2fb46d', '#1f8d55'],
      dry: ['#7b9a45', '#6b8a3a'],
      wet: ['#1f5a46', '#163f35'],
      coachboard: ['#315f34', '#214a2c'],
      whiteboard: ['#f8fafc', '#e5e7eb'],
      blackboard: ['#0b1220', '#030712'],
      uefa_b: ['#2f6a3a', '#245934'],
    };
    const stops = gradientStopsByStyle[grassStyle] || gradientStopsByStyle.classic;
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '0%', 'stop-color': stops[0] }));
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '100%', 'stop-color': stops[1] }));
    defs.appendChild(gradient);

    let grassFillId = 'pitch-bg';
    if (grassStyle === 'blackboard') {
      grassFillId = 'pitch-blackboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 120, height: 120 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 120, height: 120, fill: 'url(#pitch-bg)' }));
      for (let i = 0; i < 90; i += 1) {
        const x = (Math.random() * 120).toFixed(2);
        const y = (Math.random() * 120).toFixed(2);
        const r = (0.4 + Math.random() * 1.4).toFixed(2);
        pattern.appendChild(createSvgNode(doc, 'circle', { cx: x, cy: y, r, fill: 'rgba(248,250,252,0.06)' }));
      }
      defs.appendChild(pattern);
    } else if (grassStyle === 'whiteboard') {
      grassFillId = 'pitch-whiteboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 96, height: 96 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 96, height: 96, fill: 'url(#pitch-bg)' }));
      pattern.appendChild(createSvgNode(doc, 'path', {
        d: 'M0 24H96 M0 48H96 M0 72H96 M24 0V96 M48 0V96 M72 0V96',
        stroke: 'rgba(15,23,42,0.06)',
        'stroke-width': 1,
      }));
      defs.appendChild(pattern);
    } else if (grassStyle === 'coachboard') {
      // Estilo "pizarra de entrenador": verde táctico + micro-textura (solo SVG, sin <image>).
      grassFillId = 'pitch-coachboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 96, height: 96 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 96, height: 96, fill: 'url(#pitch-bg)' }));
      pattern.appendChild(createSvgNode(doc, 'path', {
        d: 'M 0 48 L 96 48 M 48 0 L 48 96',
        stroke: 'rgba(248,250,252,0.06)',
        'stroke-width': 1,
      }));
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 96, height: 96, fill: 'rgba(0,0,0,0.04)' }));
      defs.appendChild(pattern);
    } else if (grassStyle !== 'classic' && !isStadiumTopFamily) {
      const dataUrl = __buildGrassTextureDataUrl(grassStyle);
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
        try { image.setAttribute('xlink:href', dataUrl); } catch (e) { /* ignore */ }
        pattern.appendChild(image);
        defs.appendChild(pattern);
      }
    }
    root.appendChild(defs);

    const fillOutside = `url(#${grassFillId})`;
    root.appendChild(createSvgNode(doc, 'rect', {
      x: -bleed,
      y: -bleed,
      width: stageW + (bleed * 2),
      height: stageH + (bleed * 2),
      fill: preset === 'blank' ? 'transparent' : fillOutside,
    }));
    if (renderStadiumOverlay) {
      const overlayHref = resolvePitch3dOverlayImageHref();
      if (overlayHref) {
        const overlay = createSvgNode(doc, 'image', {
          href: overlayHref,
          x: -bleed,
          y: -bleed,
          width: stageW + (bleed * 2),
          height: stageH + (bleed * 2),
          preserveAspectRatio: 'xMidYMid slice',
        });
        try { overlay.setAttribute('xlink:href', overlayHref); } catch (e) { /* ignore */ }
        root.appendChild(overlay);
      }
    }

    const drawRoot = createSvgNode(doc, 'g');
    if (orientation === 'portrait') {
      drawRoot.setAttribute('transform', `translate(${stageW} 0) rotate(90)`);
    }
    root.appendChild(drawRoot);

    const createStage = (desiredAspect = 105 / 68, fitMode = 'contain') => {
      const portrait = orientation === 'portrait';
      const effectiveW = portrait ? stageH : stageW;
      const effectiveH = portrait ? stageW : stageH;
      const marginX = renderStadiumOverlay ? 84 : ((grassStyle === 'broadcast_premium') ? 32 : 0);
      const marginY = renderStadiumOverlay ? 74 : ((grassStyle === 'broadcast_premium') ? 22 : 0);
      const availableWidth = effectiveW - marginX * 2;
      const availableHeight = effectiveH - marginY * 2;
      const fit = safeText(fitMode, 'contain') === 'cover' ? 'cover' : 'contain';
      let width = availableWidth;
      let height = width / desiredAspect;
      if (fit === 'contain') {
        if (height > availableHeight) {
          height = availableHeight;
          width = height * desiredAspect;
        }
      } else {
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

    let stage = createStage(105 / 68, 'contain');
    let pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
    const scale = stage.width / 105;

    const line = (grassStyle === 'whiteboard') ? '#0f172a' : (renderStadiumOverlay ? 'rgba(255,255,255,0.96)' : '#f8fafc');
    const soft = (grassStyle === 'whiteboard') ? 'rgba(15,23,42,0.55)' : (renderStadiumOverlay ? 'rgba(255,255,255,0.78)' : 'rgba(248,250,252,0.66)');

    const drawFrame = (x, y, width, height, lineWidth = 4) => {
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
        x,
        y,
        width,
        height,
        fill: 'none',
        stroke: line,
        'stroke-width': lineWidth,
      }));
    };

    const drawGoal = (x, y, width, depth, atTop) => {
      const goalY = atTop ? (y - depth) : (y + stage.height);
      if (renderStadiumOverlay || grassStyle === 'broadcast_premium') {
        const frameStroke = renderStadiumOverlay ? 'rgba(255,255,255,0.44)' : 'rgba(255,255,255,0.34)';
        const meshStroke = renderStadiumOverlay ? 'rgba(255,255,255,0.24)' : 'rgba(255,255,255,0.18)';
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x,
          y: goalY,
          width,
          height: depth,
          fill: renderStadiumOverlay ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.05)',
          stroke: frameStroke,
          'stroke-width': 3,
        }));
        for (let i = 1; i <= 4; i += 1) {
          const yy = goalY + ((depth * i) / 5);
          drawRoot.appendChild(createSvgNode(doc, 'line', {
            x1: x,
            y1: yy,
            x2: x + width,
            y2: yy,
            stroke: meshStroke,
            'stroke-width': 1,
          }));
        }
        for (let i = 1; i <= 3; i += 1) {
          const xx = x + ((width * i) / 4);
          drawRoot.appendChild(createSvgNode(doc, 'line', {
            x1: xx,
            y1: goalY,
            x2: xx,
            y2: goalY + depth,
            stroke: meshStroke,
            'stroke-width': 1,
          }));
        }
        drawRoot.appendChild(createSvgNode(doc, 'line', {
          x1: x + 3,
          y1: atTop ? goalY - 2 : goalY + depth + 2,
          x2: x + width - 3,
          y2: atTop ? goalY - 2 : goalY + depth + 2,
          stroke: 'rgba(2,6,23,0.18)',
          'stroke-width': 3,
        }));
        return;
      }
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
        x,
        y: goalY,
        width,
        height: depth,
        fill: 'rgba(255,255,255,0.06)',
        stroke: soft,
        'stroke-width': 3,
      }));
    };

    const drawAdvertisingBoards = (x, y, width, height) => {
      if (renderStadiumOverlay || grassStyle !== 'broadcast_premium') return;
      const offset = 16;
      const bandH = 11;
      const palette = ['rgba(15,23,42,0.76)', 'rgba(34,211,238,0.64)', 'rgba(255,255,255,0.74)', 'rgba(34,197,94,0.62)', 'rgba(255,255,255,0.74)', 'rgba(15,23,42,0.76)'];
      const segments = 6;
      const segmentW = width / segments;
      const topY = y - offset - bandH;
      const bottomY = y + height + offset;
      for (let i = 0; i < segments; i += 1) {
        const segX = x + (i * segmentW) + 4;
        const segW = Math.max(14, segmentW - 8);
        [topY, bottomY].forEach((bandY) => {
          drawRoot.appendChild(createSvgNode(doc, 'rect', {
            x: segX,
            y: bandY,
            width: segW,
            height: bandH,
            rx: 7,
            ry: 7,
            fill: palette[i % palette.length],
            stroke: 'rgba(255,255,255,0.3)',
            'stroke-width': 1.3,
          }));
        });
      }
    };

    const drawStadiumContext = (x, y, width, height) => {
      if (renderStadiumOverlay || !isStadiumTopFamily) return;
      const runoff = 26;
      const concourseH = 38;
      const standH = 84;
      const sideW = 74;
      const drawConcourse = (bandY) => {
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: x - 10,
          y: bandY,
          width: width + 20,
          height: concourseH,
          rx: 6,
          ry: 6,
          fill: 'rgba(15,23,42,0.72)',
          stroke: 'rgba(226,232,240,0.14)',
          'stroke-width': 1.4,
        }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: x - 10,
          y: bandY + 8,
          width: width + 20,
          height: 6,
          fill: 'rgba(148,163,184,0.22)',
          stroke: 'none',
        }));
      };
      const drawStand = (bandY, fillColor, stripeColor) => {
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: x - sideW,
          y: bandY,
          width: width + (sideW * 2),
          height: standH,
          fill: fillColor,
          stroke: 'rgba(255,255,255,0.08)',
          'stroke-width': 1,
        }));
        for (let i = 0; i < 9; i += 1) {
          const rowY = bandY + 8 + (i * 6.4);
          drawRoot.appendChild(createSvgNode(doc, 'line', {
            x1: x - sideW,
            y1: rowY,
            x2: x + width + sideW,
            y2: rowY,
            stroke: stripeColor,
            'stroke-width': 1,
          }));
        }
      };
      const drawSideStand = (sideX, concourseX, fillColor, strokeColor) => {
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: sideX,
          y: y - 18,
          width: sideW - 18,
          height: height + 36,
          rx: 14,
          ry: 14,
          fill: fillColor,
          stroke: 'rgba(255,255,255,0.08)',
          'stroke-width': 1,
        }));
        for (let i = 0; i < 10; i += 1) {
          const rowX = sideX + 8 + (i * 4.8);
          drawRoot.appendChild(createSvgNode(doc, 'line', {
            x1: rowX,
            y1: y - 14,
            x2: rowX,
            y2: y + height + 14,
            stroke: strokeColor,
            'stroke-width': 1,
          }));
        }
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: concourseX,
          y: y - 12,
          width: 12,
          height: height + 24,
          rx: 6,
          ry: 6,
          fill: 'rgba(15,23,42,0.74)',
          stroke: 'rgba(226,232,240,0.14)',
          'stroke-width': 1,
        }));
      };
      const drawDugout = (cx, cy, flip = false) => {
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: cx - 64,
          y: cy - 10,
          width: 128,
          height: 20,
          rx: 10,
          ry: 10,
          fill: 'rgba(15,23,42,0.84)',
          stroke: 'rgba(255,255,255,0.2)',
          'stroke-width': 1.2,
        }));
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: cx - 58,
          y: cy - 6,
          width: 116,
          height: 12,
          rx: 7,
          ry: 7,
          fill: 'rgba(148,163,184,0.18)',
          stroke: 'rgba(255,255,255,0.12)',
          'stroke-width': 1,
        }));
        for (let i = -44; i <= 44; i += 22) {
          drawRoot.appendChild(createSvgNode(doc, 'rect', {
            x: cx + i - 8,
            y: cy - 4,
            width: 16,
            height: 8,
            rx: 3,
            ry: 3,
            fill: 'rgba(14,165,233,0.55)',
            stroke: 'none',
          }));
        }
        drawRoot.appendChild(createSvgNode(doc, 'line', {
          x1: cx - 70,
          y1: cy + (flip ? -16 : 16),
          x2: cx + 70,
          y2: cy + (flip ? -16 : 16),
          stroke: 'rgba(226,232,240,0.18)',
          'stroke-width': 2,
          'stroke-dasharray': '10 8',
        }));
      };
      const drawTechnicalArea = (cx, topY, flip = false) => {
        drawRoot.appendChild(createSvgNode(doc, 'rect', {
          x: cx - 86,
          y: topY - 14,
          width: 172,
          height: 28,
          rx: 12,
          ry: 12,
          fill: 'rgba(8,15,28,0.58)',
          stroke: 'rgba(255,255,255,0.10)',
          'stroke-width': 1,
        }));
        drawRoot.appendChild(createSvgNode(doc, 'line', {
          x1: cx - 76,
          y1: topY + (flip ? 18 : -18),
          x2: cx + 76,
          y2: topY + (flip ? 18 : -18),
          stroke: 'rgba(255,255,255,0.24)',
          'stroke-width': 2,
          'stroke-dasharray': '12 8',
        }));
      };

      drawConcourse(y - runoff - concourseH - 4);
      drawStand(y - runoff - concourseH - standH - 8, 'rgba(134,239,172,0.18)', 'rgba(240,253,244,0.10)');
      drawConcourse(y + height + runoff + 4);
      drawStand(y + height + runoff + concourseH + 8, 'rgba(163,230,53,0.16)', 'rgba(236,252,203,0.08)');
      drawSideStand(x - sideW + 8, x - 16, 'rgba(134,239,172,0.14)', 'rgba(240,253,244,0.08)');
      drawSideStand(x + width + 10, x + width + 4, 'rgba(163,230,53,0.12)', 'rgba(236,252,203,0.08)');
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
        x: x - runoff,
        y: y - runoff,
        width: width + (runoff * 2),
        height: height + (runoff * 2),
        rx: 18,
        ry: 18,
        fill: 'none',
        stroke: 'rgba(255,255,255,0.12)',
        'stroke-width': 8,
      }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', {
        x: x - 6,
        y: y - 6,
        width: width + 12,
        height: height + 12,
        rx: 18,
        ry: 18,
        fill: 'none',
        stroke: 'rgba(255,255,255,0.08)',
        'stroke-width': 14,
      }));
      drawDugout(x + (width * 0.28), y + height + 46, false);
      drawDugout(x + (width * 0.72), y + height + 46, false);
      drawDugout(x + (width * 0.28), y - 46, true);
      drawDugout(x + (width * 0.72), y - 46, true);
      drawTechnicalArea(x + (width * 0.28), y + height + 34, false);
      drawTechnicalArea(x + (width * 0.72), y + height + 34, false);
      drawTechnicalArea(x + (width * 0.28), y - 34, true);
      drawTechnicalArea(x + (width * 0.72), y - 34, true);
    };

    const drawCenter = () => {
      drawRoot.appendChild(createSvgNode(doc, 'line', {
        x1: stage.x,
        y1: stage.y + stage.height / 2,
        x2: stage.x + stage.width,
        y2: stage.y + stage.height / 2,
        stroke: line,
        'stroke-width': 3,
      }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', {
        cx: stage.x + stage.width / 2,
        cy: stage.y + stage.height / 2,
        r: 9.15 * scale,
        fill: 'none',
        stroke: line,
        'stroke-width': 3,
      }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', {
        cx: stage.x + stage.width / 2,
        cy: stage.y + stage.height / 2,
        r: 0.35 * scale,
        fill: line,
      }));
    };

    const drawPenaltyAreas = () => {
      // 16.5m box and 5.5m goal area.
      const boxW = 40.32 * scale;
      const boxH = 16.5 * scale;
      const goalW = 18.32 * scale;
      const goalH = 5.5 * scale;
      const xBox = stage.x + (stage.width - boxW) / 2;
      const xGoal = stage.x + (stage.width - goalW) / 2;
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xBox, y: stage.y, width: boxW, height: boxH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xGoal, y: stage.y, width: goalW, height: goalH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xBox, y: stage.y + stage.height - boxH, width: boxW, height: boxH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xGoal, y: stage.y + stage.height - goalH, width: goalW, height: goalH, fill: 'none', stroke: line, 'stroke-width': 3 }));
    };

    // Presets: we keep full_pitch and seven_side_single compatible with Tactical Pad.
    if (preset === 'seven_side_single') {
      // 7v7 pitch proportions (approx 45x65) centered inside 105x68 stage.
      const desiredAspect = 45 / 65;
      stage = createStage(desiredAspect, 'contain');
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
      drawStadiumContext(stage.x, stage.y, stage.width, stage.height);
      drawFrame(stage.x, stage.y, stage.width, stage.height, 4);
      drawRoot.appendChild(createSvgNode(doc, 'line', {
        x1: stage.x,
        y1: stage.y + stage.height / 2,
        x2: stage.x + stage.width,
        y2: stage.y + stage.height / 2,
        stroke: line,
        'stroke-width': 3,
      }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', {
        cx: stage.x + stage.width / 2,
        cy: stage.y + stage.height / 2,
        r: (stage.width / 105) * 9.15,
        fill: 'none',
        stroke: line,
        'stroke-width': 3,
      }));
      const goalDepth = 22;
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, true);
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, false);
      drawAdvertisingBoards(stage.x, stage.y, stage.width, stage.height);
    } else if (preset === 'half_pitch') {
      // Half pitch: keep top half.
      const halfHeight = stage.height / 2;
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: halfHeight };
      drawStadiumContext(stage.x, stage.y, stage.width, halfHeight);
      drawFrame(stage.x, stage.y, stage.width, halfHeight, 4);
      const scaleHalf = stage.width / 105;
      const boxW = 40.32 * scaleHalf;
      const boxH = 16.5 * scaleHalf;
      const goalW = 18.32 * scaleHalf;
      const goalH = 5.5 * scaleHalf;
      const xBox = stage.x + (stage.width - boxW) / 2;
      const xGoal = stage.x + (stage.width - goalW) / 2;
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xBox, y: stage.y, width: boxW, height: boxH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xGoal, y: stage.y, width: goalW, height: goalH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawAdvertisingBoards(stage.x, stage.y, stage.width, halfHeight);
    } else if (preset === 'blank') {
      // Surface free: keep only grass rect already drawn.
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
    } else {
      // full_pitch + default
      drawStadiumContext(stage.x, stage.y, stage.width, stage.height);
      drawFrame(stage.x, stage.y, stage.width, stage.height, 4);
      drawCenter();
      drawPenaltyAreas();
      const goalDepth = 22;
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, true);
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, false);
      drawAdvertisingBoards(stage.x, stage.y, stage.width, stage.height);
    }

    // For downstream consumers (export), expose pitch box.
    try {
      root.setAttribute('data-pitch-box', `${pitchBox.x.toFixed(2)} ${pitchBox.y.toFixed(2)} ${pitchBox.width.toFixed(2)} ${pitchBox.height.toFixed(2)}`);
    } catch (e) { /* ignore */ }

    return new XMLSerializer().serializeToString(doc);
  };

  const applyToSvg = (svgEl, preset, orientation, grassStyle) => {
    if (!svgEl || !svgEl.ownerDocument) return false;
    const markup = buildPitchSvg(preset, orientation, grassStyle);
    const syncFromRoot = (root) => {
      svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      try {
        const xlink = safeText(root.getAttribute('xmlns:xlink') || root.getAttribute('xmlns:XLink'));
        svgEl.setAttribute('xmlns:xlink', xlink || 'http://www.w3.org/1999/xlink');
      } catch (e) {
        try { svgEl.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink'); } catch (e2) { /* ignore */ }
      }
      svgEl.setAttribute('viewBox', root.getAttribute('viewBox') || '-30 -30 1110 740');
      svgEl.setAttribute('preserveAspectRatio', root.getAttribute('preserveAspectRatio') || 'xMidYMid meet');
      const pitchBox = root.getAttribute('data-pitch-box') || '';
      if (pitchBox) svgEl.setAttribute('data-pitch-box', pitchBox);
      else svgEl.removeAttribute('data-pitch-box');
      while (svgEl.firstChild) svgEl.removeChild(svgEl.firstChild);
      Array.from(root.childNodes).forEach((child) => {
        svgEl.appendChild(svgEl.ownerDocument.importNode(child, true));
      });
    };

    try {
      const parsed = new DOMParser().parseFromString(markup, 'image/svg+xml');
      let root = parsed.documentElement;
      if (root && root.tagName && root.tagName.toLowerCase() !== 'svg') {
        const candidate = parsed.querySelector && parsed.querySelector('svg');
        if (candidate) root = candidate;
      }
      if (root && root.tagName && root.tagName.toLowerCase() === 'svg') {
        syncFromRoot(root);
        return true;
      }
    } catch (error) {
      // ignore
    }
    try {
      const openMatch = markup.match(/<svg\\b([^>]*)>/i);
      const closeIndex = markup.lastIndexOf('</svg>');
      if (openMatch && closeIndex > 0) {
        const openIndex = openMatch.index || 0;
        const openEnd = markup.indexOf('>', openIndex);
        if (openEnd > openIndex) {
          const attrs = openMatch[1] || '';
          const inner = markup.slice(openEnd + 1, closeIndex);
          const readAttr = (name) => {
            const re = new RegExp(`\\\\b${name}\\\\s*=\\\\s*[\"']([^\"']+)[\"']`, 'i');
            const m = attrs.match(re);
            return m ? safeText(m[1]) : '';
          };
          svgEl.setAttribute('viewBox', readAttr('viewBox') || '-30 -30 1110 740');
          svgEl.setAttribute('preserveAspectRatio', readAttr('preserveAspectRatio') || 'xMidYMid meet');
          const xlink = readAttr('xmlns:xlink') || readAttr('xmlns:XLink');
          if (xlink) svgEl.setAttribute('xmlns:xlink', xlink);
          svgEl.innerHTML = inner;
          return true;
        }
      }
    } catch (error) {
      // ignore
    }
    return false;
  };

  window.WebstatsPitchSurface = {
    buildPitchSvg,
    applyToSvg,
  };
}());
