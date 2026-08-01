from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import (
    Player,
    PlayerInjuryRecord,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class FichaDeLesionEnElMoldeTests(TestCase):
    """La ficha de lesión pasa a colgar del molde común sin perder nada por el camino."""

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno12", password="x")
        self.workspace = Workspace.objects.create(
            name="Club lesion", slug="club-lesion", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.team = Team.objects.create(name="Senior lesion", slug="senior-lesion")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.player = Player.objects.create(name="Jugador Lesion", team=self.team, is_active=True)
        self.record = PlayerInjuryRecord.objects.create(
            player=self.player,
            injury="Esguince de tobillo",
            injury_zone="Tobillo",
            injury_date=date(2026, 7, 20),
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_la_ficha_sigue_abriendo_con_su_contenido(self):
        resp = self.client.get(
            reverse("player-injury-detail", args=[self.player.id, self.record.id])
        )
        html = resp.content.decode()

        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ficha de lesión", html)
        self.assertIn("Esguince de tobillo", html)
        # Su CSS propio (hitos, chips, cabecera) sigue estando.
        self.assertIn(".milestone", html)
        self.assertIn(".kicker", html)
        # Y el chasis lo pone ya el molde.
        self.assertIn(".shell", html)
        self.assertIn("prod-commercial", html)

    def test_no_repite_el_volver_del_molde(self):
        resp = self.client.get(
            reverse("player-injury-detail", args=[self.player.id, self.record.id])
        )
        html = resp.content.decode()

        # Tiene su propio "Volver" en la cabecera; el del molde se queda fuera.
        self.assertNotIn("Volver a la ficha", html)
        self.assertIn(">Volver</a>", html)

    def test_las_otras_fichas_del_molde_siguen_bien(self):
        from .models import PlayerObjective

        objetivo = PlayerObjective.objects.create(player=self.player, text="Recuperar el tobillo")

        resp = self.client.get(
            reverse("player-objective-detail", args=[self.player.id, objetivo.id])
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Volver a la ficha")
