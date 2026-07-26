from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import Player, Team


class PlayerAvatarRecolorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="B", slug="b", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Juan", is_active=True)
        self.client = Client()
        self.client.force_login(self.user)

    def _get(self):
        return self.client.get(f"/player/{self.player.id}/avatar.png", HTTP_HOST="localhost")

    def test_returns_png(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertTrue(resp.content[:8] == b"\x89PNG\r\n\x1a\n")

    def test_skin_grade_changes_output(self):
        default = self._get().content
        self.player.skin_grade = 6  # muy oscura
        self.player.save()
        dark = self._get().content
        self.assertNotEqual(default, dark)  # el recolor cambia la imagen
