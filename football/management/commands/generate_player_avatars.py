"""Genera OFFLINE el avatar de cada jugador (face-swap con su foto + peinado + color + altura).

Es un paso LOCAL: depende de insightface (+ modelo inswapper_128.onnx) que NO están en producción.
Los imports pesados son perezosos para que importar este módulo (p. ej. en `manage.py check` en
prod) no falle. El resultado se guarda en Player.avatar_generated y el resolver lo sirve en
pizarra / 11 / editor. Regenera solo si cambian las entradas (avatar_source_key).

Uso:
    python manage.py generate_player_avatars --all
    python manage.py generate_player_avatars --player 42 --force

Config de rutas (opcional):
    AVATAR_INSWAPPER=/ruta/inswapper_128.onnx   (por defecto ~/ai-image-gen/inswapper_128.onnx)
"""
import hashlib
import io
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from football.models import Player

STYLE_OVERLAYS = {"medio": "medio.png", "rizado": "rizado.png", "largo": "largo.png"}  # 'corto'/'' = pelo base
# Paleta de grado de piel 1-6 (igual que views.AVATAR_SKIN_GRADES) para el avatar SIN foto.
AVATAR_SKIN_GRADES = {
    1: (236, 205, 178), 2: (224, 176, 136), 3: (200, 144, 95),
    4: (165, 106, 60), 5: (109, 67, 40), 6: (74, 45, 26),
}


def _asset(*parts):
    from pathlib import Path
    for base in (
        Path(settings.BASE_DIR) / "football" / "static" / "football" / "images" / "coach_roster_avatars",
        Path(settings.BASE_DIR) / "static" / "football" / "images" / "coach_roster_avatars",
    ):
        p = base.joinpath(*parts)
        if p.exists():
            return str(p)
    return None


def _find_player_photo_name(player):
    """La foto del jugador NO es un campo del modelo: se guarda por convención en
    player-photos/player-<id>.<ext>. Devuelve el nombre de almacenamiento que exista, o ''."""
    from django.core.files.storage import default_storage
    pid = int(getattr(player, "id", 0) or 0)
    if not pid:
        return ""
    for ext in ("png", "jpg", "jpeg", "webp"):
        name = f"player-photos/player-{pid}.{ext}"
        try:
            if default_storage.exists(name):
                return name
        except Exception:
            pass
    return ""


def _inputs_key(player, photo_name=""):
    """Hash de las entradas del avatar. Agnóstico del almacenamiento (local o S3): usa
    name+size del fichero de foto (resuelto por convención) + características."""
    from django.core.files.storage import default_storage
    h = hashlib.sha1()
    if photo_name:
        try:
            h.update(f"{photo_name}:{default_storage.size(photo_name)}".encode())
        except Exception:
            h.update(photo_name.encode())
    else:
        h.update(b"nophoto")
    for v in (player.hairstyle, player.hair_color, player.skin_grade, player.height_cm):
        h.update(f"|{v}".encode())
    return h.hexdigest()


def _read_photo_bgr(photo_name):
    """Lee la foto (local o S3) como BGR para OpenCV, vía la API de almacenamiento (no .path)."""
    import numpy as np
    import cv2
    from django.core.files.storage import default_storage
    try:
        f = default_storage.open(photo_name, "rb")
        data = f.read()
        f.close()
    except Exception:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def _recolor_rgb(arr, mask01, rgb):
    """Recolorea (in place) la zona (mask 0-1) al RGB dado, conservando la luminancia (V)."""
    import colorsys
    import numpy as np
    if not rgb:
        return
    th, ts, _ = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    lut = np.array([colorsys.hsv_to_rgb(th, ts, v / 255.0) for v in range(256)]) * 255
    v_idx = np.max(arr[:, :, :3], axis=2).astype(np.int32).clip(0, 255)
    tint = lut[v_idx]
    mm = mask01[..., None]
    arr[:, :, :3] = arr[:, :, :3] * (1 - mm) + tint * mm


def _recolor_hair(arr, mask01, hair_hex):
    """Recolorea el pelo (mask 0-1) al hex '#rrggbb'."""
    try:
        hc = str(hair_hex).lstrip("#")
        _recolor_rgb(arr, mask01, (int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)))
    except Exception:
        return


class Command(BaseCommand):
    help = "Genera el avatar por jugador: face-swap si tiene foto, si no sintético (piel/peinado/altura)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Todos los jugadores activos (con foto o por características).")
        parser.add_argument("--player", type=int, default=0, help="Solo este id de jugador.")
        parser.add_argument("--force", action="store_true", help="Regenerar aunque no cambien las entradas.")

    def handle(self, *args, **opts):
        import cv2
        import numpy as np
        from PIL import Image
        import insightface
        from insightface.app import FaceAnalysis

        base_path = _asset("library", "kit_home_hd.png")
        hair_mask_path = _asset("masks", "hair_home.png")
        if not base_path or not hair_mask_path:
            self.stderr.write("Falta la figura base o la máscara de pelo."); return
        # Ruta del modelo: env AVATAR_INSWAPPER, si no varias rutas conocidas (donde lo deja el
        # build en Render = BASE_DIR/vendor, o el venv local del Mac). Robusto aunque falte la env.
        _model_candidates = [
            os.environ.get("AVATAR_INSWAPPER") or "",
            os.path.join(str(settings.BASE_DIR), "vendor", "inswapper_128.onnx"),
            os.path.expanduser("~/ai-image-gen/inswapper_128.onnx"),
        ]
        model_path = next((p for p in _model_candidates if p and os.path.exists(p)), "")
        if not model_path:
            self.stderr.write(f"No encuentro inswapper_128.onnx (probado: {[p for p in _model_candidates if p]}). Define AVATAR_INSWAPPER."); return

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        swapper = insightface.model_zoo.get_model(model_path, download=False, providers=["CPUExecutionProvider"])

        base_rgba = np.asarray(Image.open(base_path).convert("RGBA"))
        base_alpha = base_rgba[:, :, 3]
        base_bgr = base_rgba[:, :, :3][:, :, ::-1].copy()
        base_faces = app.get(base_bgr)
        if not base_faces:
            self.stderr.write("No se detecta cara en la figura base."); return
        base_face = sorted(base_faces, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]
        kps = base_face.kps
        hair_mask = np.asarray(Image.open(hair_mask_path).convert("L")).astype(np.float32) / 255.0
        # Máscara de piel para el avatar SIN foto (recolor por grado de piel).
        _skin_mask_path = _asset("masks", "skin_home.png")
        skin_mask = (np.asarray(Image.open(_skin_mask_path).convert("L")).astype(np.float32) / 255.0) if _skin_mask_path else None

        # Figura base DEDICADA para el rapado (buzz generado nativo): el face-swap va sobre ella,
        # sin overlay ni recolor. El rapado no funciona como overlay (se pega al cráneo).
        rapado_path = _asset("library", "kit_rapado_hd.png")
        rapado_bgr = rapado_alpha = rapado_face = None
        if rapado_path:
            _r = np.asarray(Image.open(rapado_path).convert("RGBA"))
            rapado_alpha = _r[:, :, 3]
            rapado_bgr = _r[:, :, :3][:, :, ::-1].copy()
            _rf = app.get(rapado_bgr)
            if _rf:
                rapado_face = sorted(_rf, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]

        qs = Player.objects.filter(is_active=True)
        if opts["player"]:
            qs = Player.objects.filter(id=opts["player"])
        elif not opts["all"]:
            self.stderr.write("Indica --all o --player <id>."); return

        # Altura por PERCENTIL de la plantilla: el más bajo del equipo -> escala mínima, el más
        # alto -> máxima, anclando en p10-p90 para que un outlier no comprima al resto (la mediana
        # queda en ~1.0). Usa SIEMPRE la plantilla completa, no solo los que se regeneran ahora.
        # Nota: si cambia mucho la plantilla, relanza con --force para refrescar la escala de todos.
        HEIGHT_MIN_F, HEIGHT_MAX_F = 0.88, 1.12
        _sq = sorted(h for h in Player.objects.filter(is_active=True).values_list("height_cm", flat=True) if h)
        _h_lo = _sq[int(0.10 * (len(_sq) - 1))] if len(_sq) >= 3 else None
        _h_hi = _sq[int(0.90 * (len(_sq) - 1))] if len(_sq) >= 3 else None

        def _height_factor(h_cm):
            if not h_cm or _h_lo is None or _h_hi <= _h_lo:
                return 1.0
            t = max(0.0, min(1.0, (h_cm - _h_lo) / (_h_hi - _h_lo)))
            return HEIGHT_MIN_F + t * (HEIGHT_MAX_F - HEIGHT_MIN_F)

        if _h_lo is not None:
            self.stdout.write(f"Altura por percentil de plantilla: p10={_h_lo}cm p90={_h_hi}cm "
                              f"-> escala {HEIGHT_MIN_F}–{HEIGHT_MAX_F}")

        done = skipped = failed = 0
        for player in qs:
            # Porteros: la figura base es de campo -> no se les genera avatar de campo (usan su PNG GK).
            _pos = str(getattr(player, "position", "") or "").strip().lower()
            if _pos in {"por", "gk"} or "porter" in _pos or "goalkeep" in _pos:
                continue
            photo_name = _find_player_photo_name(player)
            has_photo = bool(photo_name)
            # Nada que personalizar y sin foto -> se deja la figura estática (resolver cae al PNG base).
            if not has_photo and not (
                player.skin_grade or player.hairstyle or player.hair_color or player.height_cm
            ):
                continue
            key = _inputs_key(player, photo_name)
            if key == player.avatar_source_key and player.avatar_generated and not opts["force"]:
                skipped += 1
                continue
            try:
                # ¿Hay cara utilizable en la foto? Si sí -> face-swap; si no -> sintético.
                sface = None
                if has_photo:
                    src = _read_photo_bgr(photo_name)
                    sfaces = app.get(src) if src is not None else []
                    if sfaces:
                        sface = sorted(sfaces, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]

                style = (player.hairstyle or "").strip().lower()
                use_rapado = style == "rapado" and rapado_face is not None
                b_bgr, b_alpha, b_face = (
                    (rapado_bgr, rapado_alpha, rapado_face) if use_rapado else (base_bgr, base_alpha, base_face)
                )

                if sface is not None:
                    # CON foto: face-swap de su cara real sobre la figura elegida.
                    res = swapper.get(b_bgr.copy(), b_face, sface, paste_back=True)
                    arr = np.dstack([res[:, :, ::-1], b_alpha]).astype(np.float32)
                else:
                    # SIN foto (o sin cara): sintético = figura base + grado de piel del jugador.
                    arr = np.dstack([b_bgr[:, :, ::-1], b_alpha]).astype(np.float32)
                    if not use_rapado and player.skin_grade and skin_mask is not None:
                        _recolor_rgb(arr, skin_mask, AVATAR_SKIN_GRADES.get(int(player.skin_grade)))

                if use_rapado:
                    style = ""  # rapado ya resuelto por la figura dedicada; sin overlay/recolor

                if style in STYLE_OVERLAYS:
                    # borrar pelo base (cuero cabelludo con su tono de frente) + overlay del peinado
                    ex, ey = int((kps[0][0] + kps[1][0]) / 2), int((kps[0][1] + kps[1][1]) / 2)
                    scalp = np.median(arr[ey - 34:ey - 14, ex - 16:ex + 16, :3].reshape(-1, 3), axis=0) * 0.9
                    mm = cv2.GaussianBlur((hair_mask * 255).astype(np.uint8), (9, 9), 0).astype(np.float32) / 255.0
                    arr[:, :, :3] = arr[:, :, :3] * (1 - mm[..., None]) + scalp * mm[..., None]
                    ov_path = _asset("hairstyles", STYLE_OVERLAYS[style])
                    ov = np.asarray(Image.open(ov_path).convert("RGBA")).astype(np.float32)
                    oa = (ov[:, :, 3:4] / 255.0)
                    if player.hair_color:
                        _recolor_hair(ov, ov[:, :, 3] / 255.0, player.hair_color)
                    arr[:, :, :3] = arr[:, :, :3] * (1 - oa) + ov[:, :, :3] * oa
                    arr[:, :, 3] = np.maximum(arr[:, :, 3], ov[:, :, 3])
                elif player.hair_color:
                    _recolor_hair(arr, hair_mask, player.hair_color)

                # altura: escala la figura (pies abajo) según el percentil de la plantilla.
                out = Image.fromarray(arr.astype("uint8"), "RGBA")
                f = _height_factor(getattr(player, "height_cm", None))
                if abs(f - 1.0) > 0.01:
                    W, H = out.size
                    sc = out.resize((max(1, int(W * f)), max(1, int(H * f))), Image.LANCZOS)
                    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    canvas.paste(sc, ((W - sc.width) // 2, H - sc.height), sc)
                    out = canvas

                buf = io.BytesIO(); out.save(buf, "PNG")
                player.avatar_generated.save(f"player-{player.id}.png", ContentFile(buf.getvalue()), save=False)
                player.avatar_source_key = key
                player.save(update_fields=["avatar_generated", "avatar_source_key"])
                done += 1
                _src = "foto" if sface is not None else "sintético"
                _st = "rapado" if use_rapado else (style or "base")
                self.stdout.write(f"✓ {player.id} {player.name} [{_src}·{_st}]")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"✗ {player.id} {player.name}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Generados {done} · saltados {skipped} · fallidos {failed}"))
