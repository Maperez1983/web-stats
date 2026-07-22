from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    AppUserRole,
    Competition,
    Group,
    Player,
    PlayerInjuryRecord,
    Season,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class PlayerInjuryDetailViewTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='CompInjury', slug='comp-injury')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoInjury', slug='grupo-injury')
        self.team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-injury',
            short_name='Benagalbón',
            group=self.group,
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='injury-manager',
            email='injury-manager@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='Injury Workspace',
            slug='injury-workspace',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.player = Player.objects.create(
            team=self.team,
            name='Jugador Lesión',
            full_name='Jugador Lesión',
            is_active=True,
        )
        self.record = PlayerInjuryRecord.objects.create(
            player=self.player,
            injury='Sobrecarga',
            injury_type='Muscular',
            injury_zone='Isquios',
            injury_side='izquierdo',
            injury_date=date(2026, 7, 1),
            notes='Carga alta',
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_save_record_marks_recovered_and_creates_milestone(self):
        response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'save-record',
                'injury': 'Sobrecarga',
                'injury_type': 'Muscular',
                'injury_zone': 'Isquios',
                'injury_side': 'izquierdo',
                'injury_date': '2026-07-01',
                'return_date': '',
                'estimated_return_date': '',
                'blocks_training': '1',
                'is_recovered': '1',
                'training_status': 'rehab',
                'notes': 'Evolución favorable',
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)

        self.record.refresh_from_db()
        self.assertTrue(self.record.is_recovered)
        self.assertFalse(self.record.is_active)
        self.assertTrue(self.record.blocks_training)
        self.assertIsNotNone(self.record.return_date)

        milestone_response = self.client.post(
            reverse('player-injury-detail', args=[self.player.id, self.record.id]),
            data={
                'action': 'add-milestone',
                'milestone_title': 'Prueba diagnóstica',
                'milestone_date': '2026-07-04',
                'milestone_notes': 'Control ecográfico',
                'milestone_done': '1',
            },
            secure=True,
        )
        self.assertEqual(milestone_response.status_code, 302)
        self.assertEqual(self.record.milestones.count(), 1)
