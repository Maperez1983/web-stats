import datetime
from unittest import mock

from django.test import SimpleTestCase

from football import competition_season_services as css


class CompetitionSeasonServicesTests(SimpleTestCase):
    def test_start_year_after_cut_stays_in_year(self):
        self.assertEqual(css.current_season_start_year(datetime.date(2026, 7, 1)), 2026)
        self.assertEqual(css.current_season_start_year(datetime.date(2026, 12, 31)), 2026)

    def test_start_year_before_cut_rolls_back(self):
        self.assertEqual(css.current_season_start_year(datetime.date(2026, 6, 30)), 2025)
        self.assertEqual(css.current_season_start_year(datetime.date(2026, 1, 1)), 2025)

    def test_current_season_name_formats(self):
        self.assertEqual(css.current_season_name(today=datetime.date(2026, 7, 23)), '2026/2027')
        self.assertEqual(css.current_universo_season_name(today=datetime.date(2026, 7, 23)), '2026-2027')

    def test_override_env_wins(self):
        with mock.patch.dict('os.environ', {css.SEASON_NAME_ENV: '2030/2031'}):
            self.assertEqual(css.current_season_name(today=datetime.date(2026, 7, 23)), '2030/2031')

    def test_start_month_env_override(self):
        with mock.patch.dict('os.environ', {css.SEASON_START_MONTH_ENV: '8'}):
            # Con corte en agosto, el 23 de julio todavía es la temporada anterior.
            self.assertEqual(css.current_season_start_year(datetime.date(2026, 7, 23)), 2025)

    def test_normalize_season_name(self):
        self.assertEqual(css.normalize_season_name('2026-27'), '2026/2027')
        self.assertEqual(css.normalize_season_name('2026 / 2027'), '2026/2027')
        self.assertEqual(css.normalize_season_name('2026–2027'), '2026/2027')
        self.assertEqual(css.normalize_season_name('sin año'), '')

    def test_season_names_match_ignores_separator(self):
        self.assertTrue(css.season_names_match('2026-2027', '2026/2027'))
        self.assertTrue(css.season_names_match('2026-27', '2026/2027'))
        self.assertFalse(css.season_names_match('2025/2026', '2026/2027'))

    def test_pick_current_season_row_prefers_calendar(self):
        rows = [{'nombre': '2025-2026'}, {'nombre': '2026-2027'}]
        chosen = css.pick_current_season_row(rows, today=datetime.date(2026, 7, 23))
        self.assertEqual(chosen['nombre'], '2026-2027')

    def test_pick_current_season_row_falls_back_to_first(self):
        rows = [{'nombre': '2019-2020'}, {'nombre': '2020-2021'}]
        chosen = css.pick_current_season_row(rows, today=datetime.date(2026, 7, 23))
        self.assertEqual(chosen['nombre'], '2019-2020')

    def test_pick_current_season_row_empty(self):
        self.assertIsNone(css.pick_current_season_row([]))
        self.assertIsNone(css.pick_current_season_row(None))
