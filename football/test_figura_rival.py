"""La figura del rival en la pizarra: que aparezca, y que no vaya vestida de los nuestros.

Dos fallos distintos la hacian imposible y ninguno daba error:

1. El rail escribia el estilo a mano (`style: 'disk'`). Al rival solo se le puede
   colocar desde el rail -no esta en el banco de la plantilla-, asi que elegir
   "Figura" no le afectaba NUNCA: siempre salia chapa.
2. El ajuste global de figura (`window.__edcAvatar`) lleva NUESTRA equipacion y se
   aplicaba a todos. Con el 1 arreglado, el rival aparecia con nuestra camiseta
   verde, indistinguible de un jugador propio.

Se comprueba sobre el fuente, como el candado de la chapa: es codigo de navegador
sin bundler y esto es lo unico que corta la regresion en `manage.py test`.
"""
from pathlib import Path

from django.test import SimpleTestCase

PAD = Path(__file__).resolve().parent / "static" / "football" / "js" / "sessions_tactical_pad.js"


class FiguraDelRivalTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = PAD.read_text(encoding="utf-8")

    def test_el_rail_no_vuelve_a_fijar_el_estilo_a_mano(self):
        for kind in ("player_local", "player_rival", "goalkeeper_local", "goalkeeper_rival"):
            aguja = "playerTokenFactory('%s', null, { style: 'disk' })" % kind
            self.assertNotIn(
                aguja,
                self.src,
                "el rail vuelve a colocar %s con el estilo escrito a mano: elegir "
                "Figura/Avatar dejara de tener efecto" % kind,
            )

    def test_el_rail_usa_el_estilo_elegido(self):
        self.assertIn("const estiloDelRail = () => (", self.src)
        # La chapa sigue siendo el DEFECTO: solo se cede si el entrenador eligio.
        self.assertIn("tokenGlobalStyleUserSelected ? normalizeTokenStyle(tokenGlobalStyle) : 'disk'", self.src)

    def test_el_rival_no_lleva_nuestra_equipacion(self):
        self.assertIn("const AVATAR_RIVAL_CAMPO = 'amarilla';", self.src)
        self.assertIn(
            "const esRival = kind === 'player_rival' || kind === 'goalkeeper_rival';",
            self.src,
            "resolveAvatarUrlForToken ha dejado de distinguir al rival",
        )
        self.assertIn("? AVATAR_RIVAL_CAMPO", self.src)
        self.assertIn("esRival ? avatarGkDelRival(nuestro) : nuestro", self.src)

    def test_el_portero_rival_no_lleva_nuestra_chapa(self):
        # Le faltaba la misma regla que al jugador de campo: caia en 'chapa_gk_azul',
        # que es la nuestra, y los dos porteros del campo salian identicos.
        self.assertIn(
            "? (esRival ? 'chapa_gk_negra' : 'chapa_gk_azul')",
            self.src,
            "chapaBaseUrlForToken vuelve a dar NUESTRA chapa de portero al portero rival",
        )

    def test_el_relleno_provisional_es_del_color_que_va_a_llegar(self):
        # Miraba solo isAway, asi que el rival parpadeaba en verde antes de amarillo.
        self.assertIn("const __esRival = isRivalTokenKind(kind);", self.src)
        self.assertIn("((isAway || __esRival) ? '#f4c400' : '#0f7a35')", self.src)

    def test_las_figuras_del_rival_existen(self):
        base = PAD.parent.parent / "images" / "players"
        faltan = [
            n for n in ("act-conduccion-amarilla.png", "act-gk-frente-rojo.png", "act-gk-frente-negro.png")
            if not (base / n).exists()
        ]
        self.assertEqual(faltan, [], "faltan las figuras con las que se viste al rival")


class TercerEquipoEnElRailTests(SimpleTestCase):
    """El rail ofrece la 2a equipacion: tiene que saber colocarla.

    `activateAddKind` tenia rama para local, rival y los dos porteros, pero NO para
    `player_away`, aunque el rail lo lista. El clic caia en `simpleFactory`, que no sabe
    construir una ficha de jugador, y no pasaba nada: una tarea de TRES equipos no se podia
    dibujar. Detectado el 2026-08-06 montando tareas de 3 equipos para el Cadete.
    """

    def test_el_rail_sabe_colocar_la_segunda_equipacion(self):
        src = PAD.read_text(encoding="utf-8")
        i = src.find("const activateAddKind = (add")
        self.assertGreater(i, 0, "no encuentro activateAddKind")
        bloque = src[i:i + 2000]
        self.assertIn("kind === 'player_away'", bloque)
        self.assertIn("playerTokenFactory('player_away', null, { style: estiloDelRail() })", bloque)


class ChapaAlReconstruirTests(SimpleTestCase):
    """Al abrir una tarea GUARDADA la chapa aun se esta descargando.

    La `fabric.Image` toma width/height del elemento, que en ese momento vale 0, y una imagen
    de 0x0 reescalada sigue siendo 0x0: la ficha se quedaba en el disco de relleno provisional
    para siempre. Colocandola a mano no se veia porque la chapa ya estaba en cache. El
    manejador de `load` tiene que devolver el TAMANIO, no solo la escala.
    """

    def test_el_manejador_de_carga_devuelve_el_tamanio(self):
        src = PAD.read_text(encoding="utf-8")
        i = src.find("__chapaEl.addEventListener('load'")
        self.assertGreater(i, 0, "ha desaparecido el manejador de carga de la chapa")
        bloque = src[i:i + 900]
        self.assertIn("naturalWidth", bloque)
        self.assertIn("__cimg.set({ width: __w, height: __h })", bloque)
