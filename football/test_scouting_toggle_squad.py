from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import ScoutingTarget, Team, Workspace, WorkspaceMembership


class ToggleSquadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="Bena", slug="bena", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _target(self, **kw):
        return ScoutingTarget.objects.create(
            workspace=self.workspace,
            subject_name="Adam",
            status=kw.pop("status", ScoutingTarget.STATUS_TARGET),
            available_for_coach_tools=kw.pop("available_for_coach_tools", False),
            **kw,
        )

    def test_include_in_squad_from_detail(self):
        target = self._target()
        self.client.post(f"/direccion/{target.id}/", {"action": "toggle-squad"}, HTTP_HOST="localhost")
        target.refresh_from_db()
        self.assertTrue(target.available_for_coach_tools)
        self.assertEqual(target.status, ScoutingTarget.STATUS_WATCHLIST)

    def test_remove_from_squad(self):
        target = self._target(available_for_coach_tools=True, status=ScoutingTarget.STATUS_WATCHLIST)
        self.client.post(f"/direccion/{target.id}/", {"action": "toggle-squad"}, HTTP_HOST="localhost")
        target.refresh_from_db()
        self.assertFalse(target.available_for_coach_tools)
