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

    def test_extracts_competition_code(self):
        self.assertEqual(pcs.extract_preferente_competition_code(self.html), '26717')

    def test_extracts_competition_code_empty_without_links(self):
        self.assertEqual(pcs.extract_preferente_competition_code('<html>nada</html>'), '')

    def test_team_id_from_url(self):
        self.assertEqual(pcs._preferente_team_id_from_url('https://www.lapreferente.com/E147/cd-benagalbon'), '147')
        self.assertEqual(pcs._preferente_team_id_from_url('https://www.lapreferente.com/no-id/foo'), '')

    def test_next_match_returns_empty_on_php_error_preseason(self):
        # Respuesta real del endpoint jaxon en pretemporada (sin jornada sorteada).
        php_error = (
            '<br /><b>Warning</b>: Trying to access array offset ... '
            '<b>Fatal error</b>: Uncaught Error: Call to a member function fetch_assoc() on bool'
        )
        self.assertEqual(pcs.parse_preferente_next_match(php_error), {})

    def test_next_match_returns_empty_on_blank_panel(self):
        self.assertEqual(pcs.parse_preferente_next_match(''), {})
        self.assertEqual(pcs.parse_preferente_next_match('<div></div>'), {})

    def test_fetch_next_match_returns_empty_without_team_id_in_url(self):
        self.assertEqual(pcs.fetch_preferente_next_match('https://www.lapreferente.com/no-id/foo'), {})

    def test_active_season_extra_column_does_not_scramble(self):
        # Maqueta de temporada activa: una columna extra antes de PT desplaza los índices
        # fijos (bug "PJ=puntos / PTS vacío"). El parser se ancla en title="Puntos del...".
        html = (
            '<table id="tableClasif"><tr>'
            '<th></th><th colspan="2">Equipo</th><th title="Puntos">PT</th>'
            '<th title="Partidos Jugados">PJ</th><th>PG</th><th>PE</th><th>PP</th>'
            '<th>GF</th><th>GC</th><th>DG</th></tr>'
            '<tr>'
            '<td>4</td>'
            '<td><a href="E147C26717-1/cd-benagalbon"><img/></a></td>'
            '<td><a href="E147C26717-1/cd-benagalbon">C.D. Benagalbón</a></td>'
            '<td class="extra">&nbsp;</td>'
            '<td title="Puntos del C.D. Benagalbón">55</td>'
            '<td>30</td><td>16</td><td>7</td><td>7</td>'
            '<td>44</td><td>20</td><td>24</td></tr></table>'
        )
        rows = pcs.parse_preferente_standings(html)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['full_name'], 'C.D. Benagalbón')
        self.assertEqual(row['points'], 55)
        self.assertEqual(row['played'], 30)
        self.assertEqual(row['wins'], 16)
        self.assertEqual(row['goals_for'], 44)
        self.assertEqual(row['goals_against'], 20)
        self.assertEqual(row['goal_difference'], 24)

    def test_impossible_played_discards_table(self):
        # Guardia: si PJ sale imposible (>60), no devolvemos clasificación revuelta.
        html = (
            '<table id="tableClasif"><tr>'
            '<th></th><th>Equipo</th><th>PT</th><th>PJ</th><th>PG</th><th>PE</th>'
            '<th>PP</th><th>GF</th><th>GC</th><th>DG</th></tr>'
            '<tr><td>1</td><td></td><td>Test FC</td><td></td><td>99</td><td>0</td>'
            '<td>0</td><td>0</td><td>5</td><td>44</td><td></td></tr></table>'
        )
        self.assertEqual(pcs.parse_preferente_standings(html), [])

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
