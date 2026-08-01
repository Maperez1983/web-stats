from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parent.parent
MATCH_ACTIONS_JS = ROOT / "football" / "static" / "football" / "js" / "match_actions_page.js"


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
