"""Verificación de email (Fase 2 del sistema de usuarios).

Verificación SUAVE: al registrarse se envía un correo con un enlace firmado; verificar marca
`AppUserRole.email_verified`. NO bloquea el uso de la app (si aún no hay SMTP configurado, el
correo va a los logs y el usuario sigue trabajando con normalidad). El enlace usa
`django.core.signing` (token firmado con caducidad), sin almacenar tokens en base de datos.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

_SALT = "sj-email-verify"
_MAX_AGE = 60 * 60 * 24 * 7  # 7 días


def _make_email_token(user):
    return signing.dumps(
        {"uid": int(user.pk), "email": (getattr(user, "email", "") or "").strip().lower()},
        salt=_SALT,
    )


def _read_email_token(token, max_age=_MAX_AGE):
    return signing.loads(token, salt=_SALT, max_age=max_age)


def send_email_verification(request, user):
    """Envía el correo de verificación. Devuelve True si se pudo enviar (o encolar)."""
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return False
    token = _make_email_token(user)
    path = reverse("verify_email", args=[token])
    url = request.build_absolute_uri(path) if request is not None else path
    ctx = {"url": url, "user": user}
    subject = " ".join(render_to_string("accounts/email_verify_subject.txt", ctx).split())
    body = render_to_string("accounts/email_verify_email.html", ctx)
    try:
        send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", None) or None,
            [email],
            fail_silently=True,
        )
        return True
    except Exception:
        return False


def _mark_verified(user):
    from .models import AppUserRole

    role, _ = AppUserRole.objects.get_or_create(user=user)
    if not role.email_verified:
        role.email_verified = True
        role.email_verified_at = timezone.now()
        role.save(update_fields=["email_verified", "email_verified_at", "updated_at"])
    return role


def verify_email(request, token):
    status = "invalid"
    try:
        data = _read_email_token(token)
        User = get_user_model()
        user = User.objects.filter(pk=data.get("uid")).first()
        # Si el email del token no coincide con el actual, el enlace es viejo -> inválido.
        if user and (data.get("email") or "") == (user.email or "").strip().lower():
            _mark_verified(user)
            status = "ok"
    except signing.SignatureExpired:
        status = "expired"
    except signing.BadSignature:
        status = "invalid"
    except Exception:
        status = "invalid"
    return render(request, "accounts/email_verify_result.html", {"status": status})


@login_required
def resend_email_verification(request):
    role = getattr(request.user, "app_role", None)
    already = bool(role and role.email_verified)
    has_email = bool((request.user.email or "").strip())
    sent = False
    if not already and has_email and request.method == "POST":
        sent = send_email_verification(request, request.user)
    return render(
        request,
        "accounts/email_verify_resend.html",
        {"already": already, "sent": sent, "has_email": has_email, "email": request.user.email},
    )
