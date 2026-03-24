(function () {
  const safeJsonParse = (raw, fallback) => {
    try {
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  };

  const storageAvailable = (storage) => {
    try {
      const probeKey = '__football_tactical_probe__';
      storage.setItem(probeKey, '1');
      storage.removeItem(probeKey);
      return true;
    } catch (error) {
      return false;
    }
  };

  const localOk = typeof window !== 'undefined' && window.localStorage && storageAvailable(window.localStorage);
  const sessionOk = typeof window !== 'undefined' && window.sessionStorage && storageAvailable(window.sessionStorage);

  const readStorageJson = (key, fallback = {}) => {
    if (!localOk) return fallback;
    const parsed = safeJsonParse(window.localStorage.getItem(key), fallback);
    return parsed && typeof parsed === 'object' ? parsed : fallback;
  };

  const writeStorageJson = (key, value) => {
    if (!localOk) return false;
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  };

  const removeStorageKey = (key) => {
    if (!localOk) return;
    window.localStorage.removeItem(key);
  };

  const readSessionValue = (key, fallback = '') => {
    if (!sessionOk) return fallback;
    return String(window.sessionStorage.getItem(key) || fallback);
  };

  const writeSessionValue = (key, value) => {
    if (!sessionOk) return false;
    try {
      window.sessionStorage.setItem(key, String(value));
      return true;
    } catch (error) {
      return false;
    }
  };

  const removeSessionKey = (key) => {
    if (!sessionOk) return;
    window.sessionStorage.removeItem(key);
  };

  const debounce = (fn, wait = 400) => {
    let timer = null;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), wait);
    };
  };

  const downloadText = (content, filename, mimeType = 'text/plain;charset=utf-8') => {
    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadJson = (payload, filename) => {
    downloadText(JSON.stringify(payload, null, 2), filename, 'application/json;charset=utf-8');
  };

  const downloadDataUrl = (dataUrl, filename) => {
    if (!dataUrl) return;
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = filename;
    link.click();
  };

  window.FootballTacticalShared = {
    debounce,
    downloadDataUrl,
    downloadJson,
    readSessionValue,
    readStorageJson,
    removeSessionKey,
    removeStorageKey,
    safeJsonParse,
    writeSessionValue,
    writeStorageJson,
  };
})();
