from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from football import healthchecks, pdf_services


class PdfServicesTests(SimpleTestCase):
    def test_returns_html_when_weasyprint_is_unavailable_and_pdf_not_forced(self):
        request = RequestFactory().get('/pdf/')

        with patch.object(pdf_services, 'weasyprint', None):
            response = pdf_services.build_pdf_response_or_html_fallback(
                request,
                '<p>fallback</p>',
                'demo',
                force_pdf=False,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')
        self.assertIn(b'fallback', response.content)

    def test_returns_503_when_weasyprint_is_unavailable_and_pdf_is_forced(self):
        request = RequestFactory().get('/pdf/')

        with patch.object(pdf_services, 'weasyprint', None):
            response = pdf_services.build_pdf_response_or_html_fallback(
                request,
                '<p>fallback</p>',
                'demo',
                force_pdf=True,
            )

        self.assertEqual(response.status_code, 503)

    def test_successful_pdf_response_sets_cache_headers(self):
        request = RequestFactory().get('/pdf/')
        fake_weasyprint = SimpleNamespace()

        with patch.object(pdf_services, 'weasyprint', fake_weasyprint):
            with patch.object(pdf_services, 'pydyf_compat_status', return_value=(True, '0.10.0')):
                with patch.object(pdf_services, 'render_pdf_bytes_with_error', return_value=(b'%PDF-1.4', '')):
                    response = pdf_services.build_pdf_response_or_html_fallback(
                        request,
                        '<p>pdf</p>',
                        'demo',
                        inline=True,
                        force_pdf=True,
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'no-store, max-age=0')
        self.assertEqual(response['Content-Disposition'], 'inline; filename="demo.pdf"')


class HealthcheckPdfDependencyTests(SimpleTestCase):
    def test_weasyprint_status_reports_pydyf_incompatibility(self):
        with patch.object(healthchecks.pdf_services, 'weasyprint', SimpleNamespace()):
            with patch.object(healthchecks.pdf_services, 'pydyf_compat_status', return_value=(False, '0.11.0')):
                status = healthchecks._dependency_status()

        self.assertFalse(status['weasyprint']['ok'])
        self.assertIn('pydyf incompatible (0.11.0)', status['weasyprint']['detail'])
