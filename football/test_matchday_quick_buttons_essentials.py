from django.contrib.auth import get_user_model
from django.test import TestCase

from football.models import Team, Workspace, WorkspacePreference
from football.views import _load_matchday_quick_buttons_for_workspace


class MatchdayQuickButtonsEssentialsTests(TestCase):
    """Parada y Regate alimentan stats (paradas de portero, regates) que no se capturan de otro
    modo. Deben estar SIEMPRE disponibles como botón, incluso si el workspace personalizó su set
    de botones rápidos y los quitó.
    """

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="B", slug="b", kind=Workspace.KIND_CLUB, primary_team=self.team
        )

    def _actions(self, buttons):
        return {str(b.get("action") or "").strip().lower() for b in buttons}

    def test_defaults_include_essentials(self):
        buttons = _load_matchday_quick_buttons_for_workspace(user=self.user, workspace=self.workspace)
        acts = self._actions(buttons)
        self.assertIn("parada", acts)
        self.assertIn("regate", acts)

    def test_custom_config_without_essentials_still_gets_them(self):
        WorkspacePreference.objects.create(
            workspace=self.workspace,
            key="matchday_quick_buttons:v1",
            value={"items": [{"label": "Disparo", "action": "Disparo"}, {"label": "Pase", "action": "Pase"}]},
        )
        buttons = _load_matchday_quick_buttons_for_workspace(user=self.user, workspace=self.workspace)
        acts = self._actions(buttons)
        self.assertIn("disparo", acts)  # respeta lo del workspace
        self.assertIn("parada", acts)   # y reañade los esenciales
        self.assertIn("regate", acts)

    def test_essentials_not_duplicated(self):
        WorkspacePreference.objects.create(
            workspace=self.workspace,
            key="matchday_quick_buttons:v1",
            value={"items": [{"label": "Parada", "action": "Parada"}]},
        )
        buttons = _load_matchday_quick_buttons_for_workspace(user=self.user, workspace=self.workspace)
        parada_count = sum(1 for b in buttons if str(b.get("action") or "").strip().lower() == "parada")
        self.assertEqual(parada_count, 1)
