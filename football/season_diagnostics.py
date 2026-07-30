"""
Diagnóstico de TEMPORADA (coach-gated).

Motivo: el selector de Entrenamiento dice "2026/2027" pero la lista sigue mezclando sesiones y
microciclos de 25/26. Sin acceso a la base de datos de producción, la única forma honesta de
saber por qué es preguntárselo a la propia app: qué temporadas existen, cuál se está usando de
verdad para filtrar, y a qué temporada pertenece cada fila que aparece.
"""
from __future__ import annotations

from django.http import JsonResponse


def _iso(value):
    try:
        return value.isoformat()
    except Exception:
        return str(value or "")


def season_debug_view(request):
    from .models import TrainingMicrocycle, TrainingSession, WorkspaceSeason
    from .permissions import can_access_sessions_workspace
    from .views import (
        _get_active_workspace,
        _selected_club_season_bounds,
    )

    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    workspace = _get_active_workspace(request)
    season, start, end = _selected_club_season_bounds(request, workspace=workspace)

    seasons = []
    if workspace:
        for row in WorkspaceSeason.objects.filter(workspace=workspace).order_by("-start_date", "-id"):
            seasons.append({
                "id": int(row.id),
                "label": row.label,
                "inicio": _iso(row.start_date),
                "fin": _iso(row.end_date),
                "activa": bool(row.is_active),
            })

    try:
        team_id = int(request.GET.get("team") or 0)
    except Exception:
        team_id = 0

    sesiones = []
    qs = TrainingSession.objects.select_related("club_season", "microcycle").order_by("-session_date", "-id")
    if team_id:
        qs = qs.filter(microcycle__team_id=team_id)
    for s in qs[:25]:
        sesiones.append({
            "id": int(s.id),
            "fecha": _iso(getattr(s, "session_date", None)),
            "temporada": getattr(getattr(s, "club_season", None), "label", None),
            "microciclo": getattr(getattr(s, "microcycle", None), "title", ""),
        })

    microciclos = []
    mqs = TrainingMicrocycle.objects.order_by("-week_start", "-id")
    if team_id:
        mqs = mqs.filter(team_id=team_id)
    for m in mqs[:25]:
        microciclos.append({
            "id": int(m.id),
            "titulo": getattr(m, "title", ""),
            "semana": _iso(getattr(m, "week_start", None)),
        })

    return JsonResponse({
        "ok": True,
        "workspace": getattr(workspace, "name", None),
        "temporada_usada_para_filtrar": {
            "label": getattr(season, "label", None),
            "id": getattr(season, "id", None),
            "desde": _iso(start),
            "hasta": _iso(end),
        },
        "temporadas": seasons,
        "sesiones_recientes": sesiones,
        "microciclos_recientes": microciclos,
    }, json_dumps_params={"ensure_ascii": False})
