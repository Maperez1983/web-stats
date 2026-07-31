"""
Portal del jugador · Fase 0 (cierre de fugas).

Cubre las cuatro cosas que se arreglan antes de rediseñar nada:
1. La vinculación usuario→jugador ya no adivina (ni auto-guarda) por parecido de nombre.
2. `/players/` (cuadro de mando de toda la plantilla) deja de ser accesible para un jugador.
3. La ficha no le enseña al jugador las comunicaciones internas ni el parte médico.
4. `next=/players/` no cuela por la puerta del login.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from football import views as football_views
from football.auth_views import _is_blocked_next_for_user
from football.models import (
    AppUserRole,
    Player,
    PlayerCommunication,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class PlayerLinkResolutionTests(TestCase):
    """La resolución sólo puede acertar con certeza, nunca por parecido."""

    def setUp(self):
        cache.clear()
        self.team = Team.objects.create(name="Equipo", slug="equipo", is_primary=True)

    def _player_user(self, username, **extra):
        user = get_user_model().objects.create_user(username=username, password="pass-1234", **extra)
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        return user

    def test_explicit_link_still_wins(self):
        player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        Player.objects.create(team=self.team, name="Sanchez", is_active=True)
        user = self._player_user("cualquiera")
        player.user = user
        player.save(update_fields=["user"])

        self.assertEqual(football_views._resolve_player_for_user(user, self.team).id, player.id)

    def test_single_active_player_is_not_handed_to_a_stranger(self):
        # Antes: con un único jugador activo, la función lo devolvía a CUALQUIER usuario.
        Player.objects.create(team=self.team, name="Ayala", is_active=True)
        user = self._player_user("persona.sin.relacion")

        self.assertIsNone(football_views._resolve_player_for_user(user, self.team))

    def test_partial_name_match_no_longer_resolves(self):
        # "Ángel" no basta para elegir entre "Ángel Ayala" y "Ángel Sánchez".
        Player.objects.create(team=self.team, name="Ayala", full_name="Angel Ayala", is_active=True)
        Player.objects.create(team=self.team, name="Sanchez", full_name="Angel Sanchez", is_active=True)
        user = self._player_user("angel", first_name="Angel")

        self.assertIsNone(football_views._resolve_player_for_user(user, self.team))

    def test_exact_unique_name_resolves_without_writing(self):
        player = Player.objects.create(team=self.team, name="Ayala", full_name="Angel Ayala", is_active=True)
        Player.objects.create(team=self.team, name="Sanchez", full_name="Angel Sanchez", is_active=True)
        user = self._player_user("angel.ayala", first_name="Angel", last_name="Ayala")

        self.assertEqual(football_views._resolve_player_for_user(user, self.team).id, player.id)
        # Y NO se auto-vincula: escribir el vínculo es decisión del staff.
        player.refresh_from_db()
        self.assertIsNone(player.user_id)

    def test_ambiguous_exact_match_resolves_to_nothing(self):
        # Dos hermanos, mismo nombre completo: nadie puede desempatar sin intervención humana.
        Player.objects.create(team=self.team, name="Ayala I", full_name="Angel Ayala", is_active=True)
        Player.objects.create(team=self.team, name="Ayala II", full_name="Angel Ayala", is_active=True)
        user = self._player_user("angel.ayala", first_name="Angel", last_name="Ayala")

        self.assertIsNone(football_views._resolve_player_for_user(user, self.team))


class PlayerSquadDashboardAccessTests(TestCase):
    """El portal es individual: el cuadro de mando de la plantilla no es su sitio."""

    def setUp(self):
        cache.clear()
        self.team = Team.objects.create(name="Equipo", slug="equipo", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_player_is_redirected_to_own_space(self):
        response = self.client.get(reverse("player-dashboard"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("player-home"))

    def test_staff_still_sees_it(self):
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        client = Client()
        client.force_login(staff)
        response = client.get(reverse("player-dashboard"), HTTP_HOST="localhost")
        self.assertNotEqual(response.status_code, 302)


class PlayerCommunicationsVisibilityTests(TestCase):
    """Notas internas y partes médicos no se le enseñan al jugador."""

    def setUp(self):
        cache.clear()
        self.team = Team.objects.create(name="Equipo", slug="equipo", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])

        # Un jugador real llega a su ficha con el equipo resuelto por su club (workspace).
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.team, user=self.user)

        self.convocation = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_CONVOCATION,
            message="Convocado, citación 16:15.",
        )
        self.internal = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_INTERNAL,
            message="No cuento con él, buscar salida en enero.",
        )
        self.medical = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_MEDICAL,
            message="Parte médico: rotura fibrilar grado 2.",
        )
        self.future = PlayerCommunication.objects.create(
            player=self.player,
            category=PlayerCommunication.CATEGORY_CONVOCATION,
            message="Convocatoria de la próxima jornada.",
            scheduled_for=timezone.now() + timezone.timedelta(days=7),
        )

    def _staff_client(self):
        """La ficha es del staff: lo que ve el jugador se comprueba por la previsualización."""
        staff = get_user_model().objects.create_superuser("preview", "p@example.com", "x")
        client = Client()
        client.force_login(staff)
        return client

    def _messages_for(self, client, preview=False):
        session = client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()
        url = reverse("player-detail", args=[self.player.id])
        if preview:
            url += "?preview=player"
        response = client.get(url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        return {item.message for item in response.context["communications"]}

    def test_player_only_sees_own_convocations_already_due(self):
        messages = self._messages_for(self._staff_client(), preview=True)

        self.assertIn(self.convocation.message, messages)
        self.assertNotIn(self.internal.message, messages)
        self.assertNotIn(self.medical.message, messages)
        self.assertNotIn(self.future.message, messages)

    def test_staff_still_sees_everything(self):
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        client = Client()
        client.force_login(staff)
        messages = self._messages_for(client)

        self.assertIn(self.internal.message, messages)
        self.assertIn(self.medical.message, messages)

    def test_club_assistant_widget_is_not_rendered_for_the_player(self):
        # El asistente contesta con datos del club y su endpoint le da 403: para el jugador
        # sólo era un botón roto ("¿quién está lesionado?").
        client = self._staff_client()
        session = client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()
        response = client.get(
            reverse("player-detail", args=[self.player.id]) + "?preview=player", HTTP_HOST="localhost"
        )
        self.assertNotContains(response, "global-guard-widget-shell")

    def test_staff_preview_of_player_view_is_faithful(self):
        staff = get_user_model().objects.create_superuser("mister2", "m2@example.com", "x")
        client = Client()
        client.force_login(staff)
        response = client.get(
            reverse("player-detail", args=[self.player.id]) + "?preview=player", HTTP_HOST="localhost"
        )
        messages = {item.message for item in response.context["communications"]}
        self.assertNotIn(self.internal.message, messages)


class PlayerLoginNextTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)

    def test_squad_dashboard_is_blocked_as_next(self):
        self.assertTrue(_is_blocked_next_for_user(self.user, "/players/"))
        self.assertTrue(_is_blocked_next_for_user(self.user, "/players"))

    def test_staff_ficha_is_blocked_as_next(self):
        # La ficha (y su PDF) son del cuerpo técnico; el jugador tiene su portal.
        self.assertTrue(_is_blocked_next_for_user(self.user, "/player/3/"))
        self.assertTrue(_is_blocked_next_for_user(self.user, "/player/3/pdf/"))

    def test_player_facing_subroutes_still_allowed(self):
        self.assertFalse(_is_blocked_next_for_user(self.user, "/players/videos/inbox/"))
        self.assertFalse(_is_blocked_next_for_user(self.user, "/player/3/lesiones/5/"))
