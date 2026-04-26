from __future__ import annotations

import os
import re
from urllib.parse import quote

from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.urls import reverse

from .models import AppUserRole


def _get_user_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    role_obj = getattr(user, "app_role", None)
    role = str(getattr(role_obj, "role", "") or "").strip() or None
    legacy_map = {
        "admin": AppUserRole.ROLE_ADMIN,
        "player": AppUserRole.ROLE_PLAYER,
    }
    normalized_role = legacy_map.get(role, role)
    if normalized_role:
        return normalized_role
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return AppUserRole.ROLE_ADMIN
    return None


def _can_access_platform(user):
    role = _get_user_role(user)
    return bool(user and getattr(user, "is_authenticated", False) and (getattr(user, "is_superuser", False) or getattr(user, "is_staff", False) or role == AppUserRole.ROLE_ADMIN))


def _split_csv(raw: str) -> list[str]:
    return [item.strip().lower() for item in str(raw or "").split(",") if item.strip()]


def _request_host(request) -> str:
    try:
        host = str(request.get_host() or "")
    except Exception:
        host = ""
    return host.split(":", 1)[0].strip().lower()


def _guess_app_base_url_from_host(host: str) -> str:
    host = str(host or "").strip().lower()
    host = host.split(":", 1)[0].strip()
    if not host:
        return "https://app.segundajugada.es"
    if host.startswith("app."):
        return f"https://{host}"
    if host.startswith("www."):
        host = host[4:]
    return f"https://app.{host}"


def _resolve_app_base_url(request) -> str:
    explicit = str(os.getenv("APP_PUBLIC_BASE_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    return _guess_app_base_url_from_host(_request_host(request)).rstrip("/")


class RoleAwareLoginView(auth_views.LoginView):
    """
    LoginView con redirección post-login "segura" por rol.

    Problema real: si un admin estaba en /platform/ y luego intenta entrar con un jugador
    (o cualquier rol sin permisos de plataforma), el parámetro `next=/platform/` hace
    que, tras loguearse correctamente, el usuario vea un 403 inmediato.

    Este view ignora `next` cuando apunta a rutas claramente prohibidas por rol
    y redirige a la home (`/`), dejando que `dashboard_page` haga el enrutado final.
    """

    template_name = "registration/login.html"
    authentication_form = None

    # iOS/WKWebView a veces autocapitaliza el primer carácter o añade espacios invisibles.
    # Normalizamos aquí para que el login sea robusto sin exigir al usuario "teclear perfecto".
    class LowercaseUsernameAuthenticationForm(AuthenticationForm):
        def clean_username(self):
            raw = self.cleaned_data.get("username")
            if raw is None:
                return ""
            value = str(raw).strip()
            return value.lower()

    authentication_form = LowercaseUsernameAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        public_signup_enabled = str(os.getenv("ENABLE_PUBLIC_SIGNUP", "0") or "").strip().lower() in {"1", "true", "yes", "on"}
        context["public_signup_enabled"] = public_signup_enabled
        return context

    def dispatch(self, request, *args, **kwargs):
        # Producto: `segundajugada.es` es solo landing. El login debe vivir en `app.*`.
        host = _request_host(request)
        landing_hosts = _split_csv(
            os.getenv("LANDING_HOSTS")
            or "segundajugada.es,www.segundajugada.es,segundajugada.com,www.segundajugada.com"
        )
        if host in landing_hosts:
            app_base = _resolve_app_base_url(request)
            next_url = str(request.GET.get("next") or "").strip()
            suffix = f"?next={quote(next_url)}" if next_url else ""
            return redirect(f"{app_base}/login/{suffix}")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        # UX: "Mantener sesión" para iPad/WKWebView (evita pedir contraseña cada vez).
        # No guardamos contraseñas: solo extendemos la validez de la cookie de sesión.
        try:
            remember_raw = str(self.request.POST.get("remember_session") or "").strip().lower()
            remember = remember_raw in {"1", "true", "yes", "on"}
            if remember:
                days = int(str(os.getenv("REMEMBER_SESSION_DAYS", "30") or "30").strip() or 30)
                days = max(1, min(days, 365))
                self.request.session.set_expiry(days * 86400)
            else:
                self.request.session.set_expiry(0)
        except Exception:
            pass
        return response

    def _is_blocked_next(self, user, next_url: str) -> bool:
        if not next_url:
            return False
        path = str(next_url).split("?", 1)[0]
        if not path.startswith("/"):
            return False

        # Siempre bloqueamos rutas de plataforma/admin si el usuario no es admin.
        if path.startswith("/platform") or path.startswith("/admin-tools") or path.startswith("/admin/"):
            return not _can_access_platform(user)

        role = _get_user_role(user) or AppUserRole.ROLE_PLAYER
        if role == AppUserRole.ROLE_PLAYER:
            # Un jugador no debería aterrizar en módulos de staff por `next`.
            if re.match(r"^/(coach|convocatoria|registro-acciones|incidencias)\b", path):
                return True
            if path.startswith("/player/") or path.startswith("/players/") or path == "/":
                return False
            return True
        return False

    def get_success_url(self):
        requested_next = self.get_redirect_url()
        if self._is_blocked_next(self.request.user, requested_next):
            return reverse("dashboard-home")
        if requested_next:
            return requested_next
        # Producto: usuario de plataforma aterriza en /platform/ para elegir cliente/espacio.
        if _can_access_platform(self.request.user):
            return reverse("platform-overview")
        return reverse("dashboard-home")
