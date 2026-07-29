from django.test import TestCase
from django.contrib.auth.models import User

from football.models import (
    Workspace, Team, WorkspaceTeam, StaffMember, WorkspaceMembership, Player,
)
from football import workspace_context as wc


class TeamIsolationTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner_iso", password="x")
        self.coach_preben = User.objects.create_user("coach_preben_iso", password="x")

        self.senior = Team.objects.create(name="Club X Senior", slug="clubx-senior-iso")
        self.preben = Team.objects.create(name="Club X Prebenjamin", slug="clubx-preben-iso")

        self.ws = Workspace.objects.create(
            name="Club X (iso)", slug="club-x-iso", owner_user=self.owner,
            primary_team=self.senior, kind=Workspace.KIND_CLUB,
        )
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.senior)
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.preben)

        WorkspaceMembership.objects.create(workspace=self.ws, user=self.owner, role=WorkspaceMembership.ROLE_OWNER)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.coach_preben, role=WorkspaceMembership.ROLE_MEMBER)

        # El coach solo es staff del prebenjamin (no del senior).
        StaffMember.objects.create(workspace=self.ws, team=self.preben, user=self.coach_preben, name="Coach Preben")

        # Un jugador en cada equipo.
        self.p_senior = Player.objects.create(team=self.senior, name="Jugador Senior")
        self.p_preben = Player.objects.create(team=self.preben, name="Jugador Preben")

    def _team_ids(self, user):
        return {int(getattr(l, "team_id", 0) or 0) for l in wc.workspace_team_links_for_user(self.ws, user)}

    def test_staff_solo_ve_su_equipo(self):
        ids = self._team_ids(self.coach_preben)
        self.assertEqual(ids, {self.preben.id}, "El coach de prebenjamin debe ver SOLO su equipo")
        self.assertNotIn(self.senior.id, ids, "NO debe ver el senior")

    def test_owner_ve_todos(self):
        ids = self._team_ids(self.owner)
        self.assertEqual(ids, {self.senior.id, self.preben.id}, "El owner debe ver todos los equipos")

    def test_staff_no_puede_acceder_equipo_ajeno(self):
        self.assertFalse(wc.can_manage_workspace(self.coach_preben, self.ws))
        # staff_team_ids_for_user: fuente de verdad (StaffMember.team)
        self.assertEqual(wc.staff_team_ids_for_user(self.ws, self.coach_preben), {self.preben.id})
