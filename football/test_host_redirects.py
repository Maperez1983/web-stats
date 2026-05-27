import os
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from football.host_redirects import redirect_to_app_host_if_landing


class HostRedirectTests(SimpleTestCase):
    def test_redirects_landing_host_to_app_subdomain(self):
        request = RequestFactory().get('/onboarding/season/', HTTP_HOST='www.example.com', secure=True)

        with override_settings(ALLOWED_HOSTS=['www.example.com']):
            with patch.dict(os.environ, {'LANDING_HOSTS': 'www.example.com'}, clear=False):
                response = redirect_to_app_host_if_landing(request, path='/onboarding/season/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://app.example.com/onboarding/season/')

    def test_ignores_non_landing_host(self):
        request = RequestFactory().get('/onboarding/season/', HTTP_HOST='app.example.com', secure=True)

        with override_settings(ALLOWED_HOSTS=['app.example.com']):
            with patch.dict(os.environ, {'LANDING_HOSTS': 'www.example.com'}, clear=False):
                response = redirect_to_app_host_if_landing(request, path='/onboarding/season/')

        self.assertIsNone(response)
