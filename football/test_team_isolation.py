from django.test import TestCase, RequestFactory
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

    def _req(self, user):
        rf = RequestFactory()
        r = rf.get("/")
        r.user = user
        r.session = {"active_workspace_id": self.ws.id}
        return r

    def test_gate_activar_equipo(self):
        # El coach del prebenjamin NO puede activar/acceder al senior; sí al suyo.
        self.assertTrue(wc.user_can_access_team(self._req(self.coach_preben), self.preben))
        self.assertFalse(wc.user_can_access_team(self._req(self.coach_preben), self.senior))
        # El owner puede a ambos.
        self.assertTrue(wc.user_can_access_team(self._req(self.owner), self.senior))

    def test_gate_ficha_por_url(self):
        from football.views import _resolve_player_for_request_scope
        # Coach: abrir por URL un jugador del SENIOR -> no resuelve (anti-IDOR).
        _, pl = _resolve_player_for_request_scope(self._req(self.coach_preben), self.p_senior.id)
        self.assertIsNone(pl, "El coach NO debe resolver un jugador del senior por URL")
        # Coach: su propio jugador sí.
        _, pl_own = _resolve_player_for_request_scope(self._req(self.coach_preben), self.p_preben.id)
        self.assertIsNotNone(pl_own, "El coach SÍ debe ver un jugador de su equipo")
        # Owner: cualquiera.
        _, pl_owner = _resolve_player_for_request_scope(self._req(self.owner), self.p_senior.id)
        self.assertIsNotNone(pl_owner, "El owner SÍ resuelve cualquier jugador")
