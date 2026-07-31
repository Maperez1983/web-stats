"""Verificación de email (Fase 2 del sistema de usuarios).

Verificación SUAVE: al registrarse se envía un correo con un enlace firmado; verificar marca
`AppUserRole.email_verified`. NO bloquea el uso de la app (si aún no hay SMTP configurado, el
correo va a los logs y el usuario sigue trabajando con normalidad). El enlace usa
`django.core.signing` (token firmado con caducidad), sin almacenar tokens en base de datos.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .player_portal_policy import visibility_for_request as player_portal_visibility_for_request

logger = logging.getLogger(__name__)

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
    ("jugador", "Jugador", "jugador", "viewer"),
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
    if app_role == "jugador":
        return "jugador"
    if role == WorkspaceMembership.ROLE_VIEWER:
        return "viewer"
    if role == WorkspaceMembership.ROLE_ADMIN:
        return "administrador"
    for key, _label, ar, _mr in MEMBER_ROLE_PRESETS:
        if ar == app_role and key not in {"administrador", "viewer"}:
            return key
    return "entrenador"


def send_workspace_member_invite(request, workspace, email, name, app_role, member_role, player=None):
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
        player=player,
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
                invited_player = None
                if app_role == "jugador":
                    from .models import Player

                    _player_id = str(request.POST.get("player_id") or "").strip()
                    if not _player_id:
                        raise ValueError("Elige a qué jugador de la plantilla pertenece esta cuenta.")
                    invited_player = Player.objects.filter(
                        id=int(_player_id), team__workspace_links__workspace=workspace
                    ).first()
                    if invited_player is None:
                        raise ValueError("Ese jugador no es de este club.")
                    if invited_player.user_id:
                        raise ValueError(f"{invited_player.name} ya tiene una cuenta vinculada.")
                _u, _inv, url = send_workspace_member_invite(
                    request, workspace,
                    request.POST.get("email"), request.POST.get("name"),
                    app_role, member_role, player=invited_player,
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

    # Jugadores del club que todavía no tienen cuenta: son los que se pueden invitar.
    linkable_players = []
    try:
        from .models import Player

        linkable_players = list(
            Player.objects.filter(
                team__workspace_links__workspace=workspace, is_active=True, user__isnull=True
            )
            .select_related("team")
            .order_by("team__name", "name")
        )
    except Exception:
        logger.debug("No se pudieron listar los jugadores vinculables del club", exc_info=True)

    return render(request, "accounts/workspace_members.html", {
        "workspace": workspace,
        "rows": rows,
        "linkable_players": linkable_players,
        "role_presets": MEMBER_ROLE_PRESETS,
        "notice": notice,
        "error": error,
    })


@login_required
@login_required
def player_portal_settings_page(request):
    """
    Panel del club: qué ve cada jugador en su portal, y quién tiene cuenta.

    Sin esta pantalla la política existía pero sólo se podía tocar desde una shell, o sea que
    de hecho no se podía tocar: mandaban los valores por defecto que trae el código. Aquí el
    dueño del club decide, que es de quien es la decisión.

    Dos niveles: la regla del CLUB (lo normal, una decisión para todos) y, encima, la regla
    de una CATEGORÍA concreta. La del jugador suelto (`Player.portal_overrides`) sigue sin
    interfaz a propósito: es la salida para el caso raro, no la forma de configurar.
    """
    from . import player_portal_policy as policy
    from .access_policy import can_manage_workspace
    from .models import Player, PlayerPortalPolicy, Team, UserInvitation
    from .workspace_context import can_access_platform, get_active_workspace

    workspace = get_active_workspace(request)
    platform = can_access_platform(request.user)
    if not workspace or not can_manage_workspace(request.user, workspace, platform_access=platform):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("No tienes permiso para configurar el portal del jugador.")

    teams = list(Team.objects.filter(workspace_links__workspace=workspace).order_by("name").distinct())
    editing_team = None
    raw_team = str(request.GET.get("equipo") or "").strip()
    if raw_team:
        editing_team = next((t for t in teams if str(t.id) == raw_team), None)

    notice = ""
    error = ""
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        target_team = None
        raw_target = str(request.POST.get("team_id") or "").strip()
        if raw_target:
            target_team = next((t for t in teams if str(t.id) == raw_target), None)
            if target_team is None:
                error = "Ese equipo no es de este club."
        if not error and action == "save":
            sections = {}
            for section in policy.SECTIONS:
                value = str(request.POST.get(f"section__{section['key']}") or "").strip()
                if value:
                    sections[section["key"]] = value
            # `normalize_sections` es quien filtra: un estado imposible para esa sección no
            # entra, venga de donde venga.
            base = policy.default_sections() if target_team is None else policy.policy_sections_for(workspace)
            cleaned = policy.normalize_sections(sections, base=base)
            stored = {k: v for k, v in cleaned.items() if v != base.get(k)}
            row, _ = PlayerPortalPolicy.objects.update_or_create(
                workspace=workspace, team=target_team,
                defaults={"sections": stored, "updated_by": request.user},
            )
            notice = (
                "Regla del club guardada."
                if target_team is None
                else f"Regla de {target_team.name} guardada."
            )
        elif not error and action == "unlink":
            # Deshacer un vínculo equivocado. Los vínculos viejos los pudo escribir el
            # auto-vinculado por parecido de nombre que se retiró en la fase 0, así que hay
            # que poder revisarlos. No se toca la cuenta: sólo se suelta de esta ficha.
            from .models import Player as _Player

            _pid = str(request.POST.get("player_id") or "").strip()
            _player = (
                _Player.objects.filter(
                    id=int(_pid), team__workspace_links__workspace=workspace
                ).first()
                if _pid.isdigit()
                else None
            )
            if _player is None:
                error = "Ese jugador no es de este club."
            else:
                _player.user = None
                _player.save(update_fields=["user"])
                notice = f"{_player.name} ya no está vinculado a ninguna cuenta."
        elif not error and action == "reset" and target_team is not None:
            PlayerPortalPolicy.objects.filter(workspace=workspace, team=target_team).delete()
            notice = f"{target_team.name} vuelve a la regla del club."

    club_sections = policy.policy_sections_for(workspace)
    club_row = PlayerPortalPolicy.objects.filter(workspace=workspace, team__isnull=True).first()

    # Cada categoría dice sólo lo que le pasa: igual que el club, o cuántos cambios tiene.
    team_rows = []
    for team in teams:
        resolved = policy.policy_sections_for(workspace, team=team)
        diffs = [
            {
                "label": section["label"],
                "state": resolved[section["key"]],
            }
            for section in policy.SECTIONS
            if resolved[section["key"]] != club_sections[section["key"]]
        ]
        team_rows.append({"team": team, "diffs": diffs, "sections": resolved})

    editing_sections = (
        policy.policy_sections_for(workspace, team=editing_team) if editing_team else club_sections
    )
    section_rows = []
    for section in policy.SECTIONS:
        current = editing_sections[section["key"]]
        section_rows.append({
            "key": section["key"],
            "label": section["label"],
            "help": section["help"],
            "current": current,
            "inherited": bool(editing_team and current == club_sections[section["key"]]),
            "options": [
                {"value": state, "label": dict(policy.STATE_CHOICES)[state], "selected": state == current}
                for state in section["states"]
            ],
        })

    # Quién tiene cuenta y quién no: sin esto el panel dice qué se ve pero no quién lo ve.
    # Va por EQUIPO ACTIVO, como el resto de la app: estando en el primer equipo no pintamos
    # los bebés. La política de arriba sí es del club entero, que es otra cosa.
    from .workspace_context import get_active_team_for_request

    squad_team = get_active_team_for_request(request)
    if squad_team is not None and squad_team.id not in {t.id for t in teams}:
        squad_team = None
    if squad_team is None:
        squad_team = teams[0] if teams else None

    squad = []
    try:
        invited_ids = set(
            UserInvitation.objects.filter(
                player__isnull=False, is_active=True, accepted_at__isnull=True
            ).values_list("player_id", flat=True)
        )
        squad_qs = Player.objects.filter(is_active=True).select_related("team", "user")
        squad_qs = (
            squad_qs.filter(team=squad_team)
            if squad_team is not None
            else squad_qs.filter(team__workspace_links__workspace=workspace)
        )
        for player in squad_qs.order_by("name").distinct():
            if player.user_id:
                account = "vinculado"
            elif player.id in invited_ids:
                account = "invitado"
            else:
                account = "sin cuenta"
            linked = player.user
            squad.append({
                "player": player,
                "account": account,
                "linked_label": (
                    (linked.get_full_name() or linked.get_username()) if linked else ""
                ),
                "linked_email": (getattr(linked, "email", "") or "") if linked else "",
            })
    except Exception:
        logger.debug("No se pudo listar la plantilla para el panel del portal", exc_info=True)

    squad_team_options = []
    try:
        from django.db.models import Count

        counts = dict(
            Player.objects.filter(team__in=teams, is_active=True)
            .values("team")
            .annotate(n=Count("id"))
            .values_list("team", "n")
        )
        squad_team_options = [
            {"team": t, "count": counts.get(t.id, 0), "active": bool(squad_team and t.id == squad_team.id)}
            for t in teams
        ]
    except Exception:
        logger.debug("No se pudieron contar los jugadores por equipo", exc_info=True)

    return render(request, "accounts/player_portal_settings.html", {
        "workspace": workspace,
        "teams": teams,
        "squad_team": squad_team,
        "squad_team_options": squad_team_options,
        "editing_team": editing_team,
        "section_rows": section_rows,
        "team_rows": team_rows,
        "club_row": club_row,
        "squad": squad,
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
    # "Ver como jugador": el cuerpo técnico abre el portal TAL CUAL lo recibe un jugador
    # concreto. Sin esto, cerrar la ficha dejaría al club sin forma de comprobar qué ve, y
    # una política que no se puede mirar no se puede confiar. Es sólo lectura: no marca
    # avisos como leídos ni permite confirmar asistencia (el formulario se oculta).
    preview_of = None
    raw_preview = str(request.GET.get("ver_como") or "").strip()
    if raw_preview:
        try:
            from .permissions import can_access_coach_workspace

            if can_access_coach_workspace(request.user):
                candidate = Player.objects.select_related("team").filter(id=int(raw_preview)).first()
                if candidate is not None and _player_belongs_to_request_club(request, candidate):
                    preview_of = candidate
                    player = candidate
        except Exception:
            logger.debug("No se pudo resolver la previsualización del portal", exc_info=True)

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

    # Marcador de ENTRENO del jugador (temporada): asistencia + minutos de entreno. Alimentado por
    # la asistencia (presente implícito → asistidas = total − ausente/lesionado/justificado) y por la
    # participación por tarea (minutos = suma de duración de las tareas en las que participó).
    training_marker = {
        "sessions_total": 0,
        "sessions_attended": 0,
        "sessions_trained": 0,
        "minutes": 0,
    }
    if player is not None and getattr(player, "team_id", None):
        try:
            from datetime import timedelta
            from django.db.models import Sum
            from .models import TrainingSession, TrainingSessionAttendance, SessionTaskParticipation

            today = timezone.localdate()
            season_start = today - timedelta(days=365)
            season_end = today + timedelta(days=31)
            # Alinear con la MISMA temporada que la ficha del jugador (player_detail) para que los
            # contadores cuadren entre "Mi espacio" y la ficha. Fallback a ventana móvil si no hay temporada.
            try:
                from .season_history_services import selected_club_season_for_request
                from .workspace_context import get_active_workspace

                _ws = get_active_workspace(request)
                _season = selected_club_season_for_request(request, workspace=_ws) if _ws else None
                if _season and getattr(_season, "start_date", None):
                    season_start = _season.start_date
                    if getattr(_season, "end_date", None):
                        season_end = _season.end_date
            except Exception:
                pass
            sessions_total = (
                TrainingSession.objects.filter(
                    microcycle__team_id=player.team_id, session_date__range=(season_start, season_end)
                )
                .exclude(status=TrainingSession.STATUS_CANCELED)
                .count()
            )
            missed = TrainingSessionAttendance.objects.filter(
                player=player,
                session__session_date__range=(season_start, season_end),
                status__in=[
                    TrainingSessionAttendance.STATUS_ABSENT,
                    TrainingSessionAttendance.STATUS_INJURED,
                    TrainingSessionAttendance.STATUS_EXCUSED,
                ],
            ).count()
            part_qs = SessionTaskParticipation.objects.filter(
                player=player, session_task__session__session_date__range=(season_start, season_end)
            )
            training_marker = {
                "sessions_total": int(sessions_total or 0),
                "sessions_attended": max(0, int(sessions_total or 0) - int(missed or 0)),
                "sessions_trained": part_qs.values("session_task__session_id").distinct().count(),
                "minutes": int(part_qs.aggregate(m=Sum("session_task__duration_minutes")).get("m") or 0),
            }
        except Exception:
            pass

    workspace = None
    try:
        from .workspace_context import get_active_workspace

        workspace = get_active_workspace(request)
    except Exception:
        logger.debug("No se pudo resolver el workspace activo del jugador", exc_info=True)

    vis = player_portal_visibility_for_request(
        player, workspace=workspace, team=getattr(player, "team", None), is_player_view=True
    )

    return render(
        request,
        "accounts/player_home.html",
        {
            "player": player,
            "vis": vis,
            "preview_of": preview_of,
            "objectives": objectives if vis.objectives else [],
            "training_marker": training_marker,
            "display_name": request.user.get_full_name() or request.user.username,
            **_player_home_zones(request, player, vis),
        },
    )


def _player_belongs_to_request_club(request, player):
    """El staff sólo puede previsualizar el portal de jugadores de SU club."""
    from .models import WorkspaceTeam
    from .workspace_context import get_active_workspace

    workspace = get_active_workspace(request)
    if not workspace or not getattr(player, "team_id", None):
        return False
    return WorkspaceTeam.objects.filter(workspace=workspace, team_id=player.team_id).exists()


def _player_home_zones(request, player, vis):
    """
    Los datos de las cinco zonas del portal.

    Todo lo que sale de aquí pasa por la política (`vis`): la plantilla pinta lo que reciba
    y no decide nada. Cada bloque va en su propio try porque una zona que falle no puede
    tumbar el portal entero — el jugador se queda sin esa tarjeta, no sin su espacio.
    """
    from django.db.models import Sum

    from .models import (
        PlayerCommunication,
        PlayerFine,
        PlayerNotification,
        TrainingSession,
        TrainingSessionAttendance,
        VideoInboxItem,
    )

    zones = {
        "evaluations": [],
        "notifications": [],
        "next_session": None,
        "next_session_attendance": None,
        "attendance_status_choices": TrainingSessionAttendance.STATUS_CHOICES,
        "match_notice": None,
        "active_injury": None,
        "inbox_items": [],
        "inbox_unread": 0,
        "fines": [],
        "fines_total": 0,
        "communications": [],
    }
    if player is None:
        return zones

    # En previsualización, el "usuario" del portal es el del jugador previsualizado: si
    # usáramos el del staff, el entrenador vería sus propios avisos dentro de la pantalla
    # del jugador y la previsualización mentiría.
    user = getattr(player, "user", None) or request.user

    # HOY -------------------------------------------------------------------------------
    try:
        notifications = list(
            PlayerNotification.objects.filter(target_user=user, is_read=False).order_by("-created_at", "-id")[:8]
        )
        zones["notifications"] = notifications
        # Su estado de partido sale del aviso PUBLICADO, no de la convocatoria cruda: así
        # sólo ve lo que el cuerpo técnico ha decidido publicar, y sólo lo suyo.
        zones["match_notice"] = next(
            (n for n in notifications if n.kind in {"convocatoria", "alineacion"}), None
        )
    except Exception:
        logger.debug("No se pudieron cargar los avisos del jugador", exc_info=True)

    try:
        if getattr(player, "team_id", None):
            today = timezone.localdate()
            zones["next_session"] = (
                TrainingSession.objects.filter(
                    microcycle__team_id=player.team_id, session_date__gte=today
                )
                .exclude(status=TrainingSession.STATUS_CANCELED)
                .order_by("session_date", "id")
                .first()
            )
            if zones["next_session"] is not None:
                zones["next_session_attendance"] = TrainingSessionAttendance.objects.filter(
                    session=zones["next_session"], player=player
                ).first()
    except Exception:
        logger.debug("No se pudo cargar la próxima sesión del jugador", exc_info=True)

    # MI CUERPO -------------------------------------------------------------------------
    if vis.injuries:
        try:
            from .models import PlayerInjuryRecord

            # El parte abierto (sin alta) es el que le importa; si no hay ficha de lesión
            # pero el jugador está marcado como lesionado, al menos se le dice qué tiene.
            record = (
                PlayerInjuryRecord.objects.filter(player=player, return_date__isnull=True)
                .order_by("-injury_date", "-id")
                .first()
            )
            if record is not None:
                zones["active_injury"] = {
                    "name": record.injury,
                    "zone": record.injury_zone,
                    "since": record.injury_date,
                    "expected_return": record.estimated_return_date,
                }
            elif str(getattr(player, "injury", "") or "").strip():
                zones["active_injury"] = {
                    "name": player.injury,
                    "zone": getattr(player, "injury_zone", ""),
                    "since": getattr(player, "injury_date", None),
                    "expected_return": None,
                }
        except Exception:
            logger.debug("No se pudo cargar la lesión activa del jugador", exc_info=True)

    # MI VALORACIÓN ---------------------------------------------------------------------
    if vis.evaluation:
        try:
            from .models import PlayerEvaluation

            # Cerrada NO basta: sólo lo que el cuerpo técnico ha publicado a propósito. Y los
            # comentarios sólo si se marcaron al publicar (segunda llave).
            zones["evaluations"] = list(
                PlayerEvaluation.objects.filter(
                    player=player,
                    status=PlayerEvaluation.STATUS_CLOSED,
                    published_to_player=True,
                ).order_by("-evaluated_on", "-id")[:6]
            )
        except Exception:
            logger.debug("No se pudieron cargar las evaluaciones publicadas del jugador", exc_info=True)

    # MI TRABAJO ------------------------------------------------------------------------
    if vis.videos:
        try:
            inbox = VideoInboxItem.objects.filter(target_user=user).order_by("-created_at", "-id")
            zones["inbox_items"] = list(inbox[:6])
            zones["inbox_unread"] = int(inbox.filter(is_read=False).count())
        except Exception:
            logger.debug("No se pudo cargar el buzón de vídeo del jugador", exc_info=True)

    # CLUB ------------------------------------------------------------------------------
    if vis.fines:
        try:
            fines = list(PlayerFine.objects.filter(player=player).order_by("-created_at", "-id")[:12])
            zones["fines"] = fines
            zones["fines_total"] = int(
                PlayerFine.objects.filter(player=player).aggregate(total=Sum("amount")).get("total") or 0
            )
        except Exception:
            logger.debug("No se pudieron cargar las multas del jugador", exc_info=True)

    if vis.communication:
        try:
            # La misma regla que en la ficha: sólo lo que va dirigido a él y sólo cuando toca.
            zones["communications"] = list(
                PlayerCommunication.objects.filter(
                    player=player, category=PlayerCommunication.CATEGORY_CONVOCATION
                )
                .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=timezone.now()))
                .order_by("-created_at", "-id")[:8]
            )
        except Exception:
            logger.debug("No se pudieron cargar las comunicaciones del jugador", exc_info=True)

    return zones
