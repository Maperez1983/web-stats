import datetime

from django.test import TestCase

from football import views
from football.models import (
    Competition,
    ConvocationRecord,
    Match,
    Player,
    PlayerStatistic,
    Season,
    Team,
    TrainingSession,
    TrainingSessionAttendance,
)


class MatchAttendanceSessionTests(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(name="Liga MA", slug="liga-ma", region="Málaga")
        self.season = Season.objects.create(competition=self.comp, name="2025/26")
        self.team = Team.objects.create(name="MA FC", slug="ma-fc")
        self.p1 = Player.objects.create(team=self.team, name="Uno")
        self.p2 = Player.objects.create(team=self.team, name="Dos")
        self.p3 = Player.objects.create(team=self.team, name="Tres")  # ni convocado ni con minutos
        self.match = Match.objects.create(
            home_team=self.team, season=self.season, round="Amistoso",
            date=datetime.date(2026, 2, 1), context="friendly",
        )

    def _convoke(self, *players):
        rec = ConvocationRecord.objects.create(team=self.team, match=self.match)
        rec.players.add(*players)
        return rec

    def test_marks_present_only_convoked(self):
        self._convoke(self.p1, self.p2)
        # Se pasa TODA la plantilla, pero solo deben marcarse los convocados (p1, p2), NO p3.
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2, self.p3])
        self.assertEqual(marked, 2)
        session = TrainingSession.objects.filter(session_date=self.match.date).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, TrainingSession.STATUS_DONE)
        present_ids = set(TrainingSessionAttendance.objects.filter(session=session).values_list("player_id", flat=True))
        self.assertEqual(present_ids, {self.p1.id, self.p2.id})
        for a in TrainingSessionAttendance.objects.filter(session=session):
            self.assertEqual(a.status, TrainingSessionAttendance.STATUS_PRESENT)

    def test_players_with_minutes_also_marked(self):
        # Sin convocatoria, pero p1 tiene minutos en el partido -> se marca; p3 (sin nada) no.
        PlayerStatistic.objects.create(
            player=self.p1, season=self.season, match=self.match,
            context="manual-match", name="manual_minutes", value=35.0,
        )
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2, self.p3])
        self.assertEqual(marked, 1)
        session = TrainingSession.objects.get(session_date=self.match.date)
        present_ids = set(TrainingSessionAttendance.objects.filter(session=session).values_list("player_id", flat=True))
        self.assertEqual(present_ids, {self.p1.id})

    def test_does_not_mark_whole_squad_when_no_convocation_or_minutes(self):
        # Regresión del bug: antes marcaba a TODA la plantilla aunque no hubiera convocatoria ni minutos.
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2, self.p3])
        self.assertEqual(marked, 0)

    def test_idempotent_no_duplicate_session_or_attendance(self):
        self._convoke(self.p1, self.p2)
        views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2, self.p3])
        views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2, self.p3])
        self.assertEqual(TrainingSession.objects.filter(focus=f"Amistoso #{self.match.id}").count(), 1)
        session = TrainingSession.objects.get(focus=f"Amistoso #{self.match.id}")
        self.assertEqual(TrainingSessionAttendance.objects.filter(session=session).count(), 2)

    def test_no_date_returns_zero(self):
        self._convoke(self.p1)
        self.match.date = None
        self.match.save(update_fields=["date"])
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1])
        self.assertEqual(marked, 0)
