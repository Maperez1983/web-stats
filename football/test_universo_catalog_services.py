from django.test import SimpleTestCase

from football import universo_catalog_services


class UniversoCatalogServicesTests(SimpleTestCase):
    def test_parse_capture_form_payload_extracts_fields(self):
        raw_payload = (
            'Content-Disposition: form-data; name="id_season"\r\n\r\n42\r\n'
            'Content-Disposition: form-data; name="id_competition"\r\n\r\n45030612\r\n--'
        )

        parsed = universo_catalog_services.parse_capture_form_payload(raw_payload)

        self.assertEqual(parsed['id_season'], '42')
        self.assertEqual(parsed['id_competition'], '45030612')

    def test_build_universo_competition_catalog_indexes_capture_items(self):
        payload = {
            'items': [
                {
                    'url': 'https://www.universorfaf.es/api/competition/get-competitions',
                    'request_post_data': 'Content-Disposition: form-data; name="id_season"\r\n\r\n42\r\n--',
                    'json': {
                        'competiciones': [
                            {
                                'codigo': '45030612',
                                'nombre': 'Liga Senior (Malaga)',
                                'NombreCategoria': 'Senior',
                                'TipoJuego': 'F11',
                                'FechaInicio': '2025-09-01',
                                'FechaFin': '2026-05-31',
                            }
                        ]
                    },
                },
                {
                    'url': 'https://www.universorfaf.es/api/competition/get-groups',
                    'request_post_data': (
                        'Content-Disposition: form-data; '
                        'name="id_competition"\r\n\r\n45030612\r\n--'
                    ),
                    'json': {
                        'grupos': [
                            {
                                'codigo': '45030656',
                                'nombre': 'Grupo 2',
                                'total_jornadas': '30',
                                'total_equipos': '16',
                            }
                        ]
                    },
                },
                {
                    'url': 'https://www.universorfaf.es/api/competition/get-classification',
                    'json': {
                        'codigo_competicion': '45030612',
                        'codigo_grupo': '45030656',
                        'competicion': 'Liga Senior',
                        'grupo': 'Grupo 2',
                        'jornada': '12',
                        'clasificacion': [{'nombre': 'Equipo A'}],
                    },
                },
            ]
        }

        catalog = universo_catalog_services.build_universo_competition_catalog(payload)

        self.assertEqual(catalog['competitions']['45030612']['season_id'], '42')
        self.assertEqual(catalog['competitions']['45030612']['season_name'], '2025/2026')
        self.assertEqual(catalog['competitions']['45030612']['region'], 'Malaga')
        self.assertEqual(catalog['groups'][('45030612', '45030656')]['group_name'], 'Grupo 2')
        self.assertEqual(
            catalog['classifications'][('45030612', '45030656')]['rows'][0]['nombre'],
            'Equipo A',
        )

    def test_build_universo_competition_catalog_handles_invalid_payload(self):
        catalog = universo_catalog_services.build_universo_competition_catalog({'items': {}})

        self.assertEqual(catalog, {'competitions': {}, 'groups': {}, 'classifications': {}})
