import os
from pathlib import Path


def configure_native_runtime():
    homebrew_lib = Path('/opt/homebrew/lib')
    if homebrew_lib.exists():
        current = os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '').strip()
        parts = [part for part in current.split(':') if part]
        lib_path = str(homebrew_lib)
        if lib_path not in parts:
            parts.insert(0, lib_path)
            os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = ':'.join(parts)

    cache_candidates = [
        Path.home() / 'Library' / 'Caches',
        Path('/tmp/webstats-cache'),
    ]
    for candidate in cache_candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if os.access(candidate, os.W_OK):
            os.environ.setdefault('XDG_CACHE_HOME', str(candidate))
            break
