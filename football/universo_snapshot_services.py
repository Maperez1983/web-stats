import json
import os
from pathlib import Path

from django.conf import settings


def env_path(var_name: str, default_path: Path) -> Path:
    raw = str(os.getenv(var_name, '') or '').strip()
    if raw:
        try:
            return Path(raw).expanduser()
        except Exception:
            return default_path
    return default_path


UNIVERSO_SNAPSHOT_PATH = env_path(
    'UNIVERSO_SNAPSHOT_PATH',
    Path(settings.BASE_DIR) / 'data' / 'input' / 'universo-rfaf-snapshot.json',
)


def load_universo_snapshot():
    if not UNIVERSO_SNAPSHOT_PATH.exists():
        return None
    try:
        mtime = UNIVERSO_SNAPSHOT_PATH.stat().st_mtime
    except Exception:
        mtime = None
    memo = getattr(load_universo_snapshot, '_memo', None)
    if isinstance(memo, dict) and memo.get('mtime') and mtime and float(memo.get('mtime')) == float(mtime):
        cached_payload = memo.get('payload')
        if isinstance(cached_payload, dict):
            return cached_payload
    try:
        with UNIVERSO_SNAPSHOT_PATH.open(encoding='utf-8') as handle:
            payload = json.load(handle)
            if not isinstance(payload, dict):
                return None
            try:
                load_universo_snapshot._memo = {'mtime': mtime, 'payload': payload}
            except Exception:
                pass
            return payload
    except Exception:
        return None
