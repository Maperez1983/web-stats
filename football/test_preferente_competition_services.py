from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from football import preferente_competition_services as pcs

FIXTURE = Path(settings.BASE_DIR) / 'football' / 'test_fixtures' / 'preferente_standings.html'


class ParsePreferenteStandingsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = FIXTURE.read_text(encoding='utf-8')
        cls.rows = pcs.parse_preferente_standings(cls.html)

    def test_parses_all_eighteen_teams(self):
        self.assertEqual(len(self.rows), 18)

    def test_rows_are_ranked_and_sequential(self):
        self.assertEqual([r['rank'] for r in self.rows], list(range(1, 19)))

    def test_team_names_and_codes(self):
        first = self.rows[0]
        self.assertEqual(first['full_name'], 'Atlético Jaén F.C.')
        self.assertEqual(first['team'], 'ATLÉTICO JAÉN F.C.')
        self.assertTrue(first['team_code'].startswith('E'))
        names = {r['full_name'] for r in self.rows}
        self.assertIn('C.D. Benagalbón', names)

    def test_numeric_fields_are_ints(self):
        for row in self.rows:
            for key in ('played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'goal_difference', 'points'):
                self.assertIsInstance(row[key], int, f'{key} no es int en {row["full_name"]}')

    def test_no_header_or_junk_rows(self):
        for row in self.rows:
            self.assertNotEqual(row['full_name'].lower(), 'equipo')
            self.assertGreater(row['rank'], 0)

    def test_block_marker_returns_empty(self):
        self.assertEqual(pcs.parse_preferente_standings('<html>Just a moment... captcha</html>'), [])

    def test_missing_table_returns_empty(self):
        self.assertEqual(pcs.parse_preferente_standings('<html><body>no table here</body></html>'), [])

    def test_empty_input(self):
        self.assertEqual(pcs.parse_preferente_standings(''), [])

    def test_derives_points_and_goal_difference_when_absent(self):
        html = (
            '<table id="tableClasif"><tr>'
            '<th></th><th>Equipo</th><th>PT</th><th>PJ</th><th>PG</th><th>PE</th>'
            '<th>PP</th><th>GF</th><th>GC</th><th>DG</th></tr>'
            '<tr><td>1</td><td></td><td>Test FC</td><td></td><td>5</td><td>3</td>'
            '<td>1</td><td>1</td><td>9</td><td>4</td><td></td></tr></table>'
        )
        rows = pcs.parse_preferente_standings(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['points'], 10)  # 3*3 + 1
        self.assertEqual(rows[0]['goal_difference'], 5)  # 9 - 4
