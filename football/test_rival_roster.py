from django.test import TestCase

from football.models import Player, RivalPlayer, Team
from football.rival_roster_services import import_rival_squad, parse_rival_squad

# HTML mínimo que imita la tabla de plantilla de laPreferente (#tablePlantilla).
SQUAD_HTML = """
<table id="tablePlantilla">
  <tr><td></td><td></td><td>Jugador</td><td>DEMARCACIÓN</td><td>Edad</td><td>PC</td><td>PJ</td><td>PT</td><td>Min</td><td>Goles</td><td>TA</td><td>TR</td></tr>
  <tr><td></td><td></td><td>Jugador</td><td>Porteros (1)</td><td>Edad</td><td>PC</td><td>PJ</td><td>PT</td><td>Min</td><td>Goles</td><td>TA</td><td>TR</td></tr>
  <tr>
    <td><img src="imagenes/jugadores/20252026/40000-mini.png"/></td><td></td>
    <td><a href="J40000C26717/cd-x/keeper.html">Keeper</a> Portero Prueba</td>
    <td>Portero</td><td></td><td>-</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td>
  </tr>
  <tr><td></td><td></td><td>Jugador</td><td>Defensas (1)</td><td>Edad</td><td>PC</td><td>PJ</td><td>PT</td><td>Min</td><td>Goles</td><td>TA</td><td>TR</td></tr>
  <tr>
    <td><img src="imagenes/jugadores/20252026/86658-mini.png"/></td><td>15</td>
    <td><a href="J86658C26717/cd-x/juan.html">Juan</a> Juan Plaza Gallego</td>
    <td>Central</td><td></td><td>30</td><td>3</td><td>5</td><td>0</td><td>410</td><td>2</td><td>1</td><td>0</td>
  </tr>
</table>
"""


class RivalSquadParserTests(TestCase):
    def test_parses_players_only(self):
        rows = parse_rival_squad(SQUAD_HTML)
        self.assertEqual(len(rows), 2)  # ignora cabeceras de grupo (Porteros/Defensas)

    def test_field_extraction(self):
        rows = {r["source_player_id"]: r for r in parse_rival_squad(SQUAD_HTML)}
        juan = rows["86658"]
        self.assertEqual(juan["full_name"], "Juan Plaza Gallego")
        self.assertEqual(juan["alias"], "Juan")
        self.assertEqual(juan["number"], 15)
        self.assertEqual(juan["position"], "Central")
        self.assertEqual(juan["line"], "def")   # Central -> defensa
        self.assertEqual(juan["age"], 30)
        self.assertEqual(juan["goals"], 2)
        self.assertTrue(juan["photo_url"].endswith("86658-mini.png"))
        # El portero mapea a gk y su edad "-" queda None.
        gk = rows["40000"]
        self.assertEqual(gk["line"], "gk")
        self.assertIsNone(gk["age"])


class RivalSquadImportTests(TestCase):
    def setUp(self):
        self.rival = Team.objects.create(name="C.D. Rival", slug="cd-rival")
        self.rows = parse_rival_squad(SQUAD_HTML)

    def test_import_creates_rival_players_not_players(self):
        players_before = Player.objects.count()
        res = import_rival_squad(self.rival, self.rows, season_label="2026/2027")
        self.assertEqual(res["created"], 2)
        self.assertEqual(RivalPlayer.objects.filter(team=self.rival).count(), 2)
        # AISLAMIENTO: no se crea ningún Player.
        self.assertEqual(Player.objects.count(), players_before)

    def test_reimport_is_idempotent_by_jid(self):
        import_rival_squad(self.rival, self.rows)
        res = import_rival_squad(self.rival, self.rows)  # segunda vez
        self.assertEqual(res["created"], 0)
        self.assertEqual(res["updated"], 2)
        self.assertEqual(RivalPlayer.objects.filter(team=self.rival).count(), 2)  # no duplica

    def test_missing_player_is_deactivated_on_refresh(self):
        import_rival_squad(self.rival, self.rows)
        # Reimportar sin uno de los dos -> el que falta queda inactivo (no borrado).
        fewer = [r for r in self.rows if r["source_player_id"] == "86658"]
        res = import_rival_squad(self.rival, fewer)
        self.assertEqual(res["deactivated"], 1)
        self.assertEqual(RivalPlayer.objects.filter(team=self.rival, is_active=True).count(), 1)

    def test_matched_player_detected_by_jid(self):
        # "Reconocido como": un Player propio con la URL de la Preferente del mismo J-id (ex-jugador
        # nuestro u ojeado que ha fichado por el rival) se enlaza SIN duplicar.
        my_team = Team.objects.create(name="C.D. Benagalbón", slug="cd-bena")
        hiago = Player.objects.create(
            team=my_team, name="Juan Plaza Gallego", is_active=True,
            preferente_profile_url="https://lapreferente.com/J86658C26717/cd-x/juan.html",
        )
        res = import_rival_squad(self.rival, self.rows)
        self.assertEqual(res["matched"], 1)
        rp = RivalPlayer.objects.get(team=self.rival, source_player_id="86658")
        self.assertEqual(rp.matched_player_id, hiago.id)
        # Sigue siendo RivalPlayer aislado: no se ha tocado el Player.
        self.assertTrue(Player.objects.filter(id=hiago.id, team=my_team).exists())
