# Superficie HTTP - endpoints con `csrf_exempt` (actualizado)

Total patterns: 261
CSRF-exempt patterns: 1

| source | route | view | name | decorators | motivo |
|---|---|---|---|---|---|
| football/urls.py | `stripe/webhook/` | `views.stripe_webhook` | `stripe-webhook` | `csrf_exempt; require_POST` | Webhook externo de Stripe; valida firma con `STRIPE_WEBHOOK_SECRET`. |
