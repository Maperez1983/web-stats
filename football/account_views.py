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


# ---------------------------------------------------------------------------
# Fase 3: miembros del club + invitaciones por email
# ---------------------------------------------------------------------------
# Cada "rol de acceso" mapea a (AppUserRole global, WorkspaceMembership por club).
# (clave, etiqueta, rol GLOBAL AppUserRole, rol de CLUB WorkspaceMembership).
# IMPORTANTE: el "Administrador" de un club NO lleva el rol global `administrador` — ese rol da
# acceso al panel de PLATAFORMA (superadmin de TODOS los clubes). El admin de club obtiene su
# poder del rol de CLUB `admin` (can_manage_workspace); su rol global se queda como `entrenador`
# para no darle acceso multi-club.
MEMBER_ROLE_PRESETS = [
    ("entrenador", "Entrenador", "entrenador", "member"),
    ("analista", "Analista", "analista", "member"),
    ("preparador_fisico", "Preparador físico", "preparador_fisico", "member"),
    ("preparador_portero", "Preparador de portero", "preparador_portero", "member"),
    ("administrador", "Administrador (del club)", "entrenador", "admin"),
    ("viewer", "Solo lectura", "invitado", "viewer"),
]
_MEMBER_PRESET_BY_KEY = {p[0]: p for p in MEMBER_ROLE_PRESETS}


def _resolve_member_preset(key):
    return _MEMBER_PRESET_BY_KEY.get(str(key or "").strip(), _MEMBER_PRESET_BY_KEY["entrenador"])


def _preset_key_for_membership(membership):
    """Deriva la clave de preset a partir del rol de club + rol global (para mostrar el select)."""
    from .models import WorkspaceMembership

    role = getattr(membership, "role", "")
    app_role = getattr(getattr(membership.user, "app_role", None), "role", "") if membership else ""
    if role == WorkspaceMembership.ROLE_VIEWER:
        return "viewer"
    if role == WorkspaceMembership.ROLE_ADMIN:
        return "administrador"
    for key, _label, ar, _mr in MEMBER_ROLE_PRESETS:
        if ar == app_role and key not in {"administrador", "viewer"}:
            return key
    return "entrenador"


def send_workspace_member_invite(request, workspace, email, name, app_role, member_role):
    """Crea/enlaza el usuario (inactivo), rol global + membresía y envía el email de invitación."""
    from django.urls import reverse
    from django.utils import timezone
    from datetime import timedelta
    from .models import AppUserRole, WorkspaceMembership, UserInvitation
    from django.utils.text import slugify

    User = get_user_model()
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Email inválido.")

    user_obj = User.objects.filter(email__iexact=email).order_by("id").first()
    if user_obj is None:
        base = slugify(email.split("@", 1)[0]).replace("-", ".").strip(".")[:120] or "miembro"
        username = base
        n = 2
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}{n}"
            n += 1
        first, _, last = (name or "").strip().partition(" ")
        user_obj = User.objects.create_user(
            username=username, email=email, password=None,
            first_name=first[:150], last_name=last[:150], is_active=False,
        )
    else:
        # Usuario ya existe: no tocamos su contraseña; solo aseguramos nombre si está vacío.
        if name and not (user_obj.first_name or user_obj.last_name):
            first, _, last = name.strip().partition(" ")
            user_obj.first_name, user_obj.last_name = first[:150], last[:150]
            user_obj.save(update_fields=["first_name", "last_name"])

    AppUserRole.objects.update_or_create(user=user_obj, defaults={"role": app_role})
    WorkspaceMembership.objects.update_or_create(
        workspace=workspace, user=user_obj, defaults={"role": member_role}
    )

    # Un solo enlace activo por usuario.
    UserInvitation.objects.filter(user=user_obj, is_active=True, accepted_at__isnull=True).update(is_active=False)
    invitation = UserInvitation.objects.create(
        user=user_obj,
        token=UserInvitation.generate_token(),
        email=email,
        expires_at=timezone.now() + timedelta(days=14),
        created_by=request.user.get_username() if request.user.is_authenticated else "",
        is_active=True,
    )
    accept_url = request.build_absolute_uri(reverse("user-invite-accept", args=[invitation.token]))
    _send_member_invite_email(email, workspace, request.user, accept_url)
    return user_obj, invitation, accept_url


def _send_member_invite_email(email, workspace, inviter, accept_url):
    ctx = {
        "url": accept_url,
        "workspace": getattr(workspace, "name", "") or "tu club",
        "inviter": (getattr(inviter, "get_full_name", lambda: "")() or getattr(inviter, "username", "")),
    }
    subject = " ".join(render_to_string("accounts/member_invite_subject.txt", ctx).split())
    body = render_to_string("accounts/member_invite_email.html", ctx)
    # Devuelve "" si se envía bien, o el motivo del error (para poder mostrarlo al admin en vez de
    # tragárnoslo en silencio).
    try:
        send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None) or None, [email], fail_silently=False)
        return ""
    except Exception as exc:
        return (f"{type(exc).__name__}: {exc}")[:280]


@login_required
def workspace_members_page(request):
    from django.contrib import messages
    from .models import WorkspaceMembership, UserInvitation
    from .workspace_context import get_active_workspace, can_access_platform
    from .access_policy import can_manage_workspace, is_workspace_owner_user

    workspace = get_active_workspace(request)
    platform = can_access_platform(request.user)
    if not workspace or not can_manage_workspace(request.user, workspace, platform_access=platform):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("No tienes permiso para gestionar los miembros de este club.")

    notice = ""
    error = ""
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "invite":
                key = request.POST.get("role_preset")
                _k, _label, app_role, member_role = _resolve_member_preset(key)
                _u, _inv, url = send_workspace_member_invite(
                    request, workspace,
                    request.POST.get("email"), request.POST.get("name"),
                    app_role, member_role,
                )
                notice = f"Invitación enviada a {(request.POST.get('email') or '').strip().lower()}."
            elif action == "role":
                mid = int(request.POST.get("membership_id") or 0)
                m = WorkspaceMembership.objects.select_related("user").filter(id=mid, workspace=workspace).first()
                if not m:
                    raise ValueError("Miembro no encontrado.")
                if is_workspace_owner_user(m.user, workspace):
                    raise ValueError("No se puede cambiar el rol del propietario.")
                _k, _label, app_role, member_role = _resolve_member_preset(request.POST.get("role_preset"))
                m.role = member_role
                m.save(update_fields=["role"])
                from .models import AppUserRole
                AppUserRole.objects.update_or_create(user=m.user, defaults={"role": app_role})
                notice = "Rol actualizado."
            elif action == "remove":
                mid = int(request.POST.get("membership_id") or 0)
                m = WorkspaceMembership.objects.select_related("user").filter(id=mid, workspace=workspace).first()
                if not m:
                    raise ValueError("Miembro no encontrado.")
                if is_workspace_owner_user(m.user, workspace):
                    raise ValueError("No se puede quitar al propietario del club.")
                if int(m.user_id) == int(request.user.id):
                    raise ValueError("No puedes quitarte a ti mismo.")
                m.delete()
                notice = "Miembro retirado del club."
            elif action == "resend":
                mid = int(request.POST.get("membership_id") or 0)
                m = WorkspaceMembership.objects.select_related("user").filter(id=mid, workspace=workspace).first()
                if not m:
                    raise ValueError("Miembro no encontrado.")
                key = _preset_key_for_membership(m)
                _k, _label, app_role, member_role = _resolve_member_preset(key)
                send_workspace_member_invite(request, workspace, m.user.email, m.user.get_full_name(), app_role, member_role)
                notice = "Invitación reenviada."
        except ValueError as exc:
            error = str(exc)
        except Exception:
            error = "No se pudo completar la acción."

    memberships = list(
        WorkspaceMembership.objects.filter(workspace=workspace).select_related("user", "user__app_role").order_by("role", "user__username")
    )
    owner_id = int(getattr(workspace, "owner_user_id", 0) or 0)
    pending_invites = {
        inv.user_id: inv
        for inv in UserInvitation.objects.filter(
            user__in=[m.user for m in memberships], is_active=True, accepted_at__isnull=True
        )
    }
    rows = []
    for m in memberships:
        u = m.user
        is_owner = int(u.id) == owner_id
        # "Pendiente" = cuenta inactiva o sin contraseña utilizable (invitación no aceptada).
        pending = (not u.is_active) or (not u.has_usable_password())
        rows.append({
            "membership_id": m.id,
            "name": (u.get_full_name() or u.username),
            "email": u.email,
            "is_owner": is_owner,
            "is_self": int(u.id) == int(request.user.id),
            "preset_key": _preset_key_for_membership(m),
            "role_label": ("Propietario" if is_owner else dict((p[0], p[1]) for p in MEMBER_ROLE_PRESETS).get(_preset_key_for_membership(m), "Miembro")),
            "pending": bool(pending) and not is_owner,
        })

    return render(request, "accounts/workspace_members.html", {
        "workspace": workspace,
        "rows": rows,
        "role_presets": MEMBER_ROLE_PRESETS,
        "notice": notice,
        "error": error,
    })


@login_required
def workspace_member_access_page(request, membership_id):
    """Configura qué áreas ve un miembro concreto (WorkspaceMembership.module_access)."""
    from .models import WorkspaceMembership
    from .workspace_context import get_active_workspace, can_access_platform
    from .access_policy import can_manage_workspace, is_workspace_owner_user
    from . import views as _views  # catálogo de módulos (lazy para evitar circular)

    workspace = get_active_workspace(request)
    platform = can_access_platform(request.user)
    if not workspace or not can_manage_workspace(request.user, workspace, platform_access=platform):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("No tienes permiso para gestionar los miembros de este club.")

    membership = (
        WorkspaceMembership.objects.select_related("user")
        .filter(id=membership_id, workspace=workspace)
        .first()
    )
    if membership is None:
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Miembro no encontrado.")

    catalog = _views._workspace_access_module_catalog(getattr(workspace, "kind", None))
    is_owner = is_workspace_owner_user(membership.user, workspace)
    # owner/admin ven todo por diseño; el gating por módulo solo aplica a member/viewer.
    sees_everything = is_owner or membership.role in {
        WorkspaceMembership.ROLE_OWNER,
        WorkspaceMembership.ROLE_ADMIN,
    }
    notice = ""
    if request.method == "POST" and not sees_everything:
        access = {}
        for entry in catalog:
            key = entry.get("key")
            if key:
                access[key] = bool(request.POST.get(f"mod_{key}"))
        membership.module_access = access
        membership.save(update_fields=["module_access"])
        notice = "Accesos guardados."

    current = membership.module_access if isinstance(membership.module_access, dict) else {}
    modules = [
        {"key": e["key"], "label": e["label"], "allowed": current.get(e["key"], True) is not False}
        for e in catalog
    ]
    return render(request, "accounts/member_access.html", {
        "workspace": workspace,
        "member_name": (membership.user.get_full_name() or membership.user.username),
        "member_email": membership.user.email,
        "membership_id": membership.id,
        "modules": modules,
        "sees_everything": sees_everything,
        "notice": notice,
    })


# ---------------------------------------------------------------------------
# Fase 6: espacio del jugador (portal propio)
# ---------------------------------------------------------------------------
@login_required
def player_home_page(request):
    """Landing propia del jugador: su identidad, objetivos activos y acceso a su ficha."""
    from .models import Player, PlayerObjective

    player = Player.objects.filter(user=request.user).select_related("team").first()
    objectives = []
    if player is not None:
        try:
            objectives = list(
                PlayerObjective.objects.filter(player=player)
                .exclude(status="done")
                .order_by("-created_at")[:6]
            )
        except Exception:
            objectives = []
    return render(
        request,
        "accounts/player_home.html",
        {
            "player": player,
            "objectives": objectives,
            "display_name": request.user.get_full_name() or request.user.username,
        },
    )
