from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from football.models import (
    Club,
    SessionTask,
    SessionTaskCollection,
    SessionTaskCollectionItem,
    Team,
    TrainingMicrocycle,
    TrainingSession,
)
from football.views import _ai_trainer_suggest_tasks_for_session


class TaskRecommenderTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        today = timezone.localdate()
        # Microciclo BIBLIOTECA con una tarea (así el motor la considera candidata).
        lib_mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca test", week_start=today - timedelta(days=14), week_end=today - timedelta(days=8)
        )
        lib_sess = TrainingSession.objects.create(microcycle=lib_mc, session_date=today, focus="")
        self.lib_task = SessionTask.objects.create(
            session=lib_sess, block="main_1", title="Rondo de presión tras pérdida",
            objective="Trabajar la presión tras pérdida en campo rival", duration_minutes=12,
        )

    def test_recommends_matching_library_task_from_session_context(self):
        today = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana 1", week_start=today, week_end=today + timedelta(days=6),
            objective="Presión tras pérdida",
        )
        session = TrainingSession.objects.create(
            microcycle=mc, session_date=today, focus="Presión tras pérdida en campo rival",
        )
        rec = _ai_trainer_suggest_tasks_for_session(session, limit=6)
        self.assertIn(self.lib_task.id, [getattr(t, "id", None) for t in rec])

    def test_no_context_returns_empty(self):
        today = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana 2", week_start=today + timedelta(days=7), week_end=today + timedelta(days=13)
        )
        session = TrainingSession.objects.create(microcycle=mc, session_date=today, focus="")
        self.assertEqual(_ai_trainer_suggest_tasks_for_session(session), [])


class RecomendadorPremiumTests(TestCase):
    """Lo que hace que la recomendación valga: metodología por delante del parecido de
    palabras, material del club visible desde cualquier categoría, y variedad."""

    def setUp(self):
        self.club = Club.objects.create(name="CD Prueba")
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True, club=self.club)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Biblioteca test",
            week_start=hoy - timedelta(days=14),
            week_end=hoy - timedelta(days=8),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")

    def _tarea(self, titulo, *, meta=None, objetivo="", equipo_sesion=None):
        return SessionTask.objects.create(
            session=equipo_sesion or self.biblioteca,
            block="main_1",
            title=titulo,
            objective=objetivo,
            duration_minutes=12,
            tactical_layout={"meta": meta or {}},
        )

    def _sesion(self, **campos):
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        return TrainingSession.objects.create(microcycle=mc, session_date=hoy, **campos)

    def test_la_metodologia_manda_sobre_repetir_palabras(self):
        etiquetada = self._tarea(
            "Salida desde portero",
            meta={"game_moment": "offensive_organization"},
            objetivo="Sacar limpio jugando",
        )
        cotorra = self._tarea(
            "Charla",
            objetivo="posesion posesion posesion posesion posesion posesion",
        )
        sesion = self._sesion(focus="posesion", game_moment="offensive_organization")
        rec = _ai_trainer_suggest_tasks_for_session(sesion, limit=6)
        ids = [t.id for t in rec]
        self.assertIn(etiquetada.id, ids)
        self.assertIn(cotorra.id, ids)
        self.assertLess(
            ids.index(etiquetada.id), ids.index(cotorra.id),
            "la tarea del momento de juego que se entrena tiene que ir por delante",
        )
        self.assertIn("mismo momento de juego", getattr(rec[0], "ai_trainer_reasons", []))

    def test_una_palabra_no_casa_dentro_de_otra(self):
        # "area" vivía dentro de "tarea": la búsqueda era por subcadena y colaba cualquier cosa.
        self._tarea("Tarea de rueda de pases", objetivo="Rueda de pases con dos apoyos")
        sesion = self._sesion(focus="area")
        self.assertEqual(_ai_trainer_suggest_tasks_for_session(sesion, limit=6), [])

    def test_las_tareas_del_libro_se_ven_desde_otra_categoria(self):
        del_libro = self._tarea("Rondo 4x4 del libro", objetivo="Circular la pelota en posesion")
        carpeta = SessionTaskCollection.objects.create(
            team=self.team, repository=SessionTaskCollection.REPO_INTERACTIVE, name="Tareas importadas"
        )
        SessionTaskCollectionItem.objects.create(collection=carpeta, task=del_libro)

        cadete = Team.objects.create(name="Cadete", slug="cadete", club=self.club)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=cadete, title="Semana cadete", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        sesion = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="posesion")
        ids = [t.id for t in _ai_trainer_suggest_tasks_for_session(sesion, limit=6)]
        self.assertIn(del_libro.id, ids, "el material del club tiene que llegar a todas las categorias")

    def test_no_devuelve_seis_veces_lo_mismo(self):
        for i in range(6):
            self._tarea(f"Rondo {i}", meta={"task_family": "rondo"}, objetivo="posesion en rondo")
        for i in range(3):
            self._tarea(f"Circuito {i}", meta={"task_family": "circuito"}, objetivo="posesion en circuito")
        sesion = self._sesion(focus="posesion")
        rec = _ai_trainer_suggest_tasks_for_session(sesion, limit=4)
        familias = [getattr(t, "task_family", "") for t in rec]
        self.assertLessEqual(familias.count("rondo"), 2, "no puede devolver la misma familia una y otra vez")
        self.assertEqual(len(rec), 4, "y aun asi tiene que devolver las que se le piden")


class RecomendadorAprendeDelUsoTests(TestCase):
    """Lo que el entrenador LLEVA AL CAMPO es la señal buena: pesa, y caduca."""

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-uso", is_primary=True)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Biblioteca uso",
            week_start=hoy - timedelta(days=21),
            week_end=hoy - timedelta(days=15),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")

    def _de_biblioteca(self, titulo, **campos):
        return SessionTask.objects.create(
            session=self.biblioteca, block="main_1", title=titulo,
            objective="Rondo de posesion con apoyos", duration_minutes=12, **campos,
        )

    def _sesion_real(self, dias=0):
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title=f"Semana {dias}",
            week_start=hoy + timedelta(days=dias), week_end=hoy + timedelta(days=dias + 6),
        )
        return TrainingSession.objects.create(
            microcycle=mc, session_date=hoy + timedelta(days=dias), focus="posesion"
        )

    def test_meter_la_tarea_en_una_sesion_apunta_el_uso(self):
        origen = self._de_biblioteca("Rondo 5x2")
        sesion = self._sesion_real()
        SessionTask.objects.create(
            session=sesion, block="main_1", title="Rondo 5x2", duration_minutes=12,
            tactical_layout={"meta": {"library_source_task_id": origen.id}},
        )
        origen.refresh_from_db()
        self.assertEqual(origen.veces_usada, 1)
        self.assertEqual(origen.usada_por_ultima_vez, sesion.session_date)

    def test_guardar_en_biblioteca_no_cuenta_como_usarla(self):
        origen = self._de_biblioteca("Rondo 4x4")
        SessionTask.objects.create(
            session=self.biblioteca, block="main_1", title="Copia en biblioteca", duration_minutes=12,
            tactical_layout={"meta": {"library_source_task_id": origen.id}},
        )
        origen.refresh_from_db()
        self.assertEqual(origen.veces_usada, 0, "archivar una plantilla no es decidir entrenarla")

    def test_la_que_usas_sale_por_delante_de_la_que_nunca_has_usado(self):
        nunca = self._de_biblioteca("Rondo que nunca uso")
        usada = self._de_biblioteca(
            "Rondo que uso siempre", veces_usada=5, usada_por_ultima_vez=timezone.localdate()
        )
        rec = _ai_trainer_suggest_tasks_for_session(self._sesion_real(dias=7), limit=6)
        ids = [t.id for t in rec]
        self.assertIn(usada.id, ids)
        self.assertIn(nunca.id, ids)
        self.assertLess(ids.index(usada.id), ids.index(nunca.id))
        self.assertIn("la has usado 5 veces", getattr(rec[0], "ai_trainer_reasons", []))

    def test_el_uso_viejo_pesa_menos_que_el_reciente(self):
        antigua = self._de_biblioteca(
            "Rondo del otono", veces_usada=5,
            usada_por_ultima_vez=timezone.localdate() - timedelta(days=270),
        )
        reciente = self._de_biblioteca(
            "Rondo de esta semana", veces_usada=5, usada_por_ultima_vez=timezone.localdate()
        )
        ids = [t.id for t in _ai_trainer_suggest_tasks_for_session(self._sesion_real(dias=14), limit=6)]
        self.assertLess(
            ids.index(reciente.id), ids.index(antigua.id),
            "usarla cinco veces en octubre no vale lo mismo que usarla esta semana",
        )


class RecomendadorContextoTests(TestCase):
    """El hueco que llenas, el día del microciclo y la edad: datos que ya estaban guardados
    y que el recomendador ignoraba."""

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-ctx", is_primary=True)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca ctx",
            week_start=hoy - timedelta(days=21), week_end=hoy - timedelta(days=15),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")

    def _tarea(self, titulo, *, block="main_1", meta=None):
        return SessionTask.objects.create(
            session=self.biblioteca, block=block, title=titulo,
            objective="posesion con apoyos", duration_minutes=12, tactical_layout={"meta": meta or {}},
        )

    def _sesion(self, **campos):
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Sem ctx", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        return TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="posesion", **campos)

    def test_propone_del_bloque_que_estas_llenando(self):
        calma = self._tarea("Estiramientos con balon", block="recovery")
        principal = self._tarea("Posesion 6x6", block="main_1")
        rec = _ai_trainer_suggest_tasks_for_session(self._sesion(), limit=6, bloque="main_1")
        ids = [t.id for t in rec]
        self.assertLess(ids.index(principal.id), ids.index(calma.id))
        self.assertIn("del bloque que estás llenando", getattr(rec[0], "ai_trainer_reasons", []))

    def test_en_md_1_no_recomienda_carga_fisica_por_delante(self):
        fisica = self._tarea("Circuito de fuerza", meta={"content_domain": "physical"})
        tactica = self._tarea("Posesion posicional", meta={"content_domain": "tactical"})
        rec = _ai_trainer_suggest_tasks_for_session(self._sesion(md_day="md_minus_1"), limit=6)
        ids = [t.id for t in rec]
        self.assertLess(ids.index(tactica.id), ids.index(fisica.id))

    def test_en_md_3_la_carga_fisica_encaja(self):
        fisica = self._tarea("Circuito de fuerza", meta={"content_domain": "physical"})
        self._tarea("Posesion posicional", meta={"content_domain": "tactical"})
        rec = _ai_trainer_suggest_tasks_for_session(self._sesion(md_day="md_minus_3"), limit=6)
        self.assertEqual(rec[0].id, fisica.id)
        self.assertIn("encaja con la carga del día", rec[0].ai_trainer_reasons)

    def test_una_tarea_de_otra_edad_baja(self):
        self.team.category = "alevin"
        self.team.save(update_fields=["category"])
        senior = self._tarea("Once contra once", meta={"age_group": "senior"})
        suya = self._tarea("Rondo para alevin", meta={"age_group": "alevin"})
        ids = [t.id for t in _ai_trainer_suggest_tasks_for_session(self._sesion(), limit=6)]
        self.assertLess(ids.index(suya.id), ids.index(senior.id))


class RecomendadorMideYAprendeDelDescarteTests(TestCase):
    """Sin saber qué propuso no se puede afirmar que acierte, ni aprender de lo ignorado."""

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior-med", is_primary=True)
        hoy = timezone.localdate()
        mc = TrainingMicrocycle.objects.create(
            team=self.team, title="Biblioteca med",
            week_start=hoy - timedelta(days=21), week_end=hoy - timedelta(days=15),
        )
        self.biblioteca = TrainingSession.objects.create(microcycle=mc, session_date=hoy, focus="")
        self.a = SessionTask.objects.create(
            session=self.biblioteca, block="main_1", title="Rondo A",
            objective="posesion en rondo", duration_minutes=12,
        )
        self.b = SessionTask.objects.create(
            session=self.biblioteca, block="main_1", title="Rondo B",
            objective="posesion en rondo largo", duration_minutes=12,
        )
        mc2 = TrainingMicrocycle.objects.create(
            team=self.team, title="Sem med", week_start=hoy, week_end=hoy + timedelta(days=6)
        )
        self.sesion = TrainingSession.objects.create(microcycle=mc2, session_date=hoy, focus="posesion")

    def test_queda_constancia_de_lo_propuesto(self):
        from football.models import AiTrainerRecomendacion

        _ai_trainer_suggest_tasks_for_session(self.sesion, limit=6)
        filas = AiTrainerRecomendacion.objects.filter(session=self.sesion)
        self.assertEqual(filas.count(), 2)
        self.assertTrue(all(f.puesto > 0 for f in filas))

    def test_no_duplica_al_volver_a_proponer(self):
        from football.models import AiTrainerRecomendacion

        _ai_trainer_suggest_tasks_for_session(self.sesion, limit=6)
        _ai_trainer_suggest_tasks_for_session(self.sesion, limit=6)
        filas = AiTrainerRecomendacion.objects.filter(session=self.sesion)
        self.assertEqual(filas.count(), 2)
        self.assertEqual(sorted(f.veces_propuesta for f in filas), [2, 2])

    def test_elegir_una_marca_esa_y_cierra_las_demas(self):
        from football.models import AiTrainerRecomendacion

        _ai_trainer_suggest_tasks_for_session(self.sesion, limit=6)
        SessionTask.objects.create(
            session=self.sesion, block="main_1", title="Rondo A", duration_minutes=12,
            tactical_layout={"meta": {"library_source_task_id": self.a.id}},
        )
        elegida = AiTrainerRecomendacion.objects.get(session=self.sesion, task=self.a)
        descartada = AiTrainerRecomendacion.objects.get(session=self.sesion, task=self.b)
        self.assertTrue(elegida.usada)
        self.assertFalse(descartada.usada)

    def test_lo_ignorado_resta_menos_de_lo_que_suma_usarlo(self):
        from football.ai_trainer import CASTIGO_POR_IGNORAR, PESO_POR_USO

        self.assertLess(CASTIGO_POR_IGNORAR, PESO_POR_USO,
                        "que no te sirva hoy no significa que la tarea sea mala")
