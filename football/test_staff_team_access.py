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


class AislamientoDeCategoriaTests(TestCase):
    """
    Regla del club: quien trabaja en una categoría no ve las demás.

    Se prueba sobre `allowed_team_ids_for_request`, que es de donde beben la ficha del club,
    la plantilla y el resto de pantallas: si esto se abre, se abren todas a la vez.
    """

    def setUp(self):
        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.owner = User.objects.create_user(username="owner-aisl", password="x")
        self.coach = User.objects.create_user(username="coach-aisl", password="x")
        self.workspace = Workspace.objects.create(
            name="Club aislamiento", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.senior = Team.objects.create(name="Senior aisl", slug="senior-aisl")
        self.cadete = Team.objects.create(name="Cadete aisl", slug="cadete-aisl")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.coach, role=WorkspaceMembership.ROLE_MEMBER
        )

    def _peticion(self, user):
        from django.contrib.sessions.backends.db import SessionStore

        request = self.factory.get("/coach/")
        request.user = user
        request.session = SessionStore()
        request.session["active_workspace_id"] = self.workspace.id
        return request

    def test_el_del_cadete_no_alcanza_al_senior(self):
        from .workspace_context import allowed_team_ids_for_request, user_can_access_team

        WorkspaceTeamAccess.objects.create(
            workspace=self.workspace, user=self.coach, team=self.cadete, is_default=True
        )
        peticion = self._peticion(self.coach)

        self.assertEqual(allowed_team_ids_for_request(peticion), {self.cadete.id})
        self.assertTrue(user_can_access_team(peticion, self.cadete))
        self.assertFalse(user_can_access_team(peticion, self.senior))

    def test_quien_manda_en_el_club_llega_a_todas(self):
        from .workspace_context import allowed_team_ids_for_request

        peticion = self._peticion(self.owner)

        self.assertEqual(
            allowed_team_ids_for_request(peticion), {self.senior.id, self.cadete.id}
        )


class AmbitoExplicitoTests(TestCase):
    """
    El ámbito de una ficha de staff se ELIGE. Antes se tomaba del equipo activo de quien
    editaba: abrir la ficha del entrenador del cadete desde el senior y darle a guardar le
    cambiaba la categoría, y con ella a qué llega esa persona.
    """

    def setUp(self):
        from django.urls import reverse

        from .models import StaffMember

        self.reverse = reverse
        self.owner = User.objects.create_user(username="dueno-ambito", password="x")
        self.workspace = Workspace.objects.create(
            name="Club ambito", slug="club-ambito", kind=Workspace.KIND_CLUB, owner_user=self.owner
        )
        self.senior = Team.objects.create(name="Senior ambito", slug="senior-ambito")
        self.cadete = Team.objects.create(name="Cadete ambito", slug="cadete-ambito")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.miembro = StaffMember.objects.create(
            workspace=self.workspace, team=self.cadete, name="Del Cadete",
            role_title="Entrenador asistente", is_active=True,
        )
        self.client.force_login(self.owner)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        # Quien edita está en el SENIOR, no en el cadete.
        sesion["active_team_by_workspace"] = {str(self.workspace.id): int(self.senior.id)}
        sesion.save()

    def test_guardar_desde_otra_categoria_no_se_lo_lleva(self):
        self.client.post(
            self.reverse("staff-member-detail", args=[self.miembro.id]),
            {"name": "Del Cadete", "role_title": "Entrenador asistente",
             "scope": f"team_{self.cadete.id}", "access_action": "none", "is_active": "1"},
            follow=True,
        )
        self.miembro.refresh_from_db()

        self.assertEqual(self.miembro.team_id, self.cadete.id, "Le cambió la categoría al guardar")

    def test_se_puede_moverlo_a_otra_categoria_a_proposito(self):
        self.client.post(
            self.reverse("staff-member-detail", args=[self.miembro.id]),
            {"name": "Del Cadete", "role_title": "Entrenador asistente",
             "scope": f"team_{self.senior.id}", "access_action": "none", "is_active": "1"},
            follow=True,
        )
        self.miembro.refresh_from_db()

        self.assertEqual(self.miembro.team_id, self.senior.id)

    def test_club_completo_lo_deja_sin_categoria(self):
        self.client.post(
            self.reverse("staff-member-detail", args=[self.miembro.id]),
            {"name": "Del Cadete", "role_title": "Entrenador asistente",
             "scope": "club", "access_action": "none", "is_active": "1"},
            follow=True,
        )
        self.miembro.refresh_from_db()

        self.assertIsNone(self.miembro.team_id)

    def test_una_categoria_de_otro_club_no_cuela(self):
        ajena = Team.objects.create(name="De otro club", slug="ajena-ambito")

        self.client.post(
            self.reverse("staff-member-detail", args=[self.miembro.id]),
            {"name": "Del Cadete", "role_title": "Entrenador asistente",
             "scope": f"team_{ajena.id}", "access_action": "none", "is_active": "1"},
            follow=True,
        )
        self.miembro.refresh_from_db()

        self.assertNotEqual(self.miembro.team_id, ajena.id)
