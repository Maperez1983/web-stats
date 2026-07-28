import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from football import views
from football.models import (
    Competition,
    ConvocationRecord,
    Match,
    Player,
    PlayerNotification,
    Season,
    Team,
)


class _Actor:
    is_authenticated = False


class ConvocationNotificationTests(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga PN", slug="liga-pn", region="Málaga")
        self.season = Season.objects.create(
            competition=self.comp,
            name="2025/26",
            start_date=datetime.date(2025, 8, 1),
            end_date=datetime.date(2026, 6, 30),
        )
        self.team = Team.objects.create(name="PN Test FC", slug="pn-test-fc")
        self.user = User.objects.create_user(username="pn_player", password="x")
        self.linked = Player.objects.create(team=self.team, name="Jugador Enlazado", user=self.user)
        self.unlinked = Player.objects.create(team=self.team, name="Jugador Sin Cuenta")
        self.match = Match.objects.create(home_team=self.team, season=self.season, round="J1")
        self.record = ConvocationRecord.objects.create(
            team=self.team, match=self.match, opponent_name="Rival CF",
            match_date=datetime.date(2026, 2, 1),
        )
        self.record.players.set([self.linked, self.unlinked])

    def test_notifies_only_linked_players(self):
        views._notify_convoked_players(self.record, self.match, _Actor())
        notifs = PlayerNotification.objects.filter(match=self.match)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.target_user_id, self.user.id)
        self.assertEqual(n.kind, PlayerNotification.KIND_CONVOCATION)
        self.assertEqual(n.title, "Has sido convocado")
        self.assertIn("Rival CF", n.message)
        self.assertFalse(n.is_read)

    def test_idempotent_on_resave(self):
        views._notify_convoked_players(self.record, self.match, _Actor())
        views._notify_convoked_players(self.record, self.match, _Actor())
        self.assertEqual(PlayerNotification.objects.filter(match=self.match).count(), 1)

    def test_deconvocation_clears_unread(self):
        views._notify_convoked_players(self.record, self.match, _Actor())
        self.assertEqual(PlayerNotification.objects.filter(match=self.match, is_read=False).count(), 1)
        # el jugador enlazado sale de la convocatoria
        self.record.players.set([self.unlinked])
        views._notify_convoked_players(self.record, self.match, _Actor())
        self.assertEqual(PlayerNotification.objects.filter(match=self.match, is_read=False).count(), 0)

    def test_read_notification_survives_deconvocation(self):
        views._notify_convoked_players(self.record, self.match, _Actor())
        PlayerNotification.objects.filter(match=self.match).update(is_read=True)
        self.record.players.set([self.unlinked])
        views._notify_convoked_players(self.record, self.match, _Actor())
        # ya leída => no se borra
        self.assertEqual(PlayerNotification.objects.filter(match=self.match).count(), 1)

    def test_mark_read_endpoint(self):
        views._notify_convoked_players(self.record, self.match, _Actor())
        self.client.force_login(self.user)
        resp = self.client.post(reverse("player-notifications-read"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(PlayerNotification.objects.filter(target_user=self.user, is_read=False).count(), 0)

    def test_mark_read_requires_login(self):
        resp = self.client.post(reverse("player-notifications-read"))
        self.assertIn(resp.status_code, (301, 302))


class LineupPublishNotificationTests(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga LP", slug="liga-lp", region="Málaga")
        self.season = Season.objects.create(competition=self.comp, name="2025/26")
        self.team = Team.objects.create(name="LP Test FC", slug="lp-test-fc")
        self.u_starter = User.objects.create_user(username="lp_starter", password="x")
        self.u_bench = User.objects.create_user(username="lp_bench", password="x")
        self.starter = Player.objects.create(team=self.team, name="Titular", user=self.u_starter, number=4)
        self.bench = Player.objects.create(team=self.team, name="Suplente", user=self.u_bench, number=12)
        self.match = Match.objects.create(home_team=self.team, season=self.season, round="J1")
        self.record = ConvocationRecord.objects.create(
            team=self.team, match=self.match, opponent_name="Rival CF",
            match_date=datetime.date(2026, 2, 1),
        )
        self.record.players.set([self.starter, self.bench])

    def test_publish_notifies_status_per_player(self):
        n = views._notify_lineup_players(
            self.record, self.match, {str(self.starter.id)}, _Actor()
        )
        self.assertEqual(n, 2)
        starter_notif = PlayerNotification.objects.get(target_user=self.u_starter, kind=PlayerNotification.KIND_LINEUP)
        bench_notif = PlayerNotification.objects.get(target_user=self.u_bench, kind=PlayerNotification.KIND_LINEUP)
        self.assertEqual(starter_notif.title, "Eres titular")
        self.assertTrue(starter_notif.payload.get("starter"))
        self.assertEqual(bench_notif.title, "Estás en el banquillo")
        self.assertFalse(bench_notif.payload.get("starter"))

    def test_republish_reflects_new_status(self):
        views._notify_lineup_players(self.record, self.match, {str(self.starter.id)}, _Actor())
        # se invierte el 11: ahora el banquillo es titular
        views._notify_lineup_players(self.record, self.match, {str(self.bench.id)}, _Actor())
        self.assertEqual(
            PlayerNotification.objects.filter(match=self.match, kind=PlayerNotification.KIND_LINEUP).count(), 2
        )
        self.assertEqual(
            PlayerNotification.objects.get(target_user=self.u_bench, kind=PlayerNotification.KIND_LINEUP).title,
            "Eres titular",
        )

    def test_publish_endpoint_requires_staff(self):
        # un jugador autenticado no puede publicar
        self.client.force_login(self.u_starter)
        resp = self.client.post(reverse("initial-eleven-publish"))
        self.assertEqual(resp.status_code, 403)
