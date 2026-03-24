from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from football.models import UserInvitation
from football.staff_briefing import build_weekly_staff_brief
from football.views import SCRAPE_LOCK_KEY


class WriteEndpointAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='coach',
            email='coach@example.com',
            password='pass-1234',
        )

    def test_refresh_requires_authentication(self):
        response = self.client.post(reverse('dashboard-refresh'))
        self.assertEqual(response.status_code, 401)

    def test_save_convocation_requires_authentication(self):
        response = self.client.post(
            reverse('convocation-save'),
            data='[]',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_refresh_is_rate_limited_when_lock_exists(self):
        self.client.force_login(self.user)
        cache.set(SCRAPE_LOCK_KEY, '1', timeout=60)
        response = self.client.post(reverse('dashboard-refresh'))
        self.assertEqual(response.status_code, 429)
        cache.delete(SCRAPE_LOCK_KEY)

    def test_dashboard_page_requires_login(self):
        response = self.client.get(reverse('dashboard-home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_dashboard_data_requires_login(self):
        response = self.client.get(reverse('dashboard-data'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


class StaffBriefingTests(TestCase):
    def test_build_weekly_staff_brief_summarizes_availability(self):
        brief = build_weekly_staff_brief(
            player_cards=[
                {'player_id': 1, 'name': 'Portero', 'position': 'Portero', 'minutes': 900, 'pt': 10, 'pj': 10},
                {'player_id': 2, 'name': 'Central', 'position': 'Central', 'minutes': 850, 'pt': 9, 'pj': 10},
                {'player_id': 3, 'name': 'Medio', 'position': 'Mediocentro', 'minutes': 700, 'pt': 8, 'pj': 10},
            ],
            active_injury_ids={2},
            sanctioned_player_ids={3},
            convocation_player_ids={1},
            next_match={'round': 'Jornada 24', 'date': '2026-03-29', 'time': '18:00', 'location': 'Casa', 'opponent': 'Marbella'},
        )

        self.assertEqual(brief['availability'][0]['value'], 1)
        self.assertEqual(brief['availability'][1]['value'], 1)
        self.assertEqual(brief['availability'][2]['value'], 1)
        self.assertIn('Marbella', brief['headline'])
        self.assertTrue(any('lesión' in line for line in brief['alerts']))


class InvitationAcceptanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='jugador',
            email='jugador@example.com',
            password='old-pass-1234',
            is_active=False,
        )
        self.invitation = UserInvitation.objects.create(
            user=self.user,
            token='token-prueba',
            email=self.user.email,
            expires_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )

    def test_accept_invitation_sets_password_and_invalidates_token(self):
        response = self.client.post(
            reverse('user-invite-accept', args=[self.invitation.token]),
            {
                'password': 'NuevaPassSegura2026!',
                'password_confirm': 'NuevaPassSegura2026!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.invitation.refresh_from_db()
        self.user.refresh_from_db()
        self.assertFalse(self.invitation.is_active)
        self.assertIsNotNone(self.invitation.accepted_at)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password('NuevaPassSegura2026!'))
