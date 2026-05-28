from django.test import SimpleTestCase
from types import SimpleNamespace
from unittest.mock import patch

from football import dashboard_services, session_pdf, tactical_views, team_media_services, video_studio_views, view_delegates, views
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
            self.assertTrue(callable(getattr(dashboard_services, name)))

    def test_session_pdf_delegates_resolve_existing_views(self):
        for name in session_pdf.SESSION_PDF_DELEGATED_VIEW_NAMES:
            self.assertIs(resolve_view(name), getattr(views, name))

    def test_delegate_preserves_public_name_without_eager_view_import(self):
        delegated = view_delegate('kpi_audit')
        self.assertEqual(delegated.__name__, 'kpi_audit')
        self.assertEqual(delegated.__qualname__, 'kpi_audit')

    def test_delegate_accepts_service_style_keyword_request(self):
        def fake_view(*args, **kwargs):
            return args, kwargs

        with patch.object(view_delegates, 'resolve_view', return_value=fake_view):
            delegated = view_delegate('compute_player_dashboard')
            args, kwargs = delegated('team', request='request', force_refresh=True)

        self.assertEqual(args, ('team',))
        self.assertEqual(kwargs, {'request': 'request', 'force_refresh': True})

    def test_session_pdf_folded_text_normalizes_accents(self):
        self.assertEqual(session_pdf._normalize_folded_text('Presión tras pérdida'), 'presion tras perdida')

    def test_session_pdf_imported_task_detection_keeps_manual_tasks_out(self):
        manual = SimpleNamespace(tactical_layout={'meta': {'source': 'manual-studio'}}, task_pdf=None, notes='')
        imported = SimpleNamespace(tactical_layout={'meta': {'source': 'manual-studio', 'pdf_source_name': 'a.pdf'}}, task_pdf=None, notes='')
        self.assertFalse(session_pdf._is_imported_task(manual))
        self.assertTrue(session_pdf._is_imported_task(imported))

    def test_team_media_services_normalize_universo_paths(self):
        self.assertEqual(
            team_media_services.absolute_universo_url('/pnfg/pimg/escudo.png'),
            'https://www.universorfaf.es/pnfg/pimg/escudo.png',
        )
        self.assertEqual(team_media_services.absolute_universo_url('/media/local.png'), '/media/local.png')

    def test_team_media_services_block_universo_external_images_by_default(self):
        self.assertEqual(
            team_media_services.sanitize_universo_external_image(
                'https://www.universorfaf.es/pnfg/pimg/escudo.png'
            ),
            '',
        )

    def test_team_media_services_expose_initials_and_color_seed_for_view_wrappers(self):
        team = SimpleNamespace(id=7, slug='benagalbon-a', name='Benagalbon A')
        self.assertEqual(team_media_services.team_initials('CD Benagalbon'), views._team_initials('CD Benagalbon'))
        self.assertEqual(team_media_services.team_color_seed(team), views._team_color_seed(team))

    def test_session_pdf_uses_extracted_crest_service(self):
        team = SimpleNamespace(id=7, crest_image=None, crest_url='', is_primary=False, slug='demo', name='Demo', short_name='DM')
        self.assertEqual(
            session_pdf.resolve_team_crest_url(None, team, fallback_static=None, sync=False),
            '/team/7/crest.svg',
        )
