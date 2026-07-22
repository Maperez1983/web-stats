from django.test import SimpleTestCase

from football.templatetags.football_extras import display_position, display_text


class DisplayHelperTests(SimpleTestCase):
    def test_display_text_normalizes_spacing_and_case(self):
        self.assertEqual(display_text('  JUAN   PEREZ  '), 'Juan Perez')
        self.assertEqual(display_text('C.D.  CANTORIA 2017  F.C.'), 'C.D. Cantoria 2017 F.C.')

    def test_display_position_expands_common_abbreviations(self):
        self.assertEqual(display_position('MC'), 'Mediocentro')
        self.assertEqual(display_position('DFC'), 'Defensa central')
        self.assertEqual(display_position('mp'), 'Mediapunta')
        self.assertEqual(display_position('Lateral derecho'), 'Lateral derecho')
