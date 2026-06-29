// Lightweight pitch surface SVG builder (preview-only).
// Extracted from `sessions_tactical_pad.js` to reuse the exact same pitch rendering
// without loading the full tactical editor engine on landing pages.
(function () {
  const safeText = (value, fallback = '') => String(value || '').trim() || fallback;

  const createSvgNode = (doc, tag, attrs) => {
    const node = doc.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  };

  const __grassTextureCache = new Map();
  const __buildGrassTextureDataUrl = (styleKey) => {
    const style = safeText(styleKey, 'classic').toLowerCase();
    const allowed = new Set(['realistic', 'pro', 'natural', 'artificial', 'albero', 'dirt', 'indoor', 'dry', 'wet', 'uefa_b', 'broadcast']);
    if (!allowed.has(style)) return '';
    if (__grassTextureCache.has(style)) return __grassTextureCache.get(style);
    try {
      if (style === 'uefa_b') {
        const fromWindow = (() => {
          try { return safeText(window.__WEBSTATS_GRASS_TILES && window.__WEBSTATS_GRASS_TILES.uefa_b); } catch (e) { return ''; }
        })();
        const href = (fromWindow && fromWindow.startsWith('data:image/'))
          ? fromWindow
          : '/static/football/images/surfaces/grass_uefa_b_tile.png';
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
        natural: '#3f7a34',
        pro: '#2f6a3a',
        broadcast: '#155e3a',
        artificial: '#2fb46d',
        albero: '#c99042',
        dirt: '#8f5c38',
        indoor: '#2f5965',
        dry: '#6b8a3a',
        wet: '#1f5a46',
      };
      ctx.fillStyle = baseByStyle[style] || '#4f7f3a';
      ctx.fillRect(0, 0, size, size);

      const stripeCount = style === 'artificial' ? 10 : style === 'broadcast' ? 12 : (style === 'albero' || style === 'dirt' || style === 'indoor') ? 0 : 8;
      if (stripeCount > 0) {
        const stripeW = size / stripeCount;
        for (let i = 0; i < stripeCount; i += 1) {
          const alpha = style === 'broadcast' ? 0.10 : style === 'pro' ? 0.08 : style === 'wet' ? 0.06 : style === 'dry' ? 0.04 : 0.05;
          ctx.fillStyle = i % 2 === 0 ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha})`;
          ctx.fillRect(i * stripeW, 0, stripeW + 1, size);
        }
      }

      for (let i = 0; i < 9000; i += 1) {
        const x = (Math.random() * size) | 0;
        const y = (Math.random() * size) | 0;
        const noiseMax = style === 'artificial' ? 18 : (style === 'albero' || style === 'dirt') ? 110 : 70;
        const g = style === 'dry' ? (90 + ((Math.random() * 45) | 0)) : (110 + ((Math.random() * noiseMax) | 0));
        const a = (style === 'artificial' ? 0.04 : 0.08) + (Math.random() * 0.12);
        ctx.fillStyle = style === 'albero'
          ? `rgba(${160 + ((Math.random() * 72) | 0)}, ${100 + ((Math.random() * 48) | 0)}, ${36 + ((Math.random() * 30) | 0)}, ${a + 0.06})`
          : style === 'dirt'
            ? `rgba(${105 + ((Math.random() * 60) | 0)}, ${62 + ((Math.random() * 36) | 0)}, ${38 + ((Math.random() * 30) | 0)}, ${a + 0.08})`
            : style === 'indoor'
              ? `rgba(${30 + ((Math.random() * 36) | 0)}, ${88 + ((Math.random() * 42) | 0)}, ${102 + ((Math.random() * 40) | 0)}, ${a})`
              : style === 'wet'
                ? `rgba(10, ${Math.max(70, g)}, 30, ${a})`
                : `rgba(0, ${g}, 0, ${a})`;
        ctx.fillRect(x, y, 2, 2);
      }

      ctx.globalAlpha = style === 'pro' ? 0.14 : style === 'artificial' ? 0.08 : (style === 'albero' || style === 'dirt' || style === 'indoor') ? 0.10 : 0.12;
      const streaks = style === 'artificial' ? 140 : (style === 'albero' || style === 'dirt') ? 260 : 220;
      for (let i = 0; i < streaks; i += 1) {
        const x = Math.random() * size;
        const y = Math.random() * size;
        const len = 12 + Math.random() * 44;
        const angle = (-Math.PI / 3) + (Math.random() * (style === 'artificial' ? Math.PI / 8 : Math.PI / 5));
        const c = style === 'dry' ? (120 + ((Math.random() * 40) | 0)) : (120 + ((Math.random() * 60) | 0));
        ctx.lineWidth = 1 + Math.random() * (style === 'pro' ? 2.4 : 2);
        ctx.strokeStyle = style === 'albero'
          ? `rgb(${175 + ((Math.random() * 45) | 0)}, ${120 + ((Math.random() * 34) | 0)}, ${58 + ((Math.random() * 24) | 0)})`
          : style === 'dirt'
            ? `rgb(${118 + ((Math.random() * 42) | 0)}, ${76 + ((Math.random() * 28) | 0)}, ${48 + ((Math.random() * 24) | 0)})`
            : style === 'indoor'
              ? `rgb(45, ${120 + ((Math.random() * 36) | 0)}, ${135 + ((Math.random() * 32) | 0)})`
              : style === 'wet' ? `rgb(20, ${c}, 40)` : `rgb(30, ${c}, 30)`;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + Math.cos(angle) * len, y + Math.sin(angle) * len);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      const grad = ctx.createRadialGradient(size / 2, size / 2, size / 4, size / 2, size / 2, size * 0.9);
      grad.addColorStop(0, 'rgba(255,255,255,0)');
      grad.addColorStop(1, style === 'wet' ? 'rgba(0,0,0,0.26)' : 'rgba(0,0,0,0.18)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, size, size);
      const dataUrl = canvas.toDataURL('image/png');
      __grassTextureCache.set(style, dataUrl);
      return dataUrl;
    } catch (e) {
      return '';
    }
  };

  const buildEmergencyPitchSvg = (orientationKey = 'landscape') => {
    const portrait = safeText(orientationKey, 'landscape') === 'portrait';
    const viewW = 1200;
    const viewH = 820;
    const pitchW = 920;
    const pitchH = 596;
    const x = (viewW - pitchW) / 2;
    const y = (viewH - pitchH) / 2;
    const cx = x + pitchW / 2;
    const cy = y + pitchH / 2;
    const goalW = pitchH * 0.185;
    const goalY = cy - goalW / 2;
    const goalDepth = 30;
    const line = '#f8fbff';
    const stripes = Array.from({ length: 12 }, (_, index) => {
      const width = pitchW / 12;
      return `<rect x="${x + index * width}" y="${y}" width="${width + 1}" height="${pitchH}" fill="${index % 2 === 0 ? '#95b74b' : '#7ea43d'}" opacity="0.96"/>`;
    }).join('');
    const net = (left) => {
      const frontX = left ? x : x + pitchW;
      const backX = left ? x - goalDepth : x + pitchW + goalDepth;
      const points = left
        ? `${backX},${goalY + 8} ${frontX},${goalY} ${frontX},${goalY + goalW} ${backX},${goalY + goalW - 8}`
        : `${frontX},${goalY} ${backX},${goalY + 8} ${backX},${goalY + goalW - 8} ${frontX},${goalY + goalW}`;
      return `<polygon points="${points}" fill="url(#fallback-net)" opacity="0.58"/><line x1="${frontX}" y1="${goalY}" x2="${backX}" y2="${goalY + 8}" stroke="rgba(248,251,255,0.9)" stroke-width="3"/><line x1="${frontX}" y1="${goalY + goalW}" x2="${backX}" y2="${goalY + goalW - 8}" stroke="rgba(248,251,255,0.9)" stroke-width="3"/><line x1="${backX}" y1="${goalY + 8}" x2="${backX}" y2="${goalY + goalW - 8}" stroke="rgba(248,251,255,0.9)" stroke-width="3"/>`;
    };
    const scene = `<defs><linearGradient id="fallback-bg" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#1f6c46"/><stop offset="100%" stop-color="#185339"/></linearGradient><radialGradient id="fallback-light" cx="50%" cy="46%" r="70%"><stop offset="0%" stop-color="rgba(255,255,255,0.16)"/><stop offset="100%" stop-color="rgba(255,255,255,0)"/></radialGradient><pattern id="fallback-net" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M 0 0 L 16 16 M 16 0 L 0 16" stroke="rgba(248,251,255,0.38)" stroke-width="1"/></pattern></defs><rect width="${viewW}" height="${viewH}" fill="#5f8f42"/><ellipse cx="${cx}" cy="${cy + 16}" rx="${pitchW * 0.56}" ry="${pitchH * 0.42}" fill="rgba(0,0,0,0.10)"/><rect x="${x - 54}" y="${y - 54}" width="${pitchW + 108}" height="${pitchH + 108}" rx="28" ry="28" fill="rgba(255,255,255,0.08)"/><rect x="${x - 22}" y="${y - 22}" width="${pitchW + 44}" height="${pitchH + 44}" rx="22" ry="22" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" stroke-width="2"/><rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="url(#fallback-bg)"/>${stripes}<rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="url(#fallback-light)"/><rect x="${x + 8}" y="${y + 8}" width="${pitchW - 16}" height="${pitchH - 16}" rx="12" ry="12" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="2"/><rect x="${x}" y="${y}" width="${pitchW}" height="${pitchH}" rx="16" ry="16" fill="none" stroke="${line}" stroke-width="5"/><line x1="${cx}" y1="${y}" x2="${cx}" y2="${y + pitchH}" stroke="${line}" stroke-width="4.4"/><circle cx="${cx}" cy="${cy}" r="${pitchH * 0.145}" fill="none" stroke="${line}" stroke-width="4.4"/><circle cx="${cx}" cy="${cy}" r="5" fill="${line}"/><rect x="${x}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="${line}" stroke-width="4.4"/><rect x="${x}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="${line}" stroke-width="4.4"/><rect x="${x + pitchW - pitchW * 0.205}" y="${cy - pitchH * 0.2575}" width="${pitchW * 0.205}" height="${pitchH * 0.515}" fill="none" stroke="${line}" stroke-width="4.4"/><rect x="${x + pitchW - pitchW * 0.092}" y="${cy - pitchH * 0.1125}" width="${pitchW * 0.092}" height="${pitchH * 0.225}" fill="none" stroke="${line}" stroke-width="4.4"/><circle cx="${x + pitchW * 0.165}" cy="${cy}" r="4.2" fill="${line}"/><circle cx="${x + pitchW * 0.835}" cy="${cy}" r="4.2" fill="${line}"/>${net(true)}${net(false)}</svg>`;
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
    const grassStyle = (['classic', 'broadcast', 'realistic', 'pro', 'natural', 'artificial', 'albero', 'dirt', 'indoor', 'dry', 'wet', 'uefa_b', 'coachboard', 'whiteboard', 'blackboard'].includes(normalizedGrass))
      ? normalizedGrass
      : 'classic';
    const stageW = orientation === 'portrait' ? 680 : 1050;
    const stageH = orientation === 'portrait' ? 1050 : 680;
    const bleed = 30;
    const doc = document.implementation.createDocument('http://www.w3.org/2000/svg', 'svg', null);
    const root = doc.documentElement;
    root.setAttribute('viewBox', `${-bleed} ${-bleed} ${stageW + (bleed * 2)} ${stageH + (bleed * 2)}`);
    root.setAttribute('preserveAspectRatio', orientation === 'portrait' ? 'xMidYMid slice' : 'xMidYMid meet');

    const defs = createSvgNode(doc, 'defs');
    const gradient = createSvgNode(doc, 'linearGradient', { id: 'pitch-bg', x1: '0%', y1: '0%', x2: '0%', y2: '100%' });
    const gradientStopsByStyle = {
      classic: ['#5f8f42', '#557f3c'],
      broadcast: ['#155e3a', '#0f4d2f'],
      realistic: ['#4f7f3a', '#3f6e35'],
      pro: ['#2f6a3a', '#245934'],
      natural: ['#3f7a34', '#2f682d'],
      artificial: ['#2fb46d', '#1f8d55'],
      albero: ['#c99042', '#a96d2f'],
      dirt: ['#8f5c38', '#71452c'],
      indoor: ['#2f5965', '#244954'],
      dry: ['#7b9a45', '#6b8a3a'],
      wet: ['#1f5a46', '#163f35'],
      coachboard: ['#315f34', '#214a2c'],
      uefa_b: ['#2f6a3a', '#245934'],
      whiteboard: ['#f8fafc', '#e5e7eb'],
      blackboard: ['#0b1220', '#030712'],
    };
    const [g0, g1] = gradientStopsByStyle[grassStyle] || gradientStopsByStyle.classic;
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '0%', 'stop-color': g0 }));
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '100%', 'stop-color': g1 }));
    defs.appendChild(gradient);
    let grassFillId = 'pitch-bg';
    if (grassStyle === 'whiteboard') {
      grassFillId = 'pitch-whiteboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 80, height: 80 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 80, height: 80, fill: 'url(#pitch-bg)' }));
      pattern.appendChild(createSvgNode(doc, 'path', { d: 'M 0 40 L 80 40 M 40 0 L 40 80', stroke: 'rgba(15,23,42,0.08)', 'stroke-width': 1 }));
      defs.appendChild(pattern);
    } else if (grassStyle === 'coachboard') {
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
    } else if (grassStyle === 'blackboard') {
      grassFillId = 'pitch-blackboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 120, height: 120 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 120, height: 120, fill: 'url(#pitch-bg)' }));
      for (let i = 0; i < 70; i += 1) {
        const x = (Math.random() * 120).toFixed(2);
        const y = (Math.random() * 120).toFixed(2);
        const r = (0.4 + Math.random() * 1.4).toFixed(2);
        pattern.appendChild(createSvgNode(doc, 'circle', { cx: x, cy: y, r, fill: 'rgba(248,250,252,0.06)' }));
      }
      defs.appendChild(pattern);
    } else if (grassStyle !== 'classic') {
      const dataUrl = __buildGrassTextureDataUrl(grassStyle);
      if (dataUrl) {
        grassFillId = 'pitch-grass-img';
        const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 220, height: 220 });
        const image = createSvgNode(doc, 'image', {
          href: dataUrl,
          x: 0,
          y: 0,
          width: 220,
          height: 220,
          preserveAspectRatio: 'xMidYMid slice',
        });
        try { image.setAttribute('xlink:href', dataUrl); } catch (e) {}
        pattern.appendChild(image);
        defs.appendChild(pattern);
      }
    }
    root.appendChild(defs);

    root.appendChild(
      createSvgNode(doc, 'rect', {
        x: -bleed,
        y: -bleed,
        width: stageW + (bleed * 2),
        height: stageH + (bleed * 2),
        fill: preset === 'blank' ? 'transparent' : `url(#${grassFillId})`,
      }),
    );

    const drawRoot = createSvgNode(doc, 'g');
    if (orientation === 'portrait') drawRoot.setAttribute('transform', `translate(${stageW} 0) rotate(90)`);
    root.appendChild(drawRoot);

    const createStage = (orientation, desiredAspect = 105 / 68, fitMode = 'contain') => {
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

    const stage = createStage(orientation);
    let pitchBox = { x: stage.x, y: stage.y, width: stage.width, height: stage.height };
    const scale = stage.width / 105;
    const line = (grassStyle === 'whiteboard') ? '#0f172a' : '#f8fafc';
    const soft = (grassStyle === 'whiteboard') ? 'rgba(15,23,42,0.55)' : 'rgba(248,250,252,0.66)';

    const stripeAlphaByStyle = {
      classic: 0.05,
      realistic: 0.05,
      pro: 0.07,
      artificial: 0.06,
      dry: 0.04,
      wet: 0.04,
    };
    const drawFrame = (x, y, width, height, lineWidth = 4) => {
      drawRoot.appendChild(
        createSvgNode(doc, 'rect', { x, y, width, height, fill: `url(#${grassFillId})`, stroke: line, 'stroke-width': lineWidth }),
      );
      const stripeW = width / 12;
      const alpha = stripeAlphaByStyle[grassStyle] ?? 0.05;
      for (let index = 0; index < 12; index += 1) {
        drawRoot.appendChild(
          createSvgNode(doc, 'rect', {
            x: x + (index * stripeW),
            y,
            width: stripeW + 1,
            height,
            fill: index % 2 === 0 ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha})`,
            stroke: 'none',
          }),
        );
      }
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y, width, height, fill: 'transparent', stroke: line, 'stroke-width': lineWidth }));
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
      corners.forEach((d) => drawRoot.appendChild(createSvgNode(doc, 'path', { d, fill: 'none', stroke: line, 'stroke-width': 2 })));
    };

    const drawFullPitch = () => {
      const x = stage.x;
      const y = stage.y;
      const w = stage.width;
      const h = stage.height;
      drawFrame(x, y, w, h, 4);

      // Midline + center circle.
      drawRoot.appendChild(createSvgNode(doc, 'line', { x1: x + (w / 2), y1: y, x2: x + (w / 2), y2: y + h, stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + (w / 2), cy: y + (h / 2), r: 9.15 * scale, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + (w / 2), cy: y + (h / 2), r: 0.35 * scale, fill: soft }));

      // Penalty areas.
      const boxDepth = 16.5 * scale;
      const boxWidth = 40.3 * scale;
      const smallDepth = 5.5 * scale;
      const smallWidth = 18.32 * scale;
      const penaltySpot = 11 * scale;

      const leftBoxY = y + (h - boxWidth) / 2;
      const rightBoxY = leftBoxY;
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: leftBoxY, width: boxDepth, height: boxWidth, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + w - boxDepth, y: rightBoxY, width: boxDepth, height: boxWidth, fill: 'none', stroke: soft, 'stroke-width': 3 }));

      const leftSmallY = y + (h - smallWidth) / 2;
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x, y: leftSmallY, width: smallDepth, height: smallWidth, fill: 'none', stroke: soft, 'stroke-width': 3 }));
      drawRoot.appendChild(createSvgNode(doc, 'rect', { x: x + w - smallDepth, y: leftSmallY, width: smallDepth, height: smallWidth, fill: 'none', stroke: soft, 'stroke-width': 3 }));

      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + penaltySpot, cy: y + (h / 2), r: 0.35 * scale, fill: soft }));
      drawRoot.appendChild(createSvgNode(doc, 'circle', { cx: x + w - penaltySpot, cy: y + (h / 2), r: 0.35 * scale, fill: soft }));

      // Goals (small depth outside the line).
      drawGoal(x, y + (h / 2), 2.2 * scale, 7.32 * scale, 'left');
      drawGoal(x + w, y + (h / 2), 2.2 * scale, 7.32 * scale, 'right');

      // Corner arcs (approx 1m radius).
      drawCornerArcs(x, y, w, h, 1 * scale);

      pitchBox = { x, y, width: w, height: h };
    };

    drawFullPitch();

    // data-pitch-box used by the real engine; useful if we later reuse this SVG elsewhere.
    try {
      let box = pitchBox;
      if (orientation === 'portrait') {
        box = { x: stageW - (box.y + box.height), y: box.x, width: box.height, height: box.width };
      }
      root.setAttribute('data-pitch-box', `${box.x} ${box.y} ${box.width} ${box.height}`);
    } catch (e) {
      // ignore
    }

    return new XMLSerializer().serializeToString(doc);
  };

  window.WebstatsPitchPreview = {
    buildPitchSvg,
  };
})();
