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

    def _team_event(self, event_type, result, perspective):
        return MatchEvent.objects.create(
            match=self.match,
            player=None,
            event_type=event_type,
            result=result,
            source_file="manual-recovery",
            system="touch-field-final",
            raw_data={"perspective": perspective},
        )

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_context_builds_team_and_player_match_reports(self, _crest):
        impact_event = self._event(
            "PASE EN LARGO", "GANADO", minute=12, period=1, zone="Medio centro", tercio="Construcción"
        )
        impact_event.raw_data = {"impact": {"code": "chance_created", "reason": "decisive_action"}}
        impact_event.save(update_fields=["raw_data"])
        self._event("DUELO AEREO", "GANADO", minute=52, period=2, zone="Area", tercio="Ataque")
        self._event("DISPARO", "AP", minute=60, period=2, zone="Frontal", tercio="Ataque")
        self._event("GOL ENCAJADO", "EN CONTRA", minute=70, period=2, zone="Portería", tercio="Defensa")
        for _index in range(4):
            self._team_event("CORNER", "NEUTRAL", "for")
        for _index in range(7):
            self._team_event("CORNER", "NEUTRAL", "against")
        for _index in range(2):
            self._team_event("DISPARO RIVAL", "AP", "against")
        for _index in range(5):
            self._team_event("DISPARO RIVAL", "FALLADO", "against")

        request = RequestFactory().get("/coach/informes/partido/")
        request.user = AnonymousUser()
        context = views._match_staff_report_context(request, match=self.match, primary_team=self.team)

        family = {row["key"]: row for row in context["team_report"]["families"]}
        self.assertEqual(family["passes"]["total"], 1)
        self.assertEqual(family["duels"]["successes"], 1)
        self.assertEqual(family["shots"]["successes"], 1)
        self.assertEqual([row["actions"] for row in context["team_report"]["periods"]], [1, 3])
        self.assertEqual(context["team_report"]["known_zone_actions"], 4)
        comparison = {row["label"]: row for row in context["team_report"]["comparison"]}
        self.assertEqual((comparison["Finalizaciones"]["team"], comparison["Finalizaciones"]["opponent"]), (1, 7))
        self.assertEqual((comparison["A puerta"]["team"], comparison["A puerta"]["opponent"]), (1, 2))
        self.assertEqual((comparison["Córners"]["team"], comparison["Córners"]["opponent"]), (4, 7))

        player = context["player_reports"][0]
        self.assertEqual(player["minutes"], 75)
        self.assertEqual((player["long_passes_ok"], player["long_passes"]), (1, 1))
        self.assertEqual((player["aerial_won"], player["aerial"]), (1, 1))
        self.assertEqual((player["shots_target"], player["shots"]), (1, 1))
        self.assertEqual(player["dominant_zone"], "Ataque")
        self.assertEqual(player["goals"], 0)
        self.assertEqual(player["goals_conceded"], 1)
        self.assertEqual(player["impact_delta"], 0.15)
        self.assertEqual(context["decisive_moments"][0]["reason_label"], "Acción decisiva")
        self.assertEqual(next(card["value"] for card in context["summary_cards"] if card["label"] == "Goles"), 0)

        context["pdf_url"] = "/coach/informes/partido/pdf/?match_id=1"
        html = render_to_string("football/match_staff_report.html", context, request=request)
        pdf_html = render_to_string("football/match_staff_report_pdf.html", context)
        identity_label = "Informe al cuerpo técnico · Postpartido"
        self.assertIn("Lectura de equipo", html)
        self.assertIn("Informe por jugador", html)
        self.assertIn("Momentos decisivos", html)
        self.assertIn(identity_label, html)
        self.assertIn('class="shell sqr a4-sheet"', html)
        self.assertIn("Jugador Uno", pdf_html)
        self.assertIn(identity_label, pdf_html)
        self.assertIn("#0F8A4B", pdf_html)


class MatchRatingAlgorithmTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name="Liga notas", slug="liga-notas", region="Malaga")
        self.season = Season.objects.create(competition=competition, name="2026/27 notas")
        self.team = Team.objects.create(name="Equipo notas", slug="equipo-notas")
        self.rival = Team.objects.create(name="Rival notas", slug="rival-notas")
        self.player = Player.objects.create(team=self.team, name="Jugador Nota", number=6, position="MC")
        self.match = Match.objects.create(
            season=self.season,
            home_team=self.team,
            away_team=self.rival,
            date=datetime.date(2026, 8, 2),
            stats_source=Match.STATS_SOURCE_MANUAL,
            home_score=2,
            away_score=2,
            is_closed=True,
        )

    def _event(self, event_type, result):
        return MatchEvent.objects.create(
            match=self.match,
            player=self.player,
            event_type=event_type,
            result=result,
            source_file="manual-recovery",
            system="touch-field-final",
        )

    def test_payload_covers_extended_fm_action_families(self):
        for event_type, result in (
            ("ROBO", "GANADO"),
            ("RECUPERACION ALTA", "GANADO"),
            ("PERDIDA FORZADA", "GANADO"),
            ("PERDIDA NO FORZADA", "PERDIDO"),
            ("REGATE", "GANADO"),
            ("CENTRO", "GANADO"),
            ("PASE EN LARGO", "GANADO"),
            ("CAIDA", "PERDIDO"),
            ("FALTA COMETIDA", "NEUTRAL"),
            ("FALTA RECIBIDA", "NEUTRAL"),
            ("GOL ENCAJADO", "EN CONTRA"),
        ):
            self._event(event_type, result)

        payload, _match_payload = views._build_player_match_stats_payload(self.team, self.player, self.match)

        self.assertEqual(payload["recoveries"], 2)
        self.assertEqual(payload["forced_turnovers"], 1)
        self.assertEqual(payload["unforced_turnovers"], 1)
        self.assertEqual((payload["dribbles_completed"], payload["dribbles_attempted"]), (1, 1))
        self.assertEqual((payload["crosses_completed"], payload["crosses_attempted"]), (1, 1))
        self.assertEqual((payload["long_passes_completed"], payload["long_passes_attempted"]), (1, 1))
        self.assertEqual(payload["retentions_lost"], 1)
        self.assertEqual(payload["fouls_committed"], 1)
        self.assertEqual(payload["fouls_received"], 1)
        self.assertEqual(payload["goals_conceded"], 1)
        self.assertEqual(payload["goals"], 0)
        self.assertEqual(payload["shot_attempts"], 0)
        self.assertEqual(payload["explicit_duels_total"], 0)

    def test_manual_source_uses_confirmed_actions_for_rating(self):
        for event_type in ("ROBO", "PASE", "PASE", "DUELO", "PERDIDA FORZADA"):
            self._event(event_type, "GANADO")

        rating = views._compute_match_rating(self.team, self.player, self.match, prefer_frozen=False)

        self.assertEqual(rating["method"], "actions")
        self.assertEqual(rating["confidence"], "alta")
        self.assertGreaterEqual(rating["rating"], 6.4)

    def test_positive_and_negative_events_move_rating_around_fm_average(self):
        common = {"total_actions": 10}
        positive = {
            **common,
            "recoveries": 4,
            "dribbles_attempted": 2,
            "dribbles_completed": 2,
        }
        negative = {
            **common,
            "forced_turnovers": 3,
            "unforced_turnovers": 4,
            "fouls_committed": 3,
            "shot_attempts": 2,
            "shots_on_target": 0,
        }

        positive_rating = views._auto_match_rating_from_stats(positive, "MC")
        negative_rating = views._auto_match_rating_from_stats(negative, "MC")
        self.assertGreater(positive_rating, 6.4)
        self.assertLessEqual(positive_rating, 6.8)
        self.assertLess(negative_rating, 6.4)

    def test_a_goal_and_solid_supporting_actions_do_not_create_an_extreme_rating(self):
        solid_scorer = {
            "total_actions": 20,
            "goals": 1,
            "pass_attempts": 10,
            "passes_completed": 8,
            "explicit_duels_total": 5,
            "explicit_duels_won": 3,
            "recoveries": 2,
        }

        rating = views._auto_match_rating_from_stats(solid_scorer, "DC")

        self.assertGreaterEqual(rating, 6.8)
        self.assertLessEqual(rating, 7.3)

    def test_contextual_consequences_and_unforced_errors_have_meaningful_weight(self):
        common = {"total_actions": 12, "pass_attempts": 8, "passes_completed": 6}
        neutral = views._auto_match_rating_from_stats(common, "MC")
        conceded_chance = views._auto_match_rating_from_stats(
            {**common, "contextual_impact": -0.25}, "MC"
        )
        conceded_goal = views._auto_match_rating_from_stats(
            {**common, "contextual_impact": -0.55}, "MC"
        )
        repeated_unforced_errors = views._auto_match_rating_from_stats(
            {**common, "unforced_turnovers": 4}, "MC"
        )

        self.assertLess(conceded_chance, neutral)
        self.assertLess(conceded_goal, conceded_chance)
        self.assertLessEqual(repeated_unforced_errors, neutral - 0.5)

    def test_persist_recalculates_stale_frozen_rating_and_includes_manual_events(self):
        for _index in range(5):
            self._event("ROBO", "GANADO")
        PlayerStatistic.objects.create(
            player=self.player,
            season=self.season,
            match=self.match,
            name="rating",
            value=5.0,
            context="auto-rating",
        )

        count = views._persist_match_ratings(self.team, self.match, notify=False)
        stored = PlayerStatistic.objects.get(
            player=self.player,
            match=self.match,
            name="rating",
            context="auto-rating",
        )

        self.assertEqual(count, 1)
        self.assertGreater(stored.value, 6.4)
