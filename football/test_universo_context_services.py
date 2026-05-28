from unittest.mock import patch

from django.test import TestCase

from football import universo_context_services
from football.models import (
    Competition,
    Group,
    Season,
    Team,
    Workspace,
    WorkspaceCompetitionContext,
)


class UniversoContextServicesTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(
            name='Liga Cadete Demo',
            slug='liga-cadete-demo',
        )
        self.season = Season.objects.create(
            competition=self.competition,
            name='2026/2027',
            is_current=True,
        )
        self.group = Group.objects.create(
            season=self.season,
            name='Grupo 2',
            slug='grupo-2',
            external_id='45030656',
        )
        self.team = Team.objects.create(name='Equipo Demo', slug='equipo-demo', group=self.group)
        self.workspace = Workspace.objects.create(
            name='Cliente Contexto Universo',
            slug='cliente-contexto-universo',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
        )
        self.context = WorkspaceCompetitionContext.objects.create(
            workspace=self.workspace,
            team=self.team,
            group=self.group,
            season=self.season,
            provider=WorkspaceCompetitionContext.PROVIDER_UNIVERSO,
            external_team_name='Equipo Demo',
        )

    def test_context_team_lookup_keys_includes_external_team_key(self):
        self.context.external_team_key = 'TEAM-111'

        keys = universo_context_services.context_team_lookup_keys(self.context, self.team)

        self.assertIn('equipodemo', keys)
        self.assertIn('team111', keys)

    def test_binding_uses_existing_group_external_id(self):
        context = universo_context_services.ensure_universo_context_binding(self.context, self.team)

        self.assertEqual(context.external_group_key, '45030656')

    def test_binding_uses_catalog_candidate_when_group_has_no_external_id(self):
        self.group.external_id = ''
        self.group.save(update_fields=['external_id'])
        catalog = {
            'competitions': {
                '99999': {'name': 'Liga Cadete Demo', 'season_name': '2026/2027'},
            },
            'groups': {
                ('99999', '45030656'): {'group_name': 'Grupo 2'},
            },
            'classifications': {
                ('99999', '45030656'): {
                    'competition_name': 'Liga Cadete Demo',
                    'group_name': 'Grupo 2',
                    'rows': [{'nombre': 'Equipo Demo', 'codequipo': '111'}],
                },
            },
        }

        with patch(
            'football.universo_context_services.build_universo_competition_catalog',
            return_value=catalog,
        ):
            context = universo_context_services.ensure_universo_context_binding(self.context, self.team)

        self.assertEqual(context.external_competition_key, '99999')
        self.assertEqual(context.external_group_key, '45030656')
        self.assertEqual(context.external_team_key, '111')
        self.assertEqual(context.external_team_name, 'Equipo Demo')

    def test_binding_leaves_context_unchanged_on_ambiguous_candidates(self):
        self.group.external_id = ''
        self.group.save(update_fields=['external_id'])
        catalog = {
            'competitions': {
                '1': {'name': 'Liga Cadete Demo', 'season_name': '2026/2027'},
                '2': {'name': 'Liga Cadete Demo', 'season_name': '2026/2027'},
            },
            'groups': {
                ('1', '101'): {'group_name': 'Grupo 2'},
                ('2', '202'): {'group_name': 'Grupo 2'},
            },
            'classifications': {
                ('1', '101'): {
                    'competition_name': 'Liga Cadete Demo',
                    'group_name': 'Grupo 2',
                    'rows': [{'nombre': 'Equipo Demo', 'codequipo': '111'}],
                },
                ('2', '202'): {
                    'competition_name': 'Liga Cadete Demo',
                    'group_name': 'Grupo 2',
                    'rows': [{'nombre': 'Equipo Demo', 'codequipo': '222'}],
                },
            },
        }

        with patch(
            'football.universo_context_services.build_universo_competition_catalog',
            return_value=catalog,
        ):
            context = universo_context_services.ensure_universo_context_binding(self.context, self.team)

        self.assertEqual(context.external_group_key, '')
        self.assertEqual(context.external_team_key, '')
