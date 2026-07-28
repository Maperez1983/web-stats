from django.test import SimpleTestCase

from football.event_taxonomy import CANONICAL_EVENT_KINDS, canonical_event_kind as k
from football.event_taxonomy import event_kind


class _Ev:
    def __init__(self, event_type="", result="", zone="", observation="", raw_data=None, kind=""):
        self.event_type = event_type
        self.result = result
        self.zone = zone
        self.observation = observation
        self.raw_data = raw_data
        self.kind = kind


class EventKindReaderTests(SimpleTestCase):
    def test_column_wins_over_raw_and_text(self):
        # La columna kind (Fase 4) manda sobre raw_data y sobre el texto.
        ev = _Ev(event_type="Gol", result="Gol", raw_data={"kind": "pass"}, kind="shot")
        self.assertEqual(event_kind(ev), "shot")

    def test_prefers_stored_kind(self):
        # sin columna, texto dice 'gol' pero el kind de raw_data manda (determinista)
        ev = _Ev(event_type="Gol", result="Gol", raw_data={"kind": "pass"}, kind="")
        self.assertEqual(event_kind(ev), "pass")

    def test_derives_when_absent(self):
        ev = _Ev(event_type="Gol", result="Gol", raw_data={})
        self.assertEqual(event_kind(ev), "goal")

    def test_ignores_invalid_stored(self):
        ev = _Ev(event_type="Gol", result="Gol", raw_data={"kind": "bogus"})
        self.assertEqual(event_kind(ev), "goal")

    def test_second_yellow_event_is_red(self):
        ev = _Ev(event_type="Tarjeta Roja", result="Roja (2ª amarilla)", raw_data={"kind": "red_card"})
        self.assertEqual(event_kind(ev), "red_card")


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
