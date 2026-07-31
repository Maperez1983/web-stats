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


class StaffFichaAccessPostTests(TestCase):
    """El formulario de la ficha guarda categorías y módulos sin salir de la ficha."""

    def setUp(self):
        from .models import StaffMember

        self.owner = User.objects.create_user(username="dueno", password="x")
        self.coach = User.objects.create_user(username="tecnico", password="x")
        self.workspace = Workspace.objects.create(
            name="Club ficha",
            slug="club-ficha",
            kind=Workspace.KIND_CLUB,
            owner_user=self.owner,
        )
        self.senior = Team.objects.create(name="Senior ficha", slug="senior-ficha")
        self.cadete = Team.objects.create(name="Cadete ficha", slug="cadete-ficha")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.coach, role=WorkspaceMembership.ROLE_MEMBER
        )
        self.member = StaffMember.objects.create(
            workspace=self.workspace,
            team=self.senior,
            user=self.coach,
            name="Técnico de prueba",
            role_title="Entrenador",
        )
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.senior.id)}
        session.save()

    def _post(self, **extra):
        payload = {
            "name": self.member.name,
            "role_title": "Entrenador",
            "scope": "team",
            "is_active": "1",
        }
        payload.update(extra)
        return self.client.post(
            f"/coach/staff/{self.member.id}/?team={self.senior.id}", payload, follow=True
        )

    def test_guarda_categorias_y_modulos_solo_de_esa_categoria(self):
        resp = self._post(**{
            f"access_team_{self.senior.id}": "1",
            "access_modules_scope": "team",
            "access_module_dashboard": "1",
            "access_module_sessions": "1",
        })
        self.assertEqual(resp.status_code, 200)

        row = WorkspaceTeamAccess.objects.get(workspace=self.workspace, team=self.senior, user=self.coach)
        self.assertTrue(row.module_access.get("dashboard"))
        self.assertTrue(row.module_access.get("sessions"))
        self.assertFalse(row.module_access.get("tactics"))
        # El cadete ni siquiera tiene fila: no se le ha tocado nada.
        self.assertFalse(
            WorkspaceTeamAccess.objects.filter(workspace=self.workspace, team=self.cadete, user=self.coach).exists()
        )
        # Y el gate lo respeta.
        self.assertTrue(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "sessions", team=self.senior)
        )
        self.assertFalse(
            permissions.workspace_member_allows_module(self.workspace, self.coach, "tactics", team=self.senior)
        )

    def test_todo_el_club_marca_todas_las_categorias(self):
        self._post(access_all_teams="1")

        self.assertEqual(
            WorkspaceTeamAccess.objects.filter(workspace=self.workspace, user=self.coach).count(), 2
        )

    def test_guardar_para_todo_el_club_limpia_las_excepciones(self):
        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace,
            team=self.senior,
            user=self.coach,
            module_access={"sessions": False},
        )
        self._post(**{
            f"access_team_{self.senior.id}": "1",
            "access_modules_scope": "club",
            "access_module_sessions": "1",
        })

        membership = WorkspaceMembership.objects.get(workspace=self.workspace, user=self.coach)
        self.assertTrue(membership.module_access.get("sessions"))
        row = WorkspaceTeamAccess.objects.get(workspace=self.workspace, team=self.senior, user=self.coach)
        self.assertEqual(row.module_access, {})
