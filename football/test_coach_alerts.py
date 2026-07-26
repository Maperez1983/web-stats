from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from football.models import Player, PlayerInjuryRecord, Team
from football.views import _build_coach_alerts


class CoachAlertsTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)

    def test_no_next_match_alert(self):
        alerts = _build_coach_alerts(
            primary_team=self.team, roster_players=[], active_injury_ids=set(),
            federative_report=None, next_match={},
        )
        titles = [a["title"] for a in alerts]
        self.assertIn("Sin próximo partido fijado", titles)

    def test_expired_and_expiring_license_alerts(self):
        today = timezone.localdate()
        p1 = Player.objects.create(team=self.team, name="Caducado", is_active=True,
                                   federation_license_expires_at=today - timedelta(days=3))
        p2 = Player.objects.create(team=self.team, name="ProntoVence", is_active=True,
                                   federation_license_expires_at=today + timedelta(days=10))
        alerts = _build_coach_alerts(
            primary_team=self.team, roster_players=[p1, p2], active_injury_ids=set(),
            federative_report=None, next_match={"opponent": "X"},
        )
        titles = " ".join(a["title"] for a in alerts)
        self.assertIn("caducada", titles)
        self.assertIn("caducan pronto", titles)
        # con next_match presente NO debe avisar de "sin próximo partido"
        self.assertNotIn("Sin próximo partido", titles)

    def test_coverage_gap_from_federative_report(self):
        fr = {"coverage": [{"code": "DC", "label": "Delantero", "min": 3, "have": 1, "missing": 2}]}
        alerts = _build_coach_alerts(
            primary_team=self.team, roster_players=[], active_injury_ids=set(),
            federative_report=fr, next_match={"opponent": "X"},
        )
        cov = [a for a in alerts if "Cobertura" in a["title"]]
        self.assertTrue(cov)
        self.assertEqual(cov[0]["level"], "warning")

    def test_injury_returning_this_week(self):
        today = timezone.localdate()
        p = Player.objects.create(team=self.team, name="Vuelve", is_active=True)
        PlayerInjuryRecord.objects.create(player=p, is_active=True,
                                          injury_date=today - timedelta(days=10),
                                          estimated_return_date=today + timedelta(days=3))
        alerts = _build_coach_alerts(
            primary_team=self.team, roster_players=[p], active_injury_ids={p.id},
            federative_report=None, next_match={"opponent": "X"},
        )
        self.assertTrue(any("vuelven de lesión" in a["title"] for a in alerts))
