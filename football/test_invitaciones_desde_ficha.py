from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Player,
    Team,
    UserInvitation,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class InvitacionesDesdeLaFichaTests(TestCase):
    """
    El acceso se da desde donde vive la persona: staff en su ficha, jugadores en la
    plantilla. La lista de miembros sólo reparte accesos de directiva/administración.
    """

    def setUp(self):
        self.owner = User.objects.create_user(username="dueno2", password="x", email="d@club.com")
        self.workspace = Workspace.objects.create(
            name="Club invitaciones",
            slug="club-invitaciones",
            kind=Workspace.KIND_CLUB,
            owner_user=self.owner,
        )
        self.team = Team.objects.create(name="Cadete inv", slug="cadete-inv")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.player = Player.objects.create(name="Jugador Inv", team=self.team, is_active=True)
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_miembros_no_invita_entrenadores(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "entrenador@club.com", "role_preset": "entrenador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="entrenador@club.com").exists())
        self.assertContains(resp, "ficha de staff")

    def test_miembros_no_invita_jugadores(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "jugador@club.com", "role_preset": "jugador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(email="jugador@club.com").exists())

    def test_miembros_si_invita_a_directiva(self):
        resp = self.client.post(
            reverse("workspace-members"),
            {"action": "invite", "email": "tesorero@club.com", "name": "Tesorero", "role_preset": "administrador"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(email="tesorero@club.com").exists())

    def test_el_jugador_se_invita_desde_la_plantilla(self):
        resp = self.client.post(
            reverse("player-portal-settings"),
            {
                "action": "invite_player",
                "player_id": self.player.id,
                "player_email": "madre@casa.com",
            },
        )

        self.assertEqual(resp.status_code, 200)
        invitado = User.objects.filter(email="madre@casa.com").first()
        self.assertIsNotNone(invitado)
        # La invitación viaja atada a la ficha del jugador, no se adivina luego por el nombre.
        self.assertTrue(
            UserInvitation.objects.filter(user=invitado, player=self.player, is_active=True).exists()
        )

    def test_invitar_jugador_sin_email_no_crea_nada(self):
        antes = User.objects.count()

        resp = self.client.post(
            reverse("player-portal-settings"),
            {"action": "invite_player", "player_id": self.player.id, "player_email": ""},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), antes)


class ContactoEnLaFichaTests(TestCase):
    """El email vive en la ficha del jugador y de ahí sale la invitación en bloque."""

    def setUp(self):
        self.owner = User.objects.create_user(username="dueno3", password="x", email="d3@club.com")
        self.workspace = Workspace.objects.create(
            name="Club contacto",
            slug="club-contacto",
            kind=Workspace.KIND_CLUB,
            owner_user=self.owner,
        )
        self.team = Team.objects.create(name="Benjamin cont", slug="benjamin-cont")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.con_email = Player.objects.create(
            name="Con email",
            team=self.team,
            is_active=True,
            contact_email="padre@casa.com",
            contact_name="Su padre",
            contact_is_guardian=True,
        )
        self.sin_email = Player.objects.create(name="Sin email", team=self.team, is_active=True)
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_by_workspace"] = {str(self.workspace.id): int(self.team.id)}
        session.save()

    def test_la_ficha_guarda_el_contacto(self):
        self.assertTrue(self.con_email.contact_is_guardian)
        self.assertEqual(self.con_email.contact_email, "padre@casa.com")

    def test_invitacion_en_bloque_usa_el_email_de_la_ficha(self):
        resp = self.client.post(
            reverse("player-portal-settings"),
            {
                "action": "invite_squad",
                "player_ids": [self.con_email.id, self.sin_email.id],
            },
        )

        self.assertEqual(resp.status_code, 200)
        invitado = User.objects.filter(email="padre@casa.com").first()
        self.assertIsNotNone(invitado)
        self.assertTrue(
            UserInvitation.objects.filter(user=invitado, player=self.con_email, is_active=True).exists()
        )
        # El que no tiene email no se inventa ninguna cuenta, y se dice cuántos quedaron fuera.
        self.assertFalse(UserInvitation.objects.filter(player=self.sin_email).exists())
        self.assertContains(resp, "1 sin email en su ficha")


class AltaDeStaffConAccesoTests(TestCase):
    """
    El camino entero: dar de alta a un entrenador desde su ficha, invitarle, que acepte y
    que entre viendo SU categoría y ninguna más.
    """

    def setUp(self):
        from django.test import RequestFactory

        from .models import StaffMember

        self.factory = RequestFactory()
        self.StaffMember = StaffMember
        self.owner = User.objects.create_user(username="dueno-alta", password="x", email="d3@club.com")
        self.workspace = Workspace.objects.create(
            name="Club alta staff", slug="club-alta-staff",
            kind=Workspace.KIND_CLUB, owner_user=self.owner,
        )
        self.cadete = Team.objects.create(name="Cadete alta", slug="cadete-alta")
        self.senior = Team.objects.create(name="Senior alta", slug="senior-alta")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete, is_default=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.senior)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.client.force_login(self.owner)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        sesion["active_team_by_workspace"] = {str(self.workspace.id): int(self.cadete.id)}
        sesion.save()

    def _alta(self, **extra):
        datos = {
            "name": "Nuevo Entrenador",
            "role_title": "Entrenador",
            "email": "nuevo.entrenador@club.com",
            "scope": "team",
            "access_action": "invite",
            "role_preset": "coach",
        }
        datos.update(extra)
        return self.client.post(reverse("staff-member-create"), datos, follow=True)

    def test_el_alta_crea_la_ficha_en_su_categoria(self):
        self._alta()

        miembro = self.StaffMember.objects.get(name="Nuevo Entrenador")
        self.assertEqual(miembro.team_id, self.cadete.id)
        self.assertEqual(miembro.email, "nuevo.entrenador@club.com")
        self.assertTrue(miembro.is_active)

    def test_el_alta_crea_la_invitacion_a_su_email(self):
        self._alta()

        invitacion = UserInvitation.objects.filter(email__iexact="nuevo.entrenador@club.com").first()
        self.assertIsNotNone(invitacion, "No se creó la invitación al marcar 'Crear invitación'")
        self.assertTrue(invitacion.token)
        # La invitación ya trae su usuario creado (inactivo hasta que ponga contraseña).
        self.assertFalse(invitacion.user.is_active)
        self.assertTrue(
            WorkspaceMembership.objects.filter(workspace=self.workspace, user=invitacion.user).exists(),
            "El invitado no quedó dado de alta en el club",
        )

    def test_sin_invitacion_no_se_crea_acceso(self):
        """'Sin acceso nuevo' debe dejar la ficha hecha y NINGUNA invitación."""
        self._alta(access_action="none", email="solo.ficha@club.com")

        self.assertTrue(self.StaffMember.objects.filter(name="Nuevo Entrenador").exists())
        self.assertFalse(UserInvitation.objects.filter(email__iexact="solo.ficha@club.com").exists())

    def test_al_invitar_se_le_da_su_categoria_explicitamente(self):
        """
        Sin fila de acceso la persona entraba "de rebote", porque el sistema deducía su
        categoría de la ficha de staff. Cuando esa deducción falla, se queda fuera (403).
        """
        from .models import WorkspaceTeamAccess

        self._alta()
        invitacion = UserInvitation.objects.get(email__iexact="nuevo.entrenador@club.com")

        acceso = WorkspaceTeamAccess.objects.filter(
            workspace=self.workspace, user=invitacion.user, team=self.cadete
        ).first()
        self.assertIsNotNone(acceso, "Se invitó sin darle acceso a su categoría")
        self.assertTrue(acceso.is_default)
        self.assertFalse(
            WorkspaceTeamAccess.objects.filter(
                workspace=self.workspace, user=invitacion.user, team=self.senior
            ).exists(),
            "Se le dio acceso a una categoría que no es la suya",
        )

    def test_el_ambito_club_completo_no_ata_a_una_categoria(self):
        self._alta(scope="club", name="Coordinador Club")

        miembro = self.StaffMember.objects.get(name="Coordinador Club")
        self.assertIsNone(miembro.team_id)

    def test_al_aceptar_entra_y_solo_ve_su_categoria(self):
        from .workspace_context import allowed_team_ids_for_request

        self._alta()
        invitacion = UserInvitation.objects.get(email__iexact="nuevo.entrenador@club.com")

        usuario = invitacion.user
        self.client.logout()
        respuesta = self.client.post(
            reverse("user-invite-accept", args=[invitacion.token]),
            {"password": "Contrasena-Larga-9", "password_confirm": "Contrasena-Larga-9"},
            follow=True,
        )
        self.assertEqual(respuesta.status_code, 200)

        usuario.refresh_from_db()
        invitacion.refresh_from_db()
        self.assertTrue(usuario.is_active, "Tras aceptar, el usuario sigue sin poder entrar")
        self.assertIsNotNone(invitacion.accepted_at, "La invitación no quedó marcada como aceptada")
        self.assertTrue(
            self.client.login(username=usuario.username, password="Contrasena-Larga-9"),
            "La contraseña que puso al aceptar no le deja entrar",
        )

        peticion = self.factory.get("/coach/")
        peticion.user = usuario
        peticion.session = self.client.session
        peticion.session["active_workspace_id"] = self.workspace.id
        alcanza = allowed_team_ids_for_request(peticion)
        self.assertNotIn(self.senior.id, alcanza, "Un entrenador del cadete alcanza el senior")


class ContrasenaDesdeLaFichaTests(TestCase):
    """
    El correo de invitación no siempre llega. Sin una forma de dar la contraseña a mano, la
    persona se queda fuera y nadie puede hacer nada.
    """

    def setUp(self):
        from .models import StaffMember

        self.owner = User.objects.create_user(username="dueno-pwd", password="x", email="d4@club.com")
        self.workspace = Workspace.objects.create(
            name="Club contrasena", slug="club-contrasena",
            kind=Workspace.KIND_CLUB, owner_user=self.owner,
        )
        self.cadete = Team.objects.create(name="Cadete pwd", slug="cadete-pwd")
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.cadete, is_default=True)
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.entrenador = User.objects.create_user(
            username="entrenador.pwd", password="loquesea", email="e@club.com", is_active=False
        )
        self.miembro = StaffMember.objects.create(
            workspace=self.workspace, team=self.cadete, name="Entrenador Pwd",
            role_title="Entrenador", user=self.entrenador, is_active=True,
        )
        self.client.force_login(self.owner)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        sesion["active_team_by_workspace"] = {str(self.workspace.id): int(self.cadete.id)}
        sesion.save()

    def _poner(self, clave, repetida=None, staff_id=None):
        return self.client.post(
            reverse("staff-member-detail", args=[staff_id or self.miembro.id]),
            {"action": "set_password", "new_password": clave, "new_password_confirm": repetida if repetida is not None else clave},
            follow=True,
        )

    def test_deja_la_cuenta_lista_para_entrar(self):
        self._poner("Clave-Larga-2026x")

        self.entrenador.refresh_from_db()
        self.assertTrue(self.entrenador.is_active, "La cuenta sigue sin activar")
        self.assertTrue(self.entrenador.check_password("Clave-Larga-2026x"))

    def test_las_invitaciones_pendientes_dejan_de_valer(self):
        from django.utils import timezone
        from datetime import timedelta

        invitacion = UserInvitation.objects.create(
            user=self.entrenador, token=UserInvitation.generate_token(), email="e@club.com",
            expires_at=timezone.now() + timedelta(days=7), is_active=True,
        )

        self._poner("Clave-Larga-2026x")

        invitacion.refresh_from_db()
        self.assertFalse(invitacion.is_active, "El enlace viejo sigue sirviendo tras poner la contraseña")

    def test_si_no_coinciden_no_toca_nada(self):
        self._poner("Clave-Larga-2026x", "Otra-Clave-2026x")

        self.entrenador.refresh_from_db()
        self.assertFalse(self.entrenador.is_active)
        self.assertFalse(self.entrenador.check_password("Clave-Larga-2026x"))

    def test_una_contrasena_debil_se_rechaza(self):
        self._poner("1234")

        self.entrenador.refresh_from_db()
        self.assertFalse(self.entrenador.check_password("1234"))

    def test_no_se_le_puede_cambiar_al_propietario(self):
        from .models import StaffMember

        ficha_dueno = StaffMember.objects.create(
            workspace=self.workspace, team=self.cadete, name="El Dueño",
            role_title="Presidente", user=self.owner, is_active=True,
        )

        self._poner("Clave-Larga-2026x", staff_id=ficha_dueno.id)

        self.owner.refresh_from_db()
        self.assertFalse(self.owner.check_password("Clave-Larga-2026x"))

    def test_quien_no_manda_en_el_club_no_puede(self):
        intruso = User.objects.create_user(username="intruso-pwd", password="x")
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=intruso, role=WorkspaceMembership.ROLE_MEMBER
        )
        self.client.force_login(intruso)
        sesion = self.client.session
        sesion["active_workspace_id"] = self.workspace.id
        sesion.save()

        respuesta = self._poner("Clave-Larga-2026x")

        self.entrenador.refresh_from_db()
        self.assertFalse(self.entrenador.check_password("Clave-Larga-2026x"))
        self.assertIn(respuesta.status_code, (200, 403))
