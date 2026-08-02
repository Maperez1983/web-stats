import datetime
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from football.account_views import _player_home_zones
from football.models import (
    Player,
    PlayerInjuryRecord,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    TrainingSessionAttendance,
    Workspace,
    WorkspaceMembership,
)
from football.query_helpers import get_active_injury_player_ids
from football.views import _build_tactical_player_catalog


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

    def test_medical_discharge_updates_player_and_tactical_boards(self):
        today = timezone.localdate()
        microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            week_start=today - datetime.timedelta(days=7),
            week_end=today + datetime.timedelta(days=7),
        )
        past_session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today - datetime.timedelta(days=1),
        )
        future_session = TrainingSession.objects.create(
            microcycle=microcycle,
            session_date=today + datetime.timedelta(days=1),
        )
        past_mark = TrainingSessionAttendance.objects.create(
            session=past_session,
            player=self.player,
            status=TrainingSessionAttendance.STATUS_INJURED,
        )
        future_mark = TrainingSessionAttendance.objects.create(
            session=future_session,
            player=self.player,
            status=TrainingSessionAttendance.STATUS_INJURED,
        )
        self.player.injury = "Esguince de tobillo"
        self.player.injury_type = "Articular"
        self.player.injury_zone = "Tobillo"
        self.player.injury_side = "Derecha"
        self.player.injury_date = today - datetime.timedelta(days=7)
        self.player.save()
        record = PlayerInjuryRecord.objects.create(
            player=self.player,
            injury="Esguince de tobillo",
            injury_type="Articular",
            injury_zone="Tobillo",
            injury_side="Derecha",
            injury_date=today - datetime.timedelta(days=7),
            is_active=True,
        )

        self.assertIn(self.player.id, get_active_injury_player_ids([self.player.id]))
        response = self.client.post(
            reverse("coach-injuries"),
            {
                "action": "close",
                "player_id": self.player.id,
                "record_id": record.id,
                "return_date": today.isoformat(),
            },
            HTTP_HOST="localhost",
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.player.refresh_from_db()
        self.assertTrue(record.is_recovered)
        self.assertFalse(record.is_active)
        self.assertEqual(self.player.injury, "")
        self.assertEqual(self.player.injury_type, "")
        self.assertEqual(self.player.injury_zone, "")
        self.assertEqual(self.player.injury_side, "")
        self.assertIsNone(self.player.injury_date)
        self.assertNotIn(self.player.id, get_active_injury_player_ids([self.player.id]))
        self.assertTrue(TrainingSessionAttendance.objects.filter(id=past_mark.id).exists())
        self.assertFalse(TrainingSessionAttendance.objects.filter(id=future_mark.id).exists())

        request = RequestFactory().get("/", HTTP_HOST="localhost")
        request.user = self.user
        request.session = {
            "active_workspace_id": self.workspace.id,
            "active_team_by_workspace": {str(self.workspace.id): self.team.id},
        }
        catalog = _build_tactical_player_catalog(request, self.team)
        player_entry = next(item for item in catalog if item["id"] == self.player.id)
        self.assertEqual(player_entry["estado"], "disponible")

    def test_player_portal_ignores_recovered_record_without_return_date(self):
        PlayerInjuryRecord.objects.create(
            player=self.player,
            injury="Parte ya cerrado",
            injury_date=timezone.localdate() - datetime.timedelta(days=5),
            return_date=None,
            is_active=False,
            is_recovered=True,
        )
        request = RequestFactory().get("/", HTTP_HOST="localhost")
        request.user = self.user
        visibility = SimpleNamespace(
            injuries=True,
            injuries_published=False,
            physical=False,
            evaluation=False,
            videos=False,
            fines=False,
            communication=False,
        )

        zones = _player_home_zones(request, self.player, visibility)

        self.assertIsNone(zones["active_injury"])
