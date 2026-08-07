"""La convocatoria automática no puede crear una nueva cada vez que se abre el partido."""
from datetime import date

from django.test import TestCase

from football.models import (
    Competition,
    ConvocationRecord,
    Group,
    Match,
    Player,
    Season,
    Team,
)
from football.views import _ensure_matchday_convocation_record


class ConvocatoriaAutomaticaTests(TestCase):
    def setUp(self):
        comp = Competition.objects.create(name="Liga C", slug="liga-c", region="Andalucia")
        self.temporada = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        grupo = Group.objects.create(season=self.temporada, name="G", slug="g-c")
        self.team = Team.objects.create(name="Benagalbón C", slug="ben-c", group=grupo, is_primary=True)
        self.rival = Team.objects.create(name="Rival C", slug="riv-c", group=grupo)
        self.match = Match.objects.create(
            season=self.temporada, home_team=self.team, away_team=self.rival,
            date=date(2026, 8, 12), context=Match.CONTEXT_FRIENDLY,
        )
        for i in range(3):
            Player.objects.create(team=self.team, name=f"Jugador {i}", number=i + 1)

    def test_abrir_el_partido_dos_veces_no_crea_dos_convocatorias(self):
        primera = _ensure_matchday_convocation_record(self.team, match=self.match)
        self.assertIsNotNone(primera)
        segunda = _ensure_matchday_convocation_record(self.team, match=self.match)
        self.assertEqual(primera.id, segunda.id)
        self.assertEqual(ConvocationRecord.objects.filter(team=self.team, match=self.match).count(), 1)

    def test_reutiliza_la_convocatoria_del_partido_aunque_no_sea_la_actual(self):
        """El fallo real: al cambiar el foco a otro partido, la del primero dejaba de ser
        'actual' y al volver se creaba otra."""
        previa = ConvocationRecord.objects.create(team=self.team, match=self.match, is_current=False)
        previa.players.set(Player.objects.filter(team=self.team))

        record = _ensure_matchday_convocation_record(self.team, match=self.match)

        self.assertEqual(record.id, previa.id)
        self.assertEqual(ConvocationRecord.objects.filter(team=self.team, match=self.match).count(), 1)
        record.refresh_from_db()
        self.assertTrue(record.is_current, "al reutilizarla vuelve a ser la del partido en curso")

    def test_sin_jugadores_no_se_guarda_una_convocatoria_vacia(self):
        Player.objects.filter(team=self.team).delete()
        record = _ensure_matchday_convocation_record(self.team, match=self.match)
        self.assertIsNone(record)
        self.assertEqual(ConvocationRecord.objects.filter(team=self.team, match=self.match).count(), 0)
