from unittest.mock import patch

from django.test import SimpleTestCase

from football import session_import_services


class SessionImportServicesTests(SimpleTestCase):
    def test_open_pil_rgb_from_bytes_returns_none_without_image_backend(self):
        with patch('football.session_import_services.Image', None):
            img = session_import_services.open_pil_rgb_from_bytes(b'not-an-image')

        self.assertIsNone(img)

    def test_extract_image_text_returns_empty_without_image_backend(self):
        with patch('football.session_import_services.Image', None):
            text = session_import_services.extract_image_text_via_tesseract(b'not-an-image')

        self.assertEqual(text, '')

    def test_extract_image_text_returns_empty_without_tesseract_backend(self):
        with patch('football.session_import_services.pytesseract', None):
            text = session_import_services.extract_image_text_via_tesseract(b'not-an-image')

        self.assertEqual(text, '')
