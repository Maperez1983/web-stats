import logging
import os
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import requests

from .api_utils import api_error, api_ok
from .models import StripeEventLog, Workspace
from .workspace_subscription import is_subscription_active
from . import workspace_context

logger = logging.getLogger(__name__)


BILLING_MODULE_ENTITLEMENTS = {
    'trainer': {
        'dashboard': True,
        'coach_overview': True,
        'players': True,
        'manual_stats': True,
        'sessions': True,
        'abp_board': True,
        'tactics': True,
    },
    'match': {
        'dashboard': True,
        'convocation': True,
        'match_actions': True,
    },
    'analysis': {
        'dashboard': True,
        'analysis': True,
    },
}


def _all_module_entitlements() -> dict:
    entitlements = {}
    for modules in BILLING_MODULE_ENTITLEMENTS.values():
        entitlements.update(modules)
    return entitlements

# Stripe (opcional). No debe romper el sistema si no está configurado.
try:  # pragma: no cover
    import stripe  # type: ignore
except Exception:  # pragma: no cover
    stripe = None


def _stripe_env(name: str) -> str:
    return str(os.getenv(name, '') or '').strip()


def _stripe_secret_key():
    return _stripe_env('STRIPE_SECRET_KEY')


def _stripe_webhook_secret():
    return _stripe_env('STRIPE_WEBHOOK_SECRET')


def _stripe_public_key():
    return _stripe_env('STRIPE_PUBLISHABLE_KEY')


def _apple_env(name: str) -> str:
    return str(os.getenv(name, '') or '').strip()


def _apple_shared_secret() -> str:
    return _apple_env('APPLE_SHARED_SECRET') or _apple_env('APP_STORE_SHARED_SECRET')


def _apple_product_map() -> dict:
    """
    Product ID Apple -> módulos internos.

    Los IDs por defecto son estables para App Store Connect. Se pueden sobrescribir
    con env vars si Apple ya tiene otros IDs creados.
    """
    defaults = {
        'trainer': _apple_env('APPLE_PRODUCT_TRAINER') or 'sj_entrenador_monthly',
        'trainer_year': _apple_env('APPLE_PRODUCT_TRAINER_YEARLY') or 'sj_entrenador_yearly',
        'match': _apple_env('APPLE_PRODUCT_MATCH') or 'sj_partido_monthly',
        'match_year': _apple_env('APPLE_PRODUCT_MATCH_YEARLY') or 'sj_partido_yearly',
        'analysis': _apple_env('APPLE_PRODUCT_ANALYSIS') or 'sj_analisis_monthly',
        'analysis_year': _apple_env('APPLE_PRODUCT_ANALYSIS_YEARLY') or 'sj_analisis_yearly',
    }
    return {
        defaults['trainer']: BILLING_MODULE_ENTITLEMENTS['trainer'],
        defaults['trainer_year']: BILLING_MODULE_ENTITLEMENTS['trainer'],
        defaults['match']: BILLING_MODULE_ENTITLEMENTS['match'],
        defaults['match_year']: BILLING_MODULE_ENTITLEMENTS['match'],
        defaults['analysis']: BILLING_MODULE_ENTITLEMENTS['analysis'],
        defaults['analysis_year']: BILLING_MODULE_ENTITLEMENTS['analysis'],
    }


def _apple_public_products() -> list:
    product_map = _apple_product_map()
    labels = {
        'sj_entrenador': 'Entrenador',
        'sj_partido': 'Partido',
        'sj_analisis': 'Análisis',
    }
    rows = []
    for product_id in product_map.keys():
        base = product_id.replace('_monthly', '').replace('_yearly', '')
        label = labels.get(base, base.replace('sj_', '').replace('_', ' ').title())
        interval = 'Anual' if product_id.endswith('_yearly') else 'Mensual'
        rows.append({'product_id': product_id, 'label': f'{label} · {interval}'})
    return rows


def _apple_verify_receipt(receipt_data: str) -> dict:
    secret = _apple_shared_secret()
    if not secret:
        raise RuntimeError('apple_shared_secret_missing')
    payload = {
        'receipt-data': receipt_data,
        'password': secret,
        'exclude-old-transactions': True,
    }
    urls = [
        'https://buy.itunes.apple.com/verifyReceipt',
        'https://sandbox.itunes.apple.com/verifyReceipt',
    ]
    last = {}
    for idx, url in enumerate(urls):
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        last = data if isinstance(data, dict) else {}
        status = int(last.get('status') or 0)
        if status == 21007 and idx == 0:
            continue
        return last
    return last


def _apple_active_product_ids(receipt_payload: dict) -> set:
    now_ms = int(timezone.now().timestamp() * 1000)
    rows = []
    latest = receipt_payload.get('latest_receipt_info')
    if isinstance(latest, list):
        rows.extend([r for r in latest if isinstance(r, dict)])
    receipt = receipt_payload.get('receipt') if isinstance(receipt_payload.get('receipt'), dict) else {}
    in_app = receipt.get('in_app')
    if isinstance(in_app, list):
        rows.extend([r for r in in_app if isinstance(r, dict)])

    active = set()
    for row in rows:
        product_id = str(row.get('product_id') or '').strip()
        if not product_id:
            continue
        expires_raw = str(row.get('expires_date_ms') or '').strip()
        if expires_raw:
            try:
                if int(expires_raw) <= now_ms:
                    continue
            except Exception:
                continue
        active.add(product_id)
    return active


def _apple_entitlements_from_products(product_ids) -> dict:
    product_map = _apple_product_map()
    entitlements = {}
    for product_id in product_ids or []:
        modules = product_map.get(str(product_id).strip())
        if isinstance(modules, dict):
            entitlements.update({key: bool(value) for key, value in modules.items() if value})
    return entitlements


def _stripe_price_map():
    """
    Map interno (plan_key, interval) -> Stripe price id.
    """
    return {
        # Bundle legacy: todo incluido.
        ('pro', 'month'): _stripe_env('STRIPE_PRICE_PRO_MONTHLY'),
        ('pro', 'year'): _stripe_env('STRIPE_PRICE_PRO_YEARLY'),
        # Modular comercial: Entrenador / Partido / Analisis.
        ('trainer', 'month'): _stripe_env('STRIPE_PRICE_TRAINER_MONTHLY') or _stripe_env('STRIPE_PRICE_CORE_MONTHLY'),
        ('trainer', 'year'): _stripe_env('STRIPE_PRICE_TRAINER_YEARLY') or _stripe_env('STRIPE_PRICE_CORE_YEARLY'),
        ('match', 'month'): _stripe_env('STRIPE_PRICE_MATCH_MONTHLY') or _stripe_env('STRIPE_PRICE_LIVE_MONTHLY'),
        ('match', 'year'): _stripe_env('STRIPE_PRICE_MATCH_YEARLY') or _stripe_env('STRIPE_PRICE_LIVE_YEARLY'),
        ('analysis', 'month'): _stripe_env('STRIPE_PRICE_ANALYSIS_MONTHLY'),
        ('analysis', 'year'): _stripe_env('STRIPE_PRICE_ANALYSIS_YEARLY'),
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
        logger.exception('No se pudo inicializar Stripe.')
        return False


def _stripe_extract_workspace_id(obj) -> int:
    # metadata.workspace_id en Checkout Session / Subscription
    try:
        meta = getattr(obj, 'metadata', None)
        if isinstance(meta, dict) and meta.get('workspace_id'):
            return int(meta.get('workspace_id') or 0)
    except Exception:
        logger.debug('No se pudo extraer workspace_id desde metadata Stripe', exc_info=True)
    # client_reference_id en Checkout Session
    try:
        ref = getattr(obj, 'client_reference_id', None)
        if ref:
            return int(str(ref))
    except Exception:
        logger.debug('No se pudo extraer workspace_id desde client_reference_id Stripe', exc_info=True)
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
        logger.debug('No se pudo parsear current_period_end Stripe: %s', period_end, exc_info=True)
        period_end_dt = None
    canceled_dt = None
    try:
        if canceled_at:
            canceled_dt = timezone.datetime.fromtimestamp(int(canceled_at), tz=timezone.utc)
    except Exception:
        logger.debug('No se pudo parsear canceled_at Stripe: %s', canceled_at, exc_info=True)
        canceled_dt = None

    workspace.subscription_status = status if status else (workspace.subscription_status or 'trial')
    # Detecta modo: bundle pro vs modular core (por items).
    entitlements = {}
    try:
        entitlements = _stripe_entitlements_from_subscription(subscription)
    except Exception:
        logger.debug('No se pudieron calcular entitlements Stripe para workspace %s', getattr(workspace, 'id', None), exc_info=True)
        entitlements = {}

    if status == 'active':
        # Si hay entitlements, asumimos modular; si no, bundle legacy.
        if entitlements:
            workspace.plan_key = workspace.plan_key or 'modular'
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
    - Modular => Entrenador / Partido / Análisis.
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
    trainer_m = str(price_map.get(('trainer', 'month')) or '').strip()
    trainer_y = str(price_map.get(('trainer', 'year')) or '').strip()
    match_m = str(price_map.get(('match', 'month')) or '').strip()
    match_y = str(price_map.get(('match', 'year')) or '').strip()
    analysis_m = str(price_map.get(('analysis', 'month')) or '').strip()
    analysis_y = str(price_map.get(('analysis', 'year')) or '').strip()
    pro_m = str(price_map.get(('pro', 'month')) or '').strip()
    pro_y = str(price_map.get(('pro', 'year')) or '').strip()

    is_bundle = bool(price_ids and ((pro_m and pro_m in price_ids) or (pro_y and pro_y in price_ids)))

    ent = {}
    if is_bundle:
        ent.update(_all_module_entitlements())
        return ent

    if (trainer_m and trainer_m in price_ids) or (trainer_y and trainer_y in price_ids):
        ent.update(BILLING_MODULE_ENTITLEMENTS['trainer'])
    if (match_m and match_m in price_ids) or (match_y and match_y in price_ids):
        ent.update(BILLING_MODULE_ENTITLEMENTS['match'])
    if (analysis_m and analysis_m in price_ids) or (analysis_y and analysis_y in price_ids):
        ent.update(BILLING_MODULE_ENTITLEMENTS['analysis'])
    if ent:
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
                        logger.debug('No se pudo leer price_id de subscription Stripe %s', subscription_id, exc_info=True)
                        price_id = ''
                    _stripe_sync_workspace_from_subscription(workspace, sub, price_id=price_id)
                except Exception:
                    logger.debug('No se pudo recuperar subscription Stripe %s tras checkout', subscription_id, exc_info=True)
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
                    logger.debug('No se pudo recuperar subscription Stripe expandida %s', sub_id, exc_info=True)
                    sub_full = sub
            price_id = ''
            try:
                if getattr(sub_full, 'items', None) and getattr(sub_full.items, 'data', None):
                    price = getattr(sub_full.items.data[0], 'price', None)
                    price_id = str(getattr(price, 'id', '') or '')
            except Exception:
                logger.debug('No se pudo leer price_id de subscription Stripe %s', sub_id, exc_info=True)
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
        logger.debug('No se pudo actualizar StripeEventLog para evento %s', event_type, exc_info=True)

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

        if plan_key in {'trainer', 'entrenador', 'basic', 'club_basic', 'core'}:
            return dict(BILLING_MODULE_ENTITLEMENTS['trainer'])

        if plan_key in {'match', 'partido'}:
            return dict(BILLING_MODULE_ENTITLEMENTS['match'])

        if plan_key in {'analysis', 'analisis'}:
            return dict(BILLING_MODULE_ENTITLEMENTS['analysis'])

        if plan_key in {'pro', 'club_pro', 'bundle'}:
            return _all_module_entitlements()

        ent = {'dashboard': True}
        if 'trainer' in addons or 'entrenador' in addons:
            ent.update(BILLING_MODULE_ENTITLEMENTS['trainer'])
        if 'match' in addons or 'partido' in addons:
            ent.update(BILLING_MODULE_ENTITLEMENTS['match'])
        if 'analysis' in addons or 'analisis' in addons:
            ent.update(BILLING_MODULE_ENTITLEMENTS['analysis'])
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
        for key in ('trainer', 'match', 'analysis'):
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
            'stripe_modular_ready': any(
                bool((price_map.get((key, 'month')) or '').strip() or (price_map.get((key, 'year')) or '').strip())
                for key in ('trainer', 'match', 'analysis')
            ),
            'stripe_modular_enabled': _stripe_modular_billing_enabled(),
            'stripe_addons_available': addons_available,
            'apple_iap_ready': bool(_apple_shared_secret()),
            'apple_iap_products': _apple_public_products(),
            'allow_manual_billing': allow_manual,
            'manual_billing_message': manual_msg,
            'manual_billing_error': manual_err,
        },
    )


@login_required
@require_POST
def apple_receipt_api(request):
    workspace, error = _workspace_from_request_for_billing(request)
    if error:
        return error
    receipt_data = str(request.POST.get('receipt_data') or '').strip()
    requested_product_id = str(request.POST.get('product_id') or '').strip()
    transaction_id = str(request.POST.get('transaction_id') or '').strip()
    if not receipt_data:
        return api_error('Falta el recibo de Apple.', status=400, code='apple_receipt_missing')
    if not _apple_shared_secret():
        return api_error('Apple IAP no está configurado.', status=501, code='apple_iap_not_configured')

    try:
        verified = _apple_verify_receipt(receipt_data)
    except RuntimeError:
        return api_error('Apple IAP no está configurado.', status=501, code='apple_iap_not_configured')
    except Exception as exc:
        logger.exception('No se pudo validar recibo Apple para workspace %s', getattr(workspace, 'id', None))
        return api_error(f'No se pudo validar con Apple: {exc.__class__.__name__}', status=502, code='apple_verify_failed')

    status = int(verified.get('status') or 0)
    if status != 0:
        return api_error(f'Apple rechazó el recibo ({status}).', status=400, code='apple_receipt_invalid')

    active_product_ids = _apple_active_product_ids(verified)
    if requested_product_id and requested_product_id in _apple_product_map():
        # Si Apple devuelve el recibo con retraso pero la compra acaba de finalizar,
        # aceptamos el producto solicitado solo si pertenece a nuestro catálogo.
        active_product_ids.add(requested_product_id)
    entitlements = _apple_entitlements_from_products(active_product_ids)
    if not entitlements:
        return api_error('No hay suscripciones Apple activas para este club.', status=402, code='apple_no_active_products')

    current = getattr(workspace, 'paid_modules', None)
    current = dict(current) if isinstance(current, dict) else {}
    current.update(entitlements)
    current['apple_iap'] = {
        'product_ids': sorted(active_product_ids),
        'last_transaction_id': transaction_id,
        'verified_at': timezone.now().isoformat(),
    }
    workspace.subscription_status = 'active'
    workspace.plan_key = 'apple_modular'
    workspace.paid_modules = current
    workspace.save(update_fields=['subscription_status', 'plan_key', 'paid_modules', 'updated_at'])
    return api_ok({'subscription_status': 'active', 'paid_modules': entitlements, 'product_ids': sorted(active_product_ids)})


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

    line_items = []
    uses_modular = False
    selected_modules = []
    raw_modules = str(request.POST.get('modules') or request.GET.get('modules') or '').strip()
    if raw_modules:
        selected_modules = [m.strip().lower() for m in re.split(r'[, ]+', raw_modules) if m.strip()]
    elif plan_key in {'trainer', 'entrenador', 'core', 'starter', 'basic'}:
        selected_modules = ['trainer']
    elif plan_key in {'match', 'partido'}:
        selected_modules = ['match']
    elif plan_key in {'analysis', 'analisis'}:
        selected_modules = ['analysis']
    selected_modules = ['trainer' if m in {'entrenador', 'core', 'starter', 'basic'} else 'match' if m == 'partido' else 'analysis' if m == 'analisis' else m for m in selected_modules]
    allowed_modules = {'trainer', 'match', 'analysis'}
    selected_modules = [m for m in dict.fromkeys(selected_modules) if m in allowed_modules]

    if selected_modules:
        uses_modular = True
        for module_key in selected_modules:
            pid = (price_map.get((module_key, interval)) or '').strip()
            if not pid:
                return api_error(f'Módulo no disponible: {module_key}.', status=500, code='module_price_missing')
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
        'modules': ','.join(selected_modules) if selected_modules else '',
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
