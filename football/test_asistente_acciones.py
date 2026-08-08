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

    def test_un_si_suelto_no_ejecuta_nada(self):
        respuesta = self._decir("sí")
        self.assertIn("nada pendiente", respuesta.lower())
        self.assertEqual(self._marcas(), [])
