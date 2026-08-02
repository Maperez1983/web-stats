import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from football import views
from football.models import Competition, ConvocationRecord, Match, MatchEvent, Season, Team


class MatchdayFinalizeTests(TestCase):
    def setUp(self):
        competition = Competition.objects.create(name="Liga cierre", slug="liga-cierre", region="Malaga")
        season = Season.objects.create(competition=competition, name="2026/27")
        self.team = Team.objects.create(name="Equipo cierre", slug="equipo-cierre")
        rival = Team.objects.create(name="Rival cierre", slug="rival-cierre")
        self.match = Match.objects.create(
            home_team=self.team,
            away_team=rival,
            season=season,
            date=datetime.date(2026, 8, 2),
            context=Match.CONTEXT_FRIENDLY,
        )
        self.convocation = ConvocationRecord.objects.create(
            team=self.team,
            match=self.match,
            is_current=True,
        )
        self.pending = [
            MatchEvent.objects.create(
                match=self.match,
                minute=10 + index,
                event_type="Pase",
                result="OK",
                source_file="registro-acciones",
                system="touch-field",
            )
            for index in range(2)
        ]
        self.recovered = MatchEvent.objects.create(
            match=self.match,
            minute=55,
            event_type="Robo",
            result="OK",
            source_file="manual-recovery",
            system="touch-field-final",
            raw_data={"recovery": True},
        )

    def _request(self):
        request = RequestFactory().post("/registro-acciones/finalizar/")
        request.user = get_user_model().objects.create_user(
            username=f"staff-{get_user_model().objects.count()}",
            password="test-pass",
        )
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    @patch("football.views._persist_match_ratings")
    def test_common_close_is_idempotent_and_releases_convocation(self, persist_ratings):
        first = views._finalize_matchday_common(self._request(), self.team, self.match)

        self.assertEqual(first["updated"], 2)
        self.assertEqual(
            MatchEvent.objects.filter(match=self.match, system="touch-field-final").count(),
            3,
        )
        self.match.refresh_from_db()
        self.convocation.refresh_from_db()
        self.assertTrue(self.match.is_closed)
        self.assertFalse(self.convocation.is_current)
        self.assertTrue(MatchEvent.objects.filter(id=self.recovered.id, source_file="manual-recovery").exists())

        second = views._finalize_matchday_common(self._request(), self.team, self.match)

        self.assertEqual(second["updated"], 0)
        self.assertEqual(MatchEvent.objects.filter(match=self.match).count(), 3)
        self.assertEqual(persist_ratings.call_count, 2)
