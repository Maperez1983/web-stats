from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from football.models import Player, Team


class PlayerAvatarFichaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juan", is_active=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_profile_form_saves_skin_grade_and_hair(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(
            url,
            {"form_action": "profile", "skin_grade": "5", "hair_color": "#1a1a1a"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertEqual(self.player.skin_grade, 5)
        self.assertEqual(self.player.hair_color, "#1a1a1a")

    def test_profile_form_rejects_bad_values(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(
            url,
            {"form_action": "profile", "skin_grade": "9", "hair_color": "rojo"},
            HTTP_HOST="localhost",
        )
        self.player.refresh_from_db()
        self.assertIsNone(self.player.skin_grade)
        self.assertEqual(self.player.hair_color, "")

    def test_preview_query_overrides_change_output(self):
        base = reverse("player-avatar-recolored", args=[self.player.id])
        plain = self.client.get(base, HTTP_HOST="localhost").content
        tinted = self.client.get(base + "?g=6&h=%231a1a1a", HTTP_HOST="localhost").content
        self.assertNotEqual(plain, tinted)

    def test_lineup_card_exposes_avatar_url_when_personalized(self):
        from football.views import _safe_initial_eleven_player_card

        # Sin personalización: sin avatar_url (usa kit genérico por rol en el campo).
        self.assertEqual(_safe_initial_eleven_player_card(self.player)["avatar_url"], "")
        # Con grado de piel: la tarjeta expone la URL del avatar recoloreado.
        self.player.skin_grade = 3
        self.player.save()
        card = _safe_initial_eleven_player_card(self.player)
        self.assertEqual(card["avatar_url"], reverse("player-avatar-recolored", args=[self.player.id]))

    def test_resolver_priority(self):
        from django.core.files.base import ContentFile
        from football.views import resolve_player_avatar_url

        # 1) nada -> ''
        self.assertEqual(resolve_player_avatar_url(self.player), "")
        # 2) grado de piel -> avatar recoloreado (sintético)
        self.player.skin_grade = 4
        self.player.save()
        self.assertEqual(resolve_player_avatar_url(self.player), reverse("player-avatar-recolored", args=[self.player.id]))
        # 3) avatar generado (face-swap) -> tiene prioridad sobre el sintético
        self.player.avatar_generated.save("gen.png", ContentFile(b"\x89PNG\r\n\x1a\n"), save=True)
        self.assertIn("player-avatars/", resolve_player_avatar_url(self.player))

    def test_profile_form_saves_hairstyle(self):
        url = reverse("player-detail", args=[self.player.id])
        self.client.post(url, {"form_action": "profile", "hairstyle": "rizado"}, HTTP_HOST="localhost")
        self.player.refresh_from_db()
        self.assertEqual(self.player.hairstyle, "rizado")
        # valor inválido -> vacío
        self.client.post(url, {"form_action": "profile", "hairstyle": "mohicano"}, HTTP_HOST="localhost")
        self.player.refresh_from_db()
        self.assertEqual(self.player.hairstyle, "")
