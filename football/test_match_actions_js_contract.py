from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parent.parent
MATCH_ACTIONS_JS = ROOT / "football" / "static" / "football" / "js" / "match_actions_page.js"
MATCH_ACTIONS_LIVE_JS = ROOT / "football" / "static" / "football" / "js" / "match_actions_live.js"
MATCH_ACTIONS_TEMPLATE = ROOT / "football" / "templates" / "football" / "match_actions.html"


class MatchActionsJavascriptContractTests(SimpleTestCase):
    def test_convocation_cards_are_initialized_before_close_selects(self):
        source = MATCH_ACTIONS_JS.read_text(encoding="utf-8")

        declaration = "const convocationCards = document.querySelectorAll('.convocation-card');"
        first_use = "fillClosePlayerSelect(document.getElementById('close-mvp-player'));"

        self.assertIn(declaration, source)
        self.assertIn(first_use, source)
        self.assertLess(
            source.index(declaration),
            source.index(first_use),
            "convocationCards debe existir antes de rellenar MVP y capitán.",
        )

    def test_lineup_loops_ignore_formation_and_metadata(self):
        source = MATCH_ACTIONS_JS.read_text(encoding="utf-8")

        self.assertNotIn(
            "Object.keys(lineupState)",
            source,
            "El payload del once contiene formation y _meta; solo se recorren sus secciones de jugadores.",
        )

    def test_match_action_allows_manual_minute_and_period(self):
        source = MATCH_ACTIONS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('type="number" name="minute"', source)
        self.assertIn('min="0" max="120"', source)
        self.assertIn('<select name="period"', source)
        self.assertIn('<option value="2">2ª parte</option>', source)
        self.assertIn("var minuteInput = form.querySelector('[name=\"minute\"]');", source)
        self.assertIn("var periodInput = form.querySelector('[name=\"period\"]');", source)

        live_source = MATCH_ACTIONS_LIVE_JS.read_text(encoding="utf-8")
        submit_block = live_source.split("popupForm.addEventListener('submit'", 1)[1].split("// Señal", 1)[0]
        self.assertNotIn(
            "syncAutoFields();",
            submit_block,
            "El submit no debe pisar el minuto manual con el cronómetro.",
        )
