from django.contrib.auth.models import User
from django.test import TestCase

from . import permissions
from .models import (
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


class TeamModuleAccessTests(TestCase):
    """La categoría manda sobre la regla del club; sin excepción, hereda."""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")
        self.coach = User.objects.create_user(username="coach", password="x")
        self.workspace = Workspace.objects.create(
            name="Club de prueba",
            kind=Workspace.KIND_CLUB,
            owner_user=self.owner,
        )
        self.senior = Team.objects.create(name="Senior", slug="senior-test")
        self.cadete = Team.objects.create(name="Cadete", slug="cadete-test")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        self.membership = WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.coach,
            role=WorkspaceMembership.ROLE_MEMBER,
        )

    def test_sin_reglas_ve_todo(self):
        self.assertTrue(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=self.senior)
        )

    def test_regla_del_club_se_hereda_en_todas_las_categorias(self):
        self.membership.module_access = {"sessions": False}
        self.membership.save(update_fields=["module_access"])

        for team in (self.senior, self.cadete):
            self.assertFalse(
                permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=team)
            )

    def test_la_categoria_puede_tener_su_propia_regla(self):
        self.membership.module_access = {"sessions": False, "tactics": False}
        self.membership.save(update_fields=["module_access"])
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace,
            team=self.senior,
            user=self.coach,
            module_access={"sessions": True, "tactics": False},
        )

        # En el senior manda la excepción de esa categoría...
        self.assertTrue(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=self.senior)
        )
        self.assertFalse(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "tactics", team=self.senior)
        )
        # ...y el cadete sigue con la del club.
        self.assertFalse(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=self.cadete)
        )

    def test_fila_de_categoria_sin_reglas_no_pisa_la_del_club(self):
        self.membership.module_access = {"sessions": False}
        self.membership.save(update_fields=["module_access"])
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.senior, user=self.coach)

        self.assertFalse(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=self.senior)
        )

    def test_sin_categoria_activa_manda_la_regla_del_club(self):
        self.membership.module_access = {"sessions": False}
        self.membership.save(update_fields=["module_access"])
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace,
            team=self.senior,
            user=self.coach,
            module_access={"sessions": True},
        )

        self.assertFalse(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions")
        )
