"""
Una persona puede ser dos cosas: entrenador del cadete y jugador del senior.

El rol de aplicación es único, así que quien tiene rol de entrenador nunca podía ver su
propio espacio de jugador. Lo que manda aquí no es el rol: es que su ficha esté vinculada
a su cuenta.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    AppUserRole,
    Player,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class EntrenadorQueTambienJuegaTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="dueno-doble", password="x")
        self.persona = User.objects.create_user(username="manuel-doble", password="x")
        self.workspace = Workspace.objects.create(
            name="Club doble", slug="club-doble", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.senior = Team.objects.create(name="Senior doble", slug="senior-doble")
        self.cadete = Team.objects.create(name="Cadete doble", slug="cadete-doble")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.persona, role=WorkspaceMembership.ROLE_MEMBER
        )
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace, user=self.persona, team=self.cadete, is_default=True
        )
        # Entrenador del cadete...
        AppUserRole.objects.update_or_create(
            user=self.persona, defaults={"role": AppUserRole.ROLE_COACH}
        )
        # ...y jugador del senior.
        self.ficha = Player.objects.create(
            team=self.senior, name="Lolo", full_name="Manuel Fernández", user=self.persona, is_active=True
        )
        self.client.force_login(self.persona)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        sesion["active_team_by_workspace"] = {str(self.workspace.id): int(self.cadete.id)}
        sesion.save()

    def test_entra_en_su_espacio_de_jugador_siendo_entrenador(self):
        respuesta = self.client.get(reverse("player-home"))

        self.assertEqual(respuesta.status_code, 200)

    def test_su_espacio_es_el_suyo_y_no_el_de_otro(self):
        otro = Player.objects.create(team=self.senior, name="Otro Jugador", is_active=True)

        respuesta = self.client.get(reverse("player-home"))
        contenido = respuesta.content.decode("utf-8", "ignore")

        self.assertIn("Lolo", contenido)
        self.assertNotIn(otro.name, contenido)

    def test_sigue_siendo_entrenador_del_cadete(self):
        from .workspace_context import allowed_team_ids_for_request

        peticion = self.client.get(reverse("player-home")).wsgi_request

        self.assertEqual(allowed_team_ids_for_request(peticion), {self.cadete.id})

    def test_ser_jugador_del_senior_no_le_abre_el_senior(self):
        """Ve SU ficha, no la plantilla del senior: son cosas distintas."""
        from .workspace_context import user_can_access_team

        peticion = self.client.get(reverse("player-home")).wsgi_request

        self.assertFalse(user_can_access_team(peticion, self.senior))

    def test_el_enlace_aparece_solo_si_tiene_ficha(self):
        """El enlace "Mi ficha" sale por el VÍNCULO, no por el rol."""
        from django.test import RequestFactory

        from .context_processors import workspace_access

        def _valor():
            peticion = RequestFactory().get("/coach/")
            peticion.user = self.persona
            peticion.session = self.client.session
            return workspace_access(peticion).get("tiene_ficha_de_jugador")

        self.assertTrue(_valor())

        self.ficha.user = None
        self.ficha.save(update_fields=["user"])

        self.assertFalse(_valor())
