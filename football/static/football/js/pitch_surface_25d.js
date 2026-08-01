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
      outer: '#7d9f45',
      frame: '#b9d46b',
      frameEdge: '#96b652',
      base: '#97bc52',
      stripeA: '#b6d36a',
      stripeB: '#92b650',
      textureLight: 'rgba(255,255,255,0.024)',
      textureDark: 'rgba(34,77,18,0.05)',
      shadow: 'rgba(22,46,12,0.1)',
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
      outer: '#5c7d38',
      frame: '#89aa55',
      frameEdge: '#678542',
      base: '#7f9f4b',
      stripeA: '#95b95b',
      stripeB: '#6d8841',
      textureLight: 'rgba(255,255,255,0.022)',
      textureDark: 'rgba(16,44,16,0.11)',
      shadow: 'rgba(6,16,9,0.18)',
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
    stadium_native: {
      outer: '#dbe4ec',
      frame: '#31583d',
      frameEdge: '#1d3223',
      base: '#236742',
      stripeA: '#3f965f',
      stripeB: '#1b5a38',
      textureLight: 'rgba(255,255,255,0.018)',
      textureDark: 'rgba(7,27,15,0.09)',
      shadow: 'rgba(4,12,8,0.24)',
    },
    natural: {
      outer: '#4d682e',
      frame: '#778f43',
      frameEdge: '#5d7234',
      base: '#5f7d39',
      stripeA: '#6c8740',
      stripeB: '#526d2e',
      textureLight: 'rgba(255,255,255,0.017)',
      textureDark: 'rgba(14,31,12,0.072)',
      shadow: 'rgba(7,16,10,0.16)',
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

  const SURFACE_THEMES = {
    default: {
      apron: '#6f9341',
      floorTop: 'rgba(237,241,244,0.97)',
      floorBottom: 'rgba(207,214,222,0.97)',
      floorShadowTop: 'rgba(255,255,255,0.10)',
      floorShadowBottom: 'rgba(55,65,81,0.10)',
      frameTop: 'rgba(244,247,250,0.94)',
      frameBottom: 'rgba(210,217,224,0.94)',
      frameSheen: 'rgba(255,255,255,0.16)',
      rimTop: 'rgba(255,255,255,0.13)',
      rimBottom: 'rgba(0,0,0,0.05)',
      standShellTop: 'rgba(222,228,234,0.94)',
      standShellBottom: 'rgba(172,181,191,0.90)',
      standSeatsTop: 'rgba(78,87,98,0.94)',
      standSeatsBottom: 'rgba(45,53,64,0.94)',
      vignetteOuter: 'rgba(22,34,20,0.10)',
      adShellTop: 'rgba(34,39,46,0.84)',
      adShellBottom: 'rgba(15,18,22,0.96)',
      adGlow: 'rgba(180,216,255,0.11)',
      grassNoiseOpacity: 0.28,
      grassFiberOpacity: 0.12,
      grassStripeEven: 0.72,
      grassStripeOdd: 0.62,
      mowLineOpacity: 0.018,
      focusOpacity: 0.08,
      topLightOpacity: 0.015,
      bottomShadeOpacity: 0.015,
      fieldSheenOpacity: 0.16,
      fieldEdgeVignetteOpacity: 0.16,
    },
    premium: {
      apron: '#617f38',
      floorTop: 'rgba(242,245,248,0.98)',
      floorBottom: 'rgba(212,219,226,0.98)',
      floorShadowTop: 'rgba(255,255,255,0.11)',
      floorShadowBottom: 'rgba(31,41,55,0.08)',
      frameTop: 'rgba(247,249,251,0.95)',
      frameBottom: 'rgba(214,220,226,0.95)',
      frameSheen: 'rgba(255,255,255,0.18)',
      rimTop: 'rgba(255,255,255,0.15)',
      rimBottom: 'rgba(0,0,0,0.04)',
      standShellTop: 'rgba(226,232,238,0.95)',
      standShellBottom: 'rgba(176,186,196,0.92)',
      standSeatsTop: 'rgba(70,79,91,0.96)',
      standSeatsBottom: 'rgba(40,48,58,0.96)',
      vignetteOuter: 'rgba(15,23,42,0.08)',
      adShellTop: 'rgba(28,33,39,0.90)',
      adShellBottom: 'rgba(9,12,16,0.98)',
      adGlow: 'rgba(172,220,255,0.09)',
      grassNoiseOpacity: 0.18,
      grassFiberOpacity: 0.08,
      grassStripeEven: 0.62,
      grassStripeOdd: 0.54,
      mowLineOpacity: 0.012,
      focusOpacity: 0.045,
      topLightOpacity: 0.010,
      bottomShadeOpacity: 0.012,
      fieldSheenOpacity: 0.12,
      fieldEdgeVignetteOpacity: 0.20,
    },
    whiteboard: {
      apron: '#dde5ea',
      floorTop: 'rgba(250,252,253,0.99)',
      floorBottom: 'rgba(229,235,240,0.99)',
      floorShadowTop: 'rgba(255,255,255,0.05)',
      floorShadowBottom: 'rgba(148,163,184,0.08)',
      frameTop: 'rgba(247,250,252,0.94)',
      frameBottom: 'rgba(229,235,240,0.94)',
      frameSheen: 'rgba(255,255,255,0.10)',
      rimTop: 'rgba(255,255,255,0.08)',
      rimBottom: 'rgba(15,23,42,0.03)',
      standShellTop: 'rgba(236,240,244,0.94)',
      standShellBottom: 'rgba(210,217,224,0.94)',
      standSeatsTop: 'rgba(203,213,225,0.85)',
      standSeatsBottom: 'rgba(181,191,203,0.90)',
      vignetteOuter: 'rgba(148,163,184,0.06)',
      adShellTop: 'rgba(220,226,232,0.90)',
      adShellBottom: 'rgba(198,206,214,0.95)',
      adGlow: 'rgba(148,163,184,0.05)',
      grassNoiseOpacity: 0.10,
      grassFiberOpacity: 0.04,
      grassStripeEven: 0.35,
      grassStripeOdd: 0.28,
      mowLineOpacity: 0.010,
      focusOpacity: 0.020,
      topLightOpacity: 0.008,
      bottomShadeOpacity: 0.008,
      fieldSheenOpacity: 0.08,
      fieldEdgeVignetteOpacity: 0.10,
    },
    blackboard: {
      apron: '#0f1724',
      floorTop: 'rgba(26,35,49,0.98)',
      floorBottom: 'rgba(15,23,36,0.98)',
      floorShadowTop: 'rgba(255,255,255,0.03)',
      floorShadowBottom: 'rgba(0,0,0,0.10)',
      frameTop: 'rgba(25,35,50,0.94)',
      frameBottom: 'rgba(14,20,31,0.96)',
      frameSheen: 'rgba(255,255,255,0.06)',
      rimTop: 'rgba(255,255,255,0.06)',
      rimBottom: 'rgba(0,0,0,0.08)',
      standShellTop: 'rgba(35,45,60,0.94)',
      standShellBottom: 'rgba(18,25,36,0.94)',
      standSeatsTop: 'rgba(25,34,46,0.96)',
      standSeatsBottom: 'rgba(9,14,22,0.96)',
      vignetteOuter: 'rgba(0,0,0,0.18)',
      adShellTop: 'rgba(32,39,48,0.92)',
      adShellBottom: 'rgba(11,16,22,0.98)',
      adGlow: 'rgba(148,163,184,0.05)',
      grassNoiseOpacity: 0.14,
      grassFiberOpacity: 0.05,
      grassStripeEven: 0.42,
      grassStripeOdd: 0.34,
      mowLineOpacity: 0.012,
      focusOpacity: 0.030,
      topLightOpacity: 0.008,
      bottomShadeOpacity: 0.010,
      fieldSheenOpacity: 0.07,
      fieldEdgeVignetteOpacity: 0.12,
    },
  };

  const resolveSurfaceTheme = (grassKey) => {
    if (grassKey === 'broadcast_premium') return SURFACE_THEMES.premium;
    if (grassKey === 'whiteboard') return SURFACE_THEMES.whiteboard;
    if (grassKey === 'blackboard' || grassKey === 'coachboard') return SURFACE_THEMES.blackboard;
    return SURFACE_THEMES.default;
  };

  const buildRect = (x, y, width, height, radius, fill, extra = '') =>
    `<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${radius}" ry="${radius}" fill="${fill}" ${extra}/>`;

  const buildLine = (x1, y1, x2, y2, stroke, strokeWidth, extra = '') =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${stroke}" stroke-width="${strokeWidth}" ${extra}/>`;

  const buildCircle = (cx, cy, r, stroke, strokeWidth, fill = 'none', extra = '') =>
    `<circle cx="${cx}" cy="${cy}" r="${r}" stroke="${stroke}" stroke-width="${strokeWidth}" fill="${fill}" ${extra}/>`;

  const buildArcPath = (x1, y1, x2, y2, rx, ry, sweep) =>
    `M ${x1} ${y1} A ${rx} ${ry} 0 0 ${sweep} ${x2} ${y2}`;

  const NATIVE_STADIUM_SCENE = { sceneW: 2636, sceneH: 1318 };

  const NATIVE_STADIUM_FIELD_BOX = {
    landscape: { x: 0.268, y: 0.22, w: 0.462, h: 0.56 },
    portrait: { x: 0.3558, y: 0.0683, w: 0.2883, h: 0.8771 },
  };

  const AD_PRESETS = {
    mixed: {
      label: 'Mixto premium',
      assets: [
        '/static/football/images/kit_logos/grupo_modernia_white.png',
        '/static/football/images/kit_logos/nike_swoosh.png',
        '/static/football/images/uefa-badge.svg',
        '/static/football/images/kit_logos/benagalbon_crest_alpha.png',
      ],
    },
    modernia: {
      label: 'Club + partner',
      assets: [
        '/static/football/images/kit_logos/grupo_modernia_white.png',
        '/static/football/images/kit_logos/benagalbon_crest_alpha.png',
        '/static/football/images/kit_logos/grupo_modernia_black_alpha.png',
        '/static/football/images/2j-mark.svg',
      ],
    },
    performance: {
      label: 'Rendimiento',
      assets: [
        '/static/football/images/kit_logos/nike_swoosh.png',
        '/static/football/images/uefa-badge.svg',
        '/static/football/images/2j-mark.svg',
        '/static/football/images/kit_logos/nike_swoosh.png',
      ],
    },
    competition: {
      label: 'Competición',
      assets: [
        '/static/football/images/uefa-badge.svg',
        '/static/football/images/2j-mark.svg',
        '/static/football/images/kit_logos/benagalbon_crest_alpha.png',
        '/static/football/images/kit_logos/grupo_modernia_white.png',
      ],
    },
  };

  const normalizeAdPreset = (value) => {
    const key = safeText(value, 'mixed').toLowerCase();
    return Object.prototype.hasOwnProperty.call(AD_PRESETS, key) ? key : 'mixed';
  };

  const resolveSurfaceIdentity = () => {
    let clubName = 'SEGUNDA JUGADA';
    let venueName = 'CAMPO PRINCIPAL';
    let crest = '/static/football/images/kit_logos/benagalbon_crest_alpha.png';
    try {
      const form = document.getElementById('task-builder-form');
      const navName = safeText(document.querySelector('.nav-context-name')?.textContent || '');
      clubName = safeText(form?.dataset?.stadiumClubName || form?.dataset?.stadiumTeamName || navName || clubName).toUpperCase();
      venueName = safeText(form?.dataset?.stadiumVenueName || form?.dataset?.stadiumFieldName || venueName).toUpperCase();
      crest = safeText(form?.dataset?.pitch3dBenagalbonCrestSrc || crest);
    } catch (e) { /* ignore */ }
    return { clubName, venueName, crest };
  };

  const resolveAdAssets = () => {
    try {
      const custom = Array.isArray(window.__WEBSTATS_PITCH25D_AD_ASSETS) ? window.__WEBSTATS_PITCH25D_AD_ASSETS : null;
      if (custom && custom.length) {
        return custom.map((item) => safeText(item)).filter(Boolean);
      }
    } catch (e) { /* ignore */ }
    const preset = normalizeAdPreset(window.__WEBSTATS_PITCH25D_AD_PRESET);
    return AD_PRESETS[preset].assets.slice();
  };

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

  const computePitchRectWithinBounds = (presetKey, bounds) => {
    const preset = PRESET_METRICS[presetKey] || PRESET_METRICS.full_pitch;
    if (preset.mode === 'full' || preset.mode === 'blank') {
      return {
        x: bounds.x,
        y: bounds.y,
        w: bounds.w,
        h: bounds.h,
        metrics: preset,
      };
    }
    const aspect = preset.width / preset.height;
    let pitchW = bounds.w;
    let pitchH = pitchW / aspect;
    if (pitchH > bounds.h) {
      pitchH = bounds.h;
      pitchW = pitchH * aspect;
    }
    if (preset.mode === 'futsal') pitchH = Math.min(pitchH, bounds.h * 0.88);
    return {
      x: bounds.x + ((bounds.w - pitchW) / 2),
      y: bounds.y + ((bounds.h - pitchH) / 2),
      w: pitchW,
      h: pitchH,
      metrics: preset,
    };
  };

  const scaleNativeBounds = (orientation, scene) => {
    const ratios = NATIVE_STADIUM_FIELD_BOX[orientation] || NATIVE_STADIUM_FIELD_BOX.landscape;
    return {
      x: scene.sceneW * ratios.x,
      y: scene.sceneH * ratios.y,
      w: scene.sceneW * ratios.w,
      h: scene.sceneH * ratios.h,
    };
  };

  const resolvePitch3dTopImageHref = (orientation) => {
    const usePortrait = orientation === 'portrait';
    const premiumFallback = usePortrait
      ? '/static/football/images/pitch3d/stadium_rosaleda_top_v.png'
      : '/static/football/images/pitch3d/stadium_rosaleda_top_h.png';
    try {
      const globalImages = window.__WEBSTATS_PITCH3D_TOP_IMAGES || {};
      const preferred = usePortrait ? safeText(globalImages.v) : safeText(globalImages.h);
      if (preferred) return preferred;
    } catch (e) { /* ignore */ }
    try {
      const form = document.getElementById('task-builder-form');
      const preferred = usePortrait
        ? safeText(form?.dataset?.pitch3dStadiumTopVSrc)
        : safeText(form?.dataset?.pitch3dStadiumTopHSrc);
      if (preferred && preferred.includes('rosaleda_top_')) return preferred;
    } catch (e) { /* ignore */ }
    return premiumFallback;
  };

  const resolveGrassTextureHref = () => {
    const isCompactLab = typeof document !== 'undefined' && document.body && document.body.classList.contains('editor-lab-compact');
    try {
      const form = document.getElementById('task-builder-form');
      const custom = safeText(form?.dataset?.pitch3dGrassPremiumAlbedoSrc);
      if (custom) return isCompactLab
        ? custom.replace('grass_premium_albedo.png', 'grass_reference_tile_clean.png')
        : custom;
    } catch (e) { /* ignore */ }
    return isCompactLab
      ? '/static/football/images/pitch3d/grass_reference_tile_clean.png'
      : '/static/football/images/pitch3d/grass_premium_albedo.png';
  };

  const resolveGrassGrainHref = () => {
    const isCompactLab = typeof document !== 'undefined' && document.body && document.body.classList.contains('editor-lab-compact');
    if (!isCompactLab) return '';
    try {
      const form = document.getElementById('task-builder-form');
      const custom = safeText(form?.dataset?.pitch3dGrassPremiumAlbedoSrc);
      if (custom) return custom.replace('grass_premium_albedo.png', '');
    } catch (e) { /* ignore */ }
    return '';
  };

  const buildDefs = (idPrefix, pitch, grass, theme) => `
    <defs>
      <linearGradient id="${idPrefix}-backdrop" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.floorTop}"/>
        <stop offset="100%" stop-color="${theme.floorBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-frame" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.frameTop}"/>
        <stop offset="100%" stop-color="${theme.frameBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-frame-sheen" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.frameSheen}"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
      </linearGradient>
      <radialGradient id="${idPrefix}-scene-vignette" cx="50%" cy="48%" r="72%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.04)"/>
        <stop offset="62%" stop-color="rgba(255,255,255,0.015)"/>
        <stop offset="100%" stop-color="${theme.vignetteOuter}"/>
      </radialGradient>
      <linearGradient id="${idPrefix}-stadium-floor" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.floorTop}"/>
        <stop offset="100%" stop-color="${theme.floorBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-stadium-floor-shadow" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${theme.floorShadowTop}"/>
        <stop offset="100%" stop-color="${theme.floorShadowBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-pitch-rim" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.rimTop}"/>
        <stop offset="100%" stop-color="${theme.rimBottom}"/>
      </linearGradient>
      <clipPath id="${idPrefix}-pitch-clip">
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18"/>
      </clipPath>
      <pattern id="${idPrefix}-grass-noise" width="144" height="144" patternUnits="userSpaceOnUse">
        <path d="M 20 132 L 44 20 M 70 136 L 92 26 M 104 128 L 128 18" stroke="${grass.textureLight}" stroke-width="1.5" stroke-linecap="round"/>
        <path d="M 26 110 L 34 92 M 82 86 L 90 68 M 116 108 L 124 90 M 98 46 L 106 28" stroke="${grass.textureDark}" stroke-width="0.9" stroke-linecap="round"/>
      </pattern>
      <pattern id="${idPrefix}-grass-fibers" width="120" height="120" patternUnits="userSpaceOnUse">
        <path d="M 10 108 L 18 90 M 40 104 L 48 80 M 72 114 L 80 92 M 96 56 L 104 34" stroke="rgba(255,255,255,0.018)" stroke-width="0.9" stroke-linecap="round"/>
        <path d="M 22 28 L 30 8 M 60 70 L 68 48 M 108 112 L 116 90" stroke="rgba(17,46,10,0.035)" stroke-width="0.8" stroke-linecap="round"/>
      </pattern>
      <pattern id="${idPrefix}-goal-net" width="14" height="14" patternUnits="userSpaceOnUse">
        <path d="M 0 0 L 14 14 M 14 0 L 0 14" stroke="rgba(236,242,247,0.7)" stroke-width="0.9"/>
      </pattern>
      <linearGradient id="${idPrefix}-goal-post" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="100%" stop-color="#dee6ed"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-goal-side" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#dfe7ee"/>
        <stop offset="100%" stop-color="#a9b8c6"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-goal-net-shade" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.28)"/>
        <stop offset="100%" stop-color="rgba(148,163,184,0.08)"/>
      </linearGradient>
      <radialGradient id="${idPrefix}-pitch-light" cx="50%" cy="48%" r="66%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.045)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
      </radialGradient>
      <radialGradient id="${idPrefix}-field-edge-vignette" cx="50%" cy="50%" r="74%">
        <stop offset="56%" stop-color="rgba(0,0,0,0)"/>
        <stop offset="100%" stop-color="rgba(6,16,12,0.16)"/>
      </radialGradient>
      <linearGradient id="${idPrefix}-pitch-sheen" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.012)"/>
        <stop offset="35%" stop-color="rgba(255,255,255,0)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.014)"/>
      </linearGradient>
      <filter id="${idPrefix}-field-shadow" x="-15%" y="-15%" width="130%" height="130%">
        <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="rgba(8,20,8,0.14)"/>
      </filter>
      <filter id="${idPrefix}-goal-shadow" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="rgba(11,20,33,0.16)"/>
      </filter>
      <filter id="${idPrefix}-stadium-depth" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="rgba(15,23,42,0.12)"/>
      </filter>
      <pattern id="${idPrefix}-seat-rows" width="12" height="12" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="12" height="12" fill="rgba(78,87,96,0.14)"/>
        <path d="M 0 3 L 12 3 M 0 9 L 12 9" stroke="rgba(255,255,255,0.09)" stroke-width="0.85"/>
        <circle cx="3" cy="6" r="0.85" fill="rgba(240,244,248,0.18)"/>
        <circle cx="9" cy="6" r="0.85" fill="rgba(240,244,248,0.12)"/>
      </pattern>
      <pattern id="${idPrefix}-concourse-grid" width="28" height="28" patternUnits="userSpaceOnUse">
        <rect x="0" y="0" width="28" height="28" fill="rgba(180,190,199,0.04)"/>
        <path d="M 0 0 L 28 0 M 0 14 L 28 14 M 0 28 L 28 28 M 0 0 L 0 28 M 14 0 L 14 28 M 28 0 L 28 28" stroke="rgba(255,255,255,0.08)" stroke-width="0.7"/>
      </pattern>
      <linearGradient id="${idPrefix}-stand-shell" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.standShellTop}"/>
        <stop offset="100%" stop-color="${theme.standShellBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-stand-seats" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.standSeatsTop}"/>
        <stop offset="100%" stop-color="${theme.standSeatsBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-ad-shell-h" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${theme.adShellTop}"/>
        <stop offset="100%" stop-color="${theme.adShellBottom}"/>
      </linearGradient>
      <linearGradient id="${idPrefix}-ad-shell-v" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="${theme.adShellTop}"/>
        <stop offset="100%" stop-color="${theme.adShellBottom}"/>
      </linearGradient>
      <filter id="${idPrefix}-ad-glow" x="-20%" y="-80%" width="140%" height="260%">
        <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="${theme.adGlow}"/>
      </filter>
    </defs>
  `;

  const buildBackdrop = (scene, pitch, theme) => {
    const frameInset = 12;
    const isPresentationSurface = (() => {
      try { return !!document.body?.classList?.contains?.('focus-mode'); } catch (e) { return false; }
    })();
    if (!isPresentationSurface) {
      return `
        <g id="surface-base">
          <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="${theme.apron}"/>
          <rect x="${pitch.x - 26}" y="${pitch.y - 26}" width="${pitch.w + 52}" height="${pitch.h + 52}" rx="34" ry="34" fill="rgba(255,255,255,0.03)"/>
          <rect x="${pitch.x - 14}" y="${pitch.y - 14}" width="${pitch.w + 28}" height="${pitch.h + 28}" rx="24" ry="24" fill="rgba(8,18,12,0.22)"/>
          <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="url(#${pitch.idPrefix}-scene-vignette)"/>
          <rect x="${pitch.x - 2}" y="${pitch.y - 2}" width="${pitch.w + 4}" height="${pitch.h + 4}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-pitch-rim)" opacity="0.10"/>
        </g>
      `;
    }
    return `
      <g id="surface-base">
        <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="${theme.apron}"/>
        <rect x="34" y="26" width="${scene.sceneW - 68}" height="${scene.sceneH - 52}" rx="86" ry="86" fill="url(#${pitch.idPrefix}-stadium-floor)"/>
        <rect x="34" y="26" width="${scene.sceneW - 68}" height="${scene.sceneH - 52}" rx="86" ry="86" fill="url(#${pitch.idPrefix}-stadium-floor-shadow)"/>
        <path d="M 52 90 L 220 90 L 120 190 L 52 258 Z" fill="rgba(255,255,255,0.10)"/>
        <path d="M ${scene.sceneW - 52} 90 L ${scene.sceneW - 220} 90 L ${scene.sceneW - 120} 190 L ${scene.sceneW - 52} 258 Z" fill="rgba(255,255,255,0.10)"/>
        <path d="M 52 ${scene.sceneH - 90} L 220 ${scene.sceneH - 90} L 120 ${scene.sceneH - 190} L 52 ${scene.sceneH - 258} Z" fill="rgba(0,0,0,0.05)"/>
        <path d="M ${scene.sceneW - 52} ${scene.sceneH - 90} L ${scene.sceneW - 220} ${scene.sceneH - 90} L ${scene.sceneW - 120} ${scene.sceneH - 190} L ${scene.sceneW - 52} ${scene.sceneH - 258} Z" fill="rgba(0,0,0,0.05)"/>
        <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="url(#${pitch.idPrefix}-scene-vignette)"/>
        <rect x="${pitch.x - frameInset}" y="${pitch.y - frameInset}" width="${pitch.w + frameInset * 2}" height="${pitch.h + frameInset * 2}" rx="26" ry="26" fill="url(#${pitch.idPrefix}-frame)"/>
        <rect x="${pitch.x - frameInset}" y="${pitch.y - frameInset}" width="${pitch.w + frameInset * 2}" height="${pitch.h + frameInset * 2}" rx="26" ry="26" fill="url(#${pitch.idPrefix}-frame-sheen)" opacity="0.18"/>
        <rect x="${pitch.x - 6}" y="${pitch.y - 6}" width="${pitch.w + 12}" height="${pitch.h + 12}" rx="20" ry="20" fill="none" stroke="rgba(255,255,255,0.16)" stroke-width="0.9"/>
        <rect x="${pitch.x - 2}" y="${pitch.y - 2}" width="${pitch.w + 4}" height="${pitch.h + 4}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-pitch-rim)" opacity="0.18"/>
        <rect x="${pitch.x - 1}" y="${pitch.y - 1}" width="${pitch.w + 2}" height="${pitch.h + 2}" rx="18" ry="18" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.8"/>
      </g>
    `;
  };

  const buildAdBoards = (pitch, idPrefix, theme) => {
    const adGap = 14;
    const thickness = 24;
    const sideThickness = 28;
    const topY = pitch.y - adGap - thickness;
    const bottomY = pitch.y + pitch.h + adGap;
    const leftX = pitch.x - adGap - sideThickness;
    const rightX = pitch.x + pitch.w + adGap;
    const adAssets = resolveAdAssets();
    const horizontalBlocks = [];
    const verticalBlocks = [];
    const hCount = 4;
    const vCount = 2;
    const hW = pitch.w / hCount;
    const goalGap = pitch.h * 0.23;
    const sideSegmentH = (pitch.h - goalGap - 16) / 2;
    const topSegmentY = pitch.y + 8;
    const bottomSegmentY = pitch.y + pitch.h - sideSegmentH - 8;
    const buildAdImage = (href, x, y, width, height, opacity = 0.96) => (
      `<image href="${href}" x="${x}" y="${y}" width="${width}" height="${height}" preserveAspectRatio="xMidYMid meet" opacity="${opacity}"/>`
    );
    for (let i = 0; i < hCount; i += 1) {
      const href = adAssets[i % adAssets.length];
      const x = pitch.x + (i * hW) + 0.8;
      const yTop = topY + 1.35;
      const yBottom = bottomY + 1.35;
      const width = Math.max(8, hW - 1.6);
      const height = thickness - 2.7;
      horizontalBlocks.push(`<rect x="${x}" y="${yTop}" width="${width}" height="${height}" rx="2" ry="2" fill="rgba(12,18,24,0.92)"/>`);
      horizontalBlocks.push(`<rect x="${x}" y="${yBottom}" width="${width}" height="${height}" rx="2" ry="2" fill="rgba(12,18,24,0.92)"/>`);
      horizontalBlocks.push(buildAdImage(href, x + 0.8, yTop + 0.45, Math.max(5, width - 1.6), Math.max(4, height - 0.9), 0.96));
      horizontalBlocks.push(buildAdImage(href, x + 0.8, yBottom + 0.45, Math.max(5, width - 1.6), Math.max(4, height - 0.9), 0.96));
    }
    const sideSegments = [
      { y: topSegmentY, h: sideSegmentH, assetOffset: 1 },
      { y: bottomSegmentY, h: sideSegmentH, assetOffset: 2 },
    ];
    for (let i = 0; i < vCount; i += 1) {
      const segment = sideSegments[i];
      const href = adAssets[(i + segment.assetOffset) % adAssets.length];
      const y = segment.y;
      const width = sideThickness - 2.7;
      const height = Math.max(8, segment.h);
      verticalBlocks.push(`<rect x="${leftX + 1.35}" y="${y}" width="${width}" height="${height}" rx="4" ry="4" fill="rgba(12,18,24,0.92)"/>`);
      verticalBlocks.push(`<rect x="${rightX + 1.35}" y="${y}" width="${width}" height="${height}" rx="4" ry="4" fill="rgba(12,18,24,0.92)"/>`);
      verticalBlocks.push(buildAdImage(href, leftX + 2.2, y + 3.2, Math.max(6, width - 2.8), Math.max(8, height - 6.4), 0.94));
      verticalBlocks.push(buildAdImage(href, rightX + 2.2, y + 3.2, Math.max(6, width - 2.8), Math.max(8, height - 6.4), 0.94));
    }
    return `
      <g id="ad-boards">
        <rect x="${pitch.x}" y="${topY}" width="${pitch.w}" height="${thickness}" rx="5" ry="5" fill="url(#${idPrefix}-ad-shell-h)"/>
        <rect x="${pitch.x}" y="${bottomY}" width="${pitch.w}" height="${thickness}" rx="5" ry="5" fill="url(#${idPrefix}-ad-shell-h)"/>
        <rect x="${leftX}" y="${topSegmentY - 1.35}" width="${sideThickness}" height="${sideSegmentH + 2.7}" rx="6" ry="6" fill="url(#${idPrefix}-ad-shell-v)"/>
        <rect x="${leftX}" y="${bottomSegmentY - 1.35}" width="${sideThickness}" height="${sideSegmentH + 2.7}" rx="6" ry="6" fill="url(#${idPrefix}-ad-shell-v)"/>
        <rect x="${rightX}" y="${topSegmentY - 1.35}" width="${sideThickness}" height="${sideSegmentH + 2.7}" rx="6" ry="6" fill="url(#${idPrefix}-ad-shell-v)"/>
        <rect x="${rightX}" y="${bottomSegmentY - 1.35}" width="${sideThickness}" height="${sideSegmentH + 2.7}" rx="6" ry="6" fill="url(#${idPrefix}-ad-shell-v)"/>
        <rect x="${pitch.x + 4}" y="${topY + 2.2}" width="${pitch.w - 8}" height="1.1" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${pitch.x + 4}" y="${bottomY + 2.2}" width="${pitch.w - 8}" height="1.1" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${leftX + 2.2}" y="${topSegmentY + 4}" width="1" height="${sideSegmentH - 8}" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${leftX + 2.2}" y="${bottomSegmentY + 4}" width="1" height="${sideSegmentH - 8}" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${rightX + sideThickness - 3.4}" y="${topSegmentY + 4}" width="1" height="${sideSegmentH - 8}" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${rightX + sideThickness - 3.4}" y="${bottomSegmentY + 4}" width="1" height="${sideSegmentH - 8}" rx="1" ry="1" fill="${theme.adGlow}" filter="url(#${idPrefix}-ad-glow)"/>
        <rect x="${pitch.x}" y="${topY}" width="${pitch.w}" height="1.05" fill="rgba(255,255,255,0.2)"/>
        <rect x="${pitch.x}" y="${bottomY + thickness - 1.05}" width="${pitch.w}" height="1.05" fill="rgba(255,255,255,0.08)"/>
        <rect x="${leftX}" y="${topSegmentY - 1.35}" width="1.05" height="${sideSegmentH + 2.7}" fill="rgba(255,255,255,0.16)"/>
        <rect x="${leftX}" y="${bottomSegmentY - 1.35}" width="1.05" height="${sideSegmentH + 2.7}" fill="rgba(255,255,255,0.16)"/>
        <rect x="${rightX + sideThickness - 1.05}" y="${topSegmentY - 1.35}" width="1.05" height="${sideSegmentH + 2.7}" fill="rgba(255,255,255,0.08)"/>
        <rect x="${rightX + sideThickness - 1.05}" y="${bottomSegmentY - 1.35}" width="1.05" height="${sideSegmentH + 2.7}" fill="rgba(255,255,255,0.08)"/>
        ${horizontalBlocks.join('')}
        ${verticalBlocks.join('')}
      </g>
    `;
  };

  const buildNativeAdBoards = (pitch, idPrefix, orientation = 'landscape') => {
    const adAssets = resolveAdAssets();
    const boardDepth = clamp(Math.min(pitch.w, pitch.h) * 0.032, 20, 34);
    const goalClearance = clamp(Math.min(pitch.w, pitch.h) * 0.028, 18, 30);
    const boardGap = clamp(Math.min(pitch.w, pitch.h) * 0.02, 12, 22) + goalClearance;
    const sideDepth = clamp(boardDepth * 1.08, 22, 38);
    const sideGap = boardGap + 6;
    const boardSegments = [];
    const sideSegments = [];
    const makePanel = (x, y, width, height, href, radius = 7, rotate = 0) => `
      <g>
        <rect x="${x + 1.6}" y="${y + 2.4}" width="${width}" height="${height}" rx="${radius}" ry="${radius}" fill="rgba(3,8,14,0.24)"/>
        <rect x="${x + 0.9}" y="${y + 1.2}" width="${width}" height="${height}" rx="${radius}" ry="${radius}" fill="rgba(7,12,18,0.36)"/>
        <rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${radius}" ry="${radius}" fill="url(#${idPrefix}-native-ad-shell)"/>
        <path d="M ${x + 1.2} ${y + height - 1.2} L ${x + width - 1.2} ${y + height - 1.2} L ${x + width - 3.8} ${y + height + 1.8} L ${x + 3.8} ${y + height + 1.8} Z" fill="rgba(6,10,16,0.34)"/>
        <path d="M ${x + width - 1.2} ${y + 3.8} L ${x + width - 1.2} ${y + height - 1.2} L ${x + width + 1.8} ${y + height - 3.6} L ${x + width + 1.8} ${y + 6.2} Z" fill="rgba(10,16,24,0.22)"/>
        <rect x="${x + 0.8}" y="${y + 0.8}" width="${Math.max(4, width - 1.6)}" height="${Math.max(4, height - 1.6)}" rx="${Math.max(2, radius - 1)}" ry="${Math.max(2, radius - 1)}" fill="rgba(12,18,26,0.96)"/>
        <rect x="${x + 1.8}" y="${y + 1.8}" width="${Math.max(4, width - 3.6)}" height="${Math.max(4, height - 3.6)}" rx="${Math.max(2, radius - 2)}" ry="${Math.max(2, radius - 2)}" fill="url(#${idPrefix}-native-ad-screen)"/>
        <rect x="${x + 2.2}" y="${y + 1.8}" width="${Math.max(4, width - 4.4)}" height="1.8" rx="1.2" ry="1.2" fill="rgba(255,255,255,0.30)"/>
        <rect x="${x + 2.2}" y="${y + height - 3.6}" width="${Math.max(4, width - 4.4)}" height="1.2" rx="1" ry="1" fill="rgba(148,163,184,0.16)"/>
        <rect x="${x + 2.6}" y="${y + 2.6}" width="${Math.max(4, width - 5.2)}" height="${Math.max(4, height - 5.2)}" rx="${Math.max(2, radius - 3)}" ry="${Math.max(2, radius - 3)}" fill="rgba(255,255,255,0.03)" filter="url(#${idPrefix}-native-ad-glow)"/>
        <image href="${href}" x="${x + 6}" y="${y + 4.8}" width="${Math.max(8, width - 12)}" height="${Math.max(8, height - 9.6)}" preserveAspectRatio="xMidYMid meet" opacity="0.995" transform="${rotate ? `rotate(${rotate} ${x + (width / 2)} ${y + (height / 2)})` : ''}"/>
      </g>
    `;

    const longPanelGap = pitch.w * 0.032;
    const longPanelW = (pitch.w - (longPanelGap * 3)) / 2;
    const topY = pitch.y - boardGap - boardDepth;
    const bottomY = pitch.y + pitch.h + boardGap;
    for (let i = 0; i < 2; i += 1) {
      const href = adAssets[i % adAssets.length];
      const x = pitch.x + longPanelGap + (i * (longPanelW + longPanelGap));
      boardSegments.push(makePanel(x, topY, longPanelW, boardDepth, href));
      boardSegments.push(makePanel(x, bottomY, longPanelW, boardDepth, adAssets[(i + 1) % adAssets.length]));
    }

    if (orientation === 'portrait') {
      const sidePanelH = pitch.h * 0.39;
      const sidePanelY = pitch.y + ((pitch.h - sidePanelH) / 2);
      const leftX = pitch.x - sideGap - sideDepth;
      const rightX = pitch.x + pitch.w + sideGap;
      sideSegments.push(makePanel(leftX, sidePanelY, sideDepth, sidePanelH, adAssets[2 % adAssets.length], 8, -90));
      sideSegments.push(makePanel(rightX, sidePanelY, sideDepth, sidePanelH, adAssets[3 % adAssets.length], 8, 90));
    } else {
      const clearGoalBand = pitch.h * 0.23;
      const splitGap = pitch.h * 0.07;
      const segmentH = (pitch.h - clearGoalBand - splitGap) / 2;
      const topSegmentY = pitch.y + (splitGap * 0.5);
      const bottomSegmentY = pitch.y + pitch.h - segmentH - (splitGap * 0.5);
      const leftX = pitch.x - sideGap - sideDepth;
      const rightX = pitch.x + pitch.w + sideGap;
      sideSegments.push(makePanel(leftX, topSegmentY, sideDepth, segmentH, adAssets[1 % adAssets.length], 8, -90));
      sideSegments.push(makePanel(leftX, bottomSegmentY, sideDepth, segmentH, adAssets[2 % adAssets.length], 8, -90));
      sideSegments.push(makePanel(rightX, topSegmentY, sideDepth, segmentH, adAssets[3 % adAssets.length], 8, 90));
      sideSegments.push(makePanel(rightX, bottomSegmentY, sideDepth, segmentH, adAssets[0], 8, 90));
    }

    return `
      <g id="native-ad-boards" filter="url(#${idPrefix}-native-ad-shadow)" opacity="0.98">
        ${boardSegments.join('')}
        ${sideSegments.join('')}
      </g>
    `;
  };

  const buildCornerFlags = (pitch) => {
    const inset = 6;
    const pole = 12;
    const flagW = 10;
    const flagH = 7;
    const corners = [
      { x: pitch.x + inset, y: pitch.y + inset, dirX: 1, dirY: 1 },
      { x: pitch.x + pitch.w - inset, y: pitch.y + inset, dirX: -1, dirY: 1 },
      { x: pitch.x + inset, y: pitch.y + pitch.h - inset, dirX: 1, dirY: -1 },
      { x: pitch.x + pitch.w - inset, y: pitch.y + pitch.h - inset, dirX: -1, dirY: -1 },
    ];
    return `
      <g id="corner-flags">
        ${corners.map((corner) => `
          <line x1="${corner.x}" y1="${corner.y}" x2="${corner.x}" y2="${corner.y - (pole * corner.dirY)}" stroke="rgba(245,247,250,0.95)" stroke-width="1.8" stroke-linecap="round"/>
          <path d="M ${corner.x} ${corner.y - (pole * corner.dirY)} L ${corner.x + (flagW * corner.dirX)} ${corner.y - ((pole - flagH) * corner.dirY)} L ${corner.x} ${corner.y - ((pole - (flagH * 1.7)) * corner.dirY)} Z" fill="${corner.dirY > 0 ? '#fbbf24' : '#ef4444'}" opacity="0.96"/>
        `).join('')}
      </g>
    `;
  };

  const buildBenches = (pitch) => {
    const benchW = pitch.w * 0.15;
    const benchD = 18;
    const offset = 18;
    const centerX = pitch.x + (pitch.w / 2);
    const topY = pitch.y - offset - benchD;
    const bottomY = pitch.y + pitch.h + offset;
    const shell = (cx, y, flip = false) => {
      const x = cx - (benchW / 2);
      const lipY = flip ? y : y + benchD;
      const canopyPath = flip
        ? `M ${x} ${y + benchD} Q ${cx} ${y - 5.5} ${x + benchW} ${y + benchD} L ${x + benchW - 5} ${y + benchD} Q ${cx} ${y + 2.3} ${x + 5} ${y + benchD} Z`
        : `M ${x} ${y} Q ${cx} ${y + benchD + 5.5} ${x + benchW} ${y} L ${x + benchW - 5} ${y} Q ${cx} ${y + benchD - 2.3} ${x + 5} ${y} Z`;
      return `
        <g>
          <ellipse cx="${cx}" cy="${flip ? y + 3.4 : y + benchD - 3.4}" rx="${benchW * 0.35}" ry="4.4" fill="rgba(7,16,23,0.14)"/>
          <path d="${canopyPath}" fill="rgba(223,231,238,0.96)"/>
          <path d="${canopyPath}" fill="rgba(255,255,255,0.22)" opacity="0.84"/>
          <path d="${canopyPath}" fill="none" stroke="rgba(150,166,181,0.58)" stroke-width="1.2"/>
          <rect x="${x + 9}" y="${y + 5.6}" width="${benchW - 18}" height="${benchD - 7.6}" rx="7" ry="7" fill="rgba(150,167,182,0.26)"/>
          <line x1="${x + 10}" y1="${lipY}" x2="${x + 10}" y2="${flip ? lipY + 4.8 : lipY - 4.8}" stroke="rgba(110,123,138,0.72)" stroke-width="1.35"/>
          <line x1="${x + benchW - 10}" y1="${lipY}" x2="${x + benchW - 10}" y2="${flip ? lipY + 4.8 : lipY - 4.8}" stroke="rgba(110,123,138,0.72)" stroke-width="1.35"/>
        </g>
      `;
    };
    return `
      <g id="benches">
        ${shell(centerX, topY, false)}
        ${shell(centerX, bottomY, true)}
      </g>
    `;
  };

  const buildStands = (pitch, idPrefix) => {
    const identity = resolveSurfaceIdentity();
    const outerInsetX = 100;
    const outerInsetY = 92;
    const innerInsetX = 48;
    const innerInsetY = 54;
    const outerX = pitch.x - outerInsetX;
    const outerY = pitch.y - outerInsetY;
    const outerW = pitch.w + (outerInsetX * 2);
    const outerH = pitch.h + (outerInsetY * 2);
    const seatsX = pitch.x - innerInsetX;
    const seatsY = pitch.y - innerInsetY;
    const seatsW = pitch.w + (innerInsetX * 2);
    const seatsH = pitch.h + (innerInsetY * 2);
    const concourseX = pitch.x - 22;
    const concourseY = pitch.y - 24;
    const concourseW = pitch.w + 44;
    const concourseH = pitch.h + 48;
    const sectorCountTop = 13;
    const sectorCountSide = 9;
    const sectorLinesTop = [];
    const sectorLinesBottom = [];
    const sectorLinesLeft = [];
    const sectorLinesRight = [];
    for (let i = 1; i < sectorCountTop; i += 1) {
      const x = seatsX + ((seatsW / sectorCountTop) * i);
      sectorLinesTop.push(`<line x1="${x}" y1="${seatsY + 8}" x2="${x}" y2="${pitch.y - 22}" stroke="rgba(232,237,243,0.36)" stroke-width="2.2"/>`);
      sectorLinesBottom.push(`<line x1="${x}" y1="${pitch.y + pitch.h + 22}" x2="${x}" y2="${seatsY + seatsH - 8}" stroke="rgba(232,237,243,0.26)" stroke-width="2"/>`);
    }
    for (let i = 1; i < sectorCountSide; i += 1) {
      const y = seatsY + ((seatsH / sectorCountSide) * i);
      sectorLinesLeft.push(`<line x1="${seatsX + 10}" y1="${y}" x2="${pitch.x - 24}" y2="${y}" stroke="rgba(232,237,243,0.24)" stroke-width="1.8"/>`);
      sectorLinesRight.push(`<line x1="${pitch.x + pitch.w + 24}" y1="${y}" x2="${seatsX + seatsW - 10}" y2="${y}" stroke="rgba(232,237,243,0.24)" stroke-width="1.8"/>`);
    }
    const fasciaW = pitch.w * 0.40;
    const fasciaH = 20;
    const fasciaX = pitch.x + ((pitch.w - fasciaW) / 2);
    const topFasciaY = outerY + 16;
    const bottomFasciaY = outerY + outerH - 36;
    const crestSize = 16;
    return `
      <g id="stands" opacity="0.9">
        <rect x="${outerX}" y="${outerY}" width="${outerW}" height="${outerH}" rx="146" ry="146" fill="url(#${idPrefix}-stand-shell)" filter="url(#${idPrefix}-stadium-depth)"/>
        <rect x="${outerX + 9}" y="${outerY + 9}" width="${outerW - 18}" height="${outerH - 18}" rx="136" ry="136" fill="rgba(244,247,250,0.74)"/>
        <rect x="${seatsX}" y="${seatsY}" width="${seatsW}" height="${seatsH}" rx="92" ry="92" fill="url(#${idPrefix}-stand-seats)"/>
        <rect x="${seatsX}" y="${seatsY}" width="${seatsW}" height="${seatsH}" rx="92" ry="92" fill="url(#${idPrefix}-seat-rows)" opacity="0.58"/>
        <rect x="${concourseX}" y="${concourseY}" width="${concourseW}" height="${concourseH}" rx="30" ry="30" fill="rgba(211,218,225,0.86)"/>
        <rect x="${concourseX}" y="${concourseY}" width="${concourseW}" height="${concourseH}" rx="30" ry="30" fill="url(#${idPrefix}-concourse-grid)" opacity="0.5"/>
        <rect x="${concourseX}" y="${concourseY}" width="${concourseW}" height="${concourseH}" rx="20" ry="20" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="1.2"/>
        <ellipse cx="${pitch.x + pitch.w / 2}" cy="${pitch.y + pitch.h / 2}" rx="${pitch.w * 0.66}" ry="${pitch.h * 0.58}" fill="none" stroke="rgba(0,0,0,0.08)" stroke-width="26" opacity="0.34"/>
        <ellipse cx="${pitch.x + pitch.w / 2}" cy="${pitch.y + pitch.h / 2}" rx="${pitch.w * 0.655}" ry="${pitch.h * 0.575}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="6" opacity="0.42"/>
        ${sectorLinesTop.join('')}
        ${sectorLinesBottom.join('')}
        ${sectorLinesLeft.join('')}
        ${sectorLinesRight.join('')}
        <rect x="${pitch.x + pitch.w * 0.08}" y="${concourseY + 6}" width="${pitch.w * 0.12}" height="6" rx="3" ry="3" fill="rgba(88,101,242,0.10)"/>
        <rect x="${pitch.x + pitch.w * 0.80}" y="${concourseY + 6}" width="${pitch.w * 0.12}" height="6" rx="3" ry="3" fill="rgba(88,101,242,0.10)"/>
        <rect x="${pitch.x + pitch.w * 0.08}" y="${concourseY + concourseH - 12}" width="${pitch.w * 0.12}" height="6" rx="3" ry="3" fill="rgba(88,101,242,0.08)"/>
        <rect x="${pitch.x + pitch.w * 0.80}" y="${concourseY + concourseH - 12}" width="${pitch.w * 0.12}" height="6" rx="3" ry="3" fill="rgba(88,101,242,0.08)"/>
        <g id="stadium-identity-top">
          <rect x="${fasciaX}" y="${topFasciaY}" width="${fasciaW}" height="${fasciaH}" rx="10" ry="10" fill="rgba(15,23,32,0.84)"/>
          <rect x="${fasciaX + 1}" y="${topFasciaY + 1}" width="${fasciaW - 2}" height="${fasciaH - 2}" rx="9" ry="9" fill="rgba(28,39,51,0.42)"/>
          <image href="${identity.crest}" x="${fasciaX + 12}" y="${topFasciaY + 2}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.98"/>
          <text x="${fasciaX + fasciaW / 2}" y="${topFasciaY + 13.8}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10.8" font-weight="700" fill="rgba(248,250,252,0.96)" letter-spacing="1.3">${identity.clubName}</text>
        </g>
        <g id="stadium-identity-bottom">
          <rect x="${fasciaX}" y="${bottomFasciaY}" width="${fasciaW}" height="${fasciaH}" rx="10" ry="10" fill="rgba(15,23,32,0.84)"/>
          <rect x="${fasciaX + 1}" y="${bottomFasciaY + 1}" width="${fasciaW - 2}" height="${fasciaH - 2}" rx="9" ry="9" fill="rgba(28,39,51,0.42)"/>
          <image href="${identity.crest}" x="${fasciaX + 12}" y="${bottomFasciaY + 2}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.98"/>
          <text x="${fasciaX + fasciaW / 2}" y="${bottomFasciaY + 13.8}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10.8" font-weight="700" fill="rgba(248,250,252,0.96)" letter-spacing="1.3">${identity.venueName}</text>
        </g>
      </g>
    `;
  };

  const buildGrassLayer = (pitch, grass, theme, grassTextureSrc = '') => {
    const stripes = [];
    const blades = [];
    const compactBlades = [];
    const compactGrainSrc = resolveGrassGrainHref();
    const stripeCount = 8;
    const stripeWidth = pitch.w / stripeCount;
    const isCompactLab = typeof document !== 'undefined' && document.body && document.body.classList.contains('editor-lab-compact');
    const useSyntheticBands = !isCompactLab;
    const grassNoiseOpacity = isCompactLab ? 0.0 : theme.grassNoiseOpacity;
    const grassFiberOpacity = isCompactLab ? 0.0 : theme.grassFiberOpacity;
    const grassTextureOpacity = isCompactLab ? 1.0 : 0.88;
    let seed = Math.round((pitch.x + pitch.y + pitch.w + pitch.h) * 1000) >>> 0;
    const rand = () => {
      seed = (1664525 * seed + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    if (useSyntheticBands) {
      for (let i = 0; i < stripeCount; i += 1) {
        stripes.push(buildRect(
          pitch.x + (i * stripeWidth),
          pitch.y,
          stripeWidth + 1,
          pitch.h,
          0,
          i % 2 === 0 ? grass.stripeA : grass.stripeB,
          `opacity="${i % 2 === 0 ? Math.min(0.022, theme.grassStripeEven) : Math.min(0.016, theme.grassStripeOdd)}"`
        ));
      }
      for (let i = 0; i < 220; i += 1) {
        const x = pitch.x + (rand() * pitch.w);
        const y = pitch.y + (rand() * pitch.h);
        const len = 4.8 + (rand() * 8.2);
        const slant = ((rand() - 0.5) * 2.4);
        const hue = rand();
        const opacity = 0.05 + (rand() * 0.06);
        const green = hue > 0.55 ? 'rgba(220,255,220,' : 'rgba(7,33,13,';
        blades.push(`<line x1="${x.toFixed(2)}" y1="${y.toFixed(2)}" x2="${(x + slant).toFixed(2)}" y2="${(y + len).toFixed(2)}" stroke="${green}${opacity.toFixed(3)})" stroke-linecap="round" stroke-width="${(0.5 + rand() * 0.55).toFixed(2)}"/>`);
      }
    }
    const mowLines = [];
    if (useSyntheticBands) {
      for (let i = 1; i < 6; i += 1) {
        const y = pitch.y + ((pitch.h / 7) * i);
        mowLines.push(buildLine(pitch.x + 12, y, pitch.x + pitch.w - 12, y, `rgba(255,255,255,${Math.min(theme.mowLineOpacity * 0.8, 0.016)})`, 0.7));
      }
    }
    return `
      <g clip-path="url(#${pitch.idPrefix}-pitch-clip)">
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="${grass.outer}" filter="url(#${pitch.idPrefix}-field-shadow)"/>
        ${grassTextureSrc ? `<image href="${grassTextureSrc}" x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" preserveAspectRatio="xMidYMid slice" opacity="${grassTextureOpacity}" style="mix-blend-mode:normal; filter: saturate(1.01) brightness(1.01) contrast(0.97);"/>` : `<rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="${grass.base}" opacity="0.97"/>`}
        ${stripes.join('')}
        ${blades.join('')}
        ${compactBlades.join('')}
        ${mowLines.join('')}
        ${grassTextureSrc ? `<image href="${grassTextureSrc}" x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" preserveAspectRatio="xMidYMid slice" opacity="${Math.max(0.02, Math.min(0.045, theme.grassNoiseOpacity * 0.24))}" style="mix-blend-mode:normal; filter: saturate(1.04) brightness(1.02) contrast(0.98);"/>` : ''}
        ${compactGrainSrc ? `<image href="${compactGrainSrc}" x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" preserveAspectRatio="xMidYMid slice" opacity="0" style="mix-blend-mode:multiply; filter: blur(0.08px) saturate(1.0) contrast(1.0);"/>` : ''}
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-grass-noise)" opacity="${grassNoiseOpacity}"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-grass-fibers)" opacity="${Math.min(grassFiberOpacity * 0.82, 0.08)}"/>
        <ellipse cx="${pitch.x + pitch.w * 0.5}" cy="${pitch.y + pitch.h * 0.5}" rx="${pitch.w * 0.43}" ry="${pitch.h * 0.34}" fill="url(#${pitch.idPrefix}-pitch-light)"/>
        <ellipse cx="${pitch.x + pitch.w * 0.5}" cy="${pitch.y + pitch.h * 0.18}" rx="${pitch.w * 0.44}" ry="${pitch.h * 0.15}" fill="rgba(255,255,255,${Math.min(theme.topLightOpacity * 0.75, 0.012)})"/>
        <ellipse cx="${pitch.x + pitch.w * 0.5}" cy="${pitch.y + pitch.h * 0.82}" rx="${pitch.w * 0.44}" ry="${pitch.h * 0.15}" fill="rgba(0,0,0,${Math.min(theme.bottomShadeOpacity * 1.1, 0.024)})"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-pitch-sheen)" opacity="${Math.min(theme.fieldSheenOpacity * 0.62, 0.1)}"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="18" ry="18" fill="url(#${pitch.idPrefix}-field-edge-vignette)" opacity="${Math.min(theme.fieldEdgeVignetteOpacity * 0.78, 0.12)}"/>
      </g>
    `;
  };

  const buildEliteGrassLayer = (pitch, idPrefix, grassTextureSrc) => {
    const stripeCount = 12;
    const stripeWidth = pitch.w / stripeCount;
    const stripes = [];
    const mowLines = [];
    const fiberLines = [];
    for (let i = 0; i < stripeCount; i += 1) {
      const x = pitch.x + (i * stripeWidth);
      const fill = i % 2 === 0 ? '#63b06f' : '#478f58';
      stripes.push(`<rect x="${x}" y="${pitch.y}" width="${stripeWidth + 0.75}" height="${pitch.h}" fill="${fill}" opacity="${i % 2 === 0 ? '0.97' : '0.92'}"/>`);
    }
    for (let i = 1; i < 9; i += 1) {
      const y = pitch.y + ((pitch.h / 9) * i);
      mowLines.push(`<line x1="${pitch.x + 10}" y1="${y}" x2="${pitch.x + pitch.w - 10}" y2="${y}" stroke="rgba(255,255,255,0.038)" stroke-width="1"/>`);
    }
    for (let i = 0; i < 44; i += 1) {
      const x = pitch.x + ((pitch.w / 44) * i);
      fiberLines.push(`<line x1="${x}" y1="${pitch.y + 10}" x2="${x + (pitch.w * 0.032)}" y2="${pitch.y + pitch.h - 10}" stroke="rgba(255,255,255,0.016)" stroke-width="0.8"/>`);
    }
    return `
      <g clip-path="url(#${idPrefix}-pitch-clip)">
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="14" ry="14" fill="#2f7b45"/>
        ${stripes.join('')}
        ${mowLines.join('')}
        ${fiberLines.join('')}
        <image href="${grassTextureSrc}" x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" preserveAspectRatio="xMidYMid slice" opacity="0.34"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" fill="url(#${idPrefix}-grass-fibers)" opacity="0.12"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" fill="url(#${idPrefix}-pitch-sheen)" opacity="0.12"/>
        <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" fill="url(#${idPrefix}-native-grass-sheen)" opacity="0.28"/>
        <ellipse cx="${pitch.x + (pitch.w / 2)}" cy="${pitch.y + (pitch.h * 0.13)}" rx="${pitch.w * 0.47}" ry="${pitch.h * 0.10}" fill="rgba(255,255,255,0.022)"/>
        <ellipse cx="${pitch.x + (pitch.w / 2)}" cy="${pitch.y + (pitch.h * 0.87)}" rx="${pitch.w * 0.47}" ry="${pitch.h * 0.10}" fill="rgba(0,0,0,0.02)"/>
      </g>
    `;
  };

  const buildFocusZones = (pitch, theme) => {
    const leftCx = pitch.x + (pitch.w * 0.16);
    const rightCx = pitch.x + (pitch.w * 0.84);
    const cy = pitch.y + (pitch.h * 0.5);
    const rx = pitch.w * 0.26;
    const ry = pitch.h * 0.34;
    return `
      <g opacity="${theme.focusOpacity}">
        <ellipse cx="${leftCx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="rgba(255,255,255,0.028)"/>
        <ellipse cx="${rightCx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="rgba(255,255,255,0.028)"/>
      </g>
    `;
  };

  const buildGoal = (side, pitch, lineWidth, idPrefix) => {
    const mouth = pitch.h * 0.154;
    const depth = Math.max(22, pitch.w * 0.034);
    const y = pitch.y + ((pitch.h - mouth) / 2);
    const post = Math.max(3.4, lineWidth * 0.88);
    const backInset = Math.max(4, post * 0.95);
    const shadowRx = depth * 0.92;
    const shadowRy = mouth * 0.49;
    const lip = Math.max(1.2, post * 0.38);
    if (side === 'left') {
      const front = pitch.x;
      const back = pitch.x - depth;
      return `
        <g class="goal-left" filter="url(#${idPrefix}-goal-shadow)">
          <ellipse cx="${front - (depth * 0.56)}" cy="${y + mouth / 2}" rx="${shadowRx}" ry="${shadowRy}" fill="rgba(9,18,28,0.16)"/>
          <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net)" opacity="0.95"/>
          <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net-shade)" opacity="0.28"/>
          <polygon points="${front},${y} ${front - post},${y + post * 0.42} ${front - post},${y + mouth + post * 0.42} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-post)" opacity="0.99"/>
          <polygon points="${front - post},${y + post * 0.42} ${back - post * 0.42},${y + backInset} ${back - post * 0.42},${y + mouth - backInset} ${front - post},${y + mouth + post * 0.42}" fill="url(#${idPrefix}-goal-side)" opacity="0.54"/>
          ${buildLine(front, y, front, y + mouth, '#ffffff', post * 1.04)}
          ${buildLine(back, y + backInset, back, y + mouth - backInset, 'rgba(229,236,242,0.92)', post * 0.5)}
          ${buildLine(front, y, back, y + backInset, 'rgba(255,255,255,0.84)', post * 0.42)}
          ${buildLine(front, y + mouth, back, y + mouth - backInset, 'rgba(255,255,255,0.84)', post * 0.42)}
          ${buildLine(front - lip, y + (post * 0.5), front - lip, y + mouth + (post * 0.5), 'rgba(208,218,228,0.62)', 0.8)}
        </g>
      `;
    }
    const front = pitch.x + pitch.w;
    const back = pitch.x + pitch.w + depth;
    return `
      <g class="goal-right" filter="url(#${idPrefix}-goal-shadow)">
          <ellipse cx="${front + (depth * 0.56)}" cy="${y + mouth / 2}" rx="${shadowRx}" ry="${shadowRy}" fill="rgba(9,18,28,0.16)"/>
          <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net)" opacity="0.95"/>
          <polygon points="${front},${y} ${back},${y + backInset} ${back},${y + mouth - backInset} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-net-shade)" opacity="0.28"/>
        <polygon points="${front},${y} ${front + post},${y + post * 0.42} ${front + post},${y + mouth + post * 0.42} ${front},${y + mouth}" fill="url(#${idPrefix}-goal-post)" opacity="0.99"/>
        <polygon points="${front + post},${y + post * 0.42} ${back + post * 0.42},${y + backInset} ${back + post * 0.42},${y + mouth - backInset} ${front + post},${y + mouth + post * 0.42}" fill="url(#${idPrefix}-goal-side)" opacity="0.54"/>
        ${buildLine(front, y, front, y + mouth, '#ffffff', post * 1.04)}
        ${buildLine(back, y + backInset, back, y + mouth - backInset, 'rgba(229,236,242,0.92)', post * 0.5)}
        ${buildLine(front, y, back, y + backInset, 'rgba(255,255,255,0.84)', post * 0.42)}
        ${buildLine(front, y + mouth, back, y + mouth - backInset, 'rgba(255,255,255,0.84)', post * 0.42)}
        ${buildLine(front + lip, y + (post * 0.5), front + lip, y + mouth + (post * 0.5), 'rgba(208,218,228,0.62)', 0.8)}
      </g>
    `;
  };

  const buildPitchLines = (pitch, mode, stroke, strokeWidth, isTopLayer = false, axis = 'horizontal') => {
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

  const buildNativeIdentity = (scene, nativeField, identity, orientation = 'landscape') => {
    const crestSize = Math.max(30, scene.sceneH * 0.028);
    const textSize = Math.max(20, scene.sceneH * 0.018);
    const sharedTextStyle = `font-family="Arial, sans-serif" font-size="${textSize}" font-weight="700" fill="rgba(242,247,252,0.82)" stroke="rgba(52,64,76,0.22)" stroke-width="1.6" letter-spacing="1.7"`;
    if (orientation === 'portrait') {
      const topY = Math.max(34, nativeField.y * 0.38);
      const bottomY = scene.sceneH - topY;
      const centerX = scene.sceneW / 2;
      return `
        <g id="native-identity" opacity="0.92" style="paint-order:stroke;">
          <g transform="translate(${centerX} ${topY})">
            <image href="${identity.crest}" x="${-(crestSize + 150)}" y="${-crestSize * 0.5}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.94"/>
            <text x="0" y="${textSize * 0.28}" text-anchor="middle" ${sharedTextStyle}>${identity.clubName}</text>
          </g>
          <g transform="translate(${centerX} ${bottomY})">
            <image href="${identity.crest}" x="${-(crestSize + 150)}" y="${-crestSize * 0.5}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.90"/>
            <text x="0" y="${textSize * 0.28}" text-anchor="middle" ${sharedTextStyle}>${identity.venueName}</text>
          </g>
        </g>
      `;
    }
    const centerY = scene.sceneH / 2;
    const leftX = Math.max(88, nativeField.x * 0.2);
    const rightX = scene.sceneW - leftX;
    return `
      <g id="native-identity" opacity="0.92" style="paint-order:stroke;">
        <g transform="translate(${leftX} ${centerY}) rotate(-90)">
          <image href="${identity.crest}" x="${-crestSize - 18}" y="${-crestSize * 0.5}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.95"/>
          <text x="0" y="${textSize * 0.32}" text-anchor="start" ${sharedTextStyle}>${identity.clubName}</text>
        </g>
        <g transform="translate(${rightX} ${centerY}) rotate(90)">
          <image href="${identity.crest}" x="${-crestSize - 18}" y="${-crestSize * 0.5}" width="${crestSize}" height="${crestSize}" preserveAspectRatio="xMidYMid meet" opacity="0.9"/>
          <text x="0" y="${textSize * 0.32}" text-anchor="start" ${sharedTextStyle}>${identity.venueName}</text>
        </g>
      </g>
    `;
  };

  const buildGoalTopBottom = (side, pitch, lineWidth, idPrefix) => {
    const mouth = pitch.w * 0.126;
    const depth = Math.max(24, pitch.h * 0.04);
    const post = Math.max(2.3, lineWidth * 0.62);
    const backInset = Math.max(4, post * 1.15);
    const x = pitch.x + ((pitch.w - mouth) / 2);
    const outwardGap = Math.max(3, lineWidth * 0.75);
    const frontY = side === 'top' ? (pitch.y - outwardGap) : (pitch.y + pitch.h + outwardGap);
    const backY = side === 'top' ? (frontY - depth) : (frontY + depth);
    const shadowCx = pitch.x + (pitch.w / 2);
    const shadowCy = side === 'top' ? (frontY - (depth * 0.52)) : (frontY + (depth * 0.52));
    const shadowRx = mouth * 0.47;
    const shadowRy = depth * 0.92;
    const topEdgeY = side === 'top' ? backY + backInset : backY - backInset;
    const poly = side === 'top'
      ? `${x + backInset},${backY} ${x + mouth - backInset},${backY} ${x + mouth},${frontY} ${x},${frontY}`
      : `${x},${frontY} ${x + mouth},${frontY} ${x + mouth - backInset},${backY} ${x + backInset},${backY}`;
    return `
      <g class="goal-${side}" filter="url(#${idPrefix}-goal-shadow)">
        <ellipse cx="${shadowCx}" cy="${shadowCy}" rx="${shadowRx}" ry="${shadowRy}" fill="rgba(9,18,28,0.11)"/>
        <polygon points="${poly}" fill="url(#${idPrefix}-goal-net)" opacity="0.9"/>
        <polygon points="${poly}" fill="url(#${idPrefix}-goal-net-shade)" opacity="0.28"/>
        ${buildLine(x, frontY, x + mouth, frontY, '#ffffff', post)}
        ${buildLine(x + backInset, backY, x + mouth - backInset, backY, 'rgba(226,232,240,0.78)', post * 0.46)}
        ${buildLine(x, frontY, x + backInset, backY, 'rgba(255,255,255,0.68)', post * 0.44)}
        ${buildLine(x + mouth, frontY, x + mouth - backInset, backY, 'rgba(255,255,255,0.68)', post * 0.44)}
        <rect x="${x - (post * 0.5)}" y="${Math.min(frontY, topEdgeY)}" width="${post}" height="${Math.abs(frontY - topEdgeY)}" fill="url(#${idPrefix}-goal-post)" opacity="0.98"/>
        <rect x="${x + mouth - (post * 0.5)}" y="${Math.min(frontY, topEdgeY)}" width="${post}" height="${Math.abs(frontY - topEdgeY)}" fill="url(#${idPrefix}-goal-post)" opacity="0.98"/>
      </g>
    `;
  };

  const buildNativePitchSvg = (presetKey, orientation, grass) => {
    const preset = PRESET_METRICS[presetKey] || PRESET_METRICS.full_pitch;
    const scene = NATIVE_STADIUM_SCENE;
    const stadiumSrc = resolvePitch3dTopImageHref(orientation);
    const grassTextureSrc = resolveGrassTextureHref();
    const nativeField = scaleNativeBounds(orientation, scene);
    const pitch = computePitchRectWithinBounds(presetKey, nativeField);
    const idPrefix = `pitch25d-native-${presetKey}-${orientation}`.replace(/[^a-z0-9_-]/gi, '-');
    const identity = resolveSurfaceIdentity();
    const lineStroke = '#f8fbff';
    const lineUnderStroke = 'rgba(6,16,12,0.18)';
    const lineWidth = clamp(pitch.h / 135, 2.2, 5.2);
    const leftGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'defensive_third']);
    const rightGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'half', 'attacking_third']);
    pitch.idPrefix = idPrefix;
    const pitchBox = `${pitch.x} ${pitch.y} ${pitch.w} ${pitch.h}`;
    const nativeHasPermanentGoals = preset.mode === 'full' || preset.mode === 'blank';
    const nativeFullFieldLook = nativeHasPermanentGoals;
    const activeDiffers = (
      Math.abs(pitch.x - nativeField.x) > 0.5 ||
      Math.abs(pitch.y - nativeField.y) > 0.5 ||
      Math.abs(pitch.w - nativeField.w) > 0.5 ||
      Math.abs(pitch.h - nativeField.h) > 0.5
    );
    const pitchCenterX = pitch.x + (pitch.w / 2);
    const pitchCenterY = pitch.y + (pitch.h / 2);
    const rotatedPortraitPitch = nativeHasPermanentGoals && orientation === 'portrait'
      ? {
          x: pitchCenterX - (pitch.h / 2),
          y: pitchCenterY - (pitch.w / 2),
          w: pitch.h,
          h: pitch.w,
          metrics: pitch.metrics,
          idPrefix,
        }
      : null;
    const portraitFieldRotation = rotatedPortraitPitch
      ? `rotate(90 ${pitchCenterX} ${pitchCenterY})`
      : '';
    const useEndlineGoals = false;
    const useTouchlineGoals = nativeHasPermanentGoals && orientation !== 'portrait';
    const nativeAxis = 'horizontal';

    return `
      <svg xmlns="http://www.w3.org/2000/svg"
           viewBox="0 0 ${scene.sceneW} ${scene.sceneH}"
           preserveAspectRatio="xMidYMid meet"
           shape-rendering="geometricPrecision"
           data-pitch-box="${pitchBox}">
        <defs>
          <clipPath id="${idPrefix}-pitch-clip">
            <rect x="${pitch.x}" y="${pitch.y}" width="${pitch.w}" height="${pitch.h}" rx="14" ry="14"/>
          </clipPath>
          <clipPath id="${idPrefix}-native-field-clip">
            <rect x="${nativeField.x}" y="${nativeField.y}" width="${nativeField.w}" height="${nativeField.h}" rx="18" ry="18"/>
          </clipPath>
          <pattern id="${idPrefix}-grass-fibers" width="128" height="128" patternUnits="userSpaceOnUse">
            <path d="M 10 110 L 18 88 M 40 116 L 48 92 M 72 104 L 80 80 M 104 96 L 112 70" stroke="rgba(255,255,255,0.05)" stroke-width="1" stroke-linecap="round"/>
            <path d="M 26 28 L 34 8 M 54 78 L 62 50 M 92 118 L 100 92" stroke="rgba(6,34,18,0.10)" stroke-width="0.9" stroke-linecap="round"/>
          </pattern>
          <linearGradient id="${idPrefix}-stripe-a" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="${grass.stripeA}"/>
            <stop offset="100%" stop-color="${grass.base}"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-stripe-b" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="${grass.base}"/>
            <stop offset="100%" stop-color="${grass.stripeB}"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-field-sheen" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(255,255,255,0.10)"/>
            <stop offset="22%" stop-color="rgba(255,255,255,0.03)"/>
            <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
          </linearGradient>
          <radialGradient id="${idPrefix}-native-grass-sheen" cx="50%" cy="50%" r="70%">
            <stop offset="0%" stop-color="rgba(255,255,255,0.08)"/>
            <stop offset="48%" stop-color="rgba(255,255,255,0.03)"/>
            <stop offset="100%" stop-color="rgba(0,0,0,0.04)"/>
          </radialGradient>
          <linearGradient id="${idPrefix}-field-shadow" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(0,0,0,0.00)"/>
            <stop offset="100%" stop-color="rgba(0,0,0,0.16)"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-native-ad-shell" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(67,79,92,0.96)"/>
            <stop offset="45%" stop-color="rgba(32,41,53,0.98)"/>
            <stop offset="100%" stop-color="rgba(18,25,34,0.99)"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-native-ad-screen" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="rgba(30,40,52,0.98)"/>
            <stop offset="52%" stop-color="rgba(9,14,20,0.99)"/>
            <stop offset="100%" stop-color="rgba(5,8,13,1)"/>
          </linearGradient>
          <pattern id="${idPrefix}-goal-net" width="14" height="14" patternUnits="userSpaceOnUse">
            <path d="M 0 0 L 14 14 M 14 0 L 0 14" stroke="rgba(247,250,252,0.82)" stroke-width="0.85"/>
          </pattern>
          <linearGradient id="${idPrefix}-goal-post" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#ffffff"/>
            <stop offset="100%" stop-color="#e4ebf1"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-goal-side" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#eef4f8"/>
            <stop offset="100%" stop-color="#ccd8e2"/>
          </linearGradient>
          <linearGradient id="${idPrefix}-goal-net-shade" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(255,255,255,0.16)"/>
            <stop offset="100%" stop-color="rgba(148,163,184,0.03)"/>
          </linearGradient>
          <filter id="${idPrefix}-goal-shadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(11,20,33,0.10)"/>
          </filter>
          <filter id="${idPrefix}-field-drop" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="4" stdDeviation="10" flood-color="rgba(6,16,12,0.18)"/>
          </filter>
          <filter id="${idPrefix}-native-ad-shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="rgba(6,12,18,0.28)"/>
          </filter>
          <filter id="${idPrefix}-native-ad-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="rgba(255,255,255,0.10)"/>
          </filter>
        </defs>
        <rect x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" fill="#edf2f7"/>
        <image href="${stadiumSrc}" x="0" y="0" width="${scene.sceneW}" height="${scene.sceneH}" preserveAspectRatio="xMidYMid slice"/>
        ${buildNativeAdBoards(pitch, idPrefix, orientation)}
        ${buildNativeIdentity(scene, nativeField, identity, orientation)}
        ${!nativeFullFieldLook && activeDiffers ? `<rect x="${nativeField.x}" y="${nativeField.y}" width="${nativeField.w}" height="${nativeField.h}" rx="18" ry="18" fill="rgba(7,20,13,0.12)"/>` : ''}
        <g id="pitch-native">
          <g clip-path="url(#${idPrefix}-pitch-clip)" filter="url(#${idPrefix}-field-drop)">
            ${buildEliteGrassLayer(pitch, idPrefix, grassTextureSrc)}
          </g>
          <rect x="${pitch.x + 1.4}" y="${pitch.y + 1.4}" width="${pitch.w - 2.8}" height="${pitch.h - 2.8}" rx="13" ry="13" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
          ${nativeHasPermanentGoals && rotatedPortraitPitch
            ? `<g transform="${portraitFieldRotation}">${buildPitchLines(rotatedPortraitPitch, rotatedPortraitPitch.metrics.mode, 'rgba(8,20,14,0.14)', Math.max(1.8, lineWidth * 0.86), false, nativeAxis)}</g>`
            : (nativeFullFieldLook
              ? buildPitchLines(pitch, pitch.metrics.mode, 'rgba(8,20,14,0.14)', Math.max(1.8, lineWidth * 0.86), false, nativeAxis)
              : buildPitchLines(pitch, pitch.metrics.mode, lineUnderStroke, lineWidth + 1.2))}
          ${nativeHasPermanentGoals && rotatedPortraitPitch
            ? `<g>${buildGoalTopBottom('top', pitch, lineWidth + 0.4, idPrefix)}${buildGoalTopBottom('bottom', pitch, lineWidth + 0.4, idPrefix)}</g>`
            : ''}
          ${(useTouchlineGoals || (!nativeFullFieldLook && leftGoalModes.has(pitch.metrics.mode))) ? buildGoal('left', pitch, lineWidth + 0.4, idPrefix) : ''}
          ${(useTouchlineGoals || (!nativeFullFieldLook && rightGoalModes.has(pitch.metrics.mode))) ? buildGoal('right', pitch, lineWidth + 0.4, idPrefix) : ''}
          ${nativeHasPermanentGoals && rotatedPortraitPitch
            ? `<g transform="${portraitFieldRotation}">${buildPitchLines(rotatedPortraitPitch, rotatedPortraitPitch.metrics.mode, '#f6fbff', Math.max(1.35, lineWidth * 0.7), true, nativeAxis)}</g>`
            : (nativeFullFieldLook
              ? buildPitchLines(pitch, pitch.metrics.mode, '#f6fbff', Math.max(1.35, lineWidth * 0.7), true, nativeAxis)
              : buildPitchLines(pitch, pitch.metrics.mode, lineStroke, lineWidth, true))}
          ${buildCornerFlags(pitch)}
        </g>
      </svg>
    `.trim();
  };

  const buildCompactSevenPitchSvg = (presetKey, orientation, grass, theme) => {
    const sceneLandscape = { sceneW: 1536, sceneH: 1024 };
    const sceneW = orientation === 'portrait' ? sceneLandscape.sceneH : sceneLandscape.sceneW;
    const sceneH = orientation === 'portrait' ? sceneLandscape.sceneW : sceneLandscape.sceneH;
    const pitch = computePitchRect(presetKey, sceneLandscape.sceneW, sceneLandscape.sceneH);
    const idPrefix = `pitch25d-compact-${presetKey}-${orientation}`.replace(/[^a-z0-9_-]/gi, '-');
    const grassTextureSrc = resolveGrassTextureHref();
    const lineStroke = '#f6fbff';
    const lineUnderStroke = 'rgba(8,20,14,0.14)';
    const lineWidth = clamp(pitch.h / 132, 2.2, 5.0);
    pitch.idPrefix = idPrefix;
    const needsPortraitRotation = orientation === 'portrait';
    const sceneBody = `
      ${buildDefs(idPrefix, pitch, grass, theme)}
      <rect x="0" y="0" width="${sceneLandscape.sceneW}" height="${sceneLandscape.sceneH}" fill="rgba(8,24,13,0.22)"/>
      <g id="pitch-compact-seven">
        ${buildEliteGrassLayer(pitch, idPrefix, grassTextureSrc)}
        ${buildPitchLines(pitch, pitch.metrics.mode, lineUnderStroke, Math.max(1.8, lineWidth * 0.86), false, 'horizontal')}
        ${buildGoal('left', pitch, lineWidth + 0.4, idPrefix)}
        ${buildGoal('right', pitch, lineWidth + 0.4, idPrefix)}
        ${buildPitchLines(pitch, pitch.metrics.mode, lineStroke, Math.max(1.35, lineWidth * 0.72), true, 'horizontal')}
        ${buildCornerFlags(pitch)}
      </g>
    `;
    return `
      <svg xmlns="http://www.w3.org/2000/svg"
           viewBox="0 0 ${sceneW} ${sceneH}"
           preserveAspectRatio="xMidYMid meet"
           shape-rendering="geometricPrecision"
           data-pitch-box="${pitch.x} ${pitch.y} ${pitch.w} ${pitch.h}">
        ${needsPortraitRotation
          ? `<g transform="translate(${sceneLandscape.sceneH} 0) rotate(90)">${sceneBody}</g>`
          : sceneBody}
      </svg>
    `.trim();
  };

  const buildPitchSvg = (presetKey, orientationKey = 'landscape', grassStyleKey = 'classic') => {
    const preset = PRESET_METRICS[safeText(presetKey, 'full_pitch')] ? safeText(presetKey, 'full_pitch') : 'full_pitch';
    const orientation = safeText(orientationKey, 'landscape') === 'portrait' ? 'portrait' : 'landscape';
    const normalizedGrass = safeText(grassStyleKey, 'classic').toLowerCase();
    const isCompactLab = (() => {
      try {
        return !!document.body?.classList?.contains?.('editor-lab-compact');
      } catch (e) {
        return false;
      }
    })();
    const isPresentationSurface = (() => {
      try { return !!document.body?.classList?.contains?.('focus-mode'); } catch (e) { return false; }
    })();
    if (isCompactLab) {
      if (preset === 'seven_side' || preset === 'seven_side_single') {
        const compactGrass = GRASS_PRESETS.pro || GRASS_PRESETS.classic;
        const compactTheme = resolveSurfaceTheme('pro');
        return buildCompactSevenPitchSvg(preset, orientation, compactGrass, compactTheme);
      }
      const sceneLandscape = { sceneW: 1536, sceneH: 1024 };
      const sceneW = orientation === 'portrait' ? sceneLandscape.sceneH : sceneLandscape.sceneW;
      const sceneH = orientation === 'portrait' ? sceneLandscape.sceneW : sceneLandscape.sceneH;
      const referencePitchSrc = '/static/football/images/pitch3d/tactical_pitch_reference_local.png';
      const transform = orientation === 'portrait'
        ? `transform="translate(${sceneLandscape.sceneH} 0) rotate(90)"`
        : '';
      const content = `
        <svg xmlns="http://www.w3.org/2000/svg"
             viewBox="0 0 ${sceneW} ${sceneH}"
             preserveAspectRatio="xMidYMid meet"
             shape-rendering="geometricPrecision">
          ${orientation === 'portrait' ? `<g ${transform}>` : ''}
            <image href="${referencePitchSrc}"
                   x="0"
                   y="0"
                   width="${sceneLandscape.sceneW}"
                   height="${sceneLandscape.sceneH}"
                   preserveAspectRatio="xMidYMid slice"/>
          ${orientation === 'portrait' ? '</g>' : ''}
        </svg>
      `;
      return content.trim();
    }
    const effectiveGrass = (normalizedGrass === 'stadium_native' && !isPresentationSurface) ? 'pro' : normalizedGrass;
    const grass = GRASS_PRESETS[effectiveGrass] || GRASS_PRESETS.classic;
    const theme = resolveSurfaceTheme(effectiveGrass);
    if (effectiveGrass === 'stadium_native') {
      return buildNativePitchSvg(preset, orientation, grass);
    }
    const sceneLandscape = { sceneW: 1200, sceneH: 820 };
    const sceneW = orientation === 'portrait' ? sceneLandscape.sceneH : sceneLandscape.sceneW;
    const sceneH = orientation === 'portrait' ? sceneLandscape.sceneW : sceneLandscape.sceneH;
    const pitch = computePitchRect(preset, sceneLandscape.sceneW, sceneLandscape.sceneH);
    const idPrefix = `pitch25d-${preset}-${orientation}-${effectiveGrass}`.replace(/[^a-z0-9_-]/gi, '-');
    const lineStroke = effectiveGrass === 'whiteboard' ? 'rgba(15,23,42,0.88)' : '#fdfefe';
    const lineUnderStroke = effectiveGrass === 'whiteboard' ? 'rgba(255,255,255,0.42)' : 'rgba(9,18,28,0.11)';
    const lineWidth = clamp(pitch.h / 150, 2.7, 5.8);
    const renderContext = isPresentationSurface && !['whiteboard', 'blackboard', 'coachboard'].includes(effectiveGrass) && pitch.metrics.mode === 'full';
    const leftGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'defensive_third']);
    const rightGoalModes = new Set(['full', 'seven_side', 'seven_side_single', 'futsal', 'half', 'attacking_third']);
    pitch.idPrefix = idPrefix;

    const sceneBody = `
      ${buildDefs(idPrefix, pitch, grass, theme)}
      ${buildBackdrop(sceneLandscape, pitch, theme)}
      ${renderContext ? buildStands(pitch, idPrefix) : ''}
      ${renderContext ? buildAdBoards(pitch, idPrefix, theme) : ''}
      ${renderContext ? buildBenches(pitch) : ''}
      <g id="pitch">
          ${buildGrassLayer(pitch, grass, theme, grassTextureSrc)}
        ${buildFocusZones(pitch, theme)}
        <rect x="${pitch.x + 5}" y="${pitch.y + 5}" width="${pitch.w - 10}" height="${pitch.h - 10}" rx="14" ry="14" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.1"/>
        ${buildPitchLines(pitch, pitch.metrics.mode, lineUnderStroke, lineWidth + 1.15)}
        ${leftGoalModes.has(pitch.metrics.mode) ? buildGoal('left', pitch, lineWidth + 0.55, idPrefix) : ''}
        ${rightGoalModes.has(pitch.metrics.mode) ? buildGoal('right', pitch, lineWidth + 0.55, idPrefix) : ''}
        ${buildPitchLines(pitch, pitch.metrics.mode, lineStroke, lineWidth, true)}
        ${buildCornerFlags(pitch)}
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
           shape-rendering="geometricPrecision"
           data-pitch-box="${pitchBox}">
        ${content}
      </svg>
    `.trim();
  };

  window.WebstatsPitch25D = {
    buildPitchSvg,
    listAdPresets: () => Object.entries(AD_PRESETS).map(([key, meta]) => ({ key, label: meta.label })),
    getAdPreset: () => normalizeAdPreset(window.__WEBSTATS_PITCH25D_AD_PRESET),
    setAdPreset: (value) => {
      const next = normalizeAdPreset(value);
      try { window.__WEBSTATS_PITCH25D_AD_PRESET = next; } catch (e) { /* ignore */ }
      return next;
    },
  };
}());
