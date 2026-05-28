from django.test import TestCase

from football import universo_group_services
from football.models import Competition, Group, Season, Team, Workspace, WorkspaceCompetitionContext


class UniversoGroupServicesTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name='Benagalbon C.D. A',
            slug='benagalbon-a',
            short_name='Benagalbon A',
        )
        self.workspace = Workspace.objects.create(
            name='Cliente Universo Grupo',
            slug='cliente-universo-grupo',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        self.context = WorkspaceCompetitionContext.objects.create(
            workspace=self.workspace,
            team=self.team,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_group_key='45030656',
            external_team_name='Benagalbon C.D. A',
        )

    def test_candidate_creates_competition_season_group_and_binds_team(self):
        universo_group_services.ensure_universo_group_models_from_candidate(
            group_key='45030656',
            competition_name='Division Demo',
            group_name='Grupo Demo',
            season_name='2026/2027',
            competition_code='99999',
            primary_team=self.team,
            context=self.context,
        )

        self.team.refresh_from_db()
        self.context.refresh_from_db()
        self.assertEqual(self.team.group.name, 'Grupo Demo')
        self.assertEqual(self.team.group.external_id, '45030656')
        self.assertEqual(self.team.group.season.name, '2026/2027')
        self.assertEqual(self.team.group.season.competition.name, 'Division Demo')
        self.assertEqual(self.context.group, self.team.group)
        self.assertEqual(self.context.season, self.team.group.season)
        self.assertEqual(self.context.external_competition_key, '99999')

    def test_live_payload_updates_group_name_and_external_team_binding(self):
        competition = Competition.objects.create(name='Division Demo', slug='division-demo')
        season = Season.objects.create(competition=competition, name='2026/2027')
        Group.objects.create(
            season=season,
            name='Grupo Antiguo',
            slug='grupo-antiguo',
            external_id='45030656',
        )

        universo_group_services.ensure_universo_group_models_from_live(
            group_key='45030656',
            live_payload={
                'competicion': 'Division Demo',
                'grupo': 'Grupo Nuevo',
                'codigo_competicion': '99999',
                'clasificacion': [
                    {'nombre': "BENAGALBON C.D. 'A'", 'codequipo': '111'},
                    {'nombre': 'Rival Demo', 'codequipo': '222'},
                ],
            },
            primary_team=self.team,
            context=self.context,
        )

        self.team.refresh_from_db()
        self.context.refresh_from_db()
        self.assertEqual(self.team.group.name, 'Grupo Nuevo')
        self.assertEqual(self.context.external_team_key, '111')
        self.assertEqual(self.context.external_team_name, "BENAGALBON C.D. 'A'")

    def test_expand_team_lookup_variants_handles_suffix_and_club_prefix(self):
        variants = universo_group_services.expand_team_lookup_variants("Benagalbon C.D. 'A'")

        self.assertIn('benagalboncda', variants)
        self.assertIn('benagalboncd', variants)
        self.assertIn('benagalbon', variants)
