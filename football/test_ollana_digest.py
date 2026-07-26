from django.test import TestCase

from football.models import Workspace
from football.system_guard import (
    OPERATOR_DIGEST_PREF_KEY,
    _build_operator_digest,
    _maybe_build_daily_digest,
    _pref_value,
    _store_proactive_state,
)


class OllanaDigestTests(TestCase):
    def setUp(self):
        self.ws = Workspace.objects.create(name="WS", slug="ws")

    def test_build_digest_does_not_crash_empty(self):
        d = _build_operator_digest(self.ws)
        self.assertIn("queue_counts", d)
        self.assertIn("llm_assessment", d)
        self.assertIn("generated_at", d)

    def test_daily_digest_builds_then_throttles(self):
        # Estado de un ciclo previo para que el digest tenga contenido.
        _store_proactive_state(self.ws, {
            "last_cycle_at": "2026-07-26T03:00:00+00:00",
            "last_detection_count": 2,
            "last_strategy_mode": "monitor_only",
            "last_llm_assessment": {"available": True, "summary": "estable"},
        })
        first = _maybe_build_daily_digest(self.ws)
        self.assertTrue(first["built"])
        self.assertEqual(first["digest"]["last_detection_count"], 2)
        # Persistido
        stored = _pref_value(self.ws, OPERATOR_DIGEST_PREF_KEY, {})
        self.assertEqual(stored.get("last_strategy_mode"), "monitor_only")
        # Segunda llamada seguida -> throttled (no reconstruye)
        second = _maybe_build_daily_digest(self.ws)
        self.assertFalse(second["built"])
        self.assertEqual(second["reason"], "interval_not_elapsed")
