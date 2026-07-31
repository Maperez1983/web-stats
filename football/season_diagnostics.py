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


def sessions_perf_view(request):
    """
    Diagnóstico de RENDIMIENTO de la pantalla de Entrenamiento (coach-gated).

    Entrar en Entrenamiento tarda ~5 s de forma constante, mientras que la biblioteca (que lista
    lo mismo) va en 0,4 s. Sin acceso a la base de datos de producción no se puede perfilar a
    ciegas: esto ejecuta la propia vista con el cursor de depuración puesto y devuelve dónde se
    va el tiempo (SQL vs Python) y las consultas más caras.
    """
    import time

    from django.db import connection, reset_queries

    from .permissions import can_access_sessions_workspace
    from .views import _sessions_workspace_page

    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    force_debug = connection.force_debug_cursor
    connection.force_debug_cursor = True
    reset_queries()
    started = time.perf_counter()
    try:
        response = _sessions_workspace_page(request, scope_key="coach", scope_title="Sesiones · Entrenador")
        # El render es perezoso: sin esto medimos solo la vista y no la plantilla.
        try:
            response.render()
        except Exception:
            pass
        body_bytes = len(getattr(response, "content", b"") or b"")
        status = getattr(response, "status_code", 0)
    finally:
        total_ms = (time.perf_counter() - started) * 1000.0
        queries = list(connection.queries)
        connection.force_debug_cursor = force_debug

    sql_ms = sum(float(q.get("time") or 0.0) for q in queries) * 1000.0
    by_shape = {}
    for q in queries:
        sql = str(q.get("sql") or "")
        # Agrupa por "forma": las mismas consultas repetidas en bucle son el patrón a cazar.
        shape = sql[:110]
        entry = by_shape.setdefault(shape, {"n": 0, "ms": 0.0})
        entry["n"] += 1
        entry["ms"] += float(q.get("time") or 0.0) * 1000.0

    top = sorted(by_shape.items(), key=lambda kv: kv[1]["ms"], reverse=True)[:12]
    return JsonResponse(
        {
            "ok": True,
            "status": status,
            "html_kb": round(body_bytes / 1024.0, 1),
            "total_ms": round(total_ms, 1),
            "sql_ms": round(sql_ms, 1),
            "python_ms": round(total_ms - sql_ms, 1),
            "query_count": len(queries),
            "top_queries": [
                {"n": v["n"], "ms": round(v["ms"], 1), "sql": k} for k, v in top
            ],
        }
    )
