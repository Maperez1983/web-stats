import datetime

from django.test import TestCase

from football import views
from football.models import (
    Competition,
    Match,
    Player,
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
        self.match = Match.objects.create(
            home_team=self.team, season=self.season, round="Amistoso",
            date=datetime.date(2026, 2, 1), context="friendly",
        )

    def test_creates_session_and_marks_present(self):
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2])
        self.assertEqual(marked, 2)
        session = TrainingSession.objects.filter(session_date=self.match.date).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, TrainingSession.STATUS_DONE)
        self.assertEqual(TrainingSessionAttendance.objects.filter(session=session).count(), 2)
        for a in TrainingSessionAttendance.objects.filter(session=session):
            self.assertEqual(a.status, TrainingSessionAttendance.STATUS_PRESENT)

    def test_idempotent_no_duplicate_session_or_attendance(self):
        views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2])
        views._ensure_match_attendance_session(self.match, self.team, [self.p1, self.p2])
        # una sola sesión para el partido y una asistencia por jugador
        self.assertEqual(TrainingSession.objects.filter(focus=f"Amistoso #{self.match.id}").count(), 1)
        session = TrainingSession.objects.get(focus=f"Amistoso #{self.match.id}")
        self.assertEqual(TrainingSessionAttendance.objects.filter(session=session).count(), 2)

    def test_no_date_returns_zero(self):
        self.match.date = None
        self.match.save(update_fields=["date"])
        marked = views._ensure_match_attendance_session(self.match, self.team, [self.p1])
        self.assertEqual(marked, 0)
