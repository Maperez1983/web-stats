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


def _inputs_key(player, photo_path):
    h = hashlib.sha1()
    try:
        st = os.stat(photo_path)
        h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
    except OSError:
        h.update(b"nophoto")
    for v in (player.hairstyle, player.hair_color, player.skin_grade, player.height_cm):
        h.update(f"|{v}".encode())
    return h.hexdigest()


def _recolor_hair(arr, mask01, hair_hex):
    """Recolorea (in place) la zona de pelo (mask 0-1) al hex dado, conservando la luminancia."""
    import colorsys
    import numpy as np
    try:
        hc = hair_hex.lstrip("#")
        rgb = (int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16))
    except Exception:
        return
    th, ts, _ = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    lut = np.array([colorsys.hsv_to_rgb(th, ts, v / 255.0) for v in range(256)]) * 255
    v_idx = np.max(arr[:, :, :3], axis=2).astype(np.int32).clip(0, 255)
    tint = lut[v_idx]
    mm = mask01[..., None]
    arr[:, :, :3] = arr[:, :, :3] * (1 - mm) + tint * mm


class Command(BaseCommand):
    help = "Genera el avatar (face-swap) de los jugadores con foto."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Todos los jugadores activos con foto.")
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
        model_path = os.environ.get("AVATAR_INSWAPPER") or os.path.expanduser("~/ai-image-gen/inswapper_128.onnx")
        if not os.path.exists(model_path):
            self.stderr.write(f"No está inswapper_128.onnx en {model_path} (AVATAR_INSWAPPER)."); return

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

        done = skipped = failed = 0
        for player in qs:
            photo = getattr(player, "photo", None)
            photo_path = getattr(photo, "path", None) if photo else None
            if not photo_path or not os.path.exists(photo_path):
                continue
            key = _inputs_key(player, photo_path)
            if key == player.avatar_source_key and player.avatar_generated and not opts["force"]:
                skipped += 1
                continue
            try:
                src = cv2.imread(photo_path)
                sfaces = app.get(src)
                if not sfaces:
                    self.stdout.write(f"· {player.id} {player.name}: sin cara en la foto, saltado")
                    failed += 1
                    continue
                sface = sorted(sfaces, key=lambda f: (f.bbox[2] - f.bbox[0]))[-1]
                style = (player.hairstyle or "").strip().lower()

                if style == "rapado" and rapado_face is not None:
                    # face-swap sobre la figura rapada dedicada; sin overlay ni recolor.
                    res = swapper.get(rapado_bgr.copy(), rapado_face, sface, paste_back=True)
                    arr = np.dstack([res[:, :, ::-1], rapado_alpha]).astype(np.float32)
                    style = ""  # ya resuelto: evita el bloque de overlays/recolor de abajo
                else:
                    res = swapper.get(base_bgr.copy(), base_face, sface, paste_back=True)
                    arr = np.dstack([res[:, :, ::-1], base_alpha]).astype(np.float32)  # RGBA

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

                # altura: escala suave de la figura (pies abajo) según height_cm
                out = Image.fromarray(arr.astype("uint8"), "RGBA")
                h_cm = getattr(player, "height_cm", None) or 0
                if h_cm:
                    f = max(0.9, min(1.08, h_cm / 178.0))
                    if abs(f - 1.0) > 0.01:
                        W, H = out.size
                        sc = out.resize((int(W * f), int(H * f)), Image.LANCZOS)
                        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                        canvas.paste(sc, ((W - sc.width) // 2, H - sc.height), sc)
                        out = canvas

                buf = io.BytesIO(); out.save(buf, "PNG")
                player.avatar_generated.save(f"player-{player.id}.png", ContentFile(buf.getvalue()), save=False)
                player.avatar_source_key = key
                player.save(update_fields=["avatar_generated", "avatar_source_key"])
                done += 1
                self.stdout.write(f"✓ {player.id} {player.name} [{style or 'base'}]")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"✗ {player.id} {player.name}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Generados {done} · saltados {skipped} · fallidos {failed}"))
