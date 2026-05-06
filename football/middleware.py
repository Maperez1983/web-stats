from __future__ import annotations

import os
from urllib.parse import urlparse

from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class CanonicalHostMiddleware(MiddlewareMixin):
    """
    Evita redirecciones rotas / bucles de login por mezcla de hostnames en producción.

    Caso típico: la app se sirve bajo un dominio "canónico" (p.ej. `app.segundajugada.es`)
    pero algún link/acción acaba en el hostname interno del proveedor (p.ej. `*.onrender.com`).
    Eso rompe la cookie de sesión y parece que "te desloguea al pulsar botones".

    Comportamiento:
    - Si `APP_PUBLIC_BASE_URL` está definido, redirige (GET/HEAD) al host canónico conservando path+query.
    - Respeta `LANDING_HOSTS`: no fuerza canónico cuando el usuario navega por la landing comercial.
    """

    def process_request(self, request):
        explicit = str(os.getenv("APP_PUBLIC_BASE_URL") or "").strip()
        if not explicit:
            return None

        # Normaliza origin (sin path).
        try:
            raw = explicit if "://" in explicit else f"https://{explicit}"
            parsed = urlparse(raw)
            canonical_host = (parsed.netloc or "").split(":", 1)[0].strip().lower()
            canonical_scheme = (parsed.scheme or "https").strip().lower() or "https"
        except Exception:
            return None

        if not canonical_host or canonical_host in {"localhost", "127.0.0.1"}:
            return None

        try:
            req_host = str(request.get_host() or "").split(":", 1)[0].strip().lower()
        except Exception:
            req_host = ""
        if not req_host or req_host == canonical_host:
            return None

        landing_hosts = [
            h.strip().lower()
            for h in (os.getenv("LANDING_HOSTS") or "segundajugada.es,www.segundajugada.es,segundajugada.com,www.segundajugada.com").split(",")
            if h.strip()
        ]
        if req_host in landing_hosts and not req_host.startswith("app."):
            return None

        method = str(getattr(request, "method", "") or "").upper()
        if method not in {"GET", "HEAD"}:
            return None

        path = str(getattr(request, "get_full_path", lambda: "/")() or "/")
        target = f"{canonical_scheme}://{canonical_host}{path}"
        return redirect(target)


class CookieDomainSanitizerMiddleware(MiddlewareMixin):
    """
    Evita bucles de login por cookies con Domain inválido.

    Problema típico:
    - En Render (y otros PaaS), dominios como `onrender.com` están en la Public Suffix List.
      Si intentas setear cookies con `Domain=onrender.com` o `.onrender.com`, el navegador las bloquea.
    - Si se configura `COOKIE_DOMAIN` para un dominio personalizado pero el usuario entra por otro host
      (p.ej. `*.onrender.com`), el navegador también ignorará la cookie y se produce loop /login.

    Solución:
    - En respuestas que incluyan cookies de sesión/CSRF, eliminamos el atributo Domain cuando:
      - el dominio de la cookie es un public suffix conocido (`onrender.com`), o
      - el host de la request no pertenece al dominio configurado.

    Resultado: cookie host-only ⇒ login estable en el host real por el que entra el usuario.
    """

    _PUBLIC_SUFFIX_BLOCKLIST = {"onrender.com"}

    def process_response(self, request, response):
        try:
            request_host = str(request.get_host() or "").split(":", 1)[0].strip().lower()
        except Exception:
            request_host = ""
        if not request_host or not getattr(response, "cookies", None):
            return response

        session_cookie_name = str(getattr(settings, "SESSION_COOKIE_NAME", "sessionid") or "sessionid")
        csrf_cookie_name = str(getattr(settings, "CSRF_COOKIE_NAME", "csrftoken") or "csrftoken")
        target_cookie_names = {session_cookie_name, csrf_cookie_name}

        for name in list(getattr(response, "cookies", {}).keys()):
            if name not in target_cookie_names:
                continue
            try:
                morsel = response.cookies.get(name)
            except Exception:
                morsel = None
            if not morsel:
                continue

            try:
                raw_domain = str(morsel.get("domain") or "").strip()
            except Exception:
                raw_domain = ""
            if not raw_domain:
                continue

            domain = raw_domain.lstrip(".").lower()
            if not domain:
                continue

            is_blocklisted = domain in self._PUBLIC_SUFFIX_BLOCKLIST or any(
                domain.endswith(f".{suffix}") for suffix in self._PUBLIC_SUFFIX_BLOCKLIST
            )
            # Si el host no está dentro del dominio, el navegador ignorará la cookie ⇒ quitar Domain.
            host_mismatch = not request_host.endswith(domain)

            if is_blocklisted or host_mismatch:
                try:
                    del morsel["domain"]
                except Exception:
                    # fallback: establecer a vacío (algunos objetos lo aceptan)
                    try:
                        morsel["domain"] = ""
                    except Exception:
                        pass

        return response


class StickyTeamContextMiddleware(MiddlewareMixin):
    """
    Evita que la navegación "pierda" el equipo activo y mande al usuario a onboarding.

    - Si llega `?team=<id>` y la sesión existe, persiste `active_team_id` para siguientes pantallas.
    - Si llega un POST con `team`, también lo persiste.

    No cambia permisos: solo guarda el id para que `_get_active_team_for_request` lo use.
    """

    def process_request(self, request):
        try:
            if not hasattr(request, "session"):
                return None
            raw = request.GET.get("team") or request.GET.get("team_id")
            if not raw:
                return None
            team_id = int(str(raw).strip())
            if team_id > 0:
                request.session["active_team_id"] = team_id
        except Exception:
            return None
        return None
