from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import (
    TrainingMicrocycle,
    Player,
    PlayerObjective,
    SessionTask,
    SessionTaskParticipation,
    Team,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class FichasDeDetalleTests(TestCase):
    """Objetivo y sesión tienen ficha propia, con el mismo molde que lesión y comunicación."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno9", password="x")
        self.workspace = Workspace.objects.create(
            name="Club fichas", slug="club-fichas", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Senior fichas", slug="senior-fichas")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.player = Player.objects.create(name="Jugador Fichas", team=self.team, is_active=True)
        self.objetivo = PlayerObjective.objects.create(
            player=self.player, text="Mejorar el perfil de recepción"
        )
        self.microciclo = TrainingMicrocycle.objects.create(team=self.team, week_start=date(2026, 7, 27), week_end=date(2026, 8, 2))
        self.sesion = TrainingSession.objects.create(
            microcycle=self.microciclo, session_date=date(2026, 7, 28)
        )
        self.tarea = SessionTask.objects.create(
            session=self.sesion, title="Rondo 8x2", duration_minutes=20
        )
        SessionTaskParticipation.objects.create(session_task=self.tarea, player=self.player)
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_la_ficha_del_objetivo_abre(self):
        resp = self.client.get(
            reverse("player-objective-detail", args=[self.player.id, self.objetivo.id])
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mejorar el perfil de recepción")
        self.assertContains(resp, "Pendiente")

    def test_mover_el_objetivo_a_cumplido_deja_fecha(self):
        self.client.post(
            reverse("player-objective-detail", args=[self.player.id, self.objetivo.id]),
            {"form_action": "status", "status": PlayerObjective.STATUS_DONE},
        )
        self.objetivo.refresh_from_db()

        self.assertEqual(self.objetivo.status, PlayerObjective.STATUS_DONE)
        self.assertIsNotNone(self.objetivo.done_at)

    def test_la_ficha_de_sesion_cuenta_sus_tareas_y_minutos(self):
        resp = self.client.get(
            reverse("player-session-detail", args=[self.player.id, self.sesion.id])
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Rondo 8x2")
        self.assertContains(resp, "20 min")
        # Sin registro de asistencia se asume presente, como en los contadores del portal.
        self.assertContains(resp, "Presente (sin marcar)")

    def test_la_ficha_de_sesion_respeta_la_ausencia_marcada(self):
        TrainingSessionAttendance.objects.create(
            session=self.sesion, player=self.player, status=TrainingSessionAttendance.STATUS_ABSENT
        )

        resp = self.client.get(
            reverse("player-session-detail", args=[self.player.id, self.sesion.id])
        )

        self.assertNotContains(resp, "Presente (sin marcar)")

    def test_no_se_puede_mirar_la_sesion_de_otro_equipo(self):
        otro_equipo = Team.objects.create(name="Otro fichas", slug="otro-fichas")
        otro_micro = TrainingMicrocycle.objects.create(team=otro_equipo, week_start=date(2026, 7, 27), week_end=date(2026, 8, 2))
        ajena = TrainingSession.objects.create(microcycle=otro_micro, session_date=date(2026, 7, 29))

        resp = self.client.get(
            reverse("player-session-detail", args=[self.player.id, ajena.id])
        )

        self.assertEqual(resp.status_code, 404)
