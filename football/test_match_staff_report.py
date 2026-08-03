import datetime
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string

from football import views
from football.models import (
    Competition,
    Match,
    MatchEvent,
    MatchLineup,
    Player,
    PlayerStatistic,
    RivalConvocationRecord,
    Season,
    Team,
)


class MatchStaffReportTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name="Liga informe", slug="liga-informe", region="Malaga")
        self.season = Season.objects.create(competition=competition, name="2026/27")
        self.team = Team.objects.create(name="Equipo informe", slug="equipo-informe")
        self.rival = Team.objects.create(name="C.D. RINCON", slug="rival-informe")
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

    @patch("football.views.resolve_team_crest_url", return_value="https://media.example/Unknown.png")
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
        summary = {card["label"]: card["value"] for card in context["summary_cards"]}
        self.assertEqual(summary["A puerta"], 1)
        self.assertEqual(summary["Fuera"], 0)
        self.assertEqual(summary["Córners favor"], 4)
        self.assertEqual(summary["Córners contra"], 7)

        professional = context["professional_report"]
        self.assertEqual(context["team_name"], "Equipo informe")
        self.assertEqual(context["opponent_name"], "C.D. RINCON")
        self.assertTrue(context["crest_src"])
        self.assertTrue(context["opponent_crest_src"])
        self.assertTrue(context["opponent_crest_src"].startswith("data:image/jpeg;base64,"))
        exact = {row["label"]: (row["team"], row["opponent"]) for row in professional["exact_comparison"]}
        self.assertEqual(exact["Disparos"], (1, 7))
        self.assertEqual(exact["A puerta"], (1, 2))
        self.assertEqual(exact["Córners"], (4, 7))
        percentages = {row["label"]: row["pct"] for row in professional["percentage_metrics"]}
        self.assertEqual(percentages["Precisión de pase"], 100)
        self.assertEqual(percentages["Pase largo"], 100)
        self.assertEqual(percentages["Duelos"], 100)
        self.assertEqual(percentages["Tiros a puerta"], 100)
        self.assertEqual(percentages["Conversión total"], 0)
        self.assertEqual(percentages["Conversión a puerta"], 0)
        self.assertEqual(professional["shot_comparison"]["opponent_pct"], 28.6)
        self.assertTrue(all(row["value"].endswith("%") for row in professional["with_ball"]))
        self.assertTrue(all(row["value"].endswith("%") for row in professional["without_ball"]))
        self.assertEqual(professional["with_ball"][0]["value"], "100%")
        self.assertEqual(professional["without_ball"][3]["value"], "28.6%")
        self.assertEqual([row["level"] for row in professional["data_quality"]], ["Exacto", "Derivado", "No disponible"])

        context["pdf_url"] = "/coach/informes/partido/pdf/?match_id=1"
        html = render_to_string("football/match_staff_report.html", context, request=request)
        pdf_html = render_to_string("football/match_staff_report_pdf.html", context)
        identity_label = "Informe al cuerpo técnico · Postpartido"
        for section_title in (
            "Resumen ejecutivo",
            "Con balón",
            "Sin balón y transiciones",
            "Balón parado",
            "Rendimiento individual",
            "Conclusiones y microciclo",
        ):
            self.assertIn(section_title, html)
            self.assertIn(section_title, pdf_html)
        self.assertIn("Posesión real", html)
        self.assertIn("No disponible", html)
        self.assertNotIn("Posesión aproximada", html)
        self.assertNotIn("xG estimado", html)
        self.assertIn(identity_label, html)
        self.assertIn('class="shell sqr a4-sheet"', html)
        self.assertIn("Jugador Uno", pdf_html)
        self.assertIn("Acciones ganadas", html)
        self.assertIn("Nuestro equipo", html)
        self.assertIn("Once rival no disponible", html)
        self.assertIn('class="report-crest"', html)
        self.assertIn("Escudo de Equipo informe", html)
        self.assertNotIn("Unknown.png", html)
        self.assertIn('class="pro-player-list"', html)
        self.assertNotIn('class="pro-pitch-player"', html)
        self.assertNotIn("Qué cambió el encuentro", html)
        self.assertNotIn("Qué cambió el encuentro", pdf_html)
        self.assertNotIn("Aportación principal", html)
        self.assertIn(identity_label, pdf_html)
        self.assertIn("Resumen del partido", pdf_html)
        self.assertNotIn("El partido, en una página", pdf_html)
        self.assertIn('class="pro-team-crest"', pdf_html)
        self.assertIn("#0F8A4B", pdf_html)

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_report_uses_saved_lineups_without_filling_missing_players(self, _crest):
        MatchLineup.objects.create(
            team=self.team,
            match=self.match,
            lineup_data={
                "starters": [
                    {"id": str(self.player.id), "x_pct": 24, "y_pct": 51},
                ],
                "bench": [],
            },
        )
        RivalConvocationRecord.objects.create(
            team=self.team,
            match=self.match,
            rival_team=self.rival,
            convocation_data=[{"code": "rival-9", "name": "Delantero Rival", "number": 9, "position": "DC"}],
            lineup_data={
                "starters": [{"code": "rival-9", "x_pct": 76, "y_pct": 50}],
                "bench": [],
            },
        )
        request = RequestFactory().get("/coach/informes/partido/")
        request.user = AnonymousUser()

        context = views._match_staff_report_context(request, match=self.match, primary_team=self.team)
        tactical = context["professional_report"]["tactical"]

        self.assertEqual(len(tactical["own"]["starters"]), 1)
        self.assertEqual(tactical["own_missing"], 10)
        self.assertEqual(tactical["own"]["starters"][0]["name"], "JUGADOR UNO")
        self.assertEqual(tactical["own"]["starters"][0]["board_name"], "JUGADOR")
        self.assertTrue(tactical["own"]["starters"][0]["has_coordinates"])
        self.assertEqual(len(tactical["rival"]["starters"]), 1)
        self.assertEqual(tactical["rival_missing"], 10)
        self.assertEqual(tactical["rival"]["starters"][0]["name"], "Delantero Rival")

        html = render_to_string("football/match_staff_report.html", context, request=request)
        self.assertIn("left:24.0%;top:51.0%;", html)
        self.assertIn("left:76.0%;top:50.0%;", html)
        self.assertIn('class="pro-xi-token', html)
        self.assertIn('class="pro-xi-disc"', html)
        self.assertIn("coach_home_pitch_surface.png", html)
        self.assertNotIn("left:24,0%", html)

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_report_counts_only_decided_contested_actions_as_duels(self, _crest):
        for index, (event_type, result) in enumerate(
            (
                ("DUELO AEREO", "GANADO"),
                ("ROBO", "GANADO"),
                ("REGATE", "GANADO"),
                ("CAIDA", "PERDIDO"),
                ("REGATE", "NEUTRAL"),
                ("PRESION ALTA", "GANADO"),
                ("RECUPERACION ALTA", "GANADO"),
                ("INTERCEPCION", "GANADO"),
                ("FALTA COMETIDA", "PERDIDO"),
            ),
            start=1,
        ):
            self._event(
                event_type,
                result,
                minute=index,
                period=1,
                zone="Medio centro",
                tercio="Construcción",
            )

        request = RequestFactory().get("/coach/informes/partido/")
        request.user = AnonymousUser()
        context = views._match_staff_report_context(request, match=self.match, primary_team=self.team)

        player = context["player_reports"][0]
        self.assertEqual((player["duels_won"], player["duels"]), (3, 4))
        self.assertEqual((player["aerial_won"], player["aerial"]), (1, 1))
        percentages = {
            row["label"]: (row["pct"], row["detail"])
            for row in context["professional_report"]["percentage_metrics"]
        }
        self.assertEqual(percentages["Duelos"], (75, "3/4"))
        self.assertEqual(percentages["Duelos aéreos"], (100, "1/1"))

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_player_report_is_narrative_and_keeps_percentage_kpis_out(self, _crest):
        self.match.home_score = 2
        self.match.away_score = 2
        self.match.is_closed = True
        self.match.save(update_fields=["home_score", "away_score", "is_closed"])
        self._event("PASE", "GANADO", minute=18, period=1, zone="Medio centro", tercio="Construcción")
        self._event("ROBO", "GANADO", minute=31, period=1, zone="Medio centro", tercio="Construcción")

        request = RequestFactory().get("/player/informe/")
        request.user = AnonymousUser()
        context = views._player_match_report_context(
            request,
            primary_team=self.team,
            player=self.player,
            match=self.match,
        )
        context.update({"is_player_report": True, "is_player_account": True, "pdf_url": "/informe.pdf"})
        html = render_to_string("football/player_match_stats.html", context, request=request)
        pdf_html = render_to_string("football/player_match_report_pdf.html", context)

        self.assertEqual(
            {item["label"]: item["value"] for item in context["global_summary"]},
            {"Resultado": "2 - 2", "A puerta": 0, "Fuera": 0, "Córners favor": 0, "Córners contra": 0},
        )
        self.assertIn("Lo que aportaste", html)
        self.assertIn("Siguiente foco", html)
        self.assertNotIn("Precisión de pase", html)
        self.assertNotIn("Porcentaje", html)
        self.assertNotIn("Precisión de pase", pdf_html)

    @patch("football.views.resolve_team_crest_url", return_value="")
    def test_error_that_cost_a_goal_is_not_counted_as_a_goal_scored(self, _crest):
        event = self._event(
            "PÉRDIDA DE MARCA", "PERDIDO", minute=34, period=1, zone="Defensa Centro", tercio="Defensa"
        )
        event.observation = "Pérdida de marca que terminó en gol rival"
        event.raw_data = {"impact": {"code": "goal_conceded", "reason": "lost_mark"}}
        event.save(update_fields=["observation", "raw_data"])

        request = RequestFactory().get("/coach/informes/partido/")
        request.user = AnonymousUser()
        context = views._match_staff_report_context(request, match=self.match, primary_team=self.team)

        goals_card = next(card for card in context["summary_cards"] if card["label"] == "Goles")
        self.assertEqual(goals_card["value"], 0)
        self.assertEqual(context["player_reports"][0]["goals"], 0)
        self.assertEqual(context["player_reports"][0]["impact_delta"], -0.55)
        self.assertEqual(context["timeline"], [])


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
        self.assertEqual((payload["duels_won"], payload["duels_total"]), (2, 3))
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

    def test_error_marked_as_won_is_never_a_success_or_won_duel(self):
        self._event("ERROR FORZADO", "GANADO")

        payload, _match_payload = views._build_player_match_stats_payload(
            self.team, self.player, self.match
        )

        self.assertEqual(payload["forced_turnovers"], 1)
        self.assertEqual(payload["successes"], 0)
        self.assertEqual(payload["duels_total"], 0)
        self.assertEqual(payload["duels_won"], 0)

        context = views._match_staff_report_context(
            RequestFactory().get("/coach/informes/partido/"),
            match=self.match,
            primary_team=self.team,
        )
        report = next(row for row in context["player_reports"] if row["player_id"] == self.player.id)
        self.assertEqual(report["success_rate"], 0)

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

    def test_goal_does_not_hide_low_overall_execution(self):
        error_heavy_scorer = {
            "total_actions": 23,
            "successes": 9,
            "goals": 1,
            "explicit_duels_total": 5,
            "explicit_duels_won": 5,
            "recoveries": 1,
            "forced_turnovers": 6,
            "retentions_lost": 6,
            "long_passes_attempted": 1,
            "fouls_committed": 2,
            "fouls_received": 1,
            "minutes_played": 45,
        }

        rating = views._auto_match_rating_from_stats(error_heavy_scorer, "LD")

        self.assertLessEqual(rating, 6.5)

    def test_defensive_production_has_extra_positional_value(self):
        defensive_work = {
            "total_actions": 20,
            "successes": 15,
            "recoveries": 4,
            "explicit_duels_total": 4,
            "explicit_duels_won": 4,
            "forced_turnovers": 2,
            "retentions_lost": 4,
            "minutes_played": 45,
        }

        central_rating = views._auto_match_rating_from_stats(defensive_work, "DFC")
        forward_rating = views._auto_match_rating_from_stats(defensive_work, "DC")

        self.assertGreaterEqual(central_rating, forward_rating + 0.1)

        low_execution = {**defensive_work, "successes": 9}
        low_execution_central = views._auto_match_rating_from_stats(low_execution, "DFC")
        low_execution_forward = views._auto_match_rating_from_stats(low_execution, "DC")
        self.assertEqual(low_execution_central, low_execution_forward)

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

    def test_testimonial_minutes_cap_routine_actions_but_not_a_goal(self):
        routine = {
            "total_actions": 2,
            "pass_attempts": 2,
            "passes_completed": 2,
            "minutes_played": 2,
        }

        routine_rating = views._auto_match_rating_from_stats(routine, "MC")
        scorer_rating = views._auto_match_rating_from_stats({**routine, "goals": 1}, "DC")

        self.assertLessEqual(routine_rating, 6.4)
        self.assertGreater(scorer_rating, routine_rating)

    def test_goalkeeper_routine_distribution_is_almost_neutral(self):
        distribution = {
            "total_actions": 12,
            "pass_attempts": 10,
            "passes_completed": 10,
            "long_passes_attempted": 2,
            "long_passes_completed": 2,
            "minutes_played": 90,
        }

        goalkeeper_rating = views._auto_match_rating_from_stats(distribution, "POR")
        midfielder_rating = views._auto_match_rating_from_stats(distribution, "MC")

        self.assertLessEqual(goalkeeper_rating, 6.5)
        self.assertLess(goalkeeper_rating, midfielder_rating)

    def test_short_appearance_does_not_dilute_a_decisive_negative_error(self):
        rating = views._auto_match_rating_from_stats(
            {
                "total_actions": 2,
                "pass_attempts": 1,
                "passes_completed": 1,
                "minutes_played": 2,
                "contextual_impact": -0.55,
            },
            "MC",
        )

        self.assertLessEqual(rating, 5.9)

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
