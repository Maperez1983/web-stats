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
    slowest = max(queries, key=lambda q: float(q.get("time") or 0.0)) if queries else {}
    slowest_sql = str(slowest.get("sql") or "")
    # Lo que importa de la consulta cara es que columnas trae y por que filtra, no la lista
    # entera de campos: cortamos por FROM para ver el WHERE completo.
    from_at = slowest_sql.find(" FROM ")
    slowest_tail = slowest_sql[from_at:from_at + 900] if from_at != -1 else slowest_sql[:900]
    slowest_cols = slowest_sql[:from_at].count(",") + 1 if from_at != -1 else 0
    return JsonResponse(
        {
            "ok": True,
            "status": status,
            "html_kb": round(body_bytes / 1024.0, 1),
            "total_ms": round(total_ms, 1),
            "sql_ms": round(sql_ms, 1),
            "python_ms": round(total_ms - sql_ms, 1),
            "query_count": len(queries),
            "slowest_ms": round(float(slowest.get("time") or 0.0) * 1000.0, 1),
            "slowest_columns": slowest_cols,
            "slowest_from_where": slowest_tail,
            "top_queries": [
                {"n": v["n"], "ms": round(v["ms"], 1), "sql": k} for k, v in top
            ],
        }
    )


def task_meta_light_audit_view(request):
    """
    ¿Dice lo mismo la copia ligera que el campo gordo? (coach-gated)

    Los listados pasaron a leer `task_layout_light` para poder diferir `tactical_layout`. Si la
    copia ligera estuviera vacía o desfasada en alguna fila, esa tarea se clasificaría distinto
    (ámbito, importada, realizada, repositorio) y aparecería o desaparecería de la biblioteca sin
    que nadie la haya tocado. Esto compara clave a clave las dos fuentes y saca solo las que NO
    coinciden.
    """
    from .models import SessionTask
    from .permissions import can_access_sessions_workspace

    if not can_access_sessions_workspace(request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        team_id = int(request.GET.get("team") or 0)
    except Exception:
        team_id = 0
    if not team_id:
        return JsonResponse({"ok": False, "error": "falta ?team="}, status=400)

    watched = ("scope", "source", "pdf_source_name", "import_mode", "performed_on",
               "repository", "library_repo", "library_repository")
    rows = (
        SessionTask.objects.filter(session__microcycle__team_id=team_id, deleted_at__isnull=True)
        .order_by("-id")[:400]
    )
    total = 0
    empty_light = []
    mismatches = []
    for task in rows:
        total += 1
        light = task.task_layout_light if isinstance(task.task_layout_light, dict) else {}
        full = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        lmeta = light.get("meta") if isinstance(light.get("meta"), dict) else None
        fmeta = full.get("meta") if isinstance(full.get("meta"), dict) else {}
        if lmeta is None:
            empty_light.append({"id": task.id, "title": str(task.title or "")[:60]})
            continue
        diff = {
            key: {"light": lmeta.get(key), "full": fmeta.get(key)}
            for key in watched
            if str(lmeta.get(key) or "") != str(fmeta.get(key) or "")
        }
        if diff:
            mismatches.append({"id": task.id, "title": str(task.title or "")[:60], "diff": diff})

    return JsonResponse(
        {
            "ok": True,
            "tasks_checked": total,
            "sin_copia_ligera": empty_light,
            "discrepancias": mismatches,
            "veredicto": "coinciden" if not empty_light and not mismatches else "REVISAR",
        }
    )
