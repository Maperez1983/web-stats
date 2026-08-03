from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    SessionTask,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class TareasDeOtroEquipoTests(TestCase):
    """
    Las listas ya filtraban por equipo, pero abrir una tarea POR SU ID no comprobaba nada:
    con el número en la barra de direcciones se veía la del senior, y la de otro club.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="dueno-tareas", password="x")
        self.entrenador = User.objects.create_user(username="cadete-tareas", password="x")
        self.workspace = Workspace.objects.create(
            name="Club tareas", slug="club-tareas", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.senior = Team.objects.create(name="Senior tareas", slug="senior-tareas")
        self.cadete = Team.objects.create(name="Cadete tareas", slug="cadete-tareas")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.entrenador, role=WorkspaceMembership.ROLE_MEMBER
        )
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace, user=self.entrenador, team=self.cadete, is_default=True
        )
        self.tarea_senior = self._tarea(self.senior, "Rondo del senior")
        self.tarea_cadete = self._tarea(self.cadete, "Rondo del cadete")

        self.client.force_login(self.entrenador)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        sesion["active_team_by_workspace"] = {str(self.workspace.id): int(self.cadete.id)}
        sesion.save()

    def _tarea(self, equipo, nombre, *, plantilla=False):
        # Una semana distinta por microciclo: son únicos por equipo y semana.
        self._semana = getattr(self, "_semana", 2) + 1
        microciclo = TrainingMicrocycle.objects.create(
            team=equipo,
            week_start=date(2026, 8, self._semana),
            week_end=date(2026, 8, self._semana + 5),
        )
        sesion = TrainingSession.objects.create(
            microcycle=microciclo, session_date=date(2026, 8, 5), is_session_template=plantilla
        )
        return SessionTask.objects.create(session=sesion, title=nombre)

    def test_no_puede_abrir_la_tarea_del_senior(self):
        respuesta = self.client.get(reverse("session-task-detail", args=[self.tarea_senior.id]))

        self.assertEqual(respuesta.status_code, 404, "Se abre la tarea de otra categoría por id")

    def test_si_puede_abrir_la_suya(self):
        respuesta = self.client.get(reverse("session-task-detail", args=[self.tarea_cadete.id]))

        self.assertEqual(respuesta.status_code, 200)

    def test_la_biblioteca_del_club_se_comparte_entre_categorias(self):
        """Una plantilla de sesión es material del club: se ve desde cualquier categoría suya."""
        plantilla = self._tarea(self.senior, "Plantilla del club", plantilla=True)

        respuesta = self.client.get(reverse("session-task-detail", args=[plantilla.id]))

        self.assertEqual(respuesta.status_code, 200)

    def test_ni_la_biblioteca_de_otro_club(self):
        otro_duenio = User.objects.create_user(username="otro-tareas", password="x")
        otro = Workspace.objects.create(
            name="Otro club tareas", slug="otro-club-tareas",
            kind=Workspace.KIND_CLUB, owner_user=otro_duenio,
        )
        suyo = Team.objects.create(name="Equipo ajeno tareas", slug="ajeno-tareas")
        WorkspaceTeam.objects.create(workspace=otro, team=suyo)
        ajena = self._tarea(suyo, "Plantilla ajena", plantilla=True)

        respuesta = self.client.get(reverse("session-task-detail", args=[ajena.id]))

        self.assertEqual(respuesta.status_code, 404, "Se ve la biblioteca de otro club")

    def test_el_resto_de_vistas_usan_la_misma_regla(self):
        """El PDF, la portada y el resto cargan la tarea por id: comparten el guardián."""
        from .views import _can_reach_task

        peticion = self.client.get(reverse("session-task-detail", args=[self.tarea_cadete.id])).wsgi_request

        self.assertTrue(_can_reach_task(peticion, self.tarea_cadete))
        self.assertFalse(_can_reach_task(peticion, self.tarea_senior))
