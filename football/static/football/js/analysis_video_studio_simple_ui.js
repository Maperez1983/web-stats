(function () {
  const init = () => {
    const tabClip = document.getElementById('vs-tab-clip');
    const tabAdvanced = document.getElementById('vs-tab-advanced');
    const panelClip = document.getElementById('vs-panel-clip');
    const panelAdvanced = document.getElementById('vs-panel-advanced');
    if (!tabClip || !tabAdvanced || !panelClip || !panelAdvanced) return;

    let advancedBootstrapped = false;
    let advancedRetries = 0;
    const tryEnableAdvanced = () => {
      try {
        if (typeof window.__vsEnableAdvancedFeatures === 'function') {
          window.__vsEnableAdvancedFeatures();
          return true;
        }
      } catch (e) {
        // ignore
      }
      return false;
    };

    const setActive = (name) => {
      const isClip = name === 'clip';
      tabClip.setAttribute('aria-selected', String(isClip));
      tabAdvanced.setAttribute('aria-selected', String(!isClip));
      tabClip.tabIndex = isClip ? 0 : -1;
      tabAdvanced.tabIndex = isClip ? -1 : 0;
      panelClip.hidden = !isClip;
      panelAdvanced.hidden = isClip;
      try { document.body.classList.toggle('vs-advanced', !isClip); } catch (e) { /* ignore */ }

      if (!isClip && !advancedBootstrapped) {
        advancedBootstrapped = true;
        if (!tryEnableAdvanced()) {
          const tick = () => {
            if (tryEnableAdvanced()) return;
            advancedRetries += 1;
            if (advancedRetries > 10) return;
            window.setTimeout(tick, 250);
          };
          window.setTimeout(tick, 250);
        }
      }
    };

    tabClip.addEventListener('click', () => setActive('clip'));
    tabAdvanced.addEventListener('click', () => setActive('advanced'));

    setActive('clip');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
