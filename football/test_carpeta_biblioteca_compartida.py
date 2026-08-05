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
        # Un equipo tiene UN microciclo de biblioteca: se reutiliza, como en producción.
        mc, _ = TrainingMicrocycle.objects.get_or_create(
            team=team, week_start=date(2000, 1, 10),
            defaults={'title': 'Biblioteca', 'week_end': date(2000, 1, 16)},
        )
        sesion, _ = TrainingSession.objects.get_or_create(
            microcycle=mc, session_date=date(2000, 1, 10), defaults={'duration_minutes': 90}
        )
        tarea = SessionTask.objects.create(session=sesion, title=titulo)
        coleccion, _ = SessionTaskCollection.objects.get_or_create(
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
        from .library_sharing import carpetas_visibles

        nombres = list(
            carpetas_visibles(self.workspace, self.cadete, SessionTaskCollection.REPO_INTERACTIVE).values_list(
                'name', flat=True
            )
        )

        self.assertIn('Tareas importadas', nombres)

    def test_la_biblioteca_de_aitor_no_sale_del_senior(self):
        """Sólo se comparte lo importado: la biblioteca de una persona es de su categoría."""
        from .library_sharing import carpetas_visibles

        self._tarea_en_carpeta(self.senior, 'Biblioteca de Aitor', 'Rondo de Aitor')

        nombres = list(
            carpetas_visibles(self.workspace, self.cadete, SessionTaskCollection.REPO_INTERACTIVE).values_list(
                'name', flat=True
            )
        )

        self.assertIn('Tareas importadas', nombres)
        self.assertNotIn('Biblioteca de Aitor', nombres)

    def test_y_su_tarea_tampoco_se_alcanza_desde_el_cadete(self):
        from .views import _can_reach_task

        suya = self._tarea_en_carpeta(self.senior, 'Biblioteca de Aitor', 'Otro rondo de Aitor')
        peticion = self.client.get(reverse('session-task-detail', args=[self.tarea.id])).wsgi_request

        self.assertFalse(_can_reach_task(peticion, suya))

    def test_el_editor_abre_una_tarea_de_la_carpeta_desde_el_cadete(self):
        """Ver la tarea funcionaba, pero el editor la buscaba acotada al equipo activo: 404."""
        respuesta = self.client.get(reverse('sessions-task-edit', args=[self.tarea.id]))

        self.assertEqual(respuesta.status_code, 200)

    def test_el_editor_sigue_cerrado_a_una_tarea_suelta_de_otra_categoria(self):
        mc = TrainingMicrocycle.objects.create(
            team=self.senior, title='Semana', week_start=date(2026, 8, 10), week_end=date(2026, 8, 16)
        )
        sesion = TrainingSession.objects.create(microcycle=mc, session_date=date(2026, 8, 11), duration_minutes=90)
        suelta = SessionTask.objects.create(session=sesion, title='Rondo privado')

        respuesta = self.client.get(reverse('sessions-task-edit', args=[suelta.id]))

        self.assertEqual(respuesta.status_code, 404)


class SelectorDeBibliotecasTests(TestCase):
    """El selector pintaba las tres bibliotecas siempre, con cero tareas y en cualquier club."""

    def setUp(self):
        self.duenio = User.objects.create_user(username='dueno-selector', password='x')
        self.workspace = Workspace.objects.create(
            name='Club selector', slug='club-selector', kind=Workspace.KIND_CLUB, owner_user=self.duenio
        )
        self.equipo = Team.objects.create(name='Senior selector', slug='senior-selector')
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.equipo, is_default=True)
        self.client.force_login(self.duenio)

    def test_un_club_sin_tareas_no_ve_la_biblioteca_de_aitor(self):
        respuesta = self.client.get(reverse('sessions') + '?tab=library')

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'Biblioteca de Aitor')

    def test_y_se_le_dice_que_no_hay_nada(self):
        respuesta = self.client.get(reverse('sessions') + '?tab=library')

        self.assertContains(respuesta, 'Todavía no hay tareas en la biblioteca')
