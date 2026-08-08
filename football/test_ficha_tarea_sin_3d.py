"""La ficha de una tarea NO saca la "Vista 3D" al lado de la pizarra. Tampoco al guardar.

La 3D en pantalla sólo puede salir como un estadio vacío -el canvas no se reconstruye ahí- y se
comía media fila al lado del dibujo bueno. Se quitó, y volvía a aparecer JUSTO al pulsar Guardar.

La causa era un cruce de cables: `_wants_full_layout` existe por RENDIMIENTO (cargar o no la
columna pesada `tactical_layout`) y vale True en cualquier POST. Ese mismo valor se estaba pasando
como `allow_live_canvas_render`, que a su vez decidía si se enseña la 3D. Así que guardar ->
POST -> layout completo -> y la 3D revivía. Son dos preguntas distintas: "¿tengo el lienzo?" y
"¿quiero enseñar el 3D?".
"""
import datetime
import json

# Dos objetos de una pizarra REAL, para que el render vivo tenga algo que dibujar.
CANVAS_MINIMO = r"""{"version": "5.3.0", "objects": [{"rx": 0, "ry": 0, "top": 88, "data": {"kind": "goal_mini", "layer_uid": "layer_1786033290932_0"}, "fill": "rgba(255,255,255,0.32)", "left": 300, "type": "rect", "angle": 0, "flipX": false, "flipY": false, "skewX": 0, "skewY": 0, "width": 96, "height": 16, "scaleX": 1, "scaleY": 1, "shadow": null, "stroke": "#ffffff", "opacity": 1, "originX": "center", "originY": "center", "version": "5.3.0", "visible": true, "fillRule": "nonzero", "paintFirst": "fill", "strokeWidth": 3, "strokeLineCap": "butt", "strokeUniform": false, "strokeLineJoin": "miter", "backgroundColor": "", "strokeDashArray": null, "strokeDashOffset": 0, "strokeMiterLimit": 4, "globalCompositeOperation": "source-over"}, {"rx": 0, "ry": 0, "top": 652, "data": {"kind": "goal_mini", "layer_uid": "layer_1786033290932_1"}, "fill": "rgba(255,255,255,0.32)", "left": 300, "type": "rect", "angle": 0, "flipX": false, "flipY": false, "skewX": 0, "skewY": 0, "width": 96, "height": 16, "scaleX": 1, "scaleY": 1, "shadow": null, "stroke": "#ffffff", "opacity": 1, "originX": "center", "originY": "center", "version": "5.3.0", "visible": true, "fillRule": "nonzero", "paintFirst": "fill", "strokeWidth": 3, "strokeLineCap": "butt", "strokeUniform": false, "strokeLineJoin": "miter", "backgroundColor": "", "strokeDashArray": null, "strokeDashOffset": 0, "strokeMiterLimit": 4, "globalCompositeOperation": "source-over"}]}"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    SessionTask, Team, TrainingMicrocycle, TrainingSession, Workspace,
)

HOY = datetime.date(2026, 8, 6)


class LaFichaDeTareaNoSacaLa3DTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("tecnico", "t@x.es", "x")
        self.team = Team.objects.create(name="Equipo Ficha", slug="equipo-ficha", category="Senior", is_primary=True)
        self.ws = Workspace.objects.create(
            name="Club Ficha", kind=Workspace.KIND_CLUB, owner_user=self.user, primary_team=self.team
        )
        mc = TrainingMicrocycle.objects.create(
            team=self.team, week_start=HOY - datetime.timedelta(days=3), week_end=HOY + datetime.timedelta(days=3)
        )
        ses = TrainingSession.objects.create(microcycle=mc, session_date=HOY)
        # Un lienzo REAL (dos objetos de la pizarra de una tarea suya). Con un lienzo inventado el
        # render no llega a producir 3D y el test pasaba con el fallo puesto: no probaba nada.
        canvas = json.loads(CANVAS_MINIMO)
        layout = {
            "meta": {
                "series": "6", "repetitions": "4", "work_rest": "4 minutos por serie",
                "space": "40 x 45", "structure": "complete", "coordination": "team",
                "tactical_intent": "recover", "success_criteria": "Gana quien más marca.",
                "pitch_preset": "full_pitch", "pitch_orientation": "landscape",
                "analysis": {"task_sheet": {"dimensions": "40 x 45", "materials": "Conos, Balones",
                                            "description": "3 equipos de 5."}},
                "graphic_editor": {"canvas_state": canvas},
            },
            "tokens": [],
        }
        self.task = SessionTask.objects.create(
            session=ses, title="3 equipos · recuperar", block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=20, objective="3 equipos de 6.",
            coaching_points="Recuperar rápido.", confrontation_rules="No entrar en la zona.",
            tactical_layout=layout, task_layout_light=layout,
        )
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion["active_workspace_id"] = int(self.ws.id)
        sesion.save()
        self.url = reverse("session-task-detail", args=[self.task.id])

    def _capturar_llamadas(self):
        """Espía a `_build_task_pdf_context` y devuelve los kwargs de cada llamada.

        Se comprueba la DECISIÓN y no el HTML a propósito: en un entorno de test el render del
        3D nunca llega a producirse -no hay con qué dibujarlo-, así que un test sobre el HTML
        pasaba igual con el fallo puesto. Comprobado a mano: no probaba nada.
        """
        from unittest.mock import patch

        from football import views

        original = views._build_task_pdf_context
        llamadas = []

        def espia(*args, **kwargs):
            llamadas.append(kwargs)
            return original(*args, **kwargs)

        return patch.object(views, "_build_task_pdf_context", side_effect=espia), llamadas

    def _sale_la_3d(self, html):
        """La 3D se pinta con su rótulo; si no está, la 2D va a todo el ancho."""
        return "Vista 3D (plasmado automático)" in html and 'style="display:none"' not in html.split(
            "Vista 3D (plasmado automático)"
        )[0][-120:]

    def test_al_abrir_la_ficha_se_pide_SIN_3d(self):
        parche, llamadas = self._capturar_llamadas()
        with parche:
            self.client.get(self.url)
        self.assertTrue(llamadas, "no se ha construido el contexto de la ficha")
        self.assertIs(
            llamadas[0].get("allow_3d_view"), False,
            "la ficha no está pidiendo explícitamente que NO se dibuje el 3D",
        )

    def test_al_GUARDAR_tambien_se_pide_SIN_3d(self):
        """El que fallaba: guardar es un POST, el POST enciende el render vivo, y con él el 3D."""
        datos = {
            "detail_action": "update_task_detail",
            "task_title": self.task.title,
            "task_minutes": "20",
            "task_block": SessionTask.BLOCK_MAIN_1,
            "task_objective": "3 equipos de 6.",
            "task_coaching_points": "Recuperar rápido.",
            "task_confrontation_rules": "No entrar en la zona.",
            "task_series": "6",
            "task_repetitions": "4",
            "task_work_rest": "4 minutos por serie",
            "task_sheet_dimensions": "40 x 45",
            "task_sheet_materials": "Conos, Balones",
            "task_sheet_description": "3 equipos de 5.",
            "task_success_criteria": "Gana quien más marca.",
            "task_structure": "complete",
            "task_coordination": "team",
            "task_tactical_intent": "recover",
        }
        parche, llamadas = self._capturar_llamadas()
        with parche:
            resp = self.client.post(self.url, datos)
        self.assertIn(resp.status_code, (200, 302))
        self.assertTrue(llamadas, "no se ha construido el contexto tras guardar")
        self.assertIs(
            llamadas[0].get("allow_3d_view"), False,
            "al guardar vuelve la doble pizarra: el 3D se enciende porque el POST pide el layout "
            "completo y esa bandera decidía las dos cosas",
        )
        # Y el layout completo SÍ se sigue pidiendo: el arreglo no puede cargarse el rendimiento
        # ni el render del 2D.
        self.assertIs(llamadas[0].get("allow_live_canvas_render"), True)

    def test_el_pdf_descargable_SI_puede_llevar_3d(self):
        """La 3D no se prohíbe en general: sólo en la ficha de pantalla. Quien la quiera, la pide."""
        import inspect

        from football import views

        firma = inspect.signature(views._build_task_pdf_context)
        self.assertIn("allow_3d_view", firma.parameters)
        self.assertIsNone(
            firma.parameters["allow_3d_view"].default,
            "por defecto tiene que heredar el comportamiento de antes, no forzar False",
        )
