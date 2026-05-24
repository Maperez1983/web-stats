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

  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
    const preset = String(presetKey || 'full_pitch').trim();
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const normalizedGrass = safeText(grassStyleKey, 'classic').toLowerCase();
    const grassStyle = ([
      'classic',
      'realistic',
      'pro',
      'broadcast',
      'artificial',
      'dry',
      'wet',
      'uefa_b',
      'whiteboard',
      'blackboard',
    ].includes(normalizedGrass))
      ? normalizedGrass
      : 'classic';

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

    const defs = createSvgNode(doc, 'defs');
    const gradient = createSvgNode(doc, 'linearGradient', { id: 'pitch-bg', x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
    const gradientStopsByStyle = {
      classic: ['#5f8f42', '#557f3c'],
      realistic: ['#4f7f3a', '#3f6e35'],
      pro: ['#2f6a3a', '#245934'],
      broadcast: ['#155e3a', '#0f4d2f'],
      artificial: ['#2fb46d', '#1f8d55'],
      dry: ['#7b9a45', '#6b8a3a'],
      wet: ['#1f5a46', '#163f35'],
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
    } else if (grassStyle !== 'classic') {
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

    const drawRoot = createSvgNode(doc, 'g');
    if (orientation === 'portrait') {
      drawRoot.setAttribute('transform', `translate(${stageW} 0) rotate(90)`);
    }
    root.appendChild(drawRoot);

    const createStage = (desiredAspect = 105 / 68, fitMode = 'contain') => {
      const portrait = orientation === 'portrait';
      const effectiveW = portrait ? stageH : stageW;
      const effectiveH = portrait ? stageW : stageH;
      const availableWidth = effectiveW;
      const availableHeight = effectiveH;
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

    const line = (grassStyle === 'whiteboard') ? '#0f172a' : '#f8fafc';
    const soft = (grassStyle === 'whiteboard') ? 'rgba(15,23,42,0.55)' : 'rgba(248,250,252,0.66)';

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
      const goalY = atTop ? (y - depth) : (y + (stage.height));
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
      // Frame + center line + circle (scaled to stage).
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
      // Small goals.
      const goalDepth = 22;
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, true);
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, false);
    } else if (preset === 'half_pitch') {
      // Half pitch: keep top half.
      const halfHeight = stage.height / 2;
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: halfHeight };
      drawFrame(stage.x, stage.y, stage.width, halfHeight, 4);
      // penalty only in top.
      const scaleHalf = stage.width / 105;
      const boxW = 40.32 * scaleHalf;
      const boxH = 16.5 * scaleHalf;
      const goalW = 18.32 * scaleHalf;
      const goalH = 5.5 * scaleHalf;
      const xBox = stage.x + (stage.width - boxW) / 2;
      const xGoal = stage.x + (stage.width - goalW) / 2;
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xBox, y: stage.y, width: boxW, height: boxH, fill: 'none', stroke: line, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: xGoal, y: stage.y, width: goalW, height: goalH, fill: 'none', stroke: line, 'stroke-width': 3 }));
    } else if (preset === 'blank') {
      // Surface free: keep only grass rect already drawn.
      pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
    } else {
      // full_pitch + default
      drawFrame(stage.x, stage.y, stage.width, stage.height, 4);
      drawCenter();
      drawPenaltyAreas();
      const goalDepth = 22;
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, true);
      drawGoal(stage.x + stage.width * 0.42, stage.y, stage.width * 0.16, goalDepth, false);
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

