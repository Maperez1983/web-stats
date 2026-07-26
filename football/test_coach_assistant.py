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

    def test_weekly_summary(self):
        r = answer_coach_question(self.req, self.team, "resumen de la semana")
        self.assertEqual(r["intent"], "weekly_summary")
        self.assertIn("Plantilla", r["answer"])

    def test_unknown_gives_help(self):
        r = answer_coach_question(self.req, self.team, "cuéntame un chiste")
        self.assertEqual(r["intent"], "help")

    def test_suggested_eleven(self):
        from football.views import _suggest_probable_eleven
        pos = ["Portero", "LD", "DFC", "DFC", "LI", "MC", "MC", "MC", "ED", "DC", "EI"]
        for i, ps in enumerate(pos):
            Player.objects.create(team=self.team, name=f"X{i}", position=ps, is_active=True, number=20 + i)
        xi = _suggest_probable_eleven(self.team)
        self.assertEqual(xi["formation"], "4-3-3")
        counts = {ln["line"]: len(ln["players"]) for ln in xi["lines"]}
        self.assertEqual(counts["Portero"], 1)
        self.assertEqual(counts["Defensa"], 4)
        self.assertEqual(counts["Medio"], 3)
        self.assertEqual(counts["Ataque"], 3)
        # intención del asistente
        r = answer_coach_question(self.req, self.team, "sugiere el 11 probable")
        self.assertEqual(r["intent"], "suggested_xi")
        self.assertIn("4-3-3", r["answer"])
