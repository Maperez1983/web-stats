"""
La valoración presentada es la MEDIA del cuerpo técnico, y la autovaloración no entra.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from football.evaluation_consensus import staff_consensus
from football.models import Player, PlayerEvaluation, Team


class StaffConsensusTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        User = get_user_model()
        self.mister = User.objects.create_user(username="mister", password="x")
        self.fisico = User.objects.create_user(username="fisico", password="x")
        self.jugador = User.objects.create_user(username="ayala", password="x")
        self.player.user = self.jugador
        self.player.save(update_fields=["user"])

    def _eval(self, author, *, tech, tact, day, kind=PlayerEvaluation.AUTHOR_STAFF,
              status=PlayerEvaluation.STATUS_CLOSED):
        return PlayerEvaluation.objects.create(
            team=self.team, player=self.player, created_by=author, author_kind=kind, status=status,
            evaluated_on=date(2026, 10, day), technical_rating=tech, tactical_rating=tact,
        )

    def test_average_across_staff_members(self):
        self._eval(self.mister, tech=6, tact=6, day=1)   # media 6
        self._eval(self.fisico, tech=8, tact=8, day=1)   # media 8
        result = staff_consensus(self.player)
        self.assertEqual(result["overall"], 7.0)
        self.assertEqual(result["voters"], 2)

    def test_one_member_one_vote(self):
        # Quien valora tres veces no pesa el triple: cuenta su ultima.
        self._eval(self.mister, tech=2, tact=2, day=1)
        self._eval(self.mister, tech=4, tact=4, day=5)
        self._eval(self.mister, tech=6, tact=6, day=9)   # esta es la suya
        self._eval(self.fisico, tech=8, tact=8, day=2)
        result = staff_consensus(self.player)
        self.assertEqual(result["voters"], 2)
        self.assertEqual(result["overall"], 7.0)

    def test_self_assessment_never_moves_the_average(self):
        self._eval(self.mister, tech=6, tact=6, day=1)
        self._eval(self.jugador, tech=10, tact=10, day=2, kind=PlayerEvaluation.AUTHOR_SELF)
        result = staff_consensus(self.player)
        self.assertEqual(result["overall"], 6.0)
        self.assertEqual(result["voters"], 1)
        # Pero se devuelve aparte, con la distancia respecto al staff.
        self.assertIsNotNone(result["self_assessment"])
        self.assertEqual(result["gap"], 4.0)

    def test_drafts_do_not_count(self):
        self._eval(self.mister, tech=6, tact=6, day=1)
        self._eval(self.fisico, tech=10, tact=10, day=2, status=PlayerEvaluation.STATUS_DRAFT)
        result = staff_consensus(self.player)
        self.assertEqual(result["overall"], 6.0)
        self.assertEqual(result["voters"], 1)

    def test_areas_are_averaged_one_by_one(self):
        self._eval(self.mister, tech=4, tact=8, day=1)
        self._eval(self.fisico, tech=8, tact=4, day=1)
        areas = {a["key"]: a["value"] for a in staff_consensus(self.player)["areas"]}
        self.assertEqual(areas["technical_rating"], 6.0)
        self.assertEqual(areas["tactical_rating"], 6.0)
        self.assertIsNone(areas["physical_rating"])

    def test_no_evaluations_is_not_a_zero(self):
        # Sin valoraciones NO hay media: un 0 diria que es malisimo, y lo que pasa es que
        # nadie le ha valorado.
        result = staff_consensus(self.player)
        self.assertIsNone(result["overall"])
        self.assertEqual(result["voters"], 0)

    def test_only_a_self_assessment_leaves_the_staff_average_empty(self):
        self._eval(self.jugador, tech=9, tact=9, day=1, kind=PlayerEvaluation.AUTHOR_SELF)
        result = staff_consensus(self.player)
        self.assertIsNone(result["overall"])
        self.assertEqual(result["voters"], 0)
        self.assertIsNotNone(result["self_assessment"])
        self.assertIsNone(result["gap"])


class SelfAssessmentFromPortalTests(TestCase):
    """El jugador se valora desde su portal, y eso no toca la media del cuerpo técnico."""

    def setUp(self):
        from django.core.cache import cache
        from football.models import (
            AppUserRole, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess,
        )

        cache.clear()
        self.workspace = Workspace.objects.create(name="Club", kind=Workspace.KIND_CLUB, is_active=True)
        self.team = Team.objects.create(name="Senior", slug="senior", is_primary=True)
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team)
        self.player = Player.objects.create(team=self.team, name="Ayala", is_active=True)
        User = get_user_model()
        self.user = User.objects.create_user(username="ayala", password="pass-1234")
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_PLAYER)
        self.player.user = self.user
        self.player.save(update_fields=["user"])
        WorkspaceMembership.objects.create(
            workspace=self.workspace, user=self.user, role=WorkspaceMembership.ROLE_VIEWER
        )
        WorkspaceTeamAccess.objects.create(workspace=self.workspace, team=self.team, user=self.user)
        self.mister = User.objects.create_user(username="mister", password="x")
        PlayerEvaluation.objects.create(
            team=self.team, player=self.player, created_by=self.mister,
            status=PlayerEvaluation.STATUS_CLOSED, evaluated_on=date(2026, 10, 1),
            technical_rating=6, tactical_rating=6,
        )

        from django.test import Client

        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_id"] = self.workspace.id
        session["active_team_id"] = self.team.id
        session.save()

    def test_player_can_rate_himself(self):
        from django.urls import reverse

        self.client.post(
            reverse("player-home"),
            {
                "form_action": "self_assessment",
                "technical_rating": "9",
                "tactical_rating": "9",
                "strengths": "Voy bien de uno contra uno",
            },
            HTTP_HOST="localhost",
        )
        own = PlayerEvaluation.objects.get(author_kind=PlayerEvaluation.AUTHOR_SELF)
        self.assertEqual(own.player_id, self.player.id)
        self.assertEqual(own.created_by_id, self.user.id)

        # Y la media del cuerpo técnico no se mueve.
        result = staff_consensus(self.player)
        self.assertEqual(result["overall"], 6.0)
        self.assertEqual(result["voters"], 1)
        self.assertEqual(result["gap"], 3.0)

    def test_scores_are_clamped(self):
        from django.urls import reverse

        self.client.post(
            reverse("player-home"),
            {"form_action": "self_assessment", "technical_rating": "99", "tactical_rating": "-4"},
            HTTP_HOST="localhost",
        )
        own = PlayerEvaluation.objects.get(author_kind=PlayerEvaluation.AUTHOR_SELF)
        self.assertEqual(float(own.technical_rating), 10.0)
        self.assertEqual(float(own.tactical_rating), 1.0)
