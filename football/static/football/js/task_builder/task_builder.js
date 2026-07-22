(function () {
  var cfg = window.__TASK_BUILDER_CONFIG || {};
  window.TaskBuilder = window.TaskBuilder || {};
  try {
    if (window.history && 'scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  } catch (e) { /* ignore */ }
  try {
    const resetScroll = () => {
      try { window.scrollTo({ top: 0, left: 0, behavior: 'auto' }); } catch (e) { /* ignore */ }
    };
    if (document.readyState === 'complete') {
      try { window.setTimeout(resetScroll, 0); } catch (e) { /* ignore */ }
    } else {
      window.addEventListener('load', resetScroll, { once: true });
    }
  } catch (e) { /* ignore */ }
  try { window.__TASK_BUILDER_CONFIG = cfg; } catch (e) { /* ignore */ }
  try {
    window.TaskBuilder = Object.assign(window.TaskBuilder || {}, {
      config: cfg,
      ensureEditorStack: window.__webstatsEnsureEditorStack || null,
      setPreset: window.__webstatsTaskBuilderSetPreset || null,
      applyLocalTemplate: window.__webstatsTaskBuilderApplyLocalTemplate || null,
      applyRecommendedTokenStyle: window.__tpadApplyRecommendedTokenStyle || null,
      openOverlaysPopover: window.__tpadOpenOverlaysPopover || null,
      openZonesPopover: window.__tpadOpenZonesPopover || null,
      scheduleIdle: window.__webstatsScheduleIdle || window.scheduleIdle || null,
      init: (...args) => {
        if (typeof window.initSessionsTacticalPad === 'function') {
          return window.initSessionsTacticalPad(...args);
        }
        return null;
      },
    });
  } catch (e) { /* ignore */ }
})();
