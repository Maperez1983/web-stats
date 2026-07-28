from django.test import TestCase

from football import views
from football.models import Competition, Match, MatchEvent, Player, Season, Team


class TeamOnlyGoalInferenceTests(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga SC", slug="liga-sc", region="Málaga")
        self.season = Season.objects.create(competition=self.comp, name="2025/26")
        self.team = Team.objects.create(name="SC FC", slug="sc-fc")
        self.player = Player.objects.create(team=self.team, name="Goleador")
        self.match = Match.objects.create(home_team=self.team, season=self.season, round="J1")

    def _goal(self, player, side, minute):
        return MatchEvent.objects.create(
            match=self.match, player=player, event_type="Gol", result="Gol",
            minute=minute, raw_data={"team_side": side},
            source_file="registro-acciones", system="touch-field-final",
        )

    def test_team_only_conceded_goal_counts_against(self):
        # gol a favor (con goleador) + gol en contra registrado como evento de EQUIPO (sin jugador)
        self._goal(self.player, "for", 10)
        self._goal(None, "against", 30)  # antes se perdía por el filtro player__team
        self.assertEqual(views._infer_team_goals_from_events(self.match, self.team), 1)
        self.assertEqual(views._infer_team_goals_against_from_events(self.match, self.team), 1)

    def test_score_sync_fills_both(self):
        self._goal(self.player, "for", 10)
        self._goal(None, "against", 30)
        views._sync_match_score_from_events(self.match, self.team)
        self.match.refresh_from_db()
        self.assertEqual(self.match.home_score, 1)   # somos local -> goles a favor
        self.assertEqual(self.match.away_score, 1)   # goles en contra
        self.assertEqual(self.match.result, "1-1")

    def test_team_only_for_goal_counts(self):
        # un gol a favor registrado como evento de equipo (sin goleador asignado) también cuenta
        self._goal(None, "for", 15)
        self.assertEqual(views._infer_team_goals_from_events(self.match, self.team), 1)
        self.assertEqual(views._infer_team_goals_against_from_events(self.match, self.team), 0)

    def test_event_kind_reads_db_column(self):
        # La columna kind (Fase 4) manda sobre el texto en un MatchEvent real.
        from football.event_taxonomy import event_kind
        ev = MatchEvent.objects.create(
            match=self.match, player=self.player, event_type="Tarjeta Amarilla", result="Amarilla",
            kind="red_card", source_file="registro-acciones", system="touch-field",
        )
        self.assertEqual(event_kind(ev), "red_card")
