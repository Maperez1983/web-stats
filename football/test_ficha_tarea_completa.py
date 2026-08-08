"""La ficha de tarea: los campos que faltaban y los desplegables que se quedaban cortos.

Medido antes de tocar nada, sobre las 705 tareas vivas del club: 41 campos en la ficha, 4 con
dato en una tarea editada a mano y 13 a cero absoluto. El problema no era el catalogo sino que
faltaban cuatro piezas y sobraba desorden.
"""
from django.test import SimpleTestCase, TestCase

from football import task_choices
from football.models import SessionTask, TrainingMicrocycle, TrainingSession, Team
from football.views import _update_library_task_from_post


class VocabulariosDeTareaTests(SimpleTestCase):
    def _claves(self, choices):
        return {clave for clave, _ in choices}

    def test_el_futbol_base_tiene_su_formato_de_campo(self):
        """El club es mayoria de ninos: el 3v3 y el 4v4 son el formato real del prebenjamin."""
        claves = self._claves(task_choices.TASK_PITCH_FORMAT_CHOICES)
        self.assertIn("3v3", claves)
        self.assertIn("4v4", claves)

    def test_la_escala_de_estructura_empieza_en_el_jugador(self):
        """Iba de sectorial hacia arriba: faltaban los dos escalones del trabajo especifico."""
        claves = self._claves(task_choices.TASK_STRUCTURE_CHOICES)
        self.assertIn("individual", claves)
        self.assertIn("group", claves)

    def test_el_portero_puede_decir_que_entrena(self):
        """Habia catalogo propio de valoracion de porteros y ni una accion suya en la tarea."""
        claves = self._claves(task_choices.TASK_COORDINATION_SKILLS_CHOICES)
        for accion in ("gk_save", "gk_catch", "gk_exit", "gk_punch"):
            self.assertIn(accion, claves)

    def test_la_superioridad_numerica_no_se_acaba_en_el_2v1(self):
        claves = self._claves(task_choices.TASK_TACTICAL_INTENT_CHOICES)
        for clave in ("3v2", "4v3", "5v5", "shift", "compact", "press_escape", "cover_watch"):
            self.assertIn(clave, claves)

    def test_el_rondo_esta_en_la_tipologia(self):
        """Es el ejercicio mas usado del futbol y solo existia como 'tipo de tarea'."""
        claves = self._claves(task_choices.TASK_STRATEGY_CHOICES)
        for clave in ("rondo", "gk_specific", "activation", "preventive"):
            self.assertIn(clave, claves)

    def test_una_sola_forma_de_nombrar_el_momento_del_juego(self):
        """Habia dos vocabularios para lo mismo con claves distintas
        (`organization_attack` frente a `offensive_organization`)."""
        self.assertIs(task_choices.TASK_GAME_PHASE_CHOICES, task_choices.GAME_MOMENT_CHOICES)

    def test_ninguna_lista_repite_clave(self):
        for nombre in dir(task_choices):
            if not nombre.endswith("_CHOICES"):
                continue
            opciones = getattr(task_choices, nombre)
            claves = [clave for clave, _ in opciones]
            self.assertEqual(len(claves), len(set(claves)), f"{nombre} tiene claves repetidas")


class CamposNuevosDeLaFichaTests(TestCase):
    def setUp(self):
        equipo = Team.objects.create(name="Benagalbón FT", slug="ben-ft")
        ciclo = TrainingMicrocycle.objects.create(
            team=equipo, week_start="2026-08-10", week_end="2026-08-16"
        )
        sesion = TrainingSession.objects.create(microcycle=ciclo, session_date="2026-08-11", focus="Entreno")
        self.task = SessionTask.objects.create(
            session=sesion, title="Rondo 5v2", block=SessionTask.BLOCK_MAIN_1, duration_minutes=15
        )

    def _guardar(self, **campos):
        datos = {"task_title": self.task.title}
        datos.update(campos)
        _update_library_task_from_post(self.task, datos, scope_key=None)
        self.task.refresh_from_db()
        return (self.task.tactical_layout or {}).get("meta") or {}

    def test_los_porteros_dejan_de_ir_dentro_del_texto_de_jugadores(self):
        meta = self._guardar(task_keepers="2")
        self.assertEqual(meta.get("keepers"), "2")

    def test_se_puede_enlazar_un_video(self):
        meta = self._guardar(task_video_url="https://youtu.be/abc123")
        self.assertEqual(meta.get("video_url"), "https://youtu.be/abc123")

    def test_un_enlace_que_no_sea_http_no_entra(self):
        """Se pinta como enlace en la ficha y en el PDF: un `javascript:` aqui es un agujero."""
        meta = self._guardar(task_video_url="javascript:alert(1)")
        self.assertEqual(meta.get("video_url"), "")

    def test_la_metodologia_por_fin_se_guarda(self):
        meta = self._guardar(task_methodology="integrated")
        self.assertEqual(meta.get("methodology"), "integrated")

    def test_una_metodologia_inventada_no_entra(self):
        meta = self._guardar(task_methodology="lo-que-sea")
        self.assertEqual(meta.get("methodology"), "")

    def test_como_salio_se_guarda_entero(self):
        meta = self._guardar(
            task_execution_rating="adjust",
            task_usefulness="4",
            task_real_minutes="18",
            task_execution_notes="El espacio se quedó pequeño con 12.",
        )
        self.assertEqual(meta.get("execution_rating"), "adjust")
        self.assertEqual(meta.get("usefulness"), "4")
        self.assertEqual(meta.get("real_minutes"), 18)
        self.assertIn("espacio", meta.get("execution_notes", ""))

    def test_los_condicionantes_aceptan_varios_y_filtran_lo_que_no_existe(self):
        class _Post(dict):
            def getlist(self, clave):
                valor = self.get(clave)
                return valor if isinstance(valor, list) else [valor]

        datos = _Post({"task_title": self.task.title, "task_constraints": ["two_touches", "jokers", "inventado"]})
        _update_library_task_from_post(self.task, datos, scope_key=None)
        self.task.refresh_from_db()
        meta = (self.task.tactical_layout or {}).get("meta") or {}
        self.assertEqual(meta.get("constraints"), ["two_touches", "jokers"])

    def test_renombrar_desde_la_tarjeta_no_borra_lo_que_ya_habia(self):
        """El guardado parcial vacio tareas enteras una vez: no puede volver a pasar."""
        self._guardar(task_methodology="global", task_keepers="1")
        meta = self._guardar()  # solo el titulo, como el renombrado rapido
        self.assertEqual(meta.get("methodology"), "global")
        self.assertEqual(meta.get("keepers"), "1")
