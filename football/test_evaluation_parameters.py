from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import (
    Player,
    PlayerEvaluation,
    Team,
    Workspace,
    WorkspaceMembership,
)


class EvaluationParametersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="C.D. Ejemplo", slug="cde", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="C.D. Ejemplo", slug="cde", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.player = Player.objects.create(team=self.team, name="Juan", is_active=True)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _post(self, extra):
        data = {"form_action": "evaluation", "status": "draft"}
        data.update(extra)
        return self.client.post(f"/player/{self.player.id}/", data, HTTP_HOST="localhost")

    def test_parameters_stored_and_area_is_average(self):
        resp = self._post({
            "param_physical_velocidad": "8",
            "param_physical_fuerza": "6",
            "param_physical_resistencia": "0",  # 0 = sin valorar -> no cuenta
        })
        self.assertEqual(resp.status_code, 302)
        ev = PlayerEvaluation.objects.get(player=self.player)
        self.assertEqual(ev.parameter_scores.get("physical"), {"velocidad": 8.0, "fuerza": 6.0})
        self.assertEqual(float(ev.physical_rating), 7.0)  # media de 8 y 6, sin contar el 0

    def test_manual_area_rating_overrides_average(self):
        ev_resp = self._post({
            "param_physical_velocidad": "8",
            "param_physical_fuerza": "6",
            "physical_rating": "9.0",  # nota de área a mano -> manda sobre la media
        })
        self.assertEqual(ev_resp.status_code, 302)
        ev = PlayerEvaluation.objects.get(player=self.player)
        self.assertEqual(float(ev.physical_rating), 9.0)
        self.assertEqual(ev.parameter_scores.get("physical"), {"velocidad": 8.0, "fuerza": 6.0})

    def test_no_parameters_leaves_area_none(self):
        self._post({"technical_rating": "7.0"})
        ev = PlayerEvaluation.objects.get(player=self.player)
        self.assertEqual(float(ev.technical_rating), 7.0)
        self.assertEqual(ev.parameter_scores, {})
