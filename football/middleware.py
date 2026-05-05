from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin


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
