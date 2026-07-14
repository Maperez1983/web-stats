from datetime import date
import base64
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

from football.models import (
    AppUserRole,
    SessionTask,
    SessionTaskExportJob,
    Team,
    TrainingMicrocycle,
    TrainingSession,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
)


class SessionTaskEditorProApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='editor-pro-user',
            email='editor-pro@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.team = Team.objects.create(name='Equipo editor pro', slug='equipo-editor-pro', is_primary=True)
        self.workspace = Workspace.objects.create(
            name='Workspace editor pro',
            slug='workspace-editor-pro',
            kind=Workspace.KIND_CLUB,
            primary_team=self.team,
            owner_user=self.user,
            enabled_modules={'sessions': True},
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
            module_access={'sessions': True},
        )
        WorkspaceTeam.objects.create(workspace=self.workspace, team=self.team, is_default=True)
        self.microcycle = TrainingMicrocycle.objects.create(
            team=self.team,
            title='Micro editor pro',
            week_start=date(2026, 7, 13),
            week_end=date(2026, 7, 19),
        )
        self.session = TrainingSession.objects.create(
            microcycle=self.microcycle,
            session_date=date(2026, 7, 14),
            focus='Salida de balon',
            duration_minutes=90,
        )
        self.task = SessionTask.objects.create(
            session=self.session,
            title='Tarea editor pro',
            block=SessionTask.BLOCK_MAIN_1,
            duration_minutes=18,
            tactical_layout={
                'meta': {
                    'scope': 'coach',
                    'analysis': {
                        'task_sheet': {
                            'description': 'Conservar y progresar ante presion alta.',
                            'materials': '8 conos, 2 porterias',
                            'players': '6v6 + 2 porteros',
                        }
                    },
                }
            },
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = self.workspace.id
        session.save()

    def _sample_png_bytes(self):
        if Image is None:
            return (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02'
                b'\x08\x02\x00\x00\x00\xfd\xd4\x9as\x00\x00\x00\x0cIDATx\x9cc`\xf8\xcf'
                b'\xc0\x00\x00\x04\x00\x01\xe2&\x05\x9b\x00\x00\x00\x00IEND\xaeB`\x82'
            )
        image = Image.new('RGB', (16, 16), '#1f7a3f')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_editor_document_api_returns_unified_payload(self):
        self.task.tactical_layout = {
            'meta': {
                'scope': 'coach',
                'analysis': {
                    'task_sheet': {
                        'description': 'Conservar y progresar ante presion alta.',
                        'materials': '8 conos, 2 porterias',
                        'players': '6v6 + 2 porteros',
                    }
                },
                'graphic_editor': {
                    'canvas_state': {
                        'version': '5.3.0',
                        'objects': [
                            {'id': 'cone-1', 'type': 'circle', 'left': 120, 'top': 140, 'radius': 14, 'fill': '#f97316'},
                        ],
                    },
                    'canvas_width': 1280,
                    'canvas_height': 720,
                },
            }
        }
        self.task.save(update_fields=['tactical_layout'])
        response = self.client.get(reverse('session-task-editor-document-api', args=[self.task.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        document = payload.get('document') or {}
        self.assertEqual(document.get('task', {}).get('id'), self.task.id)
        self.assertTrue(document.get('engine', {}).get('single_document'))
        self.assertTrue(document.get('engine', {}).get('single_3d_engine'))
        self.assertIn('exports', document)
        self.assertEqual(document.get('graphic', {}).get('canvas_width'), 1280)
        self.assertEqual(document.get('graphic', {}).get('canvas_height'), 720)
        self.assertEqual(len(document.get('graphic', {}).get('canvas_state', {}).get('objects', [])), 1)
        self.assertIn('graphic_save', document.get('urls', {}))

    def test_editor_pro_page_includes_built_bundle_reference(self):
        response = self.client.get(reverse('session-task-editor-pro', args=[self.task.id]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8', errors='ignore')
        self.assertIn('football/editor-pro/tactical-editor.css', html)
        self.assertIn('football/editor-pro/tactical-editor.js', html)
        self.assertIn('data-document-url="', html)

    def test_export_jobs_api_persists_real_job_row(self):
        response = self.client.post(
            reverse('session-task-export-jobs-api', args=[self.task.id]),
            data='{"kind":"pdf_club"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionTaskExportJob.objects.filter(task=self.task).count(), 1)
        job = SessionTaskExportJob.objects.get(task=self.task)
        self.assertEqual(job.kind, SessionTaskExportJob.KIND_PDF_CLUB)
        self.assertEqual(job.status, SessionTaskExportJob.STATUS_DONE)

    def test_ai_preview_job_generates_preview_and_document_exposes_it(self):
        self.task.task_preview_image.save('task-preview.png', ContentFile(self._sample_png_bytes()), save=True)
        response = self.client.post(
            reverse('session-task-export-jobs-api', args=[self.task.id]),
            data='{"kind":"ai_preview"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        job = SessionTaskExportJob.objects.filter(task=self.task, kind=SessionTaskExportJob.KIND_AI_PREVIEW).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, SessionTaskExportJob.STATUS_DONE)
        document_response = self.client.get(reverse('session-task-editor-document-api', args=[self.task.id]))
        self.assertEqual(document_response.status_code, 200)
        document = document_response.json().get('document') or {}
        self.assertTrue(bool(document.get('ai', {}).get('generated')))
        self.assertIn('/ai-preview/', str(document.get('ai', {}).get('preview_url') or ''))
        ai_preview_response = self.client.get(reverse('session-task-ai-preview-file', args=[self.task.id]))
        self.assertEqual(ai_preview_response.status_code, 200)
        self.assertIn(ai_preview_response['Content-Type'], ['image/jpeg', 'image/png', 'image/webp'])

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-openai-key', 'OPENAI_IMAGE_MODEL': 'gpt-image-1'}, clear=False)
    @patch('football.views.requests.post')
    def test_ai_preview_job_uses_openai_when_available(self, mock_post):
        sample_png_b64 = base64.b64encode(self._sample_png_bytes()).decode('ascii')

        class _Response:
            ok = True
            status_code = 200

            def json(self):
                return {'data': [{'b64_json': sample_png_b64}]}

        mock_post.return_value = _Response()
        response = self.client.post(
            reverse('session-task-export-jobs-api', args=[self.task.id]),
            data='{"kind":"ai_preview"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.task.refresh_from_db()
        ai_meta = (((self.task.tactical_layout or {}).get('meta') or {}).get('ai') or {})
        self.assertEqual(ai_meta.get('generated_preview_provider_v1'), 'openai')
        self.assertEqual(ai_meta.get('generated_preview_model_v1'), 'gpt-image-1')
        self.assertTrue(str(ai_meta.get('generated_preview_data_v1') or '').startswith('data:image/'))
