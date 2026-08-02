from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parent.parent
MATCH_ACTIONS_JS = ROOT / "football" / "static" / "football" / "js" / "match_actions_page.js"
MATCH_ACTIONS_LIVE_JS = ROOT / "football" / "static" / "football" / "js" / "match_actions_live.js"
MATCH_ACTIONS_TEMPLATE = ROOT / "football" / "templates" / "football" / "match_actions.html"
MATCH_ACTIONS_VIEWS = ROOT / "football" / "views.py"


class MatchActionsJavascriptContractTests(SimpleTestCase):
    def test_manual_recovery_is_available_in_match_flow(self):
        template = MATCH_ACTIONS_TEMPLATE.read_text(encoding="utf-8")
        source = MATCH_ACTIONS_JS.read_text(encoding="utf-8")

        self.assertIn('id="manual-bulk-open-nav"', template)
        self.assertIn("Recuperar acciones del partido", template)
        self.assertIn('name="minute" min="0" max="120"', template)
        self.assertIn('name="observation" maxlength="500"', template)
        self.assertIn("manualBulkOpenNav?.addEventListener('click', openManualBulk);", source)
        self.assertIn("observation: String(fd.get('observation')", source)

    def test_impact_modal_is_not_nested_inside_hidden_history_modal(self):
        template = MATCH_ACTIONS_TEMPLATE.read_text(encoding="utf-8")

        history_end = template.index('<ol class="quick-history-list" id="quick-history-list"></ol>')
        impact_start = template.index('<div class="impact-modal" id="match-impact-modal"')
        between = template[history_end:impact_start]
        self.assertGreaterEqual(between.count("</div>"), 2)

    def test_manual_recovery_preserves_zero_minute_from_json(self):
        source = MATCH_ACTIONS_VIEWS.read_text(encoding="utf-8")

        self.assertIn('payload.get("minute") if "minute" in payload else request.POST.get("minute")', source)

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

        self.assertIn("fieldPopup.setAttribute('aria-hidden', 'false');", live_source)
        self.assertIn("fieldPopup.setAttribute('aria-hidden', 'true');", live_source)
        self.assertIn("popupForm.addEventListener('submit', handlePopupSubmit);", live_source)
        self.assertIn("popupSubmitButton?.addEventListener('click'", live_source)
