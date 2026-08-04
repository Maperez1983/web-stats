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

    def test_el_tablero_de_otro_equipo_no_se_ve(self):
        ajena = TacticalPlay.objects.create(team=self.otro, name="Suya", steps_data=[self._paso()])
        r = self.client.get(reverse("tactics-play-board", args=[ajena.id]), secure=True)
        self.assertEqual(r.status_code, 302)

    # --- el area ---

    def test_jugadas_esta_en_el_menu_de_tactica(self):
        r = self.client.get(reverse("tactics-plan"), secure=True)
        self.assertIn(reverse("tactics-plays"), r.content.decode(),
                      "si no está en el menú, no existe")
