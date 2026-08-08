"""El asistente NO puede escribir sin que se lo confirmen.

Esto no es una prueba de cortesía: hoy se descubrió que el guardián reparaba datos del club
porque alguien le hacía una pregunta. Si mañana alguien mueve el orden de los enrutadores o
quita la confirmación, esto tiene que ponerse rojo.
"""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase

from football.models import (
    Player,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class AsistenteAccionesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("jefe", "jefe@x.es", "x")
        self.client.force_login(self.user)
        self.team = Team.objects.create(name="Equipo Prueba", is_primary=True)
        # Sin espacio de trabajo, `_get_primary_team_for_request` no resuelve el equipo y el
        # asistente contesta en generico: no es que falle el flujo, es que no hay contexto.
        self.workspace = Workspace.objects.create(
            name="Espacio Prueba", primary_team=self.team, owner_user=self.user
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_OWNER
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.player = Player.objects.create(team=self.team, name="Nico Ruiz", number=8, is_active=True)
        self.micro = TrainingMicrocycle.objects.create(
            team=self.team, title="Semana", week_start=date.today(), week_end=date.today() + timedelta(days=6)
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.micro, session_date=date.today(), focus="Prueba"
        )

    def _decir(self, texto):
        r = self.client.post(
            "/api/system/guard-chat/",
            data={"message": texto},
            content_type="application/json",
        )
        cuerpo = r.json() if r.status_code == 200 else {}
        return str(((cuerpo.get("chat") or {}).get("response") or {}).get("message") or "")

    def _marcas(self):
        return list(
            TrainingSessionAttendance.objects.filter(player=self.player).values_list("status", flat=True)
        )

    def test_una_orden_no_escribe_hasta_que_se_confirma(self):
        respuesta = self._decir("anota como ausente a Nico Ruiz")
        self.assertIn("¿Confirmo?", respuesta)
        self.assertIn("Nico Ruiz", respuesta)
        # Lo importante: TODAVIA no ha tocado nada.
        self.assertEqual(self._marcas(), [])

        self._decir("sí")
        self.assertEqual(self._marcas(), [TrainingSessionAttendance.STATUS_ABSENT])

    def test_si_se_dice_que_no_no_se_escribe(self):
        self._decir("anota como ausente a Nico Ruiz")
        self._decir("no")
        self.assertEqual(self._marcas(), [])

    def test_presente_borra_la_marca(self):
        # Presente se guarda BORRANDO la fila: la ausencia de marca significa "vino". Si esto
        # cambiara, la pantalla y el asistente contarian cosas distintas.
        TrainingSessionAttendance.objects.create(
            session=self.session, player=self.player, status=TrainingSessionAttendance.STATUS_ABSENT
        )
        self._decir("marca a Nico Ruiz como presente")
        self._decir("sí")
        self.assertEqual(self._marcas(), [])

    def test_una_orden_no_se_confunde_con_una_consulta(self):
        # "marca a X como LESIONADO" contestaba con la lista de lesionados, como si lo hubiera
        # hecho. Una orden nunca puede responderse con datos.
        respuesta = self._decir("marca a Nico Ruiz como lesionado")
        self.assertNotIn("lesionado(s):", respuesta)

    def test_un_nombre_dentro_de_otra_palabra_no_cuenta(self):
        # "Reno" encajaba dentro de "entRENO" y el asistente preguntaba "¿Reno o Harley?" en
        # "apunta que Harley no vino al entreno". Con dos jugadores reales asi, o eliges mal o
        # preguntas siempre; las dos cosas son inservibles.
        Player.objects.create(team=self.team, name="Reno", number=11, is_active=True)
        respuesta = self._decir("apunta que Nico Ruiz no vino al entreno")
        self.assertNotIn("¿A cuál de estos", respuesta)
        self.assertIn("Nico Ruiz", respuesta)

    def test_mover_una_tarea_de_bloque(self):
        from football.models import SessionTask

        tarea = SessionTask.objects.create(
            session=self.session, title="Rondo 6 vs 3", block=SessionTask.BLOCK_MAIN_1
        )
        respuesta = self._decir("mueve Rondo 6 vs 3 a vuelta a la calma")
        self.assertIn("¿Confirmo?", respuesta)
        tarea.refresh_from_db()
        self.assertEqual(tarea.block, SessionTask.BLOCK_MAIN_1)  # aún no

        self._decir("sí")
        tarea.refresh_from_db()
        self.assertEqual(tarea.block, SessionTask.BLOCK_RECOVERY)

    def test_borrar_una_tarea_la_manda_a_la_papelera_y_se_recupera(self):
        from football.models import SessionTask

        tarea = SessionTask.objects.create(session=self.session, title="Rondo 8 x 2")
        self._decir("borra la tarea Rondo 8 x 2")
        self._decir("sí")
        tarea.refresh_from_db()
        # A la PAPELERA, no destruida: tiene que poder volver.
        self.assertIsNotNone(tarea.deleted_at)
        self.assertTrue(SessionTask.objects.filter(id=tarea.id).exists())

        self._decir("restaura la tarea Rondo 8 x 2")
        self._decir("sí")
        tarea.refresh_from_db()
        self.assertIsNone(tarea.deleted_at)

    def test_una_accion_del_catalogo_no_escribe_si_dices_que_no(self):
        from football.models import SessionTask

        tarea = SessionTask.objects.create(
            session=self.session, title="Rondo 4 x 4", block=SessionTask.BLOCK_MAIN_1
        )
        self._decir("mueve Rondo 4 x 4 a ABP")
        self._decir("no")
        tarea.refresh_from_db()
        self.assertEqual(tarea.block, SessionTask.BLOCK_MAIN_1)

    def test_entre_dos_titulos_gana_el_mas_especifico(self):
        # Con "RONDO" y "Rondo 8 x 2" en la biblioteca, pedir la segunda hacia que encajaran las
        # dos. Quedarse con cualquiera es mandar a la papelera la equivocada.
        from football.models import SessionTask

        corta = SessionTask.objects.create(session=self.session, title="RONDO")
        larga = SessionTask.objects.create(session=self.session, title="Rondo 8 x 2")
        respuesta = self._decir("borra la tarea Rondo 8 x 2")
        self.assertIn("Rondo 8 x 2", respuesta)
        self._decir("sí")
        corta.refresh_from_db()
        larga.refresh_from_db()
        self.assertIsNone(corta.deleted_at)      # la corta NO se toca
        self.assertIsNotNone(larga.deleted_at)

    def test_un_si_suelto_no_ejecuta_nada(self):
        respuesta = self._decir("sí")
        self.assertIn("nada pendiente", respuesta.lower())
        self.assertEqual(self._marcas(), [])
