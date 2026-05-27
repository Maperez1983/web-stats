import os
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import views as core_views
from .api_utils import api_error, api_ok
from .models import Workspace


def _workspace_from_request_for_billing(request):
    workspace = core_views._get_active_workspace(request)
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return None, HttpResponse('Selecciona un club (workspace) para gestionar la suscripción.', status=400)
    if not core_views._can_manage_workspace(request.user, workspace) and not core_views._can_access_platform(request.user):
        return None, HttpResponse('No tienes permisos para gestionar la suscripción.', status=403)
    return workspace, None


@login_required
def billing_page(request):
    workspace = core_views._get_active_workspace(request)
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return HttpResponse('Selecciona un club (workspace) para ver la suscripción.', status=400)
    if not core_views._can_manage_workspace(request.user, workspace) and not core_views._can_access_platform(request.user):
        return HttpResponse('No tienes permisos para gestionar la suscripción.', status=403)

    manual_msg = ''
    manual_err = ''
    allow_manual = bool(getattr(settings, 'DEBUG', False)) or str(os.getenv('ALLOW_MANUAL_BILLING', '0') or '').strip().lower() in {'1', 'true', 'yes', 'on'}

    def _manual_entitlements(plan_key: str, addons_csv: str = '') -> dict:
        plan_key = str(plan_key or '').strip().lower()
        addons = {a.strip().lower() for a in str(addons_csv or '').split(',') if a.strip()}

        if plan_key in {'basic', 'club_basic', 'core'}:
            return {
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': True,
                'manual_stats': True,
            }

        if plan_key in {'pro', 'club_pro', 'bundle'}:
            return {
                'dashboard': True,
                'coach_overview': True,
                'players': True,
                'convocation': True,
                'manual_stats': True,
                'match_actions': True,
                'sessions': True,
                'analysis': True,
                'abp_board': True,
                'tactics': True,
            }

        ent = {
            'dashboard': True,
            'coach_overview': True,
            'players': True,
            'convocation': True,
            'manual_stats': True,
        }
        if 'live' in addons:
            ent['match_actions'] = True
        if 'studio' in addons:
            ent['sessions'] = True
            ent['abp_board'] = True
        if 'analysis' in addons:
            ent['analysis'] = True
        if 'tactics' in addons:
            ent['tactics'] = True
        return ent

    if request.method == 'POST' and allow_manual:
        form_action = str(request.POST.get('form_action') or '').strip()
        if form_action == 'manual_set_plan':
            plan_key = str(request.POST.get('plan_key') or '').strip().lower() or 'pro'
            addons = str(request.POST.get('addons') or '').strip()
            try:
                entitlements = _manual_entitlements(plan_key, addons_csv=addons)
                workspace.plan_key = plan_key
                workspace.subscription_status = 'active'
                workspace.paid_modules = entitlements
                workspace.save(update_fields=['plan_key', 'subscription_status', 'paid_modules', 'updated_at'])
                manual_msg = 'Plan actualizado.'
            except Exception as exc:
                manual_err = f'No se pudo actualizar el plan: {exc.__class__.__name__}'

    expires_at = getattr(workspace, 'trial_expires_at', None)
    now = timezone.now()
    days_left = None
    if expires_at:
        try:
            days_left = max(0, int((expires_at - now).total_seconds() // 86400))
        except Exception:
            days_left = None
    status = str(getattr(workspace, 'subscription_status', '') or '').strip().lower() or 'trial'
    if status == 'trial' and expires_at and expires_at <= now:
        status = 'expired'
    price_map = core_views._stripe_price_map()
    addons_available = {}
    try:
        for key in ('live', 'studio', 'analysis', 'tactics'):
            addons_available[key] = bool((price_map.get((key, 'month')) or '').strip() or (price_map.get((key, 'year')) or '').strip())
    except Exception:
        addons_available = {}
    return render(
        request,
        'football/billing.html',
        {
            'workspace': workspace,
            'subscription_status': status,
            'trial_expires_at': expires_at,
            'trial_days_left': days_left,
            'stripe_ready': bool(str(os.getenv('STRIPE_SECRET_KEY', '') or '').strip()),
            'stripe_modular_ready': bool((core_views._stripe_price_map().get(('core', 'month')) or '').strip()),
            'stripe_modular_enabled': core_views._stripe_modular_billing_enabled(),
            'stripe_addons_available': addons_available,
            'allow_manual_billing': allow_manual,
            'manual_billing_message': manual_msg,
            'manual_billing_error': manual_err,
        },
    )


@login_required
@require_POST
def billing_checkout_session_api(request):
    workspace, error = _workspace_from_request_for_billing(request)
    if error:
        return error
    if not core_views._stripe_init():
        return api_error('Stripe no está configurado.', status=501, code='stripe_not_configured')

    plan_key = str(request.POST.get('plan_key') or request.GET.get('plan_key') or 'pro').strip().lower()
    interval = str(request.POST.get('interval') or request.GET.get('interval') or 'month').strip().lower()
    if interval not in {'month', 'year'}:
        interval = 'month'
    price_map = core_views._stripe_price_map()

    raw_addons = str(request.POST.get('addons') or request.GET.get('addons') or '').strip()
    addons = []
    if raw_addons:
        addons = [a.strip().lower() for a in re.split(r'[, ]+', raw_addons) if a.strip()]
    allowed_addons = {'live', 'studio', 'analysis', 'tactics'}
    addons = [a for a in addons if a in allowed_addons]

    line_items = []
    uses_modular = False
    core_price = (price_map.get(('core', interval)) or '').strip()
    if core_price and (plan_key in {'core', 'starter', 'basic'} or addons):
        uses_modular = True
        line_items.append({'price': core_price, 'quantity': 1})
        for addon in addons:
            pid = (price_map.get((addon, interval)) or '').strip()
            if not pid:
                return api_error(f'Módulo no disponible: {addon}.', status=500, code='addon_price_missing')
            line_items.append({'price': pid, 'quantity': 1})

    if not uses_modular:
        price_id = (price_map.get((plan_key, interval)) or '').strip()
        if not price_id:
            return api_error('Plan no disponible (missing price id).', status=500, code='plan_price_missing')
        line_items = [{'price': price_id, 'quantity': 1}]

    if core_views._workspace_is_subscription_active(workspace):
        return api_ok({'already_active': True})

    try:
        origin = request.build_absolute_uri('/').rstrip('/')
    except Exception:
        origin = ''
    success_url = f"{origin}{reverse('billing')}?status=success"
    cancel_url = f"{origin}{reverse('billing')}?status=cancel"

    customer_id = str(getattr(workspace, 'stripe_customer_id', '') or '').strip()
    customer_email = str(getattr(request.user, 'email', '') or '').strip().lower() or None
    metadata = {
        'workspace_id': str(int(workspace.id)),
        'workspace_slug': str(getattr(workspace, 'slug', '') or ''),
        'plan_key': plan_key,
        'interval': interval,
        'addons': ','.join(addons) if addons else '',
        'billing_mode': 'modular' if uses_modular else 'bundle',
        'user_id': str(int(getattr(request.user, 'id', 0) or 0)),
    }

    try:
        params = {
            'mode': 'subscription',
            'line_items': line_items,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'allow_promotion_codes': True,
            'client_reference_id': str(int(workspace.id)),
            'metadata': metadata,
            'subscription_data': {'metadata': metadata},
            'billing_address_collection': 'auto',
            'automatic_tax': {'enabled': False},
        }
        if customer_id:
            params['customer'] = customer_id
        elif customer_email:
            params['customer_email'] = customer_email

        session = core_views.stripe.checkout.Session.create(**params)
        url = str(getattr(session, 'url', '') or '').strip()
        if not url:
            return api_error('No se pudo crear la sesión de pago.', status=500, code='checkout_url_missing')
        return api_ok({'url': url})
    except Exception as exc:
        return api_error(str(exc) or 'No se pudo crear la sesión.', status=500, code='checkout_failed')


@login_required
@require_POST
def billing_portal_session_api(request):
    workspace, error = _workspace_from_request_for_billing(request)
    if error:
        return error
    if not core_views._stripe_init():
        return api_error('Stripe no está configurado.', status=501, code='stripe_not_configured')
    customer_id = str(getattr(workspace, 'stripe_customer_id', '') or '').strip()
    if not customer_id:
        return api_error('Este club no tiene cliente Stripe todavía.', status=400, code='stripe_customer_missing')
    try:
        origin = request.build_absolute_uri('/').rstrip('/')
    except Exception:
        origin = ''
    return_url = f"{origin}{reverse('billing')}"
    try:
        portal = core_views.stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        url = str(getattr(portal, 'url', '') or '').strip()
        if not url:
            return api_error('No se pudo abrir el portal.', status=500, code='portal_url_missing')
        return api_ok({'url': url})
    except Exception as exc:
        return api_error(str(exc) or 'No se pudo abrir el portal.', status=500, code='portal_failed')
