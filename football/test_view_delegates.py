from django.test import SimpleTestCase
from types import SimpleNamespace

from football import dashboard_services, session_pdf, tactical_views, video_studio_views, views
from football.view_delegates import resolve_view, view_delegate


class ViewDelegateTests(SimpleTestCase):
    def test_video_studio_delegates_resolve_existing_views(self):
        for name in video_studio_views.VIDEO_STUDIO_VIEW_NAMES:
            self.assertIs(resolve_view(name), getattr(views, name))
            self.assertTrue(callable(getattr(video_studio_views, name)))

    def test_tactical_delegates_resolve_existing_views(self):
        for name in tactical_views.TACTICAL_DELEGATED_VIEW_NAMES:
            self.assertIs(resolve_view(name), getattr(views, name))
            self.assertTrue(callable(getattr(tactical_views, name)))

    def test_dashboard_delegates_resolve_existing_views(self):
        for name in dashboard_services.DASHBOARD_DELEGATED_VIEW_NAMES:
            self.assertIs(resolve_view(name), getattr(views, name))

    def test_session_pdf_delegates_resolve_existing_views(self):
        for name in session_pdf.SESSION_PDF_DELEGATED_VIEW_NAMES:
            self.assertIs(resolve_view(name), getattr(views, name))

    def test_delegate_preserves_public_name_without_eager_view_import(self):
        delegated = view_delegate('kpi_audit')
        self.assertEqual(delegated.__name__, 'kpi_audit')
        self.assertEqual(delegated.__qualname__, 'kpi_audit')

    def test_session_pdf_folded_text_normalizes_accents(self):
        self.assertEqual(session_pdf._normalize_folded_text('Presión tras pérdida'), 'presion tras perdida')

    def test_session_pdf_imported_task_detection_keeps_manual_tasks_out(self):
        manual = SimpleNamespace(tactical_layout={'meta': {'source': 'manual-studio'}}, task_pdf=None, notes='')
        imported = SimpleNamespace(tactical_layout={'meta': {'source': 'manual-studio', 'pdf_source_name': 'a.pdf'}}, task_pdf=None, notes='')
        self.assertFalse(session_pdf._is_imported_task(manual))
        self.assertTrue(session_pdf._is_imported_task(imported))
