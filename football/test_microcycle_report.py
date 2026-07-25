import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from football.models import (
    Player,
    PlayerFine,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceMembership,
)


class MicrocycleReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="C.D. Prueba", slug="cdp", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="C.D. Prueba", slug="cdp", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.p1 = Player.objects.create(team=self.team, name="Ana Uno", number=1, position="Portero", is_active=True)
        self.p2 = Player.objects.create(team=self.team, name="Bea Dos", number=2, position="Central", is_active=True)
        self.p3 = Player.objects.create(team=self.team, name="Cris Tres", number=3, position="Delantero", is_active=True)

        today = timezone.localdate()
        self.mc = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Microciclo de prueba",
            week_start=today - datetime.timedelta(days=2),
            week_end=today + datetime.timedelta(days=4),
        )
        self.s1 = TrainingSession.objects.create(
            microcycle=self.mc, session_date=today - datetime.timedelta(days=1), focus="Fuerza"
        )
        self.s2 = TrainingSession.objects.create(microcycle=self.mc, session_date=today, focus="Táctica")
        A = TrainingSessionAttendance
        A.objects.create(session=self.s1, player=self.p1, status=A.STATUS_PRESENT)
        A.objects.create(session=self.s2, player=self.p1, status=A.STATUS_PRESENT)
        A.objects.create(session=self.s1, player=self.p2, status=A.STATUS_ABSENT, notes="Sin avisar")
        A.objects.create(session=self.s2, player=self.p2, status=A.STATUS_ABSENT)
        A.objects.create(session=self.s1, player=self.p3, status=A.STATUS_LATE)
        PlayerFine.objects.create(player=self.p2, reason=PlayerFine.REASON_ABSENCE, amount=10, note="Falta a entreno")

        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _get(self, q=""):
        return self.client.get(f"/coach/microciclo/informe/{q}", HTTP_HOST="localhost")

    def test_report_renders_with_attendance_and_fines(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("Asistencia por jugador", body)
        self.assertIn("Microciclo de prueba", body)
        self.assertIn("Bea Dos", body)          # jugadora con 2 ausencias
        self.assertIn("Multas", body)
        self.assertIn("10€", body)               # multa de la semana
        self.assertIn("Incidencias", body)
        self.assertIn("Sin avisar", body)        # nota de ausencia como incidencia

    def test_repeat_absence_alert(self):
        body = self._get().content.decode("utf-8")
        # Bea Dos falta a las 2 sesiones -> alerta de 2+ ausencias.
        self.assertIn("2+ ausencias", body)

    def test_empty_state_without_microcycle(self):
        TrainingSession.objects.all().delete()
        TrainingMicrocycle.objects.all().delete()
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Aún no hay microciclos", resp.content.decode("utf-8"))
