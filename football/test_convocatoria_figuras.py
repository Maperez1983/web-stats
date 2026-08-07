"""La pizarra de la convocatoria -en pantalla y en PDF- no puede dejar a nadie sin figura.

Tres defectos medidos el 2026-08-07 sobre un cadete de 16 convocados:

  - el PORTERO salia con el PNG rosa generico de libreria, pese a que la libreria tiene figuras
    de portero: la figura solo se pedia cuando el avatar de estado era `kit_home.png`;
  - el ADULTO sin avatar generado se quedaba con cadena vacia (`resolve_player_avatar_url`
    devuelve "" a proposito para el) y la plantilla caia al PNG de adulto;
  - en el PDF, TODOS -porteros incluidos- salian con cuerpo de adulto, y ademas metidos en un
    rectangulo solido, porque las figuras se codificaban como JPEG y eso aplasta el alfa: blanco
    para los kits y NEGRO para los chandales de nino.

La puerta unica es `resolve_player_board_avatar_url` en pantalla y `_figura_estatica_de_pizarra`
en el PDF (misma regla, pero resuelta contra la libreria: WeasyPrint no puede con una imagen
distinta por jugador, que fue la causa de un 502 en su dia).
"""
import base64
import datetime
import io

from django.test import SimpleTestCase, TestCase

from football.models import Player, PlayerInjuryRecord, Team

HOY = datetime.date(2026, 8, 7)


def _nacido_con(anios):
    return HOY.replace(year=HOY.year - anios) - datetime.timedelta(days=40)


class FiguraDeCadaConvocadoTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Cadete Figuras", slug="cadete-figuras", category="Cadete")

    def _jugador(self, nombre, posicion, *, edad=None, ficha=True):
        return Player.objects.create(
            team=self.team,
            name=nombre,
            number=1,
            position=posicion,
            birth_date=_nacido_con(edad) if edad else None,
            has_federative_license=ficha,
            is_active=True,
        )

    def _chips(self, jugadores, lesionados=None):
        from football.views import _build_coach_pitch_board_players

        return {
            chip["id"]: chip
            for chip in _build_coach_pitch_board_players(
                self.team, jugadores, {}, set(lesionados or []), include_scouts=False
            )
        }

    def test_el_portero_disponible_recibe_figura_de_portero_y_no_la_rosa_generica(self):
        portero = self._jugador("Portero", "Portero", edad=15)
        chip = self._chips([portero])[portero.id]
        self.assertTrue(chip["avatar_url"], "el portero se queda sin figura y cae al PNG de libreria")
        self.assertIn("gk_", chip["avatar_url"], "el portero no lleva figura de portero")
        self.assertNotIn("gk_magenta", chip["avatar_static"], "vuelve el portero rosa en el PDF")
        self.assertIn("gk_", chip["avatar_static"])

    def test_un_adulto_sin_avatar_generado_no_se_queda_con_cadena_vacia(self):
        adulto = self._jugador("Adulto", "Defensa", edad=24)
        chip = self._chips([adulto])[adulto.id]
        self.assertTrue(chip["avatar_url"], "el adulto sin avatar vuelve a salir sin figura")

    def test_el_jugador_de_campo_lleva_la_figura_de_su_edad_tambien_en_el_pdf(self):
        nino = self._jugador("Alevin", "Delantero", edad=11)
        chip = self._chips([nino])[nino.id]
        self.assertIn("nino_", chip["avatar_static"], "en el PDF el alevin vuelve a salir de adulto")

    def test_el_chandal_del_a_prueba_se_respeta(self):
        """Es intencionado: asi se distingue de un vistazo a quien no esta fichado."""
        prueba = self._jugador("A prueba", "Delantero", edad=24, ficha=False)
        chip = self._chips([prueba])[prueba.id]
        self.assertEqual(chip["state"], "trial")
        self.assertEqual(chip["avatar_url"], "", "el chandal del 'a prueba' ha dejado de mandar")
        self.assertIn("chandal", chip["avatar_static"])

    def test_el_lesionado_conserva_las_muletas(self):
        lesionado = self._jugador("Lesionado", "Defensa", edad=15)
        PlayerInjuryRecord.objects.create(player=lesionado, injury_date=HOY, is_active=True, is_recovered=False)
        chip = self._chips([lesionado], lesionados=[lesionado.id])[lesionado.id]
        self.assertEqual(chip["state"], "injured")
        self.assertIn("injured_crutches", chip["avatar_static"])

    def test_ningun_convocado_se_queda_sin_figura_en_el_pdf(self):
        from football.views import _coach_pitch_board_pdf_assets

        jugadores = [
            self._jugador("Portero", "Portero", edad=15),
            self._jugador("Adulto", "Defensa", edad=24),
            self._jugador("Benjamin", "Delantero", edad=8),
            self._jugador("Sin fecha", "Centrocampista"),
            self._jugador("A prueba", "Delantero", edad=11, ficha=False),
        ]
        chips = list(self._chips(jugadores).values())
        _coach_pitch_board_pdf_assets(chips)
        for chip in chips:
            self.assertTrue(
                chip.get("avatar_pdf"),
                f"{chip['name']} sale en el PDF sin figura: dorsal y nombre flotando sobre el cesped",
            )

    def test_un_chip_sin_figura_alguna_sigue_teniendo_ultimo_recurso(self):
        from football.views import _coach_pitch_board_pdf_assets

        chips = [{"name": "Roto", "avatar": "", "avatar_static": ""}]
        _coach_pitch_board_pdf_assets(chips)
        self.assertTrue(chips[0]["avatar_pdf"], "sin ultimo recurso, la ficha se queda sin figura")


class EquipacionElegidaEnLaPizarraTests(TestCase):
    """El entrenador elige equipación en la pizarra y las figuras salen con ella."""

    def _equipo(self, categoria):
        return Team.objects.create(name=f"Equipo {categoria}", slug=f"equipo-{categoria.lower()}", category=categoria)

    def _chip(self, team, player, kit):
        from football.views import _build_coach_pitch_board_players

        chips = _build_coach_pitch_board_players(team, [player], {}, set(), include_scouts=False, kit=kit)
        return chips[0]

    def test_el_adulto_de_campo_cambia_de_camiseta(self):
        team = self._equipo("Senior")
        p = Player.objects.create(
            team=team, name="Adulto", number=5, position="Defensa",
            birth_date=_nacido_con(24), has_federative_license=True, is_active=True,
        )
        esperado = {
            "titular": "kit_home_hd.png",
            "visitante": "kit_away_hd.png",
            "turquesa": "kit_turquoise_hd.png",
            "blanca": "kit_white_hd.png",
        }
        for kit, png in esperado.items():
            with self.subTest(kit=kit):
                chip = self._chip(team, p, kit)
                self.assertTrue(chip["avatar_url"].endswith(png), chip["avatar_url"])
                self.assertTrue(chip["avatar_static"].endswith(png), chip["avatar_static"])

    def test_el_portero_cambia_de_camiseta_a_cualquier_edad(self):
        for categoria, edad in (("Senior", 24), ("Cadete", 15)):
            with self.subTest(categoria=categoria):
                team = self._equipo(categoria + "GK")
                p = Player.objects.create(
                    team=team, name="Portero", number=1, position="Portero",
                    birth_date=_nacido_con(edad), has_federative_license=True, is_active=True,
                )
                self.assertTrue(self._chip(team, p, "titular")["avatar_url"].endswith("gk_blue_hd.png"))
                self.assertTrue(self._chip(team, p, "visitante")["avatar_url"].endswith("gk_black_hd.png"))

    def test_al_nino_de_campo_TAMBIEN_le_cambia_la_camiseta(self):
        """Las figuras de niño ya tienen las cuatro equipaciones.

        Las fabrica `scripts/avatares/kits_ninos.py` recoloreando la titular con la misma receta
        que unificó el verde del club. Antes sólo existía la titular y elegir "visitante" en un
        cadete sólo se le notaba al portero.
        """
        team = self._equipo("Cadete")
        p = Player.objects.create(
            team=team, name="Cadete", number=5, position="Delantero",
            birth_date=_nacido_con(15), has_federative_license=True, is_active=True,
        )
        esperado = {"titular": "_hd.png", "visitante": "_away_hd.png",
                    "turquesa": "_turquoise_hd.png", "blanca": "_white_hd.png"}
        for kit, sufijo in esperado.items():
            with self.subTest(kit=kit):
                chip = self._chip(team, p, kit)
                self.assertIn("nino_", chip["avatar_url"], "ha dejado de salir la figura de su edad")
                self.assertTrue(chip["avatar_url"].endswith(sufijo), chip["avatar_url"])
                self.assertTrue(chip["avatar_static"].endswith(sufijo), chip["avatar_static"])

    def test_las_nueve_figuras_de_nino_tienen_sus_cuatro_equipaciones(self):
        from django.contrib.staticfiles import finders

        from football.views import _BOARD_LIB

        claves = ("bebe_a", "bebe_b", "peque_a", "peque_b", "peque_c",
                  "medio_a", "medio_b", "ado_a", "ado_b")
        faltan = [
            f"nino_{clave}{sufijo}_hd.png"
            for clave in claves
            for sufijo in ("", "_away", "_turquoise", "_white")
            if not finders.find(_BOARD_LIB + f"nino_{clave}{sufijo}_hd.png")
        ]
        self.assertEqual(faltan, [], "faltan figuras de niño por equipación")

    def test_una_equipacion_desconocida_no_rompe_la_pizarra(self):
        from football.views import board_kit_valido

        self.assertEqual(board_kit_valido("lo-que-sea"), "titular")
        self.assertEqual(board_kit_valido(None), "titular")
        self.assertEqual(board_kit_valido("VISITANTE"), "visitante")


class ElStaffSeLeeEnElOrdenEnQueMandaTests(TestCase):
    """El cargo es texto libre, así que se reconoce por palabras y se muestra normalizado."""

    def test_orden_y_formato(self):
        from football.views import _staff_rango_y_etiqueta

        escritos = [
            "ANALISTA", "2o entrenador", "entrenador", "PREPARADOR FISICO",
            "Entrenador de porteros", "Administrador",
        ]
        ordenado = sorted(escritos, key=lambda c: _staff_rango_y_etiqueta(c)[0])
        etiquetas = [_staff_rango_y_etiqueta(c)[1] for c in ordenado]
        self.assertEqual(
            etiquetas,
            [
                "Entrenador",
                "Entrenador asistente",
                "Preparador físico",
                "Preparador de porteros",
                "Analista",
                "Administrador",
            ],
        )

    def test_el_segundo_entrenador_no_se_confunde_con_el_entrenador(self):
        from football.views import _staff_rango_y_etiqueta

        for escrito in ("2º entrenador", "Segundo entrenador", "entrenador ayudante"):
            with self.subTest(escrito=escrito):
                self.assertEqual(_staff_rango_y_etiqueta(escrito)[1], "Entrenador asistente")

    def test_un_cargo_raro_va_antes_del_administrador_y_conserva_su_texto(self):
        from football.views import _staff_rango_y_etiqueta

        rango_raro, etiqueta = _staff_rango_y_etiqueta("UTILLERO")
        rango_admin, _ = _staff_rango_y_etiqueta("Administrador")
        self.assertLess(rango_raro, rango_admin)
        self.assertEqual(etiqueta, "Utillero")


class LaHojaDeConvocatoriaDiceLoQueHaceFaltaTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Cadete Hoja", slug="cadete-hoja", category="Cadete")

    def _jugador(self, nombre, dorsal, pos, **extra):
        return Player.objects.create(
            team=self.team, name=nombre, number=dorsal, position=pos,
            has_federative_license=True, is_active=True, **extra
        )

    def test_las_dos_columnas_del_listado_quedan_equilibradas(self):
        from football.views import _convocation_roster_columns

        lineas = [
            {"key": "gk", "total": 3, "players": []},
            {"key": "def", "total": 5, "players": []},
            {"key": "mid", "total": 4, "players": []},
            {"key": "att", "total": 4, "players": []},
        ]
        izquierda, derecha = _convocation_roster_columns(lineas)
        self.assertEqual(sum(l["total"] for l in izquierda), 8)
        self.assertEqual(sum(l["total"] for l in derecha), 8)
        # Y sin partir ninguna línea entre columnas.
        self.assertEqual(
            [l["key"] for l in izquierda] + [l["key"] for l in derecha],
            ["gk", "def", "mid", "att"],
        )

    def test_los_no_convocados_salen_con_su_motivo(self):
        """Sin motivo escrito, se deduce: parte de lesión, sanción, o decisión del entrenador."""
        from football.views import _convocation_absences

        va = self._jugador("Convocado", 1, "Defensa")
        lesionado = self._jugador("Lesionado", 2, "Defensa")
        fuera = self._jugador("Fuera", 3, "Delantero")
        PlayerInjuryRecord.objects.create(player=lesionado, injury_date=HOY, is_active=True, is_recovered=False)

        filas = {f["name"]: f for f in _convocation_absences(self.team, [va.id])}
        self.assertNotIn("Convocado", filas, "un convocado no puede salir como ausente")
        self.assertEqual(filas["Lesionado"]["motivo"], "Lesión")
        self.assertEqual(filas["Fuera"]["motivo"], "Decisión del entrenador")
        self.assertFalse(filas["Fuera"]["elegido"], "nadie eligió ese motivo: es deducido")

    def test_el_motivo_ELEGIDO_manda_sobre_el_deducido(self):
        from football.views import _convocation_absences

        va = self._jugador("Convocado", 1, "Defensa")
        lesionado = self._jugador("Lesionado", 2, "Defensa")
        fuera = self._jugador("Fuera", 3, "Delantero")
        PlayerInjuryRecord.objects.create(player=lesionado, injury_date=HOY, is_active=True, is_recovered=False)

        filas = {
            f["name"]: f
            for f in _convocation_absences(
                self.team, [va.id],
                elegidos={str(fuera.id): "personales", str(lesionado.id): "entrenador"},
            )
        }
        self.assertEqual(filas["Fuera"]["motivo"], "Motivos personales")
        self.assertTrue(filas["Fuera"]["elegido"])
        # Tiene parte abierto, pero el entrenador ha dicho otra cosa y manda lo que él dice.
        self.assertEqual(filas["Lesionado"]["motivo"], "Decisión del entrenador")

    def test_los_cuatro_motivos_son_los_pedidos_y_no_entra_texto_libre(self):
        from football.views import motivo_ausencia_valido, motivos_ausencia_opciones

        self.assertEqual(
            [etiqueta for _, etiqueta in motivos_ausencia_opciones()],
            ["Lesión", "Motivos personales", "Decisión del entrenador", "Sanción"],
        )
        self.assertEqual(motivo_ausencia_valido("personales"), "personales")
        self.assertEqual(motivo_ausencia_valido("se fue de boda"), "")
        self.assertEqual(motivo_ausencia_valido(None), "")

    def test_el_desplegable_esta_en_la_pantalla_de_convocatoria(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parent / "templates" / "football" / "convocation.html"
        ).read_text(encoding="utf-8")
        self.assertIn("data-absence-reason", html)
        self.assertIn("absence_reasons: absenceReasons()", html, "el motivo no se manda al guardar")
        self.assertIn(
            "sel.addEventListener('click', (ev) => ev.stopPropagation());",
            html,
            "sin parar el clic, elegir un motivo convoca al jugador",
        )

    def test_la_citacion_y_la_equipacion_salen_en_la_tira_de_datos(self):
        from football.models import ConvocationRecord
        from football.views import _convocation_facts

        record = ConvocationRecord.objects.create(
            team=self.team, round="J1", match_date=HOY,
            call_time=datetime.time(9, 15), kit_choice="visitante", is_current=True,
        )
        etiquetas = {f["label"]: f for f in _convocation_facts(record, None, self.team, 16)}
        self.assertEqual(etiquetas["Citación"]["value"], "09:15")
        self.assertEqual(etiquetas["Equipación"]["value"], "Visitante")
        self.assertEqual(etiquetas["Convocados"]["value"], 16)
        self.assertNotIn("Edad media", etiquetas, "la edad media es dato de plantilla, no de convocatoria")
        self.assertNotIn("Defensas", etiquetas, "el reparto por puesto ya está en el listado")

    def test_sin_citacion_lo_dice_en_vez_de_callarse(self):
        from football.models import ConvocationRecord
        from football.views import _convocation_facts

        record = ConvocationRecord.objects.create(team=self.team, round="J1", match_date=HOY, is_current=True)
        etiquetas = {f["label"]: f for f in _convocation_facts(record, None, self.team, 5)}
        self.assertEqual(etiquetas["Citación"]["value"], "Por confirmar")


class LaFiguraDelPdfConservaElRecorteTests(SimpleTestCase):
    """El JPEG aplasta el alfa: la figura acaba dentro de un rectangulo sobre el cesped."""

    FIGURAS = (
        "kit_home_hd.png",
        "gk_blue_hd.png",
        "nino_peque_a_hd.png",
        "chandal_medio.png",
        "injured_crutches.png",
    )

    def test_las_figuras_llegan_al_pdf_con_transparencia(self):
        from PIL import Image
        from django.contrib.staticfiles import finders

        from football.views import _BOARD_LIB, _cutout_image_as_small_data_uri

        for nombre in self.FIGURAS:
            with self.subTest(figura=nombre):
                ruta = finders.find(_BOARD_LIB + nombre)
                self.assertTrue(ruta, f"falta la figura {nombre} en la libreria")
                uri = _cutout_image_as_small_data_uri(ruta)
                self.assertTrue(uri.startswith("data:image/png;base64,"), "ha vuelto el JPEG opaco")
                with Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))) as im:
                    alfa = im.convert("RGBA").split()[3]
                self.assertEqual(alfa.getpixel((0, 0)), 0, f"{nombre} llega al PDF con la esquina opaca")

    def test_la_figura_no_engorda_el_documento(self):
        """El limite es la memoria de WeasyPrint, no el disco: si una figura se dispara, el
        documento con veinte fichas vuelve a ser el que tumbaba el render."""
        from django.contrib.staticfiles import finders

        from football.views import _BOARD_LIB, _cutout_image_as_small_data_uri

        for nombre in self.FIGURAS:
            with self.subTest(figura=nombre):
                uri = _cutout_image_as_small_data_uri(finders.find(_BOARD_LIB + nombre))
                self.assertLess(len(uri) / 1024, 12, f"{nombre} pesa demasiado para el PDF")
