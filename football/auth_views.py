from __future__ import annotations

import os
import re
from urllib.parse import quote, urlparse

from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.html import escape

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
        # Robustez: si alguien configura APP_PUBLIC_BASE_URL con path (p.ej. https://app.x.com/2J),
        # nos quedamos solo con el origin para evitar redirecciones rotas.
        try:
            raw = explicit
            if "://" not in raw:
                raw = f"https://{raw}"
            parsed = urlparse(raw)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        except Exception:
            pass
        # Fallback defensivo: elimina cualquier path accidental.
        cleaned = explicit.strip().rstrip("/")
        if "://" in cleaned:
            scheme, rest = cleaned.split("://", 1)
            host = rest.split("/", 1)[0]
            cleaned = f"{scheme}://{host}"
        else:
            cleaned = cleaned.split("/", 1)[0]
        return cleaned.rstrip("/")
    return _guess_app_base_url_from_host(_request_host(request)).rstrip("/")


def _is_safari_user_agent(ua: str) -> bool:
    ua = str(ua or "").strip().lower()
    if not ua or "safari" not in ua:
        return False
    blocked_markers = ("chrome", "chromium", "crios", "fxios", "edg", "opr", "opera")
    if any(marker in ua for marker in blocked_markers):
        return False
    return True


def _should_login_js_redirect(request) -> bool:
    """
    Workaround para WebKit/Safari: en algunos entornos el navegador puede ignorar el Set-Cookie
    en una respuesta 302 tras un POST de login, provocando loop /login/ (la sesión no persiste).

    - LOGIN_JS_REDIRECT=true: fuerza siempre.
    - LOGIN_JS_REDIRECT=false: desactiva siempre.
    - (por defecto): auto → solo Safari.
    """
    mode = str(os.getenv("LOGIN_JS_REDIRECT") or "").strip().lower()
    if mode in {"0", "false", "no", "off"}:
        return False
    if mode in {"1", "true", "yes", "on"}:
        return True
    try:
        ua = str(getattr(request, "META", {}).get("HTTP_USER_AGENT") or "")
    except Exception:
        ua = ""
    return _is_safari_user_agent(ua)


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
    redirect_authenticated_user = True

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
        if host in landing_hosts and not host.startswith("app."):
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
            # Importante (iPad/WKWebView): no forzamos sesiones "de navegador" (set_expiry(0)),
            # porque pueden perderse al cambiar de app, abrir PDFs o por presión de memoria.
            # Si el usuario marca "Mantener sesión", extendemos explícitamente la expiración.
            # Si no lo marca (o el campo no llega), dejamos la expiración por defecto del sistema
            # (SESSION_COOKIE_AGE), que ya es amplia (y puede ser deslizante si se configura SESSION_SAVE_EVERY_REQUEST).
            if remember:
                days = int(str(os.getenv("REMEMBER_SESSION_DAYS", "30") or "30").strip() or 30)
                days = max(1, min(days, 365))
                self.request.session.set_expiry(days * 86400)
        except Exception:
            pass

        # Safari/WebKit: evita loop de login si el navegador ignora Set-Cookie en 302.
        # En lugar de redirigir con 302, devolvemos 200 + JS/meta refresh (manteniendo cookies).
        try:
            if not _should_login_js_redirect(self.request):
                return response
            target = ""
            try:
                target = str(getattr(response, "url", "") or response.get("Location") or "").strip()
            except Exception:
                target = ""
            if not target:
                target = str(self.get_success_url() or "").strip()
            if not target:
                return response
            safe_target = escape(target)
            html = (
                "<!doctype html><html lang=\"es\"><head>"
                "<meta charset=\"utf-8\"/>"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"/>"
                f"<meta http-equiv=\"refresh\" content=\"0;url={safe_target}\"/>"
                "<title>Entrando…</title>"
                "</head><body style=\"font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;\">"
                "<p>Entrando…</p>"
                f"<p><a href=\"{safe_target}\">Continuar</a></p>"
                f"<script>window.location.replace({target!r});</script>"
                "</body></html>"
            )
            js_response = HttpResponse(html, status=200)
            js_response["Cache-Control"] = "no-store"
            try:
                original_cookies = getattr(response, "cookies", None)
                if original_cookies:
                    for name, morsel in original_cookies.items():
                        try:
                            js_response.cookies[name] = morsel.value
                            for k, v in morsel.items():
                                if v not in (None, "", False):
                                    js_response.cookies[name][k] = v
                        except Exception:
                            continue
            except Exception:
                pass
            return js_response
        except Exception:
            return response
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
            # Si `next` apunta a una ruta inexistente (links viejos, errores de JS),
            # evitamos mandar al usuario a un 404 tras loguearse.
            try:
                path = str(requested_next).split("?", 1)[0]
            except Exception:
                path = ""
            if path and path.startswith(("/static/", "/media/")):
                return requested_next
            if path and path.startswith("/"):
                try:
                    resolve(path)
                except Resolver404:
                    requested_next = ""
                except Exception:
                    pass
        if requested_next:
            return requested_next
        # Producto: usuario de plataforma aterriza en /platform/ para elegir cliente/espacio.
        if _can_access_platform(self.request.user):
            # Si ya hay un cliente activo, evitamos “reiniciar” siempre en Platform al abrir la app.
            try:
                if hasattr(self.request, "session") and int(self.request.session.get("active_workspace_id") or 0) > 0:
                    return f"{reverse('dashboard-home')}?home=club"
            except Exception:
                pass
            return reverse("platform-overview")
        return reverse("dashboard-home")
