import datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from football.models import (
    Player,
    PlayerInjuryRecord,
    Team,
    Workspace,
    WorkspaceMembership,
)


class PlayerInjuriesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        self.team = Team.objects.create(name="Bena", slug="bena", is_primary=True)
        self.workspace = Workspace.objects.create(
            name="Bena", slug="bena", kind=Workspace.KIND_CLUB, primary_team=self.team
        )
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role="owner")
        self.player = Player.objects.create(team=self.team, name="Juan", is_active=True)
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session.save()

    def _url(self):
        return f"/player/{self.player.id}/"

    # --- Guardado (red de seguridad para el refactor de _persist_player_injury) ---
    def test_save_injury_creates_record(self):
        resp = self.client.post(
            self._url(),
            {
                "form_action": "injuries",
                "injury": "Rotura fibrilar isquios",
                "injury_type": "Muscular",
                "injury_zone": "Isquiotibiales",
                "injury_side": "Derecha",
                "injury_date": "2026-02-10",
                "injury_notes": "En partido",
                "injury_record_mode": "new",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        rec = PlayerInjuryRecord.objects.get(player=self.player, injury="Rotura fibrilar isquios")
        self.assertEqual(rec.injury_zone, "Isquiotibiales")
        self.assertEqual(rec.injury_date, datetime.date(2026, 2, 10))

    def test_update_existing_injury_marks_recovered(self):
        rec = PlayerInjuryRecord.objects.create(
            player=self.player, injury="Tobillo", injury_date=datetime.date(2026, 1, 5), is_active=True
        )
        resp = self.client.post(
            self._url(),
            {
                "form_action": "injuries",
                "injury": "Tobillo",
                "injury_date": "2026-01-05",
                "injury_return_date": "2026-01-20",
                "injury_record_id": rec.id,
                "injury_record_mode": "update",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        rec.refresh_from_db()
        self.assertEqual(rec.return_date, datetime.date(2026, 1, 20))
        self.assertTrue(rec.is_recovered)
        self.assertFalse(rec.is_active)
        self.player.refresh_from_db()
        self.assertEqual(self.player.injury, "")  # ya no figura lesionado

    # --- Borrado múltiple ---
    def test_bulk_delete_selected_injuries(self):
        i1 = PlayerInjuryRecord.objects.create(player=self.player, injury="A", injury_date=datetime.date(2026, 1, 1))
        i2 = PlayerInjuryRecord.objects.create(player=self.player, injury="A", injury_date=datetime.date(2026, 1, 1))
        i3 = PlayerInjuryRecord.objects.create(player=self.player, injury="B", injury_date=datetime.date(2026, 2, 1))
        resp = self.client.post(
            self._url(),
            {"form_action": "delete-injuries", "injury_ids": [i1.id, i2.id]},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(PlayerInjuryRecord.objects.filter(id__in=[i1.id, i2.id]).exists())
        self.assertTrue(PlayerInjuryRecord.objects.filter(id=i3.id).exists())

    def test_bulk_delete_only_touches_this_player(self):
        other = Player.objects.create(team=self.team, name="Pepe", is_active=True)
        mine = PlayerInjuryRecord.objects.create(player=self.player, injury="A", injury_date=datetime.date(2026, 1, 1))
        theirs = PlayerInjuryRecord.objects.create(player=other, injury="B", injury_date=datetime.date(2026, 1, 1))
        self.client.post(
            self._url(),
            {"form_action": "delete-injuries", "injury_ids": [mine.id, theirs.id]},
            HTTP_HOST="localhost",
        )
        self.assertFalse(PlayerInjuryRecord.objects.filter(id=mine.id).exists())
        self.assertTrue(PlayerInjuryRecord.objects.filter(id=theirs.id).exists())
