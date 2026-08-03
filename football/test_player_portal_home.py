"""
Portal del jugador · Fase 2 (el espacio propio + la vinculación por invitación).

1. `/mi-espacio/` deja de ser una landing con CSS inventado: usa el sistema visual, las
   piezas compartidas, y sus zonas obedecen a la política.
2. Invitar a un jugador exige decir a QUIÉN: el vínculo viaja en la invitación y se escribe
   al aceptarla, en vez de adivinarse después por parecido de nombre.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from football import player_portal_policy as policy
from football.models import (
    AppUserRole,
    Competition,
    Match,
    MatchEvent,
    Player,
    PlayerFine,
    PlayerObjective,
    PlayerMatchReportArchive,
    PlayerPortalPolicy,
    PlayerStatistic,
    Season,
    Team,
    UserInvitation,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class PlayerHomeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", number=4, is_active=True)
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.team, user=self.user)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def _home(self):
        return self.client.get(reverse("player-home"), HTTP_HOST="localhost")

    def test_uses_the_shared_visual_system(self):
        response = self._home()
        self.assertEqual(response.status_code, 200)
        # Hojas del sistema y clase de producto: antes esta página se lo inventaba todo.
        self.assertContains(response, "product_system.css")
        self.assertContains(response, "commercial.css")
        self.assertContains(response, 'class="prod-commercial"')

    def test_shows_the_player_identity(self):
        response = self._home()
        self.assertContains(response, "Ayala")
        self.assertContains(response, "Senior")

    def test_zones_follow_the_policy(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace,
            team=None,
            sections={"fines": policy.HIDDEN, "performance": policy.HIDDEN},
        )
        PlayerFine.objects.create(player=self.player, reason=PlayerFine.REASON_LATE, amount=5, note="Tarde")
        response = self._home()
        self.assertNotContains(response, "Tarde")
        self.assertNotContains(response, "Mi rendimiento")
        # Lo que sigue abierto se pinta.
        self.assertContains(response, "Mi cuerpo")

    def test_objectives_respect_the_policy(self):
        PlayerObjective.objects.create(player=self.player, text="Mejorar la salida de balón")
        self.assertContains(self._home(), "Mejorar la salida de balón")

        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"objectives": policy.HIDDEN}
        )
        cache.clear()
        self.assertNotContains(self._home(), "Mejorar la salida de balón")

    def test_unlinked_account_gets_an_explanation_not_an_error(self):
        stranger = get_user_model().objects.create_user(username="nadie", password="pass-1234")
        AppUserRole.objects.create(user=stranger, role=AppUserRole.ROLE_PLAYER)
        client = Client()
        client.force_login(stranger)
        response = client.get(reverse("player-home"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no está vinculada")

    def test_agenda_is_visible_and_only_closed_attendance_counts(self):
        from datetime import timedelta

        from django.utils import timezone

        from football.models import TrainingMicrocycle, TrainingSession, TrainingSessionAttendance

        today = timezone.localdate()
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title="Semana",
            week_start=today - timedelta(days=today.weekday()),
            week_end=today - timedelta(days=today.weekday()) + timedelta(days=6),
        )
        planned = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today,
            focus="Presión y cobertura",
            status=TrainingSession.STATUS_PLANNED,
        )
        TrainingSessionAttendance.objects.create(
            session=planned,
            player=self.player,
            status=TrainingSessionAttendance.STATUS_PRESENT,
        )

        response = self._home()

        self.assertContains(response, "Mi agenda")
        self.assertContains(response, "Presión y cobertura")
        self.assertEqual(response.context["training_marker"]["sessions_total"], 0)
        self.assertEqual(response.context["training_marker"]["sessions_attended"], 0)
        self.assertNotContains(response, reverse("player-attendance-mark"))

    def test_closed_match_generates_player_report_entry_and_calendar_link(self):
        competition = Competition.objects.create(name="Liga portal", slug="liga-portal", region="Malaga")
        season = Season.objects.create(competition=competition, name="2026/27 portal")
        rival = Team.objects.create(name="Rival portal", slug="rival-portal")
        match = Match.objects.create(
            season=season,
            home_team=self.team,
            away_team=rival,
            date=timezone.localdate(),
            home_score=2,
            away_score=2,
            is_closed=True,
            stats_source=Match.STATS_SOURCE_MANUAL,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=season,
            match=match,
            name="rating",
            value=6.3,
            context="auto-rating",
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=season,
            match=match,
            name="manual_minutes",
            value=45,
            context="manual-match",
        )
        for result in ("OK", "ERROR"):
            MatchEvent.objects.create(
                match=match,
                player=self.player,
                minute=12,
                event_type="Pase",
                result=result,
                source_file="manual-recovery",
                system="touch-field-final",
            )

        response = self._home()
        report_url = reverse("player-match-stats", args=[self.player.id, match.id])

        self.assertContains(response, "Mis informes de partido")
        self.assertContains(response, "Rival portal")
        self.assertContains(response, "2 - 2")
        self.assertContains(response, report_url)
        self.assertContains(response, reverse("player-match-report-pdf", args=[self.player.id, match.id]))
        self.assertContains(response, "Último partido")
        self.assertEqual(response.context["latest_match_report"]["rating"], 6.3)
        self.assertContains(response, "45 minutos")
        self.assertContains(response, "Pases")
        self.assertContains(response, "50%")

        report_response = self.client.get(report_url, HTTP_HOST="localhost")
        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, "Lo que aportaste")
        self.assertNotContains(report_response, "Precisión de pase")

    def test_open_match_does_not_create_a_personal_report(self):
        competition = Competition.objects.create(name="Liga abierta", slug="liga-abierta", region="Malaga")
        season = Season.objects.create(competition=competition, name="2026/27 abierta")
        rival = Team.objects.create(name="Rival sin cerrar", slug="rival-sin-cerrar")
        match = Match.objects.create(
            season=season,
            home_team=self.team,
            away_team=rival,
            date=timezone.localdate(),
            is_closed=False,
        )
        PlayerStatistic.objects.create(
            player=self.player,
            season=season,
            match=match,
            name="rating",
            value=7.1,
            context="auto-rating",
        )

        response = self._home()

        self.assertEqual(response.context["match_reports"], [])
        self.assertIsNone(response.context["latest_match_report"])

    def test_pdf_download_serves_the_archived_version(self):
        competition = Competition.objects.create(name="Liga PDF", slug="liga-pdf", region="Malaga")
        season = Season.objects.create(competition=competition, name="2026/27 PDF")
        rival = Team.objects.create(name="Rival PDF", slug="rival-pdf")
        match = Match.objects.create(
            season=season,
            home_team=self.team,
            away_team=rival,
            date=timezone.localdate(),
            is_closed=True,
        )
        archive = PlayerMatchReportArchive.objects.create(
            player=self.player,
            match=match,
            version=1,
            status=PlayerMatchReportArchive.STATUS_READY,
            rating=6.4,
            snapshot={"rating": 6.4, "minutes": 45},
        )
        archive.pdf.save("archived-report.pdf", ContentFile(b"%PDF-archived-version"))

        response = self.client.get(
            reverse("player-match-report-pdf", args=[self.player.id, match.id]) + "?download=1",
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-archived-version")
        self.assertIn("v1.pdf", response.headers["Content-Disposition"])


class FichaIsClosedToThePlayerTests(TestCase):
    """La ficha es la herramienta del staff; el jugador tiene su portal."""

    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.team, user=self.user)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_ficha_sends_the_player_to_the_portal(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("player-home"))

    def test_pdf_is_not_the_back_door(self):
        # El PDF es la ficha entera impresa: notas internas, parte médico, valoraciones sin publicar.
        response = self.client.get(reverse("player-pdf", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("player-home"))

    def test_staff_still_opens_the_ficha(self):
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        client = Client()
        client.force_login(staff)
        response = client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)


class PortalPreviewTests(TestCase):
    """'Ver como jugador': el club puede comprobar qué recibe cada uno."""

    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        PlayerObjective.objects.create(player=self.player, text="Trabajar el perfil malo")
        self.staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace.owner_user = self.staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(self.staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_staff_sees_the_portal_of_a_player(self):
        response = self.client.get(
            reverse("player-home") + f"?ver_como={self.player.id}", HTTP_HOST="localhost"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trabajar el perfil malo")
        self.assertContains(response, "lo que ve Ayala")

    def test_preview_is_read_only(self):
        response = self.client.get(
            reverse("player-home") + f"?ver_como={self.player.id}", HTTP_HOST="localhost"
        )
        self.assertNotContains(response, reverse("player-attendance-mark"))

    def test_a_player_cannot_preview_anyone(self):
        user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        other = Player.objects.create(team=self.team, name="Jairo", is_active=True)
        client = Client()
        client.force_login(user)
        response = client.get(reverse("player-home") + f"?ver_como={other.id}", HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Jairo")

    def test_staff_cannot_preview_another_club(self):
        other_team = Team.objects.create(name="Otro club", slug="otro")
        outsider = Player.objects.create(team=other_team, name="Ajeno", is_active=True)
        response = self.client.get(
            reverse("player-home") + f"?ver_como={outsider.id}", HTTP_HOST="localhost"
        )
        self.assertNotContains(response, "Ajeno")


class VideoPagesBelongToTheSystemTests(TestCase):
    """Tenían los colores del sistema pero ninguna estructura: el jugador se quedaba sin navegación."""

    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.team, user=self.user)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_video_inbox_has_a_way_back(self):
        response = self.client.get(reverse("player-video-inbox"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("player-home"))


class InvitationLinksThePlayerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        self.owner = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace.owner_user = self.owner
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def test_inviting_a_player_requires_choosing_one(self):
        response = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "role_preset": "jugador", "email": "ayala@example.com"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elige a qué jugador")
        self.assertFalse(UserInvitation.objects.exists())

    def test_invitation_carries_the_player(self):
        self.client.post(
            reverse("workspace-members"),
            {
                "action": "invite",
                "role_preset": "jugador",
                "email": "ayala@example.com",
                "player_id": self.player.id,
            },
            HTTP_HOST="localhost",
        )
        invitation = UserInvitation.objects.get()
        self.assertEqual(invitation.player_id, self.player.id)
        # Todavía NO se ha escrito el vínculo: se escribe al aceptar.
        self.player.refresh_from_db()
        self.assertIsNone(self.player.user_id)

    def test_accepting_writes_the_link(self):
        invited = get_user_model().objects.create_user(
            username="ayala", email="ayala@example.com", password=None, is_active=False
        )
        invitation = UserInvitation.objects.create(
            user=invited,
            player=self.player,
            token=UserInvitation.generate_token(),
            email="ayala@example.com",
            expires_at=timezone.now() + timedelta(days=7),
            is_active=True,
        )
        client = Client()
        client.post(
            reverse("user-invite-accept", args=[invitation.token]),
            {"password": "una-clave-larga-1", "password_confirm": "una-clave-larga-1"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.user_id, invited.id)

    def test_a_taken_player_cannot_be_invited_twice(self):
        other = get_user_model().objects.create_user(username="otro", password="pass-1234")
        self.player.user = other
        self.player.save(update_fields=["user"])
        response = self.client.post(
            reverse("workspace-members"),
            {
                "action": "invite",
                "role_preset": "jugador",
                "email": "ayala@example.com",
                "player_id": self.player.id,
            },
            HTTP_HOST="localhost",
        )
        self.assertContains(response, "ya tiene una cuenta vinculada")
        self.assertFalse(UserInvitation.objects.exists())


class TeamPagePortalConfigTests(TestCase):
    """La regla de cada categoría se toca en la ficha de SU equipo."""

    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace = Workspace.objects.create(
            name="C.D. Prueba", kind=Workspace.KIND_CLUB, is_active=True, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Cadete", slug="cadete", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Nano", is_active=True)
        self.client = Client()
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_team_page_shows_the_portal_block(self):
        response = self.client.get(reverse("team-page"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal del jugador")
        self.assertContains(response, "sigue la regla del club")

    def test_saving_from_the_team_page_creates_its_own_rule(self):
        from football import player_portal_policy as policy
        from football.models import PlayerPortalPolicy

        self.client.post(
            reverse("team-page"),
            {"form_action": "player_portal", "section__fines": policy.HIDDEN},
            HTTP_HOST="localhost",
        )
        self.assertTrue(PlayerPortalPolicy.objects.filter(workspace=self.workspace, team=self.team).exists())
        self.assertEqual(
            policy.player_portal_visibility(self.player, workspace=self.workspace)["fines"], policy.HIDDEN
        )

    def test_matching_the_club_removes_the_own_rule(self):
        # Sin diferencias no se deja una fila vacía colgando: vuelve a seguir al club.
        from football import player_portal_policy as policy
        from football.models import PlayerPortalPolicy

        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=self.team, sections={"fines": policy.HIDDEN}
        )
        self.client.post(
            reverse("team-page"),
            {"form_action": "player_portal", "section__fines": policy.VISIBLE},
            HTTP_HOST="localhost",
        )
        self.assertFalse(PlayerPortalPolicy.objects.filter(workspace=self.workspace, team=self.team).exists())

    def test_ficha_embeds_the_portal_preview(self):
        # Lo que se previsualiza es SU PORTAL, no esta ficha: el jugador ya no entra aquí.
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, "Vista previa de su portal")
        self.assertContains(response, 'id="portal-preview"')
        self.assertContains(response, f"?ver_como={self.player.id}")

    def test_the_preview_is_not_offered_to_a_player(self):
        user = get_user_model().objects.create_user(username="nano", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = user
        self.player.save(update_fields=["user"])
        client = Client()
        client.force_login(user)
        response = client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        # Ni siquiera abre la ficha: va a su portal.
        self.assertEqual(response.status_code, 302)
