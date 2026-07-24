from django.test import SimpleTestCase

from football.services import build_rival_briefing


class RivalBriefingTests(SimpleTestCase):
    def _insights(self):
        return {
            "top_scorers": [{"name": "Juan", "goals": 7, "minutes": 900}],
            "most_minutes": [{"name": "Luis", "minutes": 1200, "position": "MC"}],
            "most_cards": [{"name": "Paco", "yellow_cards": 6, "red_cards": 1}],
            "role_breakdown": {"GK": 2, "DEF": 7, "MID": 6, "ATT": 4},
        }

    def test_empty_inputs_produce_no_keys(self):
        self.assertEqual(build_rival_briefing({}, "Auto", {}), [])
        self.assertEqual(build_rival_briefing(None, None, None), [])

    def test_full_briefing_labels(self):
        keys = build_rival_briefing(
            self._insights(),
            "4-3-3",
            {"rival_gf": "28", "rival_ga": "15", "rival_played": "12"},
        )
        labels = [k["label"] for k in keys]
        self.assertEqual(labels, ["Sistema", "Amenaza", "Referente", "Disciplina", "Ritmo", "Plantilla"])
        by_label = {k["label"]: k["text"] for k in keys}
        self.assertIn("4-3-3", by_label["Sistema"])
        self.assertIn("Juan", by_label["Amenaza"])
        self.assertIn("2.3 GF", by_label["Ritmo"])

    def test_formation_auto_is_skipped(self):
        keys = build_rival_briefing(self._insights(), "Auto", {})
        self.assertNotIn("Sistema", [k["label"] for k in keys])

    def test_zero_goals_scorer_is_not_a_threat(self):
        ins = self._insights()
        ins["top_scorers"] = [{"name": "Nadie", "goals": 0, "minutes": 500}]
        keys = build_rival_briefing(ins, "Auto", {})
        self.assertNotIn("Amenaza", [k["label"] for k in keys])

    def test_ritmo_needs_played_and_goals(self):
        # Sin PJ no se puede promediar: no aparece "Ritmo".
        keys = build_rival_briefing(self._insights(), "Auto", {"rival_gf": "28", "rival_ga": "15"})
        self.assertNotIn("Ritmo", [k["label"] for k in keys])
