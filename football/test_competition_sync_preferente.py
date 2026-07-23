from unittest import mock

from django.test import TestCase

from football import competition_sync
from football.models import (
    Competition,
    Group,
    Season,
    Team,
    Workspace,
    WorkspaceCompetitionContext,
    WorkspaceCompetitionSnapshot,
)

_FAKE_ROWS = [
    {
        'rank': 1,
        'team': 'C.D. BENAGALBÓN',
        'full_name': 'C.D. Benagalbón',
        'team_code': 'E147',
        'crest_url': '',
        'played': 3,
        'wins': 2,
        'draws': 1,
        'losses': 0,
        'goals_for': 7,
        'goals_against': 2,
        'goal_difference': 5,
        'points': 7,
    },
    {
        'rank': 2,
        'team': 'CUEVAS C.F.',
        'full_name': 'Cuevas C.F.',
        'team_code': 'E376',
        'crest_url': '',
        'played': 3,
        'wins': 2,
        'draws': 0,
        'losses': 1,
        'goals_for': 5,
        'goals_against': 4,
        'goal_difference': 1,
        'points': 6,
    },
]


class SyncPreferenteStandingsTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name='División Honor Andaluza', slug='dha')
        self.season = Season.objects.create(competition=competition, name='2026/2027', is_current=True)
        self.group = Group.objects.create(season=self.season, name='Grupo 2', slug='grupo-2', external_id='g2')
        self.team = Team.objects.create(
            name='C.D. Benagalbón',
            slug='cd-benagalbon',
            group=self.group,
            is_primary=True,
            preferente_url='https://www.lapreferente.com/E147/cd-benagalbon',
        )
        self.workspace = Workspace.objects.create(
            name='Benagalbón',
            slug='benagalbon',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        self.context = WorkspaceCompetitionContext.objects.create(
            workspace=self.workspace,
            team=self.team,
            group=self.group,
            season=self.season,
            provider=WorkspaceCompetitionContext.PROVIDER_PREFERENTE,
        )
        # El próximo partido de Preferente no es objeto de estos tests (y saldría por red): lo
        # neutralizamos a {} para que el sync sea determinista y offline. En pretemporada real
        # devuelve {} igualmente (La Preferente responde error PHP sin jornada).
        next_patcher = mock.patch('football.competition_sync.fetch_preferente_next_match', return_value={})
        next_patcher.start()
        self.addCleanup(next_patcher.stop)

    def test_sync_writes_preferente_standings_into_snapshot(self):
        with mock.patch(
            'football.competition_sync.fetch_preferente_standings',
            return_value=(_FAKE_ROWS, {'season_name': '2026/2027'}),
        ) as fetch_mock:
            context, error = competition_sync.sync_workspace_competition_context(
                self.workspace, primary_team=self.team
            )

        fetch_mock.assert_called_once()
        # La URL usada debe ser la preferente_url del equipo.
        self.assertIn('lapreferente.com/E147', fetch_mock.call_args.args[0])
        self.assertEqual(context.sync_status, WorkspaceCompetitionContext.STATUS_READY)
        self.assertEqual(error, '')

        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(len(snapshot.standings_payload), 2)
        self.assertEqual(snapshot.standings_payload[0]['full_name'], 'C.D. Benagalbón')
        self.assertEqual(snapshot.standings_payload[0]['points'], 7)

    def test_sync_serves_standings_for_club_without_group(self):
        # Club recién dado de alta en Preferente: su Team aún no tiene Group en BD. La clasificación
        # debe aparecer igualmente (vía snapshot), no fallar con "sin grupo/competición vinculada".
        groupless = Team.objects.create(
            name='Nuevo C.F.',
            slug='nuevo-cf',
            is_primary=True,
            preferente_url='https://www.lapreferente.com/E999/nuevo-cf',
        )
        ws = Workspace.objects.create(name='Nuevo', slug='nuevo', kind=Workspace.KIND_CLUB, primary_team=groupless)
        ctx = WorkspaceCompetitionContext.objects.create(
            workspace=ws, team=groupless, provider=WorkspaceCompetitionContext.PROVIDER_PREFERENTE
        )

        with mock.patch(
            'football.competition_sync.fetch_preferente_standings',
            return_value=(_FAKE_ROWS, {}),
        ):
            context, error = competition_sync.sync_workspace_competition_context(ws, primary_team=groupless)

        self.assertEqual(error, '')
        self.assertEqual(context.sync_status, WorkspaceCompetitionContext.STATUS_READY)
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        self.assertEqual(len(snapshot.standings_payload), 2)

    def test_sync_falls_back_when_preferente_blocked(self):
        # Si Preferente viene bloqueado (rows vacías), no revienta y cae al fallback de BD.
        with mock.patch(
            'football.competition_sync.fetch_preferente_standings',
            return_value=([], {}),
        ):
            context, error = competition_sync.sync_workspace_competition_context(
                self.workspace, primary_team=self.team
            )

        self.assertEqual(error, '')
        snapshot = WorkspaceCompetitionSnapshot.objects.get(context=context)
        # Sin datos live ni en BD, la clasificación queda vacía pero el sync no falla.
        self.assertEqual(snapshot.standings_payload, [])
