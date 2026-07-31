"""
Portal del jugador · Fase 4 (el panel del club).

Sin esta pantalla la política existía pero sólo se podía tocar desde una shell — o sea que de
hecho no se podía tocar y mandaban los valores por defecto del código. Aquí se comprueba que
el dueño del club decide, y que la decisión llega de verdad al portal.

El club real de referencia (C.D. Benagalbón) tiene SIETE equipos, del primer equipo al bebé,
así que la regla por categoría no es un adorno: se prueba con varios equipos.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from football import player_portal_policy as policy
from football.models import (
    AppUserRole,
    Player,
    PlayerPortalPolicy,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class PortalSettingsPanelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user(username="mister", password="pass-1234")
        self.workspace = Workspace.objects.create(
            name="C.D. Prueba", kind=Workspace.KIND_CLUB, is_active=True, owner_user=self.owner
        )
        self.senior = Team.objects.create(name="Primer equipo", slug="senior", is_primary=True)
        self.cadete = Team.objects.create(name="Cadete", slug="cadete")
        for team in (self.senior, self.cadete):
            WorkspaceTeam.objects.create(workspace=self.workspace, team=team)
        self.player = Player.objects.create(team=self.senior, name="Ayala", is_active=True)
        self.kid = Player.objects.create(team=self.cadete, name="Nano", is_active=True)

        self.client = Client()
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.senior.id
        session.save()

    def _url(self, team=None):
        url = reverse("player-portal-settings")
        return f"{url}?equipo={team.id}" if team else url

    def test_panel_lists_every_section_and_team(self):
        response = self.client.get(self._url(), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        for section in policy.SECTIONS:
            self.assertContains(response, section["label"])
        self.assertContains(response, "Primer equipo")
        self.assertContains(response, "Cadete")

    def test_saving_the_club_rule_reaches_the_player(self):
        self.client.post(
            self._url(),
            {"action": "save", "section__fines": policy.HIDDEN},
            HTTP_HOST="localhost",
        )
        sections = policy.player_portal_visibility(self.player, workspace=self.workspace)
        self.assertEqual(sections["fines"], policy.HIDDEN)

    def test_only_the_difference_is_stored(self):
        # Guardar no debe congelar los diez valores: lo que no cambias sigue el valor por
        # defecto, así que cambiar un default más adelante no deja clubes anclados al viejo.
        self.client.post(
            self._url(),
            {"action": "save", "section__fines": policy.HIDDEN, "section__injuries": policy.VISIBLE},
            HTTP_HOST="localhost",
        )
        row = PlayerPortalPolicy.objects.get(workspace=self.workspace, team__isnull=True)
        self.assertEqual(row.sections, {"fines": policy.HIDDEN})

    def test_a_category_rule_beats_the_club_rule(self):
        self.client.post(
            self._url(), {"action": "save", "section__performance": policy.HIDDEN}, HTTP_HOST="localhost"
        )
        self.client.post(
            self._url(self.cadete),
            {"action": "save", "team_id": self.cadete.id, "section__performance": policy.VISIBLE},
            HTTP_HOST="localhost",
        )
        self.assertEqual(
            policy.player_portal_visibility(self.player, workspace=self.workspace)["performance"],
            policy.HIDDEN,
        )
        self.assertEqual(
            policy.player_portal_visibility(self.kid, workspace=self.workspace)["performance"],
            policy.VISIBLE,
        )

    def test_category_can_go_back_to_the_club_rule(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=self.cadete, sections={"fines": policy.HIDDEN}
        )
        self.client.post(
            self._url(self.cadete), {"action": "reset", "team_id": self.cadete.id}, HTTP_HOST="localhost"
        )
        self.assertFalse(PlayerPortalPolicy.objects.filter(workspace=self.workspace, team=self.cadete).exists())
        self.assertEqual(
            policy.player_portal_visibility(self.kid, workspace=self.workspace)["fines"], policy.VISIBLE
        )

    def test_panel_shows_what_each_category_changes(self):
        PlayerPortalPolicy.objects.create(
            workspace=self.workspace, team=self.cadete, sections={"fines": policy.HIDDEN}
        )
        response = self.client.get(self._url(), HTTP_HOST="localhost")
        self.assertContains(response, "1 cambio respecto al club")
        self.assertContains(response, "Igual que el club")

    def test_an_impossible_state_is_refused(self):
        # "visible" en evaluación significaría enseñar valoraciones sin publicar.
        self.client.post(
            self._url(), {"action": "save", "section__evaluation": policy.VISIBLE}, HTTP_HOST="localhost"
        )
        self.assertEqual(
            policy.player_portal_visibility(self.player, workspace=self.workspace)["evaluation"],
            policy.PUBLISHED_ONLY,
        )

    def test_a_team_from_another_club_is_refused(self):
        outsider = Team.objects.create(name="Ajeno", slug="ajeno")
        self.client.post(
            self._url(),
            {"action": "save", "team_id": outsider.id, "section__fines": policy.HIDDEN},
            HTTP_HOST="localhost",
        )
        self.assertFalse(PlayerPortalPolicy.objects.filter(team=outsider).exists())

    def test_squad_shows_who_has_an_account(self):
        user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = user
        self.player.save(update_fields=["user"])
        response = self.client.get(self._url(), HTTP_HOST="localhost")
        self.assertContains(response, "vinculado")
        self.assertContains(response, "sin cuenta")

    def test_a_player_cannot_open_the_panel(self):
        user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=user, role=WorkspaceMembership.ROLE_VIEWER
        )
        client = Client()
        client.force_login(user)
        session = client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()
        response = client.get(reverse("player-portal-settings"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 403)


class TemplateCommentsAreRealCommentsTests(TestCase):
    """
    Django sólo admite `{# #}` en UNA línea: partido en varias es texto, no comentario.

    Pasó de verdad y llegó a producción: los comentarios que escribí en `pwa_head.html` y
    `dragon_nav.html` —que carga toda la app— se imprimieron como texto visible en la
    cabecera de TODAS las páginas. No lo vio ningún test porque ninguno miraba la página
    renderizada buscando basura; sólo se vio al abrir la app de verdad.
    """

    def test_no_multiline_hash_comments_in_templates(self):
        import glob
        import re

        from django.conf import settings

        pattern = re.compile(r"\{#(.*?)#\}", re.S)
        offenders = []
        for base in [str(p) for p in settings.TEMPLATES[0]["DIRS"]] + ["football/templates"]:
            for path in glob.glob(f"{base}/**/*.html", recursive=True):
                try:
                    source = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for match in pattern.finditer(source):
                    if "\n" in match.group(1):
                        offenders.append(f"{path}: {match.group(1)[:60]!r}")
        self.assertEqual(offenders, [], "Usa {% comment %} para comentarios de varias líneas")
