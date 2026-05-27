import base64
import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from . import task_choices, workspace_context
from .team_media_services import resolve_team_crest_url
from .drills import drill_cards, normalize_drill_ids
from . import pdf_services
from .models import SessionTask, Team, TrainingSession, TrainingSessionAttendance
from .preview_render import render_task_preview_png
from .services import _parse_int
from .session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields
from .session_import_services import (
    extract_pdf_text as import_extract_pdf_text,
    extract_preview_image_from_pdf as import_extract_preview_image_from_pdf,
)
from .session_canvas_recreate import recreate_canvas_state_from_preview_image_bytes
from .task_library_services import coerce_json_dict, extract_canvas_state_for_preview

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


SESSION_PDF_DELEGATED_VIEW_NAMES = (
    '_build_session_pdf_context',
)


def session_plan_pdf(request, session_id):
    from . import views as core_views
    from .views import (
        _can_access_sessions_workspace,
        _forbid_if_workspace_module_disabled,
    )

    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    forbidden = _forbid_if_workspace_module_disabled(request, 'sessions', label='sesiones')
    if forbidden:
        return forbidden
    session = (
        TrainingSession.objects
        .select_related('microcycle__team')
        .prefetch_related('tasks')
        .filter(id=session_id)
        .first()
    )
    if not session:
        raise Http404('Sesión no encontrada')

    pdf_style = (request.GET.get('style') or 'uefa').strip().lower()
    if pdf_style not in {'uefa', 'club', 'hybrid'}:
        pdf_style = 'uefa'
    force_pdf = str(request.GET.get('force_pdf') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    inline = str(request.GET.get('inline') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    context = build_session_pdf_context(request, session.microcycle.team, session, pdf_style=pdf_style)
    html = render_to_string('football/session_plan_pdf.html', context)
    filename = slugify(f'sesion-{session.session_date}-{session.focus}') or f'sesion-{session.id}'
    if getattr(core_views, 'weasyprint', pdf_services.weasyprint) is None:
        if force_pdf:
            return HttpResponse('PDF no disponible en este servidor.', status=503)
        return HttpResponse(html, content_type='text/html; charset=utf-8')
    return pdf_services.build_pdf_response_or_html_fallback(request, html, filename, inline=inline, force_pdf=force_pdf)


def _build_pdf_nav_urls(request):
    platform_path = reverse('platform-overview')
    try:
        platform_url = request.build_absolute_uri(platform_path)
    except Exception:
        platform_url = platform_path

    raw_return = (request.GET.get('return') or '').strip() or (request.META.get('HTTP_REFERER') or '').strip()
    if not raw_return:
        return {'platform_url': platform_url, 'pdf_return_url': platform_url}
    if raw_return.startswith('/'):
        try:
            return_url = request.build_absolute_uri(raw_return)
        except Exception:
            return_url = raw_return
        return {'platform_url': platform_url, 'pdf_return_url': return_url}

    parsed = urlparse(raw_return)
    if parsed.scheme in {'http', 'https'}:
        try:
            current_host = (request.get_host() or '').split(':', 1)[0].lower()
            target_host = (parsed.netloc or '').split(':', 1)[0].lower()
            if current_host and target_host and current_host != target_host:
                return {'platform_url': platform_url, 'pdf_return_url': platform_url}
        except Exception:
            return {'platform_url': platform_url, 'pdf_return_url': platform_url}
        return {'platform_url': platform_url, 'pdf_return_url': raw_return}

    return {'platform_url': platform_url, 'pdf_return_url': platform_url}


def _coerce_json_dict(value):
    return coerce_json_dict(value)


def _decode_canvas_data_url(data_url):
    value = str(data_url or '').strip()
    if not value or ';base64,' not in value:
        return None, None
    header, encoded = value.split(';base64,', 1)
    mime = header.replace('data:', '').strip().lower()
    allowed_mimes = {
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/webp': '.webp',
    }
    extension = allowed_mimes.get(mime)
    if not extension:
        return None, None
    try:
        raw_bytes = base64.b64decode(encoded)
    except Exception:
        return None, None
    if not raw_bytes:
        return None, None
    return raw_bytes, extension


def _extract_canvas_state_for_preview(task):
    return extract_canvas_state_for_preview(task)


def _extract_preview_image_from_pdf(pdf_file, prefer_render=False):
    return import_extract_preview_image_from_pdf(pdf_file, prefer_render=prefer_render)


def _file_field_as_data_url(file_field):
    if not file_field:
        return ''
    try:
        file_field.open('rb')
        raw = file_field.read()
        file_field.close()
    except Exception:
        return ''
    if not raw:
        return ''
    ext = Path(getattr(file_field, 'name', '') or '').suffix.lower()
    mime = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
    }.get(ext, 'image/jpeg')
    return f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}"


def _get_primary_team_for_request(request):
    team = workspace_context.get_active_team_for_request(request)
    if team:
        return team
    try:
        return workspace_context.team_from_request_param(request)
    except Exception:
        return None


def _is_benagalbon_team(team):
    if not team:
        return False
    if bool(getattr(team, 'is_primary', False)):
        return True
    slug = str(getattr(team, 'slug', '') or '').strip().lower()
    name = str(getattr(team, 'name', '') or '').strip().lower()
    short_name = str(getattr(team, 'short_name', '') or '').strip().lower()
    return 'benagalbon' in slug or 'benagalbon' in name or 'benagalbon' in short_name


def _is_imported_task(task):
    if not task:
        return False
    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    source = str(meta.get('source') or '').strip().lower()
    if source in {'manual-studio', 'manual', 'studio'}:
        if bool(getattr(task, 'task_pdf', None)) or str(meta.get('pdf_source_name') or '').strip() or bool(meta.get('import_mode')):
            return True
        return False
    if source in {'pdf_analysis', 'pdf_import', 'pdf'}:
        return True
    if str(meta.get('pdf_source_name') or '').strip():
        return True
    try:
        notes = str(getattr(task, 'notes', '') or '').strip().lower()
    except Exception:
        notes = ''
    if bool(getattr(task, 'task_pdf', None)):
        if any(
            token in notes
            for token in (
                'cargada desde biblioteca pdf',
                'importada desde pdf',
                'extraída automáticamente desde pdf',
                'importada desde captura',
            )
        ):
            return True
        return True
    return False


def _normalize_folded_text(value):
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def _parse_session_plan_fields(raw_content):
    return parse_session_plan_fields(raw_content)


def _file_as_data_uri(file_path):
    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ''
        ext = path.suffix.lower()
        mime_type = {
            '.svg': 'image/svg+xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
        }.get(ext, 'application/octet-stream')
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'data:{mime_type};base64,{encoded}'
    except Exception:
        return ''


def _static_asset_as_data_uri(static_path: str) -> str:
    static_path = str(static_path or '').lstrip('/').strip()
    if not static_path:
        return ''
    try:
        source = Path(settings.BASE_DIR) / 'static' / static_path
    except Exception:
        return ''
    return _file_as_data_uri(source)


def _normalize_hex_color(value: object, fallback: str = '#0f7a35') -> str:
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


def _static_svg_asset_as_recolored_data_uri(static_path: str, stroke_color: str) -> str:
    static_path = str(static_path or '').lstrip('/').strip()
    if not static_path:
        return ''
    try:
        source = Path(settings.BASE_DIR) / 'static' / static_path
    except Exception:
        return ''
    if not source.exists() or not source.is_file():
        return ''
    try:
        raw_bytes = source.read_bytes()
    except Exception:
        return ''
    if not stroke_color or not static_path.lower().endswith('.svg'):
        return _file_as_data_uri(source)
    try:
        svg_text = raw_bytes.decode('utf-8', errors='ignore')
        color = _normalize_hex_color(stroke_color, '#0f7a35')
        svg_text = re.sub(r'stroke=(["\'])(#[0-9a-fA-F]{3,6})\1', f'stroke="{color}"', svg_text)
        svg_text = re.sub(r'fill=(["\'])(#[0-9a-fA-F]{3,6})\1', f'fill="{color}"', svg_text)
        encoded = base64.b64encode(svg_text.encode('utf-8')).decode('ascii')
        return f'data:image/svg+xml;base64,{encoded}'
    except Exception:
        return _file_as_data_uri(source)


def _task_drills_for_pdf(meta):
    if not isinstance(meta, dict):
        return []
    drill_ids = normalize_drill_ids(meta.get('drills'))
    if not drill_ids:
        return []
    cards = []
    drills_color = _normalize_hex_color(meta.get('drills_icon_color') or '', '#0f7a35')
    for card in drill_cards(drill_ids):
        icon_path = card.get('icon_static_path')
        icon_uri = _static_svg_asset_as_recolored_data_uri(icon_path, drills_color)
        if not icon_uri:
            icon_uri = _static_asset_as_data_uri(icon_path)
        cards.append(
            {
                'id': card.get('id'),
                'label': card.get('label'),
                'category': card.get('category'),
                'icon_url': icon_uri,
            }
        )
    return cards



def _team_color_seed(team):
    base = str(getattr(team, 'slug', '') or getattr(team, 'name', '') or '').strip().lower()
    if not base:
        base = str(getattr(team, 'id', '') or 'team')
    total = 0
    for ch in base:
        total = (total * 31 + ord(ch)) % 360
    return total


def _team_initials(label):
    text = ' '.join(str(label or '').split()).strip()
    if not text:
        return '??'
    tokens = [tok for tok in re.split(r'[^A-Za-z0-9]+', text) if tok]
    if not tokens:
        return (text[:2] if len(text) >= 2 else text).upper()
    if len(tokens) == 1:
        return (tokens[0][:2] if len(tokens[0]) >= 2 else tokens[0]).upper()
    return (tokens[0][0] + tokens[1][0]).upper()


def _team_pdf_palette(team_obj, style_key='uefa'):
    primary = str(getattr(team_obj, 'primary_color', '') or '').strip() or '#0f7a35'
    secondary = str(getattr(team_obj, 'secondary_color', '') or '').strip() or '#facc15'
    accent = str(getattr(team_obj, 'accent_color', '') or '').strip() or '#102734'
    if style_key in {'club', 'hybrid'}:
        if _is_benagalbon_team(team_obj):
            return {
                'primary': '#007050',
                'secondary': '#008048',
                'accent': '#063b31',
                'panel': '#eff7f4',
                'sheet': '#f6f7f5' if style_key == 'hybrid' else '#ffffff',
                'ink': '#0b1f1a',
                'muted': '#3b5a54',
            }
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


def _normalize_task_pdf_meta(meta):
    def _normalize_meta_key(raw_key):
        text = str(raw_key or '').strip()
        if not text:
            return ''
        text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
        text = text.replace(' ', '_').replace('-', '_')
        text = re.sub(r'[^a-zA-Z0-9_]', '', text)
        text = re.sub(r'__+', '_', text).strip('_').lower()
        return text

    def _normalize_meta_dict(raw_value):
        if not isinstance(raw_value, dict):
            return {}
        normalized = {}
        for key, value in raw_value.items():
            normalized_key = _normalize_meta_key(key)
            if not normalized_key:
                continue
            if isinstance(value, dict):
                normalized_value = _normalize_meta_dict(value)
            elif isinstance(value, list):
                normalized_value = [
                    _normalize_meta_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                normalized_value = value
            existing = normalized.get(normalized_key)
            if existing in (None, '', [], {}) and normalized_value not in (None, '', [], {}):
                normalized[normalized_key] = normalized_value
            elif normalized_key not in normalized:
                normalized[normalized_key] = normalized_value
        return normalized

    def _map_choice(value, mapping):
        raw = str(value or '').strip()
        if not raw:
            return raw
        if raw in mapping:
            return mapping.get(raw, raw)
        lowered = raw.lower()
        if lowered in mapping:
            return mapping.get(lowered, raw)
        normalized = lowered.replace(' ', '_').replace('-', '_')
        if normalized in mapping:
            return mapping.get(normalized, raw)
        normalized_key = _normalize_meta_key(raw)
        if normalized_key in mapping:
            return mapping.get(normalized_key, raw)
        return raw

    surface_map = {key: label for key, label in task_choices.TASK_SURFACE_CHOICES}
    pitch_map = {key: label for key, label in task_choices.TASK_PITCH_FORMAT_CHOICES}
    phase_map = {key: label for key, label in task_choices.TASK_GAME_PHASE_CHOICES}
    methodology_map = {key: label for key, label in task_choices.TASK_METHODOLOGY_CHOICES}
    complexity_map = {key: label for key, label in task_choices.TASK_COMPLEXITY_CHOICES}
    constraint_map = {key: label for key, label in task_choices.TASK_CONSTRAINT_CHOICES}
    strategy_map = {key: label for key, label in task_choices.TASK_STRATEGY_CHOICES}
    coordination_map = {key: label for key, label in task_choices.TASK_COORDINATION_CHOICES}
    coord_skills_map = {key: label for key, label in task_choices.TASK_COORDINATION_SKILLS_CHOICES}
    tactical_intent_map = {key: label for key, label in task_choices.TASK_TACTICAL_INTENT_CHOICES}
    dynamics_map = {key: label for key, label in task_choices.TASK_DYNAMICS_CHOICES}
    structure_map = {key: label for key, label in task_choices.TASK_STRUCTURE_CHOICES}
    meta = _normalize_meta_dict(meta or {})
    # Compat: algunas importaciones/analíticas guardan claves en castellano.
    # Unificamos para que el PDF siempre muestre etiquetas correctas.
    key_aliases = {
        'estrategia': 'strategy',
        'dinamica': 'dynamics',
        'situacion_de_juego': 'structure',
        'situacion_juego': 'structure',
        'habilidades_coordinativas': 'coordination_skills',
        'habilidades_coordinativas_y': 'coordination_skills',
        'intencion_accion_tactica': 'tactical_intent',
        'intencion_accion': 'tactical_intent',
        'coordinacion': 'coordination',
        'complejidad': 'complexity',
    }
    for alias_key, canonical_key in key_aliases.items():
        if alias_key in meta and canonical_key not in meta:
            meta[canonical_key] = meta.get(alias_key)
    if not meta:
        return {}
    if not meta.get('strategy') and meta.get('training_type'):
        strategy_candidate = _map_choice(meta.get('training_type'), strategy_map)
        training_type_key = str(meta.get('training_type') or '').strip().lower().replace(' ', '_').replace('-', '_')
        if training_type_key in strategy_map or strategy_candidate in strategy_map.values():
            meta['strategy'] = strategy_candidate
    if meta.get('surface'):
        meta['surface'] = _map_choice(meta.get('surface'), surface_map) or str(meta.get('surface'))
    if meta.get('pitch_format'):
        meta['pitch_format'] = _map_choice(meta.get('pitch_format'), pitch_map) or str(meta.get('pitch_format'))
    if meta.get('game_phase'):
        meta['game_phase'] = _map_choice(meta.get('game_phase'), phase_map) or str(meta.get('game_phase'))
    if meta.get('methodology'):
        meta['methodology'] = _map_choice(meta.get('methodology'), methodology_map) or str(meta.get('methodology'))
    if meta.get('complexity'):
        meta['complexity'] = _map_choice(meta.get('complexity'), complexity_map) or str(meta.get('complexity'))
    if meta.get('strategy'):
        meta['strategy'] = _map_choice(meta.get('strategy'), strategy_map) or str(meta.get('strategy'))
    if meta.get('coordination'):
        meta['coordination'] = _map_choice(meta.get('coordination'), coordination_map) or str(meta.get('coordination'))
    if meta.get('coordination_skills'):
        meta['coordination_skills'] = _map_choice(meta.get('coordination_skills'), coord_skills_map) or str(meta.get('coordination_skills'))
    if meta.get('tactical_intent'):
        meta['tactical_intent'] = _map_choice(meta.get('tactical_intent'), tactical_intent_map) or str(meta.get('tactical_intent'))
    if meta.get('dynamics'):
        meta['dynamics'] = _map_choice(meta.get('dynamics'), dynamics_map) or str(meta.get('dynamics'))
    if meta.get('structure'):
        meta['structure'] = _map_choice(meta.get('structure'), structure_map) or str(meta.get('structure'))
    if isinstance(meta.get('constraints'), list):
        meta['constraints'] = [_map_choice(v, constraint_map) or str(v) for v in meta.get('constraints')]
    if isinstance(meta.get('category_tags'), str):
        meta['category_tags'] = [item.strip() for item in str(meta.get('category_tags') or '').split(',') if item.strip()]
    elif not isinstance(meta.get('category_tags'), list):
        meta['category_tags'] = []
    if isinstance(meta.get('assigned_player_names'), str):
        meta['assigned_player_names'] = [item.strip() for item in str(meta.get('assigned_player_names') or '').split(',') if item.strip()]
    elif not isinstance(meta.get('assigned_player_names'), list):
        meta['assigned_player_names'] = []
    return meta


def _build_session_task_sheet(task):
    meta = _normalize_task_pdf_meta(task.tactical_layout.get('meta') if isinstance(task.tactical_layout, dict) else {})
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
    source_template_id = _parse_int(meta.get('library_source_task_id')) or 0
    is_template = str(meta.get('is_template') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    origin_label = 'Plantilla' if is_template else ('Copia' if source_template_id else '')
    contents = []
    for value in [
        meta.get('training_type'),
        meta.get('game_phase'),
        meta.get('principle'),
        meta.get('subprinciple'),
    ]:
        text = str(value or '').strip()
        if text:
            contents.append(text)
    return {
        'title': str(task.title or '').strip() or f'Tarea {task.id}',
        'block_label': task.get_block_display(),
        'minutes': int(task.duration_minutes or 0),
        'type_label': str(meta.get('training_type') or '').strip(),
        'origin_label': origin_label,
        'origin_template_id': int(source_template_id) if source_template_id else None,
        'contents_label': ' · '.join(contents) or str(task.objective or '').strip() or '-',
        'structure_label': ' · '.join(
            part for part in [
                str(meta.get('organization') or '').strip(),
                str(meta.get('players_distribution') or '').strip(),
                str(meta.get('player_count') or '').strip(),
            ] if part
        ) or '-',
        'players_label': ', '.join(meta.get('assigned_player_names') or []) or str(meta.get('player_count') or '').strip() or '-',
        'dimensions_label': str(task_sheet.get('dimensions') or meta.get('space') or '').strip() or '-',
        'materials_label': str(task_sheet.get('materials') or meta.get('resources_summary') or '').strip() or '-',
        'description': str(task_sheet.get('description') or '').strip(),
        'rules': str(task.confrontation_rules or '').strip(),
        'focus': str(task.coaching_points or '').strip(),
        'variants': str(meta.get('progression') or '').strip(),
        'success': str(meta.get('success_criteria') or '').strip(),
        'coordination_label': str(meta.get('coordination') or '').strip(),
        'coordination_skills_label': str(meta.get('coordination_skills') or meta.get('coordination_skills_label') or '').strip(),
        'tactical_intent_label': str(meta.get('tactical_intent') or '').strip(),
    }


def build_session_pdf_context(request, team, session, pdf_style='uefa'):
    def _safe_pdf_image_data_url(data_url: str, *, max_bytes: int = 6_000_000, max_side: int = 1800) -> str:
        """
        Normaliza imágenes embebidas para WeasyPrint.

        Motivo: ciertos binarios corruptos o extremadamente grandes pueden hacer que el motor
        nativo de imágenes (gdk-pixbuf/cairo) falle de forma no recuperable (500).
        Preferimos degradar a "sin representación gráfica" antes que tumbar el endpoint.
        """
        raw = str(data_url or '').strip()
        if not raw.startswith('data:image/') or ';base64,' not in raw:
            return raw
        raw_bytes, _ext = _decode_canvas_data_url(raw)
        if not raw_bytes:
            return ''
        if len(raw_bytes) > int(max_bytes or 0):
            return ''
        if Image is None:
            return raw
        try:
            import io as _io  # noqa: WPS433

            with Image.open(_io.BytesIO(raw_bytes)) as img:
                # Aplanamos sobre blanco para evitar problemas con alpha/transparencia.
                rgba = img.convert('RGBA')
                flat = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                try:
                    flat.alpha_composite(rgba)
                except Exception:
                    flat.paste(rgba, (0, 0), rgba)
                rgb = flat.convert('RGB')
                rgb.thumbnail((max(320, int(max_side)), max(320, int(max_side))))
                out = _io.BytesIO()
                rgb.save(out, format='JPEG', quality=84, optimize=True, progressive=True)
                payload = base64.b64encode(out.getvalue()).decode('ascii')
                return 'data:image/jpeg;base64,' + payload
        except Exception:
            return ''

    # Mantén el mismo orden que la "ficha de sesión" (training_session_detail_page):
    # orden por bloque/fase + orden dentro de bloque.
    tasks = list(session.tasks.filter(deleted_at__isnull=True).order_by('block', 'order', 'id'))
    block_order = [
        SessionTask.BLOCK_CONDITIONING,
        SessionTask.BLOCK_ACTIVATION,
        SessionTask.BLOCK_MAIN_1,
        SessionTask.BLOCK_MAIN_2,
        SessionTask.BLOCK_SET_PIECES,
        SessionTask.BLOCK_RECOVERY,
        SessionTask.BLOCK_VIDEO,
    ]
    block_rank = {key: idx for idx, key in enumerate(block_order)}
    tasks.sort(
        key=lambda t: (
            block_rank.get(str(getattr(t, 'block', '') or ''), 999),
            int(getattr(t, 'order', 0) or 0),
            int(getattr(t, 'id', 0) or 0),
        )
    )
    total_task_minutes = sum(int(getattr(task, 'duration_minutes', 0) or 0) for task in tasks)
    session_plan_fields = _parse_session_plan_fields(getattr(session, 'content', ''))
    coach_name = (
        request.user.get_full_name().strip()
        if hasattr(request.user, 'get_full_name') and request.user.get_full_name().strip()
        else getattr(request.user, 'username', '') or 'Entrenador'
    )
    primary_club_team = _get_primary_team_for_request(request) or Team.objects.filter(is_primary=True).first()
    club_logo_url = resolve_team_crest_url(request, primary_club_team, sync=True) if primary_club_team else ''
    # Para PDF "club" preferimos un escudo embebido (data URL) para evitar fallos de fetch/red en WeasyPrint.
    def _small_png_data_url(raw_bytes: bytes, *, max_side: int = 220) -> str:
        try:
            from io import BytesIO  # noqa: WPS433
            from PIL import Image  # noqa: WPS433

            bio = BytesIO(raw_bytes or b"")
            img = Image.open(bio)
            img = img.convert("RGBA")
            img.thumbnail((max_side, max_side))
            out = BytesIO()
            img.save(out, format="PNG", optimize=True)
            payload = base64.b64encode(out.getvalue()).decode("ascii")
            return "data:image/png;base64," + payload
        except Exception:
            return ''
    team_logo_url = ''
    try:
        if getattr(team, 'crest_image', None):
            team_logo_url = _file_field_as_data_url(getattr(team, 'crest_image', None)) or ''
            if team_logo_url.startswith('data:image/') and ';base64,' in team_logo_url:
                try:
                    header, payload = team_logo_url.split(';base64,', 1)
                    raw = base64.b64decode(payload.encode('ascii'))
                    team_logo_url = _small_png_data_url(raw, max_side=220) or team_logo_url
                except Exception:
                    pass
    except Exception:
        team_logo_url = ''
    if not team_logo_url and _is_benagalbon_team(team):
        try:
            crest_path = Path(getattr(settings, 'BASE_DIR', Path.cwd())) / 'static' / 'football' / 'images' / 'cdb-benagalbon-crest-pdf.png'
            raw = crest_path.read_bytes()
            if raw:
                team_logo_url = _small_png_data_url(raw, max_side=220) or ("data:image/png;base64," + base64.b64encode(raw).decode("ascii"))
        except Exception:
            team_logo_url = ''
    if not team_logo_url:
        try:
            hue = _team_color_seed(team)
            initials = _team_initials(getattr(team, 'display_name', '') or getattr(team, 'name', '') or '')
            crest_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="hsl({hue}, 70%, 42%)"/>
      <stop offset="100%" stop-color="hsl({(hue + 35) % 360}, 74%, 36%)"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="160" height="160" rx="32" fill="url(#g)"/>
  <rect x="10" y="10" width="140" height="140" rx="28" fill="rgba(2, 6, 23, 0.25)" stroke="rgba(255,255,255,0.26)" stroke-width="2"/>
  <text x="80" y="92" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="56" font-weight="800" fill="rgba(255,255,255,0.92)" letter-spacing="2">{html.escape(str(initials or '').strip())}</text>
</svg>"""
            team_logo_url = "data:image/svg+xml;base64," + base64.b64encode(crest_svg.encode("utf-8")).decode("ascii")
        except Exception:
            team_logo_url = ''
    def _static_data_url(static_path: str, mime: str) -> str:
        try:
            from django.contrib.staticfiles import finders  # noqa: WPS433

            disk_path = finders.find(static_path)
            if not disk_path:
                return ''
            raw = Path(disk_path).read_bytes()
            if not raw:
                return ''
            return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
        except Exception:
            return ''

    uefa_badge_url = _static_data_url('football/images/uefa-badge.svg', 'image/svg+xml') or request.build_absolute_uri(static('football/images/uefa-badge.svg'))
    brand_mark_data_url = _static_data_url('football/images/2j-mark.svg', 'image/svg+xml')
    club_dragon_data_url = _static_data_url('football/images/cdb-dragon-watermark.png', 'image/png') if (pdf_style in {'club', 'hybrid'} and _is_benagalbon_team(team)) else ''
    task_sheets = [_build_session_task_sheet(task) for task in tasks]

    valid_blocks = {choice[0] for choice in SessionTask.BLOCK_CHOICES}

    def _infer_task_block_for_pdf(task, meta: dict) -> str:
        """
        Inferir bloque/fase cuando la tarea viene importada desde PDF y el bloque quedó en default.

        Caso real: PDFs "sesión" con varias tareas (calentamiento, activación, principal, vuelta a la calma).
        Si el usuario sube el PDF sin asignar bloque, todas quedan como Principal 1 y el PDF sale “desordenado”.
        """
        stored = str(getattr(task, 'block', '') or '').strip()
        if stored not in valid_blocks:
            stored = SessionTask.BLOCK_MAIN_1
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        phase_tags = analysis_meta.get('phase_tags') if isinstance(analysis_meta.get('phase_tags'), list) else []
        phase_tags = [str(tag or '').strip().lower() for tag in phase_tags if str(tag or '').strip()]

        hint_parts = [
            str(getattr(task, 'title', '') or '').strip(),
            str(meta.get('pdf_segment_excerpt') or '').strip(),
            str(analysis_meta.get('summary') or '').strip(),
        ]
        try:
            sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
            hint_parts.append(str(sheet.get('description') or '').strip())
        except Exception:
            pass
        hint = '\n'.join([p for p in hint_parts if p]).strip()
        folded = _normalize_folded_text(hint)

        def _has_any(*tokens: str) -> bool:
            return any(token in folded for token in tokens if token)

        inferred = ''

        # Cooldown / recuperación.
        if _has_any(
            'vueltacalma',
            'vueltaalacalma',
            'enfriamiento',
            'cooldown',
            'cool down',
            'estiramiento',
            'compensacion',
            'compensación',
            'recuperacion',
            'recuperación',
            'bajadapulsaciones',
            'relajacion',
            'relajación',
        ):
            inferred = SessionTask.BLOCK_RECOVERY

        # ABP.
        if not inferred and ('abp' in phase_tags or _has_any('abp', 'balonparado', 'balónparado', 'corner', 'saquedeesquina', 'faltalateral')):
            inferred = SessionTask.BLOCK_SET_PIECES

        # Warmup (Condicionante) vs Activación.
        if not inferred and _has_any('calentamiento', 'acondicionamiento', 'entradaencalor'):
            inferred = SessionTask.BLOCK_CONDITIONING
        if not inferred and ('activacion' in phase_tags or _has_any('activacion', 'activación', 'movilidad')):
            inferred = SessionTask.BLOCK_ACTIVATION

        # Principal 2 / Principal 1.
        if not inferred and _has_any('principal2', 'parteprincipal2', 'pp2', 'principal ii', 'principal 2'):
            inferred = SessionTask.BLOCK_MAIN_2
        if not inferred and _has_any('principal1', 'parteprincipal1', 'pp1', 'principal i', 'principal 1'):
            inferred = SessionTask.BLOCK_MAIN_1
        if not inferred and _has_any('parteprincipal', 'parte principal'):
            inferred = SessionTask.BLOCK_MAIN_1

        if not inferred and _has_any('video', 'vídeo'):
            inferred = SessionTask.BLOCK_VIDEO

        if inferred and inferred in valid_blocks:
            if _is_imported_task(task) and stored == SessionTask.BLOCK_MAIN_1 and inferred != stored:
                return inferred
        return stored

    def _task_preview_data_url_for_pdf(task):
        def _autocrop_preview_data_url(data_url: str) -> str:
            """
            Centra la pizarra eliminando márgenes blancos del PNG/JPEG.

            En algunos renders (según preset/zoom/orientación) el preview puede tener un área en blanco a la
            derecha/abajo. WeasyPrint centrará el <img>, pero si el "blanco" está dentro del propio bitmap,
            la pizarra seguirá viéndose desplazada. Autocrop arregla esto para el PDF UEFA.
            """
            if pdf_style == 'club':
                return data_url
            raw = str(data_url or '')
            if not raw.startswith('data:image/') or ';base64,' not in raw:
                return data_url
            try:
                header, payload = raw.split(';base64,', 1)
                mime = header.split(':', 1)[1].strip().lower()
                if mime not in {'image/png', 'image/jpeg', 'image/jpg', 'image/webp'}:
                    return data_url
                blob = base64.b64decode(payload.encode('ascii'))
            except Exception:
                return data_url
            try:
                from io import BytesIO  # noqa: WPS433
                from PIL import Image, ImageChops  # noqa: WPS433

                img = Image.open(BytesIO(blob))
                # Aplanamos sobre blanco para que el recorte funcione también con transparencia.
                rgba = img.convert('RGBA')
                flat = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                try:
                    flat.alpha_composite(rgba)
                except Exception:
                    # Compat: alpha_composite puede fallar en algunas modes.
                    flat.paste(rgba, (0, 0), rgba)
                rgb = flat.convert('RGB')
                bg = Image.new('RGB', rgb.size, (255, 255, 255))
                diff = ImageChops.difference(rgb, bg)
                # Filtra "casi blanco" para evitar que fondos #f5f5f5 o antialiasing impidan el recorte.
                diff_l = diff.convert('L').point(lambda p: 255 if p > 12 else 0)
                bbox = diff_l.getbbox()
                if not bbox:
                    return data_url
                pad = 10
                left = max(0, int(bbox[0]) - pad)
                top = max(0, int(bbox[1]) - pad)
                right = min(rgb.size[0], int(bbox[2]) + pad)
                bottom = min(rgb.size[1], int(bbox[3]) + pad)
                cropped = rgb.crop((left, top, right, bottom))
                out = BytesIO()
                cropped.save(out, format='PNG', optimize=True)
                return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
            except Exception:
                return data_url

        # 1) Imagen ya guardada.
        preview = _file_field_as_data_url(getattr(task, 'task_preview_image', None))
        if preview:
            return _autocrop_preview_data_url(preview)
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        if isinstance(layout, str):
            layout = _coerce_json_dict(layout) or {}
        if not isinstance(layout, dict):
            layout = {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        canvas_state, canvas_width, canvas_height = _extract_canvas_state_for_preview(task)
        # 2) Render server-side desde canvas_state (más robusto que depender de ficheros).
        if canvas_state and isinstance(canvas_state, dict) and canvas_state.get('objects'):
            try:
                pitch_preset = str(meta.get('pitch_preset') or 'full_pitch').strip() or 'full_pitch'
                pitch_orientation = str(meta.get('pitch_orientation') or 'landscape').strip().lower()
                pitch_grass_style = str(meta.get('pitch_grass_style') or 'classic').strip().lower()
                if pitch_grass_style not in {'classic', 'broadcast', 'realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'whiteboard', 'blackboard'}:
                    pitch_grass_style = 'classic'
                # En PDF no queremos recortes por zoom: forzamos a 1.0.
                pitch_zoom = 1.0
                canvas_width = max(320, min(_parse_int(canvas_width) or 1280, 3840))
                canvas_height = max(180, min(_parse_int(canvas_height) or 720, 2160))
                png_bytes = render_task_preview_png(
                    canvas_state=canvas_state,
                    pitch_preset=pitch_preset,
                    pitch_orientation="portrait" if pitch_orientation == "portrait" else "landscape",
                    pitch_grass_style=pitch_grass_style,
                    pitch_zoom=pitch_zoom,
                    world_width=canvas_width,
                    world_height=canvas_height,
                    max_side=3200,
                )
                if png_bytes:
                    return _autocrop_preview_data_url("data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"))
            except Exception:
                pass
        # 3) Fallback: extraer preview del PDF si existe.
        pdf_field = getattr(task, 'task_pdf', None)
        if pdf_field:
            try:
                payload = _extract_preview_image_from_pdf(pdf_field, prefer_render=True)
                if payload:
                    name, content = payload
                    try:
                        content.seek(0)
                    except Exception:
                        pass
                    raw = content.read() or b''
                    if raw:
                        ext = str(name or '').rsplit('.', 1)[-1].lower()
                        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}.get(ext, 'image/png')
                        return _autocrop_preview_data_url(f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"))
            except Exception:
                pass
        return ''

    task_cards = []
    for idx, task in enumerate(tasks):
        sheet = task_sheets[idx] if idx < len(task_sheets) else _build_session_task_sheet(task)
        preview_url = _safe_pdf_image_data_url(_task_preview_data_url_for_pdf(task))
        meta = {}
        try:
            if isinstance(getattr(task, 'tactical_layout', None), dict):
                meta = task.tactical_layout.get('meta') if isinstance(task.tactical_layout.get('meta'), dict) else {}
        except Exception:
            meta = {}
        effective_block = _infer_task_block_for_pdf(task, meta if isinstance(meta, dict) else {})
        task_cards.append(
            {
                'task': task,
                'sheet': sheet,
                'preview_url': preview_url,
                'drills': _task_drills_for_pdf(meta),
                'effective_block': effective_block,
            }
        )
    # Orden estándar de sesión: Calentamiento → Activación → Principal 1 → Principal 2 → Vuelta a la calma.
    section_specs = [
        {'key': 'warmup', 'label': 'Calentamiento', 'blocks': [SessionTask.BLOCK_CONDITIONING]},
        {'key': 'activation', 'label': 'Activación', 'blocks': [SessionTask.BLOCK_ACTIVATION]},
        {'key': 'main_1', 'label': 'Principal 1', 'blocks': [SessionTask.BLOCK_MAIN_1]},
        # ABP se considera dentro de "Principal 2" para mantener el orden esperado por el entrenador.
        {'key': 'main_2', 'label': 'Principal 2', 'blocks': [SessionTask.BLOCK_MAIN_2, SessionTask.BLOCK_SET_PIECES]},
        {'key': 'cooldown', 'label': 'Vuelta a la calma', 'blocks': [SessionTask.BLOCK_RECOVERY]},
    ]
    known_blocks = {block for spec in section_specs for block in spec['blocks']}
    task_sections = []
    for spec in section_specs:
        cards = [card for card in task_cards if str(card.get('effective_block') or getattr(card['task'], 'block', '') or '') in set(spec['blocks'])]
        cards.sort(key=lambda c: (int(getattr(c.get('task'), 'order', 0) or 0), int(getattr(c.get('task'), 'id', 0) or 0)))
        if cards:
            task_sections.append({'key': spec['key'], 'label': spec['label'], 'cards': cards})
    other_cards = [card for card in task_cards if str(card.get('effective_block') or getattr(card['task'], 'block', '') or '') not in known_blocks]
    other_cards.sort(key=lambda c: (int(getattr(c.get('task'), 'order', 0) or 0), int(getattr(c.get('task'), 'id', 0) or 0)))
    if other_cards:
        task_sections.append({'key': 'other', 'label': 'Otros', 'cards': other_cards})
    # Sugerencias para plantilla UEFA (no bloqueante).
    session_materials_summary = ', '.join(
        sorted(
            {
                str(sheet.get('materials_label') or '').strip()
                for sheet in task_sheets
                if str(sheet.get('materials_label') or '').strip() and str(sheet.get('materials_label') or '').strip() != '-'
            }
        )
    )
    session_objectives_summary = str(session.focus or '').strip()
    session_materials_override = str(session_plan_fields.get('materials') or '').strip()
    if session_materials_override:
        session_materials_summary = session_materials_override
    def _attendance_incidents_summary() -> str:
        """
        Convierte las marcas de asistencia (Ausente/Tarde/Lesionado/Justificado) en un resumen legible.

        Objetivo: que el PDF refleje lo marcado en "Asistencia" aunque el staff no copie/pegue a mano.
        """
        try:
            marks = list(
                TrainingSessionAttendance.objects
                .select_related('player')
                .filter(session=session)
                .exclude(status=TrainingSessionAttendance.STATUS_PRESENT)
                .order_by('player__number', 'player__name', 'id')
            )
        except Exception:
            marks = []
        if not marks:
            return ''
        buckets = {
            TrainingSessionAttendance.STATUS_ABSENT: [],
            TrainingSessionAttendance.STATUS_LATE: [],
            TrainingSessionAttendance.STATUS_INJURED: [],
            TrainingSessionAttendance.STATUS_EXCUSED: [],
        }
        for m in marks:
            st = str(getattr(m, 'status', '') or '').strip()
            if st not in buckets:
                continue
            p = getattr(m, 'player', None)
            if not p:
                continue
            try:
                num = int(getattr(p, 'number', 0) or 0) or 0
            except Exception:
                num = 0
            label = f'#{num} {p.name}'.strip() if num else str(getattr(p, 'name', '') or '').strip()
            note = str(getattr(m, 'notes', '') or '').strip()
            if note:
                label = f'{label} ({note})'
            buckets[st].append(label or 'Jugador')

        prefix = {
            TrainingSessionAttendance.STATUS_ABSENT: 'Ausentes',
            TrainingSessionAttendance.STATUS_LATE: 'Tarde',
            TrainingSessionAttendance.STATUS_INJURED: 'Lesionados',
            TrainingSessionAttendance.STATUS_EXCUSED: 'Justificados',
        }
        lines = []
        for key in [
            TrainingSessionAttendance.STATUS_ABSENT,
            TrainingSessionAttendance.STATUS_LATE,
            TrainingSessionAttendance.STATUS_INJURED,
            TrainingSessionAttendance.STATUS_EXCUSED,
        ]:
            items = buckets.get(key) or []
            if not items:
                continue
            lines.append(f'{prefix.get(key, key)}: {", ".join(items)}')
        return '\n'.join(lines).strip()

    session_absences_summary = str(session_plan_fields.get('absences') or '').strip()
    if not session_absences_summary:
        session_absences_summary = str(session_plan_fields.get('notes') or '').strip()
    attendance_incidents = _attendance_incidents_summary()
    if attendance_incidents:
        if session_absences_summary:
            if attendance_incidents not in session_absences_summary:
                session_absences_summary = (session_absences_summary.strip() + '\n' + attendance_incidents).strip()
        else:
            session_absences_summary = attendance_incidents
    session_player_count_display = str(session_plan_fields.get('player_count') or '').strip()
    if not session_player_count_display:
        assigned_ids = set()
        for task in tasks:
            layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
            meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
            raw_ids = meta.get('assigned_player_ids')
            if not isinstance(raw_ids, list):
                continue
            for raw_id in raw_ids:
                pid = _parse_int(raw_id)
                if pid:
                    assigned_ids.add(pid)
        if assigned_ids:
            session_player_count_display = str(len(assigned_ids))
    if not session_player_count_display:
        session_player_count_display = '-'
    session_display_name = str(getattr(session, 'focus', '') or '').strip()
    microcycle_display_title = str(getattr(getattr(session, 'microcycle', None), 'title', '') or '').strip()
    try:
        if session_display_name.lower().startswith('biblioteca pdf'):
            session_display_name = 'Repositorio de tareas (PDF)'
        if microcycle_display_title.lower().startswith('biblioteca '):
            microcycle_display_title = 'Repositorio'
    except Exception:
        pass
    return {
        **_build_pdf_nav_urls(request),
        'team_name': team.name,
        'session': session,
        'microcycle': session.microcycle,
        'session_display_name': session_display_name,
        'microcycle_display_title': microcycle_display_title,
        'session_plan_fields': session_plan_fields,
        'session_notes': str(session_plan_fields.get('notes') or '').strip(),
        'tasks': tasks,
        'task_sheets': task_sheets,
        'task_cards': task_cards,
        'task_sections': task_sections,
        'tasks_count': len(tasks),
        'task_minutes_total': total_task_minutes,
        'pdf_style': pdf_style,
        'pdf_palette': _team_pdf_palette(team, pdf_style),
        'coach_name': coach_name,
        'logo_url': team_logo_url if pdf_style in {'club', 'hybrid'} else uefa_badge_url,
        'brand_mark_url': brand_mark_data_url or request.build_absolute_uri(static('football/images/2j-mark.svg')),
        'club_dragon_url': club_dragon_data_url,
        'club_logo_url': club_logo_url,
        'generated_at': timezone.localtime(),
        'intensity_label': dict(TrainingSession.INTENSITY_CHOICES).get(session.intensity, session.intensity or '-'),
        'status_label': dict(TrainingSession.STATUS_CHOICES).get(session.status, session.status or '-'),
        'session_materials_summary': session_materials_summary,
        'session_objectives_summary': session_objectives_summary,
        'session_absences_summary': session_absences_summary,
        'session_player_count_display': session_player_count_display,
    }


def extract_pdf_text(pdf_file, max_chars=12000):
    return import_extract_pdf_text(pdf_file, max_chars=max_chars)
