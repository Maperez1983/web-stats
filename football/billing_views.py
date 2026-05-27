import os
import re
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api_utils import api_error, api_ok
from .models import StripeEventLog, Workspace
from .workspace_subscription import is_subscription_active
from . import workspace_context

logger = logging.getLogger(__name__)

# Stripe (opcional). No debe romper el sistema si no está configurado.
try:  # pragma: no cover
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


def _stripe_secret_key():
    return str(os.getenv('STRIPE_SECRET_KEY', '') or '').strip()


def _stripe_webhook_secret():
    return str(os.getenv('STRIPE_WEBHOOK_SECRET', '') or '').strip()


def _stripe_public_key():
    return str(os.getenv('STRIPE_PUBLISHABLE_KEY', '') or '').strip()


def _stripe_price_map():
    """
    Map interno (plan_key, interval) -> Stripe price id.
    """
    return {
        # Bundle legacy: todo incluido.
        ('pro', 'month'): str(os.getenv('STRIPE_PRICE_PRO_MONTHLY', '') or '').strip(),
        ('pro', 'year'): str(os.getenv('STRIPE_PRICE_PRO_YEARLY', '') or '').strip(),
        # Modular (Core + add-ons).
        ('core', 'month'): str(os.getenv('STRIPE_PRICE_CORE_MONTHLY', '') or '').strip(),
        ('core', 'year'): str(os.getenv('STRIPE_PRICE_CORE_YEARLY', '') or '').strip(),
        ('live', 'month'): str(os.getenv('STRIPE_PRICE_LIVE_MONTHLY', '') or '').strip(),
        ('live', 'year'): str(os.getenv('STRIPE_PRICE_LIVE_YEARLY', '') or '').strip(),
        ('studio', 'month'): str(os.getenv('STRIPE_PRICE_STUDIO_MONTHLY', '') or '').strip(),
        ('studio', 'year'): str(os.getenv('STRIPE_PRICE_STUDIO_YEARLY', '') or '').strip(),
        ('analysis', 'month'): str(os.getenv('STRIPE_PRICE_ANALYSIS_MONTHLY', '') or '').strip(),
        ('analysis', 'year'): str(os.getenv('STRIPE_PRICE_ANALYSIS_YEARLY', '') or '').strip(),
        ('tactics', 'month'): str(os.getenv('STRIPE_PRICE_TACTICS_MONTHLY', '') or '').strip(),
        ('tactics', 'year'): str(os.getenv('STRIPE_PRICE_TACTICS_YEARLY', '') or '').strip(),
    }


def _stripe_enabled() -> bool:
    return bool(_stripe_secret_key() and stripe is not None)


def _stripe_modular_billing_enabled() -> bool:
    return str(os.getenv('STRIPE_MODULAR_BILLING', '0') or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _stripe_init():
    if not _stripe_enabled():
        return False
    try:
        stripe.api_key = _stripe_secret_key()
        return True
    except Exception:
        return False


def _stripe_extract_workspace_id(obj) -> int:
    # metadata.workspace_id en Checkout Session / Subscription
    try:
        meta = getattr(obj, 'metadata', None)
        if isinstance(meta, dict) and meta.get('workspace_id'):
            return int(meta.get('workspace_id') or 0)
    except Exception:
        pass
    # client_reference_id en Checkout Session
    try:
        ref = getattr(obj, 'client_reference_id', None)
        if ref:
            return int(str(ref))
    except Exception:
        pass
    return 0


def _stripe_map_status(subscription) -> str:
    raw = str(getattr(subscription, 'status', '') or '').strip().lower()
    if raw in {'active', 'trialing'}:
        return 'active'
    if raw in {'past_due', 'unpaid'}:
        return 'past_due'
    if raw in {'canceled', 'incomplete_expired'}:
        return 'canceled'
    return raw or 'trial'


def _stripe_sync_workspace_from_subscription(workspace, subscription, *, price_id: str = '') -> None:
    if not workspace or not subscription:
        return
    status = _stripe_map_status(subscription)
    cancel_at_period_end = bool(getattr(subscription, 'cancel_at_period_end', False))
    canceled_at = getattr(subscription, 'canceled_at', None)
    period_end = getattr(subscription, 'current_period_end', None)
    period_end_dt = None
    try:
        if period_end:
            period_end_dt = timezone.datetime.fromtimestamp(int(period_end), tz=timezone.utc)
    except Exception:
        period_end_dt = None
    canceled_dt = None
    try:
        if canceled_at:
            canceled_dt = timezone.datetime.fromtimestamp(int(canceled_at), tz=timezone.utc)
    except Exception:
        canceled_dt = None

    workspace.subscription_status = status if status else (workspace.subscription_status or 'trial')
    # Detecta modo: bundle pro vs modular core (por items).
    entitlements = {}
    try:
        entitlements = _stripe_entitlements_from_subscription(subscription)
    except Exception:
        entitlements = {}

    if status == 'active':
        # Si hay entitlements, asumimos core; si no, bundle legacy.
        if entitlements:
            workspace.plan_key = workspace.plan_key or 'core'
        else:
            workspace.plan_key = workspace.plan_key or 'pro'
    # Precio "principal" (compatibilidad).
    if price_id:
        workspace.stripe_price_id = price_id
    workspace.stripe_subscription_id = str(getattr(subscription, 'id', '') or workspace.stripe_subscription_id or '')
    workspace.subscription_cancel_at_period_end = cancel_at_period_end
    workspace.subscription_current_period_end = period_end_dt
    workspace.subscription_canceled_at = canceled_dt
    if entitlements:
        workspace.paid_modules = entitlements
    workspace.save(
        update_fields=[
            'subscription_status',
            'plan_key',
            'stripe_subscription_id',
            'stripe_price_id',
            'subscription_cancel_at_period_end',
            'subscription_current_period_end',
            'subscription_canceled_at',
            'paid_modules',
            'updated_at',
        ]
    )


def _stripe_entitlements_from_subscription(subscription) -> dict:
    """
    Devuelve dict módulo->bool según items del subscription.

    - Bundle Pro => todos los módulos.
    - Modular => Core + add-ons (Live/Studio/Analysis).
    """
    if not subscription:
        return {}
    try:
        items = getattr(subscription, 'items', None)
        data = getattr(items, 'data', None) if items is not None else None
        data = data if isinstance(data, list) else []
        price_ids = []
        for it in data[:30]:
            price = getattr(it, 'price', None)
            pid = str(getattr(price, 'id', '') or '').strip()
            if pid:
                price_ids.append(pid)
    except Exception:
        price_ids = []

    price_map = _stripe_price_map()
    core_m = str(price_map.get(('core', 'month')) or '').strip()
    core_y = str(price_map.get(('core', 'year')) or '').strip()
    live_m = str(price_map.get(('live', 'month')) or '').strip()
    live_y = str(price_map.get(('live', 'year')) or '').strip()
    studio_m = str(price_map.get(('studio', 'month')) or '').strip()
    studio_y = str(price_map.get(('studio', 'year')) or '').strip()
    analysis_m = str(price_map.get(('analysis', 'month')) or '').strip()
    analysis_y = str(price_map.get(('analysis', 'year')) or '').strip()
    pro_m = str(price_map.get(('pro', 'month')) or '').strip()
    pro_y = str(price_map.get(('pro', 'year')) or '').strip()

    is_bundle = bool(price_ids and ((pro_m and pro_m in price_ids) or (pro_y and pro_y in price_ids)))
    is_modular = bool(price_ids and ((core_m and core_m in price_ids) or (core_y and core_y in price_ids)))

    ent = {}
    if is_bundle:
        ent.update({
            'dashboard': True,
            'coach_overview': True,
            'players': True,
            'convocation': True,
            'manual_stats': True,
            'match_actions': True,
            'sessions': True,
            'analysis': True,
            'abp_board': True,
        })
        return ent

    if is_modular:
        # Core siempre.
        ent.update({'dashboard': True, 'coach_overview': True, 'players': True, 'convocation': True, 'manual_stats': True})
        if (live_m and live_m in price_ids) or (live_y and live_y in price_ids):
            ent['match_actions'] = True
        if (studio_m and studio_m in price_ids) or (studio_y and studio_y in price_ids):
            ent['sessions'] = True
            ent['abp_board'] = True
        if (analysis_m and analysis_m in price_ids) or (analysis_y and analysis_y in price_ids):
            ent['analysis'] = True
        return ent

    return {}


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Webhook Stripe: activa/actualiza la suscripción del workspace.
    """
    if stripe is None:
        return JsonResponse({'ok': False, 'error': 'Stripe lib not available.'}, status=501)
    secret = _stripe_webhook_secret()
    if not secret:
        return JsonResponse({'ok': False, 'error': 'Webhook secret not configured.'}, status=501)
    try:
        payload = request.body or b''
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        event = stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=secret)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'Invalid signature: {exc.__class__.__name__}'}, status=400)

    event_id = str(getattr(event, 'id', '') or '')
    event_type = str(getattr(event, 'type', '') or '')

    # Idempotencia.
    try:
        obj, created = StripeEventLog.objects.get_or_create(event_id=event_id, defaults={'event_type': event_type, 'payload': {}})
        if not created:
            return JsonResponse({'ok': True, 'duplicate': True})
    except Exception:
        obj = None

    _stripe_init()
    workspace = None
    workspace_id = 0
    ok = False
    try:
        data_obj = getattr(event, 'data', None)
        data_obj = getattr(data_obj, 'object', None) if data_obj is not None else None

        if data_obj is not None:
            workspace_id = _stripe_extract_workspace_id(data_obj)

        if workspace_id:
            workspace = Workspace.objects.filter(id=workspace_id).first()

        # Eventos principales.
        if event_type == 'checkout.session.completed':
            session = data_obj
            customer = str(getattr(session, 'customer', '') or '').strip()
            subscription_id = str(getattr(session, 'subscription', '') or '').strip()
            if workspace and customer:
                workspace.stripe_customer_id = customer
                workspace.stripe_subscription_id = subscription_id or workspace.stripe_subscription_id
                workspace.plan_key = workspace.plan_key or str(getattr(session, 'metadata', {}).get('plan_key') or 'pro')
                workspace.subscription_status = 'active'
                workspace.save(update_fields=['stripe_customer_id', 'stripe_subscription_id', 'plan_key', 'subscription_status', 'updated_at'])
            # Sincroniza desde subscription real para periodo fin, cancel etc.
            if workspace and subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id, expand=['items.data.price'])
                    price_id = ''
                    try:
                        price_id = str(sub.items.data[0].price.id) if getattr(sub, 'items', None) and sub.items.data else ''
                    except Exception:
                        price_id = ''
                    _stripe_sync_workspace_from_subscription(workspace, sub, price_id=price_id)
                except Exception:
                    pass
            ok = True

        elif event_type in {'customer.subscription.updated', 'customer.subscription.created'}:
            sub = data_obj
            customer = str(getattr(sub, 'customer', '') or '').strip()
            sub_id = str(getattr(sub, 'id', '') or '').strip()
            sub_full = sub
            # Para entitlements modulares, intentamos siempre recuperar con expand.
            if sub_id:
                try:
                    sub_full = stripe.Subscription.retrieve(sub_id, expand=['items.data.price'])
                except Exception:
                    sub_full = sub
            price_id = ''
            try:
                if getattr(sub_full, 'items', None) and getattr(sub_full.items, 'data', None):
                    price = getattr(sub_full.items.data[0], 'price', None)
                    price_id = str(getattr(price, 'id', '') or '')
            except Exception:
                price_id = ''
            if workspace:
                if customer:
                    workspace.stripe_customer_id = customer
                if sub_id:
                    workspace.stripe_subscription_id = sub_id
                _stripe_sync_workspace_from_subscription(workspace, sub_full, price_id=price_id)
            ok = True

        elif event_type in {'customer.subscription.deleted'}:
            sub = data_obj
            customer = str(getattr(sub, 'customer', '') or '').strip()
            sub_id = str(getattr(sub, 'id', '') or '').strip()
            if workspace:
                if customer:
                    workspace.stripe_customer_id = customer
                if sub_id:
                    workspace.stripe_subscription_id = sub_id
                workspace.subscription_status = 'canceled'
                workspace.subscription_cancel_at_period_end = False
                workspace.subscription_canceled_at = timezone.now()
                workspace.save(
                    update_fields=[
                        'stripe_customer_id',
                        'stripe_subscription_id',
                        'subscription_status',
                        'subscription_cancel_at_period_end',
                        'subscription_canceled_at',
                        'updated_at',
                    ]
                )
            ok = True

        elif event_type in {'invoice.payment_failed'}:
            inv = data_obj
            customer = str(getattr(inv, 'customer', '') or '').strip()
            sub_id = str(getattr(inv, 'subscription', '') or '').strip()
            if not workspace and sub_id:
                workspace = Workspace.objects.filter(stripe_subscription_id=sub_id).first()
            if workspace:
                if customer:
                    workspace.stripe_customer_id = customer
                if sub_id:
                    workspace.stripe_subscription_id = sub_id
                workspace.subscription_status = 'past_due'
                workspace.save(update_fields=['stripe_customer_id', 'stripe_subscription_id', 'subscription_status', 'updated_at'])
            ok = True

        elif event_type in {'invoice.paid', 'invoice.payment_succeeded'}:
            inv = data_obj
            customer = str(getattr(inv, 'customer', '') or '').strip()
            sub_id = str(getattr(inv, 'subscription', '') or '').strip()
            if not workspace and sub_id:
                workspace = Workspace.objects.filter(stripe_subscription_id=sub_id).first()
            if workspace:
                if customer:
                    workspace.stripe_customer_id = customer
                if sub_id:
                    workspace.stripe_subscription_id = sub_id
                workspace.subscription_status = 'active'
                workspace.plan_key = workspace.plan_key or 'pro'
                workspace.save(update_fields=['stripe_customer_id', 'stripe_subscription_id', 'subscription_status', 'plan_key', 'updated_at'])
            ok = True

        else:
            # Ignorar otros eventos.
            ok = True

    except Exception:
        logger.exception('stripe_webhook: error procesando evento %s', event_type)
        ok = False

    # Marca log.
    try:
        if obj is not None:
            obj.event_type = event_type
            obj.workspace = workspace
            obj.ok = bool(ok)
            # Guardamos payload mínimo (no todo request.body) por tamaño.
            obj.payload = {'type': event_type, 'workspace_id': workspace_id}
            obj.save(update_fields=['event_type', 'workspace', 'ok', 'payload'])
    except Exception:
        pass

    return JsonResponse({'ok': bool(ok)})


def _workspace_from_request_for_billing(request):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return None, HttpResponse('Selecciona un club (workspace) para gestionar la suscripción.', status=400)
    if not workspace_context.can_manage_workspace(request.user, workspace) and not workspace_context.can_access_platform(request.user):
        return None, HttpResponse('No tienes permisos para gestionar la suscripción.', status=403)
    return workspace, None


@login_required
def billing_page(request):
    workspace = workspace_context.get_active_workspace(request)
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return HttpResponse('Selecciona un club (workspace) para ver la suscripción.', status=400)
    if not workspace_context.can_manage_workspace(request.user, workspace) and not workspace_context.can_access_platform(request.user):
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
    price_map = _stripe_price_map()
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
            'stripe_modular_ready': bool((_stripe_price_map().get(('core', 'month')) or '').strip()),
            'stripe_modular_enabled': _stripe_modular_billing_enabled(),
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
    if not _stripe_init():
        return api_error('Stripe no está configurado.', status=501, code='stripe_not_configured')

    plan_key = str(request.POST.get('plan_key') or request.GET.get('plan_key') or 'pro').strip().lower()
    interval = str(request.POST.get('interval') or request.GET.get('interval') or 'month').strip().lower()
    if interval not in {'month', 'year'}:
        interval = 'month'
    price_map = _stripe_price_map()

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

    if is_subscription_active(workspace):
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

        session = stripe.checkout.Session.create(**params)
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
    if not _stripe_init():
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
        portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        url = str(getattr(portal, 'url', '') or '').strip()
        if not url:
            return api_error('No se pudo abrir el portal.', status=500, code='portal_url_missing')
        return api_ok({'url': url})
    except Exception as exc:
        return api_error(str(exc) or 'No se pudo abrir el portal.', status=500, code='portal_failed')
