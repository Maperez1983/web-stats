import datetime

from django.test import TestCase

from football import views
from football.event_taxonomy import is_red_card_event
from football.models import Competition, Match, MatchEvent, Player, Season, Team


class SecondYellowPromotionTests(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga SY", slug="liga-sy", region="Málaga")
        self.season = Season.objects.create(competition=self.comp, name="2025/26")
        self.team = Team.objects.create(name="SY FC", slug="sy-fc")
        self.player = Player.objects.create(team=self.team, name="Jugador Tarjeta")
        self.match = Match.objects.create(home_team=self.team, season=self.season, round="J1")

    def _card(self, event_type, result):
        return MatchEvent.objects.create(
            match=self.match, player=self.player, event_type=event_type, result=result,
            source_file="registro-acciones", system="touch-field",
        )

    def _run(self, action_type="Tarjeta Amarilla", result="Amarilla", zone="Tarjeta Amarilla"):
        return views._maybe_promote_second_yellow(
            self.match, self.player, action_type, result, zone, ""
        )

    def test_first_yellow_not_promoted(self):
        at, res, zone, tercio, promoted = self._run()
        self.assertFalse(promoted)
        self.assertEqual(at, "Tarjeta Amarilla")

    def test_second_yellow_promoted_to_red(self):
        self._card("Tarjeta Amarilla", "Amarilla")  # 1ª amarilla ya registrada
        at, res, zone, tercio, promoted = self._run()
        self.assertTrue(promoted)
        self.assertEqual(at, "Tarjeta Roja")
        self.assertIn("2ª amarilla", res)
        self.assertTrue(is_red_card_event(at, res, zone))

    def test_reason_preserved_on_promotion(self):
        self._card("Tarjeta Amarilla", "Amarilla")
        at, res, zone, tercio, promoted = self._run(result="Amarilla · Falta táctica")
        self.assertTrue(promoted)
        self.assertIn("Falta táctica", res)

    def test_not_promoted_if_already_red(self):
        self._card("Tarjeta Amarilla", "Amarilla")
        self._card("Tarjeta Roja", "Roja")  # ya expulsado
        at, res, zone, tercio, promoted = self._run()
        self.assertFalse(promoted)
        self.assertEqual(at, "Tarjeta Amarilla")

    def test_incoming_red_not_touched(self):
        self._card("Tarjeta Amarilla", "Amarilla")
        at, res, zone, tercio, promoted = self._run(
            action_type="Tarjeta Roja", result="Roja", zone="Tarjeta Roja"
        )
        self.assertFalse(promoted)
        self.assertEqual(at, "Tarjeta Roja")

    def test_promoted_red_triggers_sanction_detection(self):
        # La roja sintetizada debe detectarse como roja (para que la sanción de la
        # jornada siguiente NO se pierda).
        self._card("Tarjeta Amarilla", "Amarilla")
        at, res, zone, tercio, promoted = self._run()
        ev = MatchEvent.objects.create(
            match=self.match, player=self.player, event_type=at, result=res, zone=zone,
            source_file="registro-acciones", system="touch-field",
        )
        self.assertTrue(is_red_card_event(ev.event_type, ev.result, ev.zone))
