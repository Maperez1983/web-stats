import json
import os
import unicodedata
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from football.query_helpers import _normalize_team_lookup_key
from football.universo_snapshot_services import load_universo_snapshot


def _env_path(var_name: str, default_path: Path) -> Path:
    raw = str(os.getenv(var_name, '') or '').strip()
    if raw:
        try:
            return Path(raw).expanduser()
        except Exception:
            return default_path
    return default_path


UNIVERSO_CAPTURE_PATH = _env_path(
    'UNIVERSO_CAPTURE_PATH',
    Path(settings.BASE_DIR) / 'data' / 'input' / 'universo-rfaf-capture.json',
)
UNIVERSO_EXTERNAL_IMAGES_ENABLED = str(
    os.getenv('UNIVERSO_EXTERNAL_IMAGES_ENABLED', '0')
).strip().lower() in {'1', 'true', 'yes', 'on'}


def absolute_universo_url(path_or_url):
    value = str(path_or_url or '').strip()
    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value.startswith('/'):
        if value.startswith('/pnfg/') or value.startswith('/api/') or value.startswith('/_next/'):
            return f'https://www.universorfaf.es{value}'
        return value
    return f'https://www.universorfaf.es/{value.lstrip("/")}'


def sanitize_universo_external_image(url):
    value = str(url or '').strip()
    if not value:
        return ''
    if UNIVERSO_EXTERNAL_IMAGES_ENABLED:
        return value
    lowered = value.lower()
    if 'universorfaf.es/pnfg/pimg/' in lowered:
        return ''
    return value


def build_universo_capture_team_lookup():
    memo = getattr(build_universo_capture_team_lookup, '_memo', None)
    lookup = {}
    capture_path = UNIVERSO_CAPTURE_PATH
    if not capture_path.exists():
        return lookup
    try:
        mtime = capture_path.stat().st_mtime
    except Exception:
        mtime = None
    if isinstance(memo, dict) and memo.get('mtime') and mtime and float(memo.get('mtime')) == float(mtime):
        cached_lookup = memo.get('lookup')
        if isinstance(cached_lookup, dict):
            return cached_lookup
    try:
        payload = json.loads(capture_path.read_text(encoding='utf-8'))
    except Exception:
        return lookup
    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return lookup

    def _push(team_name, crest):
        full_name = str(team_name or '').strip()
        if not full_name:
            return
        key = _normalize_team_lookup_key(full_name)
        if not key:
            return
        crest_url = absolute_universo_url(crest)
        current = lookup.get(key, {})
        if not current:
            lookup[key] = {
                'full_name': full_name,
                'crest_url': crest_url,
            }
            return
        if len(full_name) > len(current.get('full_name') or ''):
            current['full_name'] = full_name
        if crest_url and not current.get('crest_url'):
            current['crest_url'] = crest_url
        lookup[key] = current

    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get('json')
        if isinstance(data, dict):
            _push(data.get('nombre_equipo') or data.get('equipo'), data.get('escudo_equipo'))
            competitions = data.get('competiciones_participa')
            if isinstance(competitions, list):
                for row in competitions:
                    if isinstance(row, dict):
                        _push(row.get('nombre_equipo') or row.get('nombre_club'), row.get('escudo_equipo'))

            for bucket in data.values():
                if isinstance(bucket, list):
                    for row in bucket:
                        if isinstance(row, dict):
                            _push(row.get('nombre_equipo') or row.get('equipo'), row.get('escudo_equipo'))
    try:
        build_universo_capture_team_lookup._memo = {'mtime': mtime, 'lookup': lookup}
    except Exception:
        pass
    return lookup


def build_team_crest_lookup(load_snapshot_func=None):
    memo = getattr(build_team_crest_lookup, '_memo', None)
    lookup = {}

    def _push(name='', external_id='', crest=''):
        crest_url = absolute_universo_url(crest)
        if not crest_url:
            return
        normalized_name = _normalize_team_lookup_key(name)
        normalized_external_id = str(external_id or '').strip().lower()
        for key in (normalized_name, normalized_external_id):
            if key and key not in lookup:
                lookup[key] = crest_url

    capture_path = UNIVERSO_CAPTURE_PATH
    try:
        capture_mtime = capture_path.stat().st_mtime if capture_path.exists() else None
    except Exception:
        capture_mtime = None
    if load_snapshot_func is None:
        load_snapshot_func = load_universo_snapshot
    snapshot_memo = getattr(load_snapshot_func, '_memo', None)
    snapshot_mtime = snapshot_memo.get('mtime') if isinstance(snapshot_memo, dict) else None
    if isinstance(memo, dict) and memo.get('capture_mtime') == capture_mtime and memo.get('snapshot_mtime') == snapshot_mtime:
        cached_lookup = memo.get('lookup')
        if isinstance(cached_lookup, dict):
            return cached_lookup
    if capture_path.exists():
        try:
            payload = json.loads(capture_path.read_text(encoding='utf-8'))
        except Exception:
            payload = {}
        items = payload.get('items') if isinstance(payload, dict) else []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            data = item.get('json')
            if not isinstance(data, dict):
                continue
            _push(
                data.get('nombre_equipo') or data.get('equipo') or data.get('nombre_club'),
                data.get('codequipo') or data.get('cod_equipo') or data.get('CodEquipo'),
                data.get('escudo_equipo') or data.get('escudo'),
            )
            competitions = data.get('competiciones_participa')
            if isinstance(competitions, list):
                for row in competitions:
                    if not isinstance(row, dict):
                        continue
                    _push(
                        row.get('nombre_equipo') or row.get('nombre_club'),
                        row.get('codequipo') or row.get('cod_equipo'),
                        row.get('escudo_equipo') or row.get('escudo'),
                    )
            for bucket in data.values():
                if not isinstance(bucket, list):
                    continue
                for row in bucket:
                    if not isinstance(row, dict):
                        continue
                    _push(
                        row.get('nombre') or row.get('nombre_equipo') or row.get('nombre_club') or row.get('Nombre_equipo_local') or row.get('Nombre_equipo_visitante'),
                        row.get('codequipo') or row.get('CodEquipo_local') or row.get('CodEquipo_visitante'),
                        row.get('escudo_equipo') or row.get('escudo') or row.get('url_img_local') or row.get('url_img_visitante'),
                    )
    snapshot = load_snapshot_func()
    if isinstance(snapshot, dict):
        for row in snapshot.get('standings') or []:
            if not isinstance(row, dict):
                continue
            _push(row.get('team') or row.get('full_name'), row.get('team_code'), row.get('crest_url'))
        next_match = snapshot.get('next_match')
        if isinstance(next_match, dict):
            opponent = next_match.get('opponent')
            if isinstance(opponent, dict):
                _push(opponent.get('full_name') or opponent.get('name'), opponent.get('team_code'), opponent.get('crest_url'))
    try:
        build_team_crest_lookup._memo = {'capture_mtime': capture_mtime, 'snapshot_mtime': snapshot_mtime, 'lookup': lookup}
    except Exception:
        pass
    return lookup


def sync_team_crest_from_sources(team, *, load_snapshot_func=None, invalidate_func=None):
    if not team:
        return ''
    if getattr(team, 'crest_image', None):
        return ''
    lookup = build_team_crest_lookup(load_snapshot_func=load_snapshot_func)
    lookup_keys = {
        _normalize_team_lookup_key(getattr(team, 'name', '') or ''),
        _normalize_team_lookup_key(getattr(team, 'display_name', '') or ''),
        str(getattr(team, 'external_id', '') or '').strip().lower(),
    }
    resolved = ''
    for key in lookup_keys:
        if key and lookup.get(key):
            resolved = lookup[key]
            break
    if resolved and resolved != (team.crest_url or ''):
        team.crest_url = resolved
        team.save(update_fields=['crest_url'])
        if invalidate_func is None:
            from .views import _invalidate_team_dashboard_caches as invalidate_func
        invalidate_func(team)
    return resolved


def _fold_team_label(value):
    text = str(value or '').strip().lower()
    if not text:
        return ''
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def is_benagalbon_team(team):
    if not team:
        return False
    labels = (
        getattr(team, 'slug', ''),
        getattr(team, 'name', ''),
        getattr(team, 'display_name', ''),
        getattr(team, 'short_name', ''),
    )
    return any('benagalbon' in _fold_team_label(label) for label in labels)


def resolve_team_crest_url(
    request,
    team,
    *,
    fallback_static='football/images/cdb-logo.png',
    sync=False,
    load_snapshot_func=None,
    invalidate_func=None,
):
    def _abs_or_relative(path: str) -> str:
        path = str(path or '').strip()
        if not path:
            return ''
        if not request:
            return path
        try:
            return request.build_absolute_uri(path)
        except Exception:
            return path

    if not team:
        if not fallback_static:
            return ''
        try:
            return _abs_or_relative(static(fallback_static))
        except Exception:
            return ''
    if getattr(team, 'crest_image', None):
        try:
            return _abs_or_relative(team.crest_image.url)
        except Exception:
            pass
    crest_url = str(getattr(team, 'crest_url', '') or '').strip()
    if not crest_url and sync:
        crest_url = sync_team_crest_from_sources(
            team,
            load_snapshot_func=load_snapshot_func,
            invalidate_func=invalidate_func,
        )
    crest_url = sanitize_universo_external_image(absolute_universo_url(crest_url))
    if crest_url:
        return crest_url
    if is_benagalbon_team(team):
        try:
            local_primary = 'football/images/cdb-benagalbon-crest-contrast.png'
            return _abs_or_relative(static(local_primary))
        except Exception:
            pass
    try:
        generated = reverse('team-crest-svg', args=[team.id])
        return _abs_or_relative(generated)
    except Exception:
        if fallback_static:
            try:
                return _abs_or_relative(static(fallback_static))
            except Exception:
                return static(fallback_static)
        return ''
