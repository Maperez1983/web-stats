from django.test import SimpleTestCase

from football.event_taxonomy import CANONICAL_EVENT_KINDS, canonical_event_kind as k


class CanonicalEventKindTests(SimpleTestCase):
    def test_basic_kinds(self):
        self.assertEqual(k("Gol", "Gol"), "goal")
        self.assertEqual(k("Pase", "OK"), "pass")
        self.assertEqual(k("Regate", "OK"), "dribble")
        self.assertEqual(k("Parada", "OK"), "save")
        self.assertEqual(k("Asistencia", ""), "assist")
        self.assertEqual(k("Tarjeta Amarilla", "Amarilla"), "yellow_card")
        self.assertEqual(k("Tarjeta Roja", "Roja"), "red_card")

    def test_second_yellow_is_red_not_yellow(self):
        # 'Roja (2ª amarilla)' contiene ambas palabras -> debe ganar la roja.
        self.assertEqual(k("Tarjeta Roja", "Roja (2ª amarilla)", "Tarjeta Roja (2ª amarilla)"), "red_card")

    def test_goal_beats_shot(self):
        # Un gol también es un tiro; debe clasificar como 'goal', no 'shot'.
        self.assertEqual(k("Tiro", "Gol"), "goal")

    def test_shot_without_goal(self):
        self.assertIn(k("Tiro", "Fuera"), ("shot", "shot_on_target"))

    def test_accent_insensitive(self):
        # 'Regaté' debe clasificar igual que 'Regate' (normalize quita acentos).
        self.assertEqual(k("Regaté", ""), "dribble")

    def test_unknown_is_other(self):
        self.assertEqual(k("Cosa rara sin keyword", ""), "other")

    def test_all_returns_are_valid_kinds(self):
        samples = [
            ("Gol", "Gol"), ("Pase", "OK"), ("Regate", "OK"), ("Parada", "OK"),
            ("Tarjeta Amarilla", "Amarilla"), ("Tarjeta Roja", "Roja"), ("Cosa", ""),
        ]
        for et, res in samples:
            self.assertIn(k(et, res), CANONICAL_EVENT_KINDS)
