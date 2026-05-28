from django.test import SimpleTestCase, TestCase

from football import assistant_blueprint_services
from football.models import AssistantKnowledgeDocument, TaskBlueprint, Team


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

    def test_extract_task_sheet_sections_derives_title_and_sections(self):
        text = """
        Capitulo 2
        3c3 + porteros
        Descripción
        Jugar en espacio reducido y finalizar tras pase atrás.
        Objetivos
        Atacar área con ventaja.
        Consideraciones
        Ajustar distancia entre líneas.
        """

        sections = assistant_blueprint_services.extract_task_sheet_sections(text)

        self.assertEqual(sections['title'], '3 c 3+porteros')
        self.assertEqual(sections['desc'], ['Jugar en espacio reducido y finalizar tras pase atrás.'])
        self.assertEqual(sections['behaviors'], ['Atacar área con ventaja.'])

    def test_infer_goal_key_uses_category_fallback(self):
        goal_key = assistant_blueprint_services.infer_goal_key_from_text(
            'Circular y fijar al rival.',
            category_hint='build_up',
        )

        self.assertEqual(goal_key, 'build_up')


class AssistantBlueprintCreationTests(TestCase):
    def test_create_idea_blueprints_from_document_creates_matching_blueprint(self):
        team = Team.objects.create(name='Test Team', slug='test-team')
        doc = AssistantKnowledgeDocument.objects.create(
            team=team,
            title='Manual presión',
            file='assistant-knowledge/manual.txt',
            sha256='abc123',
            mime_type='text/plain',
            extracted_text="""
            - Presión coordinada sobre receptor.
            - Orientar presión hacia banda.
            - Saltos tras pase atrás.
            - Circular balón con paciencia.
            """,
        )

        result = assistant_blueprint_services.create_idea_blueprints_from_document(team, doc)

        self.assertEqual(result, {'created': 1, 'updated': 0, 'skipped': 0})
        blueprint = TaskBlueprint.objects.get(team=team)
        self.assertEqual(blueprint.category, TaskBlueprint.CATEGORY_PRESS)
        self.assertEqual(blueprint.created_by, 'assistant_docs')
        self.assertEqual(blueprint.payload['meta']['goal'], 'pressing')
