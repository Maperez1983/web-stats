from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .models import Match, Team, Workspace, WorkspaceMembership, WorkspaceTeam


class AmistosoEnEquipoSinLigaTests(TestCase):
    """
    Una categoría de cantera en pretemporada NO tiene liga configurada todavía. Crear su
    amistoso tiene que funcionar igual: es justo cuando se cierran los amistosos.
    """

    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username="dueno15", password="x")
        self.workspace = Workspace.objects.create(
            name="Club cantera", slug="club-cantera", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        # Sin group ni season: exactamente como el Cadete A en agosto.
        self.cadete = Team.objects.create(name="Cadete A prueba", slug="cadete-a-prueba")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.cadete.id)}
        session.save()

    def test_se_puede_crear_el_amistoso(self):
        respuesta = self.client.post(
            reverse("match-hub-create"),
            {
                "team": self.cadete.id,
                "opponent": "U.D. Sta. Rosalía Maqueda",
                "context": "friendly",
                "date": "2026-08-22",
            },
        )

        self.assertIn(respuesta.status_code, (200, 302))
        self.assertTrue(Match.objects.filter(away_team__name__icontains="Rosalía").exists())

    def test_reutiliza_la_misma_temporada_para_los_siguientes(self):
        from .models import Season

        for rival, dia in (("Rival Uno", "2026-08-22"), ("Rival Dos", "2026-08-29")):
            self.client.post(
                reverse("match-hub-create"),
                {"team": self.cadete.id, "opponent": rival, "context": "friendly", "date": dia},
            )

        self.assertEqual(Season.objects.filter(competition__slug="amistosos").count(), 1)
        self.assertEqual(Match.objects.count(), 2)

    def test_el_equipo_con_liga_sigue_usando_la_suya(self):
        from .models import Competition, Group, Season

        competicion = Competition.objects.create(name="Liga cadete", slug="liga-cadete-t")
        temporada = Season.objects.create(competition=competicion, name="2026/2027")
        grupo = Group.objects.create(season=temporada, name="Grupo 1", slug="g1-cadete-t")
        self.cadete.group = grupo
        self.cadete.save(update_fields=["group"])

        self.client.post(
            reverse("match-hub-create"),
            {"team": self.cadete.id, "opponent": "Rival Liga", "context": "friendly", "date": "2026-08-22"},
        )

        creado = Match.objects.get(away_team__name="Rival Liga")
        self.assertEqual(creado.season, temporada)
        self.assertFalse(Season.objects.filter(competition__slug="amistosos").exists())
