from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Player,
    PlayerPhysicalMetric,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class WellnessDesdeElPortalTests(TestCase):
    """La política decía que buena parte del físico la rellena él; ahora tiene dónde."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno10", password="x")
        self.workspace = Workspace.objects.create(
            name="Club wellness", slug="club-wellness", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Cadete well", slug="cadete-well")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.jugador_user = User.objects.create_user(username="jugador10", password="x")
        self.player = Player.objects.create(
            name="Jugador Well", team=self.team, is_active=True, user=self.jugador_user
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.jugador_user, role=WorkspaceMembership.ROLE_VIEWER
        )
        self.client.force_login(self.jugador_user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def test_el_portal_ofrece_el_parte_del_dia(self):
        resp = self.client.get(reverse("player-home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "¿Cómo estás hoy?")

    def test_guarda_el_parte_del_dia(self):
        self.client.post(
            reverse("player-home"),
            {
                "form_action": "wellness",
                "wellness": "7",
                "wellness_sleep": "6",
                "wellness_soreness": "3",
                "rpe": "8",
            },
            follow=True,
        )

        registro = PlayerPhysicalMetric.objects.get(player=self.player, recorded_on=timezone.localdate())
        self.assertEqual(registro.wellness, 7)
        self.assertEqual(registro.wellness_sleep, 6)
        self.assertEqual(registro.wellness_soreness, 3)
        self.assertEqual(registro.rpe, 8)

    def test_un_parte_por_dia_se_corrige_no_se_duplica(self):
        for valor in ("5", "9"):
            self.client.post(
                reverse("player-home"), {"form_action": "wellness", "wellness": valor}, follow=True
            )

        registros = PlayerPhysicalMetric.objects.filter(
            player=self.player, recorded_on=timezone.localdate()
        )
        self.assertEqual(registros.count(), 1)
        self.assertEqual(registros.first().wellness, 9)

    def test_fuera_de_rango_se_recorta_y_lo_vacio_no_escribe(self):
        self.client.post(
            reverse("player-home"),
            {"form_action": "wellness", "wellness": "99", "wellness_sleep": "", "rpe": "0"},
            follow=True,
        )

        registro = PlayerPhysicalMetric.objects.get(player=self.player, recorded_on=timezone.localdate())
        self.assertEqual(registro.wellness, 10)
        self.assertIsNone(registro.wellness_sleep)
        self.assertEqual(registro.rpe, 1)

    def test_la_familia_si_puede_rellenar_como_esta(self):
        self.player.user_is_guardian = True
        self.player.save(update_fields=["user_is_guardian"])

        self.client.post(
            reverse("player-home"), {"form_action": "wellness", "wellness": "4"}, follow=True
        )

        registro = PlayerPhysicalMetric.objects.get(player=self.player, recorded_on=timezone.localdate())
        self.assertEqual(registro.wellness, 4)


class TarjetaCompartidaTests(TestCase):
    """La tarjeta de próxima sesión es la misma pieza en la ficha y en el portal."""

    def setUp(self):
        cache.clear()
        from datetime import date

        from .models import TrainingMicrocycle, TrainingSession

        self.owner = User.objects.create_user(username="dueno11", password="x")
        self.workspace = Workspace.objects.create(
            name="Club tarjeta", slug="club-tarjeta", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Senior tarjeta", slug="senior-tarjeta")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.jugador_user = User.objects.create_user(username="jugador11", password="x")
        self.player = Player.objects.create(
            name="Jugador Tarjeta", team=self.team, is_active=True, user=self.jugador_user
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.jugador_user, role=WorkspaceMembership.ROLE_VIEWER
        )
        micro = TrainingMicrocycle.objects.create(
            team=self.team, week_start=date(2026, 7, 27), week_end=date(2026, 8, 2)
        )
        TrainingSession.objects.create(microcycle=micro, session_date=date(2026, 7, 30))

    def test_la_ficha_del_entrenador_pinta_la_tarjeta(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

        resp = self.client.get(reverse("player-detail", args=[self.player.id]))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Próxima sesión")

    def test_el_portal_pinta_la_misma_tarjeta(self):
        self.client.force_login(self.jugador_user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

        resp = self.client.get(reverse("player-home"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "today-card")
