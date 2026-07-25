from django.test import TestCase

from football import dashboard_services, stats_services
from football.models import Team


class PlayerCardsAccuracyTests(TestCase):
    """coach_roster leía card.passes_accuracy / card.shots_accuracy, pero el dashboard emite
    passes/shots ANIDADOS ({accuracy: ...}); antes las tarjetas salían siempre a 0.
    """

    def test_cards_read_nested_passes_and_shots_accuracy(self):
        team = Team.objects.create(name="B", slug="b", is_primary=True)
        row = {
            "player_id": 1,
            "name": "J",
            "minutes": 90,
            "total_actions": 30,
            "passes": {"accuracy": 82.5},
            "shots": {"accuracy": 40.0},
        }
        # compute_player_cards hace `from .dashboard_services import compute_player_dashboard`
        # en tiempo de llamada, así que parcheamos el nombre en dashboard_services.
        orig = dashboard_services.compute_player_dashboard
        dashboard_services.compute_player_dashboard = lambda *a, **k: [row]
        try:
            cards = stats_services.compute_player_cards(team)
        finally:
            dashboard_services.compute_player_dashboard = orig

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["passes_accuracy"], 82.5)
        self.assertEqual(cards[0]["shots_accuracy"], 40.0)
