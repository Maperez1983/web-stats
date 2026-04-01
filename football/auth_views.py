from __future__ import annotations

import re

from django.contrib.auth import views as auth_views
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
            if re.match(r"^/(coach|convocatoria|registro-acciones|incidencias|task-studio)\b", path):
                return True
            if path.startswith("/player/") or path.startswith("/players/") or path == "/":
                return False
            return True
        return False

    def get_success_url(self):
        requested_next = self.get_redirect_url()
        if self._is_blocked_next(self.request.user, requested_next):
            return reverse("dashboard-home")
        return requested_next or reverse("dashboard-home")

