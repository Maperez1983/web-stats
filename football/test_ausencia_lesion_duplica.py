"""Marcar a un jugador ausente por lesión no puede crearle una lesión que ya tiene."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import (
    AppUserRole,
    TrainingMicrocycle,
    Competition,
    Group,
    Player,
    PlayerInjuryRecord,
    Season,
    Team,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
)


class AusenciaPorLesionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mister", email="mister@example.com", password="pass-1234"
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        competition = Competition.objects.create(name="Liga Lesiones", slug="liga-lesiones", region="Andalucia")
        season = Season.objects.create(competition=competition, name="2026/2027", is_current=True)
        group = Group.objects.create(season=season, name="Grupo L", slug="grupo-l")
        self.team = Team.objects.create(name="Benagalbón L", slug="benagalbon-l", group=group, is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Benagalbón L",
            slug="benagalbon-l-ws",
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            enabled_modules={"dashboard": True, "sessions": True, "injuries": True},
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_ADMIN
        )
        self.player = Player.objects.create(team=self.team, name="Cojo", number=7, position="MC")
        self.client.force_login(self.user)

    def _lesion_previa(self, dias_atras=3, etiqueta="Sobrecarga isquios"):
        return PlayerInjuryRecord.objects.create(
            player=self.player,
            injury=etiqueta,
            injury_date=date.today() - timedelta(days=dias_atras),
            is_active=True,
        )

    def _sesion(self, cuando=None):
        cuando = cuando or date.today()
        ciclo, _ = TrainingMicrocycle.objects.get_or_create(
            team=self.team,
            week_start=cuando - timedelta(days=cuando.weekday()),
            defaults={"week_end": cuando + timedelta(days=6 - cuando.weekday())},
        )
        return TrainingSession.objects.create(
            microcycle=ciclo, session_date=cuando, focus="Entrenamiento"
        )

    def test_una_lesion_activa_previa_no_debe_duplicarse_al_marcar_ausencia(self):
        """El caso real: se lesionó el lunes y el jueves sigue de baja."""
        previa = self._lesion_previa(dias_atras=3)
        sesion = self._sesion()

        self.client.post(
            reverse("training-session-detail", args=[sesion.id]),
            {
                "action": "attendance",
                f"attendance_status_{self.player.id}": "injured",
                f"attendance_injury_{self.player.id}": "Sobrecarga isquios",
            },
        )

        activas = PlayerInjuryRecord.objects.filter(player=self.player, is_active=True)
        self.assertEqual(
            activas.count(),
            1,
            "el jugador ya estaba lesionado: marcarle ausente no puede abrirle otra lesión "
            f"(hay {activas.count()}: {list(activas.values_list('injury', 'injury_date'))})",
        )
        self.assertEqual(activas.first().id, previa.id)

    def test_sin_lesion_previa_si_se_crea_el_parte(self):
        sesion = self._sesion()
        self.client.post(
            reverse("training-session-detail", args=[sesion.id]),
            {
                "action": "attendance",
                f"attendance_status_{self.player.id}": "injured",
                f"attendance_injury_{self.player.id}": "Sobrecarga isquios",
            },
        )
        self.assertLessEqual(
            PlayerInjuryRecord.objects.filter(player=self.player, is_active=True).count(),
            1,
        )

    def test_una_sesion_futura_no_puede_abrir_una_lesion_con_fecha_futura(self):
        """La app pre-marca como lesionado en las sesiones que vienen: el parte no puede nacer
        fechado dentro de un mes."""
        futura = self._sesion(cuando=date.today() + timedelta(days=40))
        self.client.post(
            reverse("training-session-detail", args=[futura.id]),
            {
                "action": "attendance",
                f"attendance_status_{self.player.id}": "injured",
                f"attendance_injury_{self.player.id}": "Sobrecarga isquios",
            },
        )
        for parte in PlayerInjuryRecord.objects.filter(player=self.player):
            self.assertLessEqual(
                parte.injury_date, date.today(), "una lesión no puede empezar en el futuro"
            )
