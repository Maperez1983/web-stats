"""Captura rápida: la pantalla de banda guarda de verdad y no ensucia nuestras estadísticas."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    AppUserRole,
    Competition,
    ConvocationRecord,
    Group,
    Match,
    MatchEvent,
    Player,
    Season,
    Team,
    Workspace,
    WorkspaceMembership,
)
from football.views import MATCH_RIVAL_SOURCE_FILE


class MatchActionCaptureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="captura-coach", email="captura@example.com", password="pass-1234"
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name="Liga Captura", slug="liga-captura", region="Andalucia")
        season = Season.objects.create(competition=competition, name="2026/2027", is_current=True)
        group = Group.objects.create(season=season, name="Grupo Captura", slug="grupo-captura")
        self.team = Team.objects.create(name="Benagalbón Captura", slug="benagalbon-captura", group=group, is_primary=True)
        self.rival = Team.objects.create(name="Rival Captura", slug="rival-captura", group=group)
        self.match = Match.objects.create(
            season=season, group=group, home_team=self.team, away_team=self.rival, round="1", date=date(2026, 8, 30)
        )
        self.workspace = Workspace.objects.create(
            name="Benagalbón Captura",
            slug="benagalbon-captura-ws",
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={"dashboard": True, "match_actions": True},
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_ADMIN
        )
        self.portero = Player.objects.create(team=self.team, name="Tadeo Ruiz", number=1, position="Portero")
        self.jugador = Player.objects.create(team=self.team, name="Antonio Martinez", number=6, position="Medio centro")
        self.suplente = Player.objects.create(team=self.team, name="Pablo Nake", number=25, position="Delantero")
        self.convocation = ConvocationRecord.objects.create(team=self.team, match=self.match, is_current=True)
        self.convocation.players.add(self.portero, self.jugador, self.suplente)
        self.client.force_login(self.user)

    def _config(self):
        page = self.client.get(reverse("match-action-capture"), {"match_id": self.match.id})
        self.assertEqual(page.status_code, 200)
        html = page.content.decode("utf-8")
        marca = '<script id="capture-config" type="application/json">'
        ini = html.index(marca) + len(marca)
        fin = html.index("</script>", ini)
        return json.loads(html[ini:fin])

    def test_la_pantalla_abre_con_el_once_y_el_vocabulario_real(self):
        config = self._config()
        self.assertTrue(config["once"], "la pantalla necesita un once para poder tocar")
        acciones = [s["accion"] for s in config["sellos"]]
        self.assertIn("Pase a la espalda", acciones)
        # Lo que él cuenta en banda tiene que estar a un toque: suelo y aire por separado,
        # el pase largo aparte del corto, y la pérdida forzada distinta de la no forzada.
        self.assertIn("Duelo", acciones)
        self.assertIn("Duelo aéreo", acciones)
        self.assertIn("Pase largo", acciones)
        perdida = [s for s in config["sellos"] if s["id"] == "Pérdida"][0]
        self.assertEqual(
            [b["accion"] for b in perdida["botones"]],
            ["Pérdida forzada", "Pérdida no forzada"],
        )
        # Falta y pérdida se leen con palabras: un ✅/❌ ahí no dice cuál es cuál.
        falta = [s for s in config["sellos"] if s["id"] == "Falta"][0]
        for boton in falta["botones"] + perdida["botones"]:
            self.assertNotIn("e", boton)
        # El portero tiene que venir marcado: no lanza los ABP.
        porteros = [j for j in config["once"] if j.get("gk")]
        self.assertEqual(len(porteros), 1)
        self.assertEqual(porteros[0]["n"], 1)

    def test_una_accion_capturada_se_guarda_como_las_del_registro_clasico(self):
        respuesta = self.client.post(
            reverse("match-action-record"),
            {
                "match_id": self.match.id,
                "player": self.jugador.id,
                "action_type": "Pase a la espalda",
                "result": "OK",
                "zone": "Medio Centro",
                "minute": 12,
                "period": 1,
                "team_side": "for",
                "client_event_uid": "cap-1",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        evento = MatchEvent.objects.get(match=self.match, player=self.jugador)
        self.assertEqual(evento.source_file, "registro-acciones")
        self.assertEqual(evento.system, "touch-field")
        self.assertEqual(evento.tercio, "Construcción")

    def test_el_mismo_uid_no_duplica_la_accion(self):
        datos = {
            "match_id": self.match.id,
            "player": self.jugador.id,
            "action_type": "Robo",
            "result": "OK",
            "zone": "Medio Centro",
            "minute": 20,
            "period": 1,
            "client_event_uid": "cap-repetido",
        }
        self.client.post(reverse("match-action-record"), datos)
        self.client.post(reverse("match-action-record"), datos)
        self.assertEqual(MatchEvent.objects.filter(match=self.match, event_type="Robo").count(), 1)

    def test_el_gol_del_rival_no_cuenta_como_gol_nuestro(self):
        respuesta = self.client.post(
            reverse("match-action-rival"),
            {"match_id": self.match.id, "action_type": "Disparo", "result": "GOL", "minute": 33, "period": 1},
        )
        self.assertEqual(respuesta.status_code, 200)
        evento = MatchEvent.objects.get(match=self.match, source_file=MATCH_RIVAL_SOURCE_FILE)
        self.assertIsNone(evento.player)
        self.assertEqual(evento.raw_data.get("team_side"), "against")
        # Lo que cuenta el resto de la app (acta, marcador, fichas) filtra por la fuente nuestra.
        self.assertEqual(MatchEvent.objects.filter(match=self.match, source_file="registro-acciones").count(), 0)

    def test_el_rival_tambien_se_puede_deshacer(self):
        self.client.post(
            reverse("match-action-rival"),
            {"match_id": self.match.id, "action_type": "Disparo", "result": "EN CONTRA", "minute": 10, "period": 1,
             "client_event_uid": "riv-1"},
        )
        evento = MatchEvent.objects.get(match=self.match, source_file=MATCH_RIVAL_SOURCE_FILE)
        respuesta = self.client.post(
            reverse("match-action-rival"),
            {"match_id": self.match.id, "event_id": evento.id, "borrar": "1"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(MatchEvent.objects.filter(id=evento.id).exists())

    def test_el_rival_no_duplica_con_el_mismo_uid(self):
        datos = {"match_id": self.match.id, "action_type": "Saque de esquina", "result": "EN CONTRA",
                 "minute": 5, "period": 1, "client_event_uid": "riv-repetido"}
        self.client.post(reverse("match-action-rival"), datos)
        self.client.post(reverse("match-action-rival"), datos)
        self.assertEqual(MatchEvent.objects.filter(match=self.match, source_file=MATCH_RIVAL_SOURCE_FILE).count(), 1)

    def test_la_segunda_amarilla_la_sigue_decidiendo_el_servidor(self):
        for minuto in (30, 55):
            self.client.post(
                reverse("match-action-record"),
                {
                    "match_id": self.match.id,
                    "player": self.jugador.id,
                    "action_type": "Tarjeta Amarilla",
                    "zone": "Tarjeta Amarilla",
                    "result": "Amarilla",
                    "minute": minuto,
                    "period": 2,
                    "client_event_uid": "cap-amarilla-%s" % minuto,
                },
            )
        tipos = list(
            MatchEvent.objects.filter(match=self.match, player=self.jugador).values_list("event_type", flat=True)
        )
        self.assertIn("Tarjeta Roja", tipos)

    def test_la_pasada_de_detalle_escribe_sobre_la_misma_accion(self):
        self.client.post(
            reverse("match-action-record"),
            {
                "match_id": self.match.id,
                "player": self.jugador.id,
                "action_type": "Pase",
                "result": "OK",
                "zone": "Medio Centro",
                "minute": 8,
                "period": 1,
            },
        )
        evento = MatchEvent.objects.get(match=self.match, event_type="Pase")
        respuesta = self.client.post(
            reverse("match-action-update"),
            {
                "match_id": self.match.id,
                "event_id": evento.id,
                "player": self.jugador.id,
                "action_type": "Pase",
                "result": "OK",
                "zone": "Medio Centro",
                "observation": "Clave",
                "minute": 8,
                "period": 1,
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        evento.refresh_from_db()
        self.assertEqual(evento.observation, "Clave")
        self.assertEqual(MatchEvent.objects.filter(match=self.match, event_type="Pase").count(), 1)

    def test_al_recargar_la_pantalla_el_historial_sigue_ahi(self):
        self.client.post(
            reverse("match-action-record"),
            {
                "match_id": self.match.id,
                "player": self.jugador.id,
                "action_type": "Disparo",
                "result": "GOL",
                "zone": "Ataque Centro",
                "minute": 61,
                "period": 2,
            },
        )
        config = self._config()
        acciones = [e["action"] for e in config["eventos"]]
        self.assertIn("Disparo", acciones)


class ValoracionDesdeLaCapturaTests(MatchActionCaptureTests):
    """La nota tiene que leer lo que se captura, y no castigar por participar."""

    def _accion(self, jugador, accion, resultado, veces=1, minuto=10):
        for i in range(veces):
            MatchEvent.objects.create(
                match=self.match, player=jugador, minute=minuto + i, period=1,
                event_type=accion, result=resultado, zone="Medio Centro", tercio="Construcción",
                source_file="registro-acciones", system="touch-field", raw_data={"team_side": "for"},
            )

    def _stats(self, jugador):
        from football.views import _build_player_match_stats_payload

        datos = _build_player_match_stats_payload(self.team, jugador, self.match)
        return datos[0] if isinstance(datos, tuple) else datos

    def test_una_falta_cometida_no_es_un_gol_encajado(self):
        self._accion(self.jugador, "Falta", "EN CONTRA", veces=3)
        stats = self._stats(self.jugador)
        self.assertEqual(stats["goals_conceded"], 0, "una falta no puede contar como gol encajado")
        self.assertEqual(stats["fouls_committed"], 3)

    def test_la_falta_recibida_se_cuenta_como_recibida(self):
        self._accion(self.jugador, "Falta", "A FAVOR", veces=2)
        stats = self._stats(self.jugador)
        self.assertEqual(stats["fouls_received"], 2)
        self.assertEqual(stats["fouls_committed"], 0)

    def test_el_gol_del_rival_si_cuenta_como_encajado(self):
        self._accion(self.portero, "Gol encajado", "EN CONTRA", veces=1)
        self.assertEqual(self._stats(self.portero)["goals_conceded"], 1)

    def test_el_trabajo_sin_balon_puntua(self):
        self._accion(self.jugador, "Presión alta", "OK", veces=3)
        self._accion(self.jugador, "Juego de espaldas", "OK", veces=3)
        self._accion(self.jugador, "Desmarque", "OK", veces=2)
        stats = self._stats(self.jugador)
        self.assertEqual(stats["high_press_won"], 3)
        self.assertEqual(stats["back_to_goal_won"], 3)
        self.assertEqual(stats["off_ball_runs"], 2)

    def test_el_abp_mal_ejecutado_resta(self):
        from football.views import _auto_match_rating_from_stats

        base = {"total_actions": 12, "successes": 8}
        bien = dict(base, set_pieces_taken=3, set_pieces_ok=3)
        mal = dict(base, set_pieces_taken=3, set_pieces_ok=0)
        self.assertGreater(
            _auto_match_rating_from_stats(bien, "Mediocentro"),
            _auto_match_rating_from_stats(mal, "Mediocentro"),
        )

    def test_participar_mucho_no_puede_hundir_la_nota(self):
        """El que toca 40 balones con 50% no puede salir por debajo del que toca 9 con 33%."""
        from football.views import _auto_match_rating_from_stats

        muchas = {"total_actions": 40, "successes": 20, "pass_attempts": 14, "passes_completed": 9,
                  "unforced_turnovers": 4, "duels_total": 14, "duels_won": 8}
        pocas = {"total_actions": 9, "successes": 3, "duels_total": 7, "duels_won": 3,
                 "aerial_duels_total": 7, "aerial_duels_won": 3}
        self.assertGreaterEqual(
            _auto_match_rating_from_stats(muchas, "Mediocentro"),
            _auto_match_rating_from_stats(pocas, "Mediapunta"),
        )

    def test_un_cero_a_cero_no_reparte_notas_de_victoria(self):
        from football.views import _auto_match_rating_from_stats

        actuacion = {"total_actions": 18, "successes": 13, "pass_attempts": 8, "passes_completed": 7}
        empate = _auto_match_rating_from_stats({**actuacion, "team_goals_for": 0, "team_goals_against": 0}, "MC")
        victoria = _auto_match_rating_from_stats({**actuacion, "team_goals_for": 2, "team_goals_against": 0}, "MC")
        derrota = _auto_match_rating_from_stats({**actuacion, "team_goals_for": 0, "team_goals_against": 2}, "MC")
        self.assertLess(empate, victoria)
        self.assertLess(derrota, empate)

    def test_un_delantero_que_dispara_y_no_marca_no_sube_por_disparar(self):
        from football.views import _auto_match_rating_from_stats

        base = {"total_actions": 16, "successes": 12, "team_goals_for": 0, "team_goals_against": 0}
        sin_tirar = _auto_match_rating_from_stats(base, "DC")
        tirando = _auto_match_rating_from_stats({**base, "shot_attempts": 2, "shots_on_target": 1}, "DC")
        # "No puede mejorar": con el tope de delantero sin producción los dos pueden acabar
        # en el mismo sitio, lo que no puede pasar es que disparar sin meter SUBA la nota.
        self.assertLessEqual(tirando, sin_tirar, "tirar sin marcar no puede mejorar la nota de un delantero")
        # Y si marca, sí sube.
        marcando = _auto_match_rating_from_stats(
            {**base, "shot_attempts": 2, "shots_on_target": 2, "goals": 1,
             "team_goals_for": 1, "team_goals_against": 0}, "DC")
        self.assertGreater(marcando, sin_tirar)

    def test_encajar_muchos_goles_no_deja_notas_altas_en_defensa(self):
        """Si encajamos, la defensa responde: es su puesto, aunque individualmente cumpliera."""
        from football.views import _auto_match_rating_from_stats

        buena_actuacion = {"total_actions": 22, "successes": 18, "recoveries": 5,
                           "explicit_duels_total": 8, "explicit_duels_won": 7}
        sin_encajar = _auto_match_rating_from_stats(
            {**buena_actuacion, "team_goals_for": 1, "team_goals_against": 0}, "DFC")
        encajando_dos = _auto_match_rating_from_stats(
            {**buena_actuacion, "team_goals_for": 1, "team_goals_against": 2}, "DFC")
        goleada = _auto_match_rating_from_stats(
            {**buena_actuacion, "team_goals_for": 1, "team_goals_against": 4}, "DFC")
        self.assertGreater(sin_encajar, encajando_dos)
        self.assertLessEqual(encajando_dos, 6.8)
        self.assertLessEqual(goleada, 6.3)
        self.assertLess(goleada, encajando_dos)

    def test_un_delantero_sin_goles_del_equipo_no_pasa_de_ahi(self):
        from football.views import _auto_match_rating_from_stats

        peleado = {"total_actions": 20, "successes": 17, "explicit_duels_total": 9,
                   "explicit_duels_won": 8, "team_goals_for": 0, "team_goals_against": 0,
                   "team_shots": 5, "team_shots_on_target": 3}
        sin_tirar = _auto_match_rating_from_stats(peleado, "DC")
        self.assertLessEqual(sin_tirar, 6.2, "un delantero sin goles del equipo y sin tirar no sube")
        marcando = _auto_match_rating_from_stats(
            {**peleado, "goals": 1, "team_goals_for": 1, "shot_attempts": 2, "shots_on_target": 2}, "DC")
        self.assertGreater(marcando, sin_tirar)

    def test_un_partido_esteril_no_reparte_notables(self):
        """0-0 sin apenas llegar a portería: por mucho acierto, nadie sale de notable."""
        from football.views import _auto_match_rating_from_stats

        impecable = {"total_actions": 26, "successes": 24, "pass_attempts": 14, "passes_completed": 14,
                     "recoveries": 6, "explicit_duels_total": 8, "explicit_duels_won": 8,
                     "team_goals_for": 0, "team_goals_against": 0, "team_shots": 3, "team_shots_on_target": 1}
        medio = _auto_match_rating_from_stats(impecable, "MC")
        central = _auto_match_rating_from_stats(impecable, "DFC")
        self.assertLessEqual(medio, 6.8)
        self.assertLessEqual(central, 7.0)
        # Con el mismo rendimiento pero un partido resuelto, sí se puede subir.
        resuelto = _auto_match_rating_from_stats(
            {**impecable, "team_goals_for": 3, "team_shots": 12, "team_shots_on_target": 7}, "MC")
        self.assertGreater(resuelto, medio)
