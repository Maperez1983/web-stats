import json
import logging
import os
import base64
import html
import unicodedata
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from football.query_helpers import _normalize_team_lookup_key
from football.universo_snapshot_services import load_universo_snapshot


logger = logging.getLogger(__name__)


def _env_path(var_name: str, default_path: Path) -> Path:
    raw = str(os.getenv(var_name, '') or '').strip()
    if raw:
        try:
            return Path(raw).expanduser()
        except Exception:
            return default_path
    return default_path


def _read_json_file(path: Path, *, fallback=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.debug('No se pudo leer JSON de %s: %s', path, exc)
        return fallback


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
    payload = _read_json_file(capture_path)
    if not isinstance(payload, dict):
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
        payload = _read_json_file(capture_path, fallback={})
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


def is_malaga_team(team):
    if not team:
        return False
    labels = (
        getattr(team, 'slug', ''),
        getattr(team, 'name', ''),
        getattr(team, 'display_name', ''),
        getattr(team, 'short_name', ''),
    )
    return any('malaga' in _fold_team_label(label) for label in labels)


def team_initials(label):
    text = ' '.join(str(label or '').split()).strip()
    if not text:
        return '??'
    tokens = [tok for tok in ''.join(ch if ch.isalnum() else ' ' for ch in text).split() if tok]
    if not tokens:
        return (text[:2] if len(text) >= 2 else text).upper()
    if len(tokens) == 1:
        return (tokens[0][:2] if len(tokens[0]) >= 2 else tokens[0]).upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def _team_initials(label):
    return team_initials(label)


def should_use_team_cover_image(request, workspace, team, *, can_access_platform_func=None, single_club_fallback_func=None) -> bool:
    """
    Decide if Team.cover_image is safe to use as a UI hero image.

    In multi-team club workspaces, legacy cloned teams may share the senior cover image.
    We only trust that cover when it has been explicitly updated for the selected team.
    """
    if not team or not getattr(team, 'cover_image', None):
        return False
    if not workspace:
        try:
            user = getattr(request, 'user', None) if request else None
            if user and getattr(user, 'is_authenticated', False) and callable(can_access_platform_func) and can_access_platform_func(user):
                return True
        except Exception:
            pass
        try:
            return bool(single_club_fallback_func()) if callable(single_club_fallback_func) else False
        except Exception:
            return False
    try:
        if getattr(team, 'cover_updated_at', None):
            return True
    except Exception:
        pass
    try:
        from .models import Workspace, WorkspaceTeam

        if getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
            return True
        other_links_exist = WorkspaceTeam.objects.filter(workspace=workspace).exclude(team=team).exists()
    except Exception:
        other_links_exist = False
    return not bool(other_links_exist)


def team_color_seed(team):
    base = str(getattr(team, 'slug', '') or getattr(team, 'name', '') or '').strip().lower()
    if not base:
        base = str(getattr(team, 'id', '') or 'team')
    total = 0
    for ch in base:
        total = (total * 31 + ord(ch)) % 360
    return total


def normalize_hex_color(value, fallback='#0f7a35'):
    raw = str(value or '').strip()
    if not raw:
        return fallback
    if not raw.startswith('#'):
        return fallback
    if len(raw) == 4:
        raw = '#' + ''.join(ch * 2 for ch in raw[1:])
    if len(raw) != 7:
        return fallback
    try:
        int(raw[1:], 16)
    except Exception:
        return fallback
    return raw.lower()


def hsl_to_hex(hue, saturation=0.68, lightness=0.38):
    try:
        h = (float(hue or 0) % 360.0) / 60.0
        s = max(0.0, min(float(saturation), 1.0))
        l = max(0.0, min(float(lightness), 1.0))
        c = (1.0 - abs((2.0 * l) - 1.0)) * s
        x = c * (1.0 - abs((h % 2.0) - 1.0))
        m = l - (c / 2.0)
        r1, g1, b1 = (0.0, 0.0, 0.0)
        if 0 <= h < 1:
            r1, g1, b1 = c, x, 0
        elif 1 <= h < 2:
            r1, g1, b1 = x, c, 0
        elif 2 <= h < 3:
            r1, g1, b1 = 0, c, x
        elif 3 <= h < 4:
            r1, g1, b1 = 0, x, c
        elif 4 <= h < 5:
            r1, g1, b1 = x, 0, c
        else:
            r1, g1, b1 = c, 0, x
        return '#%02x%02x%02x' % (
            int(round((r1 + m) * 255)),
            int(round((g1 + m) * 255)),
            int(round((b1 + m) * 255)),
        )
    except Exception:
        return '#102734'


def team_pdf_palette(team_obj, style_key='uefa'):
    primary = normalize_hex_color(getattr(team_obj, 'primary_color', ''), '#0f7a35')
    secondary = normalize_hex_color(getattr(team_obj, 'secondary_color', ''), '#facc15')
    accent = normalize_hex_color(getattr(team_obj, 'accent_color', ''), '#102734')
    if style_key in {'club', 'hybrid'}:
        if is_benagalbon_team(team_obj):
            return {
                'primary': '#007050',
                'secondary': '#ffffff',
                'accent': '#044a37',
                'panel': '#f1f7f3',
                'sheet': '#f8fbf8' if style_key == 'hybrid' else '#ffffff',
                'ink': '#0b1f1a',
                'muted': '#3b5a54',
            }
        if is_malaga_team(team_obj):
            return {
                'primary': '#6bc4e8',
                'secondary': '#ffffff',
                'accent': '#004b93',
                'panel': '#eef8fc',
                'sheet': '#f5fbff' if style_key == 'hybrid' else '#ffffff',
                'ink': '#082f49',
                'muted': '#436074',
            }
        if primary == '#0f7a35' and secondary in {'#facc15', '#f8fafc'}:
            hue = team_color_seed(team_obj)
            primary = hsl_to_hex(hue, 0.68, 0.38)
            secondary = hsl_to_hex((hue + 35) % 360, 0.70, 0.48)
            accent = hsl_to_hex((hue + 210) % 360, 0.62, 0.24)
        return {
            'primary': primary,
            'secondary': secondary,
            'accent': accent,
            'panel': '#f5fbf6',
            'sheet': '#f6f7f5' if style_key == 'hybrid' else '#ffffff',
            'ink': '#102734',
            'muted': '#51606f',
        }
    return {
        'primary': '#0e7490',
        'secondary': '#dbeafe',
        'accent': '#102734',
        'panel': '#f8fafc',
        'sheet': '#ffffff',
        'ink': '#111827',
        'muted': '#64748b',
    }


def team_fallback_crest_data_uri(team, fallback_label=''):
    label = (
        str(getattr(team, 'display_name', '') or '').strip()
        or str(getattr(team, 'name', '') or '').strip()
        or str(fallback_label or '').strip()
        or 'Equipo'
    )
    initials = team_initials(label)
    if is_malaga_team(team):
        primary = '#6bc4e8'
        accent = '#004b93'
    else:
        hue = team_color_seed(team)
        primary = hsl_to_hex(hue, 0.68, 0.42)
        accent = hsl_to_hex((hue + 35) % 360, 0.72, 0.32)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{primary}"/>
      <stop offset="100%" stop-color="{accent}"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="160" height="160" rx="32" fill="url(#g)"/>
  <rect x="10" y="10" width="140" height="140" rx="28" fill="rgba(2, 6, 23, 0.18)" stroke="rgba(255,255,255,0.40)" stroke-width="2"/>
  <text x="80" y="92" text-anchor="middle" font-family="Arial, sans-serif" font-size="56" font-weight="900" fill="rgba(255,255,255,0.94)" letter-spacing="2">{html.escape(initials)}</text>
</svg>"""
    encoded = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f'data:image/svg+xml;base64,{encoded}'


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
