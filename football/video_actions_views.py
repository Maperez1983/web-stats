"""
Del registro de acciones a los clips: el etiquetado en vivo sin etiquetar dos veces.

Vive en su propio módulo porque `video_studio_views` es sólo un puente que reexporta las vistas del
monolito, y meter aquí una vista de verdad la escondería.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST


@login_required
@require_POST
def analysis_video_clips_from_actions_api(request, video_id):
    """
    Convierte el registro de acciones de un partido en clips del vídeo.

    El entrenador ya etiquetó el domingo: aquí sólo se le dice al vídeo dónde cae cada anotación.
    Antes de generar hay que atar la grabación a su partido y decir en qué segundo empieza.
    """
    import json

    from django.http import JsonResponse

    from .models import Match, RivalVideo
    from .video_from_actions import clips_desde_el_registro
    from .views import (
        _forbid_if_no_coach_access,
        _forbid_if_workspace_module_disabled,
        _video_studio_resolve_video_for_request,
    )

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    forbidden = _forbid_if_workspace_module_disabled(request, "analysis", label="análisis")
    if forbidden:
        return forbidden

    video, equipo = _video_studio_resolve_video_for_request(request, video_id=int(video_id))
    if not video:
        return JsonResponse({"ok": False, "error": "Vídeo no disponible."}, status=404)

    try:
        datos = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except Exception:
        datos = {}

    def _ms(clave):
        try:
            return max(0, int(float(datos.get(clave) or 0) * 1000))
        except (TypeError, ValueError):
            return 0

    campos = []
    if datos.get("match_id") is not None:
        try:
            match_id = int(datos.get("match_id") or 0)
        except (TypeError, ValueError):
            match_id = 0
        partido = None
        if match_id and equipo:
            from .query_helpers import _team_match_queryset

            partido = _team_match_queryset(equipo).filter(id=match_id).first()
            if not partido:
                return JsonResponse({"ok": False, "error": "Partido no encontrado."}, status=404)
        video.match = partido
        campos.append("match")
    if "kickoff_s" in datos:
        video.kickoff_ms = _ms("kickoff_s")
        campos.append("kickoff_ms")
    if "second_half_s" in datos:
        video.second_half_ms = _ms("second_half_s")
        campos.append("second_half_ms")
    if campos:
        video.save(update_fields=campos)

    # Marcar el saque es un gesto aparte de generar: se hace viendo el vídeo, y muchas veces antes
    # de que exista el registro del partido.
    if datos.get("solo_marcar"):
        return JsonResponse({"ok": True, "marked": True, "match_id": video.match_id})

    if not video.match_id:
        return JsonResponse(
            {"ok": False, "error": "Ata primero la grabación a su partido."}, status=400
        )

    duracion = None
    try:
        duracion = int(float(datos.get("duration_s") or 0) * 1000) or None
    except (TypeError, ValueError):
        duracion = None

    creados, saltados, sin_minuto = clips_desde_el_registro(
        video,
        creado_por=request.user.get_username() if request.user.is_authenticated else "",
        duracion_ms=duracion,
    )
    return JsonResponse(
        {"ok": True, "created": creados, "skipped": saltados, "without_minute": sin_minuto}
    )
