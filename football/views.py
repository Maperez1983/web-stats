import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
import unicodedata
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max, Q
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
except Exception:  # pragma: no cover
    weasyprint = None

from football.models import (
    Match,
    MatchEvent,
    Player,
    PlayerStatistic,
    ScrapeSource,
    Season,
    Team,
    TeamStanding,
    ConvocationRecord,
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
SCRAPE_LOCK_KEY = "football:refresh_scraping_running"
SCRAPE_LOCK_TIMEOUT_SECONDS = 900


def authenticated_write(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Autenticación requerida'}, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped


def load_cached_next_match():
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

    if not NEXT_MATCH_CACHE.exists():
        return None
    try:
        with NEXT_MATCH_CACHE.open(encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
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


@login_required
def dashboard_data(request):
    """Devuelve los datos principales que alimentarán la home cuerpo técnico/jugador."""
    primary_team = Team.objects.filter(is_primary=True).first()
    if not primary_team:
        return JsonResponse({'error': 'No hay equipo principal configurado'}, status=400)

    group = primary_team.group
    if not group:
        return JsonResponse({'error': 'El equipo principal no está asignado a ningún grupo'}, status=400)
    try:
        refresh_primary_roster_cache(primary_team, force=True)
    except Exception:
        pass

    standings = serialize_standings(group)
    next_match = get_next_match(primary_team, group)
    team_metrics = compute_team_metrics(primary_team)
    player_metrics = compute_player_metrics(primary_team)
    player_cards = compute_player_cards(primary_team)
    player_cards_scope = {'type': 'global', 'label': 'Jugador · datos La Preferente'}

    return JsonResponse(
        {
            'team': {'name': primary_team.name, 'group': group.name},
            'standings': standings,
            'next_match': next_match,
            'team_metrics': team_metrics,
            'player_metrics': player_metrics,
            'player_cards': player_cards,
            'player_cards_scope': player_cards_scope,
        }
    )


@login_required
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
            'substitution_history': substitution_history,
        },
    )


@authenticated_write
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
    period = _parse_int(request.POST.get('period'))
    result = (request.POST.get('result') or '').strip()
    zone = (request.POST.get('zone') or '').strip()
    tercio = zone_to_tercio(zone)
    observation = (request.POST.get('observation') or '').strip()
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
    return JsonResponse(
        {
            'id': event.id,
            'minute': event.minute,
            'period': event.period,
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
    players = Player.objects.filter(team=primary_team).order_by('name')
    return render(
        request,
        'football/convocation.html',
        {
            'players': players,
        'team_name': primary_team.name,
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
    try:
        player_ids = [int(pid) for pid in payload if pid]
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Formato de jugadores inválido'}, status=400)
    players = Player.objects.filter(team=primary_team, id__in=player_ids)
    if not players.exists():
        return JsonResponse({'error': 'No se encontraron jugadores para la convocatoria'}, status=400)
    with transaction.atomic():
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
    lineup = []
    insights = {}
    formation = 'Auto'
    error = ''
    auto_loaded = False
    auto_team_name = ''
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
        primary_team = Team.objects.filter(is_primary=True).first()
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
                    'manual_yellow_cards': _parse_int(request.POST.get(f'yellow_{player.id}')) or 0,
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
                'yellow_cards': manual.get('yellow_cards', roster_entry.get('yellow_cards', 0)),
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
    except Exception as e:
        import logging
        logging.exception(f"Error en player_detail_page para player_id={player_id}")
        return HttpResponse(f"Error interno: {e}", status=500)




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
    roster_ok, roster_message = refresh_primary_roster_cache(primary_team, force=True)
    roster_status = 'y plantilla actualizada' if roster_ok else f'plantilla no actualizada ({roster_message})'
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
            return payload
        except Exception:
            return None

    today = timezone.localdate()
    all_team_matches_qs = (
        Match.objects.filter(Q(home_team=primary_team) | Q(away_team=primary_team))
        .select_related('home_team', 'away_team')
    )
    scoped_qs = all_team_matches_qs.filter(group=group) if group else all_team_matches_qs

    upcoming = scoped_qs.filter(date__gte=today).order_by('date').first()
    if not upcoming:
        upcoming = all_team_matches_qs.filter(date__gte=today).order_by('date').first()
    if upcoming:
        return build_match_payload(upcoming, primary_team, status='next')

    cached = load_cached_next_match()
    if cached:
        return cached

    rfaf_fallback = _fetch_next_from_rfaf()
    if rfaf_fallback:
        return rfaf_fallback

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
        data = per_player.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number or '--',
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
    cards = []
    for player in Player.objects.filter(team=primary_team).order_by('name'):
        roster_entry = find_roster_entry(player.name, roster_cache) or {}
        cards.append(
            {
                'player_id': player.id,
                'name': player.name,
                'pj': int(roster_entry.get('pj', 0) or 0),
                'minutes': int(roster_entry.get('minutes', 0) or 0),
                'goals': int(roster_entry.get('goals', 0) or 0),
                'yellow_cards': int(roster_entry.get('yellow_cards', 0) or 0),
                'red_cards': int(roster_entry.get('red_cards', 0) or 0),
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
            name__in=['manual_pj', 'manual_pt', 'manual_minutes', 'manual_yellow_cards'],
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
        elif stat.name == 'manual_yellow_cards':
            player_data['yellow_cards'] = value
    return overrides


def compute_player_dashboard(primary_team):
    player_stats = {}
    roster_cache = get_roster_stats_cache()
    manual_overrides = get_manual_player_base_overrides(primary_team)
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
        base_pj = manual_entry.get('pj', roster_entry.get('pj', 0))
        base_pt = manual_entry.get('pt', roster_entry.get('pt', 0))
        base_minutes = manual_entry.get('minutes', roster_entry.get('minutes', 0))
        base_pc = max(roster_entry.get('pc', 0), base_pj)
        base_goals = roster_entry.get('goals', 0)
        base_yellow = manual_entry.get('yellow_cards', roster_entry.get('yellow_cards', 0))
        base_red = roster_entry.get('red_cards', 0)
        base_assists = roster_entry.get('assists', 0)
        stats = player_stats.setdefault(
            player.id,
            {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'position': player.position or roster_entry.get('position', ''),
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
                'age': roster_entry.get('age'),
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
    roster_players = Player.objects.filter(team=primary_team)
    for player in roster_players:
        if player.id not in player_stats:
            normalized = normalize_player_name(player.name)
            roster_entry = roster_cache.get(normalized, {})
            manual_entry = manual_overrides.get(player.id, {})
            base_pj = manual_entry.get('pj', roster_entry.get('pj', 0))
            base_pt = manual_entry.get('pt', roster_entry.get('pt', 0))
            player_stats[player.id] = {
                'player_id': player.id,
                'name': player.name,
                'number': player.number,
                'position': player.position or roster_entry.get('position'),
                'total_actions': 0,
                'successes': 0,
                'pc': max(roster_entry.get('pc', 0), base_pj),
                'pj': base_pj,
                'pt': base_pt,
                'minutes': manual_entry.get('minutes', roster_entry.get('minutes', 0)),
                'goals': roster_entry.get('goals', 0),
                'yellow_cards': manual_entry.get('yellow_cards', roster_entry.get('yellow_cards', 0)),
                'red_cards': roster_entry.get('red_cards', 0),
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
                'age': roster_entry.get('age'),
                'has_events': base_pj > 0,
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
        profile, profile_label, smart_kpis = build_smart_kpis(stats)
        merged['profile'] = profile
        merged['profile_label'] = profile_label
        merged['smart_kpis'] = smart_kpis
        result.append(merged)
    return sorted(
        result,
        key=lambda entry: (-entry.get('total_actions', 0), -entry.get('pj', 0), entry.get('name', '')),
    )
