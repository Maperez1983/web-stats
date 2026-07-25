import os
from datetime import timedelta

from django.utils import timezone

from .models import Workspace


def trial_days_default() -> int:
    try:
        value = int(str(os.getenv('TRIAL_DAYS', '7') or '7').strip())
    except Exception:
        value = 7
    return max(1, min(value, 30))


def trial_expires_at_default():
    return timezone.now() + timedelta(days=trial_days_default())


def is_subscription_active(workspace) -> bool:
    if not workspace:
        return False
    status = str(getattr(workspace, 'subscription_status', '') or '').strip().lower()
    if status != 'active':
        return False
    # A2: revalidar contra el fin de periodo. Si `subscription_current_period_end` ya pasó (p. ej.
    # se perdió el webhook de cancelación), no se considera activo. Margen de 2 días por el lag de
    # renovación/webhook para no cortar accesos legítimos durante la renovación.
    period_end = getattr(workspace, 'subscription_current_period_end', None)
    if period_end:
        try:
            if period_end + timedelta(days=2) < timezone.now():
                return False
        except Exception:
            pass
    return True


def is_trial_active(workspace) -> bool:
    if not workspace:
        return False
    status = str(getattr(workspace, 'subscription_status', '') or '').strip().lower()
    if status not in {'trial'}:
        return False
    expires_at = getattr(workspace, 'trial_expires_at', None)
    if not expires_at:
        return True
    try:
        return expires_at > timezone.now()
    except Exception:
        return False


def requires_subscription(workspace) -> bool:
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return False
    if is_subscription_active(workspace):
        return False
    status = str(getattr(workspace, 'subscription_status', '') or '').strip().lower()
    if not status:
        return False
    if status == 'trial':
        return not is_trial_active(workspace)
    if is_trial_active(workspace):
        return False
    return status in {'expired', 'past_due', 'canceled'}
