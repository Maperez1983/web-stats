import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from football.models import AppUserRole


class CookieDomainSanitizerMiddlewareTests(TestCase):
    def test_strips_session_cookie_domain_when_host_mismatches(self):
        user = get_user_model().objects.create_user(username='cookie-mismatch', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        self.client.force_login(user)
        with override_settings(ALLOWED_HOSTS=['testserver', 'web-stats.onrender.com', 'segundajugada.es']):
            with override_settings(SESSION_COOKIE_DOMAIN='.segundajugada.es'):
                response = self.client.get(reverse('session-keepalive'), HTTP_HOST='web-stats.onrender.com', secure=True)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get('webstats_sessionid') or response.cookies.get('sessionid')
        self.assertIsNotNone(cookie)
        self.assertFalse(bool(cookie.get('domain')))

    def test_strips_cookie_domain_for_onrender_public_suffix(self):
        user = get_user_model().objects.create_user(username='cookie-onrender', password='pass-1234')
        AppUserRole.objects.create(user=user, role=AppUserRole.ROLE_COACH)
        self.client.force_login(user)
        with override_settings(ALLOWED_HOSTS=['testserver', 'web-stats.onrender.com']):
            with override_settings(SESSION_COOKIE_DOMAIN='.onrender.com'):
                response = self.client.get(reverse('session-keepalive'), HTTP_HOST='web-stats.onrender.com', secure=True)
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get('webstats_sessionid') or response.cookies.get('sessionid')
        self.assertIsNotNone(cookie)
        self.assertFalse(bool(cookie.get('domain')))


class LoginNextRedirectTests(TestCase):
    def setUp(self):
        self.player_user = get_user_model().objects.create_user(
            username='player-next',
            email='player-next@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.player_user, role=AppUserRole.ROLE_PLAYER)

    def test_player_login_ignores_platform_next(self):
        response = self.client.post(
            f"{reverse('login')}?next=/platform/",
            {'username': 'player-next', 'password': 'pass-1234'},
            secure=True,
        )
        self.assertIn(response.status_code, {301, 302})
        self.assertEqual(response['Location'], reverse('dashboard-home'))


class LoginSafariJsRedirectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='safari-user',
            email='safari-user@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        try:
            self.client.logout()
        except Exception:
            pass

    def test_safari_user_agent_uses_js_redirect_and_sets_session_cookie(self):
        safari_ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
        )
        with patch.dict(os.environ, {'LOGIN_JS_REDIRECT': 'auto'}, clear=False):
            response = self.client.post(
                reverse('login'),
                {'username': 'safari-user', 'password': 'pass-1234'},
                secure=True,
                HTTP_USER_AGENT=safari_ua,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'window.location.replace')
        self.assertIn(getattr(settings, 'SESSION_COOKIE_NAME', 'sessionid'), response.cookies)

    def test_login_js_redirect_can_be_disabled(self):
        safari_ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
        )
        with patch.dict(os.environ, {'LOGIN_JS_REDIRECT': 'false'}, clear=False):
            response = self.client.post(
                reverse('login'),
                {'username': 'safari-user', 'password': 'pass-1234'},
                secure=True,
                HTTP_USER_AGENT=safari_ua,
            )
        self.assertIn(response.status_code, {301, 302})
