from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from football.manual_stats import save_manual_player_base_overrides
from football.models import (
    Competition,
    Group,
    Player,
    Season,
    Team,
    Workspace,
    WorkspaceSeason,
    WorkspaceSeasonPlayer,
)
from football.views import compute_player_dashboard


class ManualOverridesActiveSeasonTests(TestCase):
    """El 'Ajuste manual' debe aplicar en la ficha cuando la temporada de club es la ACTIVA.

    Antes se apagaba en cuanto había cualquier temporada de club activa, con lo que los
    números metidos a mano no surtían efecto en la ficha (contradecía el propio comentario
    del código). En temporada histórica NO deben aplicar (usarían los de la actual).
    """

    def _dashboard(self, *, season_active):
        user = get_user_model().objects.create_superuser("s", "s@example.com", "x")
        comp = Competition.objects.create(name="DH", slug="dh")
        season = Season.objects.create(competition=comp, name="2026/2027", is_current=True)
        group = Group.objects.create(season=season, name="G", slug="g")
        team = Team.objects.create(name="B", slug="b", is_primary=True, group=group)
        workspace = Workspace.objects.create(
            name="B", slug="b", kind=Workspace.KIND_CLUB, primary_team=team
        )
        ws = WorkspaceSeason.objects.create(
            workspace=workspace, label="2026/2027", start_date="2026-07-01", is_active=season_active
        )
        workspace.active_season = ws
        workspace.save()
        player = Player.objects.create(team=team, name="J", is_active=True)
        WorkspaceSeasonPlayer.objects.create(
            season=ws, player=player, team=team, is_confirmed=True,
            status=WorkspaceSeasonPlayer.STATUS_CONFIRMED,
        )
        save_manual_player_base_overrides(
            player=player, season=season,
            values={"manual_goals": "5", "manual_pj": "10", "manual_minutes": "800"},
        )
        req = RequestFactory().get("/")
        req.user = user
        sess = SessionStore()
        sess["active_workspace_id"] = workspace.id
        sess.save()
        req.session = sess
        rows = compute_player_dashboard(
            team, request=req, club_season=ws, scope="league", refresh_photo_urls=False
        )
        return next((r for r in rows if int(r.get("player_id") or 0) == player.id), None)

    def test_manual_override_applies_when_season_active(self):
        row = self._dashboard(season_active=True)
        self.assertIsNotNone(row)
        self.assertEqual(int(row.get("goals") or 0), 5)
        self.assertEqual(int(row.get("pj") or 0), 10)

    def test_manual_override_skipped_on_historical_season(self):
        row = self._dashboard(season_active=False)
        # Temporada histórica: no aplica el override de la temporada actual.
        if row is not None:
            self.assertNotEqual(int(row.get("goals") or 0), 5)
