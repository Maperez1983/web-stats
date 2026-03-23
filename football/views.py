import json
import os
import subprocess
import sys
import base64
import mimetypes
import io
import csv
import zipfile
import uuid
import tempfile
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timedelta, time
from functools import wraps
from pathlib import Path
import unicodedata
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    import weasyprint
except Exception:  # pragma: no cover
    weasyprint = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

from football.models import (
    Match,
    MatchEvent,
    Player,
    PlayerInjuryRecord,
    PlayerCommunication,
    PlayerFine,
    PlayerPhysicalMetric,
    PlayerStatistic,
    SessionTask,
    ScrapeSource,
    Season,
    Team,
    TeamStanding,
    TrainingMicrocycle,
    TrainingSession,
    ConvocationRecord,
    HomeCarouselImage,
    RivalVideo,
    RivalAnalysisReport,
    AppUserRole,
    UserInvitation,
    TaskBlueprint,
)
from football.event_taxonomy import (
    DRIBBLE_KEYWORDS,
    FIELD_ZONE_KEYS,
    FIELD_ZONES,
    PASS_KEYWORDS,
    SHOT_KEYWORDS,
    STANDARD_TERCIO_LABELS,
    build_smart_kpis,
    categorize_position,
    classify_duel_event,
    contains_keyword,
    extract_round_number,
    is_assist_event,
    is_goal_event,
    is_goalkeeper_save_event,
    is_red_card_event,
    is_substitution_entry,
    is_substitution_event,
    is_substitution_exit,
    is_yellow_card_event,
    map_tercio,
    map_zone_label,
    min_or_none,
    normalize_label,
    result_is_success,
    zone_to_tercio,
)
from football.services import (
    assign_lineup_slots,
    canonical_roster_key,
    compute_probable_eleven,
    compute_formation,
    build_rival_insights,
    fetch_preferente_team_roster,
    find_roster_entry,
    get_roster_stats_cache,
    load_match_actions,
    load_match_results,
    normalize_player_name,
    parse_preferente_roster,
    refresh_primary_roster_cache,
    _parse_int,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_from_rfef.py"
MANAGE_PY_DIR = SCRIPT_PATH.parents[1]
NEXT_MATCH_CACHE = Path(settings.BASE_DIR) / "data" / "input" / "rfaf-next-match.json"
UNIVERSO_SNAPSHOT_PATH = Path(settings.BASE_DIR) / "data" / "input" / "universo-rfaf-snapshot.json"
TASK_RESOURCE_LIBRARY_PATH = Path(settings.BASE_DIR) / "data" / "input" / "task-resource-library.json"
SCRAPE_LOCK_KEY = "football:refresh_scraping_running"
SCRAPE_LOCK_TIMEOUT_SECONDS = 900
DASHBOARD_CACHE_KEY_PREFIX = "football:dashboard_payload"
DASHBOARD_CACHE_SECONDS = int(os.getenv('DASHBOARD_CACHE_SECONDS', '90'))

TASK_MATERIAL_LIBRARY = [
    {'label': 'CONO', 'title': 'Cono alto', 'kind': 'cone', 'category': 'delimitacion', 'icon': '△'},
    {'label': 'SETA', 'title': 'Seta baja', 'kind': 'marker', 'category': 'delimitacion', 'icon': '◉'},
    {'label': 'DISCO', 'title': 'Disco plano', 'kind': 'marker-flat', 'category': 'delimitacion', 'icon': '◍'},
    {'label': 'PICA', 'title': 'Pica', 'kind': 'pole', 'category': 'delimitacion', 'icon': '┃'},
    {'label': 'CINTA', 'title': 'Cinta delimitación', 'kind': 'tape', 'category': 'delimitacion', 'icon': '═'},
    {'label': 'ARO', 'title': 'Aro coordinación', 'kind': 'ring', 'category': 'coordinacion', 'icon': '◯'},
    {'label': 'ESC', 'title': 'Escalera coordinación', 'kind': 'ladder', 'category': 'coordinacion', 'icon': '☷'},
    {'label': 'VALLA', 'title': 'Valla coordinación', 'kind': 'hurdle', 'category': 'coordinacion', 'icon': '⊓'},
    {'label': 'SLALOM', 'title': 'Palo slalom', 'kind': 'slalom', 'category': 'coordinacion', 'icon': '╽'},
    {'label': 'MINI', 'title': 'Mini valla velocidad', 'kind': 'mini-hurdle', 'category': 'coordinacion', 'icon': '⫍'},
    {'label': 'BAL', 'title': 'Balón', 'kind': 'ball', 'category': 'juego', 'icon': '●'},
    {'label': 'MED', 'title': 'Balón medicinal', 'kind': 'medicine-ball', 'category': 'fisico', 'icon': '◒'},
    {'label': 'PORT', 'title': 'Portería móvil', 'kind': 'goal', 'category': 'porterias', 'icon': '⌷'},
    {'label': 'MPORT', 'title': 'Mini portería', 'kind': 'mini-goal', 'category': 'porterias', 'icon': '⌸'},
    {'label': 'PGK', 'title': 'Portería portero', 'kind': 'gk-goal', 'category': 'porterias', 'icon': '▭'},
    {'label': 'MANIQ', 'title': 'Maniquí', 'kind': 'mannequin', 'category': 'oposicion', 'icon': '♞'},
    {'label': 'DUMMY', 'title': 'Dummie inflable', 'kind': 'dummy', 'category': 'oposicion', 'icon': '♜'},
    {'label': 'MURO', 'title': 'Muro faltas', 'kind': 'wall', 'category': 'oposicion', 'icon': '▥'},
    {'label': 'PETO', 'title': 'Petos', 'kind': 'bib', 'category': 'organizacion', 'icon': '▣'},
    {'label': 'GPS', 'title': 'GPS chaleco', 'kind': 'gps', 'category': 'control', 'icon': '⌖'},
    {'label': 'CRONO', 'title': 'Cronómetro', 'kind': 'timer', 'category': 'control', 'icon': '◷'},
    {'label': 'SILB', 'title': 'Silbato', 'kind': 'whistle', 'category': 'control', 'icon': '⌇'},
    {'label': 'TAB', 'title': 'Pizarra coach', 'kind': 'board', 'category': 'control', 'icon': '▤'},
    {'label': 'GOMA', 'title': 'Goma resistencia', 'kind': 'band', 'category': 'fisico', 'icon': '∞'},
    {'label': 'TRX', 'title': 'Suspensión TRX', 'kind': 'trx', 'category': 'fisico', 'icon': '⟂'},
    {'label': 'CAJON', 'title': 'Cajón pliometría', 'kind': 'box', 'category': 'fisico', 'icon': '▧'},
    {'label': 'TRINEO', 'title': 'Trineo arrastre', 'kind': 'sled', 'category': 'fisico', 'icon': '⎍'},
    {'label': 'ESTACA', 'title': 'Estaca zona', 'kind': 'stake', 'category': 'delimitacion', 'icon': '⎸'},
    {'label': 'ARCO', 'title': 'Arco precisión', 'kind': 'arc', 'category': 'finalizacion', 'icon': '◠'},
    {'label': 'OBJ', 'title': 'Objetivo diana', 'kind': 'target', 'category': 'finalizacion', 'icon': '◎'},
]
TASK_MATERIAL_PPT_DIR = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'task-materials' / 'ppt'
TASK_SURFACE_CHOICES = [
    ('natural_grass', 'Hierba natural'),
    ('artificial_turf', 'Césped artificial'),
    ('futsal', 'Pista futsal'),
    ('sand', 'Arena'),
    ('indoor', 'Indoor'),
    ('gym', 'Gimnasio'),
]
TASK_PITCH_FORMAT_CHOICES = [
    ('11v11_full', '11v11 · Campo completo'),
    ('11v11_half', '11v11 · Medio campo'),
    ('9v9', '9v9'),
    ('8v8', '8v8'),
    ('7v7', '7v7'),
    ('5v5', '5v5'),
    ('abp', 'ABP'),
    ('specific_zone', 'Zona específica'),
]
TASK_GAME_PHASE_CHOICES = [
    ('organization_attack', 'Organización ofensiva'),
    ('organization_defense', 'Organización defensiva'),
    ('offensive_transition', 'Transición ofensiva'),
    ('defensive_transition', 'Transición defensiva'),
    ('set_pieces', 'ABP'),
]
TASK_METHODOLOGY_CHOICES = [
    ('analytical', 'Analítica'),
    ('integrated', 'Integrada'),
    ('global', 'Global'),
    ('competition', 'Competitiva'),
    ('coadjuvant', 'Coadyuvante'),
]
TASK_COMPLEXITY_CHOICES = [
    ('low', 'Baja'),
    ('medium', 'Media'),
    ('high', 'Alta'),
]
TASK_USEFULNESS_CHOICES = [
    ('1', '1 · Baja'),
    ('2', '2'),
    ('3', '3 · Media'),
    ('4', '4'),
    ('5', '5 · Top'),
]
TASK_CONSTRAINT_CHOICES = [
    ('two_touches', '2 toques'),
    ('one_touch_zone', '1 toque zona final'),
    ('mandatory_switch', 'Cambio de orientación obligatorio'),
    ('finish_under_10', 'Finalizar < 10 segundos'),
    ('press_6_seconds', 'Presionar 6 segundos tras pérdida'),
    ('bonus_recovery_high', 'Bonus por recuperación alta'),
    ('max_3_passes_before_finish', 'Máx. 3 pases antes de finalizar'),
]
TASK_TEMPLATE_LIBRARY = [
    {
        'key': 'none',
        'label': 'Sin plantilla (manual)',
    },
    {
        'key': 'rondo_press',
        'label': 'Rondo + presión tras pérdida',
        'values': {
            'task_title': 'Rondo + presión tras pérdida',
            'task_objective': 'Mejorar orientación corporal, apoyos y reacción tras pérdida.',
            'task_space': '24x24m',
            'task_organization': '6v3 + 1 comodín',
            'task_players_distribution': '2 equipos de 5 + 1 comodín',
            'task_load_target': 'RPE 7',
            'task_work_rest': '4x3\' + 1\' pausa',
            'task_series': '4',
            'task_repetitions': '1',
            'task_coaching_points': '- Perfil corporal abierto\n- Pase tenso y línea de pase de seguridad\n- Tras pérdida: 3" de presión máxima',
            'task_confrontation_rules': '- 1 punto por 8 pases seguidos\n- Si roba defensa y sale del cuadrado: 2 puntos',
            'task_progression': '- Limitar a 2 toques\n- Reducir espacio a 20x20m',
            'task_regression': '- Aumentar espacio\n- Añadir segundo comodín',
            'task_success_criteria': 'Al menos 60% de secuencias > 6 pases y recuperación en <6".',
        },
    },
    {
        'key': 'positional_game',
        'label': 'Juego de posición',
        'values': {
            'task_title': 'Juego de posición por calles',
            'task_objective': 'Fijar por dentro y progresar por fuera con tercer hombre.',
            'task_space': '48x36m · 3 calles',
            'task_organization': '7v7 + 3 comodines',
            'task_players_distribution': 'Líneas por altura + comodines interiores',
            'task_load_target': 'RPE 6-7',
            'task_work_rest': '3x6\' + 2\' pausa',
            'task_series': '3',
            'task_repetitions': '1',
            'task_coaching_points': '- Atracción interior para liberar lado débil\n- Ocupar 5 carriles en amplitud',
            'task_confrontation_rules': '- Gol válido tras cambio de orientación\n- Máximo 3 toques en zona interior',
            'task_progression': '- Reducir toques por línea\n- Limitar comodín a 1 toque',
            'task_regression': '- Sin límite de toques\n- Añadir un comodín extra',
            'task_success_criteria': '8+ progresiones con cambio de orientación por bloque.',
        },
    },
    {
        'key': 'transition_wave',
        'label': 'Transición ataque-defensa',
        'values': {
            'task_title': 'Olas de transición 4v3 + 3v2',
            'task_objective': 'Acelerar decisión tras robo y proteger carril central en repliegue.',
            'task_space': 'Medio campo',
            'task_organization': 'Secuencias por olas',
            'task_players_distribution': '2 equipos + finalizadores + recuperadores',
            'task_load_target': 'RPE 8',
            'task_work_rest': '6x90" + 90" pausa',
            'task_series': '2',
            'task_repetitions': '6',
            'task_coaching_points': '- Primer pase tras robo hacia delante\n- Repliegue en sprint 6"',
            'task_confrontation_rules': '- Gol en <10" vale doble\n- Si recupera defensor y sale, punto',
            'task_progression': '- Reducir tiempo de finalización a 8"\n- Iniciar desde estímulo imprevisible',
            'task_regression': '- Aumentar superioridad ofensiva',
            'task_success_criteria': '50% finalizaciones en tiempo objetivo y cero goles por carril central.',
        },
    },
    {
        'key': 'abp_corner',
        'label': 'ABP córner ofensivo',
        'values': {
            'task_title': 'ABP ofensiva · córner corto/largo',
            'task_objective': 'Automatizar dos rutinas y timing de bloqueos.',
            'task_space': 'Último tercio',
            'task_organization': 'Atacantes vs defensores + portero',
            'task_players_distribution': '8 atacantes + 6 defensores',
            'task_load_target': 'RPE 5',
            'task_work_rest': '10 repeticiones por rutina',
            'task_series': '2',
            'task_repetitions': '10',
            'task_coaching_points': '- Timing de bloqueo y desmarque\n- Perfil del centrador según rutina',
            'task_confrontation_rules': '- Solo vale gol de zona objetivo\n- Si despeja defensa fuera del área: punto defensa',
            'task_progression': '- Añadir segunda jugada\n- Variar perfil de centro',
            'task_regression': '- Sin oposición en primeras repeticiones',
            'task_success_criteria': '70% de ejecuciones con remate en zona prevista.',
        },
    },
]


def build_task_material_library():
    materials = [dict(item) for item in TASK_MATERIAL_LIBRARY]
    if not TASK_MATERIAL_PPT_DIR.exists():
        return materials

    allowed_suffixes = {'.png', '.gif', '.jpg', '.jpeg', '.webp'}
    icon_files = [
        path
        for path in sorted(TASK_MATERIAL_PPT_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in allowed_suffixes
    ]
    for index, icon_file in enumerate(icon_files, start=1):
        materials.append(
            {
                'label': f'P{index:02d}',
                'title': f'Recurso visual PPT {index:02d}',
                'kind': f'ppt-{index:02d}',
                'category': 'ppt',
                'icon': '',
                'asset': f"football/images/task-materials/ppt/{icon_file.name}",
            }
        )
    return materials


def _canonical_action_value(value):
    return ' '.join(str(value or '').split()).strip().lower()


def _build_pdf_response_or_html_fallback(request, html: str, filename: str):
    if not weasyprint:
        return HttpResponse(html, content_type='text/html; charset=utf-8')
    try:
        def _safe_url_fetcher(url, timeout=4, ssl_context=None):
            try:
                default_fetcher = getattr(weasyprint, 'default_url_fetcher', None)
                if callable(default_fetcher):
                    return default_fetcher(url, timeout=timeout, ssl_context=ssl_context)
            except Exception:
                pass
            return {'string': b'', 'mime_type': 'text/plain'}

        pdf_file = weasyprint.HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_safe_url_fetcher,
        ).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        return response
    except Exception:
        return HttpResponse(html, content_type='text/html; charset=utf-8')


def resolve_player_photo_static_path(player):
    if not player:
        return ''
    players_dir = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'players'
    if not players_dir.exists():
        return ''

    name_slug = slugify(player.name or '')
    number_value = player.number if player.number is not None else ''
    candidates = []
    candidates.extend(
        [
            f'player-{player.id}.png',
            f'player-{player.id}.jpg',
            f'player-{player.id}.jpeg',
            f'player-{player.id}.webp',
        ]
    )
    if name_slug and number_value != '':
        candidates.extend(
            [
                f'{name_slug}-n{number_value}-final.png',
                f'{name_slug}-n{number_value}.png',
                f'{name_slug}-{number_value}.png',
            ]
        )
    if name_slug:
        candidates.extend(
            [
                f'{name_slug}-final.png',
                f'{name_slug}.png',
                f'{name_slug}.jpg',
                f'{name_slug}.jpeg',
            ]
        )
    if number_value != '':
        candidates.extend(
            [
                f'n{number_value}-{name_slug}.png',
                f'{name_slug}-n{number_value}-cut.png',
                f'{name_slug}-n{number_value}-crop.png',
            ]
        )

    seen = set()
    for filename in candidates:
        if filename in seen:
            continue
        seen.add(filename)
        file_path = players_dir / filename
        if file_path.exists():
            return f'football/images/players/{filename}'
    if number_value != '':
        wildcard_patterns = [
            f'*-n{number_value}-final.*',
            f'*-n{number_value}-cut.*',
            f'*-n{number_value}-crop.*',
            f'*-n{number_value}.*',
        ]
        for pattern in wildcard_patterns:
            for file_path in players_dir.glob(pattern):
                if file_path.is_file():
                    return f'football/images/players/{file_path.name}'
    return ''


def resolve_player_photo_url(request, player):
    static_path = resolve_player_photo_static_path(player)
    if not static_path:
        return ''
    if request is None:
        return static(static_path)
    try:
        return request.build_absolute_uri(static(static_path))
    except Exception:
        return static(static_path)


def _file_as_data_uri(file_path):
    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ''
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = 'image/png'
        encoded = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'data:{mime_type};base64,{encoded}'
    except Exception:
        return ''


def _image_file_as_small_data_uri(file_path, max_width=1200, max_height=800, quality=72):
    """Encode image files as a lightweight JPEG data URI for faster PDF rendering."""
    if Image is None:
        return _file_as_data_uri(file_path)
    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return ''
        with Image.open(path) as img:
            normalized = img.convert('RGB')
            normalized.thumbnail((int(max_width), int(max_height)))
            buffer = io.BytesIO()
            normalized.save(buffer, format='JPEG', optimize=True, quality=int(quality))
        encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
        return f'data:image/jpeg;base64,{encoded}'
    except Exception:
        return _file_as_data_uri(file_path)


def resolve_team_photo_for_pdf(request):
    default_path = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'team-01.jpg'
    fallback_url = request.build_absolute_uri(static('football/images/team-01.jpg'))
    fallback_data_uri = _image_file_as_small_data_uri(default_path)
    source_path = default_path
    source_url = fallback_url

    carousel_cover = (
        HomeCarouselImage.objects
        .filter(is_active=True)
        .order_by('order', '-created_at', '-id')
        .first()
    )
    if not carousel_cover:
        carousel_cover = (
            HomeCarouselImage.objects
            .order_by('order', '-created_at', '-id')
            .first()
        )
    if carousel_cover and carousel_cover.image:
        try:
            source_url = request.build_absolute_uri(carousel_cover.image.url)
            if getattr(carousel_cover.image, 'path', None):
                source_path = Path(carousel_cover.image.path)
        except Exception:
            source_path = default_path
            source_url = fallback_url

    data_uri = _image_file_as_small_data_uri(source_path) or fallback_data_uri
    return {
        'url': source_url or fallback_url,
        'data_uri': data_uri or '',
    }


def get_active_injury_player_ids(player_ids):
    normalized_ids = [int(pid) for pid in set(player_ids or []) if pid]
    if not normalized_ids:
        return set()
    try:
        return set(
            PlayerInjuryRecord.objects
            .filter(player_id__in=normalized_ids, is_active=True)
            .values_list('player_id', flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def get_competition_total_rounds(primary_team):
    if not primary_team:
        return 0
    group = primary_team.group
    if not group:
        return 0
    matches = Match.objects.filter(group=group)
    round_numbers = []
    for round_value in matches.values_list('round', flat=True):
        round_num = extract_round_number(round_value)
        if round_num is not None:
            round_numbers.append(round_num)
    total_by_rounds = max(round_numbers) if round_numbers else 0
    teams_count = Team.objects.filter(group=group).exclude(id__isnull=True).count()
    total_double_round_robin = max((teams_count - 1) * 2, 0) if teams_count >= 2 else 0
    return max(total_by_rounds, total_double_round_robin)


def get_previous_match(primary_team, reference_match=None):
    if not primary_team:
        return None
    qs = _team_match_queryset(primary_team)
    if not qs.exists():
        return None
    if reference_match and reference_match.date:
        previous = qs.exclude(id=reference_match.id).filter(date__lt=reference_match.date).order_by('-date', '-id').first()
        if previous:
            return previous
    today = timezone.localdate()
    previous = qs.filter(date__lt=today).order_by('-date', '-id').first()
    if previous:
        return previous
    return None


def get_sanctioned_player_ids_from_previous_round(primary_team, reference_match=None):
    previous_match = get_previous_match(primary_team, reference_match=reference_match)
    if not previous_match:
        return set()
    sanctioned_ids = set()
    events = (
        confirmed_events_queryset()
        .filter(match=previous_match, player__team=primary_team)
        .select_related('player')
    )
    for event in events:
        if event.player_id and is_red_card_event(event.event_type, event.result, event.zone):
            sanctioned_ids.add(event.player_id)
    return sanctioned_ids


def is_manual_sanction_active(player, today=None):
    if not player or not getattr(player, 'manual_sanction_active', False):
        return False
    reference_day = today or timezone.localdate()
    until_date = getattr(player, 'manual_sanction_until', None)
    if until_date and until_date < reference_day:
        return False
    return True


def _serialize_match_event(event, duplicate=False):
    player = event.player
    return {
        'id': event.id,
        'minute': event.minute,
        'period': event.period,
        'action': event.event_type,
        'zone': event.zone,
        'result': event.result,
        'duplicate': bool(duplicate),
        'player': {
            'id': player.id if player else None,
            'name': player.name if player else 'Equipo',
            'number': (player.number if player and player.number is not None else '--'),
        },
    }


TEAM_ONLY_ACTION_TYPES = {
    'saque de esquina a favor',
    'saque de esquina en contra',
}

TECHNICAL_ROLES = {
    AppUserRole.ROLE_COACH,
    AppUserRole.ROLE_FITNESS,
    AppUserRole.ROLE_GOALKEEPER,
    AppUserRole.ROLE_ANALYST,
    AppUserRole.ROLE_ADMIN,
}


def _get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    role_obj = getattr(user, 'app_role', None)
    return str(getattr(role_obj, 'role', '') or '').strip() or None


def _is_admin_user(user):
    role = _get_user_role(user)
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff or role == AppUserRole.ROLE_ADMIN))


def _can_access_sessions_workspace(user):
    role = _get_user_role(user)
    if not user or not user.is_authenticated:
        return False
    if _is_admin_user(user):
        return True
    return role in TECHNICAL_ROLES


def _is_team_only_action(action_type: str) -> bool:
    normalized = (action_type or '').strip().lower()
    if not normalized:
        return False
    folded = ''.join(
        ch for ch in unicodedata.normalize('NFKD', normalized) if not unicodedata.combining(ch)
    )
    team_only_aliases = {
        'saque de esquina a favor',
        'saque de esquina en contra',
        'corner a favor',
        'corner en contra',
    }
    return folded in team_only_aliases


def authenticated_write(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autenticación requerida'}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped


def load_cached_next_match():
    if not NEXT_MATCH_CACHE.exists():
        return None
    try:
        with NEXT_MATCH_CACHE.open(encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                payload = normalize_next_match_payload(payload)
                payload.setdefault("status", "next")
                status = (payload.get('status') or '').lower()
                date_raw = payload.get('date')
                if date_raw:
                    payload_date = _parse_payload_date(date_raw)
                    today = timezone.localdate()
                    if payload_date:
                        if status == 'next' and payload_date < today:
                            return None
                        if status == 'latest' and payload_date < (today - timedelta(days=3)):
                            return None
                    elif status == 'next':
                        # If we cannot parse the date, avoid surfacing stale "next match" payloads.
                        return None
                return payload
    except Exception:
        return None
    return None


def normalize_next_match_payload(payload):
    if not isinstance(payload, dict):
        return payload
    opponent = payload.get('opponent')
    if isinstance(opponent, str):
        clean_name = opponent.strip() or 'Rival por confirmar'
        payload['opponent'] = {
            'name': clean_name,
            'full_name': clean_name,
            'crest_url': '',
            'team_code': '',
        }
    elif isinstance(opponent, dict):
        name = str(opponent.get('name') or opponent.get('full_name') or '').strip()
        full_name = str(opponent.get('full_name') or name).strip()
        payload['opponent'] = {
            'name': name or 'Rival por confirmar',
            'full_name': full_name or name or 'Rival por confirmar',
            'crest_url': str(opponent.get('crest_url') or '').strip(),
            'team_code': str(opponent.get('team_code') or '').strip(),
        }
    else:
        fallback = str(payload.get('rival') or '').strip()
        payload['opponent'] = {
            'name': fallback or 'Rival por confirmar',
            'full_name': fallback or 'Rival por confirmar',
            'crest_url': '',
            'team_code': '',
        }
    return payload


def _parse_payload_date(raw):
    if not raw:
        return None
    value = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _payload_opponent_name(payload):
    if not isinstance(payload, dict):
        return ''
    opponent = payload.get('opponent')
    if isinstance(opponent, dict):
        return str(opponent.get('full_name') or opponent.get('name') or '').strip()
    if isinstance(opponent, str):
        return opponent.strip()
    return str(payload.get('rival') or '').strip()


def _normalize_team_lookup_key(value):
    text = str(value or '').strip()
    if not text:
        return ''
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r'[^a-z0-9]+', '', normalized.lower())
    return normalized


def _team_name_signature(value):
    text = str(value or '').strip()
    if not text:
        return ()
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    tokens = [tok for tok in re.findall(r'[a-z0-9]+', normalized) if tok]
    if not tokens:
        return ()
    return tuple(sorted(tokens))


def _build_universo_standings_lookup(snapshot):
    lookup = {}
    if not isinstance(snapshot, dict):
        return lookup
    for row in snapshot.get('standings') or []:
        if not isinstance(row, dict):
            continue
        team_name = str(row.get('team') or row.get('full_name') or '').strip()
        key = _normalize_team_lookup_key(team_name)
        if not key:
            continue
        lookup[key] = {
            'full_name': str(row.get('full_name') or team_name).strip() or team_name,
            'crest_url': str(row.get('crest_url') or '').strip(),
            'team_code': str(row.get('team_code') or '').strip(),
        }
    return lookup


def _absolute_universo_url(path_or_url):
    value = str(path_or_url or '').strip()
    if not value:
        return ''
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value.startswith('/'):
        return f'https://www.universorfaf.es{value}'
    return f'https://www.universorfaf.es/{value.lstrip("/")}'


def _build_universo_capture_team_lookup():
    lookup = {}
    capture_path = Path(settings.BASE_DIR) / 'data' / 'input' / 'universo-rfaf-capture.json'
    if not capture_path.exists():
        return lookup
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
        crest_url = _absolute_universo_url(crest)
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
    return lookup


def _resolve_rival_identity(rival_name, preferred_opponent=None):
    rival_name = str(rival_name or '').strip() or 'Rival por confirmar'
    rival_full_name = rival_name
    rival_crest_url = ''
    rival_key = _normalize_team_lookup_key(rival_name)

    if isinstance(preferred_opponent, dict):
        preferred_name = str(preferred_opponent.get('name') or '').strip()
        preferred_full_name = str(preferred_opponent.get('full_name') or '').strip()
        preferred_key = _normalize_team_lookup_key(preferred_name or preferred_full_name)
        if preferred_key and rival_key and (preferred_key == rival_key or preferred_key in rival_key or rival_key in preferred_key):
            rival_full_name = preferred_full_name or preferred_name or rival_full_name
            rival_crest_url = str(preferred_opponent.get('crest_url') or '').strip()

    standings_lookup = _build_universo_standings_lookup(load_universo_snapshot())
    capture_lookup = _build_universo_capture_team_lookup()

    best_meta = {}
    candidates = [standings_lookup.get(rival_key, {}), capture_lookup.get(rival_key, {})]
    for source in (standings_lookup, capture_lookup):
        if best_meta.get('full_name') and best_meta.get('crest_url'):
            break
        for key, meta in source.items():
            if not key or not rival_key:
                continue
            if rival_key in key or key in rival_key:
                if len(str(meta.get('full_name') or '')) > len(str(best_meta.get('full_name') or '')):
                    best_meta['full_name'] = str(meta.get('full_name') or '').strip()
                if meta.get('crest_url') and not best_meta.get('crest_url'):
                    best_meta['crest_url'] = str(meta.get('crest_url') or '').strip()
    for meta in candidates:
        if not isinstance(meta, dict):
            continue
        if len(str(meta.get('full_name') or '')) > len(str(best_meta.get('full_name') or '')):
            best_meta['full_name'] = str(meta.get('full_name') or '').strip()
        if meta.get('crest_url') and not best_meta.get('crest_url'):
            best_meta['crest_url'] = str(meta.get('crest_url') or '').strip()

    rival_full_name = best_meta.get('full_name') or rival_full_name
    rival_crest_url = best_meta.get('crest_url') or rival_crest_url
    return rival_full_name, rival_crest_url


def load_preferred_next_match_payload():
    today = timezone.localdate()
    snapshot = load_universo_snapshot()
    if isinstance(snapshot, dict) and isinstance(snapshot.get('next_match'), dict):
        snapshot_next = normalize_next_match_payload(snapshot.get('next_match'))
        status = str(snapshot_next.get('status') or 'next').lower()
        payload_date = _parse_payload_date(snapshot_next.get('date'))
        if status == 'next' and payload_date and payload_date >= today:
            return snapshot_next

    cached_next = load_cached_next_match()
    if isinstance(cached_next, dict):
        status = str(cached_next.get('status') or '').lower()
        payload_date = _parse_payload_date(cached_next.get('date'))
        if status == 'next' and payload_date and payload_date >= today:
            return normalize_next_match_payload(cached_next)
    return None


def _build_next_match_from_convocation(primary_team):
    record = get_current_convocation_record(primary_team)
    if not record:
        return None

    opponent_name = (record.opponent_name or '').strip()
    round_label = (record.round or '').strip()
    location_label = (record.location or '').strip()
    date_iso = record.match_date.isoformat() if record.match_date else None
    time_label = record.match_time.strftime('%H:%M') if record.match_time else ''

    if not any([opponent_name, round_label, date_iso, time_label, location_label]):
        return None

    home_flag = None
    match = record.match
    if match and primary_team:
        if match.home_team_id == primary_team.id:
            home_flag = True
        elif match.away_team_id == primary_team.id:
            home_flag = False

    rival_full_name, rival_crest_url = _resolve_rival_identity(opponent_name or 'Rival por confirmar')

    payload = {
        'round': round_label or 'Jornada por confirmar',
        'date': date_iso,
        'time': time_label,
        'location': location_label or 'Campo por confirmar',
        'opponent': {
            'name': opponent_name or rival_full_name or 'Rival por confirmar',
            'full_name': rival_full_name or opponent_name or 'Rival por confirmar',
            'crest_url': _absolute_universo_url(rival_crest_url),
            'team_code': '',
        },
        'home': home_flag if home_flag is not None else True,
        'status': 'next',
        'source': 'convocation-manual',
    }
    return normalize_next_match_payload(payload)


def _next_match_payload_is_reliable(payload):
    if not isinstance(payload, dict):
        return False
    status = str(payload.get('status') or '').strip().lower()
    if status != 'next':
        return False
    opponent_name = _payload_opponent_name(payload).strip().lower()
    if not opponent_name or opponent_name in {'rival por confirmar', 'rival desconocido'}:
        return False
    payload_date = _parse_payload_date(payload.get('date'))
    if payload_date and payload_date < timezone.localdate():
        return False
    return True


def _dashboard_cache_key(team_id):
    return f'{DASHBOARD_CACHE_KEY_PREFIX}:{team_id}'


def load_universo_snapshot():
    if not UNIVERSO_SNAPSHOT_PATH.exists():
        return None
    try:
        with UNIVERSO_SNAPSHOT_PATH.open(encoding='utf-8') as handle:
            payload = json.load(handle)
            return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _serialize_universo_standings(snapshot):
    if not isinstance(snapshot, dict):
        return []
    rows = snapshot.get('standings')
    if not isinstance(rows, list):
        return []
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        team = str(row.get('team') or '').strip()
        if not team:
            continue
        gf = _safe_int(row.get('goals_for'))
        ga = _safe_int(row.get('goals_against'))
        gd = row.get('goal_difference')
        if gd in (None, ''):
            gd = gf - ga
        normalized.append(
            {
                'rank': _safe_int(row.get('position'), default=0),
                'team': team,
                'full_name': str(row.get('full_name') or team).strip() or team,
                'crest_url': str(row.get('crest_url') or '').strip(),
                'team_code': str(row.get('team_code') or '').strip(),
                'played': _safe_int(row.get('played')),
                'wins': _safe_int(row.get('wins')),
                'draws': _safe_int(row.get('draws')),
                'losses': _safe_int(row.get('losses')),
                'goals_for': gf,
                'goals_against': ga,
                'goal_difference': _safe_int(gd),
                'points': _safe_int(row.get('points')),
            }
        )
    return sorted(normalized, key=lambda x: (x['rank'] <= 0, x['rank'], -x['points'], x['full_name']))


@login_required
def dashboard_data(request):
    """Devuelve los datos principales que alimentarán la home cuerpo técnico/jugador."""
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)

    group = primary_team.group
    if not group:
        return JsonResponse({'error': 'El equipo principal no está asignado a ningún grupo'}, status=400)

    cache_key = _dashboard_cache_key(primary_team.id)
    cached_payload = cache.get(cache_key)
    if isinstance(cached_payload, dict):
        return JsonResponse(cached_payload)

    refresh_roster_on_load = str(
        os.getenv('PREFERENTE_ROSTER_REFRESH_ON_LOAD', '0')
    ).strip().lower() in {'1', 'true', 'yes', 'on'}
    if refresh_roster_on_load:
        try:
            refresh_primary_roster_cache(primary_team, force=False)
        except Exception:
            pass

    universo_snapshot = load_universo_snapshot()
    standings = _serialize_universo_standings(universo_snapshot) or serialize_standings(group)
    next_match = load_preferred_next_match_payload() or get_next_match(primary_team, group)
    convocation_next_match = _build_next_match_from_convocation(primary_team)
    # Product rule: Home must prioritize the data configured in Convocatoria.
    if convocation_next_match:
        next_match = convocation_next_match
    team_metrics = compute_team_metrics(primary_team)
    player_metrics = compute_player_metrics(primary_team)
    player_cards = compute_player_cards(primary_team)
    player_cards_scope = {'type': 'global', 'label': 'Jugador · datos La Preferente'}

    payload = {
        'team': {'name': primary_team.name, 'group': group.name},
        'standings': standings,
        'next_match': next_match,
        'team_metrics': team_metrics,
        'player_metrics': player_metrics,
        'player_cards': player_cards,
        'player_cards_scope': player_cards_scope,
    }
    cache.set(cache_key, payload, DASHBOARD_CACHE_SECONDS)
    return JsonResponse(payload)


@login_required
@ensure_csrf_cookie
def dashboard_page(request):
    sources = list(ScrapeSource.objects.filter(is_active=True))
    active_items = list(HomeCarouselImage.objects.filter(is_active=True).order_by('order', '-created_at', '-id'))
    all_items = list(HomeCarouselImage.objects.order_by('order', '-created_at', '-id'))
    candidates = active_items if active_items else all_items
    hero_image_candidates = [item.image.url for item in candidates if item.image]
    current_role = _get_user_role(request.user) or AppUserRole.ROLE_PLAYER
    role_labels = dict(AppUserRole.ROLE_CHOICES)
    can_access_admin = _is_admin_user(request.user)
    can_access_sessions = _can_access_sessions_workspace(request.user)
    return render(
        request,
        'football/dashboard.html',
        {
            'scrape_sources': sources,
            'hero_image_candidates': hero_image_candidates,
            'current_role': current_role,
            'current_role_label': role_labels.get(current_role, 'Jugador'),
            'can_access_admin': can_access_admin,
            'can_access_sessions': can_access_sessions,
        },
    )


def _handle_home_carousel_post(request):
    form_action = (request.POST.get('form_action') or '').strip().lower()

    if form_action == 'carousel_upload':
        uploaded = request.FILES.get('carousel_image')
        if uploaded:
            title = (request.POST.get('carousel_title') or '').strip()
            order = _parse_int(request.POST.get('carousel_order')) or 0
            is_active = str(request.POST.get('carousel_is_active') or '').lower() in {'1', 'true', 'on', 'yes'}
            HomeCarouselImage.objects.create(
                title=title,
                image=uploaded,
                order=order,
                is_active=is_active,
            )
        return True

    if form_action == 'carousel_update':
        image_id = _parse_int(request.POST.get('carousel_id'))
        item = HomeCarouselImage.objects.filter(id=image_id).first()
        if item:
            item.title = (request.POST.get('carousel_title') or '').strip()
            item.order = _parse_int(request.POST.get('carousel_order')) or 0
            item.is_active = str(request.POST.get('carousel_is_active') or '').lower() in {'1', 'true', 'on', 'yes'}
            item.save(update_fields=['title', 'order', 'is_active'])
        return True

    if form_action == 'carousel_delete':
        image_id = _parse_int(request.POST.get('carousel_id'))
        item = HomeCarouselImage.objects.filter(id=image_id).first()
        if item:
            if item.image:
                try:
                    item.image.delete(save=False)
                except Exception:
                    pass
            item.delete()
        return True
    return False


@login_required
@ensure_csrf_cookie
def admin_page(request):
    def _split_full_name(value):
        text = str(value or '').strip()
        if not text:
            return '', ''
        parts = [part for part in text.split() if part]
        if len(parts) == 1:
            return parts[0], ''
        return parts[0], ' '.join(parts[1:])

    def _display_full_name(user_obj):
        full = user_obj.get_full_name().strip()
        return full or user_obj.username

    primary_team = Team.objects.filter(is_primary=True).first()
    current_role = AppUserRole.objects.filter(user=request.user).values_list('role', flat=True).first()
    is_admin_user = bool(request.user.is_staff or current_role == AppUserRole.ROLE_ADMIN)
    roster_message = ''
    roster_error = ''
    carousel_message = ''
    user_message = ''
    user_error = ''
    actions_message = ''
    actions_error = ''
    invitation_links = []
    active_tab = (request.GET.get('tab') or request.POST.get('active_tab') or 'roster').strip().lower()
    if active_tab not in {'roster', 'carousel', 'users', 'actions'}:
        active_tab = 'roster'
    users_segment = (request.GET.get('segment') or request.POST.get('users_segment') or 'all').strip().lower()
    if users_segment not in {'all', 'technical', 'players', 'guests'}:
        users_segment = 'all'
    if request.method == 'POST':
        form_action = (request.POST.get('form_action') or '').strip()
        if form_action in {'roster_add_or_update', 'roster_deactivate', 'roster_reactivate'} and primary_team:
            active_tab = 'roster'
            player_id = _parse_int(request.POST.get('player_id'))
            name = (request.POST.get('name') or '').strip()
            number_raw = (request.POST.get('number') or '').strip()
            position = (request.POST.get('position') or '').strip()
            is_active = str(request.POST.get('is_active') or '1').strip().lower() in {'1', 'true', 'on', 'yes'}
            try:
                if form_action in {'roster_deactivate', 'roster_reactivate'}:
                    if not player_id:
                        raise ValueError('Jugador no válido.')
                    player = Player.objects.filter(id=player_id, team=primary_team).first()
                    if not player:
                        raise ValueError('Jugador no encontrado.')
                    player.is_active = form_action == 'roster_reactivate'
                    player.save(update_fields=['is_active'])
                    roster_message = (
                        f'{player.name} reactivado correctamente.'
                        if player.is_active
                        else f'{player.name} marcado como inactivo.'
                    )
                else:
                    if not name:
                        raise ValueError('El nombre es obligatorio.')
                    number = _parse_int(number_raw) if number_raw else None
                    player = (
                        Player.objects.filter(team=primary_team, name__iexact=name)
                        .order_by('id')
                        .first()
                    )
                    if player:
                        player.number = number
                        player.position = position
                        player.is_active = is_active
                        player.save(update_fields=['number', 'position', 'is_active'])
                        roster_message = f'Jugador actualizado: {player.name}.'
                    else:
                        Player.objects.create(
                            team=primary_team,
                            name=name,
                            number=number,
                            position=position,
                            is_active=is_active,
                        )
                        roster_message = f'Jugador añadido: {name}.'
            except ValueError as exc:
                roster_error = str(exc)
            except Exception:
                roster_error = 'No se pudo guardar la plantilla.'
        elif form_action in {'carousel_upload', 'carousel_update', 'carousel_delete'}:
            active_tab = 'carousel'
            if _handle_home_carousel_post(request):
                carousel_message = 'Cambios guardados en fotos Home.'
        elif form_action == 'user_create':
            active_tab = 'users'
            username = (request.POST.get('username') or '').strip().lower()
            full_name = (request.POST.get('full_name') or '').strip()
            email = (request.POST.get('email') or '').strip()
            password = (request.POST.get('password') or '').strip()
            role_value = (request.POST.get('role') or AppUserRole.ROLE_PLAYER).strip()
            role_choices = {choice[0] for choice in AppUserRole.ROLE_CHOICES}
            if role_value not in role_choices:
                role_value = AppUserRole.ROLE_PLAYER
            try:
                if not username:
                    raise ValueError('El usuario es obligatorio.')
                if User.objects.filter(username__iexact=username).exists():
                    raise ValueError('Ese usuario ya existe.')
                if len(password) < 6:
                    raise ValueError('La contraseña debe tener al menos 6 caracteres.')
                first_name, last_name = _split_full_name(full_name)
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                if role_value == AppUserRole.ROLE_ADMIN:
                    user.is_staff = True
                    user.save(update_fields=['is_staff'])
                AppUserRole.objects.update_or_create(user=user, defaults={'role': role_value})
                user_message = f'Usuario creado: {username}.'
            except ValueError as exc:
                user_error = str(exc)
            except Exception:
                user_error = 'No se pudo crear el usuario.'
        elif form_action == 'user_update':
            active_tab = 'users'
            user_id = _parse_int(request.POST.get('user_id'))
            username = (request.POST.get('username') or '').strip().lower()
            full_name = (request.POST.get('full_name') or '').strip()
            email = (request.POST.get('email') or '').strip()
            password = (request.POST.get('password') or '').strip()
            role_value = (request.POST.get('role') or AppUserRole.ROLE_PLAYER).strip()
            role_choices = {choice[0] for choice in AppUserRole.ROLE_CHOICES}
            if role_value not in role_choices:
                role_value = AppUserRole.ROLE_PLAYER
            user_obj = User.objects.filter(id=user_id).first() if user_id else None
            try:
                if not user_obj:
                    raise ValueError('Usuario no encontrado.')
                if not username:
                    raise ValueError('El usuario es obligatorio.')
                username_taken = User.objects.filter(username__iexact=username).exclude(id=user_obj.id).exists()
                if username_taken:
                    raise ValueError('Ese nombre de usuario ya está en uso.')
                first_name, last_name = _split_full_name(full_name)
                user_obj.username = username
                user_obj.first_name = first_name
                user_obj.last_name = last_name
                user_obj.email = email
                if password:
                    if len(password) < 6:
                        raise ValueError('La contraseña debe tener al menos 6 caracteres.')
                    user_obj.set_password(password)
                should_staff = role_value == AppUserRole.ROLE_ADMIN
                user_obj.is_staff = should_staff
                user_obj.save()
                AppUserRole.objects.update_or_create(user=user_obj, defaults={'role': role_value})
                user_message = f'Usuario actualizado: {user_obj.username}.'
            except ValueError as exc:
                user_error = str(exc)
            except Exception:
                user_error = 'No se pudo actualizar el usuario.'
        elif form_action == 'user_invite_create':
            active_tab = 'users'
            user_id = _parse_int(request.POST.get('user_id'))
            validity_days = _parse_int(request.POST.get('valid_days')) or 7
            validity_days = max(1, min(validity_days, 30))
            user_obj = User.objects.filter(id=user_id).first() if user_id else None
            try:
                if not user_obj:
                    raise ValueError('Usuario no encontrado.')
                UserInvitation.objects.filter(user=user_obj, is_active=True, accepted_at__isnull=True).update(is_active=False)
                invitation = UserInvitation.objects.create(
                    user=user_obj,
                    token=UserInvitation.generate_token(),
                    email=(user_obj.email or '').strip(),
                    expires_at=timezone.now() + timedelta(days=validity_days),
                    created_by=request.user.get_username() if request.user.is_authenticated else '',
                    is_active=True,
                )
                invite_url = request.build_absolute_uri(
                    reverse('user-invite-accept', args=[invitation.token])
                )
                invitation_links.append(
                    {
                        'username': user_obj.username,
                        'url': invite_url,
                        'expires_at': invitation.expires_at,
                    }
                )
                user_message = f'Invitación generada para {user_obj.username}.'
            except ValueError as exc:
                user_error = str(exc)
            except Exception:
                user_error = 'No se pudo generar la invitación.'
        elif form_action == 'user_update_role':
            active_tab = 'users'
            user_id = _parse_int(request.POST.get('user_id'))
            role_value = (request.POST.get('role') or '').strip()
            role_choices = {choice[0] for choice in AppUserRole.ROLE_CHOICES}
            if role_value not in role_choices:
                role_value = AppUserRole.ROLE_PLAYER
            user_obj = User.objects.filter(id=user_id).first() if user_id else None
            if not user_obj:
                user_error = 'Usuario no encontrado.'
            else:
                AppUserRole.objects.update_or_create(user=user_obj, defaults={'role': role_value})
                should_staff = role_value == AppUserRole.ROLE_ADMIN
                if user_obj.is_staff != should_staff:
                    user_obj.is_staff = should_staff
                    user_obj.save(update_fields=['is_staff'])
                user_message = f'Rol actualizado para {user_obj.username}.'
        elif form_action == 'user_toggle_active':
            active_tab = 'users'
            user_id = _parse_int(request.POST.get('user_id'))
            user_obj = User.objects.filter(id=user_id).first() if user_id else None
            if not user_obj:
                user_error = 'Usuario no encontrado.'
            elif user_obj == request.user:
                user_error = 'No puedes desactivar tu propio usuario.'
            else:
                user_obj.is_active = not bool(user_obj.is_active)
                user_obj.save(update_fields=['is_active'])
                user_message = (
                    f'Usuario {user_obj.username} activado.'
                    if user_obj.is_active
                    else f'Usuario {user_obj.username} desactivado.'
                )
        elif form_action in {'admin_match_save', 'admin_action_bulk_add'}:
            active_tab = 'actions'
            if not is_admin_user:
                actions_error = 'Solo administradores pueden editar partidos y acciones.'
            elif not primary_team:
                actions_error = 'No hay equipo principal configurado.'
            elif form_action == 'admin_match_save':
                match_id = _parse_int(request.POST.get('match_id'))
                opponent_name = (request.POST.get('opponent_name') or '').strip()
                round_value = (request.POST.get('round') or '').strip()
                location = (request.POST.get('location') or '').strip()
                date_raw = (request.POST.get('match_date') or '').strip()
                time_raw = (request.POST.get('match_time') or '').strip()
                if not opponent_name:
                    actions_error = 'El rival es obligatorio.'
                else:
                    match_date = None
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            match_date = datetime.strptime(date_raw, fmt).date() if date_raw else None
                            break
                        except ValueError:
                            continue
                    match_time = None
                    if time_raw:
                        try:
                            match_time = datetime.strptime(time_raw, '%H:%M').time()
                        except ValueError:
                            actions_error = 'Hora inválida. Usa HH:MM.'
                    if not actions_error:
                        rival_team = Team.objects.filter(name__iexact=opponent_name).first()
                        if not rival_team:
                            rival_team = Team.objects.create(
                                slug=_unique_team_slug(opponent_name),
                                name=opponent_name,
                                short_name=opponent_name[:24],
                                group=primary_team.group,
                            )
                        match_dt = None
                        if match_date:
                            match_dt = timezone.make_aware(
                                datetime.combine(match_date, match_time or time(hour=0, minute=0)),
                                timezone.get_current_timezone(),
                            )
                        match_obj = Match.objects.filter(id=match_id).first() if match_id else None
                        if not match_obj:
                            match_obj = Match.objects.create(
                                home_team=primary_team,
                                away_team=rival_team,
                                date=match_date,
                                round=round_value,
                                location=location,
                            )
                        else:
                            match_obj.away_team = rival_team
                            match_obj.date = match_date
                            match_obj.round = round_value
                            match_obj.location = location
                            match_obj.save(update_fields=['away_team', 'date', 'round', 'location'])
                        # compatibilidad: guardar datetime cuando exista
                        if match_dt:
                            try:
                                match_obj.datetime = match_dt
                                match_obj.save(update_fields=['datetime'])
                            except Exception:
                                pass
                        actions_message = f'Partido guardado (ID {match_obj.id}).'
            elif form_action == 'admin_action_bulk_add':
                match_id = _parse_int(request.POST.get('match_id'))
                player_id = _parse_int(request.POST.get('player_id'))
                action_type = (request.POST.get('action_type') or '').strip()
                result = (request.POST.get('result') or '').strip()
                zone = (request.POST.get('zone') or '').strip()
                quantity = _parse_int(request.POST.get('quantity')) or 1
                if quantity < 1:
                    quantity = 1
                if quantity > 500:
                    quantity = 500
                match_obj = Match.objects.filter(id=match_id).first() if match_id else None
                player_obj = Player.objects.filter(id=player_id, team=primary_team).first() if player_id else None
                if not match_obj:
                    actions_error = 'Selecciona un partido válido.'
                elif not player_obj:
                    actions_error = 'Selecciona un jugador válido.'
                elif not action_type:
                    actions_error = 'Selecciona una acción.'
                elif not result:
                    actions_error = 'Selecciona un resultado.'
                else:
                    tercio = zone_to_tercio(zone)
                    base_minute = 1
                    try:
                        last_min = (
                            MatchEvent.objects.filter(match=match_obj)
                            .exclude(minute__isnull=True)
                            .order_by('-minute')
                            .values_list('minute', flat=True)
                            .first()
                        )
                        if isinstance(last_min, int):
                            base_minute = max(1, min(120, last_min))
                    except Exception:
                        pass
                    events = []
                    for idx in range(quantity):
                        minute_value = min(120, base_minute + (idx % 5))
                        events.append(
                            MatchEvent(
                                match=match_obj,
                                player=player_obj,
                                minute=minute_value,
                                period=1 if minute_value <= 45 else 2,
                                event_type=action_type,
                                result=result,
                                zone=zone,
                                tercio=tercio,
                                observation='Carga manual admin',
                                source_file='admin-manual',
                                system='touch-field-final',
                            )
                        )
                    MatchEvent.objects.bulk_create(events, batch_size=200)
                    actions_message = (
                        f'Se añadieron {quantity} acciones a {player_obj.name} '
                        f'en partido ID {match_obj.id}.'
                    )
    carousel_images = []
    roster_players = []
    users = []
    technical_users = []
    players_users = []
    guests_users = []
    users_filtered = []
    admin_matches = []
    selected_admin_match = None
    admin_players = []
    admin_action_choices = []
    admin_result_choices = []
    admin_zone_choices = []

    if active_tab == 'carousel':
        carousel_images = list(HomeCarouselImage.objects.all())

    if active_tab == 'roster':
        roster_players = (
            list(Player.objects.filter(team=primary_team).order_by('-is_active', 'number', 'name'))
            if primary_team
            else []
        )

    if active_tab == 'users':
        users = list(User.objects.order_by('username'))
        role_map = {}
        try:
            role_map = {item.user_id: item.role for item in AppUserRole.objects.select_related('user')}
        except Exception:
            role_map = {}
        role_labels = dict(AppUserRole.ROLE_CHOICES)
        for item in users:
            role_value = role_map.get(item.id, AppUserRole.ROLE_PLAYER)
            item.role_value = role_value
            item.role_label = role_labels.get(role_value, 'Jugador')
            item.full_name_display = _display_full_name(item)
        technical_roles = {
            AppUserRole.ROLE_COACH,
            AppUserRole.ROLE_FITNESS,
            AppUserRole.ROLE_GOALKEEPER,
            AppUserRole.ROLE_ANALYST,
            AppUserRole.ROLE_ADMIN,
        }
        technical_users = [u for u in users if u.role_value in technical_roles]
        players_users = [u for u in users if u.role_value == AppUserRole.ROLE_PLAYER]
        guests_users = [u for u in users if u.role_value == AppUserRole.ROLE_GUEST]
        users_filtered = (
            users
            if users_segment == 'all'
            else technical_users
            if users_segment == 'technical'
            else players_users if users_segment == 'players' else guests_users
        )

    if active_tab == 'actions' and is_admin_user:
        admin_match_qs = _team_match_queryset(primary_team) if primary_team else Match.objects.none()
        # Mostrar siempre todos los partidos asociados al equipo principal.
        # Filtrar por group_id ocultaba cruces válidos (p. ej. partidos cargados manualmente
        # o en otro grupo temporal) en la edición manual de partidos/acciones.
        admin_matches = list(admin_match_qs.order_by('-date', '-id'))
        selected_admin_match_id = _parse_int(request.GET.get('match_id') or request.POST.get('match_id'))
        selected_admin_match = (
            next((m for m in admin_matches if m.id == selected_admin_match_id), None)
            if selected_admin_match_id
            else (admin_matches[0] if admin_matches else None)
        )
        admin_players = (
            list(Player.objects.filter(team=primary_team).order_by('number', 'name'))
            if primary_team
            else []
        )
        admin_action_choices = load_match_actions()
        admin_result_choices = load_match_results()
        seen_zone_labels = set()
        for zone_def in FIELD_ZONES:
            label = str(zone_def.get('label') or '').strip()
            if not label or label in seen_zone_labels:
                continue
            seen_zone_labels.add(label)
            admin_zone_choices.append(label)
    return render(
        request,
        'football/admin.html',
        {
            'carousel_images': carousel_images,
            'roster_players': roster_players,
            'roster_message': roster_message,
            'roster_error': roster_error,
            'carousel_message': carousel_message,
            'users': users,
            'role_choices': AppUserRole.ROLE_CHOICES,
            'user_message': user_message,
            'user_error': user_error,
            'invitation_links': invitation_links,
            'active_tab': active_tab,
            'team_name': primary_team.name if primary_team else '',
            'primary_team_id': primary_team.id if primary_team else None,
            'users_segment': users_segment,
            'technical_users_count': len(technical_users),
            'players_users_count': len(players_users),
            'guests_users_count': len(guests_users),
            'users_filtered': users_filtered,
            'is_admin_user': is_admin_user,
            'admin_matches': admin_matches,
            'selected_admin_match': selected_admin_match,
            'admin_players': admin_players,
            'admin_action_choices': admin_action_choices,
            'admin_result_choices': admin_result_choices,
            'admin_zone_choices': admin_zone_choices,
            'actions_message': actions_message,
            'actions_error': actions_error,
        },
    )


def invitation_accept_page(request, token):
    invitation = (
        UserInvitation.objects
        .select_related('user')
        .filter(token=token, is_active=True)
        .order_by('-created_at')
        .first()
    )
    now = timezone.now()
    if not invitation:
        return render(
            request,
            'football/invitation_accept.html',
            {'status': 'invalid'},
            status=404,
        )
    if invitation.accepted_at:
        return render(
            request,
            'football/invitation_accept.html',
            {'status': 'used', 'username': invitation.user.username},
            status=410,
        )
    if invitation.is_expired(now=now):
        invitation.is_active = False
        invitation.save(update_fields=['is_active'])
        return render(
            request,
            'football/invitation_accept.html',
            {'status': 'expired', 'username': invitation.user.username},
            status=410,
        )
    error = ''
    success = ''
    if request.method == 'POST':
        password = (request.POST.get('password') or '').strip()
        password_confirm = (request.POST.get('password_confirm') or '').strip()
        if not password:
            error = 'La contraseña es obligatoria.'
        elif password != password_confirm:
            error = 'Las contraseñas no coinciden.'
        else:
            try:
                validate_password(password, user=invitation.user)
                invitation.user.set_password(password)
                invitation.user.is_active = True
                invitation.user.save(update_fields=['password', 'is_active'])
                invitation.accepted_at = timezone.now()
                invitation.is_active = False
                invitation.save(update_fields=['accepted_at', 'is_active'])
                UserInvitation.objects.filter(
                    user=invitation.user,
                    is_active=True,
                    accepted_at__isnull=True,
                ).exclude(id=invitation.id).update(is_active=False)
                success = 'Invitación aceptada. Ya puedes iniciar sesión.'
            except DjangoValidationError as exc:
                error = ' '.join(exc.messages) or 'Contraseña inválida.'
            except Exception:
                error = 'No se pudo completar la invitación.'
    return render(
        request,
        'football/invitation_accept.html',
        {
            'status': 'ok',
            'username': invitation.user.username,
            'expires_at': invitation.expires_at,
            'error': error,
            'success': success,
        },
    )


@login_required
def player_dashboard_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    try:
        refresh_primary_roster_cache(primary_team, force=True)
    except Exception:
        pass
    player_stats = compute_player_dashboard(primary_team)
    match_options = []
    selected_match = None
    selected_match_id = ''
    selected_match_total_actions = 0

    current_role = _get_user_role(request.user) or AppUserRole.ROLE_PLAYER
    role_labels = dict(AppUserRole.ROLE_CHOICES)
    return render(
        request,
        'football/player_dashboard.html',
        {
            'player_stats': player_stats,
            'team_name': primary_team.name,
            'match_options': match_options,
            'selected_match': selected_match,
            'selected_match_id': selected_match_id,
            'selected_match_total_actions': selected_match_total_actions,
            'current_role': current_role,
            'current_role_label': role_labels.get(current_role, 'Jugador'),
        },
    )


def coach_overview_page(request):
    sources = list(ScrapeSource.objects.filter(is_active=True))
    technical_roles = {
        AppUserRole.ROLE_COACH,
        AppUserRole.ROLE_FITNESS,
        AppUserRole.ROLE_GOALKEEPER,
        AppUserRole.ROLE_ANALYST,
        AppUserRole.ROLE_ADMIN,
    }
    role_labels = dict(AppUserRole.ROLE_CHOICES)
    role_rows = list(AppUserRole.objects.select_related('user').filter(role__in=technical_roles))
    technical_members = []
    technical_members_lower = set()
    for role_row in role_rows:
        if not role_row.user.is_active:
            continue
        full_name = role_row.user.get_full_name().strip() or role_row.user.username
        label = f'{role_labels.get(role_row.role, "Técnico")} · {full_name}'
        technical_members.append(label)
        technical_members_lower.add(label.lower())

    extra_assignments = [
        ('alonso', 'Preparador de porteros'),
        ('jeremias', 'Preparador físico'),
    ]
    for role_row in role_rows:
        if not role_row.user.is_active:
            continue
        full_name = role_row.user.get_full_name().strip() or role_row.user.username
        name_folded = full_name.lower()
        for key, role_label in extra_assignments:
            if key in name_folded:
                extra_label = f'{role_label} · {full_name}'
                if extra_label.lower() not in technical_members_lower:
                    technical_members.append(extra_label)
                    technical_members_lower.add(extra_label.lower())

    if not technical_members:
        technical_members = ['Sin miembros técnicos configurados en Admin']
    summary = {
        'entrainers': technical_members,
        'rival': [
            'Último rival: Atlético de Marbella',
            'Consecutivos sin recibir gol: 1',
            'Fortaleza: laterales rápidos',
        ],
    }
    return render(
        request,
        'football/coach_overview.html',
        {
            'sources': sources,
            'summary': summary,
        },
    )


def incident_page(request):
    return render(
        request,
        'football/incidents.html',
        {
            'title': 'Registro de incidencias',
        },
    )


def get_current_convocation_record(team, match=None, fallback_to_latest=True):
    if not team:
        return None
    qs = ConvocationRecord.objects.filter(team=team, is_current=True).prefetch_related('players')
    if match:
        by_match = qs.filter(match=match).order_by('-created_at').first()
        if by_match:
            return by_match
        if not fallback_to_latest:
            return None
    return qs.order_by('-created_at').first()


def get_current_convocation(team, match=None):
    record = get_current_convocation_record(team, match=match)
    if record:
        return record.players.order_by('name')
    return Player.objects.filter(team=team, is_active=True).order_by('name')


def _normalize_lineup_payload(payload, allowed_players):
    allowed = {str(player.id): player for player in (allowed_players or [])}
    base = {'starters': [], 'bench': []}
    if not isinstance(payload, dict):
        return base
    for section in ('starters', 'bench'):
        rows = payload.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = str(row.get('id') or '').strip()
            if not pid or pid not in allowed:
                continue
            player = allowed[pid]
            base[section].append(
                {
                    'id': str(player.id),
                    'name': (player.name or '').upper(),
                    'number': player.number if player.number is not None else '--',
                    'position': player.position or '',
                    'photo': resolve_player_photo_url(None, player),
                }
            )
    # dedupe: a player must appear only once across sections
    seen = set()
    for section in ('starters', 'bench'):
        deduped = []
        for row in base[section]:
            pid = str(row.get('id'))
            if pid in seen:
                continue
            seen.add(pid)
            deduped.append(row)
        base[section] = deduped
    if len(base['starters']) > 11:
        overflow = base['starters'][11:]
        base['starters'] = base['starters'][:11]
        base['bench'].extend(overflow)
    return base


def _build_default_lineup_payload(convocation_players):
    if not convocation_players:
        return {'starters': [], 'bench': []}
    sorted_players = sorted(
        convocation_players,
        key=lambda p: ((p.number if p.number is not None else 999), (p.name or '').lower()),
    )
    starters = sorted_players[:11]
    bench = sorted_players[11:]
    return _normalize_lineup_payload(
        {
            'starters': [{'id': str(p.id)} for p in starters],
            'bench': [{'id': str(p.id)} for p in bench],
        },
        convocation_players,
    )


@login_required
def match_action_page(request):
    if not _is_admin_user(request.user):
        return HttpResponse('Solo administradores pueden editar estadísticas de partido.', status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    requested_match = get_requested_match(request, primary_team)
    active_match = requested_match or get_active_match(primary_team)
    convocation_record = get_current_convocation_record(
        primary_team,
        match=active_match,
        fallback_to_latest=True,
    )
    convocation_players = convocation_record.players.order_by('name') if convocation_record else Player.objects.none()
    convocation_players = list(convocation_players)
    for player in convocation_players:
        player.photo_url = resolve_player_photo_url(request, player)
    initial_lineup_payload = {'starters': [], 'bench': []}
    if convocation_record:
        stored_lineup = convocation_record.lineup_data if isinstance(convocation_record.lineup_data, dict) else {}
        normalized_stored = _normalize_lineup_payload(stored_lineup, convocation_players)
        if normalized_stored['starters'] or normalized_stored['bench']:
            initial_lineup_payload = normalized_stored
        else:
            initial_lineup_payload = _build_default_lineup_payload(convocation_players)
            convocation_record.lineup_data = initial_lineup_payload
            convocation_record.save(update_fields=['lineup_data'])
    message = None
    if request.method == 'POST':
        action = request.POST.get('action_type', '').strip()
        player_id = request.POST.get('player')
        player = next((item for item in convocation_players if str(item.id) == str(player_id)), None)
        if action and player:
            message = f"Acción de partido para {player.name} registrada ({action})."
        else:
            message = "Completa el jugador y el tipo de acción."
    # Persistencia de registro en vivo:
    # prioriza siempre las acciones pendientes del partido activo (touch-field)
    # para que al recargar no "desaparezcan" hasta guardar/finalizar.
    if active_match:
        recent_events = (
            MatchEvent.objects.filter(
                match=active_match,
                source_file='registro-acciones',
                system='touch-field',
            )
            .select_related('player')
            .order_by('-created_at', '-id')[:120]
        )
    else:
        recent_match_ids = list(
            Match.objects.filter(Q(home_team=primary_team) | Q(away_team=primary_team))
            .order_by('-date', '-id')
            .values_list('id', flat=True)[:12]
        )
        recent_events = (
            MatchEvent.objects.filter(match_id__in=recent_match_ids)
            .select_related('player')
            .order_by('-created_at', '-id')[:20]
        )
    official_next = load_preferred_next_match_payload()

    def _payload_date_label(payload):
        raw_date = (payload or {}).get('date')
        if not raw_date:
            return None
        value = str(raw_date).strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(value, fmt).strftime('%d/%m/%Y')
            except ValueError:
                continue
        return None

    substitution_history = []
    match_info = None
    if active_match:
        opponent = active_match.away_team if active_match.home_team == primary_team else active_match.home_team
        match_info = {
            'match_id': active_match.id,
            'opponent': opponent.name if opponent else '',
            'location': active_match.location or '',
            'round': active_match.round or '',
            'date': active_match.date.strftime('%d/%m/%Y') if active_match.date else None,
            'time': active_match.date.strftime('%H:%M') if active_match.date else '00:00',
        }
        if official_next:
            official_opponent = _payload_opponent_name(official_next)
            official_round = str(official_next.get('round') or '').strip()
            official_location = str(official_next.get('location') or '').strip()
            official_date_label = _payload_date_label(official_next)
            if official_opponent:
                match_info['opponent'] = official_opponent
            if official_round:
                match_info['round'] = official_round
            if official_location:
                match_info['location'] = official_location
            if official_date_label:
                match_info['date'] = official_date_label
        if convocation_record:
            if convocation_record.opponent_name:
                match_info['opponent'] = convocation_record.opponent_name
            if convocation_record.round:
                match_info['round'] = convocation_record.round
            if convocation_record.location:
                match_info['location'] = convocation_record.location
            if convocation_record.match_date:
                match_info['date'] = convocation_record.match_date.strftime('%d/%m/%Y')
            if convocation_record.match_time:
                match_info['time'] = convocation_record.match_time.strftime('%H:%M')
        substitution_events = (
            MatchEvent.objects.filter(match=active_match, player__team=primary_team)
            .select_related('player')
            .order_by('created_at', 'id')
        )
        for event in substitution_events:
            if not (
                is_substitution_event(event.event_type, event.zone)
                or is_substitution_entry(event.event_type, event.result, event.zone)
                or is_substitution_exit(event.event_type, event.result, event.zone)
            ):
                continue
            minute_label = f"{event.minute}'" if event.minute is not None else "--'"
            result_label = (event.result or '').strip() or (event.zone or '').strip() or 'Sustitución'
            player_name = event.player.name if event.player else 'Jugador'
            substitution_history.append(f"{player_name} · {minute_label} · {result_label}".upper())
    universo_lookup = _build_universo_standings_lookup(load_universo_snapshot())
    category_rivals = []
    team_fields = []
    group = primary_team.group
    if group:
        team_fields = gather_team_fields_for_group(group)
        field_map = {item['team_slug']: item['location'] for item in team_fields if item.get('team_slug')}
        standings = (
            TeamStanding.objects.filter(group=group)
            .select_related('team')
            .order_by('position')
        )
        for standing in standings:
            team = standing.team
            team_name = team.name if team else ''
            team_meta = universo_lookup.get(_normalize_team_lookup_key(team_name), {})
            full_name = team_meta.get('full_name') or team_name
            category_rivals.append(
                {
                    'position': standing.position,
                    'name': full_name,
                    'short_name': team.short_name or full_name,
                    'crest_url': team_meta.get('crest_url') or '',
                    'team_code': team_meta.get('team_code') or '',
                    'points': standing.points,
                    'played': standing.played,
                    'slug': team.slug,
                    'is_primary': team == primary_team,
                    'field_location': field_map.get(team.slug, ''),
                }
            )
    match_selector_options = list(
        _team_match_queryset(primary_team).order_by('-date', '-id')
    )
    selected_match_id = active_match.id if active_match else None
    return render(
        request,
        'football/match_actions.html',
        {
            'players': convocation_players,
            'convocation_players': convocation_players,
            'avatar_url': request.build_absolute_uri(static('football/images/player-avatar.svg')),
            'message': message,
            'team_name': primary_team.name,
            'quick_actions': load_match_actions(),
            'field_zone_defs': FIELD_ZONES,
            'result_options': load_match_results(),
            'tercio_options': STANDARD_TERCIO_LABELS,
            'recent_events': recent_events,
            'match_info': match_info,
            'category_rivals': category_rivals,
            'team_fields': team_fields,
            'substitution_history': substitution_history,
            'initial_lineup_json': json.dumps(initial_lineup_payload, ensure_ascii=False),
            'match_selector_options': match_selector_options,
            'selected_match_id': selected_match_id,
        },
    )


@authenticated_write
@require_POST
def register_match_action(request):
    if not _is_admin_user(request.user):
        return JsonResponse({'error': 'Solo administradores pueden editar estadísticas de partido.'}, status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    player_id = request.POST.get('player')
    action_type = (request.POST.get('action_type') or '').strip()
    action_type_key = action_type.lower()
    requested_match = get_requested_match(request, primary_team)
    target_match = requested_match or get_active_match(primary_team)
    convocation_record = get_current_convocation_record(
        primary_team,
        match=target_match,
        fallback_to_latest=True,
    )
    if not convocation_record:
        return JsonResponse({'error': 'No hay convocatoria activa guardada para registrar acciones'}, status=400)

    player = None
    if not _is_team_only_action(action_type_key):
        player = convocation_record.players.filter(id=player_id).first()
        if not player:
            return JsonResponse({'error': 'Selecciona un jugador convocado válido'}, status=400)

    if not action_type:
        return JsonResponse({'error': 'Especifica el tipo de acción'}, status=400)
    match = target_match
    if not match:
        return JsonResponse({'error': 'No hay partido disponible para registrar acciones'}, status=400)
    if player and (not convocation_record.players.filter(id=player.id).exists()):
        return JsonResponse({'error': 'Jugador fuera de convocatoria para este partido'}, status=400)
    minute = _parse_int(request.POST.get('minute'))
    if minute is not None:
        minute = max(0, min(minute, 120))
    period = _parse_int(request.POST.get('period'))
    result = (request.POST.get('result') or '').strip()
    zone = (request.POST.get('zone') or '').strip()
    tercio = zone_to_tercio(zone)
    observation = (request.POST.get('observation') or '').strip()
    duplicate_window = timezone.now() - timedelta(seconds=8)
    recent_duplicates = MatchEvent.objects.filter(
        match=match,
        player=player if player else None,
        minute=minute if minute is not None else None,
        period=period,
        source_file='registro-acciones',
        system='touch-field',
        created_at__gte=duplicate_window,
    ).order_by('-id')
    for existing in recent_duplicates:
        if (
            _canonical_action_value(existing.event_type) == _canonical_action_value(action_type)
            and _canonical_action_value(existing.result) == _canonical_action_value(result)
            and _canonical_action_value(existing.zone) == _canonical_action_value(zone)
            and _canonical_action_value(existing.tercio) == _canonical_action_value(tercio)
            and _canonical_action_value(existing.observation) == _canonical_action_value(observation)
        ):
            return JsonResponse(_serialize_match_event(existing, duplicate=True))

    event = MatchEvent.objects.create(
        match=match,
        player=player if player else None,
        minute=minute if minute is not None else None,
        period=period,
        event_type=action_type,
        result=result,
        zone=zone,
        tercio=tercio,
        observation=observation,
        source_file='registro-acciones',
        system='touch-field',
    )
    return JsonResponse(_serialize_match_event(event, duplicate=False))


@authenticated_write
@require_POST
def save_match_lineup(request):
    if not _is_admin_user(request.user):
        return JsonResponse({'error': 'Solo administradores pueden editar estadísticas de partido.'}, status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    requested_match = get_requested_match(request, primary_team)
    target_match = requested_match or get_active_match(primary_team)
    convocation_record = get_current_convocation_record(
        primary_team,
        match=target_match,
        fallback_to_latest=True,
    )
    if not convocation_record:
        return JsonResponse({'error': 'No hay convocatoria activa para guardar el 11'}, status=400)
    payload = {}
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({'error': 'Payload inválido'}, status=400)
    lineup = payload.get('lineup')
    allowed_players = list(convocation_record.players.all())
    normalized = _normalize_lineup_payload(lineup, allowed_players)
    convocation_record.lineup_data = normalized
    convocation_record.save(update_fields=['lineup_data'])
    return JsonResponse({'saved': True, 'starters': len(normalized['starters']), 'bench': len(normalized['bench'])})


@authenticated_write
@require_POST
def delete_match_action(request):
    if not _is_admin_user(request.user):
        return JsonResponse({'error': 'Solo administradores pueden editar estadísticas de partido.'}, status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    event_id = request.POST.get('event_id')
    requested_match = get_requested_match(request, primary_team)
    candidate_events = MatchEvent.objects.filter(
        Q(match__home_team=primary_team) | Q(match__away_team=primary_team)
    )
    if requested_match:
        candidate_events = candidate_events.filter(match=requested_match)
    try:
        event = candidate_events.get(id=event_id)
    except MatchEvent.DoesNotExist:
        return JsonResponse({'error': 'Evento no encontrado'}, status=404)
    event.delete()
    return JsonResponse({'deleted': event_id})


@authenticated_write
@require_POST
def finalize_match_actions(request):
    if not _is_admin_user(request.user):
        return JsonResponse({'error': 'Solo administradores pueden editar estadísticas de partido.'}, status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    requested_match = get_requested_match(request, primary_team)
    match = requested_match or get_active_match(primary_team)
    if not match:
        return JsonResponse({'error': 'No hay partido activo para guardar'}, status=400)
    payload = {}
    try:
        if request.body:
            payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = {}
    _apply_match_info_overrides(match, primary_team, payload.get('match_info'))
    pending_events = list(
        MatchEvent.objects.filter(match=match, system='touch-field').select_related('player')
    )
    if not pending_events:
        return JsonResponse({'saved': True, 'updated': 0, 'match_id': match.id})
    # Limpiar tarjetas y sustituciones anteriores
    MatchEvent.objects.filter(
        match=match,
        system='touch-field-final',
    ).filter(
        Q(event_type__icontains='tarjeta') | Q(event_type__icontains='sustitucion') | Q(event_type__icontains='sustitución') | Q(event_type__icontains='cambio'),
    ).delete()

    # Evita consolidar duplicados por doble click/reintento de red en pocos segundos.
    # Importante: no eliminar acciones reales repetidas a lo largo del partido.
    dedupe_seconds = 12
    existing_final_by_signature = defaultdict(list)
    for event in MatchEvent.objects.filter(match=match, system='touch-field-final').select_related('player'):
        existing_final_by_signature[_event_signature(event)].append(event.created_at)
    seen_pending_by_signature = defaultdict(list)
    keep_ids = []
    drop_ids = []
    for event in sorted(pending_events, key=lambda e: e.created_at or timezone.now()):
        signature = _event_signature(event)
        created_at = event.created_at or timezone.now()
        existing_times = existing_final_by_signature.get(signature, [])
        pending_times = seen_pending_by_signature.get(signature, [])
        is_near_duplicate = any(
            abs((created_at - known).total_seconds()) <= dedupe_seconds
            for known in [*existing_times, *pending_times]
        )
        if is_near_duplicate:
            drop_ids.append(event.id)
            continue
        seen_pending_by_signature[signature].append(created_at)
        keep_ids.append(event.id)

    if drop_ids:
        MatchEvent.objects.filter(id__in=drop_ids, match=match, system='touch-field').delete()

    updated = 0
    if keep_ids:
        updated = MatchEvent.objects.filter(id__in=keep_ids).update(system='touch-field-final')
    return JsonResponse(
        {
            'saved': True,
            'updated': updated,
            'deduplicated': len(drop_ids),
            'match_id': match.id,
            'match_label': str(match),
        }
    )


@authenticated_write
@require_POST
def reset_match_action_register(request):
    if not _is_admin_user(request.user):
        return JsonResponse({'error': 'Solo administradores pueden editar estadísticas de partido.'}, status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    requested_match = get_requested_match(request, primary_team)
    match = requested_match or get_active_match(primary_team)
    if not match:
        return JsonResponse({'error': 'No hay partido activo para reiniciar'}, status=400)
    deleted_count, _ = MatchEvent.objects.filter(
        match=match,
        source_file='registro-acciones',
    ).filter(
        Q(system='touch-field') | Q(system='touch-field-final'),
    ).delete()
    return JsonResponse(
        {
            'reset': True,
            'deleted': int(deleted_count),
            'match_id': match.id,
        }
    )


def convocation_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    all_players = list(Player.objects.filter(team=primary_team, is_active=True).order_by('name'))
    for player in all_players:
        player.photo_url = resolve_player_photo_url(request, player)
    roster_cache = get_roster_stats_cache()
    manual_overrides = get_manual_player_base_overrides(primary_team)
    universo_snapshot = load_universo_snapshot() or {}
    universo_players = universo_snapshot.get('players') if isinstance(universo_snapshot, dict) else []
    universo_map = {}
    universo_by_number = {}
    if isinstance(universo_players, list):
        for item in universo_players:
            if not isinstance(item, dict):
                continue
            team_name = str(item.get('team') or '').strip().lower()
            if team_name and 'benagalbon' not in team_name:
                continue
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            key = normalize_player_name(name)
            universo_map[key] = item
            dorsal_raw = str(item.get('dorsal') or '').strip()
            if dorsal_raw.isdigit():
                universo_by_number[int(dorsal_raw)] = item

    def _find_universo_entry(player_obj):
        key = normalize_player_name(player_obj.name)
        direct = universo_map.get(key)
        if direct:
            return direct
        if player_obj.number is not None and player_obj.number in universo_by_number:
            return universo_by_number[player_obj.number]
        compact = key.replace('-', '')
        for ukey, entry in universo_map.items():
            ucompact = ukey.replace('-', '')
            if compact in ucompact or ucompact in compact:
                return entry
        tokens = [token for token in compact.split('-') if token]
        for ukey, entry in universo_map.items():
            u_tokens = [token for token in ukey.replace('-', ' ').split() if token]
            overlap = sum(1 for token in tokens if token in u_tokens)
            if overlap >= 2:
                return entry
        return {}
    active_injury_ids = get_active_injury_player_ids([p.id for p in all_players])
    active_match = get_active_match(primary_team)
    sanctioned_player_ids = get_sanctioned_player_ids_from_previous_round(
        primary_team,
        reference_match=active_match,
    )
    filtered_players = []
    today = timezone.localdate()
    for player in all_players:
        roster_entry = find_roster_entry(player.name, roster_cache) or {}
        manual_entry = manual_overrides.get(player.id, {})
        universo_entry = _find_universo_entry(player) or {}
        yellow_cards = (
            manual_entry.get('yellow_cards')
            if manual_entry.get('yellow_cards') is not None
            else _parse_int(universo_entry.get('yellow_cards'))
            if universo_entry.get('yellow_cards') not in (None, '')
            else roster_entry.get('yellow_cards', 0)
        )
        red_cards = (
            manual_entry.get('red_cards')
            if manual_entry.get('red_cards') is not None
            else _parse_int(universo_entry.get('red_cards'))
            if universo_entry.get('red_cards') not in (None, '')
            else roster_entry.get('red_cards', 0)
        )
        player.yellow_cards = int(yellow_cards or 0)
        player.red_cards = int(red_cards or 0)
        player.is_sanctioned = (player.id in sanctioned_player_ids) or is_manual_sanction_active(player, today=today)
        player.is_apercibido = player.yellow_cards in {4, 9, 14}
        player.has_active_injury = player.id in active_injury_ids
        filtered_players.append(player)
    players = filtered_players
    convocation_record = get_current_convocation_record(primary_team)
    selected_player_ids = []
    if convocation_record:
        available_ids = {player.id for player in players}
        selected_player_ids = [
            player_id
            for player_id in convocation_record.players.values_list('id', flat=True)
            if player_id in available_ids
        ]

    next_match_payload = load_preferred_next_match_payload()
    if not next_match_payload and primary_team.group:
        next_match_payload = get_next_match(primary_team, primary_team.group)
    if isinstance(next_match_payload, dict) and str(next_match_payload.get('status') or '').lower() != 'next':
        next_match_payload = None
    default_match_info = normalize_next_match_payload(next_match_payload or {}) if next_match_payload else {}

    opponent_name = ''
    if isinstance(default_match_info, dict):
        opponent = default_match_info.get('opponent')
        if isinstance(opponent, dict):
            opponent_name = str(opponent.get('name') or '').strip()
        elif isinstance(opponent, str):
            opponent_name = opponent.strip()

    match_info = {
        'round': str(default_match_info.get('round') or '').strip() if isinstance(default_match_info, dict) else '',
        'date': str(default_match_info.get('date') or '').strip() if isinstance(default_match_info, dict) else '',
        'time': str(default_match_info.get('time') or '').strip() if isinstance(default_match_info, dict) else '',
        'location': str(default_match_info.get('location') or '').strip() if isinstance(default_match_info, dict) else '',
        'opponent': opponent_name,
    }
    if convocation_record:
        if convocation_record.round:
            match_info['round'] = convocation_record.round
        if convocation_record.match_date:
            match_info['date'] = convocation_record.match_date.isoformat()
        if convocation_record.match_time:
            match_info['time'] = convocation_record.match_time.strftime('%H:%M')
        if convocation_record.location:
            match_info['location'] = convocation_record.location
        if convocation_record.opponent_name:
            match_info['opponent'] = convocation_record.opponent_name

    home_location = 'ESTADIO CAÑA CHAQUETA'
    recent_home_match = (
        Match.objects.filter(
            group=primary_team.group,
            home_team=primary_team,
        )
        .exclude(location__isnull=True)
        .exclude(location__exact='')
        .order_by('-date', '-id')
        .first()
    )
    if recent_home_match and recent_home_match.location:
        home_location = recent_home_match.location.strip()

    team_fields = gather_team_fields_for_group(primary_team.group)
    field_map = {
        normalize_label(item.get('team_name') or ''): (item.get('location') or '').strip()
        for item in team_fields
        if item.get('team_name')
    }

    opponent_options = []
    seen_opponents = set()
    group_teams = Team.objects.filter(group=primary_team.group).order_by('name') if primary_team.group else Team.objects.none()
    for team in group_teams:
        if team.id == primary_team.id:
            continue
        key = normalize_label(team.name)
        if not key or key in seen_opponents:
            continue
        seen_opponents.add(key)
        opponent_options.append(
            {
                'name': team.name,
                'short_name': team.short_name or team.name,
                'location': field_map.get(key, ''),
            }
        )

    current_opponent = str(match_info.get('opponent') or '').strip()
    current_key = normalize_label(current_opponent)
    if current_opponent and current_key and current_key not in seen_opponents:
        opponent_options.append(
            {
                'name': current_opponent,
                'short_name': current_opponent,
                'location': field_map.get(current_key, ''),
            }
        )

    return render(
        request,
        'football/convocation.html',
        {
            'players': players,
            'team_name': primary_team.name,
            'avatar_url': request.build_absolute_uri(static('football/images/player-avatar.svg')),
            'selected_player_ids_json': json.dumps(selected_player_ids),
            'injured_player_ids_json': json.dumps(
                [p.id for p in all_players if getattr(p, 'has_active_injury', False)]
            ),
            'match_info': match_info,
            'has_saved_convocation': bool(convocation_record and selected_player_ids),
            'opponent_options_json': json.dumps(opponent_options, ensure_ascii=False),
            'home_location_label': home_location,
        },
    )


@authenticated_write
@require_POST
def save_convocation(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    try:
        payload = json.loads(request.body or '[]')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido'}, status=400)

    if isinstance(payload, dict):
        raw_players = payload.get('players') or payload.get('player_ids') or []
        match_info = payload.get('match_info') if isinstance(payload.get('match_info'), dict) else {}
    else:
        raw_players = payload
        match_info = {}

    try:
        player_ids = [int(pid) for pid in raw_players if pid]
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Formato de jugadores inválido'}, status=400)
    players = Player.objects.filter(team=primary_team, is_active=True, id__in=player_ids)
    blocked_injury_ids = get_active_injury_player_ids(players.values_list('id', flat=True))
    players = players.exclude(id__in=blocked_injury_ids)
    if not players.exists():
        return JsonResponse({'error': 'No se encontraron jugadores para la convocatoria'}, status=400)

    round_value = str(match_info.get('round') or '').strip()
    location_value = str(match_info.get('location') or '').strip()
    opponent_value = str(match_info.get('opponent') or '').strip()
    date_value_raw = str(match_info.get('date') or '').strip()
    time_value_raw = str(match_info.get('time') or '').strip()

    parsed_match_date = None
    if date_value_raw:
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                parsed_match_date = datetime.strptime(date_value_raw, fmt).date()
                break
            except ValueError:
                continue
    parsed_match_time = None
    if time_value_raw:
        for fmt in ('%H:%M', '%H:%M:%S'):
            try:
                parsed_match_time = datetime.strptime(time_value_raw, fmt).time()
                break
            except ValueError:
                continue

    target_match = get_active_match(primary_team)
    if not target_match:
        season = None
        if primary_team.group and primary_team.group.season:
            season = primary_team.group.season
        if not season:
            season = Season.objects.filter(is_current=True).order_by('-start_date', '-id').first()
        if season:
            target_match = Match.objects.create(
                season=season,
                group=primary_team.group,
                round=round_value,
                date=parsed_match_date,
                location=location_value,
                home_team=primary_team,
                away_team=None,
            )

    if target_match:
        datetime_label = date_value_raw
        if time_value_raw:
            datetime_label = f'{date_value_raw} · {time_value_raw}' if date_value_raw else time_value_raw
        _apply_match_info_overrides(
            target_match,
            primary_team,
            {
                'round': round_value,
                'location': location_value,
                'datetime': datetime_label,
                'opponent': opponent_value,
            },
        )

    active_injury_ids = get_active_injury_player_ids(players.values_list('id', flat=True))
    injured_players = [
        player.name
        for player in players
        if player.id in active_injury_ids
    ]

    with transaction.atomic():
        ConvocationRecord.objects.filter(team=primary_team, is_current=True).update(is_current=False)
        record = ConvocationRecord.objects.create(
            team=primary_team,
            match=target_match,
            round=round_value,
            match_date=parsed_match_date,
            match_time=parsed_match_time,
            location=location_value,
            opponent_name=opponent_value,
        )
        record.players.set(players.distinct())
    cache.delete(_dashboard_cache_key(primary_team.id))
    return JsonResponse(
        {
            'saved': True,
            'count': players.count(),
            'match_id': target_match.id if target_match else None,
            'injury_warning_count': len(injured_players),
            'injury_warning_players': injured_players[:8],
        }
    )


@login_required
def convocation_pdf(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    convocation_record = get_current_convocation_record(primary_team)
    if not convocation_record:
        return HttpResponse('No hay convocatoria guardada.', status=400)

    players = list(convocation_record.players.order_by('number', 'name'))
    if not players:
        return HttpResponse('No hay jugadores convocados.', status=400)

    def _sort_player_key(player):
        number = player.number if player.number is not None else 999
        return (number, (player.name or '').lower())

    ordered_players = sorted(players, key=_sort_player_key)

    static_base_dir = Path(settings.BASE_DIR) / 'static'
    logo_static_path = static_base_dir / 'football' / 'images' / 'cdb-logo.png'
    avatar_static_path = static_base_dir / 'football' / 'images' / 'player-avatar.svg'
    logo_data_uri = _file_as_data_uri(logo_static_path)
    avatar_data_uri = _file_as_data_uri(avatar_static_path)

    include_player_photos = str(
        os.getenv('CONVOCATION_PDF_PLAYER_PHOTOS', '0')
    ).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _player_photo_src(player_obj):
        # Default to lightweight avatar for reliability/performance on Render.
        if not include_player_photos:
            if avatar_data_uri:
                return avatar_data_uri
            return request.build_absolute_uri(static('football/images/player-avatar.svg'))

        player_static_rel = resolve_player_photo_static_path(player_obj)
        if player_static_rel:
            player_data_uri = _image_file_as_small_data_uri(
                static_base_dir / player_static_rel,
                max_width=220,
                max_height=220,
                quality=65,
            )
            if player_data_uri:
                return player_data_uri
            return request.build_absolute_uri(static(player_static_rel))
        if avatar_data_uri:
            return avatar_data_uri
        return request.build_absolute_uri(static('football/images/player-avatar.svg'))

    player_rows = [
        {
            'number': player.number,
            'name': player.name,
            'photo_src': _player_photo_src(player),
        }
        for player in ordered_players
    ]
    midpoint = (len(player_rows) + 1) // 2
    left_column_players = player_rows[:midpoint]
    right_column_players = player_rows[midpoint:]

    date_label = convocation_record.match_date.strftime('%d/%m/%Y') if convocation_record.match_date else '--'
    time_label = convocation_record.match_time.strftime('%H:%M') if convocation_record.match_time else '--:--'
    location_label = convocation_record.location or (convocation_record.match.location if convocation_record.match else '')
    rival_label = convocation_record.opponent_name
    if not rival_label and convocation_record.match:
        opponent = (
            convocation_record.match.away_team
            if convocation_record.match.home_team_id == primary_team.id
            else convocation_record.match.home_team
        )
        rival_label = opponent.name if opponent else ''

    rival_name = (rival_label or '').strip() or 'Rival por confirmar'
    preferred_next = load_preferred_next_match_payload()
    preferred_opponent = preferred_next.get('opponent') if isinstance(preferred_next, dict) else None
    rival_full_name, rival_crest_url = _resolve_rival_identity(
        rival_name,
        preferred_opponent=preferred_opponent,
    )
    rival_crest_url = _absolute_universo_url(rival_crest_url)

    round_digits = ''.join(re.findall(r'\d+', convocation_record.round or ''))
    round_short = f'J{round_digits}' if round_digits else 'J'
    date_human = date_label
    if convocation_record.match_date:
        day_map = ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB', 'DOM']
        month_map = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
        weekday = day_map[convocation_record.match_date.weekday()]
        month = month_map[convocation_record.match_date.month - 1]
        date_human = f'{weekday} {convocation_record.match_date.day} {month}'

    rival_crest_src = str(rival_crest_url or '').strip()
    if rival_crest_src.startswith('http://') or rival_crest_src.startswith('https://'):
        # Avoid external HTTP fetches during PDF rendering to reduce timeout/502 risk on Render.
        rival_crest_src = ''

    context = {
        'team_name': primary_team.name,
        'team_full_name': primary_team.name,
        'round_label': convocation_record.round or 'Jornada por confirmar',
        'round_short': round_short,
        'date_label': date_label,
        'date_human': date_human,
        'time_label': time_label,
        'location_label': location_label or 'Campo por confirmar',
        'rival_label': rival_name,
        'rival_full_name': rival_full_name,
        'rival_crest_src': rival_crest_src,
        'players': player_rows,
        'left_column_players': left_column_players,
        'right_column_players': right_column_players,
        'coach_name': os.getenv('TEAM_COACH_NAME', 'Aitor Castillo'),
        'club_hashtag': os.getenv('TEAM_HASHTAG', '#VamosVerdes'),
        'logo_src': logo_data_uri or request.build_absolute_uri(static('football/images/cdb-logo.png')),
        'avatar_src': avatar_data_uri or request.build_absolute_uri(static('football/images/player-avatar.svg')),
        'team_photo_url': request.build_absolute_uri(static('football/images/team-01.jpg')),
        'team_photo_data_uri': '',
        'coach_photo_url': request.build_absolute_uri(static(os.getenv('TEAM_COACH_PHOTO', 'football/images/team-01.jpg'))),
    }
    team_photo = resolve_team_photo_for_pdf(request)
    context['team_photo_url'] = team_photo.get('url') or context['team_photo_url']
    context['coach_photo_url'] = context['team_photo_url']
    context['team_photo_data_uri'] = team_photo.get('data_uri') or ''

    html = render_to_string('football/convocation_pdf.html', context)
    filename = f'convocatoria-{timezone.localdate().isoformat()}'
    return _build_pdf_response_or_html_fallback(request, html, filename)


@login_required
def session_task_pdf(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task:
        raise Http404('Tarea no encontrada')

    team = task.session.microcycle.team
    tokens = []
    tactical_layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    raw_tokens = tactical_layout.get('tokens') if isinstance(tactical_layout, dict) else []
    meta = tactical_layout.get('meta') if isinstance(tactical_layout, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    surface_map = {key: label for key, label in TASK_SURFACE_CHOICES}
    pitch_map = {key: label for key, label in TASK_PITCH_FORMAT_CHOICES}
    phase_map = {key: label for key, label in TASK_GAME_PHASE_CHOICES}
    methodology_map = {key: label for key, label in TASK_METHODOLOGY_CHOICES}
    complexity_map = {key: label for key, label in TASK_COMPLEXITY_CHOICES}
    constraint_map = {key: label for key, label in TASK_CONSTRAINT_CHOICES}
    meta = dict(meta)
    if meta.get('surface'):
        meta['surface'] = surface_map.get(str(meta.get('surface')), str(meta.get('surface')))
    if meta.get('pitch_format'):
        meta['pitch_format'] = pitch_map.get(str(meta.get('pitch_format')), str(meta.get('pitch_format')))
    if meta.get('game_phase'):
        meta['game_phase'] = phase_map.get(str(meta.get('game_phase')), str(meta.get('game_phase')))
    if meta.get('methodology'):
        meta['methodology'] = methodology_map.get(str(meta.get('methodology')), str(meta.get('methodology')))
    if meta.get('complexity'):
        meta['complexity'] = complexity_map.get(str(meta.get('complexity')), str(meta.get('complexity')))
    if isinstance(meta.get('constraints'), list):
        meta['constraints'] = [constraint_map.get(str(v), str(v)) for v in meta.get('constraints')]
    animation_frames = tactical_layout.get('timeline') if isinstance(tactical_layout, dict) else []
    if not isinstance(animation_frames, list):
        animation_frames = []
    material_icon_by_kind = {
        'cone': '△',
        'marker': '◉',
        'marker-flat': '◍',
        'pole': '┃',
        'ring': '◯',
        'ball': '●',
        'hurdle': '⊓',
        'ladder': '☷',
        'slalom': '╽',
        'mini-hurdle': '⫍',
        'goal': '⌷',
        'mini-goal': '⌸',
        'gk-goal': '▭',
        'mannequin': '♞',
        'dummy': '♜',
        'wall': '▥',
        'bib': '▣',
        'gps': '⌖',
        'timer': '◷',
        'whistle': '⌇',
        'board': '▤',
        'band': '∞',
        'trx': '⟂',
        'box': '▧',
        'sled': '⎍',
        'stake': '⎸',
        'arc': '◠',
        'target': '◎',
        'medicine-ball': '◒',
        'tape': '═',
    }

    if isinstance(raw_tokens, list):
        for token in raw_tokens:
            if not isinstance(token, dict):
                continue
            x = _parse_int(token.get('x'))
            y = _parse_int(token.get('y'))
            x = max(2, min(x if x is not None else 50, 98))
            y = max(2, min(y if y is not None else 50, 98))
            token_type = str(token.get('type') or '').strip()
            token_kind = str(token.get('kind') or '').strip()
            token_icon = ''
            token_asset = str(token.get('asset') or '').strip()
            if token_type == 'material':
                token_icon = str(token.get('icon') or '').strip() or material_icon_by_kind.get(token_kind, '•')
            token_asset_url = ''
            if token_asset:
                if token_asset.startswith('/'):
                    token_asset_url = request.build_absolute_uri(token_asset)
                else:
                    token_asset_url = request.build_absolute_uri(static(token_asset))
            tokens.append(
                {
                    'label': str(token.get('label') or '?')[:16],
                    'title': str(token.get('title') or token.get('label') or '').strip(),
                    'type': token_type,
                    'kind': token_kind,
                    'icon': token_icon,
                    'asset_url': token_asset_url,
                    'x': x,
                    'y': y,
                }
            )

    def _split_lines(value):
        text = str(value or '').replace('\r', '\n')
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return lines or ['-']

    context = {
        'team_name': team.name,
        'task': task,
        'session': task.session,
        'microcycle': task.session.microcycle,
        'objective_lines': _split_lines(task.objective),
        'coaching_lines': _split_lines(task.coaching_points),
        'rules_lines': _split_lines(task.confrontation_rules),
        'tokens': tokens,
        'task_meta': meta,
        'animation_frames_count': len(animation_frames),
        'logo_url': request.build_absolute_uri(static('football/images/cdb-logo.png')),
        'generated_at': timezone.localtime(),
    }
    html = render_to_string('football/session_task_pdf.html', context)
    filename = slugify(f'tarea-{task.session.session_date}-{task.title}') or f'tarea-{task.id}'
    return _build_pdf_response_or_html_fallback(request, html, filename)


def _resolve_static_asset_file(asset_value):
    raw = str(asset_value or '').strip()
    if not raw:
        return None
    if raw.startswith('/static/'):
        rel = raw[len('/static/'):]
    else:
        rel = raw
    rel = rel.lstrip('/')
    roots = [
        Path(settings.BASE_DIR) / 'static',
        Path(settings.BASE_DIR) / 'football' / 'static',
    ]
    for root in roots:
        candidate = root / rel
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


@login_required
def session_task_canva_export(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task:
        raise Http404('Tarea no encontrada')

    team = task.session.microcycle.team
    session = task.session
    tactical_layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = tactical_layout.get('meta') if isinstance(tactical_layout, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    tokens = tactical_layout.get('tokens') if isinstance(tactical_layout, dict) else []
    if not isinstance(tokens, list):
        tokens = []
    timeline = tactical_layout.get('timeline') if isinstance(tactical_layout, dict) else []
    if not isinstance(timeline, list):
        timeline = []

    constraints_value = meta.get('constraints') if isinstance(meta.get('constraints'), list) else []
    canva_fields = {
        'equipo': team.name,
        'fecha_sesion': session.session_date.isoformat() if session.session_date else '',
        'foco_sesion': session.focus or '',
        'tarea': task.title or '',
        'bloque': task.get_block_display() if hasattr(task, 'get_block_display') else task.block,
        'duracion_min': str(task.duration_minutes or ''),
        'objetivo': task.objective or '',
        'consignas': task.coaching_points or '',
        'reglas': task.confrontation_rules or '',
        'superficie': str(meta.get('surface') or ''),
        'formato_campo': str(meta.get('pitch_format') or ''),
        'espacio': str(meta.get('space') or ''),
        'organizacion': str(meta.get('organization') or ''),
        'distribucion': str(meta.get('players_distribution') or ''),
        'carga_objetivo': str(meta.get('load_target') or ''),
        'material': str(meta.get('resources_summary') or ''),
        'progresion': str(meta.get('progression') or ''),
        'regresion': str(meta.get('regression') or ''),
        'trabajo_pausa': str(meta.get('work_rest') or ''),
        'series': str(meta.get('series') or ''),
        'repeticiones': str(meta.get('repetitions') or ''),
        'principio': str(meta.get('principle') or ''),
        'subprincipio': str(meta.get('subprinciple') or ''),
        'puntuacion': str(meta.get('scoring_model') or ''),
        'criterio_exito': str(meta.get('success_criteria') or ''),
        'fase_juego': str(meta.get('game_phase') or ''),
        'subfase': str(meta.get('game_sub_phase') or ''),
        'metodologia': str(meta.get('methodology') or ''),
        'complejidad': str(meta.get('complexity') or ''),
        'carga_cognitiva': str(meta.get('cognitive_load') or ''),
        'carga_emocional': str(meta.get('emotional_load') or ''),
        'targets': str(meta.get('targets') or ''),
        'outcomes': str(meta.get('expected_outcomes') or ''),
        'errores_frecuentes': str(meta.get('common_errors') or ''),
        'correcciones': str(meta.get('corrective_cues') or ''),
        'video_ref': str(meta.get('video_reference') or ''),
        'notas_staff': str(meta.get('staff_notes') or ''),
        'constraints': ' | '.join(str(v) for v in constraints_value),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=list(canva_fields.keys()))
        writer.writeheader()
        writer.writerow(canva_fields)
        zf.writestr('canva/canva_task_data.csv', csv_buffer.getvalue())

        payload = {
            'task_id': task.id,
            'session_id': session.id,
            'team': team.name,
            'created_at': timezone.now().isoformat(),
            'task': canva_fields,
            'tactical_layout': tactical_layout,
        }
        zf.writestr(
            'canva/task_payload.json',
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            'canva/tactical_layout.json',
            json.dumps(
                {'tokens': tokens, 'timeline': timeline, 'meta': meta},
                ensure_ascii=False,
                indent=2,
            ),
        )

        readme = (
            'PACK EXPORT CANVA - WEB STATS\n\n'
            '1) Canva > Crear diseño.\n'
            '2) Apps > Bulk create > Subir CSV: canva/canva_task_data.csv\n'
            '3) Vincula los campos del CSV a textos de tu plantilla.\n'
            '4) Usa canva/tactical_layout.json como referencia de pizarra.\n'
            '5) Usa assets/ para arrastrar iconos/imagenes al diseño.\n'
        )
        zf.writestr('README_CANVA.txt', readme)

        seen_names = set()
        for token in tokens:
            if not isinstance(token, dict):
                continue
            asset_value = token.get('asset')
            source_file = _resolve_static_asset_file(asset_value)
            if not source_file:
                continue
            filename = source_file.name
            if filename in seen_names:
                continue
            seen_names.add(filename)
            zf.write(source_file, arcname=f'assets/{filename}')

    buffer.seek(0)
    slug = slugify(task.title or f'tarea-{task.id}') or f'tarea-{task.id}'
    filename = f'canva-task-{slug}.zip'
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def coach_cards_page(request):
    cards = [
        {
            'title': 'Entrenador',
            'description': 'Convocatoria, 11 inicial, sesiones y multas en un único bloque.',
            'link': 'coach-role-trainer',
            'member_name': 'Aitor · Antonio',
        },
        {
            'title': 'Preparador porteros',
            'description': 'Repositorio táctico y tareas específicas de porteros.',
            'link': 'coach-role-goalkeeper',
            'member_name': 'Sin asignar',
        },
        {
            'title': 'Preparación física',
            'description': 'Espacio preparado para métricas y carga física.',
            'link': 'coach-role-fitness',
            'member_name': 'Sin asignar',
        },
        {
            'title': 'ABP',
            'description': 'Repositorio de sesiones ABP y pizarra táctica con simulación.',
            'link': 'coach-role-abp',
            'member_name': 'Alonso',
        },
        {
            'title': 'Análisis',
            'description': 'Análisis de rival, vídeo y reportes tácticos de partido.',
            'link': 'analysis',
            'member_name': 'Miguel Ángel Pérez · Jose García Menéndez',
        },
    ]
    return render(
        request,
        'football/coach_cards.html',
        {
            'cards': cards,
        },
    )


def coach_role_trainer_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    standing = None
    if primary_team and primary_team.group and primary_team.group.season:
        standing = TeamStanding.objects.filter(
            season=primary_team.group.season,
            group=primary_team.group,
            team=primary_team,
        ).first()
    events = (
        confirmed_events_queryset().filter(player__team=primary_team)
        if primary_team
        else MatchEvent.objects.none()
    )
    total_actions = events.count() if primary_team else 0
    total_matches = (
        Match.objects.filter(Q(home_team=primary_team) | Q(away_team=primary_team)).count()
        if primary_team
        else 0
    )
    goals_for = standing.goals_for if standing else 0
    goals_against = standing.goals_against if standing else 0
    points = standing.points if standing else 0
    rank = standing.position if standing else 0
    yellows = sum(1 for event in events if is_yellow_card_event(event.event_type, event.result, event.zone))
    reds = sum(1 for event in events if is_red_card_event(event.event_type, event.result, event.zone))
    duel_classifications = [
        classify_duel_event(event.event_type, event.result, event.observation, event.zone)
        for event in events
    ]
    duels = [item for item in duel_classifications if item.get('is_duel')]
    duel_won = [item for item in duels if item.get('won')]
    duel_rate = round((len(duel_won) / len(duels)) * 100, 1) if duels else 0.0
    success_actions = [event for event in events if result_is_success(event.result)]
    success_rate = round((len(success_actions) / total_actions) * 100, 1) if total_actions else 0.0
    avg_actions = round(total_actions / total_matches, 1) if total_matches else 0.0
    avg_duels = round(len(duels) / total_matches, 1) if total_matches else 0.0
    avg_yellows = round(yellows / total_matches, 2) if total_matches else 0.0
    season_played_matches = standing.played if standing and standing.played else total_matches
    goals_per_match = round((goals_for / season_played_matches), 2) if season_played_matches else 0.0
    goals_conceded_per_match = round((goals_against / season_played_matches), 2) if season_played_matches else 0.0
    card_total = yellows + reds
    cards_per_match = round((card_total / season_played_matches), 2) if season_played_matches else 0.0

    def _summarize_events(event_list):
        total = len(event_list)
        successes_local = sum(1 for event in event_list if result_is_success(event.result))
        duel_local_classifications = [
            classify_duel_event(event.event_type, event.result, event.observation, event.zone)
            for event in event_list
        ]
        duels_local = [item for item in duel_local_classifications if item.get('is_duel')]
        duels_won_local = [item for item in duels_local if item.get('won')]
        shots_attempts = 0
        shots_on_target = 0
        passes_attempts = 0
        passes_completed = 0
        yellow_local = 0
        red_local = 0
        zone_counts_local = {key: 0 for key in FIELD_ZONE_KEYS}
        for event in event_list:
            if is_yellow_card_event(event.event_type, event.result, event.zone):
                yellow_local += 1
            if is_red_card_event(event.event_type, event.result, event.zone):
                red_local += 1
            shot_event = contains_keyword(event.event_type, SHOT_KEYWORDS) or contains_keyword(event.observation, SHOT_KEYWORDS)
            save_event = is_goalkeeper_save_event(event.event_type, event.result, event.observation)
            if shot_event or save_event:
                shots_attempts += 1
                if save_event or result_is_success(event.result):
                    shots_on_target += 1
            if contains_keyword(event.event_type, PASS_KEYWORDS) or contains_keyword(event.observation, PASS_KEYWORDS):
                passes_attempts += 1
                if result_is_success(event.result):
                    passes_completed += 1
            zone_label = map_zone_label((event.zone or '').strip())
            if zone_label:
                zone_counts_local[zone_label] += 1
        return {
            'total_actions': total,
            'success_rate': round((successes_local / total) * 100, 1) if total else 0.0,
            'duels_total': len(duels_local),
            'duel_rate': round((len(duels_won_local) / len(duels_local)) * 100, 1) if duels_local else 0.0,
            'yellow_cards': yellow_local,
            'red_cards': red_local,
            'shots_attempts': shots_attempts,
            'shots_on_target': shots_on_target,
            'passes_attempts': passes_attempts,
            'passes_completed': passes_completed,
            'zone_counts': zone_counts_local,
            'field_zones': [
                {
                    **zone,
                    'count': zone_counts_local.get(zone['key'], 0),
                    'pct': round((zone_counts_local.get(zone['key'], 0) / total) * 100, 1) if total else 0,
                }
                for zone in FIELD_ZONES
            ],
        }

    # General overview based on player base stats (Universo/cache/manual) + actions dataset.
    player_cards = compute_player_cards(primary_team) if primary_team else []
    top_minutes_player = max(player_cards, key=lambda item: item.get('minutes', 0), default={})
    top_goals_player = max(player_cards, key=lambda item: item.get('goals', 0), default={})
    top_yellow_player = max(player_cards, key=lambda item: item.get('yellow_cards', 0), default={})

    duels_won_by_player = {}
    recoveries_by_player = {}
    for event in events:
        player = event.player
        if not player:
            continue
        duel_event = classify_duel_event(event.event_type, event.result, event.observation, event.zone)
        if duel_event.get('is_duel') and duel_event.get('won'):
            duels_won_by_player[player.id] = duels_won_by_player.get(player.id, 0) + 1
        event_text = ' '.join(
            [
                str(event.event_type or ''),
                str(event.result or ''),
                str(event.observation or ''),
            ]
        )
        if contains_keyword(event_text, ['robo', 'recuper', 'intercep']):
            recoveries_by_player[player.id] = recoveries_by_player.get(player.id, 0) + 1

    def _top_player_from_counter(counter_dict):
        if not counter_dict:
            return {}
        top_id, top_value = max(counter_dict.items(), key=lambda x: x[1])
        player_obj = Player.objects.filter(id=top_id).first()
        if not player_obj:
            return {}
        return {
            'name': player_obj.name,
            'value': top_value,
        }

    top_duels_player = _top_player_from_counter(duels_won_by_player)
    top_recovery_player = _top_player_from_counter(recoveries_by_player)

    active_injuries = 0
    total_injuries = 0
    if primary_team:
        injuries_qs = PlayerInjuryRecord.objects.filter(player__team=primary_team)
        active_injuries = injuries_qs.filter(is_active=True).count()
        total_injuries = injuries_qs.count()

    coach_general_stats = [
        {'label': 'Partidos jugados', 'value': season_played_matches},
        {'label': 'Goles totales', 'value': goals_for},
        {'label': 'Goles por partido', 'value': goals_per_match},
        {'label': 'GC por partido', 'value': goals_conceded_per_match},
        {'label': 'Tarjetas totales', 'value': card_total},
        {'label': 'Tarjetas por partido', 'value': cards_per_match},
        {'label': 'Lesiones activas', 'value': active_injuries},
        {'label': 'Lesiones totales', 'value': total_injuries},
    ]
    coach_player_leaders = [
        {
            'label': 'Más minutos',
            'name': top_minutes_player.get('name') or '-',
            'value': top_minutes_player.get('minutes', 0),
            'suffix': 'min',
        },
        {
            'label': 'Más goles',
            'name': top_goals_player.get('name') or '-',
            'value': top_goals_player.get('goals', 0),
            'suffix': 'g',
        },
        {
            'label': 'Más robos/recuperaciones',
            'name': top_recovery_player.get('name') or '-',
            'value': top_recovery_player.get('value', 0),
            'suffix': '',
        },
        {
            'label': 'Más duelos ganados',
            'name': top_duels_player.get('name') or '-',
            'value': top_duels_player.get('value', 0),
            'suffix': '',
        },
        {
            'label': 'Más amarillas',
            'name': top_yellow_player.get('name') or '-',
            'value': top_yellow_player.get('yellow_cards', 0),
            'suffix': '',
        },
    ]

    kpis = [
        {'label': 'Clasificación', 'value': rank or '-', 'pct': min(100, max(0, 100 - (rank * 4 if rank else 0))), 'suffix': ''},
        {'label': 'Puntos', 'value': points, 'pct': min(100, round((points / 75) * 100, 1) if points else 0), 'suffix': ''},
        {'label': 'Goles a favor', 'value': goals_for, 'pct': min(100, round((goals_for / 60) * 100, 1) if goals_for else 0), 'suffix': ''},
        {'label': 'Goles en contra', 'value': goals_against, 'pct': min(100, round((goals_against / 60) * 100, 1) if goals_against else 0), 'suffix': ''},
        {'label': 'Amarillas', 'value': yellows, 'pct': min(100, round((yellows / 75) * 100, 1) if yellows else 0), 'suffix': ''},
        {'label': 'Rojas', 'value': reds, 'pct': min(100, round((reds / 20) * 100, 1) if reds else 0), 'suffix': ''},
        {'label': 'Posesión*', 'value': f'{min(80, max(35, 45 + (success_rate / 4))):.1f}%', 'pct': min(100, max(0, min(80, max(35, 45 + (success_rate / 4))))), 'suffix': ''},
        {'label': 'Duelos', 'value': len(duels), 'pct': min(100, round((len(duels) / 240) * 100, 1) if duels else 0), 'suffix': ''},
        {'label': '% Acierto', 'value': f'{success_rate:.1f}%', 'pct': min(100, max(0, success_rate)), 'suffix': ''},
        {'label': 'Acciones totales', 'value': total_actions, 'pct': min(100, round((total_actions / 1200) * 100, 1) if total_actions else 0), 'suffix': ''},
        {'label': 'Acciones/partido', 'value': avg_actions, 'pct': min(100, round((avg_actions / 80) * 100, 1) if avg_actions else 0), 'suffix': ''},
        {'label': 'Duelos/partido', 'value': avg_duels, 'pct': min(100, round((avg_duels / 20) * 100, 1) if avg_duels else 0), 'suffix': ''},
        {'label': 'Amarillas/partido', 'value': avg_yellows, 'pct': min(100, round((avg_yellows / 4) * 100, 1) if avg_yellows else 0), 'suffix': ''},
        {'label': '% Duelo ganado', 'value': f'{duel_rate:.1f}%', 'pct': min(100, max(0, duel_rate)), 'suffix': ''},
    ]

    team_events = list(events.select_related('match', 'match__home_team', 'match__away_team').order_by('match__date', 'id'))
    totals_breakdown = _summarize_events(team_events)
    coach_total_field_zones = totals_breakdown['field_zones']
    coach_total_actions_count = totals_breakdown['total_actions']
    match_events_map = defaultdict(list)
    for event in team_events:
        if event.match_id:
            match_events_map[event.match_id].append(event)
    team_matches = list(_team_match_queryset(primary_team).select_related('home_team', 'away_team').order_by('-date', '-id'))
    coach_match_rows = []
    for match in team_matches:
        match_events = match_events_map.get(match.id, [])
        metrics = _summarize_events(match_events)
        if match.home_team == primary_team:
            opponent_name = match.away_team.name if match.away_team else 'Rival desconocido'
        else:
            opponent_name = match.home_team.name if match.home_team else 'Rival desconocido'
        coach_match_rows.append(
            {
                'match_id': match.id,
                'round': match.round or f'Partido {match.id}',
                'date': match.date.strftime('%d/%m/%Y') if match.date else '--/--/----',
                'opponent': opponent_name,
                'location': match.location or 'Campo por confirmar',
                'total_actions': metrics['total_actions'],
                'success_rate': metrics['success_rate'],
                'duel_rate': metrics['duel_rate'],
                'yellow_cards': metrics['yellow_cards'],
                'red_cards': metrics['red_cards'],
            }
        )

    selected_match_id = _parse_int(request.GET.get('match'))
    valid_match_ids = {row['match_id'] for row in coach_match_rows}
    if selected_match_id not in valid_match_ids:
        selected_match_id = coach_match_rows[0]['match_id'] if coach_match_rows else None
    selected_match_row = next((row for row in coach_match_rows if row['match_id'] == selected_match_id), None)
    selected_match_metrics = _summarize_events(match_events_map.get(selected_match_id, [])) if selected_match_id else None

    modules = [
        {'title': 'Convocatoria', 'description': 'Define lista oficial y PDF del partido.', 'link': 'convocation'},
        {'title': '11 inicial', 'description': 'Pantalla táctica visual para construir la alineación titular y banquillo.', 'link': 'initial-eleven'},
        {'title': 'Sesiones', 'description': 'Planificador semanal de sesiones y tareas.', 'link': 'sessions'},
        {'title': 'Multas', 'description': 'Control disciplinario del vestuario.', 'link': 'fines'},
    ]
    return render(
        request,
        'football/coach_role_hub.html',
        {
            'role_title': 'Entrenador',
            'role_description': 'Área operativa principal del staff técnico.',
            'modules': modules,
            'kpis': kpis,
            'kpi_note': '* Posesión estimada sobre registros de acciones.',
            'coach_general_stats': coach_general_stats,
            'coach_player_leaders': coach_player_leaders,
            'coach_total_field_zones': coach_total_field_zones,
            'coach_total_actions_count': coach_total_actions_count,
            'coach_match_rows': coach_match_rows,
            'coach_selected_match': selected_match_row,
            'coach_selected_match_metrics': selected_match_metrics,
        },
    )


def coach_role_goalkeeper_page(request):
    modules = [
        {
            'title': 'Tareas portero · Carga PDF',
            'description': 'Sube, analiza y crea tareas especificas de porteria.',
            'link': 'sessions-goalkeeper',
        },
        {'title': 'Pizarra táctica', 'description': 'Simula secuencias de portero en campo y guarda movimientos.', 'link': 'coach-abp-board'},
    ]
    return render(
        request,
        'football/coach_role_hub.html',
        {
            'role_title': 'Preparador de porteros',
            'role_description': 'Repositorio técnico especializado para trabajo específico de portería.',
            'modules': modules,
        },
    )


def coach_role_fitness_page(request):
    modules = [
        {
            'title': 'Tareas fisicas · Carga PDF',
            'description': 'Sube, analiza y crea tareas de preparacion fisica.',
            'link': 'sessions-fitness',
        },
        {'title': 'Métricas físicas', 'description': 'Sección lista para cargar datos, test y seguimiento.', 'link': 'player-dashboard'},
        {'title': 'Registro individual', 'description': 'Completa datos físicos por jugador desde su ficha.', 'link': 'player-dashboard'},
    ]
    return render(
        request,
        'football/coach_role_hub.html',
        {
            'role_title': 'Preparación física',
            'role_description': 'Base preparada para incorporar carga interna/externa y control físico.',
            'modules': modules,
        },
    )


def coach_role_abp_page(request):
    modules = [
        {'title': 'Repositorio ABP', 'description': 'Guarda tareas y sesiones ABP en el planificador.', 'link': 'sessions'},
        {'title': 'Pizarra ABP', 'description': 'Campo interactivo con fichas, grabación y reproducción de jugadas.', 'link': 'coach-abp-board'},
    ]
    return render(
        request,
        'football/coach_role_hub.html',
        {
            'role_title': 'ABP',
            'role_description': 'Acciones a balón parado: diseño, simulación y biblioteca de jugadas.',
            'modules': modules,
        },
    )


def coach_abp_board_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    players = []
    if primary_team:
        players = list(
            Player.objects.filter(team=primary_team, is_active=True).order_by('number', 'name')[:28]
        )
    return render(
        request,
        'football/coach_abp_board.html',
        {
            'players': players,
            'team_name': primary_team.name if primary_team else 'Equipo principal',
        },
    )


def coach_roster_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')

    message = ''
    error = ''
    if request.method == 'POST':
        action = (request.POST.get('action') or 'add').strip()
        player_id = _parse_int(request.POST.get('player_id'))
        name = (request.POST.get('name') or '').strip()
        number_raw = (request.POST.get('number') or '').strip()
        position = (request.POST.get('position') or '').strip()
        is_active = (request.POST.get('is_active') or '1').strip() in {'1', 'true', 'on', 'yes'}

        try:
            if action == 'deactivate':
                if not player_id:
                    raise ValueError('Jugador no válido para desactivar.')
                player = Player.objects.filter(id=player_id, team=primary_team).first()
                if not player:
                    raise ValueError('Jugador no encontrado.')
                player.is_active = False
                player.save(update_fields=['is_active'])
                message = f'{player.name} marcado como inactivo.'
            else:
                if not name:
                    raise ValueError('El nombre es obligatorio.')
                number = _parse_int(number_raw) if number_raw else None
                player = (
                    Player.objects.filter(team=primary_team, name__iexact=name)
                    .order_by('id')
                    .first()
                )
                if player:
                    player.number = number
                    player.position = position
                    player.is_active = is_active
                    player.save(update_fields=['number', 'position', 'is_active'])
                    message = f'Jugador actualizado: {player.name}.'
                else:
                    Player.objects.create(
                        team=primary_team,
                        name=name,
                        number=number,
                        position=position,
                        is_active=is_active,
                    )
                    message = f'Jugador añadido: {name}.'
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = 'No se pudo guardar el jugador. Revisa los datos.'

    players = Player.objects.filter(team=primary_team).order_by('is_active', 'number', 'name')
    return render(
        request,
        'football/coach_roster.html',
        {
            'team_name': primary_team.name,
            'players': players,
            'message': message,
            'error': error,
        },
    )


def initial_eleven_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    convocation_record = get_current_convocation_record(
        primary_team,
        match=get_active_match(primary_team),
        fallback_to_latest=True,
    )
    convocation_players = list(convocation_record.players.order_by('number', 'name')) if convocation_record else []
    for player in convocation_players:
        player.photo_url = resolve_player_photo_url(request, player)

    lineup_seed = {'starters': [], 'bench': []}
    if convocation_record:
        stored = convocation_record.lineup_data if isinstance(convocation_record.lineup_data, dict) else {}
        normalized = _normalize_lineup_payload(stored, convocation_players)
        if normalized['starters'] or normalized['bench']:
            lineup_seed = normalized
        else:
            lineup_seed = _build_default_lineup_payload(convocation_players)
            convocation_record.lineup_data = lineup_seed
            convocation_record.save(update_fields=['lineup_data'])

    return render(
        request,
        'football/coach_initial_eleven.html',
        {
            'team_name': primary_team.name,
            'convocation_record': convocation_record,
            'convocation_players': convocation_players,
            'lineup_seed_json': json.dumps(lineup_seed, ensure_ascii=False),
        },
    )


def _extract_pdf_text(pdf_file, max_chars=12000):
    if PdfReader is None:
        raise ValueError('Falta dependencia de lectura PDF. Instala `pypdf`.')

    def _ocr_text_from_image_bytes(raw_bytes):
        if not raw_bytes or Image is None or pytesseract is None:
            return ''
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                rgb = img.convert('RGB')
                # OCR bilingual by default to improve mixed ES/EN task sheets.
                return (pytesseract.image_to_string(rgb, lang='spa+eng') or '').strip()
        except Exception:
            return ''

    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        chunks = []
        for page in reader.pages:
            chunks.append((page.extract_text() or '').strip())
        text = '\n'.join([item for item in chunks if item]).strip()
        text = re.sub(r'\n{3,}', '\n\n', text)
        if len(text) < 180:
            ocr_chunks = []
            for page in reader.pages[:5]:
                images = getattr(page, 'images', []) or []
                for image in images[:3]:
                    image_bytes = getattr(image, 'data', b'') or b''
                    ocr_text = _ocr_text_from_image_bytes(image_bytes)
                    if ocr_text:
                        ocr_chunks.append(ocr_text)
                if sum(len(c) for c in ocr_chunks) >= 5000:
                    break
            if ocr_chunks:
                text = '\n'.join([text, '\n'.join(ocr_chunks)]).strip() if text else '\n'.join(ocr_chunks)
                text = re.sub(r'\n{3,}', '\n\n', text)
        text = _repair_joined_words_text(text)
        return text[:max_chars]
    except Exception:
        raise ValueError('No se pudo leer el PDF. Verifica que no esté protegido o corrupto.')


def _analyze_preview_image_bytes(raw_bytes):
    if Image is None or not raw_bytes:
        return None
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb = img.convert('RGB')
            width, height = rgb.size
            if width <= 0 or height <= 0:
                return None
            sample = rgb.copy()
            sample.thumbnail((128, 128))
            pixels = list(sample.getdata())
            total = max(1, len(pixels))
            greenish = 0
            whitish = 0
            darkish = 0
            colorful = 0
            for r, g, b in pixels:
                if g > 70 and g > (r + 14) and g > (b + 10):
                    greenish += 1
                if r > 232 and g > 232 and b > 232:
                    whitish += 1
                if r < 30 and g < 30 and b < 30:
                    darkish += 1
                if (max(r, g, b) - min(r, g, b)) >= 24:
                    colorful += 1
            green_ratio = greenish / total
            white_ratio = whitish / total
            dark_ratio = darkish / total
            color_ratio = colorful / total
            area = width * height
            aspect = width / max(1.0, float(height))

            score = 0.0
            score += min(area / float(1280 * 720), 2.6) * 28.0
            score += green_ratio * 46.0
            score += color_ratio * 16.0
            if 0.95 <= aspect <= 2.35:
                score += 8.0
            if 1.15 <= aspect <= 2.05:
                score += 6.0
            score -= white_ratio * 44.0
            if min(width, height) < 210:
                score -= 26.0
            if white_ratio > 0.78 and green_ratio < 0.06:
                score -= 48.0
            if dark_ratio > 0.88:
                score -= 20.0

            return {
                'width': int(width),
                'height': int(height),
                'area': int(area),
                'aspect': float(aspect),
                'green_ratio': float(green_ratio),
                'white_ratio': float(white_ratio),
                'dark_ratio': float(dark_ratio),
                'score': float(score),
            }
    except Exception:
        return None


def _is_preview_quality_low(raw_bytes):
    metrics = _analyze_preview_image_bytes(raw_bytes)
    if not metrics:
        return False
    score = float(metrics.get('score') or 0.0)
    area = int(metrics.get('area') or 0)
    white_ratio = float(metrics.get('white_ratio') or 0.0)
    green_ratio = float(metrics.get('green_ratio') or 0.0)
    # Typical bad previews: tiny crops, white text snippets, or non-graphic chunks.
    if area < 260 * 170:
        return True
    if score < 10.0:
        return True
    if white_ratio > 0.72 and green_ratio < 0.08:
        return True
    return False


def _extract_preview_images_from_pdf(pdf_file, max_images=8, prefer_render=False):
    if PdfReader is None or pdf_file is None:
        return []
    if prefer_render:
        rendered_payload = _render_pdf_preview_with_pdftoppm(pdf_file)
        if rendered_payload:
            return [rendered_payload]
    payloads = []
    candidates = []
    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        seq = 0
        for page_idx, page in enumerate(reader.pages):
            images = getattr(page, 'images', []) or []
            for image in images:
                seq += 1
                raw = getattr(image, 'data', b'') or b''
                if not raw:
                    continue
                ext = str(getattr(image, 'name', 'img.bin') or 'img.bin').rsplit('.', 1)[-1].lower()
                if ext not in {'png', 'jpg', 'jpeg', 'webp'}:
                    ext = 'png'
                metrics = _analyze_preview_image_bytes(raw)
                score = float(metrics.get('score') or 0.0) if metrics else 0.0
                candidates.append(
                    {
                        'raw': raw,
                        'ext': ext,
                        'score': score,
                        'page_idx': page_idx,
                        'seq': seq,
                    }
                )
    except Exception:
        candidates = []
    if candidates:
        max_count = max(1, int(max_images or 1))
        good_candidates = [item for item in candidates if float(item.get('score') or 0.0) >= 12.0]
        if good_candidates:
            # Keep original document order for multi-task PDFs once quality threshold is met.
            selected = sorted(good_candidates, key=lambda item: (int(item.get('page_idx') or 0), int(item.get('seq') or 0)))
        else:
            # If every embedded image is poor, still try top-scored ones before falling back.
            selected = sorted(candidates, key=lambda item: float(item.get('score') or 0.0), reverse=True)
        for item in selected[:max_count]:
            ext = str(item.get('ext') or 'jpg')
            filename = f'task-preview-{uuid.uuid4().hex[:10]}.{ext}'
            payloads.append((filename, ContentFile(item.get('raw') or b'')))
        if payloads:
            return payloads
    if payloads:
        return payloads

    # Fallback: render first page when PDF uses vector drawings (no embedded images).
    fallback_payload = _render_pdf_preview_with_pdftoppm(pdf_file)
    if fallback_payload:
        return [fallback_payload]

    # Last fallback: generic field image so old tasks never stay without thumbnail.
    default_payload = _default_task_preview_payload()
    if default_payload:
        return [default_payload]
    return payloads


def _extract_preview_image_from_pdf(pdf_file, prefer_render=False):
    payloads = _extract_preview_images_from_pdf(pdf_file, max_images=1, prefer_render=prefer_render)
    return payloads[0] if payloads else None


def _render_pdf_preview_with_pdftoppm(pdf_file):
    if pdf_file is None:
        return None
    pdftoppm_bin = shutil.which('pdftoppm')
    if not pdftoppm_bin:
        return None
    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return None
        with tempfile.TemporaryDirectory(prefix='task-preview-') as tmpdir:
            tmp_path = Path(tmpdir)
            source_pdf = tmp_path / 'source.pdf'
            output_base = tmp_path / 'preview'
            source_pdf.write_bytes(pdf_bytes)
            subprocess.run(
                [
                    pdftoppm_bin,
                    '-jpeg',
                    '-f',
                    '1',
                    '-singlefile',
                    '-scale-to',
                    '1400',
                    str(source_pdf),
                    str(output_base),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
            output_jpg = tmp_path / 'preview.jpg'
            if not output_jpg.exists():
                return None
            raw = output_jpg.read_bytes()
            if not raw:
                return None
            if Image is not None:
                try:
                    with Image.open(io.BytesIO(raw)) as img:
                        optimized = img.convert('RGB')
                        optimized.thumbnail((1400, 1000))
                        buffer = io.BytesIO()
                        optimized.save(buffer, format='JPEG', quality=76, optimize=True)
                        raw = buffer.getvalue()
                except Exception:
                    pass
            filename = f'task-preview-{uuid.uuid4().hex[:10]}.jpg'
            return filename, ContentFile(raw)
    except Exception:
        return None


def _default_task_preview_payload():
    try:
        fallback_path = Path(settings.BASE_DIR) / 'static' / 'football' / 'campo-futbol.jpg'
        if not fallback_path.exists() or not fallback_path.is_file():
            return None
        raw = fallback_path.read_bytes()
        if Image is not None:
            try:
                with Image.open(io.BytesIO(raw)) as img:
                    normalized = img.convert('RGB')
                    normalized.thumbnail((1200, 850))
                    buffer = io.BytesIO()
                    normalized.save(buffer, format='JPEG', quality=74, optimize=True)
                    raw = buffer.getvalue()
            except Exception:
                pass
        filename = f'task-preview-{uuid.uuid4().hex[:10]}.jpg'
        return filename, ContentFile(raw)
    except Exception:
        return None


def _ensure_task_preview_image(task, prefer_render=False):
    if not task or not getattr(task, 'task_pdf', None):
        return False
    preview_payload = _extract_preview_image_from_pdf(task.task_pdf, prefer_render=prefer_render)
    if not preview_payload:
        return False
    preview_name, preview_content = preview_payload
    try:
        task.task_preview_image.save(preview_name, preview_content, save=True)
        return bool(task.task_preview_image)
    except Exception:
        return False


def _task_preview_needs_refresh(task):
    if not task:
        return False
    preview_name = str(getattr(task, 'task_preview_image', '') or '').strip()
    if not preview_name:
        return True
    try:
        if not default_storage.exists(preview_name):
            return True
    except Exception:
        return True
    cache_key = f'football:preview-quality:{preview_name}'
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached)
    try:
        with default_storage.open(preview_name, 'rb') as handle:
            raw = handle.read()
        needs_refresh = _is_preview_quality_low(raw)
    except Exception:
        needs_refresh = True
    cache.set(cache_key, bool(needs_refresh), 60 * 60 * 6)
    return bool(needs_refresh)


def _ensure_library_task_preview(task, force=False, prefer_render=False):
    if not task:
        return False
    current_name = str(getattr(task, 'task_preview_image', '') or '').strip()
    if current_name and not force:
        try:
            if default_storage.exists(current_name):
                return True
        except Exception:
            pass
    if getattr(task, 'task_pdf', None):
        if _ensure_task_preview_image(task, prefer_render=prefer_render):
            return True
    fallback = _default_task_preview_payload()
    if not fallback:
        return False
    fallback_name, fallback_content = fallback
    try:
        task.task_preview_image.save(fallback_name, fallback_content, save=True)
        return bool(task.task_preview_image)
    except Exception:
        return False


TASK_CONTEXT_KEYWORDS = {
    'presion_alta': ['presion alta', 'presión alta', 'repliegue tras perdida', 'robo alto'],
    'salida_balon': ['salida de balon', 'salida de balón', 'inicio juego', 'construccion'],
    'finalizacion': ['finalizacion', 'finalización', 'remate', 'tiro', 'gol'],
    'transicion_ofensiva': ['transicion ofensiva', 'transición ofensiva', 'contraataque'],
    'transicion_defensiva': ['transicion defensiva', 'transición defensiva', 'balance defensivo'],
    'abp': ['abp', 'balon parado', 'balón parado', 'corner', 'falta lateral'],
    'porteros': ['portero', 'porteria', 'porteria', 'blocaje', 'despeje'],
    'fisico': ['fuerza', 'resistencia', 'velocidad', 'aceleracion', 'aceleración', 'potencia'],
}

TASK_OBJECTIVE_KEYWORDS = {
    'perfil_corporal': ['perfil corporal', 'orientacion corporal', 'orientación corporal'],
    'tercer_hombre': ['tercer hombre', 'hombre libre'],
    'amplitud': ['amplitud', 'carril exterior', 'lado debil', 'lado débil'],
    'temporizacion': ['temporizacion', 'temporización', 'esperar salto'],
    'duelo': ['duelo', '1v1', '1x1'],
    'coordinacion': ['coordinacion', 'coordinación', 'sincronizacion', 'sincronización'],
}

TASK_TYPE_KEYWORDS = {
    'rondo': ['rondo'],
    'posesion': ['posesion', 'posesión', 'conservacion', 'conservación'],
    'juego_posicional': ['juego de posicion', 'juego de posición', 'posicional'],
    'transicion': ['transicion', 'transición', 'contraataque', 'ataque rapido', 'ataque rápido'],
    'finalizacion': ['finalizacion', 'finalización', 'remate', 'tiro', 'gol'],
    'circuito': ['circuito', 'estacion', 'estación', 'posta'],
    'abp': ['abp', 'balon parado', 'balón parado', 'corner', 'falta lateral', 'saque de esquina'],
    'partido_reducido': ['partido reducido', 'ssg', 'small sided', 'juego reducido'],
}

TASK_PHASE_KEYWORDS = {
    'ataque': ['ataque', 'ofensiva', 'ofensivo', 'con balon', 'con balón'],
    'defensa': ['defensa', 'defensiva', 'defensivo', 'sin balon', 'sin balón'],
    'transicion': ['transicion', 'transición', 'tras perdida', 'tras pérdida', 'tras robo'],
    'mixta': ['ida y vuelta', 'ataque y defensa', 'mixto'],
}

TASK_JOINED_WORD_VOCAB = [
    'TAREA', 'EJERCICIO', 'SESION', 'BLOQUE', 'PARTE', 'PRINCIPAL',
    'DESCRIPCION', 'OBJETIVO', 'CONSIGNAS', 'REGLAS', 'DOSIFICACION',
    'TIEMPO', 'TOTAL', 'TRABAJO', 'PAUSA', 'SERIE', 'SERIES', 'REPETICIONES',
    'JUGADORES', 'COMODIN', 'COMODINES', 'MATERIAL', 'MATERIALES',
    'PORTERIA', 'PORTERIAS', 'PORTERO', 'PORTEROS', 'PORTERIA', 'MOVIL',
    'BALON', 'CONO', 'ARCO', 'PRECISION', 'FINALIZACION', 'DUEL', 'DUELO', 'DUELOS',
    'AEREOS', 'AEREO', 'TRANSICION', 'DEFENSA', 'ATAQUE', 'OFENSIVA', 'DEFENSIVA',
    'CAMPO', 'MEDIO', 'ZONA', 'ESPACIO', 'MEDIDAS', 'FRENTE', 'ORIENTADOS',
    'TRABAJAMOS', 'TRABAJAR', 'GENERA', 'GENERAMOS', 'HACEMOS', 'HACEMOSUN',
    'DONDE', 'CUANDO', 'CON', 'SIN', 'PARA', 'POR', 'DEL', 'AL',
    'LA', 'EL', 'LOS', 'LAS', 'UN', 'UNA', 'UNO', 'Y', 'DE', 'EN',
    'VERDE', 'ROJO', 'SALIR', 'SALE', 'SE', 'QUE', 'YA', 'VEZ',
    'MAS', 'CAIDA', 'DESPEJE', 'ORIENTADO', 'INFERIORIDAD', 'SUPERIORIDAD',
    'REACCION', 'PRESION', 'RECUPERACION', 'PASE', 'APOYO',
]


def _normalize_folded_text(value):
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_upper_compact(value):
    raw = str(value or '').strip().upper()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    stripped = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z]+', '', stripped)


JOINED_WORD_MAP = {
    _normalize_upper_compact(word): str(word).upper()
    for word in TASK_JOINED_WORD_VOCAB
    if _normalize_upper_compact(word)
}


def _split_joined_upper_token(token):
    compact = _normalize_upper_compact(token)
    if len(compact) < 10:
        return token
    n = len(compact)
    best = [None] * (n + 1)
    best[0] = (0, [])
    max_len = min(18, n)
    for i in range(n):
        if best[i] is None:
            continue
        base_score, base_words = best[i]
        for step in range(1, max_len + 1):
            j = i + step
            if j > n:
                break
            chunk = compact[i:j]
            mapped = JOINED_WORD_MAP.get(chunk)
            if not mapped:
                continue
            bonus = (step * step) + (4 if step >= 4 else 0)
            candidate = (base_score + bonus, base_words + [mapped])
            if best[j] is None or candidate[0] > best[j][0]:
                best[j] = candidate
    if best[n] is None:
        return token
    words = best[n][1]
    if len(words) < 2:
        return token
    joined = ' '.join(words).strip()
    # Keep guardrails: avoid over-splitting into too many tiny pieces.
    if len(words) >= 7 and (len(compact) / max(1, len(words))) < 2.2:
        return token
    return joined or token


def _repair_joined_words_text(value):
    text = str(value or '')
    if not text:
        return ''
    cleaned = text.replace('\r\n', '\n').replace('\r', '\n')
    cleaned = re.sub(r'(?<=\d)(?=[A-Za-zÁÉÍÓÚÜÑ])', ' ', cleaned)
    cleaned = re.sub(r'(?<=[A-Za-zÁÉÍÓÚÜÑ])(?=\d)', ' ', cleaned)
    cleaned = re.sub(r'([,:;])(?=\S)', r'\1 ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r' *\n *', '\n', cleaned)

    def _replace_token(match):
        token = match.group(0)
        return _split_joined_upper_token(token)

    cleaned = re.sub(r'\b[A-ZÁÉÍÓÚÜÑ]{10,}\b', _replace_token, cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r' *\n *', '\n', cleaned)
    return cleaned.strip()


def _detect_keyword_tags(text, taxonomy):
    haystack = _normalize_folded_text(text)
    tags = []
    for tag, keys in (taxonomy or {}).items():
        for key in keys:
            if _normalize_folded_text(key) in haystack:
                tags.append(tag)
                break
    return tags


def _detect_materials_in_text(text):
    haystack = _normalize_folded_text(text)
    detected = []
    for item in TASK_MATERIAL_LIBRARY:
        label = _normalize_folded_text(item.get('label'))
        title = _normalize_folded_text(item.get('title'))
        kind = _normalize_folded_text(item.get('kind'))
        if any(token and token in haystack for token in {label, title, kind}):
            detected.append(
                {
                    'label': item.get('label') or '',
                    'title': item.get('title') or '',
                    'kind': item.get('kind') or '',
                    'category': item.get('category') or '',
                }
            )
    return detected


def _analysis_quality_score(analysis):
    if not isinstance(analysis, dict):
        return 0
    score = 0
    if analysis.get('title'):
        score += 20
    if analysis.get('objective'):
        score += 20
    if analysis.get('coaching_points'):
        score += 20
    if analysis.get('confrontation_rules'):
        score += 20
    if analysis.get('work_contexts'):
        score += 10
    if analysis.get('objective_tags'):
        score += 5
    if analysis.get('detected_materials'):
        score += 5
    if analysis.get('exercise_types'):
        score += 5
    if analysis.get('phase_tags'):
        score += 5
    task_sheet = analysis.get('task_sheet') if isinstance(analysis.get('task_sheet'), dict) else {}
    if task_sheet.get('description'):
        score += 5
    if task_sheet.get('players') or task_sheet.get('dimensions') or task_sheet.get('materials'):
        score += 5
    return min(100, score)


def _apply_analysis_to_task(task, analysis):
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta['analysis'] = {
        'work_contexts': analysis.get('work_contexts') or [],
        'objective_tags': analysis.get('objective_tags') or [],
        'detected_materials': analysis.get('detected_materials') or [],
        'exercise_types': analysis.get('exercise_types') or [],
        'phase_tags': analysis.get('phase_tags') or [],
        'players_count_estimate': analysis.get('players_count_estimate') or None,
        'players_band': analysis.get('players_band') or '',
        'duration_band': analysis.get('duration_band') or '',
        'quality_score': analysis.get('quality_score') or 0,
        'summary': (analysis.get('summary') or '')[:900],
        'task_sheet': analysis.get('task_sheet') if isinstance(analysis.get('task_sheet'), dict) else {},
        'analyzed_at': timezone.now().isoformat(),
    }
    layout['meta'] = meta
    task.tactical_layout = layout
    task.save(update_fields=['tactical_layout'])


def _extract_section_block(text, section_aliases):
    lines = [ln.strip() for ln in str(text or '').splitlines()]
    if not lines:
        return ''
    aliases = [a.lower() for a in section_aliases]
    start = None
    for idx, line in enumerate(lines):
        low = line.lower()
        if any(re.search(rf'^{re.escape(alias)}\s*[:\-]?\s*$', low) for alias in aliases):
            start = idx + 1
            break
        if any(low.startswith(f'{alias}:') or low.startswith(f'{alias} -') for alias in aliases):
            inline = re.split(r'[:\-]', line, maxsplit=1)
            if len(inline) == 2 and inline[1].strip():
                return inline[1].strip()
    if start is None:
        return ''

    end = len(lines)
    for idx in range(start, len(lines)):
        low = lines[idx].lower()
        if re.match(r'^[a-záéíóúüñ ]{3,30}\s*[:\-]?\s*$', low):
            if idx > start:
                end = idx
                break
    return '\n'.join([ln for ln in lines[start:end] if ln]).strip()


def _pick_bullets_or_sentences(raw_text, limit=5):
    lines = [ln.strip() for ln in str(raw_text or '').splitlines() if ln.strip()]
    items = []
    for line in lines:
        clean = re.sub(r'^[\-\•\*\d\)\.\s]+', '', line).strip()
        if not clean:
            continue
        if len(clean) < 4:
            continue
        items.append(clean)
        if len(items) >= limit:
            break
    return '\n'.join(items)


def _extract_inline_field(text, aliases, max_len=240):
    raw = str(text or '')
    if not raw:
        return ''
    alias_pattern = '|'.join(re.escape(alias) for alias in aliases)
    patterns = [
        rf'(?im)^\s*(?:{alias_pattern})\s*[:\-]\s*(.+?)\s*$',
        rf'(?i)\b(?:{alias_pattern})\s*[:\-]\s*([^\n\r]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            value = ' '.join(str(match.group(1) or '').split()).strip(' ,.;:-')
            if value:
                return value[:max_len]
    return ''


def _extract_first_dimension_text(text):
    raw = str(text or '')
    if not raw:
        return ''
    match = re.search(
        r'(?i)\b(\d{1,3}(?:[.,]\d{1,2})?\s*(?:m|metros?)?)\s*[xX×]\s*(\d{1,3}(?:[.,]\d{1,2})?\s*(?:m|metros?)?)\b',
        raw,
    )
    if not match:
        return ''
    left = str(match.group(1) or '').strip()
    right = str(match.group(2) or '').strip()
    return f'{left} x {right}'


def _extract_players_text(text):
    raw = str(text or '')
    if not raw:
        return ''
    explicit = _extract_inline_field(
        raw,
        ['jugadores', 'participantes', 'n jugadores', 'num jugadores', 'nº jugadores', 'numero jugadores'],
        max_len=120,
    )
    if explicit:
        return explicit
    pattern = re.search(r'(?i)\b(\d{1,2}\s*v\s*\d{1,2}(?:\s*\+\s*\d{1,2})?)\b', raw)
    if pattern:
        return str(pattern.group(1)).replace(' ', '')
    total = re.search(r'(?i)\b(\d{1,2})\s*(?:jugadores?|participantes?)\b', raw)
    if total:
        return f'{total.group(1)} jugadores'
    return ''


def _estimate_players_count(players_text, fallback_text=''):
    source = ' '.join([str(players_text or ''), str(fallback_text or '')]).strip()
    if not source:
        return None
    cleaned = source.replace('vs', 'v').replace('x', 'v')
    total = 0
    matched = False
    for group in re.findall(r'(\d{1,2}\s*v\s*\d{1,2}(?:\s*\+\s*\d{1,2})?)', cleaned, flags=re.IGNORECASE):
        nums = [_parse_int(n) for n in re.findall(r'\d{1,2}', group)]
        nums = [n for n in nums if n is not None]
        if nums:
            total += sum(nums)
            matched = True
    if matched and total > 0:
        return total
    explicit_total = re.search(r'(?i)\b(\d{1,2})\s*(?:jugadores?|participantes?)\b', cleaned)
    if explicit_total:
        parsed = _parse_int(explicit_total.group(1))
        if parsed:
            return parsed
    nums = [_parse_int(n) for n in re.findall(r'\b\d{1,2}\b', cleaned)]
    nums = [n for n in nums if n is not None]
    plausible = [n for n in nums if 4 <= n <= 30]
    if plausible:
        return max(plausible)
    return None


def _players_band_label(players_count):
    value = _parse_int(players_count)
    if not value:
        return ''
    if value <= 6:
        return 'micro (1-6)'
    if value <= 12:
        return 'grupo (7-12)'
    if value <= 18:
        return 'equipo (13-18)'
    return 'ampliado (19+)'


def _duration_band_label(minutes):
    value = _parse_int(minutes)
    if not value:
        return ''
    if value <= 12:
        return 'corta (5-12m)'
    if value <= 20:
        return 'media (13-20m)'
    if value <= 35:
        return 'larga (21-35m)'
    return 'extendida (36m+)'


def _extract_task_sheet_from_pdf(text, detected_materials=None):
    description = _extract_section_block(
        text,
        ['descripcion', 'descripción', 'desarrollo', 'organizacion', 'organización', 'estructura', 'dinamica', 'dinámica'],
    )
    if not description:
        description = _pick_bullets_or_sentences(text, limit=6)

    players = _extract_players_text(text)
    space = _extract_inline_field(text, ['espacio', 'superficie', 'zona', 'campo', 'area', 'área'], max_len=120)
    dimensions = _extract_inline_field(text, ['medidas', 'dimensiones', 'tamano', 'tamaño'], max_len=120)
    if not dimensions:
        dimensions = _extract_first_dimension_text(text)

    material_section = _extract_section_block(text, ['material', 'materiales', 'elementos', 'recursos'])
    material_detected = []
    for item in detected_materials or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get('title') or item.get('label') or item.get('kind') or '').strip()
        if label:
            material_detected.append(label)
    if material_section:
        materials = material_section
    else:
        materials = ', '.join(sorted(set(material_detected)))[:300]

    return {
        'description': _repair_joined_words_text((description or '')[:1400])[:1200],
        'players': _repair_joined_words_text(players),
        'space': _repair_joined_words_text(space),
        'dimensions': _repair_joined_words_text(dimensions),
        'materials': _repair_joined_words_text(materials),
    }


def _suggest_task_from_pdf(pdf_text):
    text = _repair_joined_words_text(pdf_text or '')
    text = str(text or '').strip()
    if not text:
        return {
            'title': '',
            'objective': '',
            'minutes': 15,
            'coaching_points': '',
            'confrontation_rules': '',
            'summary': '',
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ''
    skip_title_tokens = (
        'parteprincipal',
        'materialdeentrenamiento',
        'tiempototaldesesion',
        'tiempo total de sesion',
        'fecha:',
        'hora:',
        'micro-ciclo',
        'meso-ciclo',
    )
    for line in lines[:24]:
        if len(line) > 120 or re.search(r'^\d+$', line):
            continue
        folded = _normalize_folded_text(line)
        if not folded or folded in {',', '.', ';'}:
            continue
        if any(token in folded for token in skip_title_tokens):
            continue
        if (
            folded.startswith('2bloques')
            or folded.startswith('3bloques')
            or folded.startswith('tiempototal')
            or re.match(r'^tiempo\s*total', folded)
        ):
            continue
        title = line
        break

    objective = _extract_section_block(text, ['objetivo', 'objective', 'finalidad', 'meta'])
    if not objective:
        objective_match = re.search(r'(objetivo|objective)\s*[:\-]\s*(.+)', text, re.IGNORECASE)
        if objective_match:
            objective = objective_match.group(2).strip()
        elif len(lines) > 1:
            for candidate in lines[1:10]:
                folded = _normalize_folded_text(candidate)
                if len(candidate.strip(' ,.;:-')) < 4:
                    continue
                if re.match(r'^(dosificacion|tiempo\s*total|parteprincipal)\b', folded):
                    continue
                if re.match(r'^\d+\s*bloques', folded):
                    continue
                objective = candidate[:180]
                break

    minutes = 15
    dosage_line = re.search(r'dosificaci[oó]n\s*[:\-]?\s*([^\n]{0,120})', text, re.IGNORECASE)
    if dosage_line:
        nums = [_parse_int(num) for num in re.findall(r'\d{1,3}', dosage_line.group(1))]
        nums = [n for n in nums if n is not None]
        plausible = [n for n in nums if 5 <= n <= 90]
        if plausible:
            minutes = max(plausible)
    if minutes == 15:
        minute_match = re.search(
            r'tiempo\s*total\s*[:\-]?\s*(\d{1,3})\s*(?:min|mins|minutos|minutes|[\'’`´])?',
            text,
            re.IGNORECASE,
        )
        if not minute_match:
            minute_match = re.search(r'(\d{1,3})\s*(?:min|mins|minutos|minutes|[\'’`´])', text, re.IGNORECASE)
        if minute_match:
            parsed = _parse_int(minute_match.group(1)) or 15
            minutes = max(5, min(parsed, 90))

    coaching_points = _extract_section_block(
        text,
        ['consignas', 'coaching points', 'puntos clave', 'indicaciones', 'correcciones'],
    )
    confrontation_rules = _extract_section_block(
        text,
        ['reglas', 'reglas de confrontacion', 'puntuacion', 'normas', 'restricciones'],
    )
    if not coaching_points or not confrontation_rules:
        bullet_like = []
        for line in lines:
            if line.startswith(('-', '•', '*')) or re.match(r'^\d+[\).\s-]', line):
                bullet_like.append(re.sub(r'^[\-\•\*\d\)\.\s]+', '', line).strip())
            if len(bullet_like) >= 10:
                break
        if not coaching_points:
            coaching_points = '\n'.join(bullet_like[:5])
        if not confrontation_rules:
            confrontation_rules = '\n'.join(bullet_like[5:10])
    if not coaching_points:
        coaching_points = _pick_bullets_or_sentences(text, limit=4)
    if not confrontation_rules:
        confrontation_rules = ''

    summary = '\n'.join(lines[:12])[:900]
    work_contexts = _detect_keyword_tags(text, TASK_CONTEXT_KEYWORDS)
    objective_tags = _detect_keyword_tags(' '.join([objective, coaching_points, confrontation_rules]), TASK_OBJECTIVE_KEYWORDS)
    exercise_types = _detect_keyword_tags(text, TASK_TYPE_KEYWORDS)
    phase_tags = _detect_keyword_tags(' '.join([text, objective, coaching_points]), TASK_PHASE_KEYWORDS)
    detected_materials = _detect_materials_in_text(text)
    task_sheet = _extract_task_sheet_from_pdf(text, detected_materials=detected_materials)
    players_count_estimate = _estimate_players_count(task_sheet.get('players'), text)
    players_band = _players_band_label(players_count_estimate)
    duration_band = _duration_band_label(minutes)

    analysis = {
        'title': _repair_joined_words_text((title or 'Tarea desde PDF')[:220])[:160],
        'objective': _repair_joined_words_text(objective[:240])[:180],
        'minutes': minutes,
        'coaching_points': _repair_joined_words_text(coaching_points),
        'confrontation_rules': _repair_joined_words_text(confrontation_rules),
        'summary': _repair_joined_words_text(summary),
        'work_contexts': work_contexts,
        'objective_tags': objective_tags,
        'exercise_types': exercise_types,
        'phase_tags': phase_tags,
        'players_count_estimate': players_count_estimate,
        'players_band': players_band,
        'duration_band': duration_band,
        'detected_materials': detected_materials,
        'task_sheet': task_sheet,
    }
    analysis['quality_score'] = _analysis_quality_score(analysis)
    return analysis


def _split_pdf_into_task_sections(pdf_text):
    text = str(pdf_text or '').strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 6:
        return [text]

    start_patterns = [
        re.compile(r'^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\b', re.IGNORECASE),
        re.compile(r'^\d{1,2}\s*[\)\.\-]\s*(?:tarea|ejercicio|task|drill)\b', re.IGNORECASE),
        re.compile(r'^(?:task|drill)\s*\d{1,2}\b', re.IGNORECASE),
        re.compile(r'^(?:primera|segunda|tercera|cuarta)\s+tarea\b', re.IGNORECASE),
    ]

    boundaries = []
    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in start_patterns):
            boundaries.append(idx)

    if len(boundaries) < 2:
        objective_indices = []
        for idx, line in enumerate(lines):
            if re.match(r'^(?:objetivo|objective)\s*[:\-]', line, re.IGNORECASE):
                objective_indices.append(max(0, idx - 1))
        boundaries = sorted(set(objective_indices))

    if len(boundaries) < 2:
        return [text]

    sections = []
    seen = set()
    stop_keywords = (
        'estiramientos',
        'partefinal',
        'parte final',
        'tiempototaldesesion',
        'tiempo total de sesion',
        'observaciones',
        'ausentes',
        'lesionados',
    )
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        if end - start < 3:
            continue
        chunk = '\n'.join(lines[start:end]).strip()
        folded = _normalize_folded_text(chunk)
        has_load_or_task_data = (
            'dosificacion' in folded
            or 'tiempototaldetrabajo' in folded
            or 'consignas' in folded
            or 'tarea' in folded
        )
        if any(word in folded for word in stop_keywords) and not has_load_or_task_data:
            continue
        normalized = _normalize_folded_text(chunk)
        if len(chunk) < 80 or normalized in seen:
            continue
        seen.add(normalized)
        sections.append(chunk)

    # Heuristic for session sheets where "Tarea 1" is implicit and first explicit marker is Tarea 2.
    if sections:
        first_folded = _normalize_folded_text(sections[0])
        looks_like_second = any(token in first_folded for token in ('tarea2', 'tarea 2', 'segunda tarea'))
        has_first_marker = any(any(token in _normalize_folded_text(sec) for token in ('tarea1', 'tarea 1', 'primera tarea')) for sec in sections)
        if looks_like_second and not has_first_marker:
            prefix_lines = lines[:boundaries[0]]
            prefix_text = '\n'.join(prefix_lines)
            prefix_folded = _normalize_folded_text(prefix_text)
            if 'parteprincipal' in prefix_folded:
                idx = prefix_folded.rfind('parteprincipal')
                candidate = prefix_text[idx:].strip()
            else:
                candidate = '\n'.join(prefix_lines[-28:]).strip()
            candidate_folded = _normalize_folded_text(candidate)
            if (
                len(candidate) >= 140
                and ('dosificacion' in candidate_folded or 'tiempototaldetrabajo' in candidate_folded)
                and 'estiramientos' not in candidate_folded
            ):
                sections.insert(0, candidate)

    cleaned_sections = []
    for chunk in sections:
        folded = _normalize_folded_text(chunk)
        if any(word in folded for word in stop_keywords):
            if not ('dosificacion' in folded or 'tiempototaldetrabajo' in folded):
                continue
        cleaned_sections.append(chunk)
    sections = cleaned_sections

    if len(sections) < 2:
        return [text]
    return sections[:8]


def _extract_tasks_from_pdf_text(pdf_text, fallback_title='Tarea desde PDF'):
    sections = _split_pdf_into_task_sections(pdf_text)
    analyses = []
    for idx, section in enumerate(sections, start=1):
        analysis = _suggest_task_from_pdf(section)
        title = (analysis.get('title') or '').strip()
        if not title or title.lower() == 'tarea desde pdf':
            if len(sections) > 1:
                title = f'{fallback_title} · Tarea {idx}'
            else:
                title = fallback_title
            analysis['title'] = title[:160]
        analyses.append(
            {
                'analysis': analysis,
                'raw_text': section[:2500],
                'segment_index': idx,
                'segment_total': len(sections),
            }
        )
    return analyses


def _parse_bulk_tasks_text(raw_text, default_block, default_minutes):
    """
    Parse bulk task rows from a plain-text block.
    Supported row formats (separator: |, ;, or TAB):
      titulo
      titulo|minutos
      titulo|minutos|bloque
      titulo|minutos|bloque|objetivo|consignas|reglas
    """
    lines = [ln.strip() for ln in str(raw_text or '').splitlines()]
    rows = [ln for ln in lines if ln and not ln.startswith('#')]
    parsed = []
    errors = []
    allowed_blocks = {choice[0] for choice in SessionTask.BLOCK_CHOICES}

    for idx, row in enumerate(rows, start=1):
        separator = '|'
        if '|' in row:
            separator = '|'
        elif ';' in row:
            separator = ';'
        elif '\t' in row:
            separator = '\t'
        parts = [part.strip() for part in row.split(separator)]
        parts = [part for part in parts if part != '']
        if not parts:
            continue

        title = (parts[0] or '').strip()
        if not title:
            errors.append(f'Línea {idx}: título vacío.')
            continue

        minutes = default_minutes
        block = default_block
        objective = ''
        coaching_points = ''
        confrontation_rules = ''

        if len(parts) >= 2:
            maybe_minutes = _parse_int(parts[1])
            if maybe_minutes is None:
                errors.append(f'Línea {idx}: minutos inválidos ({parts[1]}).')
                continue
            minutes = max(5, min(maybe_minutes, 90))
        if len(parts) >= 3:
            candidate_block = str(parts[2]).strip()
            if candidate_block in allowed_blocks:
                block = candidate_block
            else:
                errors.append(f'Línea {idx}: bloque inválido ({candidate_block}).')
                continue
        if len(parts) >= 4:
            objective = (parts[3] or '')[:180]
        if len(parts) >= 5:
            coaching_points = parts[4] or ''
        if len(parts) >= 6:
            confrontation_rules = parts[5] or ''

        parsed.append(
            {
                'title': title[:160],
                'minutes': minutes,
                'block': block,
                'objective': objective,
                'coaching_points': coaching_points,
                'confrontation_rules': confrontation_rules,
                'source_line': idx,
            }
        )
    return parsed, errors


def _persist_detected_resources_library(task_items, scope_key='coach'):
    try:
        counters = Counter()
        meta_by_key = {}
        for task in task_items or []:
            layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
            meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
            analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
            for mat in analysis_meta.get('detected_materials') or []:
                if not isinstance(mat, dict):
                    continue
                label = str(mat.get('label') or '').strip()
                title = str(mat.get('title') or '').strip()
                kind = str(mat.get('kind') or '').strip()
                category = str(mat.get('category') or '').strip()
                key = (kind or label or title or '').lower()
                if not key:
                    continue
                counters[key] += 1
                current = meta_by_key.get(key, {})
                if not current:
                    meta_by_key[key] = {
                        'label': label,
                        'title': title,
                        'kind': kind,
                        'category': category,
                    }
                else:
                    if title and len(title) > len(current.get('title') or ''):
                        current['title'] = title
                    if label and not current.get('label'):
                        current['label'] = label
                    if kind and not current.get('kind'):
                        current['kind'] = kind
                    if category and not current.get('category'):
                        current['category'] = category
                    meta_by_key[key] = current

        existing = {}
        if TASK_RESOURCE_LIBRARY_PATH.exists():
            try:
                existing = json.loads(TASK_RESOURCE_LIBRARY_PATH.read_text(encoding='utf-8'))
            except Exception:
                existing = {}
        if not isinstance(existing, dict):
            existing = {}
        resources_by_scope = existing.get('resources_by_scope')
        if not isinstance(resources_by_scope, dict):
            resources_by_scope = {}

        scope_items = []
        for key, count in counters.most_common():
            item_meta = meta_by_key.get(key, {})
            scope_items.append(
                {
                    'key': key,
                    'label': item_meta.get('label') or '',
                    'title': item_meta.get('title') or item_meta.get('label') or key,
                    'kind': item_meta.get('kind') or '',
                    'category': item_meta.get('category') or '',
                    'count': int(count),
                }
            )
        resources_by_scope[str(scope_key)] = scope_items
        payload = {
            'generated_at': timezone.now().isoformat(),
            'resources_by_scope': resources_by_scope,
        }
        TASK_RESOURCE_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        TASK_RESOURCE_LIBRARY_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    except Exception:
        # Never break the sessions workspace if library persistence fails.
        return


def _task_scope_for_item(task):
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    scope = str(meta.get('scope') or '').strip()
    return scope or 'coach'


def _get_or_create_library_session(team, scope_key):
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    scope_label = {
        'coach': 'Entrenador',
        'goalkeeper': 'Porteros',
        'fitness': 'Preparacion fisica',
    }.get(scope_key, 'Staff')
    microcycle, _ = TrainingMicrocycle.objects.get_or_create(
        team=team,
        week_start=week_start,
        defaults={
            'week_end': week_end,
            'title': f'Biblioteca {scope_label}',
            'objective': 'Repositorio de tareas en PDF',
            'status': TrainingMicrocycle.STATUS_DRAFT,
            'notes': 'Microciclo tecnico generado automaticamente para biblioteca.',
        },
    )
    session, _ = TrainingSession.objects.get_or_create(
        microcycle=microcycle,
        session_date=today,
        focus=f'Biblioteca PDF · {scope_label}',
        defaults={
            'duration_minutes': 90,
            'intensity': TrainingSession.INTENSITY_LOW,
            'content': 'Sesion tecnica para almacenar tareas subidas a biblioteca.',
            'order': 0,
        },
    )
    return session


def _cleanup_task_joined_text_fields(task):
    if not task:
        return False
    changed = False

    def _clean_attr(attr_name, max_len=None):
        nonlocal changed
        current = str(getattr(task, attr_name, '') or '')
        cleaned = _repair_joined_words_text(current)
        if max_len:
            cleaned = cleaned[:max_len]
        if cleaned != current:
            setattr(task, attr_name, cleaned)
            changed = True

    _clean_attr('title', 160)
    _clean_attr('objective', 180)
    _clean_attr('coaching_points')
    _clean_attr('confrontation_rules')

    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    if layout:
        layout_copy = dict(layout)
        meta = layout_copy.get('meta') if isinstance(layout_copy.get('meta'), dict) else {}
        meta = dict(meta)
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        analysis_meta = dict(analysis_meta)
        summary_raw = str(analysis_meta.get('summary') or '')
        summary_clean = _repair_joined_words_text(summary_raw)[:900]
        if summary_clean != summary_raw:
            analysis_meta['summary'] = summary_clean
            changed = True
        task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
        if task_sheet:
            task_sheet_copy = dict(task_sheet)
            for key in ('description', 'players', 'space', 'dimensions', 'materials'):
                raw_val = str(task_sheet_copy.get(key) or '')
                clean_val = _repair_joined_words_text(raw_val)
                if clean_val != raw_val:
                    task_sheet_copy[key] = clean_val
                    changed = True
            analysis_meta['task_sheet'] = task_sheet_copy
        meta['analysis'] = analysis_meta
        layout_copy['meta'] = meta
        if layout_copy != layout:
            task.tactical_layout = layout_copy
            changed = True

    if changed:
        task.save(
            update_fields=[
                'title',
                'objective',
                'coaching_points',
                'confrontation_rules',
                'tactical_layout',
            ]
        )
    return changed


def _update_library_task_from_post(task, post_data, scope_key=None):
    if not task:
        raise ValueError('Tarea no encontrada.')
    if scope_key and _task_scope_for_item(task) != scope_key:
        raise ValueError('La tarea seleccionada no pertenece a este espacio.')

    _ensure_original_task_snapshot(task)

    title = (post_data.get('task_title') or '').strip()
    if not title:
        raise ValueError('El título de la tarea es obligatorio.')
    block = (post_data.get('task_block') or task.block or SessionTask.BLOCK_MAIN_1).strip()
    valid_blocks = {choice[0] for choice in SessionTask.BLOCK_CHOICES}
    if block not in valid_blocks:
        block = SessionTask.BLOCK_MAIN_1
    minutes = _parse_int(post_data.get('task_minutes'))
    if minutes is None:
        minutes = int(task.duration_minutes or 15)
    minutes = max(5, min(minutes, 90))

    task.title = _repair_joined_words_text(title[:220])[:160]
    task.block = block
    task.duration_minutes = minutes
    task.objective = _repair_joined_words_text((post_data.get('task_objective') or '').strip()[:260])[:180]
    task.coaching_points = _repair_joined_words_text((post_data.get('task_coaching_points') or '').strip())
    task.confrontation_rules = _repair_joined_words_text((post_data.get('task_confrontation_rules') or '').strip())

    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta = dict(meta)
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    analysis_meta = dict(analysis_meta)
    task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
    task_sheet = dict(task_sheet)

    sheet_field_map = {
        'task_sheet_description': 'description',
        'task_sheet_players': 'players',
        'task_sheet_space': 'space',
        'task_sheet_dimensions': 'dimensions',
        'task_sheet_materials': 'materials',
    }
    task_sheet_touched = False
    for post_key, sheet_key in sheet_field_map.items():
        if post_key in post_data:
            task_sheet[sheet_key] = _repair_joined_words_text(str(post_data.get(post_key) or '').strip())
            task_sheet_touched = True
    if task_sheet_touched:
        analysis_meta['task_sheet'] = task_sheet
        meta['analysis'] = analysis_meta
        layout['meta'] = meta
        task.tactical_layout = layout
        task.save(
            update_fields=[
                'title',
                'block',
                'duration_minutes',
                'objective',
                'coaching_points',
                'confrontation_rules',
                'tactical_layout',
            ]
        )
    else:
        layout['meta'] = meta
        task.tactical_layout = layout
        task.save(
            update_fields=[
                'title',
                'block',
                'duration_minutes',
                'objective',
                'coaching_points',
                'confrontation_rules',
                'tactical_layout',
            ]
        )


def _storage_url_or_empty(name):
    value = str(name or '').strip()
    if not value:
        return ''
    try:
        return default_storage.url(value)
    except Exception:
        return ''


def _ensure_original_task_snapshot(task):
    if not task:
        return {}
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta = dict(meta)
    if isinstance(meta.get('original_version'), dict):
        return meta.get('original_version') or {}
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    analysis_meta = dict(analysis_meta)
    task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
    snapshot = {
        'captured_at': timezone.now().isoformat(),
        'title': task.title or '',
        'block': task.block or '',
        'duration_minutes': int(task.duration_minutes or 0),
        'objective': task.objective or '',
        'coaching_points': task.coaching_points or '',
        'confrontation_rules': task.confrontation_rules or '',
        'task_sheet': dict(task_sheet),
        'graphic_editor': meta.get('graphic_editor') if isinstance(meta.get('graphic_editor'), dict) else {},
        'task_preview_image': task.task_preview_image.name if task.task_preview_image else '',
        'task_pdf': task.task_pdf.name if task.task_pdf else '',
    }
    meta['original_version'] = snapshot
    layout['meta'] = meta
    task.tactical_layout = layout
    task.save(update_fields=['tactical_layout'])
    return snapshot


def _is_imported_task(task):
    if not task:
        return False
    if bool(getattr(task, 'task_pdf', None)):
        return True
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    source = str(meta.get('source') or '').strip().lower()
    if source in {'pdf_analysis', 'pdf_import', 'pdf'}:
        return True
    if str(meta.get('pdf_source_name') or '').strip():
        return True
    return False


def _is_task_editable(task):
    return not _is_imported_task(task)


def _restore_task_from_original_snapshot(task, scope_key=None):
    if not task:
        raise ValueError('Tarea no encontrada.')
    if scope_key and _task_scope_for_item(task) != scope_key:
        raise ValueError('La tarea seleccionada no pertenece a este espacio.')
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta = dict(meta)
    original = meta.get('original_version') if isinstance(meta.get('original_version'), dict) else {}
    if not original:
        raise ValueError('La tarea no tiene versión original guardada.')

    task.title = str(original.get('title') or task.title or '')[:160]
    block = str(original.get('block') or task.block or SessionTask.BLOCK_MAIN_1).strip()
    if block not in {choice[0] for choice in SessionTask.BLOCK_CHOICES}:
        block = SessionTask.BLOCK_MAIN_1
    task.block = block
    task.duration_minutes = max(5, min(_parse_int(original.get('duration_minutes')) or int(task.duration_minutes or 15), 90))
    task.objective = str(original.get('objective') or '')[:180]
    task.coaching_points = str(original.get('coaching_points') or '')
    task.confrontation_rules = str(original.get('confrontation_rules') or '')

    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    analysis_meta = dict(analysis_meta)
    original_sheet = original.get('task_sheet') if isinstance(original.get('task_sheet'), dict) else {}
    if original_sheet:
        analysis_meta['task_sheet'] = dict(original_sheet)
        meta['analysis'] = analysis_meta

    original_graphic = original.get('graphic_editor') if isinstance(original.get('graphic_editor'), dict) else {}
    if original_graphic:
        meta['graphic_editor'] = dict(original_graphic)

    layout['meta'] = meta
    task.tactical_layout = layout
    preview_name = str(original.get('task_preview_image') or '').strip()
    update_fields = [
        'title',
        'block',
        'duration_minutes',
        'objective',
        'coaching_points',
        'confrontation_rules',
        'tactical_layout',
    ]
    if preview_name:
        task.task_preview_image = preview_name
        update_fields.append('task_preview_image')
    task.save(update_fields=update_fields)


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


def _sessions_tab_from_action(action):
    action_key = str(action or '').strip()
    if action_key == 'library_upload_pdf':
        return 'import'
    if action_key in {'bulk_create_tasks', 'create_draw_task'}:
        return 'create'
    if action_key in {
        'analyze_all_library_pdfs',
        'split_existing_library_pdfs',
        'analyze_library_pdf',
        'delete_library_task',
        'update_library_task',
        'create_task_from_analysis',
    }:
        return 'library'
    return 'library'


def _starter_canvas_state(preset):
    preset_key = str(preset or 'full_pitch').strip()
    if preset_key == 'blank':
        return {'version': '5.3.0', 'objects': []}

    background = {
        'type': 'rect',
        'left': 0,
        'top': 0,
        'width': 1280,
        'height': 720,
        'fill': '#0f9f36',
        'stroke': '',
        'strokeWidth': 0,
        'selectable': False,
        'evented': False,
        'excludeFromExport': False,
    }
    field_border = {
        'type': 'rect',
        'left': 60,
        'top': 40,
        'width': 1160,
        'height': 640,
        'fill': '',
        'stroke': 'rgba(255,255,255,0.8)',
        'strokeWidth': 4,
        'selectable': False,
        'evented': False,
        'excludeFromExport': False,
    }
    objects = [background, field_border]

    if preset_key == 'half_pitch':
        objects.extend(
            [
                {
                    'type': 'rect',
                    'left': 60,
                    'top': 40,
                    'width': 580,
                    'height': 640,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.6)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
                {
                    'type': 'circle',
                    'left': 640 - 90,
                    'top': 360 - 90,
                    'radius': 90,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.55)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
            ]
        )
    elif preset_key == 'futsal':
        objects.extend(
            [
                {
                    'type': 'rect',
                    'left': 220,
                    'top': 120,
                    'width': 840,
                    'height': 480,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.78)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
                {
                    'type': 'line',
                    'x1': 640,
                    'y1': 120,
                    'x2': 640,
                    'y2': 600,
                    'stroke': 'rgba(255,255,255,0.7)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
            ]
        )
    else:
        objects.extend(
            [
                {
                    'type': 'line',
                    'x1': 640,
                    'y1': 40,
                    'x2': 640,
                    'y2': 680,
                    'stroke': 'rgba(255,255,255,0.75)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
                {
                    'type': 'circle',
                    'left': 640 - 90,
                    'top': 360 - 90,
                    'radius': 90,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.55)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
                {
                    'type': 'rect',
                    'left': 60,
                    'top': 220,
                    'width': 170,
                    'height': 280,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.7)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
                {
                    'type': 'rect',
                    'left': 1050,
                    'top': 220,
                    'width': 170,
                    'height': 280,
                    'fill': '',
                    'stroke': 'rgba(255,255,255,0.7)',
                    'strokeWidth': 3,
                    'selectable': False,
                    'evented': False,
                },
            ]
        )

    return {'version': '5.3.0', 'objects': objects}


def _sessions_workspace_page(request, scope_key='coach', scope_title='Sesiones'):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')

    feedback = ''
    error = ''
    analysis = None
    analysis_task = None
    active_tab = 'library'

    planner_tables_ready = True
    try:
        SessionTask.objects.order_by('-id').values_list('id', flat=True).first()
    except (OperationalError, ProgrammingError):
        planner_tables_ready = False
        error = (
            'El módulo de sesiones requiere migración de base de datos. '
            'Ejecuta `python manage.py migrate` y recarga la página.'
        )

    all_sessions = list(
        TrainingSession.objects
        .select_related('microcycle')
        .filter(microcycle__team=primary_team)
        .order_by('-session_date', '-id')[:150]
    ) if planner_tables_ready else []

    if request.method == 'POST' and planner_tables_ready:
        planner_action = (request.POST.get('planner_action') or '').strip()
        posted_tab = (request.POST.get('planner_tab') or '').strip()
        if posted_tab in {'import', 'create', 'library'}:
            active_tab = posted_tab
        else:
            active_tab = _sessions_tab_from_action(planner_action)
        try:
            if planner_action == 'library_upload_pdf':
                title = (request.POST.get('pdf_task_title') or '').strip()
                objective = (request.POST.get('pdf_task_objective') or '').strip()
                block = (request.POST.get('pdf_task_block') or SessionTask.BLOCK_MAIN_1).strip()
                minutes = _parse_int(request.POST.get('pdf_task_minutes')) or 15
                pdf_files = list(request.FILES.getlist('library_task_pdf'))
                if block not in {choice[0] for choice in SessionTask.BLOCK_CHOICES}:
                    block = SessionTask.BLOCK_MAIN_1
                target_session = _get_or_create_library_session(primary_team, scope_key)
                if not pdf_files:
                    raise ValueError('Selecciona al menos un PDF.')
                for item in pdf_files:
                    if not str(getattr(item, 'name', '') or '').lower().endswith('.pdf'):
                        raise ValueError('Todos los archivos deben ser PDF.')
                base_order = SessionTask.objects.filter(session=target_session).count()
                created_count = 0
                processed_pdfs = 0
                for idx, pdf_file in enumerate(pdf_files, start=1):
                    raw_name = str(getattr(pdf_file, 'name', '') or '').rsplit('/', 1)[-1]
                    file_stem = raw_name.rsplit('.', 1)[0].strip() or f'Tarea PDF {idx}'
                    task_title = title or file_stem
                    if title and len(pdf_files) > 1:
                        task_title = f'{title} · {file_stem}'

                    extracted_text = ''
                    try:
                        extracted_text = _extract_pdf_text(pdf_file, max_chars=60000)
                    except Exception:
                        pass
                    parsed_tasks = _extract_tasks_from_pdf_text(extracted_text, fallback_title=task_title)
                    if not parsed_tasks:
                        parsed_tasks = [
                            {
                                'analysis': {
                                    'title': task_title[:160],
                                    'objective': objective[:180],
                                    'minutes': max(5, min(minutes, 90)),
                                    'coaching_points': '',
                                    'confrontation_rules': '',
                                    'summary': '',
                                    'work_contexts': [],
                                    'objective_tags': [],
                                    'exercise_types': [],
                                    'phase_tags': [],
                                    'players_count_estimate': None,
                                    'players_band': '',
                                    'duration_band': _duration_band_label(max(5, min(minutes, 90))),
                                    'detected_materials': [],
                                    'quality_score': 0,
                                },
                                'raw_text': '',
                                'segment_index': 1,
                                'segment_total': 1,
                            }
                        ]

                    if hasattr(pdf_file, 'seek'):
                        pdf_file.seek(0)
                    preview_payloads = _extract_preview_images_from_pdf(
                        pdf_file,
                        max_images=max(1, len(parsed_tasks)),
                    )

                    first = parsed_tasks[0]
                    first_analysis = first.get('analysis') or {}
                    first_title = (first_analysis.get('title') or task_title or 'Tarea desde PDF')[:160]
                    first_task = SessionTask.objects.create(
                        session=target_session,
                        title=first_title,
                        block=block,
                        duration_minutes=max(5, min((_parse_int(first_analysis.get('minutes')) or minutes), 90)),
                        objective=((first_analysis.get('objective') or objective or '')[:180]),
                        coaching_points=(first_analysis.get('coaching_points') or ''),
                        confrontation_rules=(first_analysis.get('confrontation_rules') or ''),
                        tactical_layout={
                            'meta': {
                                'scope': scope_key,
                                'pdf_source_name': raw_name,
                                'pdf_segment_index': first.get('segment_index') or 1,
                                'pdf_segments_total': first.get('segment_total') or 1,
                                'pdf_segment_excerpt': (first.get('raw_text') or '')[:1200],
                                'pdf_split_done': True,
                            }
                        },
                        task_pdf=pdf_file,
                        status=SessionTask.STATUS_PLANNED,
                        order=base_order + created_count + 1,
                        notes='Cargada desde Biblioteca PDF',
                    )
                    preview_payload = preview_payloads[0] if preview_payloads else None
                    if preview_payload:
                        preview_name, preview_content = preview_payload
                        first_task.task_preview_image.save(preview_name, preview_content, save=True)
                    try:
                        _apply_analysis_to_task(first_task, first_analysis)
                    except Exception:
                        pass
                    created_count += 1
                    processed_pdfs += 1

                    shared_pdf_name = first_task.task_pdf.name if first_task.task_pdf else ''
                    shared_preview_name = first_task.task_preview_image.name if first_task.task_preview_image else ''
                    for extra in parsed_tasks[1:]:
                        extra_analysis = extra.get('analysis') or {}
                        extra_title = (extra_analysis.get('title') or f'{task_title} · Tarea {extra.get("segment_index") or 0}')[:160]
                        extra_task = SessionTask.objects.create(
                            session=target_session,
                            title=extra_title,
                            block=block,
                            duration_minutes=max(5, min((_parse_int(extra_analysis.get('minutes')) or minutes), 90)),
                            objective=((extra_analysis.get('objective') or objective or '')[:180]),
                            coaching_points=(extra_analysis.get('coaching_points') or ''),
                            confrontation_rules=(extra_analysis.get('confrontation_rules') or ''),
                            tactical_layout={
                                'meta': {
                                    'scope': scope_key,
                                    'pdf_source_name': raw_name,
                                    'pdf_segment_index': extra.get('segment_index') or 1,
                                    'pdf_segments_total': extra.get('segment_total') or 1,
                                    'pdf_segment_excerpt': (extra.get('raw_text') or '')[:1200],
                                    'pdf_split_done': True,
                                }
                            },
                            task_pdf=shared_pdf_name or None,
                            task_preview_image=shared_preview_name or None,
                            status=SessionTask.STATUS_PLANNED,
                            order=base_order + created_count + 1,
                            notes='Extraída automáticamente desde PDF multi-tarea',
                        )
                        segment_index = max(1, int(extra.get('segment_index') or 1))
                        extra_preview_payload = None
                        if preview_payloads:
                            extra_preview_payload = preview_payloads[min(segment_index - 1, len(preview_payloads) - 1)]
                        if extra_preview_payload:
                            extra_preview_name, extra_preview_content = extra_preview_payload
                            extra_task.task_preview_image.save(extra_preview_name, extra_preview_content, save=True)
                        elif shared_preview_name:
                            extra_task.task_preview_image = shared_preview_name
                            extra_task.save(update_fields=['task_preview_image'])
                        try:
                            _apply_analysis_to_task(extra_task, extra_analysis)
                        except Exception:
                            pass
                        created_count += 1
                feedback = (
                    f'Se procesó 1 PDF y se creó 1 tarea.'
                    if created_count == 1 and processed_pdfs == 1
                    else f'Se procesaron {processed_pdfs} PDFs y se crearon {created_count} tareas.'
                )

            elif planner_action == 'bulk_create_tasks':
                bulk_text = (request.POST.get('bulk_tasks_text') or '').strip()
                block_default = (request.POST.get('bulk_default_block') or SessionTask.BLOCK_MAIN_1).strip()
                minutes_default = _parse_int(request.POST.get('bulk_default_minutes')) or 15
                target_session_id = _parse_int(request.POST.get('bulk_target_session_id'))
                if block_default not in {choice[0] for choice in SessionTask.BLOCK_CHOICES}:
                    block_default = SessionTask.BLOCK_MAIN_1
                minutes_default = max(5, min(minutes_default, 90))
                if not bulk_text:
                    raise ValueError('Pega al menos una línea para crear tareas.')

                target_session = None
                if target_session_id:
                    target_session = (
                        TrainingSession.objects
                        .select_related('microcycle')
                        .filter(id=target_session_id, microcycle__team=primary_team)
                        .first()
                    )
                if not target_session:
                    target_session = _get_or_create_library_session(primary_team, scope_key)

                parsed_rows, parse_errors = _parse_bulk_tasks_text(
                    bulk_text,
                    default_block=block_default,
                    default_minutes=minutes_default,
                )
                if not parsed_rows and parse_errors:
                    raise ValueError(parse_errors[0])
                if not parsed_rows:
                    raise ValueError('No se detectaron tareas válidas en el bloque pegado.')

                base_order = SessionTask.objects.filter(session=target_session).count()
                created_count = 0
                for row in parsed_rows:
                    SessionTask.objects.create(
                        session=target_session,
                        title=row['title'],
                        block=row['block'],
                        duration_minutes=row['minutes'],
                        objective=row['objective'],
                        coaching_points=row['coaching_points'],
                        confrontation_rules=row['confrontation_rules'],
                        tactical_layout={
                            'meta': {
                                'scope': scope_key,
                                'bulk_source': 'manual_batch',
                                'bulk_source_line': row.get('source_line'),
                            }
                        },
                        status=SessionTask.STATUS_PLANNED,
                        order=base_order + created_count + 1,
                        notes='Creada mediante carga masiva',
                    )
                    created_count += 1

                if parse_errors:
                    feedback = (
                        f'Carga masiva completada: {created_count} tareas creadas. '
                        f'Incidencias: {len(parse_errors)} (primer error: {parse_errors[0]}).'
                    )
                else:
                    feedback = f'Carga masiva completada: {created_count} tareas creadas.'

            elif planner_action == 'create_draw_task':
                target_session_id = _parse_int(request.POST.get('draw_target_session_id'))
                title = (request.POST.get('draw_task_title') or '').strip()
                block = (request.POST.get('draw_task_block') or SessionTask.BLOCK_MAIN_1).strip()
                minutes = _parse_int(request.POST.get('draw_task_minutes')) or 15
                objective = (request.POST.get('draw_task_objective') or '').strip()
                coaching_points = (request.POST.get('draw_task_coaching_points') or '').strip()
                confrontation_rules = (request.POST.get('draw_task_confrontation_rules') or '').strip()
                description = (request.POST.get('draw_task_description') or '').strip()
                players = (request.POST.get('draw_task_players') or '').strip()
                dimensions = (request.POST.get('draw_task_dimensions') or '').strip()
                space = (request.POST.get('draw_task_space') or '').strip()
                materials = (request.POST.get('draw_task_materials') or '').strip()
                organization = (request.POST.get('draw_task_organization') or '').strip()
                work_rest = (request.POST.get('draw_task_work_rest') or '').strip()
                load_target = (request.POST.get('draw_task_load_target') or '').strip()
                players_distribution = (request.POST.get('draw_task_players_distribution') or '').strip()
                progression = (request.POST.get('draw_task_progression') or '').strip()
                regression = (request.POST.get('draw_task_regression') or '').strip()
                success_criteria = (request.POST.get('draw_task_success_criteria') or '').strip()
                selected_surface = (request.POST.get('draw_task_surface') or '').strip()
                selected_pitch_format = (request.POST.get('draw_task_pitch_format') or '').strip()
                selected_phase = (request.POST.get('draw_task_game_phase') or '').strip()
                selected_methodology = (request.POST.get('draw_task_methodology') or '').strip()
                selected_complexity = (request.POST.get('draw_task_complexity') or '').strip()
                template_key = (request.POST.get('draw_task_template') or 'none').strip()
                pitch_preset = (request.POST.get('draw_task_pitch_preset') or 'full_pitch').strip()
                constraints = [str(v).strip() for v in request.POST.getlist('draw_constraints') if str(v).strip()]
                series = (request.POST.get('draw_task_series') or '').strip()
                repetitions = (request.POST.get('draw_task_repetitions') or '').strip()

                template_map = {
                    str(item.get('key') or ''): dict(item.get('values') or {})
                    for item in TASK_TEMPLATE_LIBRARY
                }
                template_values = template_map.get(template_key) or {}
                if not title:
                    title = str(template_values.get('task_title') or '').strip()
                if not objective:
                    objective = str(template_values.get('task_objective') or '').strip()
                if not coaching_points:
                    coaching_points = str(template_values.get('task_coaching_points') or '').strip()
                if not confrontation_rules:
                    confrontation_rules = str(template_values.get('task_confrontation_rules') or '').strip()
                if not space:
                    space = str(template_values.get('task_space') or '').strip()
                if not organization:
                    organization = str(template_values.get('task_organization') or '').strip()
                if not players_distribution:
                    players_distribution = str(template_values.get('task_players_distribution') or '').strip()
                if not load_target:
                    load_target = str(template_values.get('task_load_target') or '').strip()
                if not work_rest:
                    work_rest = str(template_values.get('task_work_rest') or '').strip()
                if not series:
                    series = str(template_values.get('task_series') or '').strip()
                if not repetitions:
                    repetitions = str(template_values.get('task_repetitions') or '').strip()
                if not progression:
                    progression = str(template_values.get('task_progression') or '').strip()
                if not regression:
                    regression = str(template_values.get('task_regression') or '').strip()
                if not success_criteria:
                    success_criteria = str(template_values.get('task_success_criteria') or '').strip()

                if not title:
                    raise ValueError('Indica un título para la tarea dibujada.')
                if block not in {choice[0] for choice in SessionTask.BLOCK_CHOICES}:
                    block = SessionTask.BLOCK_MAIN_1
                minutes = max(5, min(minutes, 90))
                valid_surfaces = {key for key, _ in TASK_SURFACE_CHOICES}
                valid_pitch_formats = {key for key, _ in TASK_PITCH_FORMAT_CHOICES}
                valid_phases = {key for key, _ in TASK_GAME_PHASE_CHOICES}
                valid_methodologies = {key for key, _ in TASK_METHODOLOGY_CHOICES}
                valid_complexities = {key for key, _ in TASK_COMPLEXITY_CHOICES}
                valid_constraints = {key for key, _ in TASK_CONSTRAINT_CHOICES}
                constraints = [item for item in constraints if item in valid_constraints]
                if selected_surface not in valid_surfaces:
                    selected_surface = ''
                if selected_pitch_format not in valid_pitch_formats:
                    selected_pitch_format = ''
                if selected_phase not in valid_phases:
                    selected_phase = ''
                if selected_methodology not in valid_methodologies:
                    selected_methodology = ''
                if selected_complexity not in valid_complexities:
                    selected_complexity = ''
                if pitch_preset not in {'full_pitch', 'half_pitch', 'futsal', 'blank'}:
                    pitch_preset = 'full_pitch'
                target_session = None
                if target_session_id:
                    target_session = (
                        TrainingSession.objects
                        .select_related('microcycle')
                        .filter(id=target_session_id, microcycle__team=primary_team)
                        .first()
                    )
                if not target_session:
                    target_session = _get_or_create_library_session(primary_team, scope_key)
                canvas_state = None
                raw_canvas_state = (request.POST.get('draw_canvas_state') or '').strip()
                if raw_canvas_state:
                    try:
                        parsed_state = json.loads(raw_canvas_state)
                        if isinstance(parsed_state, dict):
                            canvas_state = parsed_state
                    except Exception:
                        canvas_state = None
                if not isinstance(canvas_state, dict):
                    canvas_state = _starter_canvas_state(pitch_preset)

                canvas_width = _parse_int(request.POST.get('draw_canvas_width')) or 1280
                canvas_height = _parse_int(request.POST.get('draw_canvas_height')) or 720
                canvas_width = max(320, min(canvas_width, 3840))
                canvas_height = max(180, min(canvas_height, 2160))

                task = SessionTask.objects.create(
                    session=target_session,
                    title=title[:160],
                    block=block,
                    duration_minutes=minutes,
                    objective=objective[:180],
                    coaching_points=coaching_points,
                    confrontation_rules=confrontation_rules,
                    tactical_layout={
                        'meta': {
                            'scope': scope_key,
                            'source': 'manual-draw',
                            'template_key': template_key,
                            'surface': selected_surface,
                            'pitch_format': selected_pitch_format,
                            'game_phase': selected_phase,
                            'methodology': selected_methodology,
                            'complexity': selected_complexity,
                            'space': space,
                            'organization': organization,
                            'players_distribution': players_distribution,
                            'load_target': load_target,
                            'work_rest': work_rest,
                            'series': series,
                            'repetitions': repetitions,
                            'progression': progression,
                            'regression': regression,
                            'success_criteria': success_criteria,
                            'constraints': constraints,
                            'graphic_editor': {
                                'canvas_state': canvas_state,
                                'canvas_width': canvas_width,
                                'canvas_height': canvas_height,
                            },
                            'analysis': {
                                'task_sheet': {
                                    'description': description,
                                    'players': players,
                                    'space': space,
                                    'dimensions': dimensions,
                                    'materials': materials,
                                }
                            },
                        }
                    },
                    status=SessionTask.STATUS_PLANNED,
                    order=SessionTask.objects.filter(session=target_session).count() + 1,
                    notes='Tarea creada para dibujo manual',
                )
                preview_data = request.POST.get('draw_canvas_preview_data')
                if preview_data:
                    raw_bytes, extension = _decode_canvas_data_url(preview_data)
                    if raw_bytes and extension:
                        filename = f'task_preview_{task.id}{extension}'
                        task.task_preview_image.save(filename, ContentFile(raw_bytes), save=False)
                        task.save(update_fields=['task_preview_image'])
                feedback = 'Tarea creada con pizarra táctica.'

            elif planner_action == 'analyze_all_library_pdfs':
                tasks_for_scope = list(
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(session__microcycle__team=primary_team, task_pdf__isnull=False)
                    .order_by('-id')[:400]
                )
                tasks_for_scope = [item for item in tasks_for_scope if _task_scope_for_item(item) == scope_key]
                success_count = 0
                fail_count = 0
                for item in tasks_for_scope:
                    try:
                        extracted_text = _extract_pdf_text(item.task_pdf)
                        parsed = _suggest_task_from_pdf(extracted_text)
                        _apply_analysis_to_task(item, parsed)
                        success_count += 1
                    except Exception:
                        fail_count += 1
                feedback = f'Análisis masivo completado. OK: {success_count} · Error: {fail_count}.'

            elif planner_action == 'split_existing_library_pdfs':
                tasks_for_scope = list(
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(session__microcycle__team=primary_team, task_pdf__isnull=False)
                    .order_by('id')[:600]
                )
                tasks_for_scope = [item for item in tasks_for_scope if _task_scope_for_item(item) == scope_key]
                split_ok = 0
                split_created = 0
                split_skipped = 0
                split_fail = 0
                for item in tasks_for_scope:
                    layout = item.tactical_layout if isinstance(item.tactical_layout, dict) else {}
                    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
                    if meta.get('pdf_split_done'):
                        split_skipped += 1
                        continue
                    if int(meta.get('pdf_segments_total') or 1) > 1:
                        meta['pdf_split_done'] = True
                        layout['meta'] = meta
                        item.tactical_layout = layout
                        item.save(update_fields=['tactical_layout'])
                        split_skipped += 1
                        continue
                    try:
                        extracted_text = _extract_pdf_text(item.task_pdf, max_chars=30000)
                        parsed_tasks = _extract_tasks_from_pdf_text(extracted_text, fallback_title=item.title or 'Tarea desde PDF')
                        if not parsed_tasks:
                            meta['pdf_split_done'] = True
                            layout['meta'] = meta
                            item.tactical_layout = layout
                            item.save(update_fields=['tactical_layout'])
                            split_skipped += 1
                            continue
                        if len(parsed_tasks) <= 1:
                            single = parsed_tasks[0]
                            single_analysis = single.get('analysis') or {}
                            if single_analysis:
                                item.title = (single_analysis.get('title') or item.title or 'Tarea desde PDF')[:160]
                                item.duration_minutes = max(
                                    5,
                                    min((_parse_int(single_analysis.get('minutes')) or item.duration_minutes or 15), 90),
                                )
                                item.objective = (single_analysis.get('objective') or item.objective or '')[:180]
                                item.coaching_points = single_analysis.get('coaching_points') or item.coaching_points or ''
                                item.confrontation_rules = single_analysis.get('confrontation_rules') or item.confrontation_rules or ''
                            meta['pdf_segment_index'] = 1
                            meta['pdf_segments_total'] = 1
                            meta['pdf_segment_excerpt'] = (single.get('raw_text') or '')[:1200]
                            meta['pdf_split_done'] = True
                            layout['meta'] = meta
                            item.tactical_layout = layout
                            item.save(
                                update_fields=[
                                    'title',
                                    'duration_minutes',
                                    'objective',
                                    'coaching_points',
                                    'confrontation_rules',
                                    'tactical_layout',
                                ]
                            )
                            try:
                                _apply_analysis_to_task(item, single_analysis)
                            except Exception:
                                pass
                            split_ok += 1
                            continue

                        if hasattr(item.task_pdf, 'seek'):
                            item.task_pdf.seek(0)
                        preview_payloads = _extract_preview_images_from_pdf(
                            item.task_pdf,
                            max_images=max(1, len(parsed_tasks)),
                        )
                        original_order = int(item.order or 0)
                        first = parsed_tasks[0]
                        first_analysis = first.get('analysis') or {}
                        item.title = (first_analysis.get('title') or item.title or 'Tarea desde PDF')[:160]
                        item.duration_minutes = max(
                            5,
                            min((_parse_int(first_analysis.get('minutes')) or item.duration_minutes or 15), 90),
                        )
                        item.objective = (first_analysis.get('objective') or item.objective or '')[:180]
                        item.coaching_points = first_analysis.get('coaching_points') or item.coaching_points or ''
                        item.confrontation_rules = first_analysis.get('confrontation_rules') or item.confrontation_rules or ''
                        meta['pdf_segment_index'] = 1
                        meta['pdf_segments_total'] = len(parsed_tasks)
                        meta['pdf_segment_excerpt'] = (first.get('raw_text') or '')[:1200]
                        meta['pdf_split_done'] = True
                        layout['meta'] = meta
                        item.tactical_layout = layout
                        if preview_payloads:
                            first_preview_name, first_preview_content = preview_payloads[0]
                            item.task_preview_image.save(first_preview_name, first_preview_content, save=False)
                        item.save(
                            update_fields=[
                                'title',
                                'duration_minutes',
                                'objective',
                                'coaching_points',
                                'confrontation_rules',
                                'tactical_layout',
                                'task_preview_image',
                            ]
                        )
                        try:
                            _apply_analysis_to_task(item, first_analysis)
                        except Exception:
                            pass

                        for offset, extra in enumerate(parsed_tasks[1:], start=1):
                            extra_analysis = extra.get('analysis') or {}
                            extra_title = (extra_analysis.get('title') or f'{item.title} · Tarea {offset + 1}')[:160]
                            extra_layout = {
                                'meta': {
                                    'scope': scope_key,
                                    'pdf_source_name': str(meta.get('pdf_source_name') or Path(item.task_pdf.name).name),
                                    'pdf_segment_index': extra.get('segment_index') or (offset + 1),
                                    'pdf_segments_total': len(parsed_tasks),
                                    'pdf_segment_excerpt': (extra.get('raw_text') or '')[:1200],
                                    'pdf_split_done': True,
                                }
                            }
                            new_task = SessionTask.objects.create(
                                session=item.session,
                                title=extra_title,
                                block=item.block,
                                duration_minutes=max(
                                    5,
                                    min((_parse_int(extra_analysis.get('minutes')) or item.duration_minutes or 15), 90),
                                ),
                                objective=((extra_analysis.get('objective') or '')[:180]),
                                coaching_points=(extra_analysis.get('coaching_points') or ''),
                                confrontation_rules=(extra_analysis.get('confrontation_rules') or ''),
                                tactical_layout=extra_layout,
                                task_pdf=item.task_pdf.name,
                                status=SessionTask.STATUS_PLANNED,
                                order=original_order + offset,
                                notes='Separada automáticamente desde PDF existente',
                            )
                            preview_idx = min(offset, len(preview_payloads) - 1) if preview_payloads else -1
                            if preview_idx >= 0:
                                extra_preview_name, extra_preview_content = preview_payloads[preview_idx]
                                new_task.task_preview_image.save(extra_preview_name, extra_preview_content, save=True)
                            elif item.task_preview_image:
                                new_task.task_preview_image = item.task_preview_image.name
                                new_task.save(update_fields=['task_preview_image'])
                            try:
                                _apply_analysis_to_task(new_task, extra_analysis)
                            except Exception:
                                pass
                            split_created += 1

                        split_ok += 1
                    except Exception:
                        split_fail += 1
                feedback = (
                    f'Separación completada. PDFs revisados: {split_ok} · '
                    f'Tareas nuevas: {split_created} · Omitidos: {split_skipped} · Error: {split_fail}.'
                )

            elif planner_action == 'analyze_library_pdf':
                task_id = _parse_int(request.POST.get('task_id'))
                analysis_task = (
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(id=task_id, session__microcycle__team=primary_team)
                    .first()
                )
                if not analysis_task or not analysis_task.task_pdf:
                    raise ValueError('Selecciona una tarea con PDF guardado para analizar.')
                if _task_scope_for_item(analysis_task) != scope_key:
                    raise ValueError('La tarea seleccionada no pertenece a este espacio.')
                pdf_text = _extract_pdf_text(analysis_task.task_pdf)
                analysis = _suggest_task_from_pdf(pdf_text)
                analysis['raw_text'] = pdf_text[:2500]
                _apply_analysis_to_task(analysis_task, analysis)

            elif planner_action == 'delete_library_task':
                task_id = _parse_int(request.POST.get('task_id'))
                target_task = (
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(id=task_id, session__microcycle__team=primary_team)
                    .first()
                )
                if not target_task:
                    raise ValueError('Tarea no encontrada.')
                if _task_scope_for_item(target_task) != scope_key:
                    raise ValueError('La tarea seleccionada no pertenece a este espacio.')
                task_title = str(target_task.title or f'Tarea {target_task.id}')
                if target_task.task_preview_image:
                    try:
                        target_task.task_preview_image.delete(save=False)
                    except Exception:
                        pass
                # Intentionally keep PDF files that might be shared across split tasks.
                target_task.delete()
                feedback = f'Tarea eliminada: {task_title}.'

            elif planner_action == 'update_library_task':
                task_id = _parse_int(request.POST.get('task_id'))
                target_task = (
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(id=task_id, session__microcycle__team=primary_team)
                    .first()
                )
                _update_library_task_from_post(target_task, request.POST, scope_key=scope_key)
                feedback = 'Tarea actualizada correctamente.'

            elif planner_action == 'create_task_from_analysis':
                source_task_id = _parse_int(request.POST.get('source_task_id'))
                target_session_id = _parse_int(request.POST.get('target_session_id'))
                title = (request.POST.get('task_title') or '').strip()
                objective = (request.POST.get('task_objective') or '').strip()
                coaching_points = (request.POST.get('task_coaching_points') or '').strip()
                confrontation_rules = (request.POST.get('task_confrontation_rules') or '').strip()
                minutes = _parse_int(request.POST.get('task_minutes')) or 15
                block = (request.POST.get('task_block') or SessionTask.BLOCK_MAIN_1).strip()

                if not title:
                    raise ValueError('El título de la tarea es obligatorio.')
                if block not in {choice[0] for choice in SessionTask.BLOCK_CHOICES}:
                    block = SessionTask.BLOCK_MAIN_1

                source_task = (
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(id=source_task_id, session__microcycle__team=primary_team)
                    .first()
                )
                target_session = (
                    TrainingSession.objects
                    .select_related('microcycle')
                    .filter(id=target_session_id, microcycle__team=primary_team)
                    .first()
                )
                if not source_task or not source_task.task_pdf:
                    raise ValueError('No se encontró el PDF fuente para crear la tarea.')
                if _task_scope_for_item(source_task) != scope_key:
                    raise ValueError('El PDF fuente no pertenece a este espacio.')
                if not target_session:
                    raise ValueError('Selecciona una sesión destino válida.')

                extracted_text = (request.POST.get('task_raw_text') or '').strip()
                layout_meta = {
                    'source': 'pdf_analysis',
                    'source_task_id': source_task.id,
                    'extracted_text_excerpt': extracted_text[:1200],
                    'scope': scope_key,
                }
                created_task = SessionTask.objects.create(
                    session=target_session,
                    title=title[:160],
                    block=block,
                    duration_minutes=max(5, min(minutes, 90)),
                    objective=objective[:180],
                    coaching_points=coaching_points,
                    confrontation_rules=confrontation_rules,
                    tactical_layout={'meta': layout_meta},
                    task_pdf=source_task.task_pdf,
                    task_preview_image=source_task.task_preview_image,
                    status=SessionTask.STATUS_PLANNED,
                    order=SessionTask.objects.filter(session=target_session).count() + 1,
                    notes='Creada con editor basado en análisis de PDF',
                )
                if not created_task.task_preview_image and created_task.task_pdf:
                    preview_payload = _extract_preview_image_from_pdf(created_task.task_pdf)
                    if preview_payload:
                        preview_name, preview_content = preview_payload
                        created_task.task_preview_image.save(preview_name, preview_content, save=True)
                if source_task and isinstance(source_task.tactical_layout, dict):
                    source_meta = source_task.tactical_layout.get('meta') if isinstance(source_task.tactical_layout.get('meta'), dict) else {}
                    source_analysis = source_meta.get('analysis') if isinstance(source_meta.get('analysis'), dict) else {}
                    if source_analysis:
                        _apply_analysis_to_task(created_task, source_analysis)
                feedback = 'Tarea creada desde análisis de PDF.'
            else:
                error = 'Acción no reconocida.'
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = 'No se pudo completar la operación. Revisa los datos e inténtalo de nuevo.'
    elif request.method == 'GET':
        requested_tab = (request.GET.get('tab') or '').strip()
        if requested_tab in {'import', 'create', 'library'}:
            active_tab = requested_tab

    analyze_task_id = _parse_int(request.GET.get('analyze'))
    if planner_tables_ready and analyze_task_id and not analysis:
        candidate = (
            SessionTask.objects
            .select_related('session__microcycle')
            .filter(id=analyze_task_id, session__microcycle__team=primary_team)
            .first()
        )
        if candidate and candidate.task_pdf:
            try:
                pdf_text = _extract_pdf_text(candidate.task_pdf)
                analysis_task = candidate
                analysis = _suggest_task_from_pdf(pdf_text)
                analysis['raw_text'] = pdf_text[:2500]
                _apply_analysis_to_task(analysis_task, analysis)
            except ValueError as exc:
                error = str(exc)

    task_library_raw = list(
        SessionTask.objects
        .select_related('session__microcycle')
        .filter(session__microcycle__team=primary_team)
        .order_by('-id')[:300]
    ) if planner_tables_ready else []
    task_library = [item for item in task_library_raw if _task_scope_for_item(item) == scope_key]
    if active_tab == 'library' and task_library:
        preview_rebuilt = 0
        preview_upgraded = 0
        text_normalized = 0
        for task in task_library:
            if _cleanup_task_joined_text_fields(task):
                text_normalized += 1
            before_name = str(getattr(task, 'task_preview_image', '') or '').strip()
            should_refresh = _task_preview_needs_refresh(task)
            if not should_refresh:
                continue
            had_preview = bool(before_name)
            if _ensure_library_task_preview(task, force=had_preview, prefer_render=had_preview):
                after_name = str(getattr(task, 'task_preview_image', '') or '').strip()
                if after_name:
                    if had_preview:
                        preview_upgraded += 1
                    else:
                        preview_rebuilt += 1
        if preview_rebuilt or preview_upgraded or text_normalized:
            rebuilt_msg = f'Previews recuperadas: {preview_rebuilt}.' if preview_rebuilt else ''
            upgraded_msg = f'Previews mejoradas: {preview_upgraded}.' if preview_upgraded else ''
            cleaned_msg = f'Textos corregidos: {text_normalized}.' if text_normalized else ''
            joined = ' '.join([part for part in [rebuilt_msg, upgraded_msg, cleaned_msg] if part]).strip()
            feedback = (
                f'{feedback} '
                if feedback
                else ''
            ) + joined

    context_groups = defaultdict(list)
    objective_groups = defaultdict(list)
    type_groups = defaultdict(list)
    phase_groups = defaultdict(list)
    players_band_groups = defaultdict(list)
    duration_band_groups = defaultdict(list)
    for task in task_library:
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        task.analysis_meta = analysis_meta
        task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
        task.task_sheet = task_sheet
        task.is_imported = _is_imported_task(task)
        task.analysis_summary = str(analysis_meta.get('summary') or '').strip()
        task.detected_materials = analysis_meta.get('detected_materials') if isinstance(analysis_meta.get('detected_materials'), list) else []
        task.exercise_types = analysis_meta.get('exercise_types') if isinstance(analysis_meta.get('exercise_types'), list) else []
        task.phase_tags = analysis_meta.get('phase_tags') if isinstance(analysis_meta.get('phase_tags'), list) else []
        if not task.exercise_types or not task.phase_tags:
            fallback_haystack = '\n'.join(
                [
                    str(task.title or ''),
                    str(task.objective or ''),
                    str(task.coaching_points or ''),
                    str(task.confrontation_rules or ''),
                    task.analysis_summary,
                    str(task_sheet.get('description') or ''),
                ]
            )
            if not task.exercise_types:
                task.exercise_types = _detect_keyword_tags(fallback_haystack, TASK_TYPE_KEYWORDS)
            if not task.phase_tags:
                task.phase_tags = _detect_keyword_tags(fallback_haystack, TASK_PHASE_KEYWORDS)
        task.players_count_estimate = _parse_int(analysis_meta.get('players_count_estimate'))
        task.players_band = str(analysis_meta.get('players_band') or '').strip()
        if not task.players_band and task.task_sheet:
            task.players_band = _players_band_label(_estimate_players_count(task.task_sheet.get('players') or '', task.title))
        task.duration_band = str(analysis_meta.get('duration_band') or '').strip()
        if not task.duration_band:
            task.duration_band = _duration_band_label(task.duration_minutes)
        objective_summary = str(task.objective or '').strip()
        if not objective_summary:
            objective_summary = str(task_sheet.get('description') or '').strip()
        if not objective_summary:
            objective_summary = str(analysis_meta.get('summary') or '').strip()
        task.objective_summary = objective_summary or 'Sin objetivo extraído todavía.'
        for ctx in analysis_meta.get('work_contexts') or []:
            context_groups[str(ctx)].append(task)
        for obj in analysis_meta.get('objective_tags') or []:
            objective_groups[str(obj)].append(task)
        for exercise_type in task.exercise_types:
            type_groups[str(exercise_type)].append(task)
        for phase_tag in task.phase_tags:
            phase_groups[str(phase_tag)].append(task)
        if task.players_band:
            players_band_groups[task.players_band].append(task)
        if task.duration_band:
            duration_band_groups[task.duration_band].append(task)
    _persist_detected_resources_library(task_library, scope_key=scope_key)
    context_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in context_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    objective_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in objective_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    type_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in type_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    phase_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in phase_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    players_band_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in players_band_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    duration_band_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in duration_band_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )

    return render(
        request,
        'football/sessions_planner.html',
        {
            'team_name': primary_team.name,
            'feedback': feedback,
            'error': error,
            'planner_tables_ready': planner_tables_ready,
            'task_blocks': SessionTask.BLOCK_CHOICES,
            'all_sessions': all_sessions,
            'task_library': task_library,
            'analysis': analysis,
            'analysis_task': analysis_task,
            'scope_key': scope_key,
            'scope_title': scope_title,
            'context_group_rows': context_group_rows,
            'objective_group_rows': objective_group_rows,
            'type_group_rows': type_group_rows,
            'phase_group_rows': phase_group_rows,
            'players_band_group_rows': players_band_group_rows,
            'duration_band_group_rows': duration_band_group_rows,
            'active_tab': active_tab,
            'task_templates': TASK_TEMPLATE_LIBRARY,
            'task_surface_choices': TASK_SURFACE_CHOICES,
            'task_pitch_choices': TASK_PITCH_FORMAT_CHOICES,
            'task_phase_choices': TASK_GAME_PHASE_CHOICES,
            'task_methodology_choices': TASK_METHODOLOGY_CHOICES,
            'task_complexity_choices': TASK_COMPLEXITY_CHOICES,
            'task_constraint_choices': TASK_CONSTRAINT_CHOICES,
        },
    )


def sessions_page(request):
    return _sessions_workspace_page(request, scope_key='coach', scope_title='Sesiones · Entrenador')


def sessions_goalkeeper_page(request):
    return _sessions_workspace_page(request, scope_key='goalkeeper', scope_title='Sesiones · Porteros')


def sessions_fitness_page(request):
    return _sessions_workspace_page(request, scope_key='fitness', scope_title='Sesiones · Preparacion fisica')


@login_required
def session_task_detail_page(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task:
        raise Http404('Tarea no encontrada')

    scope_key = _task_scope_for_item(task)
    scope_route_name = {
        'coach': 'sessions',
        'goalkeeper': 'sessions-goalkeeper',
        'fitness': 'sessions-fitness',
    }.get(scope_key, 'sessions')
    scope_title = {
        'coach': 'Sesiones · Entrenador',
        'goalkeeper': 'Sesiones · Porteros',
        'fitness': 'Sesiones · Preparacion fisica',
    }.get(scope_key, 'Sesiones')

    feedback = ''
    error = ''
    is_editable_task = _is_task_editable(task)
    is_imported_task = _is_imported_task(task)
    if request.method == 'POST':
        detail_action = (request.POST.get('detail_action') or '').strip()
        try:
            if detail_action == 'update_task_detail':
                if not is_editable_task:
                    raise ValueError('Las tareas importadas son de solo lectura.')
                _update_library_task_from_post(task, request.POST, scope_key=scope_key)
                feedback = 'Tarea actualizada correctamente.'
                task.refresh_from_db()
            elif detail_action == 'restore_original_version':
                if not is_editable_task:
                    raise ValueError('Las tareas importadas son de solo lectura.')
                _restore_task_from_original_snapshot(task, scope_key=scope_key)
                feedback = 'Se restauró la versión original de la tarea.'
                task.refresh_from_db()
            else:
                error = 'Acción no reconocida.'
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = 'No se pudo guardar la tarea.'

    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
    original_version = meta.get('original_version') if isinstance(meta.get('original_version'), dict) else {}
    original_task_sheet = original_version.get('task_sheet') if isinstance(original_version.get('task_sheet'), dict) else {}
    original_preview_url = _storage_url_or_empty(original_version.get('task_preview_image') if isinstance(original_version, dict) else '')
    pdf_excerpt = str(meta.get('pdf_segment_excerpt') or meta.get('extracted_text_excerpt') or '').strip()
    detected_materials = analysis_meta.get('detected_materials') if isinstance(analysis_meta.get('detected_materials'), list) else []
    if task.task_pdf and not task.task_preview_image:
        _ensure_task_preview_image(task)
    return render(
        request,
        'football/session_task_detail.html',
        {
            'task': task,
            'scope_key': scope_key,
            'scope_title': scope_title,
            'scope_route_name': scope_route_name,
            'analysis_meta': analysis_meta,
            'task_sheet': task_sheet,
            'pdf_excerpt': pdf_excerpt,
            'detected_materials': detected_materials,
            'feedback': feedback,
            'error': error,
            'task_blocks': SessionTask.BLOCK_CHOICES,
            'graphic_editor_state_json': json.dumps(meta.get('graphic_editor', {}), ensure_ascii=False),
            'original_version': original_version,
            'original_task_sheet': original_task_sheet,
            'original_preview_url': original_preview_url,
            'is_editable_task': is_editable_task,
            'is_imported_task': is_imported_task,
        },
    )


@authenticated_write
@require_POST
def save_session_task_graphic(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return JsonResponse({'error': 'No tienes permisos para acceder a sesiones.'}, status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task:
        return JsonResponse({'error': 'Tarea no encontrada.'}, status=404)
    if not _is_task_editable(task):
        return JsonResponse({'error': 'Las tareas importadas son de solo lectura.'}, status=403)
    payload = {}
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except Exception:
        return JsonResponse({'error': 'Payload inválido.'}, status=400)

    canvas_state = payload.get('canvas_state')
    if not isinstance(canvas_state, dict):
        return JsonResponse({'error': 'Estado gráfico inválido.'}, status=400)
    canvas_width = _parse_int(payload.get('canvas_width'))
    canvas_height = _parse_int(payload.get('canvas_height'))

    _ensure_original_task_snapshot(task)

    preview_data = payload.get('preview_data')
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout = dict(layout)
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    meta = dict(meta)
    graphic_editor = meta.get('graphic_editor') if isinstance(meta.get('graphic_editor'), dict) else {}
    graphic_editor = dict(graphic_editor)
    graphic_editor.update(
        {
            'canvas_state': canvas_state,
            'canvas_width': canvas_width if canvas_width and canvas_width > 0 else None,
            'canvas_height': canvas_height if canvas_height and canvas_height > 0 else None,
            'updated_at': timezone.now().isoformat(),
            'updated_by': request.user.get_username() if request.user.is_authenticated else '',
        }
    )
    meta['graphic_editor'] = graphic_editor
    layout['meta'] = meta
    task.tactical_layout = layout
    update_fields = ['tactical_layout']

    if preview_data:
        raw_bytes, extension = _decode_canvas_data_url(preview_data)
        if raw_bytes and extension:
            filename = f'task-{task.id}-graphic-{uuid.uuid4().hex[:10]}{extension}'
            task.task_preview_image.save(filename, ContentFile(raw_bytes), save=False)
            update_fields.append('task_preview_image')

    task.save(update_fields=update_fields)
    return JsonResponse({'saved': True, 'task_id': task.id})


@login_required
def session_task_preview_file(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task:
        raise Http404('Imagen de tarea no disponible')
    if not task.task_preview_image:
        if not _ensure_library_task_preview(task):
            raise Http404('Imagen de tarea no disponible')
    file_field = task.task_preview_image
    try:
        file_field.open('rb')
    except Exception:
        # If stored preview is broken/missing, try to regenerate from PDF on the fly.
        if _ensure_library_task_preview(task):
            file_field = task.task_preview_image
            try:
                file_field.open('rb')
            except Exception:
                return HttpResponse('No se pudo abrir la imagen de la tarea.', status=500)
        else:
            return HttpResponse('No se pudo abrir la imagen de la tarea.', status=500)
    extension = Path(file_field.name).suffix.lower()
    content_type = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
    }.get(extension, 'application/octet-stream')
    response = FileResponse(file_field, content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{Path(file_field.name).name}"'
    return response


@login_required
def session_task_file(request, task_id):
    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    task = (
        SessionTask.objects
        .select_related('session__microcycle__team')
        .filter(id=task_id)
        .first()
    )
    if not task or not task.task_pdf:
        raise Http404('Archivo de tarea no disponible')
    file_field = task.task_pdf
    try:
        file_field.open('rb')
    except Exception:
        return HttpResponse('No se pudo abrir el archivo PDF.', status=500)
    filename = (Path(file_field.name).name or f'tarea-{task.id}.pdf').replace('"', '')
    response = FileResponse(file_field, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def fines_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    error = ''
    message = ''
    can_manage_fines = _is_admin_user(request.user)
    if request.method == 'POST':
        if not can_manage_fines:
            error = 'Solo administradores pueden registrar o eliminar multas.'
        else:
            form_action = (request.POST.get('form_action') or 'add').strip().lower()
            if form_action == 'delete':
                fine_id = _parse_int(request.POST.get('fine_id'))
                fine = PlayerFine.objects.filter(id=fine_id, player__team=primary_team).first() if fine_id else None
                if not fine:
                    error = 'Multa no encontrada.'
                else:
                    fine.delete()
                    message = 'Multa eliminada.'
            else:
                player_id = _parse_int(request.POST.get('player_id'))
                reason = (request.POST.get('reason') or '').strip()
                amount = _parse_int(request.POST.get('amount')) or 0
                note = (request.POST.get('note') or '').strip()
                player = Player.objects.filter(id=player_id, team=primary_team).first() if player_id else None
                valid_reasons = {item[0] for item in PlayerFine.REASON_CHOICES}
                if not player:
                    error = 'Selecciona un jugador válido.'
                elif reason not in valid_reasons:
                    error = 'Selecciona un motivo válido.'
                elif amount <= 0 or amount % 5 != 0:
                    error = 'La cantidad debe ser un múltiplo de 5.'
                else:
                    PlayerFine.objects.create(
                        player=player,
                        reason=reason,
                        amount=amount,
                        note=note,
                        created_by=(request.user.get_username() if request.user.is_authenticated else ''),
                    )
                    message = 'Multa registrada.'
    players = list(Player.objects.filter(team=primary_team, is_active=True).order_by('number', 'name'))
    fines = list(PlayerFine.objects.filter(player__team=primary_team).select_related('player')[:120])
    reason_labels = dict(PlayerFine.REASON_CHOICES)
    summary_total = sum((item.amount or 0) for item in fines)
    return render(
        request,
        'football/fines.html',
        {
            'team_name': primary_team.name,
            'players': players,
            'fines': fines,
            'reason_choices': PlayerFine.REASON_CHOICES,
            'reason_labels': reason_labels,
            'summary_count': len(fines),
            'summary_total': summary_total,
            'message': message,
            'error': error,
            'can_manage_fines': can_manage_fines,
        },
    )


def analysis_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    team_url = ''
    team_id = ''
    raw_text = ''
    roster = []
    probable_eleven = []
    lineup = []
    insights = {}
    formation = 'Auto'
    error = ''
    auto_loaded = False
    auto_team_name = ''
    video_error = ''
    video_message = ''
    manual_report_error = ''
    manual_report_message = ''
    extracted = {}
    preferred_next = load_preferred_next_match_payload() or {}
    preferred_opponent = preferred_next.get('opponent') if isinstance(preferred_next, dict) else {}
    home_rival_name = _payload_opponent_name(preferred_next)
    if home_rival_name:
        home_rival_key = normalize_label(home_rival_name)
        guessed_team = Team.objects.filter(is_primary=False).order_by('name').filter(name__icontains=home_rival_name[:12]).first()
        if guessed_team and not team_id:
            team_id = str(guessed_team.id)
    if request.method == 'POST':
        form_action = (request.POST.get('form_action') or 'analyze').strip()
        if form_action == 'upload_video':
            video_title = (request.POST.get('video_title') or '').strip() or 'Vídeo rival'
            video_source = (request.POST.get('video_source') or RivalVideo.SOURCE_MANUAL).strip()
            rival_team_id = _parse_int(request.POST.get('video_team_id'))
            video_file = request.FILES.get('video_file')
            rival_team = Team.objects.filter(id=rival_team_id).first() if rival_team_id else None
            if not video_file:
                video_error = 'Selecciona un vídeo para subir.'
            else:
                RivalVideo.objects.create(
                    rival_team=rival_team,
                    title=video_title,
                    video=video_file,
                    source=video_source if video_source in {c[0] for c in RivalVideo.SOURCE_CHOICES} else RivalVideo.SOURCE_MANUAL,
                    notes=(request.POST.get('video_notes') or '').strip(),
                )
                video_message = 'Vídeo subido correctamente.'
        elif form_action == 'delete_video':
            video_id = _parse_int(request.POST.get('video_id'))
            entry = RivalVideo.objects.filter(id=video_id).first()
            if entry:
                try:
                    if entry.video:
                        entry.video.delete(save=False)
                except Exception:
                    pass
                entry.delete()
                video_message = 'Vídeo eliminado.'
        elif form_action == 'save_manual_report':
            selected_team_id = _parse_int(request.POST.get('team_id'))
            selected_team = Team.objects.filter(id=selected_team_id).first() if selected_team_id else None
            rival_name_input = (
                (request.POST.get('manual_rival_name') or '').strip()
                or (selected_team.name if selected_team else '')
                or (home_rival_name or '').strip()
            )
            if not primary_team:
                manual_report_error = 'No hay equipo principal configurado.'
            elif not rival_name_input:
                manual_report_error = 'Indica el rival para guardar el informe.'
            else:
                status_value = (request.POST.get('manual_status') or RivalAnalysisReport.STATUS_DRAFT).strip()
                if status_value not in {choice[0] for choice in RivalAnalysisReport.STATUS_CHOICES}:
                    status_value = RivalAnalysisReport.STATUS_DRAFT
                confidence = _parse_int(request.POST.get('manual_confidence')) or 3
                confidence = max(1, min(confidence, 5))
                RivalAnalysisReport.objects.create(
                    team=primary_team,
                    rival_team=selected_team,
                    rival_name=rival_name_input,
                    report_title=(request.POST.get('manual_report_title') or '').strip(),
                    match_round=(request.POST.get('manual_match_round') or '').strip(),
                    match_date=(request.POST.get('manual_match_date') or '').strip(),
                    match_location=(request.POST.get('manual_match_location') or '').strip(),
                    tactical_system=(request.POST.get('manual_tactical_system') or '').strip(),
                    attacking_patterns=(request.POST.get('manual_attacking_patterns') or '').strip(),
                    defensive_patterns=(request.POST.get('manual_defensive_patterns') or '').strip(),
                    transitions=(request.POST.get('manual_transitions') or '').strip(),
                    set_pieces_for=(request.POST.get('manual_set_pieces_for') or '').strip(),
                    set_pieces_against=(request.POST.get('manual_set_pieces_against') or '').strip(),
                    key_players=(request.POST.get('manual_key_players') or '').strip(),
                    weaknesses=(request.POST.get('manual_weaknesses') or '').strip(),
                    opportunities=(request.POST.get('manual_opportunities') or '').strip(),
                    match_plan=(request.POST.get('manual_match_plan') or '').strip(),
                    individual_tasks=(request.POST.get('manual_individual_tasks') or '').strip(),
                    alert_notes=(request.POST.get('manual_alert_notes') or '').strip(),
                    confidence_level=confidence,
                    status=status_value,
                    created_by=(request.user.get_username() if request.user.is_authenticated else ''),
                )
                manual_report_message = 'Informe manual guardado correctamente.'
        team_url = (request.POST.get('team_url') or '').strip()
        team_url = (request.POST.get('team_url') or '').strip()
        team_id = (request.POST.get('team_id') or '').strip()
        raw_text = (request.POST.get('raw_text') or '').strip()
        team = None
        if team_id:
            team = Team.objects.filter(id=team_id).first()
            if team and not team_url:
                team_url = team.preferente_url or ''
        if form_action == 'analyze':
            try:
                if raw_text:
                    roster = parse_preferente_roster(raw_text)
                elif team_url:
                    roster = fetch_preferente_team_roster(team_url)

                probable_eleven = compute_probable_eleven(roster)
                insights = build_rival_insights(roster)
                formation = compute_formation(probable_eleven)
                try:
                    lineup = assign_lineup_slots(probable_eleven, formation)
                except Exception:
                    lineup = []
                    error = 'Plantilla cargada, pero no se ha podido dibujar el 11 probable.'

                if not roster:
                    error = 'No se han encontrado jugadores en la plantilla.'
            except Exception:
                error = 'No se ha podido procesar la plantilla del rival. Revisa URL o el contenido pegado.'
        if team and team_url and team.preferente_url != team_url:
            team.preferente_url = team_url
            team.save(update_fields=['preferente_url'])
    else:
        active_match = get_active_match(primary_team) if primary_team else None
        auto_team = None
        if active_match and primary_team:
            auto_team = (
                active_match.away_team if active_match.home_team == primary_team else active_match.home_team
            )
        if auto_team:
            team_id = str(auto_team.id)
            auto_team_name = auto_team.name
            team_url = (auto_team.preferente_url or '').strip()
            if team_url:
                try:
                    roster = fetch_preferente_team_roster(team_url)
                    probable_eleven = compute_probable_eleven(roster)
                    insights = build_rival_insights(roster)
                    formation = compute_formation(probable_eleven)
                    lineup = assign_lineup_slots(probable_eleven, formation)
                    auto_loaded = True
                    if not roster:
                        error = 'No se han encontrado jugadores en la plantilla.'
                except Exception:
                    error = (
                        f'Rival detectado automáticamente ({auto_team.name}), '
                        'pero no se ha podido cargar su plantilla.'
                    )
            else:
                error = (
                    f'Rival detectado automáticamente ({auto_team.name}), '
                    'pero no tiene URL de La Preferente guardada.'
                )
    selected_team = Team.objects.filter(id=_parse_int(team_id)).first() if team_id else None
    universe = load_universo_snapshot() or {}
    standings = universe.get('standings') or []
    team_lookup = _build_universo_standings_lookup(universe)
    rival_name = selected_team.name if selected_team else (home_rival_name or auto_team_name)
    rival_full_name, rival_crest_url = _resolve_rival_identity(rival_name, preferred_opponent=preferred_opponent)
    rival_meta = team_lookup.get(_normalize_team_lookup_key(rival_name), {})
    extracted = {
        'source_priority': 'Universo RFAF > RFAF > La Preferente',
        'rival_name': rival_full_name,
        'rival_crest_url': _absolute_universo_url(rival_crest_url or rival_meta.get('crest_url')),
        'standings_count': len(standings),
        'next_match_round': preferred_next.get('round') if isinstance(preferred_next, dict) else '',
        'next_match_date': preferred_next.get('date') if isinstance(preferred_next, dict) else '',
        'next_match_time': preferred_next.get('time') if isinstance(preferred_next, dict) else '',
        'next_match_location': preferred_next.get('location') if isinstance(preferred_next, dict) else '',
        'preferente_url': selected_team.preferente_url if selected_team else '',
    }
    manual_report_latest = None
    manual_reports = []
    if primary_team:
        manual_reports_qs = RivalAnalysisReport.objects.filter(team=primary_team)
        if selected_team:
            manual_reports_qs = manual_reports_qs.filter(rival_team=selected_team)
        elif rival_name:
            manual_reports_qs = manual_reports_qs.filter(rival_name__icontains=rival_name[:18])
        manual_reports = list(manual_reports_qs.order_by('-updated_at', '-id')[:12])
        manual_report_latest = manual_reports[0] if manual_reports else None

    manual_initial = {
        'rival_name': rival_full_name or (selected_team.name if selected_team else ''),
        'report_title': '',
        'match_round': extracted.get('next_match_round') or '',
        'match_date': extracted.get('next_match_date') or '',
        'match_location': extracted.get('next_match_location') or '',
        'tactical_system': '',
        'attacking_patterns': '',
        'defensive_patterns': '',
        'transitions': '',
        'set_pieces_for': '',
        'set_pieces_against': '',
        'key_players': '',
        'weaknesses': '',
        'opportunities': '',
        'match_plan': '',
        'individual_tasks': '',
        'alert_notes': '',
        'confidence': 3,
        'status': RivalAnalysisReport.STATUS_DRAFT,
    }
    if manual_report_latest:
        manual_initial.update(
            {
                'rival_name': manual_report_latest.rival_name,
                'report_title': manual_report_latest.report_title,
                'match_round': manual_report_latest.match_round,
                'match_date': manual_report_latest.match_date,
                'match_location': manual_report_latest.match_location,
                'tactical_system': manual_report_latest.tactical_system,
                'attacking_patterns': manual_report_latest.attacking_patterns,
                'defensive_patterns': manual_report_latest.defensive_patterns,
                'transitions': manual_report_latest.transitions,
                'set_pieces_for': manual_report_latest.set_pieces_for,
                'set_pieces_against': manual_report_latest.set_pieces_against,
                'key_players': manual_report_latest.key_players,
                'weaknesses': manual_report_latest.weaknesses,
                'opportunities': manual_report_latest.opportunities,
                'match_plan': manual_report_latest.match_plan,
                'individual_tasks': manual_report_latest.individual_tasks,
                'alert_notes': manual_report_latest.alert_notes,
                'confidence': manual_report_latest.confidence_level,
                'status': manual_report_latest.status,
            }
        )
    rival_videos = list(
        RivalVideo.objects.filter(rival_team=selected_team).order_by('-created_at')
    ) if selected_team else list(RivalVideo.objects.filter(rival_team__isnull=True).order_by('-created_at')[:12])

    return render(
        request,
        'football/coach_analysis.html',
        {
            'section_title': 'Análisis rival',
            'description': 'Indicadores y notas tácticas para el próximo rival.',
            'team_url': team_url,
            'team_id': team_id,
            'teams': Team.objects.order_by('name'),
            'raw_text': raw_text,
            'roster': roster,
            'probable_eleven': probable_eleven,
            'lineup': lineup,
            'insights': insights,
            'formation': formation,
            'error': error,
            'auto_loaded': auto_loaded,
            'auto_team_name': auto_team_name,
            'rival_videos': rival_videos,
            'video_error': video_error,
            'video_message': video_message,
            'video_sources': RivalVideo.SOURCE_CHOICES,
            'home_rival_name': home_rival_name,
            'extracted': extracted,
            'manual_initial': manual_initial,
            'manual_reports': manual_reports,
            'manual_report_message': manual_report_message,
            'manual_report_error': manual_report_error,
            'manual_report_status_choices': RivalAnalysisReport.STATUS_CHOICES,
        },
    )


@login_required
def manual_player_stats_page(request):
    if not _is_admin_user(request.user):
        return HttpResponse('Solo administradores pueden editar estadísticas manuales.', status=403)
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)

    season = None
    if primary_team.group and primary_team.group.season:
        season = primary_team.group.season
    if season is None:
        season = Season.objects.filter(is_current=True).order_by('-start_date', '-id').first()
    if season is None:
        return JsonResponse({'error': 'No hay temporada activa para guardar estadísticas'}, status=400)

    players = list(Player.objects.filter(team=primary_team).order_by('name'))
    current_overrides = get_manual_player_base_overrides(primary_team, season)

    if request.method == 'POST':
        with transaction.atomic():
            for player in players:
                overrides = {
                    'manual_pj': _parse_int(request.POST.get(f'pj_{player.id}')) or 0,
                    'manual_pt': _parse_int(request.POST.get(f'pt_{player.id}')) or 0,
                    'manual_minutes': _parse_int(request.POST.get(f'minutes_{player.id}')) or 0,
                    'manual_goals': _parse_int(request.POST.get(f'goals_{player.id}')) or 0,
                    'manual_yellow_cards': _parse_int(request.POST.get(f'yellow_{player.id}')) or 0,
                    'manual_red_cards': _parse_int(request.POST.get(f'red_{player.id}')) or 0,
                }
                for stat_name, stat_value in overrides.items():
                    PlayerStatistic.objects.update_or_create(
                        player=player,
                        season=season,
                        match=None,
                        name=stat_name,
                        context='manual-base',
                        defaults={'value': stat_value},
                    )
        current_overrides = get_manual_player_base_overrides(primary_team, season)
        message = 'Estadísticas manuales guardadas.'
    else:
        message = ''

    rows = []
    roster_cache = get_roster_stats_cache()
    for player in players:
        roster_entry = find_roster_entry(player.name, roster_cache) or {}
        manual = current_overrides.get(player.id, {})
        rows.append(
            {
                'player': player,
                'pj': manual.get('pj', roster_entry.get('pj', 0)),
                'pt': manual.get('pt', roster_entry.get('pt', 0)),
                'minutes': manual.get('minutes', roster_entry.get('minutes', 0)),
                'goals': manual.get('goals', roster_entry.get('goals', 0)),
                'yellow_cards': manual.get('yellow_cards', roster_entry.get('yellow_cards', 0)),
                'red_cards': manual.get('red_cards', roster_entry.get('red_cards', 0)),
            }
        )

    return render(
        request,
        'football/manual_player_stats.html',
        {
            'team_name': primary_team.name,
            'season_name': season.name,
            'rows': rows,
            'message': message,
        },
    )


def player_detail_page(request, player_id):
    try:
        primary_team = Team.objects.filter(is_primary=True).first()
        if not primary_team:
            return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
        player = Player.objects.filter(id=player_id, team=primary_team).first()
        if not player:
            return JsonResponse({'error': 'Jugador no encontrado'}, status=404)
        active_match = get_active_match(primary_team)
        current_convocation = get_current_convocation_record(primary_team, match=active_match)
        is_called_up = bool(
            current_convocation
            and current_convocation.players.filter(id=player.id).exists()
        )

        def _parse_date_value(raw_value):
            value = str(raw_value or '').strip()
            if not value:
                return None
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            return None

        def _parse_datetime_value(raw_value):
            value = str(raw_value or '').strip()
            if not value:
                return None
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M'):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            return None

        def _parse_decimal_value(raw_value):
            value = str(raw_value or '').strip().replace(',', '.')
            if not value:
                return None
            try:
                return round(float(value), 2)
            except Exception:
                return None

        def _resolve_season():
            if primary_team.group and primary_team.group.season:
                return primary_team.group.season
            return Season.objects.filter(is_current=True).order_by('-start_date', '-id').first()

        if request.method == 'POST':
            form_action = (request.POST.get('form_action') or 'profile').strip().lower()

            if form_action == 'profile':
                uploaded_photo = request.FILES.get('player_photo')
                number = request.POST.get('number', '').strip()
                injury_name = request.POST.get('injury', '').strip()
                injury_type = request.POST.get('injury_type', '').strip()
                injury_zone = request.POST.get('injury_zone', '').strip()
                injury_side = request.POST.get('injury_side', '').strip()
                injury_notes = request.POST.get('injury_notes', '').strip()
                injury_date = _parse_date_value(request.POST.get('injury_date'))
                injury_return_date = _parse_date_value(request.POST.get('injury_return_date'))
                manual_sanction_active = str(request.POST.get('manual_sanction_active') or '').lower() in {'1', 'true', 'on', 'yes'}
                manual_sanction_reason = request.POST.get('manual_sanction_reason', '').strip()
                manual_sanction_until = _parse_date_value(request.POST.get('manual_sanction_until'))
                injury_record_mode = (request.POST.get('injury_record_mode') or '').strip().lower()
                force_new_injury_record = injury_record_mode in {'new', 'add', 'create'}
                player.number = int(number) if number else None
                player.position = request.POST.get('position', '').strip()
                player.full_name = request.POST.get('full_name', '').strip()
                player.nickname = request.POST.get('nickname', '').strip()
                player.birth_date = _parse_date_value(request.POST.get('birth_date'))
                player.height_cm = _parse_int(request.POST.get('height_cm'))
                player.weight_kg = _parse_decimal_value(request.POST.get('weight_kg_base'))
                player.injury = injury_name
                player.injury_type = injury_type
                player.injury_zone = injury_zone
                player.injury_side = injury_side
                player.injury_date = injury_date
                player.manual_sanction_active = manual_sanction_active
                player.manual_sanction_reason = manual_sanction_reason
                player.manual_sanction_until = manual_sanction_until
                player.save()
                if uploaded_photo:
                    players_dir = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'players'
                    players_dir.mkdir(parents=True, exist_ok=True)
                    output_path = players_dir / f'player-{player.id}.png'
                    try:
                        if Image is not None:
                            with Image.open(uploaded_photo) as image:
                                if image.mode in ('RGBA', 'LA', 'P'):
                                    converted = image.convert('RGBA')
                                    background = Image.new('RGBA', converted.size, (3, 7, 18, 255))
                                    background.alpha_composite(converted)
                                    final_image = background.convert('RGB')
                                else:
                                    final_image = image.convert('RGB')
                                final_image.save(output_path, format='PNG', optimize=True)
                        else:
                            with output_path.open('wb') as destination:
                                for chunk in uploaded_photo.chunks():
                                    destination.write(chunk)
                    except Exception:
                        pass

                active_injury = (
                    PlayerInjuryRecord.objects
                    .filter(player=player, is_active=True)
                    .order_by('-injury_date', '-id')
                    .first()
                )
                if injury_name and injury_date:
                    same_record = None
                    if not force_new_injury_record:
                        same_record = (
                            PlayerInjuryRecord.objects
                            .filter(
                                player=player,
                                injury__iexact=injury_name,
                                injury_date=injury_date,
                            )
                            .order_by('-id')
                            .first()
                        )
                    if same_record:
                        updated_fields = []
                        if injury_type != same_record.injury_type:
                            same_record.injury_type = injury_type
                            updated_fields.append('injury_type')
                        if injury_zone != same_record.injury_zone:
                            same_record.injury_zone = injury_zone
                            updated_fields.append('injury_zone')
                        if injury_side != same_record.injury_side:
                            same_record.injury_side = injury_side
                            updated_fields.append('injury_side')
                        if injury_notes != same_record.notes:
                            same_record.notes = injury_notes
                            updated_fields.append('notes')
                        if injury_return_date != same_record.return_date:
                            same_record.return_date = injury_return_date
                            updated_fields.append('return_date')
                        should_be_active = not bool(injury_return_date)
                        if same_record.is_active != should_be_active:
                            same_record.is_active = should_be_active
                            updated_fields.append('is_active')
                        if updated_fields:
                            same_record.save(update_fields=updated_fields + ['updated_at'])
                    else:
                        PlayerInjuryRecord.objects.create(
                            player=player,
                            injury=injury_name,
                            injury_type=injury_type,
                            injury_zone=injury_zone,
                            injury_side=injury_side,
                            injury_date=injury_date,
                            return_date=injury_return_date,
                            notes=injury_notes,
                            is_active=not bool(injury_return_date),
                        )
                    if active_injury and active_injury.injury.lower() != injury_name.lower():
                        active_injury.is_active = False
                        if not active_injury.return_date:
                            active_injury.return_date = injury_return_date or timezone.localdate()
                            active_injury.save(update_fields=['is_active', 'return_date', 'updated_at'])
                        else:
                            active_injury.save(update_fields=['is_active', 'updated_at'])
                elif active_injury and injury_return_date:
                    active_injury.return_date = injury_return_date
                    active_injury.is_active = False
                    active_injury.save(update_fields=['return_date', 'is_active', 'updated_at'])

                return redirect(f"{reverse('player-detail', args=[player.id])}?tab=general")

            if form_action == 'manual_stats':
                season = _resolve_season()
                if season:
                    manual_values = {
                        'manual_pj': _parse_int(request.POST.get('manual_pj')) or 0,
                        'manual_pt': _parse_int(request.POST.get('manual_pt')) or 0,
                        'manual_minutes': _parse_int(request.POST.get('manual_minutes')) or 0,
                        'manual_goals': _parse_int(request.POST.get('manual_goals')) or 0,
                        'manual_yellow_cards': _parse_int(request.POST.get('manual_yellow_cards')) or 0,
                        'manual_red_cards': _parse_int(request.POST.get('manual_red_cards')) or 0,
                    }
                    with transaction.atomic():
                        for stat_name, stat_value in manual_values.items():
                            PlayerStatistic.objects.update_or_create(
                                player=player,
                                season=season,
                                match=None,
                                name=stat_name,
                                context='manual-base',
                                defaults={'value': stat_value},
                            )
                return redirect(f"{reverse('player-detail', args=[player.id])}?tab=general")

            if form_action == 'physical':
                PlayerPhysicalMetric.objects.create(
                    player=player,
                    recorded_on=_parse_date_value(request.POST.get('recorded_on')) or timezone.localdate(),
                    workload=request.POST.get('workload', '').strip(),
                    rpe=_parse_int(request.POST.get('rpe')),
                    wellness=_parse_int(request.POST.get('wellness')),
                    weight_kg=request.POST.get('weight_kg', '').strip() or None,
                    notes=request.POST.get('physical_notes', '').strip(),
                )
                return redirect(f"{reverse('player-detail', args=[player.id])}?tab=physical")

            if form_action == 'communication':
                message = request.POST.get('message', '').strip()
                if message:
                    PlayerCommunication.objects.create(
                        player=player,
                        match=active_match,
                        category=request.POST.get('category') or PlayerCommunication.CATEGORY_INTERNAL,
                        message=message,
                        scheduled_for=_parse_datetime_value(request.POST.get('scheduled_for')),
                        created_by=(request.user.get_username() if request.user.is_authenticated else ''),
                    )
                return redirect(f"{reverse('player-detail', args=[player.id])}?tab=communication")

        matches = compute_player_dashboard(primary_team)
        detail = next((p for p in matches if p.get('player_id') == player_id), None)
        active_tab = (request.GET.get('tab') or 'general').strip().lower()
        physical_metrics = player.physical_metrics.all()[:20]
        latest_physical_metric = physical_metrics[0] if physical_metrics else None
        communications = player.communications.select_related('match').all()[:20]
        injury_records = player.injury_records.all()[:20]
        latest_injury_record = injury_records[0] if injury_records else None
        has_active_injury = player.id in get_active_injury_player_ids([player.id])
        if not has_active_injury and latest_injury_record:
            has_active_injury = bool(latest_injury_record.is_active)
        has_manual_sanction = is_manual_sanction_active(player)
        player_photo_url = resolve_player_photo_url(request, player)
        fines_summary = {
            'registered_fines': 0,
            'registered_total': 0,
            'manual_sanctions': 1 if has_manual_sanction else 0,
            'total': 0,
        }
        fines_records = []
        player_fines = list(player.fines.all()[:80])
        reason_labels = dict(PlayerFine.REASON_CHOICES)
        for fine in player_fines:
            fines_summary['registered_fines'] += 1
            fines_summary['registered_total'] += int(fine.amount or 0)
            fines_records.append(
                {
                    'type': reason_labels.get(fine.reason, fine.reason),
                    'amount': int(fine.amount or 0),
                    'date': fine.created_at.strftime('%d/%m/%Y'),
                    'detail': fine.note or '-',
                }
            )
        if has_manual_sanction:
            until_label = (
                player.manual_sanction_until.strftime('%d/%m/%Y')
                if player.manual_sanction_until
                else 'Sin fecha fin'
            )
            fines_records.insert(
                0,
                {
                    'type': 'Sanción manual',
                    'amount': 0,
                    'date': until_label,
                    'detail': player.manual_sanction_reason or 'Sanción configurada en ficha',
                }
            )
        fines_summary['total'] = (
            fines_summary['registered_fines']
            + fines_summary['manual_sanctions']
        )

        def _to_int_value(value):
            return _parse_int(value) or 0

        stats_source = detail or {}
        pj = _to_int_value(stats_source.get('pj'))
        pt = _to_int_value(stats_source.get('pt'))
        minutes = _to_int_value(stats_source.get('minutes'))
        goals = _to_int_value(stats_source.get('goals'))
        yellow_cards = _to_int_value(stats_source.get('yellow_cards'))
        red_cards = _to_int_value(stats_source.get('red_cards'))
        second_yellow_cards = _to_int_value(stats_source.get('second_yellow_cards'))
        competition_total_rounds = _to_int_value(stats_source.get('competition_total_rounds')) or get_competition_total_rounds(primary_team)
        participation_pct = (
            round(min((pj / competition_total_rounds) * 100, 100), 1)
            if competition_total_rounds > 0
            else 0
        )
        suplente = max(pj - pt, 0)
        goals_per_match = round((goals / pj), 2) if pj else 0
        max_minutes = pj * 90
        minute_ratio = round((minutes / max_minutes) * 100, 1) if max_minutes else 0
        minute_ratio = max(0, min(minute_ratio, 100))

        standings_rows = _serialize_universo_standings(load_universo_snapshot())
        if not standings_rows and primary_team.group:
            standings_rows = serialize_standings(primary_team.group)
        team_points = 0
        team_rank = 0
        team_key = _normalize_team_lookup_key(primary_team.name)
        for row in standings_rows:
            candidate_key = _normalize_team_lookup_key(row.get('full_name') or row.get('team'))
            if team_key and candidate_key == team_key:
                team_points = _to_int_value(row.get('points'))
                team_rank = _to_int_value(row.get('rank'))
                break
        if not team_points and not team_rank and standings_rows:
            preferred_aliases = ('benagalbon', 'c.d. benagalbon', 'cd benagalbon')
            for row in standings_rows:
                full_name = str(row.get('full_name') or row.get('team') or '').lower()
                if any(alias in full_name for alias in preferred_aliases):
                    team_points = _to_int_value(row.get('points'))
                    team_rank = _to_int_value(row.get('rank'))
                    break

        season_label = ''
        division_label = ''
        if primary_team.group:
            division_label = primary_team.group.name or ''
            season = primary_team.group.season
            if season:
                if season.start_date and season.end_date:
                    season_label = f'{season.start_date.year}-{season.end_date.year}'
                else:
                    season_label = season.name or ''
        if not season_label:
            season_label = 'Temporada actual'

        general_kpis = [
            {'label': 'Partidos', 'value': pj, 'pct': 100 if pj else 0},
            {'label': 'Titular', 'value': pt, 'pct': round((pt / pj) * 100, 1) if pj else 0},
            {'label': 'Suplente', 'value': suplente, 'pct': round((suplente / pj) * 100, 1) if pj else 0},
            {'label': 'Minutos', 'value': minutes, 'pct': minute_ratio},
            {'label': 'Total goles', 'value': goals, 'pct': round((goals / pj) * 100, 1) if pj else 0},
            {'label': 'Media goles/partido', 'value': goals_per_match, 'pct': round(min(goals_per_match * 100, 100), 1)},
            {'label': '% participación', 'value': participation_pct, 'pct': participation_pct},
            {'label': 'Amarillas', 'value': yellow_cards, 'pct': round(min(yellow_cards * 15, 100), 1)},
            {'label': 'Rojas', 'value': red_cards, 'pct': round(min(red_cards * 30, 100), 1)},
            {'label': 'Doble amarilla', 'value': second_yellow_cards, 'pct': round(min(second_yellow_cards * 30, 100), 1)},
        ]

        return render(
            request,
            'football/player_detail.html',
            {
                'player': player,
                'stats': detail or {},
                'active_tab': active_tab,
                'physical_metrics': physical_metrics,
                'latest_physical_metric': latest_physical_metric,
                'communications': communications,
                'injury_records': injury_records,
                'latest_injury_record': latest_injury_record,
                'has_active_injury': has_active_injury,
                'has_manual_sanction': has_manual_sanction,
                'is_called_up': is_called_up,
                'current_convocation': current_convocation,
                'active_match': active_match,
                'player_photo_url': player_photo_url,
                'general_kpis': general_kpis,
                'team_points': team_points,
                'team_rank': team_rank,
                'season_label': season_label,
                'division_label': division_label,
                'fines_summary': fines_summary,
                'fines_records': fines_records,
            },
        )
    except Exception as e:
        import logging
        logging.exception(f"Error en player_detail_page para player_id={player_id}")
        return HttpResponse(f"Error interno: {e}", status=500)




def player_pdf(request, player_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    player = Player.objects.filter(id=player_id, team=primary_team).first()
    if not player:
        raise Http404('Jugador no encontrado')
    matches = compute_player_dashboard(primary_team)
    detail = next((p for p in matches if p.get('player_id') == player_id), None)
    if not detail:
        raise Http404('Sin datos para generar el PDF')
    html = render_to_string(
        'football/player_pdf.html',
        {'player': player, 'stats': detail},
        request=request,
    )
    filename = slugify(player.name or 'jugador')
    return _build_pdf_response_or_html_fallback(request, html, filename)


def player_presentation(request, player_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    player = Player.objects.filter(id=player_id, team=primary_team).first()
    if not player:
        raise Http404('Jugador no encontrado')
    matches = compute_player_dashboard(primary_team)
    detail = next((p for p in matches if p.get('player_id') == player_id), None)
    if not detail:
        raise Http404('Sin datos para generar la presentación')
    return render(
        request,
        'football/player_pdf.html',
        {'player': player, 'stats': detail},
    )


def match_stats_page(request, match_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    match = _team_match_queryset(primary_team).filter(id=match_id).first()
    if not match:
        raise Http404('Partido no encontrado')
    opponent = match.away_team if match.home_team == primary_team else match.home_team
    payload = {
        'round': match.round or 'Partido sin jornada',
        'date': match.date.strftime('%d/%m/%Y') if match.date else 'Fecha por definir',
        'location': match.location or 'Campo por confirmar',
        'opponent': opponent.name if opponent else 'Rival desconocido',
        'home': match.home_team == primary_team,
    }
    team_metrics = compute_team_metrics_for_match(match)
    player_cards = compute_player_cards_for_match(match, primary_team)
    return render(
        request,
        'football/match_stats.html',
        {
            'match': payload,
            'team_metrics': team_metrics,
            'player_cards': player_cards,
        },
    )


def player_match_stats_page(request, player_id, match_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    player = Player.objects.filter(id=player_id, team=primary_team).first()
    if not player:
        raise Http404('Jugador no encontrado')
    match = _team_match_queryset(primary_team).filter(id=match_id).first()
    if not match:
        raise Http404('Partido no encontrado')
    opponent = match.away_team if match.home_team == primary_team else match.home_team
    events = confirmed_events_queryset().filter(match=match, player=player).order_by('minute')
    stats = {
        'player_id': player.id,
        'name': player.name,
        'number': player.number,
        'position': player.position,
        'total_actions': 0,
        'successes': 0,
        'goals': 0,
        'assists': 0,
        'yellow_cards': 0,
        'red_cards': 0,
        'zone_counts': {key: 0 for key in FIELD_ZONE_KEYS},
        'tercio_counts': {label: 0 for label in STANDARD_TERCIO_LABELS},
        'tercio_totals': {label: 0 for label in STANDARD_TERCIO_LABELS},
        'duels_total': 0,
        'duels_won': 0,
        'shot_attempts': 0,
        'shots_on_target': 0,
        'pass_attempts': 0,
        'passes_completed': 0,
    }
    for event in events:
        stats['total_actions'] += 1
        if result_is_success(event.result):
            stats['successes'] += 1
        if is_goal_event(event.event_type, event.result, event.observation):
            stats['goals'] += 1
        if is_assist_event(event.event_type, event.result, event.observation):
            stats['assists'] += 1
        if is_yellow_card_event(event.event_type, event.result, event.zone):
            stats['yellow_cards'] += 1
        if is_red_card_event(event.event_type, event.result, event.zone):
            stats['red_cards'] += 1
        duel_event = classify_duel_event(event.event_type, event.result, event.observation, event.zone)
        if duel_event.get('is_duel'):
            stats['duels_total'] += 1
            if duel_event.get('won'):
                stats['duels_won'] += 1
        zone_label = map_zone_label((event.zone or '').strip())
        if zone_label:
            stats['zone_counts'][zone_label] += 1
        tercio_raw = (event.tercio or '').strip()
        if tercio_raw:
            mapped = map_tercio(tercio_raw)
            if mapped:
                stats['tercio_counts'][mapped] += 1
                stats['tercio_totals'][mapped] += 1
        shot_event = contains_keyword(event.event_type, SHOT_KEYWORDS) or contains_keyword(event.observation, SHOT_KEYWORDS)
        save_event = is_goalkeeper_save_event(event.event_type, event.result, event.observation)
        if shot_event or save_event:
            stats['shot_attempts'] += 1
            if save_event or result_is_success(event.result):
                stats['shots_on_target'] += 1
        if contains_keyword(event.event_type, PASS_KEYWORDS) or contains_keyword(event.observation, PASS_KEYWORDS):
            stats['pass_attempts'] += 1
            if result_is_success(event.result):
                stats['passes_completed'] += 1
    total_tercios = sum(stats['tercio_totals'].values())
    stats['success_rate'] = round(
        (stats['successes'] / stats['total_actions']) * 100, 1
    ) if stats['total_actions'] else 0
    stats['duel_rate'] = round(
        (stats['duels_won'] / stats['duels_total']) * 100, 1
    ) if stats['duels_total'] else 0
    stats['zone_heatmap'] = sorted(
        [
            {'zone': zone, 'count': count}
            for zone, count in stats['zone_counts'].items()
            if count > 0
        ],
        key=lambda entry: entry['count'],
        reverse=True,
    )[:5]
    stats['tercio_heatmap'] = sorted(
        [{'tercio': tercio, 'count': count} for tercio, count in stats['tercio_counts'].items()],
        key=lambda entry: entry['count'],
        reverse=True,
    )[:5]
    stats['tercio_summary'] = [
        {
            'label': tercio_label,
            'count': stats['tercio_totals'].get(tercio_label, 0),
            'pct': round(
                (stats['tercio_totals'].get(tercio_label, 0) / total_tercios) * 100, 1
            )
            if total_tercios
            else 0,
        }
        for tercio_label in ('Ataque', 'Construcción', 'Defensa')
    ]
    stats['shots'] = {
        'attempts': stats['shot_attempts'],
        'on_target': stats['shots_on_target'],
        'accuracy': round((stats['shots_on_target'] / stats['shot_attempts']) * 100, 1)
        if stats['shot_attempts']
        else 0,
    }
    stats['passes'] = {
        'attempts': stats['pass_attempts'],
        'completed': stats['passes_completed'],
        'accuracy': round((stats['passes_completed'] / stats['pass_attempts']) * 100, 1)
        if stats['pass_attempts']
        else 0,
    }
    total_zone_actions = max(1, int(stats.get('total_actions') or 0))
    stats['field_zones'] = [
        {
            **zone,
            'count': stats['zone_counts'].get(zone['key'], 0),
            'pct': round((stats['zone_counts'].get(zone['key'], 0) / total_zone_actions) * 100, 1)
            if stats.get('total_actions')
            else 0,
        }
        for zone in FIELD_ZONES
    ]
    match_payload = {
        'round': match.round or 'Partido sin jornada',
        'date': match.date.strftime('%d/%m/%Y') if match.date else 'Fecha por definir',
        'location': match.location or 'Campo por confirmar',
        'opponent': opponent.name if opponent else 'Rival desconocido',
        'home': match.home_team == primary_team,
    }
    return render(
        request,
        'football/player_detail.html',
        {
            'player': player,
            'stats': stats,
            'match_context': match_payload,
        },
    )


@authenticated_write
@require_POST
def refresh_scraping(request):
    if not cache.add(SCRAPE_LOCK_KEY, "1", timeout=SCRAPE_LOCK_TIMEOUT_SECONDS):
        return JsonResponse(
            {'status': 'error', 'message': 'Ya hay una actualización en curso. Inténtalo en unos minutos.'},
            status=429,
        )
    primary_team = Team.objects.filter(is_primary=True).first()
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=str(MANAGE_PY_DIR),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or 'Error desconocido al ejecutar el script.')
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)
    finally:
        cache.delete(SCRAPE_LOCK_KEY)
    # Si trabajamos con Universo RFAF, evitamos depender de La Preferente en este flujo.
    preferente_refresh_enabled = str(
        os.getenv('PREFERENTE_ROSTER_REFRESH_ENABLED', '0')
    ).strip().lower() in {'1', 'true', 'yes', 'on'}
    if preferente_refresh_enabled:
        roster_ok, roster_message = refresh_primary_roster_cache(primary_team, force=True)
        roster_status = 'y plantilla actualizada' if roster_ok else f'plantilla no actualizada ({roster_message})'
    else:
        roster_status = 'plantilla gestionada por Universo RFAF'
    if primary_team:
        cache.delete(_dashboard_cache_key(primary_team.id))
    return JsonResponse(
        {'status': 'success', 'message': f'Clasificación actualizada desde RFAF, {roster_status}.'}
    )


def serialize_standings(group):
    standings = TeamStanding.objects.filter(group=group)
    current_meta = standings.aggregate(total=Count('id'), latest=Max('last_updated'))

    # Si hay grupos duplicados para misma temporada/nombre, priorizar el más reciente.
    sibling_group = (
        TeamStanding.objects.filter(
            group__season=group.season,
            group__name__iexact=group.name,
        )
        .values('group_id')
        .annotate(total=Count('id'), latest=Max('last_updated'))
        .order_by('-latest', '-total')
        .first()
    )
    if sibling_group:
        sibling_is_better = (
            current_meta['total'] == 0
            or (
                sibling_group['group_id'] != group.id
                and sibling_group['latest']
                and (
                    not current_meta['latest']
                    or sibling_group['latest'] > current_meta['latest']
                )
            )
        )
        if sibling_is_better:
            standings = TeamStanding.objects.filter(group_id=sibling_group['group_id'])

    standings = standings.order_by('position')
    if not standings.exists():
        fallback = TeamStanding.objects.filter(group__slug__icontains='grupo-2').order_by('position')
        if fallback.exists():
            standings = fallback
    return [
        {
            'rank': standing.position,
            'team': standing.team.name.strip().upper(),
            'played': standing.played,
            'wins': standing.wins,
            'draws': standing.draws,
            'losses': standing.losses,
            'goals_for': standing.goals_for,
            'goals_against': standing.goals_against,
            'goal_difference': standing.goal_difference,
            'points': standing.points,
        }
        for standing in standings
    ]


def get_next_match(primary_team, group):
    def _pick_undated_next(queryset):
        candidates = list(queryset.filter(date__isnull=True))
        if not candidates:
            return None
        candidates.sort(
            key=lambda match: (
                extract_round_number(match.round or '') or -1,
                match.id or 0,
            ),
            reverse=True,
        )
        return candidates[0]

    def _fetch_next_from_rfaf():
        try:
            from scripts.import_from_rfef import (
                extract_next_jornada,
                extract_next_match_from_classification,
                fetch_html,
                fetch_schedule,
            )
            html = fetch_html()
            payload = extract_next_match_from_classification(html)
            if not payload:
                next_jornada = extract_next_jornada(html)
                payload = fetch_schedule(next_jornada) if next_jornada else None
            if not isinstance(payload, dict):
                return None
            if (payload.get('status') or '').lower() != 'next':
                return None
            date_raw = payload.get('date')
            if date_raw:
                try:
                    if datetime.strptime(str(date_raw), '%Y-%m-%d').date() < timezone.localdate():
                        return None
                except ValueError:
                    return None
            # Refresh file cache so subsequent requests don't depend on network.
            try:
                NEXT_MATCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
                with NEXT_MATCH_CACHE.open('w', encoding='utf-8') as handle:
                    json.dump(payload, handle)
            except Exception:
                pass
            return normalize_next_match_payload(payload)
        except Exception:
            return None

    today = timezone.localdate()
    all_team_matches_qs = (
        Match.objects.filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .select_related('home_team', 'away_team')
    )
    scoped_qs = all_team_matches_qs.filter(group=group) if group else all_team_matches_qs

    rfaf_next = _fetch_next_from_rfaf()
    if rfaf_next:
        return rfaf_next

    cached_next = load_cached_next_match()
    if cached_next and (cached_next.get('status') or '').lower() == 'next':
        return normalize_next_match_payload(cached_next)

    upcoming = scoped_qs.filter(date__gte=today).order_by('date').first()
    if not upcoming:
        upcoming = all_team_matches_qs.filter(date__gte=today).order_by('date').first()
    if upcoming:
        return build_match_payload(upcoming, primary_team, status='next')

    undated_next = _pick_undated_next(scoped_qs)
    if not undated_next:
        undated_next = _pick_undated_next(all_team_matches_qs)
    if undated_next:
        return build_match_payload(undated_next, primary_team, status='next')

    latest = scoped_qs.exclude(date__isnull=True).order_by('-date').first()
    if not latest:
        latest = all_team_matches_qs.exclude(date__isnull=True).order_by('-date').first()
    if not latest:
        latest = scoped_qs.order_by('-id').first()
    if not latest:
        latest = all_team_matches_qs.order_by('-id').first()
    if not latest:
        return None

    return build_match_payload(latest, primary_team, status='latest')


def _team_match_queryset(primary_team):
    if not primary_team:
        return Match.objects.none()
    direct_filter = Q(home_team=primary_team) | Q(away_team=primary_team)
    team_signature = _team_name_signature(primary_team.name)
    if not team_signature:
        return Match.objects.filter(direct_filter).select_related('home_team', 'away_team')

    # Some imports may create a duplicated team entry for Benagalbón (name variants),
    # leaving matches linked to that alias instead of the canonical `is_primary` team.
    alias_ids = []
    for candidate in Team.objects.exclude(id=primary_team.id).only('id', 'name'):
        if _team_name_signature(candidate.name) == team_signature:
            alias_ids.append(candidate.id)
    if alias_ids:
        direct_filter = direct_filter | Q(home_team_id__in=alias_ids) | Q(away_team_id__in=alias_ids)
    return Match.objects.filter(direct_filter).select_related('home_team', 'away_team').distinct()


def get_active_match(primary_team):
    qs = _team_match_queryset(primary_team)
    if not qs.exists():
        return None
    today = timezone.localdate()
    upcoming = qs.filter(date__gte=today).order_by('date').first()
    if upcoming:
        return upcoming
    undated_next = list(qs.filter(date__isnull=True))
    if undated_next:
        undated_next.sort(
            key=lambda match: (
                extract_round_number(match.round or '') or -1,
                match.id or 0,
            ),
            reverse=True,
        )
        return undated_next[0]
    latest = qs.exclude(date__isnull=True).order_by('-date').first()
    if latest:
        return latest
    return qs.order_by('-id').first()


def get_requested_match(request, primary_team):
    if not primary_team:
        return None
    raw_match_id = request.GET.get('match_id') or request.POST.get('match_id')
    match_id = _parse_int(raw_match_id)
    if not match_id:
        return None
    return _team_match_queryset(primary_team).filter(id=match_id).first()


def get_latest_pizarra_match(primary_team):
    if not primary_team:
        return None
    return (
        _team_match_queryset(primary_team)
        .filter(events__source_file='registro-acciones', events__system='touch-field-final')
        .annotate(last_event_at=Max('events__created_at'))
        .order_by('-last_event_at', '-id')
        .first()
    )


def _parse_match_date_from_ui(raw_value):
    value = (raw_value or '').strip()
    if not value:
        return None
    date_part = value.split('·', 1)[0].strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_part, fmt).date()
        except ValueError:
            continue
    return None


def _unique_team_slug(base_name):
    base_slug = slugify(base_name) or 'rival'
    slug = base_slug
    suffix = 2
    while Team.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{suffix}'
        suffix += 1
    return slug


def _apply_match_info_overrides(match, primary_team, match_info_payload):
    if not match or not isinstance(match_info_payload, dict):
        return
    changed_fields = []
    round_value = (match_info_payload.get('round') or '').strip()
    location_value = (match_info_payload.get('location') or '').strip()
    datetime_value = (match_info_payload.get('datetime') or '').strip()
    opponent_name = (match_info_payload.get('opponent') or '').strip()

    if round_value != (match.round or ''):
        match.round = round_value
        changed_fields.append('round')
    if location_value != (match.location or ''):
        match.location = location_value
        changed_fields.append('location')

    parsed_date = _parse_match_date_from_ui(datetime_value)
    if parsed_date and parsed_date != match.date:
        match.date = parsed_date
        changed_fields.append('date')

    if opponent_name and normalize_label(opponent_name) != normalize_label(primary_team.name):
        rival_team = Team.objects.filter(name__iexact=opponent_name).first()
        if not rival_team:
            rival_team = Team.objects.create(
                name=opponent_name,
                slug=_unique_team_slug(opponent_name),
                short_name=opponent_name[:60],
                group=match.group or primary_team.group,
            )
        if match.home_team_id == primary_team.id:
            if match.away_team_id != rival_team.id:
                match.away_team = rival_team
                changed_fields.append('away_team')
        elif match.away_team_id == primary_team.id:
            if match.home_team_id != rival_team.id:
                match.home_team = rival_team
                changed_fields.append('home_team')
        else:
            match.home_team = primary_team
            match.away_team = rival_team
            changed_fields.extend(['home_team', 'away_team'])

    if changed_fields:
        match.save(update_fields=list(dict.fromkeys(changed_fields)))


def gather_team_fields_for_group(group):
    if not group:
        return []
    seen = set()
    fields = []
    matches = (
        Match.objects.filter(group=group, home_team__isnull=False)
        .exclude(location__isnull=True)
        .exclude(location__exact='')
        .select_related('home_team')
        .order_by('home_team__name', '-date')
    )
    for match in matches:
        team = match.home_team
        if not team or team.id in seen:
            continue
        seen.add(team.id)
        fields.append(
            {
                'team_slug': team.slug,
                'team_name': team.name,
                'location': match.location.strip(),
            }
        )
    return fields


def build_match_payload(match, primary_team, status):
    opponent = match.away_team if match.home_team == primary_team else match.home_team
    return normalize_next_match_payload({
        'round': match.round,
        'date': match.date.isoformat() if match.date else None,
        'location': match.location,
        'opponent': {
            'name': opponent.name if opponent else 'Rival desconocido',
            'full_name': opponent.name if opponent else 'Rival desconocido',
            'crest_url': '',
            'team_code': '',
        },
        'home': match.home_team == primary_team,
        'status': status,
    })


def confirmed_events_queryset():
    return MatchEvent.objects.exclude(system='touch-field')


def preferred_event_source_by_match(primary_team):
    """
    Choose one authoritative source per match to avoid cross-source double counting.
    Priority:
    1) Any `registro-acciones` events for that match.
    2) Otherwise, most frequent non-empty source_file.
    """
    if not primary_team:
        return {}
    team_events = confirmed_events_queryset().filter(player__team=primary_team)
    preferred = {}
    registro_match_ids = set(
        team_events.filter(source_file='registro-acciones')
        .values_list('match_id', flat=True)
        .distinct()
    )
    for match_id in registro_match_ids:
        preferred[match_id] = 'registro-acciones'

    fallback_rows = (
        team_events.exclude(source_file__isnull=True)
        .exclude(source_file__exact='')
        .values('match_id', 'source_file')
        .annotate(c=Count('id'))
        .order_by('match_id', '-c', 'source_file')
    )
    seen = set(preferred.keys())
    for row in fallback_rows:
        match_id = row['match_id']
        if match_id in seen:
            continue
        preferred[match_id] = row['source_file']
        seen.add(match_id)
    return preferred


def _normalize_excel_header(value):
    if not value:
        return ''
    return ''.join(ch.lower() for ch in str(value).strip() if ch.isalnum())


def append_events_to_bd_eventos(match, primary_team, events):
    if not events:
        return 0
    if os.getenv('WRITE_BD_EVENTOS_EXCEL', 'false').lower() != 'true':
        return 0
    path = Path(settings.BASE_DIR) / 'data' / 'excel' / 'BDT PARTIDOS BENABALBON.xlsm'
    if not path.exists():
        raise FileNotFoundError('No se encuentra el Excel de BD_EVENTOS.')
    try:
        from openpyxl import load_workbook
    except Exception as exc:
        raise RuntimeError('No se pudo cargar openpyxl para escribir BD_EVENTOS.') from exc
    workbook = load_workbook(path, keep_vba=True)
    if 'BD_EVENTOS' not in workbook.sheetnames:
        raise RuntimeError('La hoja BD_EVENTOS no existe en el Excel.')
    sheet = workbook['BD_EVENTOS']
    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        raise RuntimeError('La hoja BD_EVENTOS no tiene cabecera.')
    headers = [_normalize_excel_header(cell) for cell in header_row]
    header_index = {key: idx for idx, key in enumerate(headers) if key}
    opponent = match.away_team if match.home_team == primary_team else match.home_team
    match_date = match.date or timezone.localdate()
    match_round = match.round or f'Partido {match.id}'
    match_location = match.location or ''
    rival_name = opponent.name if opponent else 'Rival desconocido'
    rows_written = 0
    for event in events:
        row_payload = {
            'partidoid': match.id,
            'fecha': match_date,
            'rival': rival_name,
            'jornada': match_round,
            'campo': match_location,
            'sistema': event.system or 'touch-field-final',
            'minuto': event.minute,
            'jugador': event.player.name if event.player else '',
            'evento': event.event_type,
            'resultadoaccion': event.result,
            'zona': event.zone,
            'tercio': event.tercio,
            'observacion': event.observation,
        }
        row_values = [''] * len(headers)
        for key, value in row_payload.items():
            index = header_index.get(key)
            if index is not None:
                row_values[index] = value
        sheet.append(row_values)
        rows_written += 1
    workbook.save(path)
    return rows_written


def compute_team_metrics(primary_team):
    events = confirmed_events_queryset().filter(
        Q(match__home_team=primary_team) | Q(match__away_team=primary_team)
    )
    total_events = events.count()
    event_counter = Counter(events.values_list('event_type', flat=True))
    result_counter = Counter(events.values_list('result', flat=True))

    top_events = [{'event': etype, 'count': count} for etype, count in event_counter.most_common(5)]
    top_results = [{'result': result, 'count': count} for result, count in result_counter.most_common(5)]

    return {
        'total_events': total_events,
        'top_event_types': top_events,
        'top_results': top_results,
    }


def compute_team_metrics_for_match(match):
    events = confirmed_events_queryset().filter(match=match)
    total_events = events.count()
    event_counter = Counter(events.values_list('event_type', flat=True))
    result_counter = Counter(events.values_list('result', flat=True))
    top_events = [{'event': etype, 'count': count} for etype, count in event_counter.most_common(6)]
    top_results = [{'result': result, 'count': count} for result, count in result_counter.most_common(6)]
    return {
        'total_events': total_events,
        'top_event_types': top_events,
        'top_results': top_results,
    }


def _event_signature(event):
    def canon(value):
        text = ' '.join(str(value or '').split())
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        return text.lower().strip()

    # "Acción realizada" for dashboard cards:
    # keep one action per player/match/minute/type.
    # If minute is missing, retain more fields to avoid over-collapsing.
    minute = event.minute
    action_type = canon(event.event_type)
    if minute is not None:
        return (
            event.match_id,
            event.player_id,
            minute,
            action_type,
        )
    return (
        event.match_id,
        event.player_id,
        minute,
        action_type,
        canon(event.result),
        canon(event.zone),
        canon(event.tercio),
        canon(event.observation),
    )


def compute_player_cards_for_match(match, primary_team, source_file=None):
    events = confirmed_events_queryset().filter(match=match, player__team=primary_team)
    if source_file:
        events = events.filter(source_file=source_file)
    else:
        preferred_sources = preferred_event_source_by_match(primary_team)
        preferred_source = preferred_sources.get(match.id)
        if preferred_source:
            events = events.filter(source_file=preferred_source)
    rows = events.select_related('player').order_by('id')
    seen_signatures = set()
    per_player = {}
    for event in rows:
        signature = _event_signature(event)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        player = event.player
        if not player:
            continue
        photo_path = resolve_player_photo_static_path(player)
        data = per_player.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number or '--',
                'photo_url': static(photo_path) if photo_path else '',
                'actions': 0,
                'successes': 0,
            },
        )
        data['actions'] += 1
        if (event.result or '').strip().lower() == 'ok':
            data['successes'] += 1
    cards = list(per_player.values())
    for item in cards:
        total_actions = item['actions']
        success = item['successes']
        item['success_rate'] = round((success / total_actions) * 100, 1) if total_actions else 0
    return sorted(cards, key=lambda item: item['actions'], reverse=True)

def compute_player_metrics(primary_team):
    events = confirmed_events_queryset().filter(player__team=primary_team)
    aggregated = (
        events.values('player__id', 'player__name')
        .annotate(
            actions=Count('id'),
            successful=Count('id', filter=Q(result__iexact='OK')),
        )
        .order_by('-actions')
    )

    return [
        {
            'player_id': item['player__id'],
            'player': item['player__name'],
            'actions': item['actions'],
            'successes': item['successful'],
        }
        for item in aggregated
    ]


def compute_player_cards(primary_team):
    if not primary_team:
        return []

    roster_cache = get_roster_stats_cache() or {}
    manual_overrides = get_manual_player_base_overrides(primary_team)
    universo_snapshot = load_universo_snapshot() or {}
    universo_players = universo_snapshot.get('players') if isinstance(universo_snapshot, dict) else []
    universo_map = {}
    universo_by_number = {}
    if isinstance(universo_players, list):
        for item in universo_players:
            if not isinstance(item, dict):
                continue
            team_name = str(item.get('team') or '').strip().lower()
            if team_name and 'benagalbon' not in team_name:
                continue
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            key = normalize_player_name(name)
            universo_map[key] = item
            dorsal_raw = str(item.get('dorsal') or '').strip()
            if dorsal_raw.isdigit():
                universo_by_number[int(dorsal_raw)] = item

    def _to_int(value):
        try:
            return int(str(value).strip())
        except Exception:
            return 0

    def _find_universo_entry(player_obj):
        key = normalize_player_name(player_obj.name)
        direct = universo_map.get(key)
        if direct:
            return direct
        if player_obj.number is not None and player_obj.number in universo_by_number:
            return universo_by_number[player_obj.number]
        target = key.replace('-', '')
        for ukey, entry in universo_map.items():
            compact = ukey.replace('-', '')
            if target in compact or compact in target:
                return entry
        player_tokens = [token for token in target.split('-') if token]
        for ukey, entry in universo_map.items():
            compact_tokens = [token for token in ukey.replace('-', ' ').split() if token]
            overlap = sum(1 for token in player_tokens if token in compact_tokens)
            if overlap >= 2:
                return entry
        return {}

    cards = []
    for player in Player.objects.filter(team=primary_team).order_by('name'):
        photo_path = resolve_player_photo_static_path(player)
        roster_entry = find_roster_entry(player.name, roster_cache) or {}
        manual_entry = manual_overrides.get(player.id, {})
        universo_entry = _find_universo_entry(player) or {}

        pj = (
            manual_entry.get('pj')
            if manual_entry.get('pj') is not None
            else universo_entry.get('pj')
            if universo_entry.get('pj') not in (None, '')
            else roster_entry.get('pj', 0)
        )
        minutes = (
            manual_entry.get('minutes')
            if manual_entry.get('minutes') is not None
            else universo_entry.get('minutes')
            if universo_entry.get('minutes') not in (None, '')
            else roster_entry.get('minutes', 0)
        )
        goals = (
            manual_entry.get('goals')
            if manual_entry.get('goals') is not None
            else universo_entry.get('goals')
            if universo_entry.get('goals') not in (None, '')
            else roster_entry.get('goals', 0)
        )
        yellow_cards = (
            manual_entry.get('yellow_cards')
            if manual_entry.get('yellow_cards') is not None
            else universo_entry.get('yellow_cards')
            if universo_entry.get('yellow_cards') not in (None, '')
            else roster_entry.get('yellow_cards', 0)
        )
        red_cards = (
            manual_entry.get('red_cards')
            if manual_entry.get('red_cards') is not None
            else universo_entry.get('red_cards')
            if universo_entry.get('red_cards') not in (None, '')
            else roster_entry.get('red_cards', 0)
        )

        cards.append(
            {
                'player_id': player.id,
                'name': player.name,
                'photo_url': static(photo_path) if photo_path else '',
                'pj': _to_int(pj),
                'minutes': _to_int(minutes),
                'goals': _to_int(goals),
                'yellow_cards': _to_int(yellow_cards),
                'red_cards': _to_int(red_cards),
            }
        )
    return sorted(cards, key=lambda entry: (-entry['goals'], -entry['pj'], entry['name']))


def get_manual_player_base_overrides(primary_team, season=None):
    if not primary_team:
        return {}
    if season is None:
        if primary_team.group and primary_team.group.season:
            season = primary_team.group.season
        else:
            season = Season.objects.filter(is_current=True).order_by('-start_date', '-id').first()
    if season is None:
        return {}
    stats = (
        PlayerStatistic.objects.filter(
            player__team=primary_team,
            season=season,
            match__isnull=True,
            context='manual-base',
            name__in=[
                'manual_pj',
                'manual_pt',
                'manual_minutes',
                'manual_goals',
                'manual_yellow_cards',
                'manual_red_cards',
            ],
        )
        .select_related('player')
    )
    overrides = {}
    for stat in stats:
        player_data = overrides.setdefault(stat.player_id, {})
        value = int(stat.value or 0)
        if stat.name == 'manual_pj':
            player_data['pj'] = value
        elif stat.name == 'manual_pt':
            player_data['pt'] = value
        elif stat.name == 'manual_minutes':
            player_data['minutes'] = value
        elif stat.name == 'manual_goals':
            player_data['goals'] = value
        elif stat.name == 'manual_yellow_cards':
            player_data['yellow_cards'] = value
        elif stat.name == 'manual_red_cards':
            player_data['red_cards'] = value
    return overrides


def compute_player_dashboard(primary_team):
    player_stats = {}
    competition_total_rounds = get_competition_total_rounds(primary_team)
    roster_players = list(Player.objects.filter(team=primary_team))
    player_by_id = {player.id: player for player in roster_players}
    active_injury_ids = get_active_injury_player_ids([player.id for player in roster_players])
    active_match = get_active_match(primary_team)
    sanctioned_player_ids = get_sanctioned_player_ids_from_previous_round(
        primary_team,
        reference_match=active_match,
    )
    roster_cache = get_roster_stats_cache()
    manual_overrides = get_manual_player_base_overrides(primary_team)
    universo_snapshot = load_universo_snapshot() or {}
    universo_players = universo_snapshot.get('players') if isinstance(universo_snapshot, dict) else []
    universo_map = {}
    universo_by_number = {}
    if isinstance(universo_players, list):
        for item in universo_players:
            if not isinstance(item, dict):
                continue
            team_name = str(item.get('team') or '').strip().lower()
            if team_name and 'benagalbon' not in team_name:
                continue
            name = str(item.get('name') or '').strip()
            if not name:
                continue
            key = normalize_player_name(name)
            universo_map[key] = item
            dorsal_raw = str(item.get('dorsal') or '').strip()
            if dorsal_raw.isdigit():
                universo_by_number[int(dorsal_raw)] = item

    def _find_universo_entry(player_obj):
        key = normalize_player_name(player_obj.name)
        direct = universo_map.get(key)
        if direct:
            return direct
        if player_obj.number is not None and player_obj.number in universo_by_number:
            return universo_by_number[player_obj.number]
        compact = key.replace('-', '')
        for ukey, entry in universo_map.items():
            ucompact = ukey.replace('-', '')
            if compact in ucompact or ucompact in compact:
                return entry
        tokens = [token for token in compact.split('-') if token]
        for ukey, entry in universo_map.items():
            u_tokens = [token for token in ukey.replace('-', ' ').split() if token]
            overlap = sum(1 for token in tokens if token in u_tokens)
            if overlap >= 2:
                return entry
        return {}
    preferred_sources = preferred_event_source_by_match(primary_team)
    lineup_by_match = {}
    convocation_qs = (
        ConvocationRecord.objects.filter(team=primary_team, match__isnull=False)
        .exclude(lineup_data={})
        .order_by('match_id', '-created_at')
    )
    for record in convocation_qs:
        if record.match_id in lineup_by_match:
            continue
        allowed = list(record.players.all())
        normalized = _normalize_lineup_payload(record.lineup_data if isinstance(record.lineup_data, dict) else {}, allowed)
        lineup_by_match[record.match_id] = normalized
    match_end_minutes = {}
    player_match_timeline = {}
    events = (
        confirmed_events_queryset()
        .filter(player__team=primary_team)
        .select_related('player', 'match')
        .order_by('player__name', 'match__date')
    )
    live_events = (
        MatchEvent.objects.filter(
            system='touch-field-final',
        ).filter(
            Q(player__team=primary_team) | Q(player__isnull=True),
            Q(match__home_team=primary_team) | Q(match__away_team=primary_team),
        )
        .select_related('player', 'match')
        .order_by('player__name', 'match__date')
    )
    seen_signatures = set()
    for event in events:
        player = event.player
        if not player:
            continue
        photo_path = resolve_player_photo_static_path(player)
        match = event.match
        preferred_source = preferred_sources.get(match.id if match else None)
        event_source = (event.source_file or '').strip().lower()
        # Keep admin/manual edits visible in player stats even when another source
        # is preferred for that match.
        is_manual_source = event_source == 'admin-manual' or 'manual' in event_source
        if preferred_source and (event.source_file or '') != preferred_source and not is_manual_source:
            continue
        signature = _event_signature(event)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        roster_entry = find_roster_entry(player.name, roster_cache) or {}
        manual_entry = manual_overrides.get(player.id, {})
        universo_entry = _find_universo_entry(player) or {}
        base_pj = (
            manual_entry.get('pj')
            if manual_entry.get('pj') is not None
            else _parse_int(universo_entry.get('pj'))
            if universo_entry.get('pj') not in (None, '')
            else roster_entry.get('pj', 0)
        )
        base_pt = (
            manual_entry.get('pt')
            if manual_entry.get('pt') is not None
            else _parse_int(universo_entry.get('pt'))
            if universo_entry.get('pt') not in (None, '')
            else roster_entry.get('pt', 0)
        )
        base_minutes = (
            manual_entry.get('minutes')
            if manual_entry.get('minutes') is not None
            else _parse_int(universo_entry.get('minutes'))
            if universo_entry.get('minutes') not in (None, '')
            else roster_entry.get('minutes', 0)
        )
        base_pc = max(roster_entry.get('pc', 0), base_pj)
        base_goals = (
            manual_entry.get('goals')
            if manual_entry.get('goals') is not None
            else _parse_int(universo_entry.get('goals'))
            if universo_entry.get('goals') not in (None, '')
            else roster_entry.get('goals', 0)
        )
        base_yellow = (
            manual_entry.get('yellow_cards')
            if manual_entry.get('yellow_cards') is not None
            else _parse_int(universo_entry.get('yellow_cards'))
            if universo_entry.get('yellow_cards') not in (None, '')
            else roster_entry.get('yellow_cards', 0)
        )
        base_red = (
            manual_entry.get('red_cards')
            if manual_entry.get('red_cards') is not None
            else _parse_int(universo_entry.get('red_cards'))
            if universo_entry.get('red_cards') not in (None, '')
            else roster_entry.get('red_cards', 0)
        )
        base_assists = roster_entry.get('assists', 0)
        stats = player_stats.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'photo_url': static(photo_path) if photo_path else '',
                'position': player.position or universo_entry.get('position') or roster_entry.get('position', ''),
                'total_actions': 0,
                'successes': 0,
                'pc': base_pc,
                'pj': base_pj,
                'pt': base_pt,
                'minutes': base_minutes,
                'goals': base_goals,
                'yellow_cards': base_yellow,
                'red_cards': base_red,
                'assists': base_assists,
                # Only manual-base overrides should lock auto aggregation.
                'totals_locked': any(
                    key in manual_entry
                    for key in ('pj', 'pt', 'minutes', 'goals', 'yellow_cards', 'red_cards')
                ),
                'matches': {},
                'zone_counts': {key: 0 for key in FIELD_ZONE_KEYS},
                'position_counts': {key: 0 for key in FIELD_ZONE_KEYS},
                'tercio_counts': {label: 0 for label in STANDARD_TERCIO_LABELS},
                'tercio_totals': {label: 0 for label in STANDARD_TERCIO_LABELS},
                'duels_total': 0,
                'duels_won': 0,
                'shot_attempts': 0,
                'shots_on_target': 0,
                'pass_attempts': 0,
                'passes_completed': 0,
                'dribbles_attempted': 0,
                'dribbles_completed': 0,
                'age': _parse_int(universo_entry.get('age')) or roster_entry.get('age'),
                'has_events': False,
            },
        )
        if base_pj > 0:
            stats['has_events'] = True
        stats['total_actions'] += 1
        if result_is_success(event.result):
            stats['successes'] += 1
        if (not stats['totals_locked']) and is_goal_event(event.event_type, event.result, event.observation):
            stats['goals'] += 1
        if (not stats['totals_locked']) and is_assist_event(event.event_type, event.result, event.observation):
            stats['assists'] += 1
        if (not stats['totals_locked']) and is_yellow_card_event(event.event_type, event.result, event.zone):
            stats['yellow_cards'] += 1
        if (not stats['totals_locked']) and is_red_card_event(event.event_type, event.result, event.zone):
            stats['red_cards'] += 1
        duel_event = classify_duel_event(event.event_type, event.result, event.observation, event.zone)
        if duel_event.get('is_duel'):
            stats['duels_total'] += 1
            if duel_event.get('won'):
                stats['duels_won'] += 1
        zone = (event.zone or '').strip()
        zone_label = map_zone_label(zone)
        if zone_label:
            stats['zone_counts'][zone_label] += 1
        tercio = (event.tercio or '').strip()
        if tercio:
            mapped = map_tercio(tercio)
            if mapped:
                stats['tercio_counts'][mapped] += 1
                stats['tercio_totals'][mapped] += 1
        position_label = categorize_position(player.position, event.zone)
        if position_label:
            stats['position_counts'][position_label] += 1
        shot_event = contains_keyword(event.event_type, SHOT_KEYWORDS) or contains_keyword(event.observation, SHOT_KEYWORDS)
        save_event = is_goalkeeper_save_event(event.event_type, event.result, event.observation)
        if shot_event or save_event:
            stats['shot_attempts'] += 1
            if save_event or result_is_success(event.result):
                stats['shots_on_target'] += 1
        if contains_keyword(event.event_type, PASS_KEYWORDS) or contains_keyword(event.observation, PASS_KEYWORDS):
            stats['pass_attempts'] += 1
            if result_is_success(event.result):
                stats['passes_completed'] += 1
        if contains_keyword(event.event_type, DRIBBLE_KEYWORDS) or contains_keyword(event.observation, DRIBBLE_KEYWORDS):
            stats['dribbles_attempted'] += 1
            if result_is_success(event.result):
                stats['dribbles_completed'] += 1
        if not match:
            continue
        match_key = match.id
        match_entry = stats['matches'].setdefault(
            match_key,
            {
                'match_id': match.id,
                'round': match.round or 'Partido sin jornada',
                'date': match.date.isoformat() if match.date else None,
                'home': match.home_team == primary_team,
                'opponent': (
                    match.away_team.name
                    if match.home_team == primary_team and match.away_team
                    else match.home_team.name
                    if match.away_team == primary_team and match.home_team
                    else 'Rival desconocido'
                ),
                'actions': 0,
                'successes': 0,
            },
        )
        match_entry['actions'] += 1
        if result_is_success(event.result):
            match_entry['successes'] += 1
        match_entry['success_rate'] = round(
            (match_entry['successes'] / match_entry['actions']) * 100
        ) if match_entry['actions'] else 0
    for event in live_events:
        match = event.match
        if match and event.minute is not None:
            match_end_minutes[match.id] = max(match_end_minutes.get(match.id, 0), event.minute)
        player = event.player
        if not player:
            continue
        if match:
            timeline = player_match_timeline.setdefault(player.id, {}).setdefault(
                match.id,
                {'entry': None, 'exit': None, 'has_event': False},
            )
            timeline['has_event'] = True
            if is_substitution_entry(event.event_type, event.result, event.zone):
                timeline['entry'] = min_or_none(timeline['entry'], event.minute or 0)
            if is_substitution_exit(event.event_type, event.result, event.zone):
                timeline['exit'] = min_or_none(timeline['exit'], event.minute or 0)
    processed_lineup_matches = defaultdict(set)
    for player_id, matches in player_match_timeline.items():
        stats = player_stats.get(player_id)
        if not stats:
            continue
        for match_id, timeline in matches.items():
            processed_lineup_matches[player_id].add(match_id)
            match_end = match_end_minutes.get(match_id, 0)
            lineup_seed = lineup_by_match.get(match_id) or {}
            lineup_starters = {
                str(item.get('id'))
                for item in (lineup_seed.get('starters') or [])
                if isinstance(item, dict)
            }
            player_key = str(player_id)
            entry_minute = timeline.get('entry')
            exit_minute = timeline.get('exit')
            if entry_minute is None and player_key in lineup_starters:
                entry_minute = 0
            if entry_minute is None:
                entry_minute = 0
            if match_end <= 0 and player_key in lineup_starters:
                match_end = 90
            if exit_minute is None:
                exit_minute = match_end
            if exit_minute is None:
                exit_minute = entry_minute
            if exit_minute < entry_minute:
                exit_minute = entry_minute
            if not stats.get('totals_locked'):
                played_match = bool(timeline.get('has_event')) or (player_key in lineup_starters)
                stats['minutes'] += max(0, exit_minute - entry_minute)
                stats['pj'] += 1 if played_match else 0
                if player_key in lineup_starters:
                    stats['pt'] += 1
        if not stats.get('totals_locked'):
            stats['pc'] = max(stats.get('pc', 0), stats['pj'])
    # ensure roster players appear even without events
    for player in roster_players:
        if player.id not in player_stats:
            photo_path = resolve_player_photo_static_path(player)
            normalized = normalize_player_name(player.name)
            roster_entry = roster_cache.get(normalized, {})
            manual_entry = manual_overrides.get(player.id, {})
            universo_entry = _find_universo_entry(player) or {}
            base_pj = (
                manual_entry.get('pj')
                if manual_entry.get('pj') is not None
                else _parse_int(universo_entry.get('pj'))
                if universo_entry.get('pj') not in (None, '')
                else roster_entry.get('pj', 0)
            )
            base_pt = (
                manual_entry.get('pt')
                if manual_entry.get('pt') is not None
                else _parse_int(universo_entry.get('pt'))
                if universo_entry.get('pt') not in (None, '')
                else roster_entry.get('pt', 0)
            )
            player_stats[player.id] = {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'photo_url': static(photo_path) if photo_path else '',
                'position': player.position or universo_entry.get('position') or roster_entry.get('position'),
                'total_actions': 0,
                'successes': 0,
                'pc': max(roster_entry.get('pc', 0), base_pj),
                'pj': base_pj,
                'pt': base_pt,
                'minutes': (
                    manual_entry.get('minutes')
                    if manual_entry.get('minutes') is not None
                    else _parse_int(universo_entry.get('minutes'))
                    if universo_entry.get('minutes') not in (None, '')
                    else roster_entry.get('minutes', 0)
                ),
                'goals': (
                    manual_entry.get('goals')
                    if manual_entry.get('goals') is not None
                    else _parse_int(universo_entry.get('goals'))
                    if universo_entry.get('goals') not in (None, '')
                    else roster_entry.get('goals', 0)
                ),
                'yellow_cards': (
                    manual_entry.get('yellow_cards')
                    if manual_entry.get('yellow_cards') is not None
                    else _parse_int(universo_entry.get('yellow_cards'))
                    if universo_entry.get('yellow_cards') not in (None, '')
                    else roster_entry.get('yellow_cards', 0)
                ),
                'red_cards': (
                    manual_entry.get('red_cards')
                    if manual_entry.get('red_cards') is not None
                    else _parse_int(universo_entry.get('red_cards'))
                    if universo_entry.get('red_cards') not in (None, '')
                    else roster_entry.get('red_cards', 0)
                ),
                'assists': roster_entry.get('assists', 0),
                'totals_locked': any(
                    key in manual_entry
                    for key in ('pj', 'pt', 'minutes', 'goals', 'yellow_cards', 'red_cards')
                ),
                'matches': {},
                'zone_counts': {key: 0 for key in FIELD_ZONE_KEYS},
                'position_counts': {key: 0 for key in FIELD_ZONE_KEYS},
                'tercio_counts': {label: 0 for label in STANDARD_TERCIO_LABELS},
                'tercio_totals': {label: 0 for label in STANDARD_TERCIO_LABELS},
                'duels_total': 0,
                'duels_won': 0,
                'shot_attempts': 0,
                'shots_on_target': 0,
                'pass_attempts': 0,
                'passes_completed': 0,
                'dribbles_attempted': 0,
                'dribbles_completed': 0,
                'age': _parse_int(universo_entry.get('age')) or roster_entry.get('age'),
                'has_events': base_pj > 0,
            }

    lineup_matches = {
        match.id: match
        for match in Match.objects.filter(id__in=list(lineup_by_match.keys())).select_related('home_team', 'away_team')
    }
    for match_id, lineup_seed in lineup_by_match.items():
        starters = {
            int(item.get('id'))
            for item in (lineup_seed.get('starters') or [])
            if isinstance(item, dict) and str(item.get('id') or '').isdigit()
        }
        if not starters:
            continue
        match = lineup_matches.get(match_id)
        match_end = match_end_minutes.get(match_id, 90)
        if match_end <= 0:
            match_end = 90
        for player_id in starters:
            if match_id in processed_lineup_matches[player_id]:
                continue
            stats = player_stats.get(player_id)
            if not stats:
                continue
            if stats.get('totals_locked'):
                processed_lineup_matches[player_id].add(match_id)
                continue
            stats['pt'] += 1
            stats['pj'] += 1
            stats['minutes'] += match_end
            stats['pc'] = max(stats.get('pc', 0), stats['pj'])
            stats['has_events'] = True
            if match:
                stats['matches'].setdefault(
                    match_id,
                    {
                        'match_id': match.id,
                        'round': match.round or 'Partido sin jornada',
                        'date': match.date.isoformat() if match.date else None,
                        'home': match.home_team == primary_team,
                        'opponent': (
                            match.away_team.name
                            if match.home_team == primary_team and match.away_team
                            else match.home_team.name
                            if match.away_team == primary_team and match.home_team
                            else 'Rival desconocido'
                        ),
                        'actions': 0,
                        'successes': 0,
                        'success_rate': 0,
                    },
                )
            processed_lineup_matches[player_id].add(match_id)

    result = []
    today = timezone.localdate()
    for stats in player_stats.values():
        matches = sorted(
            stats['matches'].values(),
            key=lambda entry: (
                extract_round_number(entry['round']) is None,
                extract_round_number(entry['round']) or 9999,
                entry['date'] or '',
            ),
        )
        roster_entry = find_roster_entry(stats['name'], roster_cache)
        total_tercios = sum(stats['tercio_totals'].values())
        position_list = sorted(
            stats['position_counts'].items(),
            key=lambda item: item[1],
            reverse=True,
        )
        field_zones = []
        total_zone_actions = max(1, int(stats.get('total_actions') or 0))
        for zone in FIELD_ZONES:
            zone_count = stats['zone_counts'].get(zone['key'], 0)
            field_zones.append(
                {
                    **zone,
                    'count': zone_count,
                    'pct': round((zone_count / total_zone_actions) * 100, 1) if stats.get('total_actions') else 0,
                }
            )
        merged = {
            **stats,
            'matches': matches,
            'match_count': len(matches),
            'competition_total_rounds': competition_total_rounds,
            'age': stats.get('age') or (roster_entry.get('age') if roster_entry else None),
            'success_rate': round(
                (stats['successes'] / stats['total_actions']) * 100, 1
            )
            if stats['total_actions']
            else 0,
            'duel_summary': {
                'won': stats['duels_won'],
                'total': stats['duels_total'],
            },
            'duel_rate': round(
                (stats['duels_won'] / stats['duels_total']) * 100, 1
            )
            if stats['duels_total']
            else 0,
            'zone_heatmap': sorted(
                [
                    {'zone': zone, 'count': count}
                    for zone, count in stats['zone_counts'].items()
                    if count > 0
                ],
                key=lambda entry: entry['count'],
                reverse=True,
            )[:5],
            'tercio_summary': [
                {
                    'label': tercio_label,
                    'count': stats['tercio_totals'].get(tercio_label, 0),
                    'pct': round(
                        (stats['tercio_totals'].get(tercio_label, 0) / total_tercios) * 100, 1
                    )
                    if total_tercios
                    else 0,
                }
                for tercio_label in ('Ataque', 'Construcción', 'Defensa')
            ],
            'tercio_heatmap': sorted(
                [{'tercio': tercio, 'count': count} for tercio, count in stats['tercio_counts'].items()],
                key=lambda entry: entry['count'],
                reverse=True,
            )[:5],
            'position_breakdown': [
                {'label': label, 'count': count}
                for label, count in position_list
            ],
            'dominant_position': position_list[0][0] if position_list else (stats.get('position') or 'Sin definir'),
            'field_zones': field_zones,
            'shots': {
                'attempts': stats['shot_attempts'],
                'on_target': stats['shots_on_target'],
                'accuracy': round((stats['shots_on_target'] / stats['shot_attempts']) * 100, 1)
                if stats['shot_attempts']
                else 0,
            },
            'passes': {
                'attempts': stats['pass_attempts'],
                'completed': stats['passes_completed'],
                'accuracy': round((stats['passes_completed'] / stats['pass_attempts']) * 100, 1)
                if stats['pass_attempts']
                else 0,
            },
        }
        player_obj = player_by_id.get(stats.get('player_id'))
        red_cards_value = int(stats.get('red_cards') or 0)
        yellow_cards_value = int(stats.get('yellow_cards') or 0)
        merged['has_active_injury'] = bool(player_obj and player_obj.id in active_injury_ids)
        merged['is_sanctioned'] = bool(
            player_obj
            and (
                player_obj.id in sanctioned_player_ids
                or is_manual_sanction_active(player_obj, today=today)
            )
        )
        merged['is_apercibido'] = yellow_cards_value in {4, 9, 14}
        if competition_total_rounds > 0:
            merged['participation_pct'] = round(
                min((int(stats.get('pj') or 0) / competition_total_rounds) * 100, 100),
                1,
            )
        else:
            merged['participation_pct'] = 0
        profile, profile_label, smart_kpis = build_smart_kpis(stats)
        merged['profile'] = profile
        merged['profile_label'] = profile_label
        merged['smart_kpis'] = smart_kpis
        result.append(merged)
    return sorted(
        result,
        key=lambda entry: (-entry.get('total_actions', 0), -entry.get('pj', 0), entry.get('name', '')),
    )
