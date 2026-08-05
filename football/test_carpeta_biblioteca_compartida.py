"""Una carpeta de la biblioteca se ve desde cualquier categoría del club.

Las tareas del libro se importan a una carpeta que cuelga del senior, porque es quien tiene
la biblioteca. Desde que las listas filtran por categoría, al entrar como cadete la carpeta
desaparecía y abrir una tarea por su id daba 404 (2026-08-05).
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    SessionTask,
    SessionTaskCollection,
    SessionTaskCollectionItem,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class CarpetaCompartidaTests(TestCase):
    def setUp(self):
        self.duenio = User.objects.create_user(username='dueno-carpeta', password='x')
        self.entrenador = User.objects.create_user(username='cadete-carpeta', password='x')
        self.workspace = Workspace.objects.create(
            name='Club carpeta', slug='club-carpeta', kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        self.senior = Team.objects.create(name='Senior carpeta', slug='senior-carpeta')
        self.cadete = Team.objects.create(name='Cadete carpeta', slug='cadete-carpeta')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.entrenador, role=WorkspaceMembership.ROLE_MEMBER
        )
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace, user=self.entrenador, team=self.cadete, is_default=True
        )
        self.tarea = self._tarea_en_carpeta(self.senior, 'Tareas importadas', '4 c 4 en seis subzonas')
        self.client.force_login(self.entrenador)

    def _tarea_en_carpeta(self, team, carpeta, titulo):
        mc = TrainingMicrocycle.objects.create(
            team=team, title='Biblioteca', week_start=date(2000, 1, 10), week_end=date(2000, 1, 16)
        )
        sesion = TrainingSession.objects.create(microcycle=mc, session_date=date(2000, 1, 10), duration_minutes=90)
        tarea = SessionTask.objects.create(session=sesion, title=titulo)
        coleccion = SessionTaskCollection.objects.create(
            team=team, repository=SessionTaskCollection.REPO_INTERACTIVE, name=carpeta
        )
        SessionTaskCollectionItem.objects.create(collection=coleccion, task=tarea)
        return tarea

    def test_el_cadete_alcanza_una_tarea_archivada_en_la_carpeta_del_senior(self):
        from .views import _can_reach_task

        peticion = self.client.get(reverse('session-task-detail', args=[self.tarea.id])).wsgi_request

        self.assertTrue(_can_reach_task(peticion, self.tarea))

    def test_y_la_abre_sin_404(self):
        respuesta = self.client.get(reverse('session-task-detail', args=[self.tarea.id]))

        self.assertEqual(respuesta.status_code, 200)

    def test_una_tarea_suelta_del_senior_sigue_sin_verse(self):
        """Compartir la carpeta no abre la puerta al resto del material de otra categoría."""
        from .views import _can_reach_task

        mc = TrainingMicrocycle.objects.create(
            team=self.senior, title='Semana', week_start=date(2026, 8, 3), week_end=date(2026, 8, 9)
        )
        sesion = TrainingSession.objects.create(microcycle=mc, session_date=date(2026, 8, 4), duration_minutes=90)
        suelta = SessionTask.objects.create(session=sesion, title='Rondo del senior')
        peticion = self.client.get(reverse('session-task-detail', args=[self.tarea.id])).wsgi_request

        self.assertFalse(_can_reach_task(peticion, suelta))

    def test_la_carpeta_de_otro_club_no_se_ve(self):
        from .views import _can_reach_task

        otro_duenio = User.objects.create_user(username='otro-carpeta', password='x')
        otro = Workspace.objects.create(
            name='Otro club carpeta', slug='otro-club-carpeta', kind=Workspace.KIND_CLUB, owner_user=otro_duenio
        )
        ajeno = Team.objects.create(name='Ajeno carpeta', slug='ajeno-carpeta')
        WorkspaceTeam.objects.create(workspace=otro, team=ajeno)
        tarea_ajena = self._tarea_en_carpeta(ajeno, 'Tareas importadas', 'Tarea de otro club')
        peticion = self.client.get(reverse('session-task-detail', args=[self.tarea.id])).wsgi_request

        self.assertFalse(_can_reach_task(peticion, tarea_ajena))

    def test_las_carpetas_del_club_se_listan_desde_cualquier_categoria(self):
        from .library_sharing import carpetas_del_club

        nombres = list(
            carpetas_del_club(self.workspace, self.cadete, SessionTaskCollection.REPO_INTERACTIVE).values_list(
                'name', flat=True
            )
        )

        self.assertIn('Tareas importadas', nombres)
