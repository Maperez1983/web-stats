"""
El mantenimiento de la ficha sale a su propia pantalla.

La ficha tenía 198 campos de formulario; 62 de ellos eran este bloque, metido como plegable
dentro de la pestaña Datos personales. Una pantalla de consulta no es un formulario. Ahora
`/player/N/editar/` aloja el formulario, con el MISMO markup (partial compartido) y enviando
al mismo sitio de siempre: no se ha duplicado ni una línea de guardado.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import AppUserRole, Player, Team, Workspace, WorkspaceTeam


class PlayerEditPageTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", number=21, is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.staff = get_user_model().objects.create_superuser("mister", "m@example.com", "x")
        self.workspace.owner_user = self.staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(self.staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_the_edit_page_renders(self):
        response = self.client.get(reverse("player-edit", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar ficha")

    def test_the_ficha_links_it_and_no_longer_carries_the_form(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-edit", args=[self.player.id]))
        # El formulario de perfil ya no vive en la ficha.
        self.assertNotContains(response, 'value="profile"')

    def test_saving_still_works_from_the_new_page(self):
        # El POST sigue yendo a la ficha, que es donde está el guardado de siempre.
        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "profile", "skin_grade": "5", "hair_color": "#1a1a1a"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.skin_grade, 5)

    def test_a_player_cannot_open_it(self):
        user = get_user_model().objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = user
        self.player.save(update_fields=["user"])
        client = Client()
        client.force_login(user)
        response = client.get(reverse("player-edit", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("player-home"))


class PlayerEvaluationNewPageTests(TestCase):
    """La nueva valoración —67 campos— sale también de la pestaña de consulta."""

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        staff = get_user_model().objects.create_superuser("mister2", "m2@example.com", "x")
        self.workspace.owner_user = staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_the_page_renders(self):
        response = self.client.get(
            reverse("player-evaluation-new", args=[self.player.id]), HTTP_HOST="localhost"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nueva valoración")

    def test_the_ficha_links_it_and_no_longer_carries_the_form(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        self.assertContains(response, reverse("player-evaluation-new", args=[self.player.id]))
        self.assertNotContains(response, 'value="evaluation"')

    def test_saving_still_works(self):
        from football.models import PlayerEvaluation

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "evaluation", "evaluation_type": "monthly", "status": "draft",
             "technical_rating": "6"},
            HTTP_HOST="localhost",
        )
        self.assertTrue(PlayerEvaluation.objects.filter(player=self.player).exists())


class PlayerFormPageTests(TestCase):
    """
    Una sola pantalla aloja los formularios de mantenimiento que salieron de la ficha.

    El ajuste manual de estadísticas NO salió: precarga con las estadísticas agregadas que la
    ficha calcula, y ese cálculo no se duplica. Además pertenece a la pestaña que ajusta.
    """

    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juanmi", is_active=True)
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        staff = get_user_model().objects.create_superuser("mister3", "m3@example.com", "x")
        self.workspace.owner_user = staff
        self.workspace.save(update_fields=["owner_user"])
        self.client = Client()
        self.client.force_login(staff)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_each_form_has_its_page(self):
        for key, titulo in [("fisico", "registro físico"), ("lesion", "lesión"), ("comunicacion", "comunicación")]:
            response = self.client.get(reverse("player-form", args=[self.player.id, key]), HTTP_HOST="localhost")
            self.assertEqual(response.status_code, 200, key)
            self.assertContains(response, titulo)

    def test_an_invented_key_is_404(self):
        response = self.client.get(reverse("player-form", args=[self.player.id, "inventado"]), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 404)

    def test_the_ficha_links_them_and_dropped_the_forms(self):
        response = self.client.get(reverse("player-detail", args=[self.player.id]), HTTP_HOST="localhost")
        for key in ("fisico", "lesion", "comunicacion"):
            self.assertContains(response, reverse("player-form", args=[self.player.id, key]))
        for accion in ('value="physical"', 'value="injuries"', 'value="communication"'):
            self.assertNotContains(response, accion)
        # El ajuste manual se queda en su pestaña.
        self.assertContains(response, 'value="manual_stats"')

    def test_saving_an_injury_still_works(self):
        from football.models import PlayerInjuryRecord

        self.client.post(
            reverse("player-detail", args=[self.player.id]),
            {"form_action": "injuries", "injury": "Sobrecarga", "injury_date": "2026-07-01",
             "injury_record_mode": "new"},
            HTTP_HOST="localhost",
        )
        self.assertTrue(PlayerInjuryRecord.objects.filter(player=self.player).exists())
