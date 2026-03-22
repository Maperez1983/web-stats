import json
import os
import subprocess
import sys
import base64
import mimetypes
import io
import csv
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
import unicodedata
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max, Q
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404, HttpResponse, JsonResponse
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
    import weasyprint
except Exception:  # pragma: no cover
    weasyprint = None

from football.models import (
    Match,
    MatchEvent,
    Player,
    PlayerInjuryRecord,
    PlayerCommunication,
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
    contains_keyword,
    duel_result_is_success,
    extract_round_number,
    is_assist_event,
    is_duel_event,
    is_goal_event,
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


def resolve_team_photo_for_pdf(request):
    default_path = Path(settings.BASE_DIR) / 'static' / 'football' / 'images' / 'team-01.jpg'
    fallback_url = request.build_absolute_uri(static('football/images/team-01.jpg'))
    fallback_data_uri = _file_as_data_uri(default_path)
    source_path = default_path
    source_url = fallback_url

    carousel_cover = (
        HomeCarouselImage.objects
        .filter(is_active=True)
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

    data_uri = _file_as_data_uri(source_path) or fallback_data_uri
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
            'name': player.name if player else 'Jugador',
            'number': (player.number if player and player.number is not None else '--'),
        },
    }


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

    payload = {
        'round': round_label or 'Jornada por confirmar',
        'date': date_iso,
        'time': time_label,
        'location': location_label or 'Campo por confirmar',
        'opponent': {
            'name': opponent_name or 'Rival por confirmar',
            'full_name': opponent_name or 'Rival por confirmar',
            'crest_url': '',
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
    hero_image_candidates = [
        item.image.url
        for item in HomeCarouselImage.objects.filter(is_active=True).order_by('order', '-created_at', '-id')
        if item.image
    ]
    return render(
        request,
        'football/dashboard.html',
        {
            'scrape_sources': sources,
            'hero_image_candidates': hero_image_candidates,
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
    primary_team = Team.objects.filter(is_primary=True).first()
    roster_message = ''
    roster_error = ''
    carousel_message = ''
    user_message = ''
    user_error = ''
    active_tab = (request.GET.get('tab') or request.POST.get('active_tab') or 'roster').strip().lower()
    if active_tab not in {'roster', 'carousel', 'users'}:
        active_tab = 'roster'
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
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
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
    carousel_images = list(HomeCarouselImage.objects.all())
    roster_players = (
        list(Player.objects.filter(team=primary_team).order_by('-is_active', 'number', 'name'))
        if primary_team
        else []
    )
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
            'active_tab': active_tab,
            'team_name': primary_team.name if primary_team else '',
        },
    )


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
        },
    )


def coach_overview_page(request):
    sources = list(ScrapeSource.objects.filter(is_active=True))
    summary = {
        'entrainers': [
            'Entrenador principal · Aitor Castillo',
            'Entrenador auxiliar · Antonio Martín',
            'Preparador físico · Alonso García',
        ],
        'rival': [
            'Último rival: Atlético de Marbella',
            'Consecutivos sin recibir gol: 1',
            'Fortaleza: laterales rápidos',
        ],
        'sessions': [
            'Martes AM · Táctica ofensiva',
            'Martes PM · Duelo alto',
            'Domingo · Video y recuperación',
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


def match_action_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    active_match = get_active_match(primary_team)
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
    recent_match_ids = list(
        Match.objects.filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .order_by('-date', '-id')
        .values_list('id', flat=True)[:12]
    )
    recent_events = (
        MatchEvent.objects.filter(match_id__in=recent_match_ids)
        .select_related('player')
        .order_by('-created_at')[:6]
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
    return render(
        request,
        'football/match_actions.html',
        {
            'players': convocation_players,
            'convocation_players': convocation_players,
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
        },
    )


@authenticated_write
@require_POST
def register_match_action(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    player_id = request.POST.get('player')
    convocation_record = get_current_convocation_record(
        primary_team,
        match=get_active_match(primary_team),
        fallback_to_latest=True,
    )
    if not convocation_record:
        return JsonResponse({'error': 'No hay convocatoria activa guardada para registrar acciones'}, status=400)
    player = convocation_record.players.filter(id=player_id).first()
    if not player:
        return JsonResponse({'error': 'Selecciona un jugador convocado válido'}, status=400)
    action_type = (request.POST.get('action_type') or '').strip()
    if not action_type:
        return JsonResponse({'error': 'Especifica el tipo de acción'}, status=400)
    match = get_active_match(primary_team)
    if not match:
        return JsonResponse({'error': 'No hay partido disponible para registrar acciones'}, status=400)
    if not convocation_record.players.filter(id=player.id).exists():
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
        player=player,
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
        player=player,
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
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    convocation_record = get_current_convocation_record(
        primary_team,
        match=get_active_match(primary_team),
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
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    event_id = request.POST.get('event_id')
    try:
        event = MatchEvent.objects.filter(
            Q(match__home_team=primary_team) | Q(match__away_team=primary_team)
        ).get(id=event_id)
    except MatchEvent.DoesNotExist:
        return JsonResponse({'error': 'Evento no encontrado'}, status=404)
    event.delete()
    return JsonResponse({'deleted': event_id})


@authenticated_write
@require_POST
def finalize_match_actions(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    match = get_active_match(primary_team)
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

    updated = MatchEvent.objects.filter(id__in=[event.id for event in pending_events]).update(
        system='touch-field-final'
    )
    return JsonResponse(
        {
            'saved': True,
            'updated': updated,
            'match_id': match.id,
            'match_label': str(match),
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

    player_rows = [
        {
            'number': player.number,
            'name': player.name,
            'photo_url': resolve_player_photo_url(request, player),
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
        'rival_crest_url': rival_crest_url,
        'players': player_rows,
        'left_column_players': left_column_players,
        'right_column_players': right_column_players,
        'coach_name': os.getenv('TEAM_COACH_NAME', 'Aitor Castillo'),
        'club_hashtag': os.getenv('TEAM_HASHTAG', '#VamosVerdes'),
        'logo_url': request.build_absolute_uri(static('football/images/cdb-logo.png')),
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
        },
        {
            'title': 'Preparador porteros',
            'description': 'Repositorio táctico y tareas específicas de porteros.',
            'link': 'coach-role-goalkeeper',
        },
        {
            'title': 'Preparación física',
            'description': 'Espacio preparado para métricas y carga física.',
            'link': 'coach-role-fitness',
        },
        {
            'title': 'ABP',
            'description': 'Repositorio de sesiones ABP y pizarra táctica con simulación.',
            'link': 'coach-role-abp',
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
    duels = [event for event in events if is_duel_event(event.event_type, event.observation)]
    duel_won = [event for event in duels if duel_result_is_success(event.result)]
    duel_rate = round((len(duel_won) / len(duels)) * 100, 1) if duels else 0.0
    success_actions = [event for event in events if result_is_success(event.result)]
    success_rate = round((len(success_actions) / total_actions) * 100, 1) if total_actions else 0.0
    avg_actions = round(total_actions / total_matches, 1) if total_matches else 0.0
    avg_duels = round(len(duels) / total_matches, 1) if total_matches else 0.0
    avg_yellows = round(yellows / total_matches, 2) if total_matches else 0.0

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

    modules = [
        {'title': 'Convocatoria', 'description': 'Define lista oficial y PDF del partido.', 'link': 'convocation'},
        {'title': '11 inicial', 'description': 'Registro de acción con once titular y banquillo.', 'link': 'match-action-page'},
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
        },
    )


def coach_role_goalkeeper_page(request):
    modules = [
        {'title': 'Repositorio tareas portero', 'description': 'Usa el planner para guardar ejercicios de porteros.', 'link': 'sessions'},
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


def sessions_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')

    def parse_date(raw):
        value = (raw or '').strip()
        if not value:
            return None
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    feedback = ''
    error = ''
    active_match = get_active_match(primary_team)
    today = timezone.localdate()
    default_week_start = today - timedelta(days=today.weekday())
    if active_match and active_match.date:
        default_week_start = active_match.date - timedelta(days=active_match.date.weekday())

    planner_tables_ready = True
    try:
        TrainingMicrocycle.objects.order_by('-id').values_list('id', flat=True).first()
        SessionTask.objects.order_by('-id').values_list('tactical_layout', flat=True).first()
    except (OperationalError, ProgrammingError):
        planner_tables_ready = False
        error = (
            'El planificador de sesiones requiere migración de base de datos. '
            'Ejecuta `python manage.py migrate` y recarga la página.'
        )

    if request.method == 'POST' and planner_tables_ready:
        planner_action = (request.POST.get('planner_action') or '').strip()
        try:
            if planner_action == 'create_microcycle':
                week_start = parse_date(request.POST.get('week_start')) or default_week_start
                week_end = week_start + timedelta(days=6)
                title = (request.POST.get('title') or '').strip() or 'Microciclo semanal'
                objective = (request.POST.get('objective') or '').strip()
                notes = (request.POST.get('notes') or '').strip()
                status = (request.POST.get('status') or TrainingMicrocycle.STATUS_DRAFT).strip()
                allowed_statuses = {choice[0] for choice in TrainingMicrocycle.STATUS_CHOICES}
                if status not in allowed_statuses:
                    status = TrainingMicrocycle.STATUS_DRAFT
                microcycle, created = TrainingMicrocycle.objects.get_or_create(
                    team=primary_team,
                    week_start=week_start,
                    defaults={
                        'week_end': week_end,
                        'title': title,
                        'objective': objective,
                        'status': status,
                        'notes': notes,
                        'reference_match': active_match,
                    },
                )
                if not created:
                    microcycle.week_end = week_end
                    microcycle.title = title
                    microcycle.objective = objective
                    microcycle.status = status
                    microcycle.notes = notes
                    if active_match:
                        microcycle.reference_match = active_match
                    microcycle.save()
                feedback = 'Microciclo guardado correctamente.'
            elif planner_action == 'create_session':
                microcycle_id = _parse_int(request.POST.get('microcycle_id'))
                session_date = parse_date(request.POST.get('session_date'))
                focus = (request.POST.get('focus') or '').strip()
                if not microcycle_id or not session_date or not focus:
                    raise ValueError('Completa microciclo, fecha y foco de la sesión.')
                microcycle = TrainingMicrocycle.objects.filter(id=microcycle_id, team=primary_team).first()
                if not microcycle:
                    raise ValueError('Microciclo no válido.')
                start_time = None
                start_time_raw = (request.POST.get('start_time') or '').strip()
                if start_time_raw:
                    try:
                        start_time = datetime.strptime(start_time_raw, '%H:%M').time()
                    except ValueError:
                        raise ValueError('Formato de hora inválido. Usa HH:MM.')
                duration = _parse_int(request.POST.get('duration_minutes')) or 90
                intensity = (request.POST.get('intensity') or TrainingSession.INTENSITY_MEDIUM).strip()
                intensity_choices = {choice[0] for choice in TrainingSession.INTENSITY_CHOICES}
                if intensity not in intensity_choices:
                    intensity = TrainingSession.INTENSITY_MEDIUM
                content = (request.POST.get('content') or '').strip()
                TrainingSession.objects.create(
                    microcycle=microcycle,
                    session_date=session_date,
                    start_time=start_time,
                    duration_minutes=max(15, min(duration, 240)),
                    intensity=intensity,
                    focus=focus,
                    content=content,
                    order=0,
                )
                feedback = 'Sesión creada correctamente.'
            elif planner_action == 'create_task':
                session_id = _parse_int(request.POST.get('session_id'))
                title = (request.POST.get('task_title') or '').strip()
                if not session_id or not title:
                    raise ValueError('Selecciona sesión y añade el nombre de la tarea.')
                session = (
                    TrainingSession.objects
                    .select_related('microcycle')
                    .filter(id=session_id, microcycle__team=primary_team)
                    .first()
                )
                if not session:
                    raise ValueError('Sesión no válida.')
                block = (request.POST.get('block') or SessionTask.BLOCK_MAIN_1).strip()
                block_choices = {choice[0] for choice in SessionTask.BLOCK_CHOICES}
                if block not in block_choices:
                    block = SessionTask.BLOCK_MAIN_1
                duration = _parse_int(request.POST.get('task_minutes')) or 15
                objective = (request.POST.get('task_objective') or '').strip()
                coaching_points = (request.POST.get('task_coaching_points') or '').strip()
                confrontation_rules = (request.POST.get('task_confrontation_rules') or '').strip()
                surface = (request.POST.get('task_surface') or '').strip()
                pitch_format = (request.POST.get('task_pitch_format') or '').strip()
                space = (request.POST.get('task_space') or '').strip()
                organization = (request.POST.get('task_organization') or '').strip()
                players_distribution = (request.POST.get('task_players_distribution') or '').strip()
                load_target = (request.POST.get('task_load_target') or '').strip()
                resources_summary = (request.POST.get('task_resources_summary') or '').strip()
                progression = (request.POST.get('task_progression') or '').strip()
                regression = (request.POST.get('task_regression') or '').strip()
                work_rest = (request.POST.get('task_work_rest') or '').strip()
                series = (request.POST.get('task_series') or '').strip()
                repetitions = (request.POST.get('task_repetitions') or '').strip()
                principle = (request.POST.get('task_principle') or '').strip()
                subprinciple = (request.POST.get('task_subprinciple') or '').strip()
                scoring_model = (request.POST.get('task_scoring_model') or '').strip()
                success_criteria = (request.POST.get('task_success_criteria') or '').strip()
                game_phase = (request.POST.get('task_game_phase') or '').strip()
                game_sub_phase = (request.POST.get('task_game_sub_phase') or '').strip()
                methodology = (request.POST.get('task_methodology') or '').strip()
                complexity = (request.POST.get('task_complexity') or '').strip()
                cognitive_load = (request.POST.get('task_cognitive_load') or '').strip()
                emotional_load = (request.POST.get('task_emotional_load') or '').strip()
                targets = (request.POST.get('task_targets') or '').strip()
                expected_outcomes = (request.POST.get('task_expected_outcomes') or '').strip()
                common_errors = (request.POST.get('task_common_errors') or '').strip()
                corrective_cues = (request.POST.get('task_corrective_cues') or '').strip()
                video_reference = (request.POST.get('task_video_reference') or '').strip()
                staff_notes = (request.POST.get('task_staff_notes') or '').strip()
                constraints = [str(v).strip() for v in request.POST.getlist('task_constraints') if str(v).strip()]
                tactical_pad_enabled = str(request.POST.get('task_tactical_pad_enabled') or '').strip().lower() in {'1', 'true', 'on', 'yes'}
                blueprint_id = _parse_int(request.POST.get('task_blueprint_id'))
                tactical_layout_raw = (request.POST.get('tactical_layout') or '').strip()
                tactical_layout = {}
                blueprint_payload = {}
                if blueprint_id:
                    blueprint = TaskBlueprint.objects.filter(id=blueprint_id, team=primary_team).first()
                    if blueprint and isinstance(blueprint.payload, dict):
                        blueprint_payload = dict(blueprint.payload)
                if tactical_layout_raw:
                    try:
                        parsed_layout = json.loads(tactical_layout_raw)
                        if isinstance(parsed_layout, dict):
                            tactical_layout = parsed_layout
                    except Exception:
                        tactical_layout = {}
                meta = tactical_layout.get('meta') if isinstance(tactical_layout, dict) else {}
                if not isinstance(meta, dict):
                    meta = {}
                surface = surface or str(blueprint_payload.get('task_surface') or '').strip()
                pitch_format = pitch_format or str(blueprint_payload.get('task_pitch_format') or '').strip()
                space = space or str(blueprint_payload.get('task_space') or '').strip()
                organization = organization or str(blueprint_payload.get('task_organization') or '').strip()
                players_distribution = players_distribution or str(blueprint_payload.get('task_players_distribution') or '').strip()
                load_target = load_target or str(blueprint_payload.get('task_load_target') or '').strip()
                resources_summary = resources_summary or str(blueprint_payload.get('task_resources_summary') or '').strip()
                progression = progression or str(blueprint_payload.get('task_progression') or '').strip()
                regression = regression or str(blueprint_payload.get('task_regression') or '').strip()
                work_rest = work_rest or str(blueprint_payload.get('task_work_rest') or '').strip()
                series = series or str(blueprint_payload.get('task_series') or '').strip()
                repetitions = repetitions or str(blueprint_payload.get('task_repetitions') or '').strip()
                principle = principle or str(blueprint_payload.get('task_principle') or '').strip()
                subprinciple = subprinciple or str(blueprint_payload.get('task_subprinciple') or '').strip()
                scoring_model = scoring_model or str(blueprint_payload.get('task_scoring_model') or '').strip()
                success_criteria = success_criteria or str(blueprint_payload.get('task_success_criteria') or '').strip()
                objective = objective or str(blueprint_payload.get('task_objective') or '').strip()
                coaching_points = coaching_points or str(blueprint_payload.get('task_coaching_points') or '').strip()
                confrontation_rules = confrontation_rules or str(blueprint_payload.get('task_confrontation_rules') or '').strip()
                game_phase = game_phase or str(blueprint_payload.get('task_game_phase') or '').strip()
                game_sub_phase = game_sub_phase or str(blueprint_payload.get('task_game_sub_phase') or '').strip()
                methodology = methodology or str(blueprint_payload.get('task_methodology') or '').strip()
                complexity = complexity or str(blueprint_payload.get('task_complexity') or '').strip()
                cognitive_load = cognitive_load or str(blueprint_payload.get('task_cognitive_load') or '').strip()
                emotional_load = emotional_load or str(blueprint_payload.get('task_emotional_load') or '').strip()
                targets = targets or str(blueprint_payload.get('task_targets') or '').strip()
                expected_outcomes = expected_outcomes or str(blueprint_payload.get('task_expected_outcomes') or '').strip()
                common_errors = common_errors or str(blueprint_payload.get('task_common_errors') or '').strip()
                corrective_cues = corrective_cues or str(blueprint_payload.get('task_corrective_cues') or '').strip()
                video_reference = video_reference or str(blueprint_payload.get('task_video_reference') or '').strip()
                staff_notes = staff_notes or str(blueprint_payload.get('task_staff_notes') or '').strip()
                if not constraints:
                    raw_constraints = blueprint_payload.get('task_constraints')
                    if isinstance(raw_constraints, list):
                        constraints = [str(v).strip() for v in raw_constraints if str(v).strip()]
                if surface:
                    meta['surface'] = surface
                if pitch_format:
                    meta['pitch_format'] = pitch_format
                if space:
                    meta['space'] = space
                if organization:
                    meta['organization'] = organization
                if players_distribution:
                    meta['players_distribution'] = players_distribution
                if load_target:
                    meta['load_target'] = load_target
                if resources_summary:
                    meta['resources_summary'] = resources_summary
                if progression:
                    meta['progression'] = progression
                if regression:
                    meta['regression'] = regression
                if work_rest:
                    meta['work_rest'] = work_rest
                if series:
                    meta['series'] = series
                if repetitions:
                    meta['repetitions'] = repetitions
                if principle:
                    meta['principle'] = principle
                if subprinciple:
                    meta['subprinciple'] = subprinciple
                if scoring_model:
                    meta['scoring_model'] = scoring_model
                if success_criteria:
                    meta['success_criteria'] = success_criteria
                if game_phase:
                    meta['game_phase'] = game_phase
                if game_sub_phase:
                    meta['game_sub_phase'] = game_sub_phase
                if methodology:
                    meta['methodology'] = methodology
                if complexity:
                    meta['complexity'] = complexity
                if cognitive_load:
                    meta['cognitive_load'] = cognitive_load
                if emotional_load:
                    meta['emotional_load'] = emotional_load
                if targets:
                    meta['targets'] = targets
                if expected_outcomes:
                    meta['expected_outcomes'] = expected_outcomes
                if common_errors:
                    meta['common_errors'] = common_errors
                if corrective_cues:
                    meta['corrective_cues'] = corrective_cues
                if video_reference:
                    meta['video_reference'] = video_reference
                if staff_notes:
                    meta['staff_notes'] = staff_notes
                if constraints:
                    meta['constraints'] = constraints
                meta['tactical_pad_enabled'] = bool(tactical_pad_enabled)
                tactical_layout['meta'] = meta
                created_task = SessionTask.objects.create(
                    session=session,
                    title=title,
                    block=block,
                    duration_minutes=max(5, min(duration, 90)),
                    objective=objective,
                    coaching_points=coaching_points,
                    confrontation_rules=confrontation_rules,
                    tactical_layout=tactical_layout,
                    order=session.tasks.count() + 1,
                )
                save_as_blueprint = str(request.POST.get('task_save_as_blueprint') or '').strip().lower() in {'1', 'true', 'on', 'yes'}
                blueprint_name = (request.POST.get('task_blueprint_name') or '').strip()
                blueprint_category = (request.POST.get('task_blueprint_category') or TaskBlueprint.CATEGORY_OTHER).strip()
                allowed_categories = {item[0] for item in TaskBlueprint.CATEGORY_CHOICES}
                if blueprint_category not in allowed_categories:
                    blueprint_category = TaskBlueprint.CATEGORY_OTHER
                if save_as_blueprint and blueprint_name:
                    payload = {
                        'task_title': title,
                        'task_objective': objective,
                        'task_surface': surface,
                        'task_pitch_format': pitch_format,
                        'task_space': space,
                        'task_organization': organization,
                        'task_players_distribution': players_distribution,
                        'task_load_target': load_target,
                        'task_resources_summary': resources_summary,
                        'task_coaching_points': coaching_points,
                        'task_confrontation_rules': confrontation_rules,
                        'task_progression': progression,
                        'task_regression': regression,
                        'task_work_rest': work_rest,
                        'task_series': series,
                        'task_repetitions': repetitions,
                        'task_principle': principle,
                        'task_subprinciple': subprinciple,
                        'task_scoring_model': scoring_model,
                        'task_success_criteria': success_criteria,
                        'task_game_phase': game_phase,
                        'task_game_sub_phase': game_sub_phase,
                        'task_methodology': methodology,
                        'task_complexity': complexity,
                        'task_cognitive_load': cognitive_load,
                        'task_emotional_load': emotional_load,
                        'task_targets': targets,
                        'task_expected_outcomes': expected_outcomes,
                        'task_common_errors': common_errors,
                        'task_corrective_cues': corrective_cues,
                        'task_video_reference': video_reference,
                        'task_staff_notes': staff_notes,
                        'task_constraints': constraints,
                    }
                    TaskBlueprint.objects.update_or_create(
                        team=primary_team,
                        name=blueprint_name,
                        defaults={
                            'category': blueprint_category,
                            'description': f'Plantilla creada desde {created_task.title}',
                            'payload': payload,
                            'created_by': request.user.get_username() if request.user.is_authenticated else '',
                        },
                    )
                feedback = 'Tarea añadida a la sesión.'
            elif planner_action == 'delete_blueprint':
                blueprint_id = _parse_int(request.POST.get('blueprint_id'))
                blueprint = TaskBlueprint.objects.filter(id=blueprint_id, team=primary_team).first() if blueprint_id else None
                if not blueprint:
                    raise ValueError('Plantilla no encontrada.')
                blueprint.delete()
                feedback = 'Plantilla eliminada.'
            elif planner_action == 'duplicate_task':
                task_id = _parse_int(request.POST.get('task_id'))
                base_task = (
                    SessionTask.objects
                    .select_related('session__microcycle')
                    .filter(id=task_id, session__microcycle__team=primary_team)
                    .first()
                )
                if not base_task:
                    raise ValueError('Tarea no encontrada para duplicar.')
                SessionTask.objects.create(
                    session=base_task.session,
                    title=f'{base_task.title} (copia)',
                    block=base_task.block,
                    duration_minutes=base_task.duration_minutes,
                    objective=base_task.objective,
                    coaching_points=base_task.coaching_points,
                    confrontation_rules=base_task.confrontation_rules,
                    tactical_layout=base_task.tactical_layout if isinstance(base_task.tactical_layout, dict) else {},
                    status=SessionTask.STATUS_PLANNED,
                    order=SessionTask.objects.filter(session=base_task.session).count() + 1,
                    notes=base_task.notes,
                )
                feedback = 'Tarea duplicada correctamente.'
            else:
                error = 'Acción no reconocida.'
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = 'No se pudo guardar la planificación. Revisa los datos y vuelve a intentar.'

    microcycles = []
    if planner_tables_ready:
        microcycles = (
            TrainingMicrocycle.objects
            .filter(team=primary_team)
            .select_related('reference_match')
            .prefetch_related('sessions__tasks')
            .order_by('-week_start')[:8]
        )
    all_sessions = []
    for microcycle in microcycles:
        all_sessions.extend(list(microcycle.sessions.all()))

    category_labels = {
        'delimitacion': 'Delimitación',
        'coordinacion': 'Coordinación',
        'juego': 'Juego',
        'porterias': 'Porterías',
        'oposicion': 'Oposición',
        'organizacion': 'Organización',
        'control': 'Control',
        'fisico': 'Físico',
        'finalizacion': 'Finalización',
        'ppt': 'Biblioteca PPT',
    }
    task_materials = build_task_material_library()
    material_categories = []
    materials_by_category = {}
    for item in task_materials:
        category = str(item.get('category') or 'otros')
        if category not in materials_by_category:
            materials_by_category[category] = []
            material_categories.append(
                {
                    'value': category,
                    'label': category_labels.get(category, category.title()),
                }
            )
        materials_by_category[category].append(item)
    blueprints = list(TaskBlueprint.objects.filter(team=primary_team).order_by('category', 'name'))

    return render(
        request,
        'football/sessions_planner.html',
        {
            'team_name': primary_team.name,
            'feedback': feedback,
            'error': error,
            'active_match': active_match,
            'default_week_start': default_week_start,
            'microcycles': microcycles,
            'all_sessions': all_sessions,
            'microcycle_statuses': TrainingMicrocycle.STATUS_CHOICES,
            'session_intensities': TrainingSession.INTENSITY_CHOICES,
            'task_blocks': SessionTask.BLOCK_CHOICES,
            'task_materials': task_materials,
            'task_surface_choices': TASK_SURFACE_CHOICES,
            'task_pitch_format_choices': TASK_PITCH_FORMAT_CHOICES,
            'task_template_library': TASK_TEMPLATE_LIBRARY,
            'task_blueprints': blueprints,
            'task_blueprint_categories': TaskBlueprint.CATEGORY_CHOICES,
            'task_game_phase_choices': TASK_GAME_PHASE_CHOICES,
            'task_methodology_choices': TASK_METHODOLOGY_CHOICES,
            'task_complexity_choices': TASK_COMPLEXITY_CHOICES,
            'task_constraint_choices': TASK_CONSTRAINT_CHOICES,
            'material_categories': material_categories,
            'materials_by_category': materials_by_category,
            'planner_tables_ready': planner_tables_ready,
            'roster_players': Player.objects.filter(team=primary_team).order_by('name')[:28],
        },
    )


def fines_page(request):
    return render(
        request,
        'football/coach_section.html',
        {
            'section_title': 'Multas',
            'description': 'Seguimiento de sanciones disciplinarias.',
            'items': ['Jugador X · 1 partido', 'Jugador Y · trabajo extra'],
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


def manual_player_stats_page(request):
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
        if is_duel_event(event.event_type, event.observation):
            stats['duels_total'] += 1
            if duel_result_is_success(event.result):
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
        if contains_keyword(event.event_type, SHOT_KEYWORDS) or contains_keyword(event.observation, SHOT_KEYWORDS):
            stats['shot_attempts'] += 1
            if result_is_success(event.result):
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
    stats['field_zones'] = [
        {**zone, 'count': stats['zone_counts'].get(zone['key'], 0)}
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
    return Match.objects.filter(
        Q(home_team=primary_team) | Q(away_team=primary_team)
    ).select_related('home_team', 'away_team')


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
    match_end_minutes = {}
    player_match_timeline = {}
    events = (
        confirmed_events_queryset()
        .filter(player__team=primary_team)
        .select_related('player', 'match')
        .order_by('player__name', 'match__date')
    )
    live_events = (
        MatchEvent.objects.filter(player__team=primary_team, system='touch-field-final')
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
        if preferred_source and (event.source_file or '') != preferred_source:
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
                'totals_locked': bool(
                    base_pj
                    or base_pt
                    or base_minutes
                    or base_goals
                    or base_yellow
                    or base_red
                    or base_assists
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
        if is_duel_event(event.event_type, event.observation):
            stats['duels_total'] += 1
            if duel_result_is_success(event.result):
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
        if contains_keyword(event.event_type, SHOT_KEYWORDS) or contains_keyword(event.observation, SHOT_KEYWORDS):
            stats['shot_attempts'] += 1
            if result_is_success(event.result):
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
        player = event.player
        if not player:
            continue
        match = event.match
        if match and event.minute is not None:
            match_end_minutes[match.id] = max(match_end_minutes.get(match.id, 0), event.minute)
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
    for player_id, matches in player_match_timeline.items():
        stats = player_stats.get(player_id)
        if not stats:
            continue
        for match_id, timeline in matches.items():
            match_end = match_end_minutes.get(match_id, 0)
            entry_minute = timeline.get('entry')
            exit_minute = timeline.get('exit')
            if entry_minute is None:
                entry_minute = 0
            if exit_minute is None:
                exit_minute = match_end
            if exit_minute is None:
                exit_minute = entry_minute
            if exit_minute < entry_minute:
                exit_minute = entry_minute
            if not stats.get('totals_locked'):
                stats['minutes'] += max(0, exit_minute - entry_minute)
                stats['pj'] += 1 if timeline.get('has_event') else 0
                if entry_minute == 0:
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
                'totals_locked': bool(
                    base_pj
                    or base_pt
                    or roster_entry.get('minutes', 0)
                    or roster_entry.get('goals', 0)
                    or manual_entry.get('yellow_cards', roster_entry.get('yellow_cards', 0))
                    or roster_entry.get('red_cards', 0)
                    or roster_entry.get('assists', 0)
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
        field_zones = [
            {**zone, 'count': stats['zone_counts'].get(zone['key'], 0)}
            for zone in FIELD_ZONES
        ]
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
