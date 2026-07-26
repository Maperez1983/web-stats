from django.test import TestCase

from football.system_guard import (
    _detect_remote_incidents,
    _detect_repair_candidates,
    _guarded_apply_code_fix,
    _tool_render_services,
)


class OllanaAutonomyTests(TestCase):
    def test_repair_candidate_matches_catalog_and_is_not_auto_by_default(self):
        report = {"issues": [{"id": "x", "title": "DisallowedHost: testserver", "detail": "allowed_hosts host header"}]}
        cand = _detect_repair_candidates(report)
        self.assertTrue(cand)
        self.assertEqual(cand[0]["detector"], "repair::dev_testserver_allowed_host")
        self.assertFalse(cand[0]["auto_execute"])  # seguro: no auto por defecto
        self.assertIn("apply_code_fix:dev_testserver_allowed_host", cand[0]["tools"])

    def test_repair_candidate_no_match(self):
        self.assertEqual(_detect_repair_candidates({"issues": [{"id": "y", "title": "algo sin relación"}]}), [])

    def test_remote_monitor_off_by_default(self):
        self.assertEqual(_detect_remote_incidents(), [])

    def test_apply_code_fix_requires_confirmation_by_default(self):
        res = _guarded_apply_code_fix("dev_testserver_allowed_host")
        self.assertFalse(res["ok"])
        self.assertEqual(res["status"], "requires_confirmation")

    def test_apply_code_fix_unknown_key(self):
        self.assertEqual(_guarded_apply_code_fix("nope")["error"], "unknown_candidate")

    def test_render_tool_needs_api_key(self):
        self.assertEqual(_tool_render_services()["error"], "render_api_not_configured")
