from django.test import SimpleTestCase

from football.normalization import normalize_person_name, normalize_position_value
from football.templatetags.football_extras import display_position, display_text


class DisplayHelperTests(SimpleTestCase):
    def test_display_text_normalizes_spacing_and_case(self):
        self.assertEqual(display_text('  JUAN   PEREZ  '), 'Juan Perez')
        self.assertEqual(display_text('C.D.  CANTORIA 2017  F.C.'), 'C.D. Cantoria 2017 F.C.')
        self.assertEqual(display_text('Jugador QA'), 'Jugador QA')

    def test_display_position_expands_common_abbreviations(self):
        self.assertEqual(display_position('MC'), 'Mediocentro')
        self.assertEqual(display_position('DFC'), 'Defensa central')
        self.assertEqual(display_position('mp'), 'Mediapunta')
        self.assertEqual(display_position('Lateral derecho'), 'Lateral derecho')

    def test_storage_normalizers_apply_canonical_format(self):
        self.assertEqual(normalize_person_name('  JUAN   PEREZ  '), 'Juan Perez')
        self.assertEqual(normalize_person_name('Jugador QA'), 'Jugador QA')
        self.assertEqual(normalize_person_name('C.D. CANTORIA 2017 F.C.', preserve_acronyms=True), 'C.D. Cantoria 2017 F.C.')
        self.assertEqual(normalize_position_value('medio centro'), 'MC')
        self.assertEqual(normalize_position_value('carrilero izquierdo'), 'CARRILERO I')
        self.assertEqual(normalize_position_value('Mediapunta'), 'MP')
