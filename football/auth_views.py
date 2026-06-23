from __future__ import annotations

import logging
import os
import re
from urllib.parse import quote, urlparse

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django.utils.html import escape
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import AppUserRole, ServiceAccessToken
from .workspace_context import can_access_platform as workspace_can_access_platform
from .workspace_context import available_workspaces_for_user as workspace_available_workspaces_for_user
from .workspace_context import get_user_role as workspace_get_user_role


logger = logging.getLogger(__name__)
auth_logger = logging.getLogger("webstats.auth")


_get_user_role = workspace_get_user_role


_can_access_platform = workspace_can_access_platform


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
            logger.debug("APP_PUBLIC_BASE_URL no se pudo parsear como URL: %s", explicit, exc_info=True)
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
    if _is_safari_user_agent(ua):
        return True
    # WKWebView / iOS embebido: a veces el UA no incluye "Safari" (o viene recortado),
    # pero el problema de cookies en 302 es el mismo. Detectamos iOS/iPadOS por markers.
    try:
        ua_l = str(ua or "").lower()
    except Exception:
        ua_l = ""
    if not ua_l:
        return False
    ios_markers = ("iphone", "ipad", "ipod")
    if any(marker in ua_l for marker in ios_markers) and "applewebkit" in ua_l and "mobile" in ua_l:
        return True
    # iPadOS modernos a veces reportan "Macintosh" pero con AppleWebKit + Mobile.
    if "macintosh" in ua_l and "applewebkit" in ua_l and "mobile" in ua_l:
        return True
    return False


def _post_login_redirect_target(request, user, requested_next: str = "") -> str:
    requested_next = str(requested_next or "").strip()
    if _is_blocked_next_for_user(user, requested_next):
        return reverse("dashboard-home")
    if requested_next:
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
                logger.debug("No se pudo resolver next post-login %s", path, exc_info=True)
    if requested_next:
        return requested_next
    if _can_access_platform(user):
        try:
            if hasattr(request, "session") and int(request.session.get("active_workspace_id") or 0) > 0:
                return f"{reverse('dashboard-home')}?home=club"
        except Exception:
            logger.debug("No se pudo leer active_workspace_id post-login", exc_info=True)
        return reverse("platform-overview")
    return reverse("dashboard-home")


def _is_blocked_next_for_user(user, next_url: str) -> bool:
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
        # Diagnóstico opcional: loguea señales de sesión/cookies para depurar bucles de login.
        try:
            if str(os.getenv("LOGIN_DEBUG") or "").strip().lower() in {"1", "true", "yes", "on"}:
                try:
                    host = str(self.request.get_host() or "")
                except Exception:
                    logger.debug("No se pudo leer host durante diagnostico de login", exc_info=True)
                    host = ""
                try:
                    ua = str(getattr(self.request, "META", {}).get("HTTP_USER_AGENT") or "")
                except Exception:
                    logger.debug("No se pudo leer user agent durante diagnostico de login", exc_info=True)
                    ua = ""
                try:
                    cookie_header = str(getattr(self.request, "META", {}).get("HTTP_COOKIE") or "")
                except Exception:
                    logger.debug("No se pudo leer cookies durante diagnostico de login", exc_info=True)
                    cookie_header = ""
                auth_logger.warning(
                    "login_valid user=%s host=%s ua=%s cookie_header_len=%s js_redirect=%s",
                    str(getattr(self.request.user, "username", "") or ""),
                    host,
                    (ua[:140] + "…") if len(ua) > 140 else ua,
                    len(cookie_header or ""),
                    _should_login_js_redirect(self.request),
                )
        except Exception:
            logger.debug("No se pudo emitir diagnostico de login", exc_info=True)
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
            logger.debug("No se pudo aplicar expiracion extendida de sesion", exc_info=True)

        # Safari/WebKit: evita loop de login si el navegador ignora Set-Cookie en 302.
        # En lugar de redirigir con 302, devolvemos 200 + JS/meta refresh (manteniendo cookies).
        try:
            if not _should_login_js_redirect(self.request):
                return response
            target = ""
            try:
                target = str(getattr(response, "url", "") or response.get("Location") or "").strip()
            except Exception:
                logger.debug("No se pudo leer destino de respuesta de login", exc_info=True)
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
                            logger.debug("No se pudo copiar cookie %s en respuesta JS de login", name, exc_info=True)
                            continue
            except Exception:
                logger.debug("No se pudieron copiar cookies a respuesta JS de login", exc_info=True)
            return js_response
        except Exception:
            logger.debug("No se pudo construir respuesta JS de login; usando respuesta original", exc_info=True)
            return response
        return response

    def _is_blocked_next(self, user, next_url: str) -> bool:
        return _is_blocked_next_for_user(user, next_url)

    def get_success_url(self):
        return _post_login_redirect_target(self.request, self.request.user, self.get_redirect_url())


def _extract_service_token(request) -> str:
    header = str(getattr(request, "headers", {}).get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        candidate = header.split(None, 1)[1].strip()
        if candidate:
            return candidate
    for key in ("X-Service-Token", "X-Api-Key", "service_token", "token"):
        candidate = str(getattr(request, "headers", {}).get(key) or request.POST.get(key) or request.GET.get(key) or "").strip()
        if candidate:
            return candidate
    return ""


def _service_login_get_form(request) -> HttpResponse:
    next_url = escape(str(request.GET.get("next") or "").strip())
    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Acceso de servicio</title>
  <style>
    body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif; margin: 0; padding: 32px; background: #0f172a; color: #e2e8f0; }}
    .card {{ max-width: 520px; margin: 0 auto; background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 24px; }}
    input {{ width: 100%; box-sizing: border-box; margin: 8px 0 16px; padding: 12px 14px; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #f8fafc; }}
    button {{ padding: 12px 16px; border: 0; border-radius: 10px; background: #22c55e; color: #052e16; font-weight: 700; cursor: pointer; }}
    small {{ color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Acceso de servicio</h1>
    <p>Pega un token de servicio para abrir una sesión de usuario en la app.</p>
    <form method="post">
      <input type="hidden" name="next" value="{next_url}">
      <label for="service_token">Token</label>
      <input id="service_token" name="service_token" type="password" autocomplete="off" spellcheck="false" autofocus>
      <button type="submit">Entrar</button>
    </form>
    <p><small>Este endpoint intercambia un token de servicio por una sesión de Django.</small></p>
  </div>
</body>
</html>"""
    response = HttpResponse(html)
    response["Cache-Control"] = "no-store"
    return response


def _service_login_failure(request, message: str, status_code: int = 403):
    wants_json = "application/json" in str(getattr(request, "headers", {}).get("Accept") or "")
    if wants_json:
        return JsonResponse({"ok": False, "error": message}, status=status_code)
    response = _service_login_get_form(request)
    response.status_code = status_code
    response.content = response.content.replace(b"</h1>", f"</h1><p style=\"color:#fca5a5;\">{escape(message)}</p>".encode("utf-8"))
    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def service_token_login_page(request):
    if request.method == "GET":
        return _service_login_get_form(request)

    raw_token = _extract_service_token(request)
    if not raw_token:
        return _service_login_failure(request, "Falta el token de servicio.", status_code=400)

    token_prefix = ServiceAccessToken._token_prefix(raw_token)
    candidates = (
        ServiceAccessToken.objects
        .select_related("user", "workspace")
        .filter(is_active=True, token_prefix=token_prefix)
        .order_by("-created_at", "-id")
    )
    token_obj = None
    for candidate in candidates[:10]:
        if candidate.check_token(raw_token):
            token_obj = candidate
            break
    if not token_obj:
        return _service_login_failure(request, "Token de servicio inválido o desactivado.")
    if token_obj.is_expired():
        return _service_login_failure(request, "Token de servicio caducado.")

    user = getattr(token_obj, "user", None)
    if not user or not user.is_active:
        return _service_login_failure(request, "El usuario asociado al token no está activo.")

    auth_login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])

    try:
        if token_obj.expires_at:
            remaining = int((token_obj.expires_at - timezone.now()).total_seconds())
            if remaining > 0:
                request.session.set_expiry(remaining)
    except Exception:
        logger.debug("No se pudo ajustar expiracion de sesion desde token", exc_info=True)

    try:
        available_qs = workspace_available_workspaces_for_user(user)
        if token_obj.workspace_id and available_qs.filter(id=token_obj.workspace_id).exists():
            request.session["active_workspace_id"] = int(token_obj.workspace_id)
    except Exception:
        logger.debug("No se pudo fijar active_workspace_id desde token", exc_info=True)

    try:
        token_obj.last_used_at = timezone.now()
        token_obj.save(update_fields=["last_used_at"])
    except Exception:
        logger.debug("No se pudo actualizar last_used_at del token", exc_info=True)

    next_url = str(request.POST.get("next") or request.GET.get("next") or "").strip()
    redirect_url = _post_login_redirect_target(request, user, next_url)
    wants_json = "application/json" in str(getattr(request, "headers", {}).get("Accept") or "")
    if wants_json:
        return JsonResponse(
            {
                "ok": True,
                "redirect": redirect_url,
                "username": getattr(user, "username", ""),
                "workspace_id": int(request.session.get("active_workspace_id") or 0) or None,
            }
        )
    return redirect(redirect_url)
