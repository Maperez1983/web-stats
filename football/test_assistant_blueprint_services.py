from django.test import SimpleTestCase

from football import assistant_blueprint_services


class AssistantBlueprintServicesTests(SimpleTestCase):
    def test_extract_assistant_bullets_normalizes_and_deduplicates(self):
        text = """
        - Presionar tras pérdida durante cinco segundos.
        1. Presionar tras pérdida durante cinco segundos.
        Objetivo: atacar espacio tras recuperación.
        DEMASIADO GENERICO EN MAYUSCULAS
        """

        bullets = assistant_blueprint_services.extract_assistant_bullets(text)

        self.assertEqual(
            bullets,
            [
                'Presionar tras pérdida durante cinco segundos.',
                'Objetivo: atacar espacio tras recuperación.',
            ],
        )

    def test_pick_assistant_bullets_for_goal_requires_three_matches(self):
        bullets = [
            'Presión coordinada sobre receptor.',
            'Orientar presión hacia banda.',
            'Saltos tras pase atrás.',
            'Circular balón con paciencia.',
        ]

        picked = assistant_blueprint_services.pick_assistant_bullets_for_goal(
            bullets,
            ['presión', 'salt'],
        )

        self.assertEqual(picked, bullets[:3])

    def test_assistant_html_list_escapes_items(self):
        html = assistant_blueprint_services.assistant_html_list(['Presionar <alto>', ''])

        self.assertEqual(html, '<ul><li>Presionar &lt;alto&gt;</li></ul>')
