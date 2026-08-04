import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import (
    Player,
    TacticalPlan,
    TacticalPlay,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)
from football.tactical_play_views import _dibujo, _normalizar_pasos


class JugadasTests(TestCase):
    """Táctica · Jugadas: el dibujo libre, por pasos, sobre el once real."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="Benagalbón", slug="bena", is_primary=True)
        self.otro = Team.objects.create(name="Otro", slug="otro")
        self.ws = Workspace.objects.create(name="Club", slug="club", kind=Workspace.KIND_CLUB)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.user, role="owner")
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.team, is_default=True)
        self.p1 = Player.objects.create(team=self.team, name="Uno", number=1, is_active=True)
        self.p2 = Player.objects.create(team=self.team, name="Dos", number=2, is_active=True)
        self.ajeno = Player.objects.create(team=self.otro, name="Ajeno", number=9, is_active=True)
        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = self.ws.id
        s["active_team_by_workspace"] = {str(self.ws.id): self.team.id}
        s.save()

    def _paso(self, **extra):
        paso = {
            "name": "Salida",
            "starters": [{"id": self.p1.id, "x_pct": 10, "y_pct": 50}],
            "rival": [],
            "shapes": [{"tool": "pase", "points": [{"x": 10, "y": 50}, {"x": 40, "y": 30}]}],
        }
        paso.update(extra)
        return paso

    def _guardar(self, **extra):
        payload = {"name": "Salida 3-2", "kind": "ataque", "steps": [self._paso()]}
        payload.update(extra)
        return self.client.post(reverse("tactics-play-save"), data=json.dumps(payload),
                                content_type="application/json", secure=True)

    # --- la pantalla ---

    def test_la_pantalla_usa_el_cesped_de_siempre(self):
        r = self.client.get(reverse("tactics-plays"), secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("coach_home_pitch_surface", html, "el campo tiene que ser el mismo de toda la app")
        self.assertIn("tactical_play.js", html)

    def test_la_pantalla_ofrece_los_planteamientos_como_punto_de_partida(self):
        TacticalPlan.objects.create(
            team=self.team, name="1-4-3-3 base",
            lineup_data={"starters": [{"id": self.p1.id, "x_pct": 7, "y_pct": 50}]},
        )
        r = self.client.get(reverse("tactics-plays"), secure=True)
        self.assertIn("1-4-3-3 base", r.content.decode())

    # --- guardar ---

    def test_guardar_y_recuperar_una_jugada(self):
        r = self._guardar()
        self.assertEqual(r.status_code, 200)
        jugada = r.json()["play"]
        self.assertEqual(len(jugada["steps"]), 1)
        self.assertEqual(len(jugada["steps"][0]["shapes"]), 1)
        self.assertEqual(jugada["steps"][0]["shapes"][0]["tool"], "pase")

    def test_la_jugada_necesita_nombre(self):
        r = self._guardar(name="  ")
        self.assertEqual(r.status_code, 400)

    def test_una_jugada_vacia_no_se_guarda(self):
        r = self._guardar(steps=[])
        self.assertEqual(r.status_code, 400)
        self.assertFalse(TacticalPlay.objects.exists())

    def test_el_mismo_nombre_no_duplica(self):
        self._guardar()
        self._guardar()
        self.assertEqual(TacticalPlay.objects.filter(team=self.team).count(), 1)

    def test_no_se_cuela_un_jugador_de_otro_equipo(self):
        r = self._guardar(steps=[self._paso(starters=[{"id": self.ajeno.id, "x_pct": 10, "y_pct": 10}])])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["play"]["steps"][0]["starters"], [],
                         "un jugador de otro equipo no puede aparecer en nuestra jugada")

    def test_sin_fichas_ni_trazos_la_jugada_esta_vacia(self):
        r = self._guardar(steps=[{"name": "Nada", "starters": [], "rival": [], "shapes": []}])
        self.assertEqual(r.status_code, 400)

    def test_borrar(self):
        self._guardar()
        jugada = TacticalPlay.objects.get()
        r = self.client.post(reverse("tactics-play-delete"), data=json.dumps({"id": jugada.id}),
                             content_type="application/json", secure=True)
        self.assertTrue(r.json()["ok"])
        self.assertFalse(TacticalPlay.objects.exists())

    def test_no_se_borra_la_jugada_de_otro_equipo(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[self._paso()])
        r = self.client.post(reverse("tactics-play-delete"), data=json.dumps({"id": ajena.id}),
                             content_type="application/json", secure=True)
        self.assertFalse(r.json()["ok"])
        self.assertTrue(TacticalPlay.objects.filter(id=ajena.id).exists())

    # --- saneado de los trazos ---

    def test_se_descarta_la_herramienta_inventada(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "laser", "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}]}], {})
        self.assertEqual(pasos[0]["shapes"], [])

    def test_un_trazo_de_un_solo_punto_no_es_un_trazo(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "pase", "points": [{"x": 1, "y": 1}]}]}], {})
        self.assertEqual(pasos[0]["shapes"], [])

    def test_una_marca_si_es_de_un_punto(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "cono", "points": [{"x": 1, "y": 1}, {"x": 9, "y": 9}]}]}], {})
        self.assertEqual(len(pasos[0]["shapes"][0]["points"]), 1, "una marca es un punto, no un arrastre")

    def test_las_coordenadas_se_quedan_dentro_del_campo(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "pase", "points": [{"x": -40, "y": 800}, {"x": 20, "y": 20}]}]}], {})
        punto = pasos[0]["shapes"][0]["points"][0]
        self.assertEqual((punto["x"], punto["y"]), (0.0, 100.0))

    def test_no_se_guardan_pasos_ni_trazos_sin_limite(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "pase", "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}] * 200}] * 40, {})
        self.assertLessEqual(len(pasos), 12)
        self.assertLessEqual(len(pasos[0]["shapes"]), 60)

    def test_el_texto_se_recorta(self):
        pasos = _normalizar_pasos([{"shapes": [{"tool": "texto", "points": [{"x": 5, "y": 5}], "text": "x" * 200}]}], {})
        self.assertEqual(len(pasos[0]["shapes"][0]["text"]), 60)

    # --- geometría ---

    def test_el_pase_y_el_desmarque_no_se_pintan_igual(self):
        pase = _dibujo([{"tool": "pase", "points": [{"x": 0, "y": 0}, {"x": 50, "y": 50}]}])[0]
        desmarque = _dibujo([{"tool": "desmarque", "points": [{"x": 0, "y": 0}, {"x": 50, "y": 50}]}])[0]
        self.assertEqual(pase["dash"], "", "el pase es línea continua")
        self.assertTrue(desmarque["dash"], "el desmarque es discontinuo")
        self.assertNotEqual(pase["color"], desmarque["color"], "el balón y el jugador no son lo mismo")

    def test_la_conduccion_va_ondulada(self):
        recta = _dibujo([{"tool": "pase", "points": [{"x": 0, "y": 50}, {"x": 90, "y": 50}]}])[0]
        onda = _dibujo([{"tool": "conduccion", "points": [{"x": 0, "y": 50}, {"x": 90, "y": 50}]}])[0]
        self.assertGreater(onda["d"].count("L"), recta["d"].count("L"),
                           "sin ondular, conducción y pase serían la misma raya")

    def test_las_coordenadas_del_dibujo_son_las_del_cesped(self):
        forma = _dibujo([{"tool": "pase", "points": [{"x": 0, "y": 0}, {"x": 100, "y": 100}]}])[0]
        self.assertIn("M0.0 0.0", forma["d"])
        self.assertIn("L1664.0 945.0", forma["d"], "el viewBox del campo es 1664x945")

    def test_la_zona_es_un_rectangulo_aunque_se_dibuje_al_reves(self):
        forma = _dibujo([{"tool": "zona", "points": [{"x": 60, "y": 60}, {"x": 20, "y": 20}]}])[0]
        self.assertEqual(forma["tipo"], "rect")
        self.assertGreater(float(forma["w"]), 0)
        self.assertGreater(float(forma["h"]), 0)

    def test_los_numeros_del_svg_no_llevan_coma_decimal(self):
        # Con locale es-ES un float en plantilla sale "1.664,0" y el SVG se rompe entero.
        forma = _dibujo([{"tool": "zona", "points": [{"x": 10.5, "y": 10.5}, {"x": 20, "y": 20}]}])[0]
        self.assertNotIn(",", forma["x"] + forma["y"] + forma["w"] + forma["h"])

    # --- el tablero ---

    def test_el_tablero_pinta_los_trazos(self):
        self._guardar()
        jugada = TacticalPlay.objects.get()
        r = self.client.get(reverse("tactics-play-board", args=[jugada.id]), secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("marker-end", html, "una flecha sin punta no dice hacia dónde va")
        self.assertIn("coach_home_pitch_surface", html)

    def test_el_tablero_puede_pedir_un_solo_paso(self):
        self._guardar(steps=[self._paso(name="Uno"), self._paso(name="Dos")])
        jugada = TacticalPlay.objects.get()
        r = self.client.get(reverse("tactics-play-board", args=[jugada.id]) + "?paso=2", secure=True)
        html = r.content.decode()
        self.assertIn("Dos", html)
        self.assertNotIn("· Uno", html)
        self.assertIn("2 · Dos", html, "el paso suelto tiene que seguir siendo el 2, no volver a ser el 1")

    def test_el_tablero_de_otro_equipo_no_se_ve(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[self._paso()])
        r = self.client.get(reverse("tactics-play-board", args=[ajena.id]), secure=True)
        self.assertEqual(r.status_code, 302)

    # --- el area ---

    def test_jugadas_esta_en_el_menu_de_tactica(self):
        r = self.client.get(reverse("tactics-plan"), secure=True)
        self.assertIn(reverse("tactics-plays"), r.content.decode(),
                      "si no está en el menú, no existe")


class JugadaEnSesionYPortalTests(TestCase):
    """La jugada no se queda en Táctica: entra en la tarea de entreno y llega al jugador."""

    def setUp(self):
        from datetime import date

        from football.models import SessionTask, TrainingMicrocycle, TrainingSession

        self.user = get_user_model().objects.create_superuser("s2", "s2@example.com", "x")
        self.team = Team.objects.create(name="Benagalbón", slug="bena2", is_primary=True)
        self.otro = Team.objects.create(name="Otro", slug="otro2")
        self.ws = Workspace.objects.create(name="Club", slug="club2", kind=Workspace.KIND_CLUB)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.user, role="owner")
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.team, is_default=True)
        self.p1 = Player.objects.create(team=self.team, name="Uno", number=1, is_active=True)

        self.jugador_user = get_user_model().objects.create_user("chaval", "c@example.com", "x")
        self.p2 = Player.objects.create(
            team=self.team, name="Dos", number=2, is_active=True, user=self.jugador_user
        )

        self.play = TacticalPlay.objects.create(
            team=self.team, name="Salida 3-2",
            steps_data=[{"name": "Salida", "starters": [{"id": self.p1.id, "x_pct": 10, "y_pct": 50}],
                         "rival": [], "shapes": []}],
        )
        micro = TrainingMicrocycle.objects.create(
            team=self.team, week_start=date(2026, 8, 3), week_end=date(2026, 8, 9)
        )
        sesion = TrainingSession.objects.create(microcycle=micro, session_date=date(2026, 8, 4))
        self.tarea = SessionTask.objects.create(session=sesion, title="Rondo", duration_minutes=15)

        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = self.ws.id
        s["active_team_by_workspace"] = {str(self.ws.id): self.team.id}
        s.save()

    # --- la sesión ---

    def test_enganchar_una_jugada_a_una_tarea(self):
        r = self.client.post(reverse("tactics-play-attach"),
                             {"task_id": self.tarea.id, "play_id": self.play.id}, secure=True)
        self.assertEqual(r.status_code, 200)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.tactical_play_id, self.play.id)

    def test_desenganchar(self):
        self.tarea.tactical_play = self.play
        self.tarea.save(update_fields=["tactical_play"])
        self.client.post(reverse("tactics-play-attach"),
                         {"task_id": self.tarea.id, "play_id": 0}, secure=True)
        self.tarea.refresh_from_db()
        self.assertIsNone(self.tarea.tactical_play_id)

    def test_no_se_engancha_una_jugada_de_otro_equipo(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[])
        r = self.client.post(reverse("tactics-play-attach"),
                             {"task_id": self.tarea.id, "play_id": ajena.id}, secure=True)
        self.assertEqual(r.status_code, 404)
        self.tarea.refresh_from_db()
        self.assertIsNone(self.tarea.tactical_play_id)

    def test_borrar_la_jugada_no_borra_la_tarea(self):
        self.tarea.tactical_play = self.play
        self.tarea.save(update_fields=["tactical_play"])
        self.play.delete()
        self.tarea.refresh_from_db()
        self.assertIsNone(self.tarea.tactical_play_id, "la tarea sobrevive, sólo pierde el enlace")

    # --- el portal ---

    def test_publicar_avisa_a_los_jugadores_con_cuenta(self):
        from football.models import PlayerNotification

        r = self.client.post(reverse("tactics-play-publish"),
                             data=json.dumps({"id": self.play.id, "publish": True}),
                             content_type="application/json", secure=True)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r.json()["notified"], 1, "sólo se avisa a quien tiene cuenta")
        self.play.refresh_from_db()
        self.assertTrue(self.play.published_to_players)
        self.assertIsNotNone(self.play.published_at)
        aviso = PlayerNotification.objects.get(target_user=self.jugador_user)
        self.assertIn("Salida 3-2", aviso.title)
        self.assertEqual(aviso.link_url, reverse("tactics-play-player", args=[self.play.id]))

    def test_retirar_la_publicacion(self):
        self.client.post(reverse("tactics-play-publish"),
                         data=json.dumps({"id": self.play.id, "publish": True}),
                         content_type="application/json", secure=True)
        self.client.post(reverse("tactics-play-publish"),
                         data=json.dumps({"id": self.play.id, "publish": False}),
                         content_type="application/json", secure=True)
        self.play.refresh_from_db()
        self.assertFalse(self.play.published_to_players)

    def test_el_jugador_no_ve_una_jugada_sin_publicar(self):
        c = Client()
        c.force_login(self.jugador_user)
        r = c.get(reverse("tactics-play-player", args=[self.play.id]), secure=True)
        self.assertEqual(r.status_code, 302, "sin publicar no es suya")

    def test_el_jugador_ve_la_jugada_publicada_de_su_equipo(self):
        self.play.published_to_players = True
        self.play.save(update_fields=["published_to_players"])
        c = Client()
        c.force_login(self.jugador_user)
        r = c.get(reverse("tactics-play-player", args=[self.play.id]), secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Salida 3-2", r.content.decode())

    def test_el_jugador_no_ve_la_jugada_publicada_de_otro_equipo(self):
        ajena = TacticalPlay.objects.create(
            team=self.otro, name="Ajena", published_to_players=True, steps_data=[],
        )
        c = Client()
        c.force_login(self.jugador_user)
        r = c.get(reverse("tactics-play-player", args=[ajena.id]), secure=True)
        self.assertEqual(r.status_code, 302, "publicada sí, pero no es de su equipo")

    def test_la_politica_del_portal_trae_la_seccion_de_jugadas(self):
        from football.player_portal_policy import PUBLISHED_ONLY, default_sections

        self.assertEqual(default_sections()["plays"], PUBLISHED_ONLY,
                         "por defecto sólo lo publicado, como el resto de lo sensible")


class JugadaEnPartidoYExportacionTests(TestCase):
    """La jugada en la charla del partido, el GIF y el encaje estimado."""

    def setUp(self):
        from datetime import date

        from football.models import Competition, Match, Season

        self.user = get_user_model().objects.create_superuser("s3", "s3@example.com", "x")
        self.team = Team.objects.create(name="Benagalbón", slug="bena3", is_primary=True)
        self.otro = Team.objects.create(name="Otro", slug="otro3")
        self.ws = Workspace.objects.create(name="Club", slug="club3", kind=Workspace.KIND_CLUB)
        WorkspaceMembership.objects.create(workspace=self.ws, user=self.user, role="owner")
        WorkspaceTeam.objects.create(workspace=self.ws, team=self.team, is_default=True)
        self.p1 = Player.objects.create(team=self.team, name="Uno", number=1, position="LI", is_active=True)

        comp = Competition.objects.create(name="Liga", slug="liga3")
        temporada = Season.objects.create(competition=comp, name="2026/2027")
        self.match = Match.objects.create(
            home_team=self.team, away_team=self.otro, date=date(2026, 8, 9), season=temporada, is_closed=False,
        )
        paso = {
            "name": "Salida", "rival": [], "shapes": [
                {"tool": "pase", "points": [{"x": 10, "y": 50}, {"x": 40, "y": 30}]},
                {"tool": "desmarque", "points": [{"x": 20, "y": 80}, {"x": 50, "y": 70}]},
            ],
            "starters": [{"id": self.p1.id, "name": "Uno", "number": "1", "x_pct": 10, "y_pct": 50}],
        }
        paso2 = {**paso, "name": "Progresión",
                 "starters": [{**paso["starters"][0], "x_pct": 40, "y_pct": 40}]}
        self.play = TacticalPlay.objects.create(team=self.team, name="Salida 3-2", steps_data=[paso, paso2])

        self.client = Client()
        self.client.force_login(self.user)
        s = self.client.session
        s["active_workspace_id"] = self.ws.id
        s["active_team_by_workspace"] = {str(self.ws.id): self.team.id}
        s.save()

    # --- la charla del partido ---

    def test_colgar_una_jugada_de_un_partido(self):
        r = self.client.post(reverse("tactics-play-match"),
                             data=json.dumps({"play_id": self.play.id, "match_id": self.match.id}),
                             content_type="application/json", secure=True)
        self.assertTrue(r.json()["ok"])
        self.assertEqual([p.name for p in self.match.plays.all()], ["Salida 3-2"])

    def test_quitarla_de_la_charla(self):
        self.match.plays.add(self.play)
        self.client.post(reverse("tactics-play-match"),
                         data=json.dumps({"play_id": self.play.id, "match_id": self.match.id, "remove": True}),
                         content_type="application/json", secure=True)
        self.assertEqual(self.match.plays.count(), 0)

    def test_no_se_cuelga_una_jugada_de_otro_equipo(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[])
        r = self.client.post(reverse("tactics-play-match"),
                             data=json.dumps({"play_id": ajena.id, "match_id": self.match.id}),
                             content_type="application/json", secure=True)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.match.plays.count(), 0)

    # --- el GIF ---

    def test_el_gif_sale_y_es_un_gif_animado(self):
        from PIL import Image

        r = self.client.get(reverse("tactics-play-gif", args=[self.play.id]), secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/gif")
        imagen = Image.open(__import__("io").BytesIO(r.content))
        self.assertGreater(imagen.n_frames, 1, "un GIF de un solo fotograma no es una animación")

    def test_el_gif_no_pesa_como_para_no_poder_mandarlo(self):
        r = self.client.get(reverse("tactics-play-gif", args=[self.play.id]), secure=True)
        self.assertLess(len(r.content), 2_000_000, "por encima de 2 MB no se manda por WhatsApp")

    def test_una_jugada_de_un_solo_paso_no_se_anima(self):
        quieta = TacticalPlay.objects.create(
            team=self.team, name="Quieta",
            steps_data=[{"name": "Uno", "starters": [], "rival": [], "shapes": []}],
        )
        r = self.client.get(reverse("tactics-play-gif", args=[quieta.id]), secure=True)
        self.assertEqual(r.status_code, 400)

    def test_el_gif_de_otro_equipo_no_se_descarga(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[])
        r = self.client.get(reverse("tactics-play-gif", args=[ajena.id]), secure=True)
        self.assertEqual(r.status_code, 404)

    # --- el filtro por tipo (balón parado es esta pantalla, no otra) ---

    def test_balon_parado_abre_jugadas_filtrado(self):
        r = self.client.get(reverse("tactics-plays") + "?tipo=abp", secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("tj-filter", r.content.decode(), "sin filtro no se puede separar el ABP")

    def test_el_menu_de_tactica_ya_no_lleva_a_la_pizarra_vieja(self):
        html = self.client.get(reverse("tactics-plays"), secure=True).content.decode()
        menu = html.split('class="zone-menu-list"')[1].split('</details>')[0]
        # Ojo: "/coach/tactica/" es prefijo de todas las demás, así que se busca el enlace ENTERO.
        self.assertNotIn(f'href="{reverse("coach-tactics")}"', menu,
                         "el área tiene UN editor; a la pizarra vieja se llega desde el panel de dentro")
        self.assertNotIn(f'href="{reverse("coach-tactics")}?', menu)
        self.assertIn(reverse("tactics-plays"), menu)

    # --- roles: encaje estimado cuando no hay valoraciones ---

    def test_sin_valoraciones_el_encaje_se_estima_por_el_puesto(self):
        from football.views import FM_ROLE_CATALOG, _fm_baseline_scores

        def encaje(pos, grupo):
            base = _fm_baseline_scores(pos)
            _clave, _etq, params = FM_ROLE_CATALOG[grupo][0]
            vals = [base[p] for p in params if p in base]
            return sum(vals) / len(vals) * 10

        self.assertGreater(encaje("LI", "lateral"), encaje("LI", "delantero"),
                           "un lateral tiene que encajar mejor de lateral que de delantero")
        self.assertGreater(encaje("POR", "gk"), encaje("POR", "central"))

    def test_la_pantalla_de_roles_avisa_de_que_es_una_estimacion(self):
        r = self.client.get(reverse("tactics-roles"), secure=True)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("estimados por el puesto", html, "un % sin avisar se lee como un dato medido")
        self.assertIn('"estimado": true', html)
