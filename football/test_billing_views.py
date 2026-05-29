import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from football.models import AppUserRole, Workspace, WorkspaceMembership


class BillingViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='billing-owner',
            email='billing-owner@example.com',
            password='pass-1234',
        )
        AppUserRole.objects.create(user=self.user, role=AppUserRole.ROLE_COACH)
        self.workspace = Workspace.objects.create(
            name='Billing Club',
            slug='billing-club',
            kind=Workspace.KIND_CLUB,
            owner_user=self.user,
            is_active=True,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_workspace_id'] = int(self.workspace.id)
        session.save()

    def test_billing_checkout_uses_stable_json_error_when_stripe_is_missing(self):
        with patch.dict(os.environ, {'STRIPE_SECRET_KEY': ''}):
            response = self.client.post(reverse('billing-checkout-session'), secure=True)

        self.assertEqual(response.status_code, 501)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertEqual(payload.get('code'), 'stripe_not_configured')

    def test_billing_page_uses_extracted_view(self):
        response = self.client.get(reverse('billing'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Billing Club')

    @patch('football.billing_views.stripe', None)
    def test_stripe_webhook_uses_extracted_view(self):
        response = self.client.post(
            reverse('stripe-webhook'),
            data=b'{}',
            content_type='application/json',
            secure=True,
        )

        self.assertEqual(response.status_code, 501)
        payload = response.json()
        self.assertFalse(payload.get('ok'))

    @patch.dict(os.environ, {'APPLE_SHARED_SECRET': 'test-secret'})
    @patch('football.billing_views._apple_verify_receipt')
    def test_apple_receipt_activates_matching_modules(self, verify_receipt):
        verify_receipt.return_value = {
            'status': 0,
            'latest_receipt_info': [
                {
                    'product_id': 'sj_analisis_monthly',
                    'expires_date_ms': '4102444800000',
                }
            ],
        }

        response = self.client.post(
            reverse('billing-apple-receipt'),
            data={
                'product_id': 'sj_analisis_monthly',
                'transaction_id': 'tx-1',
                'receipt_data': 'receipt',
            },
            secure=True,
        )

        self.assertEqual(response.status_code, 200)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.subscription_status, 'active')
        self.assertEqual(self.workspace.plan_key, 'apple_modular')
        self.assertTrue(self.workspace.paid_modules.get('analysis'))
        self.assertIn('apple_iap', self.workspace.paid_modules)
