import datetime
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string

from football import views
from football.models import Competition, Match, MatchEvent, Player, PlayerStatistic, Season, Team


class MatchStaffReportTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name="Liga informe", slug="liga-informe", region="Malaga")
        self.season = Season.objects.create(competition=competition, name="2026/27")
        self.team = Team.objects.create(name="Equipo informe", slug="equipo-informe")
        self.rival = Team.objects.create(name="Rival informe", slug="rival-informe")
        self.player = Player.objects.create(team=self.team, name="Jugador Uno", number=8, position="MC")
        self.match = Match.objects.create(
            season=self.season,
            home_team=self.team,
            away_team=self.rival,
            date=datetime.date(2026, 8, 2),
            stats_source=Match.STATS_SOURCE_LIVE,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=self.match,
            name="manual_minutes",
            value=75,
            context="manual-match",
        )

    def _event(self, event_type, result, *, minute, period, zone, tercio):
        return MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type=event_type,
            result=result,
            minute=minute,
            period=period,
            zone=zone,
            tercio=tercio,
            source_file="manual-recovery",
            system="touch-field-final",
        )

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_context_builds_team_and_player_match_reports(self, _crest):
        self._event("PASE EN LARGO", "GANADO", minute=12, period=1, zone="Medio centro", tercio="Construcción")
        self._event("DUELO AEREO", "GANADO", minute=52, period=2, zone="Area", tercio="Ataque")
        self._event("DISPARO", "AP", minute=60, period=2, zone="Frontal", tercio="Ataque")
        self._event("GOL ENCAJADO", "EN CONTRA", minute=70, period=2, zone="Portería", tercio="Defensa")

        request = RequestFactory().get("/coach/informes/partido/")
        request.user = AnonymousUser()
        context = views._match_staff_report_context(request, match=self.match, primary_team=self.team)

        family = {row["key"]: row for row in context["team_report"]["families"]}
        self.assertEqual(family["passes"]["total"], 1)
        self.assertEqual(family["duels"]["successes"], 1)
        self.assertEqual(family["shots"]["successes"], 1)
        self.assertEqual([row["actions"] for row in context["team_report"]["periods"]], [1, 3])
        self.assertEqual(context["team_report"]["known_zone_actions"], 4)

        player = context["player_reports"][0]
        self.assertEqual(player["minutes"], 75)
        self.assertEqual((player["long_passes_ok"], player["long_passes"]), (1, 1))
        self.assertEqual((player["aerial_won"], player["aerial"]), (1, 1))
        self.assertEqual((player["shots_target"], player["shots"]), (1, 1))
        self.assertEqual(player["dominant_zone"], "Ataque")
        self.assertEqual(player["goals"], 0)
        self.assertEqual(player["goals_conceded"], 1)
        self.assertEqual(next(card["value"] for card in context["summary_cards"] if card["label"] == "Goles"), 0)

        context["pdf_url"] = "/coach/informes/partido/pdf/?match_id=1"
        html = render_to_string("football/match_staff_report.html", context, request=request)
        pdf_html = render_to_string("football/match_staff_report_pdf.html", context)
        self.assertIn("Lectura de equipo", html)
        self.assertIn("Informe por jugador", html)
        self.assertIn("Jugador Uno", pdf_html)
