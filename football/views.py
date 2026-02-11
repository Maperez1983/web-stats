import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
import unicodedata
import re

from django.conf import settings
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

try:
    import weasyprint
except (ImportError, OSError):  # pragma: no cover
    weasyprint = None

from football.models import (
    Match,
    MatchEvent,
    Player,
    ScrapeSource,
    Team,
    TeamStanding,
    ConvocationRecord,
)
from football.services import (
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
    _parse_int,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_from_rfef.py"
MANAGE_PY_DIR = SCRIPT_PATH.parents[1]
NEXT_MATCH_CACHE = Path(settings.BASE_DIR) / "data" / "input" / "rfaf-next-match.json"
SUCCESS_RESULTS = {"ok", "ganado", "g", "ganó", "goles", "anotado", "marcado"}
DUEL_EVENT_KEYWORDS = {
    "duelo",
    "regate",
    "regates",
    "robo",
    "robado",
    "intercepción",
    "intervención",
    "entrada",
    "entradas",
    "recuperación",
    "recuperado",
    "falta cometida",
    "falta recibida",
    "presión",
    "presionado",
    "error forzado",
    "error",
    "disputa",
}
DUEL_SUCCESS_KEYWORD = {"ganado", "recuperado", "ok", "fortaleza", "favorable", "superado"}
ZONE_MAP = {
    "defensa izquierda": "Defensa Izquierda",
    "lateral izquierdo": "Defensa Izquierda",
    "carril izquierdo": "Defensa Izquierda",
    "costa izquierda": "Defensa Izquierda",
    "defensa izquierda centro": "Defensa Izquierda",
    "defensa central": "Defensa Centro",
    "central": "Defensa Centro",
    "zona central": "Defensa Centro",
    "defensa derecha": "Defensa Derecha",
    "lateral derecho": "Defensa Derecha",
    "carril derecho": "Defensa Derecha",
    "costa derecha": "Defensa Derecha",
    "medio izquierdo": "Medio Izquierdo",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "medio derecho": "Medio Derecho",
    "media punta": "Ataque Centro",
    "pivote": "Medio Centro",
    "central ofensivo": "Medio Centro",
    "ataque izquierdo": "Ataque Izquierda",
    "extremo izquierdo": "Ataque Izquierda",
    "delantero izquierdo": "Ataque Izquierda",
    "ataque centro": "Ataque Centro",
    "delantero centro": "Ataque Centro",
    "punta": "Ataque Centro",
    "ataque derecho": "Ataque Derecha",
    "delantero derecho": "Ataque Derecha",
    "extremo derecho": "Ataque Derecha",
    "delantero": "Ataque Centro",
    "atacante": "Ataque Centro",
    "delanztero": "Ataque Centro",  # typo fallback
}
POSITION_MAP = {
    "defensa izquierda": "Defensa Izquierda",
    "lateral izquierdo": "Defensa Izquierda",
    "carril izquierdo": "Defensa Izquierda",
    "izquierda": "Defensa Izquierda",
    "defensa central": "Defensa Centro",
    "central": "Defensa Centro",
    "defensa derecha": "Defensa Derecha",
    "lateral derecho": "Defensa Derecha",
    "carril derecho": "Defensa Derecha",
    "derecha": "Defensa Derecha",
    "medio izquierdo": "Medio Izquierdo",
    "medio centro": "Medio Centro",
    "mediocentro": "Medio Centro",
    "medio derecho": "Medio Derecho",
    "pivote": "Medio Centro",
    "delantero izquierdo": "Ataque Izquierda",
    "ataque izquierdo": "Ataque Izquierda",
    "extremo izquierdo": "Ataque Izquierda",
    "delantero centro": "Ataque Centro",
    "ataque centro": "Ataque Centro",
    "delantero derecho": "Ataque Derecha",
    "ataque derecho": "Ataque Derecha",
    "extremo derecho": "Ataque Derecha",
    "punta": "Ataque Centro",
    "delantero": "Ataque Centro",
    "atacante": "Ataque Centro",
}
TERCIO_MAP = {
    "ataque": "Ataque",
    "ofensivo": "Ataque",
    "zona ataque": "Ataque",
    "finalización": "Ataque",
    "propia": "Defensa",
    "defensa": "Defensa",
    "defensivo": "Defensa",
    "construccion": "Construcción",
    "construcción": "Construcción",
    "medio": "Construcción",
    "progresión": "Construcción",
    "posesión": "Construcción",
    "control": "Construcción",
    "ataque centro": "Ataque",
    "ataque izquierdo": "Ataque",
}
def _build_field_zones():
    sections = [
        {'key': 'Defensa', 'label': 'Defensa', 'left_pct': 0, 'width_pct': 35},
        {'key': 'Medio', 'label': 'Medio', 'left_pct': 35, 'width_pct': 30},
        {'key': 'Ataque', 'label': 'Ataque', 'left_pct': 65, 'width_pct': 35},
    ]
    lanes = [
        {'suffix': 'Izquierda', 'top_pct': 0, 'height_pct': 33},
        {'suffix': 'Centro', 'top_pct': 33, 'height_pct': 34},
        {'suffix': 'Derecha', 'top_pct': 67, 'height_pct': 33},
    ]
    zones = []
    for section in sections:
        for lane in lanes:
            key = f"{section['key']} {lane['suffix']}"
            label = f"{section['label']} {lane['suffix']}"
            zones.append(
                {
                    'key': key,
                    'label': label,
                    'left': f"{section['left_pct']}%",
                    'top': f"{lane['top_pct']}%",
                    'width': f"{section['width_pct']}%",
                    'height': f"{lane['height_pct']}%",
                    'left_pct': section['left_pct'],
                    'top_pct': lane['top_pct'],
                    'width_pct': section['width_pct'],
                    'height_pct': lane['height_pct'],
                }
            )
    return zones

FIELD_ZONES = _build_field_zones()
FIELD_ZONE_KEYS = [zone['key'] for zone in FIELD_ZONES]
STANDARD_TERCIO_LABELS = ['Ataque', 'Construcción', 'Defensa']
SHOT_KEYWORDS = {'tiro', 'remate', 'disparo', 'chuza', 'chute'}
PASS_KEYWORDS = {'pase', 'pases', 'pase clave', 'pase al hueco'}
GOAL_KEYWORDS = {'gol', 'goles', 'anotado', 'marcado', 'goal'}
ASSIST_KEYWORDS = {'asistencia', 'asist', 'pase gol', 'asiste'}
YELLOW_CARD_KEYWORDS = {'amarilla', 'tarjeta amarilla'}
RED_CARD_KEYWORDS = {'roja', 'tarjeta roja'}
SUBSTITUTION_KEYWORDS = {'sustitucion', 'sustitución', 'cambio'}
SUB_ENTRY_KEYWORDS = {'entrada', 'entrante', 'subida'}
SUB_EXIT_KEYWORDS = {'salida', 'saliente', 'bajada'}


def load_cached_next_match():
    if not NEXT_MATCH_CACHE.exists():
        return None
    try:
        with NEXT_MATCH_CACHE.open(encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                payload.setdefault("status", "next")
                return payload
    except Exception:
        return None
    return None


def dashboard_data(request):
    """Devuelve los datos principales que alimentarán la home cuerpo técnico/jugador."""
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)

    group = primary_team.group
    if not group:
        return JsonResponse({'error': 'El equipo principal no está asignado a ningún grupo'}, status=400)

    standings = serialize_standings(group)
    next_match = get_next_match(primary_team, group)
    team_metrics = compute_team_metrics(primary_team)
    player_metrics = compute_player_metrics(primary_team)
    player_cards = compute_player_cards(primary_team)

    return JsonResponse(
        {
            'team': {'name': primary_team.name, 'group': group.name},
            'standings': standings,
            'next_match': next_match,
            'team_metrics': team_metrics,
            'player_metrics': player_metrics,
            'player_cards': player_cards,
        }
    )


@ensure_csrf_cookie
def dashboard_page(request):
    sources = list(ScrapeSource.objects.filter(is_active=True))
    return render(
        request,
        'football/dashboard.html',
        {
            'scrape_sources': sources,
        },
    )


def player_dashboard_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    player_stats = compute_player_dashboard(primary_team)
    return render(
        request,
        'football/player_dashboard.html',
        {
            'player_stats': player_stats,
            'team_name': primary_team.name,
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


def get_current_convocation(team):
    record = ConvocationRecord.objects.filter(team=team, is_current=True).first()
    if record:
        return record.players.order_by('name')
    return Player.objects.filter(team=team, is_active=True).order_by('name')


def match_action_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    convocation_players = get_current_convocation(primary_team)
    message = None
    if request.method == 'POST':
        action = request.POST.get('action_type', '').strip()
        player_id = request.POST.get('player')
        player = convocation_players.filter(id=player_id).first()
        if action and player:
            message = f"Acción de partido para {player.name} registrada ({action})."
        else:
            message = "Completa el jugador y el tipo de acción."
    recent_events = (
        MatchEvent.objects.filter(
            Q(match__home_team=primary_team) | Q(match__away_team=primary_team)
        )
        .order_by('-created_at')[:6]
    )
    active_match = get_active_match(primary_team)
    match_info = None
    if active_match:
        opponent = active_match.away_team if active_match.home_team == primary_team else active_match.home_team
        match_info = {
            'opponent': opponent.name if opponent else 'Rival desconocido',
            'location': active_match.location or 'Campo oficial',
            'round': active_match.round or 'Partido sin jornada',
            'date': active_match.date.strftime('%d/%m/%Y') if active_match.date else None,
            'time': active_match.date.strftime('%H:%M') if active_match.date else '00:00',
        }
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
            category_rivals.append(
                {
                    'position': standing.position,
                    'name': team.name,
                    'short_name': team.short_name or team.name,
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
        },
    )


@require_POST
def register_match_action(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    player_id = request.POST.get('player')
    player = Player.objects.filter(team=primary_team, id=player_id).first()
    if not player:
        return JsonResponse({'error': 'Selecciona un jugador válido'}, status=400)
    action_type = (request.POST.get('action_type') or '').strip()
    if not action_type:
        return JsonResponse({'error': 'Especifica el tipo de acción'}, status=400)
    match = get_active_match(primary_team)
    if not match:
        return JsonResponse({'error': 'No hay partido disponible para registrar acciones'}, status=400)
    minute = _parse_int(request.POST.get('minute'))
    if minute is not None:
        minute = max(0, min(minute, 120))
    result = (request.POST.get('result') or '').strip()
    zone = (request.POST.get('zone') or '').strip()
    tercio = zone_to_tercio(zone) or (request.POST.get('tercio') or '').strip()
    observation = (request.POST.get('observation') or '').strip()
    event = MatchEvent.objects.create(
        match=match,
        player=player,
        minute=minute if minute is not None else None,
        event_type=action_type,
        result=result,
        zone=zone,
        tercio=tercio,
        observation=observation,
        source_file='registro-acciones',
        system='touch-field',
    )
    return JsonResponse(
        {
            'id': event.id,
            'minute': event.minute,
            'action': event.event_type,
            'zone': event.zone,
            'result': event.result,
            'player': {
                'id': player.id,
                'name': player.name,
                'number': player.number or '--',
            },
        }
    )


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
    return JsonResponse(
        {
            'id': event.id,
            'minute': event.minute,
            'action': event.event_type,
            'zone': event.zone,
            'result': event.result,
            'event_id': event.id,
            'player': {
                'id': player.id,
                'name': player.name,
                'number': player.number or '--',
            },
        }
    )


@require_POST
def finalize_match_actions(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    match = get_active_match(primary_team)
    if not match:
        return JsonResponse({'error': 'No hay partido activo para guardar'}, status=400)
    pending_events = list(
        MatchEvent.objects.filter(match=match, system='touch-field').select_related('player')
    )
    if not pending_events:
        return JsonResponse({'saved': True, 'updated': 0, 'match_id': match.id})
    try:
        rows_written = append_events_to_bd_eventos(match, primary_team, pending_events)
    except Exception as exc:
        return JsonResponse({'error': f'No se pudo escribir en BD_EVENTOS: {exc}'}, status=500)
    updated = MatchEvent.objects.filter(id__in=[event.id for event in pending_events]).update(
        system='touch-field-final'
    )
    return JsonResponse(
        {
            'saved': True,
            'updated': updated,
            'rows_written': rows_written,
            'match_id': match.id,
        }
    )


def convocation_page(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    players = Player.objects.filter(team=primary_team).order_by('name')
    return render(
        request,
        'football/convocation.html',
        {
            'players': players,
        'team_name': primary_team.name,
    },
)


@require_POST
def save_convocation(request):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'Equipo principal no configurado'}, status=400)
    try:
        payload = json.loads(request.body or '[]')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato JSON inválido'}, status=400)
    player_ids = [int(pid) for pid in payload if pid]
    players = Player.objects.filter(team=primary_team, id__in=player_ids)
    if not players.exists():
        return JsonResponse({'error': 'No se encontraron jugadores para la convocatoria'}, status=400)
    ConvocationRecord.objects.filter(team=primary_team, is_current=True).update(is_current=False)
    record = ConvocationRecord.objects.create(team=primary_team)
    record.players.set(players.distinct())
    return JsonResponse({'saved': True, 'count': players.count()})


def coach_cards_page(request):
    cards = [
        {
            'title': 'Convocatoria',
            'description': 'Lista oficial de jugadores llamados a la siguiente jornada.',
            'link': 'convocation',
        },
        {
            'title': '11 inicial',
            'description': 'Selecciona el once titular y arma las instrucciones.',
            'link': 'initial-eleven',
        },
        {
            'title': 'Sesiones',
            'description': 'Planifica entrenamientos y prepara las unidades.',
            'link': 'sessions',
        },
        {
            'title': 'Multas',
            'description': 'Controla sanciones y comportamientos disciplinarios.',
            'link': 'fines',
        },
    ]
    return render(
        request,
        'football/coach_cards.html',
        {
            'cards': cards,
        },
    )


def initial_eleven_page(request):
    return render(
        request,
        'football/coach_section.html',
        {
            'section_title': '11 Inicial',
            'description': 'Selecciona el once titular y fija roles/zonas priorizadas.',
            'items': ['Titular 1', 'Titular 2', 'Titular 3'],
        },
    )


def sessions_page(request):
    return render(
        request,
        'football/coach_section.html',
        {
            'section_title': 'Sesiones',
            'description': 'Agenda de entrenamientos de la semana.',
            'items': ['Martes · Táctica ofensiva', 'Jueves · Transiciones'],
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
    team_url = ''
    team_id = ''
    raw_text = ''
    roster = []
    probable_eleven = []
    insights = {}
    formation = 'Auto'
    error = ''
    if request.method == 'POST':
        team_url = (request.POST.get('team_url') or '').strip()
        team_id = (request.POST.get('team_id') or '').strip()
        raw_text = (request.POST.get('raw_text') or '').strip()
        team = None
        if team_id:
            team = Team.objects.filter(id=team_id).first()
            if team and not team_url:
                team_url = team.preferente_url or ''
        try:
            if raw_text:
                roster = parse_preferente_roster(raw_text)
            elif team_url:
                roster = fetch_preferente_team_roster(team_url)
            probable_eleven = compute_probable_eleven(roster)
            insights = build_rival_insights(roster)
            formation = compute_formation(probable_eleven)
            if not roster:
                error = 'No se han encontrado jugadores en la plantilla.'
        except Exception as exc:
            error = f'No se ha podido procesar la plantilla del rival. {exc}'
        if team and team_url and team.preferente_url != team_url:
            team.preferente_url = team_url
            team.save(update_fields=['preferente_url'])
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
            'insights': insights,
            'formation': formation,
            'error': error,
        },
    )


def player_detail_page(request, player_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)
    player = Player.objects.filter(id=player_id, team=primary_team).first()
    if not player:
        return JsonResponse({'error': 'Jugador no encontrado'}, status=404)
    if request.method == 'POST':
        number = request.POST.get('number', '').strip()
        position = request.POST.get('position', '').strip()
        player.number = int(number) if number else None
        player.position = position
        player.save()
        return redirect('player-detail', player_id=player.id)
    matches = compute_player_dashboard(primary_team)
    detail = next((p for p in matches if p.get('player_id') == player_id), None)
    return render(
        request,
        'football/player_detail.html',
        {
            'player': player,
            'stats': detail or {},
        },
    )


def player_pdf(request, player_id):
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        raise Http404('Equipo principal no configurado')
    if not weasyprint:
        raise Http404('La generación de PDF no está disponible en este entorno')
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
    pdf_file = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = slugify(player.name or 'jugador')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response


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


@require_POST
def refresh_scraping(request):
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
    return JsonResponse({'status': 'success', 'message': 'Clasificación actualizada desde RFAF.'})


def serialize_standings(group):
    standings = TeamStanding.objects.filter(group=group).order_by('position')
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
    today = timezone.localdate()
    base_qs = (
        Match.objects.filter(group=group)
        .filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .select_related('home_team', 'away_team')
    )

    upcoming = base_qs.filter(date__gte=today).order_by('date').first()
    if upcoming:
        return build_match_payload(upcoming, primary_team, status='next')

    cached = load_cached_next_match()
    if cached:
        return cached

    latest = base_qs.exclude(date__isnull=True).order_by('-date').first()
    if not latest:
        latest = base_qs.order_by('-id').first()
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
    latest = qs.exclude(date__isnull=True).order_by('-date').first()
    if latest:
        return latest
    return qs.order_by('-id').first()


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
    return {
        'round': match.round,
        'date': match.date.isoformat() if match.date else None,
        'location': match.location,
        'opponent': {'name': opponent.name if opponent else 'Rival desconocido'},
        'home': match.home_team == primary_team,
        'status': status,
    }


def confirmed_events_queryset():
    return MatchEvent.objects.exclude(system='touch-field')


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


def compute_player_cards_for_match(match, primary_team):
    events = confirmed_events_queryset().filter(match=match, player__team=primary_team)
    aggregated = (
        events.values('player__id', 'player__name', 'player__number')
        .annotate(
            actions=Count('id'),
            successful=Count('id', filter=Q(result__iexact='OK')),
        )
        .order_by('-actions')
    )
    cards = []
    for item in aggregated:
        total_actions = item['actions']
        success = item['successful']
        cards.append(
            {
                'player_id': item['player__id'],
                'name': item['player__name'],
                'number': item.get('player__number') or '--',
                'actions': total_actions,
                'successes': success,
                'success_rate': round((success / total_actions) * 100, 1) if total_actions else 0,
            }
        )
    return cards

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
    players = compute_player_dashboard(primary_team)
    cards = []
    seen_keys = set()
    for player in players:
        key = canonical_roster_key(player['name'])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cards.append(
            {
                'player_id': player['player_id'],
                'name': player['name'],
                'pj': player.get('pj', 0),
                'pt': player.get('pt', 0),
                'minutes': player.get('minutes', 0),
                'goals': player.get('goals', 0),
                'yellow_cards': player.get('yellow_cards', 0),
                'red_cards': player.get('red_cards', 0),
                'actions': player['total_actions'],
                'successes': player['successes'],
                'success_rate': round((player['successes'] / player['total_actions']) * 100)
                if player['total_actions']
                else 0,
            }
        )
    return cards


def result_is_success(result):
    if not result:
        return False
    normalized = result.strip().lower()
    return normalized in SUCCESS_RESULTS


def normalize_label(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    filtered = "".join(ch for ch in normalized if ch.isalnum() or ch.isspace())
    return filtered.lower().strip()


def contains_keyword(value, keywords):
    normalized = normalize_label(value)
    return any(keyword in normalized for keyword in keywords)

def is_goal_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, GOAL_KEYWORDS)
        or contains_keyword(result, GOAL_KEYWORDS)
        or contains_keyword(observation, GOAL_KEYWORDS)
    )


def is_assist_event(event_type, result=None, observation=None):
    return (
        contains_keyword(event_type, ASSIST_KEYWORDS)
        or contains_keyword(result, ASSIST_KEYWORDS)
        or contains_keyword(observation, ASSIST_KEYWORDS)
    )


def is_yellow_card_event(event_type, result=None, zone=None):
    return (
        contains_keyword(event_type, YELLOW_CARD_KEYWORDS)
        or contains_keyword(result, YELLOW_CARD_KEYWORDS)
        or contains_keyword(zone, YELLOW_CARD_KEYWORDS)
    )


def is_red_card_event(event_type, result=None, zone=None):
    return (
        contains_keyword(event_type, RED_CARD_KEYWORDS)
        or contains_keyword(result, RED_CARD_KEYWORDS)
        or contains_keyword(zone, RED_CARD_KEYWORDS)
    )


def is_substitution_event(event_type, zone=None):
    return contains_keyword(event_type, SUBSTITUTION_KEYWORDS) or contains_keyword(zone, SUBSTITUTION_KEYWORDS)


def is_substitution_entry(event_type, result=None, zone=None):
    if not is_substitution_event(event_type, zone):
        return False
    return contains_keyword(result, SUB_ENTRY_KEYWORDS) or contains_keyword(zone, SUB_ENTRY_KEYWORDS)


def is_substitution_exit(event_type, result=None, zone=None):
    if not is_substitution_event(event_type, zone):
        return False
    return contains_keyword(result, SUB_EXIT_KEYWORDS) or contains_keyword(zone, SUB_EXIT_KEYWORDS)


def min_or_none(current, candidate):
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)


def extract_round_number(value):
    if not value:
        return None
    match = re.search(r'(\d+)', str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def is_duel_event(event_type, observation=None):
    normalized = normalize_label(event_type)
    if not normalized:
        return False
    for keyword in DUEL_EVENT_KEYWORDS:
        if keyword in normalized:
            return True
    if observation:
        for keyword in DUEL_EVENT_KEYWORDS:
            if keyword in normalize_label(observation):
                return True
    return False


def duel_result_is_success(result):
    if not result:
        return False
    normalized = result.strip().lower()
    return any(keyword in normalized for keyword in DUEL_SUCCESS_KEYWORD)


def categorize_position(player_position, zone):
    normalized_position = normalize_label(player_position)
    normalized_zone = normalize_label(zone)
    for key, label in sorted(POSITION_MAP.items(), key=lambda item: -len(item[0])):
        if key in normalized_position or key in normalized_zone:
            return label
    return None


def zone_to_tercio(zone_label):
    normalized = normalize_label(zone_label)
    if not normalized:
        return ''
    if 'defensa' in normalized:
        return 'Defensa'
    if 'medio' in normalized or 'construcción' in normalized:
        return 'Construcción'
    if 'ataque' in normalized:
        return 'Ataque'
    return ''


def map_tercio(raw):
    normalized = normalize_label(raw)
    for key, label in TERCIO_MAP.items():
        if key in normalized:
            return label
    return None


def map_zone_label(zone):
    normalized = normalize_label(zone)
    for key, label in sorted(ZONE_MAP.items(), key=lambda item: -len(item[0])):
        if key in normalized:
            return label
    return None


def compute_player_dashboard(primary_team):
    player_stats = {}
    roster_cache = get_roster_stats_cache()
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
    for event in events:
        player = event.player
        if not player:
            continue
        match = event.match
        roster_entry = find_roster_entry(player.name, roster_cache)
        base_pc = roster_entry.get('pc', 0) if roster_entry else 0
        base_pj = roster_entry.get('pj', 0) if roster_entry else 0
        base_pt = roster_entry.get('pt', 0) if roster_entry else 0
        base_minutes = roster_entry.get('minutes', 0) if roster_entry else 0
        base_goals = roster_entry.get('goals', 0) if roster_entry else 0
        base_yellow = roster_entry.get('yellow_cards', 0) if roster_entry else 0
        base_red = roster_entry.get('red_cards', 0) if roster_entry else 0
        base_assists = roster_entry.get('assists', 0) if roster_entry else 0
        stats = player_stats.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'position': player.position or (roster_entry.get('position') if roster_entry else ''),
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
                'age': roster_entry.get('age') if roster_entry else None,
                'has_events': False,
            },
        )
        stats['has_events'] = True
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
            stats['minutes'] += max(0, exit_minute - entry_minute)
            stats['pj'] += 1 if timeline.get('has_event') else 0
            if entry_minute == 0:
                stats['pt'] += 1
        stats['pc'] = max(stats.get('pc', 0), stats['pj'])
    # ensure roster players appear even without events
    roster_players = Player.objects.filter(team=primary_team)
    for player in roster_players:
        if player.id not in player_stats:
            normalized = normalize_player_name(player.name)
            roster_entry = roster_cache.get(normalized, {})
            player_stats[player.id] = {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'position': player.position or roster_entry.get('position'),
                'total_actions': 0,
                'successes': 0,
                'pc': roster_entry.get('pc', 0),
                'pj': roster_entry.get('pj', 0),
                'pt': roster_entry.get('pt', 0),
                'minutes': roster_entry.get('minutes', 0),
                'goals': roster_entry.get('goals', 0),
                'yellow_cards': roster_entry.get('yellow_cards', 0),
                'red_cards': roster_entry.get('red_cards', 0),
                'assists': roster_entry.get('assists', 0),
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
                'age': roster_entry.get('age'),
                'has_events': False,
            }

    result = []
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
            'dominant_position': position_list[0][0] if position_list else player.position,
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
        result.append(merged)
    return sorted(result, key=lambda player: player['total_actions'], reverse=True)
