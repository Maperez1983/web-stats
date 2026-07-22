from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import AppUserRole, Competition, Group, ScoutingTarget, Season, Team, Workspace, WorkspaceMembership, WorkspaceTeam


class ScoutingTargetPersistenceTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name='CompScouting', slug='comp-scouting')
        self.season = Season.objects.create(competition=self.competition, name='2025/2026', is_current=True)
        self.group = Group.objects.create(season=self.season, name='GrupoScouting', slug='grupo-scouting')
        self.team = Team.objects.create(
            name='Benagalbón',
            slug='benagalbon-scouting',
            short_name='Benagalbón',
            group=self.group,
            is_primary=True,
        )
        self.user = get_user_model().objects.create_user(
            username='scout-manager',
            email='scout-manager@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='Scouting Workspace',
            slug='scouting-workspace',
            kind=Workspace.KIND_CLUB,
            is_active=True,
            primary_team=self.team,
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.target = ScoutingTarget.objects.create(
            workspace=self.workspace,
            subject_name='Jugador Ojeado',
            subject_team_name='Club Origen',
            position='Defensa derecho',
            dominant_foot='Derecho',
            status=ScoutingTarget.STATUS_TARGET,
            priority=ScoutingTarget.PRIORITY_LOW,
            available_for_coach_tools=False,
            created_by=self.user,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session['active_team_by_workspace'] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_save_target_persists_edits(self):
        response = self.client.post(
            reverse('scouting-target-detail', args=[self.target.id]),
            data={
                'action': 'save-target',
                'subject_name': 'Jugador Editado',
                'subject_team_name': 'Club Actualizado',
                'position': 'Lateral derecho',
                'dominant_foot': 'Izquierdo',
                'birth_date': '2005-02-14',
                'status': ScoutingTarget.STATUS_WATCHLIST,
                'priority': ScoutingTarget.PRIORITY_URGENT,
                'assigned_to_id': str(self.user.id),
                'next_review_on': '2026-08-01',
                'budget_note': 'Prioridad alta',
                'summary': 'Primer informe.',
                'available_for_coach_tools': '1',
            },
            secure=True,
        )
        self.assertEqual(response.status_code, 302)

        self.target.refresh_from_db()
        self.assertEqual(self.target.subject_name, 'Jugador Editado')
        self.assertEqual(self.target.subject_team_name, 'Club Actualizado')
        self.assertEqual(self.target.position, 'LD')
        self.assertEqual(self.target.dominant_foot, 'Izquierdo')
        self.assertEqual(self.target.birth_date, date(2005, 2, 14))
        self.assertEqual(self.target.status, ScoutingTarget.STATUS_WATCHLIST)
        self.assertEqual(self.target.priority, ScoutingTarget.PRIORITY_URGENT)
        self.assertEqual(self.target.assigned_to_id, self.user.id)
        self.assertEqual(self.target.next_review_on, date(2026, 8, 1))
        self.assertEqual(self.target.budget_note, 'Prioridad alta')
        self.assertEqual(self.target.summary, 'Primer informe.')
        self.assertTrue(self.target.available_for_coach_tools)
