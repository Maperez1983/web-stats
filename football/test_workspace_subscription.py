from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from football import workspace_subscription
from football import permissions
from football.models import Workspace


class WorkspaceSubscriptionTests(SimpleTestCase):
    def test_active_subscription_does_not_require_subscription(self):
        workspace = SimpleNamespace(kind=Workspace.KIND_CLUB, subscription_status='active', trial_expires_at=None)

        self.assertTrue(workspace_subscription.is_subscription_active(workspace))
        self.assertFalse(workspace_subscription.requires_subscription(workspace))

    def test_expired_trial_requires_subscription_for_club(self):
        workspace = SimpleNamespace(
            kind=Workspace.KIND_CLUB,
            subscription_status='trial',
            trial_expires_at=timezone.now() - timedelta(days=1),
        )

        self.assertFalse(workspace_subscription.is_trial_active(workspace))
        self.assertTrue(workspace_subscription.requires_subscription(workspace))

    def test_non_club_workspace_never_requires_subscription(self):
        workspace = SimpleNamespace(kind='personal', subscription_status='expired', trial_expires_at=None)

        self.assertFalse(workspace_subscription.requires_subscription(workspace))

    def test_apple_modular_paid_modules_limit_billable_access(self):
        workspace = SimpleNamespace(
            kind=Workspace.KIND_CLUB,
            subscription_status='active',
            plan_key='apple_modular',
            enabled_modules={},
            paid_modules={'coach_overview': True, 'players': True, 'sessions': True, 'abp_board': True, 'tactics': True},
        )

        self.assertTrue(permissions.workspace_has_module_for_user(workspace, 'tactics'))
        self.assertTrue(permissions.workspace_has_module_for_user(workspace, 'sessions'))
        self.assertFalse(permissions.workspace_has_module_for_user(workspace, 'match_actions'))
        self.assertTrue(permissions.workspace_has_module_for_user(workspace, 'dashboard'))
