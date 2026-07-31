"""
Portal del jugador · Fase 1 (política de visibilidad).

Lo que se comprueba aquí:
1. El resolver de tres capas (defaults -> política del club -> excepción del jugador).
2. Que un JSON roto o inventado NO abre nada: ante la duda, cerrado.
3. Que la ficha obedece la política (pestañas y contenido).
4. Que cerrar una evaluación NO se la enseña al jugador: hay que publicarla a propósito,
   ni por la ficha ni por el informe.
5. Que el jugador no ve percentiles (su posición relativa dentro de la plantilla).
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from football import player_portal_policy as policy
from football.models import (
    AppUserRole,
    Player,
    PlayerEvaluation,
    PlayerPortalPolicy,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class PortalPolicyResolutionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)

    def test_defaults_close_what_is_sensitive(self):
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["evaluation"], policy.PUBLISHED_ONLY)
        self.assertEqual(sections["communication"], policy.PUBLISHED_ONLY)
        self.assertEqual(sections["documents"], policy.HIDDEN)
        self.assertEqual(sections["performance"], policy.VISIBLE)

    def test_club_policy_overrides_defaults(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"performance": policy.HIDDEN}
        )
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["performance"], policy.HIDDEN)
        # Lo que no se toca sigue en su valor por defecto.
        self.assertEqual(sections["injuries"], policy.VISIBLE)

    def test_team_policy_overrides_club_policy(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"injuries": policy.HIDDEN}
        )
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=self.team, sections={"injuries": policy.VISIBLE}
        )
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["injuries"], policy.VISIBLE)

    def test_player_override_beats_everything(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"fines": policy.VISIBLE}
        )
        self.player.portal_overrides = {"fines": policy.HIDDEN}
        self.player.save(update_fields=["portal_overrides"])
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["fines"], policy.HIDDEN)

    def test_garbage_never_opens_anything(self):
        # Claves inventadas, estados inventados, tipo equivocado: todo se ignora y manda el
        # valor de abajo. Una política ilegible no puede convertirse en una fuga.
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace,
            team=None,
            sections={"inventada": "visible", "documents": "abierto-del-todo", "fines": None},
        )
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["documents"], policy.HIDDEN)
        self.assertEqual(sections["fines"], policy.VISIBLE)
        self.assertNotIn("inventada", sections)

    def test_impossible_state_for_a_section_is_refused(self):
        # "visible" en evaluación significaría enseñar valoraciones sin publicar.
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"evaluation": policy.VISIBLE}
        )
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["evaluation"], policy.PUBLISHED_ONLY)

    def test_staff_view_is_never_restricted(self):
        vis = policy.visibility_for_request(self.player, workspace=self.workspace, is_player_view=False)
        self.assertTrue(vis.unrestricted)
        self.assertTrue(vis.documents)  # oculta para el jugador, visible para el staff

    def test_template_helper_answers(self):
        vis = policy.visibility_for_request(self.player, workspace=self.workspace, is_player_view=True)
        self.assertTrue(vis.evaluation)             # la sección se pinta…
        self.assertTrue(vis.evaluation_published)   # …pero sólo lo publicado
        self.assertFalse(vis.evaluation_full)
        self.assertFalse(vis.documents)


class PortalPolicyFichaTests(TestCase):
    """La ficha obedece la política."""

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
        # La ficha ya no la abre el jugador: lo que recibe se comprueba por la
        # previsualización del staff, que está hecha para ser fiel.
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def _get_ficha(self):
        return self.client.get(
            reverse("player-detail", args=[self.player.id]) + "?preview=player", HTTP_HOST="localhost"
        )

    def test_hidden_section_drops_tab_and_content(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=None, sections={"injuries": policy.HIDDEN}
        )
        response = self._get_ficha()
        self.assertEqual(response.status_code, 200)
        # Ni la pestaña ni el panel: esconder sólo el botón dejaría el dato en el HTML.
        self.assertNotContains(response, 'data-tab="injuries"')
        self.assertNotContains(response, 'data-pane="injuries"')

    def test_visible_section_is_rendered(self):
        response = self._get_ficha()
        self.assertContains(response, 'data-tab="injuries"')
        self.assertContains(response, 'data-pane="injuries"')

    def test_player_never_sees_squad_percentiles(self):
        # El portal es individual: un percentil es su posición dentro del vestuario.
        response = self._get_ficha()
        self.assertEqual(response.context["player_percentiles"], {})


class EvaluationPublishTests(TestCase):
    """Cerrada no es publicada."""

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

        self.evaluation = PlayerEvaluation.objects.create(
            team=self.team,
            player=self.player,
            status=PlayerEvaluation.STATUS_CLOSED,
            evaluated_on=timezone.localdate(),
            overall_rating=7,
        )

        self.client = Client()
        self.client.force_login(self.user)
        # Para mirar la ficha con los ojos del jugador (que ya no puede abrirla) se usa la
        # previsualización del staff.
        self.preview = Client()
        self.preview.force_login(get_user_model().objects.create_superuser("ojos", "o@example.com", "x"))
        for client in (self.client, self.preview):
            session = client.session
            session["active_workspace_id"] = self.workspace.id
            session["active_team_id"] = self.team.id
            session.save()

    def _ficha(self):
        return reverse("player-detail", args=[self.player.id]) + "?preview=player"

    def test_closed_but_unpublished_is_invisible_to_the_player(self):
        response = self.preview.get(self._ficha(), HTTP_HOST="localhost")
        self.assertEqual(list(response.context["player_evaluations"]), [])
        # Y tampoco se filtra por lo derivado (la chapa de media sale de aquí).
        self.assertIsNone(response.context["evaluation_summary"]["latest"])

    def test_report_url_is_not_the_back_door(self):
        response = self.client.get(
            reverse("player-evaluation-report", args=[self.player.id, self.evaluation.id]),
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 403)

    def test_published_evaluation_reaches_the_player(self):
        self.evaluation.published_to_player = True
        self.evaluation.save(update_fields=["published_to_player"])

        response = self.preview.get(self._ficha(), HTTP_HOST="localhost")
        self.assertEqual([e.id for e in response.context["player_evaluations"]], [self.evaluation.id])

        report = self.client.get(
            reverse("player-evaluation-report", args=[self.player.id, self.evaluation.id]),
            HTTP_HOST="localhost",
        )
        self.assertEqual(report.status_code, 200)

    def test_staff_publishes_and_retires(self):
        staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        client = Client()
        client.force_login(staff)
        url = reverse("player-detail", args=[self.player.id])

        client.post(
            url,
            {"form_action": "evaluation_publish", "evaluation_id": self.evaluation.id, "publish": "1"},
            HTTP_HOST="localhost",
        )
        self.evaluation.refresh_from_db()
        self.assertTrue(self.evaluation.published_to_player)
        self.assertIsNotNone(self.evaluation.published_to_player_at)
        self.assertEqual(self.evaluation.published_to_player_by_id, staff.id)

        client.post(
            url,
            {"form_action": "evaluation_publish", "evaluation_id": self.evaluation.id, "publish": "0"},
            HTTP_HOST="localhost",
        )
        self.evaluation.refresh_from_db()
        self.assertFalse(self.evaluation.published_to_player)
        self.assertIsNone(self.evaluation.published_to_player_at)

    def test_coach_comments_are_a_second_key(self):
        # Publicar la valoración no publica lo que el entrenador escribió sobre ella: eso se
        # marca aparte al publicar.
        self.evaluation.coach_comments = "Hablar con él del cambio de posición."
        self.evaluation.save(update_fields=["coach_comments"])
        staff = get_user_model().objects.create_superuser("mister3", "m3@example.com", "x")
        staff_client = Client()
        staff_client.force_login(staff)
        url = reverse("player-detail", args=[self.player.id])
        ficha = self._ficha()
        informe = reverse("player-evaluation-report", args=[self.player.id, self.evaluation.id])

        # Publicada SIN comentarios.
        staff_client.post(
            url,
            {"form_action": "evaluation_publish", "evaluation_id": self.evaluation.id, "publish": "1"},
            HTTP_HOST="localhost",
        )
        self.evaluation.refresh_from_db()
        self.assertTrue(self.evaluation.published_to_player)
        self.assertFalse(self.evaluation.published_comments_to_player)
        self.assertNotContains(self.preview.get(ficha, HTTP_HOST="localhost"), self.evaluation.coach_comments)
        self.assertNotContains(self.client.get(informe, HTTP_HOST="localhost"), self.evaluation.coach_comments)

        # Publicada CON comentarios.
        staff_client.post(
            url,
            {
                "form_action": "evaluation_publish",
                "evaluation_id": self.evaluation.id,
                "publish": "1",
                "publish_comments": "1",
            },
            HTTP_HOST="localhost",
        )
        self.evaluation.refresh_from_db()
        self.assertTrue(self.evaluation.published_comments_to_player)
        self.assertContains(self.preview.get(ficha, HTTP_HOST="localhost"), self.evaluation.coach_comments)
        self.assertContains(self.client.get(informe, HTTP_HOST="localhost"), self.evaluation.coach_comments)

    def test_retiring_closes_both_keys(self):
        self.evaluation.coach_comments = "Nota interna."
        self.evaluation.published_to_player = True
        self.evaluation.published_comments_to_player = True
        self.evaluation.save()
        staff = get_user_model().objects.create_superuser("mister4", "m4@example.com", "x")
        client = Client()
        client.force_login(staff)
        client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "evaluation_publish", "evaluation_id": self.evaluation.id, "publish": "0"},
            HTTP_HOST="localhost",
        )
        self.evaluation.refresh_from_db()
        self.assertFalse(self.evaluation.published_to_player)
        self.assertFalse(self.evaluation.published_comments_to_player)

    def test_a_draft_cannot_be_published(self):
        draft = PlayerEvaluation.objects.create(
            team=self.team,
            player=self.player,
            status=PlayerEvaluation.STATUS_DRAFT,
            evaluated_on=timezone.localdate(),
        )
        staff = get_user_model().objects.create_superuser("mister2", "m2@example.com", "x")
        client = Client()
        client.force_login(staff)
        client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "evaluation_publish", "evaluation_id": draft.id, "publish": "1"},
            HTTP_HOST="localhost",
        )
        draft.refresh_from_db()
        self.assertFalse(draft.published_to_player)
