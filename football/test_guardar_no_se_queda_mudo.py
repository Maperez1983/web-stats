"""Un campo obligatorio que no se ve NO puede bloquear el guardado en silencio.

Medido en producción el 2026-08-08 sobre la tarea 1222 ("Ajax 50"): "Tipo de tarea" es
`required`, vive en el panel lateral clásico —que la carcasa actual del editor mantiene en
`display:none`— y no hay ningún otro sitio donde elegirlo. El navegador se niega a enviar el
formulario, no puede ni enfocar el campo para quejarse ("An invalid form control with
name='task_family' is not focusable"), y desde fuera pulsar Guardar no hace absolutamente nada.

**448 de las 957 tareas** no tienen ese campo relleno: en todas ellas guardar era imposible.

Estas pruebas fijan las dos mitades del arreglo. Si alguien quita el rescate y deja el campo
obligatorio y escondido, vuelve a haber media biblioteca que no se puede guardar, así que aquí
se falla antes de que llegue a producción.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

JS = Path(settings.BASE_DIR) / "football/static/football/js/sessions_tactical_pad.js"
SIDEBAR = Path(settings.BASE_DIR) / "football/templates/football/includes/task_builder/sidebar.html"


class GuardarNoSeQuedaMudoTests(SimpleTestCase):
    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")
        self.sidebar = SIDEBAR.read_text(encoding="utf-8")

    def test_el_campo_sigue_siendo_obligatorio_y_escondido(self):
        """Si esto cambia, el resto de las pruebas de aquí dejan de tener sentido.

        No es un fallo: es la premisa. Si algún día `task_family` deja de ser obligatorio, o se
        saca a un sitio visible, este test avisa de que hay que revisar el rescate (y quizá
        borrarlo, que sería la buena noticia).
        """
        self.assertRegex(
            self.sidebar, r'<select name="task_family"[^>]*\brequired\b',
            "task_family ya no es obligatorio: revisa si el rescate del guardado sigue haciendo falta",
        )

    def test_el_rescate_escucha_invalid_EN_CAPTURA(self):
        """El detalle que me costó dos intentos, y por eso está fijado aquí.

        Un `checkValidity()` dentro del manejador de `submit` NO sirve: cuando la validación
        nativa falla, `submit` no llega a dispararse nunca. Lo único que se dispara es `invalid`,
        y como no burbujea hay que escucharlo en fase de captura.
        """
        patron = re.compile(
            r"form\.addEventListener\(\s*['\"]invalid['\"].*?\}\s*,\s*true\s*\)",
            re.DOTALL,
        )
        self.assertRegex(
            self.js, patron,
            "el rescate no escucha `invalid` en captura: sin eso, pulsar Guardar no hace nada",
        )

    def test_si_el_campo_no_se_ve_se_PREGUNTA_el_valor(self):
        """Decir 'falta rellenar X' no basta si no hay forma de llegar a X."""
        self.assertIn(
            "pedirValorInalcanzable", self.js,
            "no hay forma de dar valor a un desplegable obligatorio que no está en pantalla",
        )
        rescate = self.js[self.js.index("const pedirValorInalcanzable"):][:3000]
        self.assertIn(
            "campo.options", rescate,
            "las opciones deben salir del propio <select>: duplicar el vocabulario a mano se "
            "queda viejo en cuanto se añada una familia de tarea",
        )
        self.assertIn(
            "requestSubmit", rescate,
            "elegir el valor tiene que guardar; si no, el usuario se queda igual de atascado",
        )

    def test_el_aviso_dice_QUE_campo_falta(self):
        self.assertIn("Falta rellenar «", self.js,
                      "el aviso no nombra el campo que falta")
