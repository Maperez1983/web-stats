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

  // Preview: we keep SVG-only grass (no canvas texture generation).
  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
    const preset = String(presetKey || 'full_pitch').trim();
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const normalizedGrass = safeText(grassStyleKey, 'classic').toLowerCase();
    const grassStyle = (['classic', 'broadcast', 'realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'whiteboard', 'blackboard'].includes(normalizedGrass))
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
      artificial: ['#2fb46d', '#1f8d55'],
      dry: ['#7b9a45', '#6b8a3a'],
      wet: ['#1f5a46', '#163f35'],
      uefa_b: ['#2f6a3a', '#245934'],
      whiteboard: ['#f8fafc', '#e5e7eb'],
      blackboard: ['#0b1220', '#030712'],
    };
    const [g0, g1] = gradientStopsByStyle[grassStyle] || gradientStopsByStyle.classic;
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '0%', 'stop-color': g0 }));
    gradient.appendChild(createSvgNode(doc, 'stop', { offset: '100%', 'stop-color': g1 }));
    defs.appendChild(gradient);
    let grassFillId = 'pitch-bg';
    if (grassStyle === 'uefa_b') {
      // Prefer dataURL injection if present; otherwise use same-origin static URL.
      const tileHref = (() => {
        try {
          const v = safeText(window.__WEBSTATS_GRASS_TILES && window.__WEBSTATS_GRASS_TILES.uefa_b);
          if (v && v.startsWith('data:image/')) return v;
        } catch (e) {}
        return '/static/football/images/surfaces/grass_uefa_b_tile.png';
      })();
      grassFillId = 'pitch-grass-uefa-b';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 140, height: 140 });
      const image = createSvgNode(doc, 'image', { href: tileHref, x: 0, y: 0, width: 140, height: 140, preserveAspectRatio: 'xMidYMid slice' });
      pattern.appendChild(image);
      defs.appendChild(pattern);
    } else if (grassStyle === 'whiteboard') {
      grassFillId = 'pitch-whiteboard';
      const pattern = createSvgNode(doc, 'pattern', { id: grassFillId, patternUnits: 'userSpaceOnUse', width: 80, height: 80 });
      pattern.appendChild(createSvgNode(doc, 'rect', { x: 0, y: 0, width: 80, height: 80, fill: 'url(#pitch-bg)' }));
      pattern.appendChild(createSvgNode(doc, 'path', { d: 'M 0 40 L 80 40 M 40 0 L 40 80', stroke: 'rgba(15,23,42,0.08)', 'stroke-width': 1 }));
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
