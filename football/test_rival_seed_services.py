from django.test import TestCase

from football.models import Team
from football.rival_seed_services import seed_rivals_from_standings


class SeedRivalsFromStandingsTests(TestCase):
    def setUp(self):
        self.primary = Team.objects.create(name="CD Benagalbon", slug="cd-bena", is_primary=True)

    def _rows(self):
        return [
            {"full_name": "CD Benagalbon", "team_code": "100"},  # el propio equipo -> skip
            {"full_name": "Rival Uno", "team_code": "201", "crest_url": "http://x/1.png", "location": "Campo A"},
            {"full_name": "Rival Dos", "team_code": "202"},
        ]

    def test_creates_one_team_per_rival_excluding_self(self):
        result = seed_rivals_from_standings(self.primary, self._rows())
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["skipped"], 1)  # el propio equipo
        self.assertTrue(Team.objects.filter(external_id="201", is_primary=False).exists())
        r1 = Team.objects.get(external_id="201")
        self.assertEqual(r1.name, "Rival Uno")
        self.assertEqual(r1.home_stadium, "Campo A")

    def test_is_idempotent(self):
        seed_rivals_from_standings(self.primary, self._rows())
        again = seed_rivals_from_standings(self.primary, self._rows())
        self.assertEqual(again["created"], 0)
        # Cada rival de la clasificación existe exactamente una vez.
        self.assertEqual(Team.objects.filter(external_id="201").count(), 1)
        self.assertEqual(Team.objects.filter(external_id="202").count(), 1)

    def test_updates_empty_fields_only(self):
        seed_rivals_from_standings(self.primary, [{"full_name": "Rival Uno", "team_code": "201"}])
        # Segunda pasada con escudo -> rellena el que faltaba.
        result = seed_rivals_from_standings(
            self.primary, [{"full_name": "Rival Uno", "team_code": "201", "crest_url": "http://x/z.png"}]
        )
        self.assertEqual(result["updated"], 1)
        self.assertEqual(Team.objects.get(external_id="201").crest_url, "http://x/z.png")

    def test_matches_existing_team_by_name(self):
        existing = Team.objects.create(name="Rival Uno", slug="rival-uno", is_primary=False)
        result = seed_rivals_from_standings(self.primary, [{"full_name": "Rival Uno", "team_code": "201"}])
        self.assertEqual(result["created"], 0)
        existing.refresh_from_db()
        self.assertEqual(existing.external_id, "201")  # vincula el código al equipo ya existente

    def test_empty_inputs(self):
        self.assertEqual(seed_rivals_from_standings(None, [{"full_name": "X"}])["created"], 0)
        self.assertEqual(seed_rivals_from_standings(self.primary, [])["created"], 0)
