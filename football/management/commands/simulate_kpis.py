from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from football.manual_stats import save_manual_player_base_overrides
from football.event_taxonomy import FIELD_ZONE_KEYS, STANDARD_TERCIO_LABELS
from football.models import (
    AppUserRole,
    Competition,
    ConvocationRecord,
    Group,
    Match,
    MatchEvent,
    Player,
    PlayerInjuryRecord,
    Season,
    Team,
    Workspace,
    WorkspaceTeam,
    WorkspaceMembership,
)
from football.views import compute_player_dashboard, kpi_audit, player_dashboard_page, player_detail_page


def _make_request(user, *, path='/', method='get', session_data=None, query_string=''):
    rf = RequestFactory()
    if method.lower() == 'post':
        req = rf.post(f'{path}{query_string}')
    else:
        req = rf.get(f'{path}{query_string}')
    req.user = user
    # session
    SessionMiddleware(lambda r: None).process_request(req)
    if session_data:
        for key, value in session_data.items():
            req.session[key] = value
    req.session.save()
    # messages
    setattr(req, '_messages', FallbackStorage(req))
    # accept html
    req.META['HTTP_ACCEPT'] = 'text/html'
    return req


@dataclass(frozen=True)
class ScenarioConfig:
    key: str
    label: str
    teams_count: int = 15
    matches_count: int = 3
    players_count: int = 6
    game_format: str = 'f11'  # f11|f7
    with_group: bool = True
    add_end_marker: bool = True
    end_minute_override: int | None = None
    substitutions: bool = False
    duplicate_events: bool = False
    mixed_sources: bool = False
    missing_zone_inference: bool = False
    manual_lock_assists: bool = False
    manual_lock_totals: bool = False
    isolate_no_group_name_collision: bool = False
    rotate_absences: bool = False
    starter_without_events: bool = False
    include_cards: bool = False
    include_injury: bool = False
    include_sanction: bool = False
    live_events: bool = False


def _write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def _write_bytes(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _request_json(user, *, path: str, session_data: dict, query: str):
    req = _make_request(user, path=path, session_data=session_data, query_string=query)
    # For JSON views
    req.META['HTTP_ACCEPT'] = 'application/json'
    return req


def _run_scenario(*, config: ScenarioConfig, base_output_dir: Path, render_html: bool, persist_db: bool) -> dict:
    run_id = uuid.uuid4().hex[:8]
    scenario_dir = base_output_dir / f'{config.key}-{run_id}'
    scenario_dir.mkdir(parents=True, exist_ok=True)

    def _pick_zone(player_obj, match_index: int) -> str:
        if not FIELD_ZONE_KEYS:
            return 'Medio Centro'
        seed = int((player_obj.number or 0) + (match_index * 3))
        return FIELD_ZONE_KEYS[seed % len(FIELD_ZONE_KEYS)]

    def _pick_tercio(player_obj, match_index: int) -> str:
        if not STANDARD_TERCIO_LABELS:
            return 'Construcción'
        seed = int((player_obj.number or 0) + match_index)
        return STANDARD_TERCIO_LABELS[seed % len(STANDARD_TERCIO_LABELS)]

    with transaction.atomic():
        # Admin user for rendering views.
        user_model = get_user_model()
        admin_user, _ = user_model.objects.get_or_create(
            username=f'sim-admin-{config.key}-{run_id}',
            defaults={
                'email': f'sim-admin-{config.key}-{run_id}@example.com',
                'is_staff': True,
            },
        )
        if not hasattr(admin_user, 'app_role'):
            AppUserRole.objects.create(user=admin_user, role=AppUserRole.ROLE_ADMIN)
        else:
            AppUserRole.objects.filter(user=admin_user).update(role=AppUserRole.ROLE_ADMIN)

        competition = Competition.objects.create(
            name=f'Sim KPI {config.key} {run_id}',
            slug=f'sim-kpi-{config.key}-{run_id}',
            region='Sim',
        )
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = None
        if config.with_group:
            group = Group.objects.create(season=season, name=f'Grupo {config.key} {run_id}', slug=f'grupo-{config.key}-{run_id}')

        game_format = config.game_format.strip().lower()
        regulation_minutes = 50 if game_format == 'f7' else 90
        end_minute = int(config.end_minute_override) if config.end_minute_override else regulation_minutes
        club = Team.objects.create(
            name=f'Club KPI {config.key} {run_id}',
            slug=f'club-kpi-{config.key}-{run_id}',
            short_name=f'Club {config.key}'.upper(),
            group=group,
            is_primary=True,
            game_format=Team.GAME_FORMAT_F7 if game_format == 'f7' else Team.GAME_FORMAT_F11,
        )

        # Optional: create another team with same name/no-group to stress isolation logic.
        collision_team = None
        if config.isolate_no_group_name_collision and not config.with_group:
            collision_team = Team.objects.create(
                name=club.name,
                slug=f'club-kpi-collision-{config.key}-{run_id}',
                short_name=club.short_name,
                group=None,
                is_primary=False,
                game_format=club.game_format,
            )

        opponents = []
        for idx in range(max(2, int(config.teams_count)) - 1):
            opponents.append(
                Team.objects.create(
                    name=f'Rival {idx + 1} {config.key} {run_id}',
                    slug=f'rival-{idx + 1}-{config.key}-{run_id}',
                    short_name=f'Rival {idx + 1}',
                    group=group,
                )
            )

        # Workspace to enable modules
        workspace = Workspace.objects.create(
            name=f'Workspace KPI {config.key} {run_id}',
            slug=f'ws-kpi-{config.key}-{run_id}',
            kind=Workspace.KIND_CLUB,
            primary_team=club,
            owner_user=admin_user,
            enabled_modules={'dashboard': True, 'players': True, 'convocation': True, 'match_actions': True},
        )
        WorkspaceTeam.objects.create(workspace=workspace, team=club, is_default=True)
        WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=admin_user,
            defaults={'role': WorkspaceMembership.ROLE_OWNER},
        )

        players = []
        for idx in range(max(1, int(config.players_count))):
            pos = 'POR' if idx == 0 else ('DC' if idx == 1 else ('ED' if idx == 2 else 'MC'))
            players.append(
                Player.objects.create(
                    team=club,
                    name=f'Jugador {idx + 1} {config.key} {run_id}',
                    full_name=f'Jugador {idx + 1} {config.key} {run_id}',
                    position=pos,
                    number=idx + 1,
                )
            )

        # Manual locks (manual-base stats)
        if config.manual_lock_assists or config.manual_lock_totals:
            # Ensure season is current and resolvable.
            for player in players:
                values = {
                    'manual_pj': 0,
                    'manual_pt': 0,
                    'manual_minutes': 0,
                    'manual_goals': 0,
                    'manual_assists': 0,
                    'manual_yellow_cards': 0,
                    'manual_red_cards': 0,
                }
                if config.manual_lock_assists:
                    values['manual_assists'] = 2
                if config.manual_lock_totals:
                    values['manual_pj'] = 5
                    values['manual_pt'] = 4
                    values['manual_minutes'] = 300
                    values['manual_goals'] = 3
                save_manual_player_base_overrides(player=player, season=season, values=values)

        if config.include_injury and players:
            PlayerInjuryRecord.objects.create(
                player=players[-1],
                injury='Sim lesión',
                injury_type='Muscular',
                injury_zone='Pierna',
                injury_side='Derecha',
                injury_date=timezone.localdate() - timedelta(days=5),
                return_date=None,
                is_active=True,
            )

        if config.include_sanction and players:
            players[-1].manual_sanction_active = True
            players[-1].manual_sanction_reason = 'Sim sanción'
            players[-1].manual_sanction_until = timezone.localdate() + timedelta(days=7)
            players[-1].save(update_fields=['manual_sanction_active', 'manual_sanction_reason', 'manual_sanction_until'])

        today = timezone.localdate()
        for match_index in range(max(1, int(config.matches_count))):
            opponent = opponents[match_index % len(opponents)]
            match = Match.objects.create(
                season=season,
                group=group,
                round=str(match_index + 1) if match_index % 2 == 0 else f'J{match_index + 1}',
                date=today - timedelta(days=(max(1, int(config.matches_count)) - match_index) * 7),
                home_team=club,
                away_team=opponent,
            )

            conv = ConvocationRecord.objects.create(
                team=club,
                match=match,
                round=f'J{match_index + 1}',
                match_date=match.date,
                match_time=timezone.localtime().time().replace(second=0, microsecond=0),
                location='Campo Sim',
                opponent_name=opponent.display_name,
                is_current=(match_index == max(1, int(config.matches_count)) - 1),
            )
            conv_players = list(players)
            if config.rotate_absences and len(conv_players) >= 3:
                missing = conv_players[match_index % len(conv_players)]
                conv_players = [p for p in conv_players if p.id != missing.id]
            conv.players.set(conv_players)
            starters_limit = 7 if game_format == 'f7' else 11
            starters = conv_players[: min(len(conv_players), starters_limit)]
            bench = conv_players[min(len(conv_players), starters_limit) :]
            conv.lineup_data = {
                'starters': [{'id': str(p.id)} for p in starters],
                'bench': [{'id': str(p.id)} for p in bench],
            }
            conv.captain = starters[1] if len(starters) > 1 else starters[0]
            conv.goalkeeper = starters[0]
            conv.save(update_fields=['lineup_data', 'captain', 'goalkeeper'])

            # Optional match end marker
            if config.add_end_marker:
                MatchEvent.objects.create(
                    match=match,
                    player=None,
                    minute=end_minute,
                    period=2,
                    event_type='FIN',
                    result='OK',
                    zone='',
                    tercio='',
                    observation='Fin partido',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )

            # Base player events (para asegurar que aparecen en el dashboard)
            silent_starter_id = None
            if config.starter_without_events and starters:
                silent_starter_id = starters[-1].id
            for player in starters + bench:
                if silent_starter_id and player.id == silent_starter_id:
                    continue
                zone_value = _pick_zone(player, match_index)
                if config.missing_zone_inference and player.position != 'POR':
                    zone_value = '' if (player.number or 0) % 2 == 0 else 'Medio Centro'
                system_value = 'touch-field-final'
                if config.live_events and (player.number or 0) % 2 == 0:
                    system_value = 'touch-field'
                source_value = 'registro-acciones'
                if config.mixed_sources and (player.number or 0) % 2 == 0:
                    source_value = 'BDT PARTIDOS BENABALBON.xlsm'
                    system_value = 'touch-field-final'
                MatchEvent.objects.create(
                    match=match,
                    player=player,
                    minute=10 + match_index,
                    period=1,
                    event_type='Pase',
                    result='OK',
                    zone=zone_value,
                    tercio=_pick_tercio(player, match_index),
                    observation='',
                    system=system_value,
                    source_file=source_value,
                )
                if config.duplicate_events and player.number == 1:
                    MatchEvent.objects.create(
                        match=match,
                        player=player,
                        minute=10 + match_index,
                        period=1,
                        event_type='Pase',
                        result='OK',
                        zone=zone_value,
                        tercio=_pick_tercio(player, match_index),
                        observation='',
                        system=system_value,
                        source_file=source_value,
                    )

            # Make player 2 score in match 1; player 3 assist in match 1.
            if match_index == 0 and len(players) >= 3:
                MatchEvent.objects.create(
                    match=match,
                    player=players[2],
                    minute=18,
                    period=1,
                    event_type='Asistencia',
                    result='OK',
                    zone='Ataque Centro',
                    tercio='Ataque',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )
                MatchEvent.objects.create(
                    match=match,
                    player=players[1],
                    minute=19,
                    period=1,
                    event_type='Gol',
                    result='Gol',
                    zone='Área',
                    tercio='Ataque',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )

            if config.include_cards and players:
                MatchEvent.objects.create(
                    match=match,
                    player=players[1],
                    minute=22,
                    period=1,
                    event_type='Tarjeta amarilla',
                    result='OK',
                    zone='',
                    tercio='',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )
                MatchEvent.objects.create(
                    match=match,
                    player=players[1],
                    minute=44,
                    period=2,
                    event_type='Tarjeta roja',
                    result='OK',
                    zone='',
                    tercio='',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )

            # Substitution timeline scenario (bench comes in, starter goes out)
            if config.substitutions and len(starters) >= 2 and bench:
                starter_out = starters[-1]
                bench_in = bench[0]
                sub_minute = 30 if game_format == 'f7' else 55
                MatchEvent.objects.create(
                    match=match,
                    player=starter_out,
                    minute=sub_minute,
                    period=2,
                    event_type='Sustitución',
                    result='Salida',
                    zone='',
                    tercio='',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )
                MatchEvent.objects.create(
                    match=match,
                    player=bench_in,
                    minute=sub_minute,
                    period=2,
                    event_type='Sustitución',
                    result='Entrada',
                    zone='',
                    tercio='',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )

            if collision_team:
                # Create unrelated match/events for collision_team; should not affect club KPIs.
                other_match = Match.objects.create(
                    season=season,
                    group=None,
                    round=f'X{match_index + 1}',
                    date=match.date,
                    home_team=collision_team,
                    away_team=opponent,
                )
                MatchEvent.objects.create(
                    match=other_match,
                    player=None,
                    minute=end_minute,
                    period=2,
                    event_type='FIN',
                    result='OK',
                    zone='',
                    tercio='',
                    observation='Fin partido',
                    system='touch-field-final',
                    source_file='registro-acciones',
                )

        # Compute + dump results
        dashboard = compute_player_dashboard(club, force_refresh=True)
        _write_text(scenario_dir / 'scenario.json', json.dumps(config.__dict__, ensure_ascii=False, indent=2))
        _write_text(scenario_dir / 'kpis.json', json.dumps(dashboard, ensure_ascii=False, indent=2))

        session_data = {
            'active_workspace_id': int(workspace.id),
            'active_team_by_workspace': {str(workspace.id): int(club.id)},
        }

        if render_html:
            # Render dashboard + each player detail
            dash_req = _make_request(admin_user, path=reverse('player-dashboard'), session_data=session_data, query_string='?refresh=1')
            dash_resp = player_dashboard_page(dash_req)
            _write_bytes(scenario_dir / 'player_dashboard.html', dash_resp.content)
            for player in players:
                detail_req = _make_request(admin_user, path=reverse('player-detail', args=[player.id]), session_data=session_data, query_string='?refresh=1')
                resp = player_detail_page(detail_req, player.id)
                _write_bytes(scenario_dir / f'player_{player.id}.html', resp.content)

        # KPI audit JSON from admin endpoint logic
        audit_req = _request_json(admin_user, path=reverse('kpi-audit'), session_data=session_data, query=f'?team_id={club.id}&refresh=1')
        audit_resp = kpi_audit(audit_req)
        audit_payload = {}
        try:
            audit_payload = json.loads(audit_resp.content.decode('utf-8'))
        except Exception:
            audit_payload = {'ok': False, 'error': 'No JSON'}
        _write_text(scenario_dir / 'kpi_audit.json', json.dumps(audit_payload, ensure_ascii=False, indent=2))

        result = {
            'key': config.key,
            'label': config.label,
            'dir': str(scenario_dir),
            'team_id': int(club.id),
            'workspace_id': int(workspace.id),
            'persisted': bool(persist_db),
            'audit_summary': audit_payload.get('summary') if isinstance(audit_payload, dict) else {},
        }
        if not persist_db:
            transaction.set_rollback(True)
        return result


class Command(BaseCommand):
    help = 'Simula varios partidos/jugadores y genera HTMLs para validar cálculo/pintado de KPIs.'

    def add_arguments(self, parser):
        parser.add_argument('--matrix', action='store_true', help='Ejecuta una matriz de escenarios (cobertura amplia de variables).')
        parser.add_argument('--fuzz', type=int, default=0, help='Ejecuta N escenarios aleatorios (sin HTML por defecto).')
        parser.add_argument('--seed', type=int, default=0, help='Seed para --fuzz (0 = aleatorio).')
        parser.add_argument('--teams', type=int, default=15, help='Número de equipos en el grupo (afecta jornadas totales).')
        parser.add_argument('--matches', type=int, default=3, help='Número de partidos a crear.')
        parser.add_argument('--players', type=int, default=5, help='Número de jugadores a crear.')
        parser.add_argument('--game-format', type=str, default='f11', choices=['f11', 'f7'])
        parser.add_argument('--output-dir', type=str, default=str(Path(settings.BASE_DIR) / 'artifacts' / 'sim-kpis'))
        parser.add_argument('--only', type=str, default='', help='Ejecuta solo escenarios cuyo key contenga este texto.')
        parser.add_argument('--render-html', action='store_true', help='Renderiza HTML incluso en modos --fuzz (más lento).')
        parser.add_argument('--persist-db', action='store_true', help='No hace rollback de la BD al finalizar cada escenario.')
        parser.add_argument('--fail-on-issues', action='store_true', help='Falla (exit!=0) si kpi_audit detecta incoherencias.')

    def handle(self, *args, **options):
        output_dir = Path(str(options['output_dir'])).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        only = str(options.get('only') or '').strip().lower()
        render_html = bool(options.get('render_html'))
        persist_db = bool(options.get('persist_db'))
        fail_on_issues = bool(options.get('fail_on_issues'))
        if bool(options.get('matrix')):
            matrix_id = uuid.uuid4().hex[:8]
            matrix_dir = output_dir / f'matrix-{matrix_id}'
            matrix_dir.mkdir(parents=True, exist_ok=True)
            scenarios = [
                ScenarioConfig(key='f11_baseline', label='F11 · baseline (registro-acciones)', with_group=True, game_format='f11'),
                ScenarioConfig(key='f7_baseline', label='F7 · prebenjamín (50\')', with_group=True, game_format='f7', teams_count=10),
                ScenarioConfig(key='substitutions', label='Sustituciones (entrada/salida)', with_group=True, game_format='f11', substitutions=True, matches_count=2),
                ScenarioConfig(key='duplicate_events', label='Dedupe eventos duplicados', with_group=True, game_format='f11', duplicate_events=True, matches_count=1),
                ScenarioConfig(key='mixed_sources', label='Fuentes mixtas (registro vs excel)', with_group=True, game_format='f11', mixed_sources=True, matches_count=2),
                ScenarioConfig(key='missing_zone', label='Inferencia de zona (zona vacía)', with_group=True, game_format='f11', missing_zone_inference=True, matches_count=2),
                ScenarioConfig(key='manual_lock_assists', label='Manual-base bloquea asistencias', with_group=True, game_format='f11', manual_lock_assists=True, matches_count=1),
                ScenarioConfig(key='manual_lock_totals', label='Manual-base bloquea PJ/PT/min/goles', with_group=True, game_format='f11', manual_lock_totals=True, matches_count=1),
                ScenarioConfig(key='no_group_isolation', label='Sin group: aislamiento por nombre', with_group=False, game_format='f11', isolate_no_group_name_collision=True, matches_count=2),
                ScenarioConfig(key='extra_time', label='Fin partido con añadido (95\')', with_group=True, game_format='f11', end_minute_override=95, matches_count=1),
                ScenarioConfig(key='no_end_marker', label='Sin FIN: inferencia de fin de partido', with_group=True, game_format='f11', add_end_marker=False, matches_count=2),
                ScenarioConfig(key='starter_no_events', label='Titular sin acciones: PJ/PT por alineación', with_group=True, game_format='f11', starter_without_events=True, matches_count=1),
                ScenarioConfig(key='absences_rotation', label='Ausencias rotativas: convocados vs roster', with_group=True, game_format='f11', rotate_absences=True, matches_count=3),
                ScenarioConfig(key='cards_injury_sanction', label='Tarjetas + lesión + sanción', with_group=True, game_format='f11', include_cards=True, include_injury=True, include_sanction=True, matches_count=2),
                ScenarioConfig(key='live_events', label='Acciones en vivo (touch-field) + final', with_group=True, game_format='f11', live_events=True, matches_count=1),
            ]
            results = []
            issues_total = 0
            for scenario in scenarios:
                if only and only not in scenario.key.lower():
                    continue
                result = _run_scenario(config=scenario, base_output_dir=matrix_dir, render_html=True, persist_db=persist_db)
                results.append(result)
                summary = result.get('audit_summary') or {}
                issues_total += int(summary.get('issues_total') or 0)
            _write_text(
                matrix_dir / 'matrix_summary.json',
                json.dumps({'ok': True, 'issues_total': issues_total, 'results': results}, ensure_ascii=False, indent=2),
            )
            # Lightweight HTML index for quick browsing.
            lines = [
                '<!doctype html><html><head><meta charset="utf-8"><title>KPI Matrix</title></head><body>',
                f'<h1>KPI Matrix {matrix_id}</h1>',
                '<ul>',
            ]
            for item in results:
                rel = Path(item['dir']).name
                label = item.get('label') or item.get('key')
                dash_link = f'{rel}/player_dashboard.html' if (Path(item['dir']) / 'player_dashboard.html').exists() else ''
                if dash_link:
                    lines.append(f'<li><strong>{label}</strong> · <a href="{dash_link}">dashboard</a> · <a href="{rel}/kpi_audit.json">audit</a></li>')
                else:
                    lines.append(f'<li><strong>{label}</strong> · <a href="{rel}/kpi_audit.json">audit</a></li>')
            lines.extend(['</ul>', '</body></html>'])
            _write_text(matrix_dir / 'index.html', '\n'.join(lines))
            self.stdout.write(self.style.SUCCESS('Matriz de simulación generada.'))
            self.stdout.write(f'- Output: {matrix_dir}')
            self.stdout.write(f'- Index: {matrix_dir / "index.html"}')
            if issues_total and fail_on_issues:
                raise CommandError(f'kpi_audit detectó incoherencias. issues_total={issues_total}')
            return

        fuzz_count = int(options.get('fuzz') or 0)
        if fuzz_count > 0:
            base_seed = int(options.get('seed') or 0) or random.randint(1, 10_000_000)
            rng = random.Random(base_seed)
            fuzz_id = uuid.uuid4().hex[:8]
            fuzz_dir = output_dir / f'fuzz-{fuzz_id}'
            fuzz_dir.mkdir(parents=True, exist_ok=True)
            results = []
            issues_total = 0
            for idx in range(max(1, fuzz_count)):
                game_format = rng.choice(['f11', 'f7'])
                teams_count = rng.randint(6, 18) if game_format == 'f11' else rng.randint(6, 12)
                matches_count = rng.randint(1, 6)
                players_count = rng.randint(3, 16) if game_format == 'f11' else rng.randint(3, 12)
                cfg = ScenarioConfig(
                    key=f'fuzz_{idx + 1:03d}',
                    label=f'Fuzz {idx + 1} (seed={base_seed})',
                    teams_count=teams_count,
                    matches_count=matches_count,
                    players_count=players_count,
                    game_format=game_format,
                    with_group=rng.choice([True, True, False]),
                    add_end_marker=rng.choice([True, True, False]),
                    end_minute_override=(95 if game_format == 'f11' and rng.random() < 0.15 else (55 if game_format == 'f7' and rng.random() < 0.15 else None)),
                    substitutions=(rng.random() < 0.35),
                    duplicate_events=(rng.random() < 0.2),
                    mixed_sources=(rng.random() < 0.3),
                    missing_zone_inference=(rng.random() < 0.35),
                    manual_lock_assists=(rng.random() < 0.15),
                    manual_lock_totals=(rng.random() < 0.15),
                    isolate_no_group_name_collision=(rng.random() < 0.15),
                    rotate_absences=(rng.random() < 0.25),
                    starter_without_events=(rng.random() < 0.25),
                    include_cards=(rng.random() < 0.25),
                    include_injury=(rng.random() < 0.15),
                    include_sanction=(rng.random() < 0.15),
                    live_events=(rng.random() < 0.25),
                )
                result = _run_scenario(config=cfg, base_output_dir=fuzz_dir, render_html=render_html, persist_db=persist_db)
                results.append(result)
                summary = result.get('audit_summary') or {}
                issues_total += int(summary.get('issues_total') or 0)
            _write_text(
                fuzz_dir / 'fuzz_summary.json',
                json.dumps({'ok': True, 'seed': base_seed, 'issues_total': issues_total, 'results': results}, ensure_ascii=False, indent=2),
            )
            self.stdout.write(self.style.SUCCESS('Fuzz de simulación generado.'))
            self.stdout.write(f'- Output: {fuzz_dir}')
            self.stdout.write(f'- Seed: {base_seed}')
            self.stdout.write(f'- issues_total: {issues_total}')
            if issues_total and fail_on_issues:
                raise CommandError(f'kpi_audit detectó incoherencias. issues_total={issues_total}')
            return

        # Single scenario (compatible with el comportamiento anterior)
        scenario = ScenarioConfig(
            key='single',
            label='Single scenario',
            teams_count=max(2, int(options['teams'] or 15)),
            matches_count=max(1, int(options['matches'] or 3)),
            players_count=max(1, int(options['players'] or 5)),
            game_format=str(options['game_format'] or 'f11').strip().lower(),
            with_group=True,
        )
        result = _run_scenario(config=scenario, base_output_dir=output_dir, render_html=True, persist_db=persist_db)
        self.stdout.write(self.style.SUCCESS('Simulación generada.'))
        self.stdout.write(f"- Output: {result['dir']}")
