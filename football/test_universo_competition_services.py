from django.test import SimpleTestCase

from football import universo_competition_services


class UniversoCompetitionServicesTests(SimpleTestCase):
    def test_payload_matches_category_ignores_senior_guardrail(self):
        payload = {'competition_name': '1 Andaluza Jaen'}

        self.assertTrue(universo_competition_services.universo_payload_matches_category(payload, 'Senior'))

    def test_payload_matches_category_checks_base_categories(self):
        payload = {'competition_name': 'Liga Cadete Provincial'}

        self.assertTrue(universo_competition_services.universo_payload_matches_category(payload, 'Cadete'))
        self.assertFalse(universo_competition_services.universo_payload_matches_category(payload, 'Alevin'))

    def test_serialize_universo_live_classification_normalizes_rows(self):
        payload = {
            'clasificacion': [
                {
                    'posicion': '2',
                    'nombre': 'Rival B',
                    'puntos': '12',
                    'pj': '5',
                    'pg': '4',
                    'pe': '0',
                    'pp': '1',
                    'gf': '10',
                    'gc': '4',
                },
                {
                    'posicion': '1',
                    'nombre': 'Rival A',
                    'puntos': '15',
                    'pj': '5',
                    'pg': '5',
                    'pe': '0',
                    'pp': '0',
                    'gf': '14',
                    'gc': '3',
                },
            ]
        }

        rows = universo_competition_services.serialize_universo_live_classification(payload)

        self.assertEqual([row['full_name'] for row in rows], ['Rival A', 'Rival B'])
        self.assertEqual(rows[0]['goal_difference'], 11)
        self.assertEqual(rows[1]['team'], 'RIVAL B')
