from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone

from football.models import Player, PlayerInjuryRecord, Team
from football.views import answer_coach_question


class CoachAssistantTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        self.req = RequestFactory().get("/")
        self.req.user = get_user_model().objects.create_superuser("s", "s@x.com", "x")
        self.p1 = Player.objects.create(team=self.team, name="Ana", is_active=True)
        self.p2 = Player.objects.create(team=self.team, name="Beto", is_active=True)
        PlayerInjuryRecord.objects.create(player=self.p2, is_active=True,
                                          injury_date=timezone.localdate() - timedelta(days=5))

    def test_injured_intent(self):
        r = answer_coach_question(self.req, self.team, "¿quién está lesionado?")
        self.assertEqual(r["intent"], "injured")
        self.assertIn("Beto", r["answer"])

    def test_available_intent(self):
        r = answer_coach_question(self.req, self.team, "¿cuántos jugadores disponibles tengo?")
        self.assertEqual(r["intent"], "available")
        self.assertIn("2", r["answer"])  # 2 activos

    def test_next_match_intent_none(self):
        r = answer_coach_question(self.req, self.team, "¿cuándo es el próximo partido?")
        self.assertEqual(r["intent"], "next_match")

    def test_action_is_redirected_not_executed(self):
        r = answer_coach_question(self.req, self.team, "crea una sesión de fuerza")
        self.assertEqual(r["intent"], "action_redirect")

    def test_unknown_gives_help(self):
        r = answer_coach_question(self.req, self.team, "cuéntame un chiste")
        self.assertEqual(r["intent"], "help")
