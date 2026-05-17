from __future__ import annotations

import base64
import io
import json
import zipfile

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def kit2d_generator_page(request):
    return render(request, "football/kit2d_generator.html", {})


@login_required
@require_POST
def kit2d_generate_api(request):
    """
    Genera 2 tokens PNG (kit 2D) a partir de una foto.

    - `club_png`: pensado para mostrarse junto al escudo (por defecto 96x96)
    - `editor_png`: pensado para la pizarra (por defecto 44x44, como las chapas/fotos)

    POST multipart:
      - image: fichero (jpg/png/heic)
      - club_size: int (opcional)
      - editor_size: int (opcional)
      - debug: 1/true (opcional) -> añade mask.png
      - format: "zip" (default) | "json"
      - mode: "warp" (default) | "template" | "cutout"
    """
    upload = request.FILES.get("image") or request.FILES.get("file")
    if not upload:
        return JsonResponse({"ok": False, "error": "Falta el archivo (campo 'image')."}, status=400)
    try:
        club_size = int(request.POST.get("club_size") or 96)
    except Exception:
        club_size = 96
    try:
        editor_size = int(request.POST.get("editor_size") or 44)
    except Exception:
        editor_size = 44

    debug_flag = str(request.POST.get("debug") or "").strip().lower() in {"1", "true", "yes", "on", "si"}
    out_format = str(request.POST.get("format") or request.GET.get("format") or "").strip().lower() or "zip"
    mode = str(request.POST.get("mode") or request.GET.get("mode") or "").strip().lower() or "warp"

    try:
        # Lazy import: OpenCV/numpy pueden pesar en cold start; evita impactar el arranque si no se usa.
        from .kit2d_generator import generate_kit2d_tokens

        payload = generate_kit2d_tokens(
            image_bytes=upload.read(),
            club_size=club_size,
            editor_size=editor_size,
            include_debug=debug_flag,
            mode=mode,
            pattern=str(request.POST.get("pattern") or request.GET.get("pattern") or "").strip(),
            base_color=str(request.POST.get("base_color") or request.GET.get("base_color") or "").strip(),
            stripe_color=str(request.POST.get("stripe_color") or request.GET.get("stripe_color") or "").strip(),
            logo_preset=str(request.POST.get("logo_preset") or request.GET.get("logo_preset") or "").strip(),
        )
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc) or "No se pudo generar el kit 2D."}, status=400)

    if out_format == "json":
        return JsonResponse(
            {
                "ok": True,
                "club_size": club_size,
                "editor_size": editor_size,
                "kit_club_png_b64": base64.b64encode(payload.club_png).decode("ascii"),
                "kit_editor_png_b64": base64.b64encode(payload.editor_png).decode("ascii"),
                "mask_png_b64": (base64.b64encode(payload.debug_mask_png).decode("ascii") if payload.debug_mask_png else ""),
            }
        )

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("kit_club.png", payload.club_png)
        zf.writestr("kit_editor.png", payload.editor_png)
        if payload.debug_mask_png:
            zf.writestr("mask.png", payload.debug_mask_png)
        meta = {
            "club_size": club_size,
            "editor_size": editor_size,
        }
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    mem.seek(0)

    resp = HttpResponse(mem.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = 'attachment; filename="kit2d.zip"'
    return resp
