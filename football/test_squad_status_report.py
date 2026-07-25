import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import (
    Player,
    Team,
    Workspace,
    WorkspaceMembership,
)


class SquadStatusReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="C.D. Prueba", slug="cdp", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="C.D. Prueba", slug="cdp", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        # Plantilla mínima con posiciones y edades variadas.
        specs = [
            ("Portero Uno", "Portero", 2000),
            ("Central Uno", "Central", 1996),
            ("Lateral Uno", "Lateral derecho", 2004),
            ("Pivote Uno", "Pivote", 1999),
            ("Extremo Uno", "Extremo", 2002),
            ("Delantero Uno", "Delantero", 1990),
        ]
        for i, (name, pos, year) in enumerate(specs, start=1):
            Player.objects.create(
                team=self.team, name=name, position=pos, number=i,
                birth_date=datetime.date(year, 5, 10), is_active=True,
            )
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _get(self, query=""):
        return self.client.get(f"/coach/plantilla/informe/{query}", HTTP_HOST="localhost")

    def test_pretemporada_renders(self):
        resp = self._get("?phase=pretemporada")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("Cierre de plantilla", body)
        self.assertIn("Completar por líneas", body)
        self.assertIn("Tablero de decisiones", body)
        self.assertIn("Plantilla en el campo", body)  # el campo con avatares (pizarra reutilizada)
        self.assertIn("Sin valorar", body)  # jugadores sin evaluación cerrada quedan marcados
        self.assertIn("Descargar PDF", body)  # botón de descarga/impresión
        self.assertIn("C.D. Prueba", body)
        # La estructura por líneas debe pintar las 4 líneas objetivo.
        self.assertIn("Portería", body)
        self.assertIn("Ataque", body)

    def test_other_phase_renders(self):
        resp = self._get("?phase=liga")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("Semana de competición", body)

    def test_invalid_phase_falls_back(self):
        resp = self._get("?phase=zzz")
        self.assertEqual(resp.status_code, 200)

    def test_no_workspace_selected_is_handled(self):
        session = self.client.session
        session["active_workspace_id"] = 0
        session.save()
        resp = self._get("?phase=pretemporada")
        # Sin club seleccionado, responde con aviso controlado (no 500).
        self.assertIn(resp.status_code, (200, 400))
