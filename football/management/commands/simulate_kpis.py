from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from football.models import (
    AppUserRole,
    Competition,
    ConvocationRecord,
    Group,
    Match,
    MatchEvent,
    Player,
    Season,
    Team,
    Workspace,
    WorkspaceTeam,
    WorkspaceMembership,
)
from football.views import compute_player_dashboard, player_dashboard_page, player_detail_page


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


class Command(BaseCommand):
    help = 'Simula varios partidos/jugadores y genera HTMLs para validar cálculo/pintado de KPIs.'

    def add_arguments(self, parser):
        parser.add_argument('--teams', type=int, default=15, help='Número de equipos en el grupo (afecta jornadas totales).')
        parser.add_argument('--matches', type=int, default=3, help='Número de partidos a crear.')
        parser.add_argument('--players', type=int, default=5, help='Número de jugadores a crear.')
        parser.add_argument('--game-format', type=str, default='f11', choices=['f11', 'f7'])
        parser.add_argument('--output-dir', type=str, default=str(Path(settings.BASE_DIR) / 'artifacts' / 'sim-kpis'))

    def handle(self, *args, **options):
        teams_count = max(2, int(options['teams'] or 15))
        matches_count = max(1, int(options['matches'] or 3))
        players_count = max(1, int(options['players'] or 5))
        game_format = str(options['game_format'] or 'f11').strip().lower()
        output_dir = Path(str(options['output_dir'])).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = uuid.uuid4().hex[:8]
        run_dir = output_dir / f'run-{run_id}'
        run_dir.mkdir(parents=True, exist_ok=True)

        # Admin user for rendering views.
        user_model = get_user_model()
        admin_user, _ = user_model.objects.get_or_create(
            username=f'sim-admin-{run_id}',
            defaults={
                'email': f'sim-admin-{run_id}@example.com',
                'is_staff': True,
            },
        )
        if not hasattr(admin_user, 'app_role'):
            AppUserRole.objects.create(user=admin_user, role=AppUserRole.ROLE_ADMIN)
        else:
            AppUserRole.objects.filter(user=admin_user).update(role=AppUserRole.ROLE_ADMIN)

        competition = Competition.objects.create(
            name=f'Sim KPI {run_id}',
            slug=f'sim-kpi-{run_id}',
            region='Sim',
        )
        season = Season.objects.create(competition=competition, name='2025/2026', is_current=True)
        group = Group.objects.create(season=season, name=f'Grupo único {run_id}', slug=f'grupo-{run_id}')

        # Main club
        club = Team.objects.create(
            name=f'Club KPI {run_id}',
            slug=f'club-kpi-{run_id}',
            short_name='BENAGALBÓN',
            group=group,
            is_primary=True,
            game_format=Team.GAME_FORMAT_F7 if game_format == 'f7' else Team.GAME_FORMAT_F11,
        )

        # Other teams to drive `get_competition_total_rounds` double round robin
        opponents = []
        for idx in range(teams_count - 1):
            opponents.append(
                Team.objects.create(
                    name=f'Rival {idx + 1} {run_id}',
                    slug=f'rival-{idx + 1}-{run_id}',
                    short_name=f'Rival {idx + 1}',
                    group=group,
                )
            )

        # Workspace to enable modules
        workspace = Workspace.objects.create(
            name=f'Workspace KPI {run_id}',
            slug=f'ws-kpi-{run_id}',
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
        for idx in range(players_count):
            pos = 'POR' if idx == 0 else ('DC' if idx == 1 else 'MC')
            players.append(
                Player.objects.create(
                    team=club,
                    name=f'Jugador {idx + 1} {run_id}',
                    full_name=f'Jugador {idx + 1} {run_id}',
                    position=pos,
                    number=idx + 1,
                )
            )

        # Create matches + convocations + events
        regulation_minutes = 50 if game_format == 'f7' else 90
        today = timezone.localdate()
        for match_index in range(matches_count):
            opponent = opponents[match_index % len(opponents)]
            match = Match.objects.create(
                season=season,
                group=group,
                round=str(match_index + 1),
                date=today - timedelta(days=(matches_count - match_index) * 7),
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
                is_current=(match_index == matches_count - 1),
            )
            conv.players.set(players)
            conv.lineup_data = {
                'starters': [{'id': str(p.id)} for p in players[: min(len(players), 11)]],
                'bench': [{'id': str(p.id)} for p in players[min(len(players), 11) :]],
            }
            conv.captain = players[1] if len(players) > 1 else players[0]
            conv.goalkeeper = players[0]
            conv.save(update_fields=['lineup_data', 'captain', 'goalkeeper'])

            # End-of-match marker so minutes can be computed.
            MatchEvent.objects.create(
                match=match,
                player=None,
                minute=regulation_minutes,
                period=2,
                event_type='FIN',
                result='OK',
                zone='',
                tercio='',
                observation='Fin partido',
                system='touch-field-final',
                source_file='registro-acciones',
            )

            # Player events
            for player in players:
                # Each starter has at least one action.
                MatchEvent.objects.create(
                    match=match,
                    player=player,
                    minute=10 + match_index,
                    period=1,
                    event_type='Pase',
                    result='OK',
                    zone='Medio Centro',
                    tercio='Construcción',
                    observation='',
                    system='touch-field-final',
                    source_file='registro-acciones',
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

        # Compute + dump results
        dashboard = compute_player_dashboard(club, force_refresh=True)
        summary_path = run_dir / 'kpis.json'
        summary_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding='utf-8')

        session_data = {
            'active_workspace_id': int(workspace.id),
            'active_team_by_workspace': {str(workspace.id): int(club.id)},
        }
        # Render dashboard + each player detail
        dash_req = _make_request(admin_user, path=reverse('player-dashboard'), session_data=session_data, query_string='?refresh=1')
        dash_resp = player_dashboard_page(dash_req)
        (run_dir / 'player_dashboard.html').write_bytes(dash_resp.content)

        for player in players:
            detail_req = _make_request(admin_user, path=reverse('player-detail', args=[player.id]), session_data=session_data, query_string='?refresh=1')
            resp = player_detail_page(detail_req, player.id)
            (run_dir / f'player_{player.id}.html').write_bytes(resp.content)

        self.stdout.write(self.style.SUCCESS('Simulación generada.'))
        self.stdout.write(f'- Team: {club.display_name} (id={club.id}, format={game_format})')
        self.stdout.write(f'- Workspace: {workspace.name} (id={workspace.id})')
        self.stdout.write(f'- Output: {run_dir}')
        self.stdout.write(f'- KPIs JSON: {summary_path}')
        self.stdout.write(f'- HTML dashboard: {run_dir / "player_dashboard.html"}')
