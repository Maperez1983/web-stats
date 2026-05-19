from __future__ import annotations

import io
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2  # type: ignore
import numpy as np  # type: ignore

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None
else:
    # Permite abrir HEIC/HEIF si `pillow-heif` está instalado.
    try:  # pragma: no cover
        from pillow_heif import register_heif_opener  # type: ignore

        register_heif_opener()
    except Exception:
        pass


@dataclass(frozen=True)
class Kit2DResult:
    club_png: bytes
    editor_png: bytes
    debug_mask_png: Optional[bytes] = None


# Silueta estándar (inspirada en kits 2D de Football Manager: 414x414 aprox).
# Se usa como máscara para proyectar la textura desde una foto.
JERSEY_PATH_DEF = (
    "M 86 47 "
    "L 50 97 "
    "L 23 163 "
    "L 66 195 "
    "L 110 193 "
    "L 99 389 "
    "L 148 406 "
    "L 264 406 "
    "L 308 395 "
    "L 315 371 "
    "L 303 192 "
    "L 341 197 "
    "L 390 163 "
    "L 383 135 "
    "L 342 60 "
    "L 246 10 "
    "L 167 10 "
    "Z"
)
JERSEY_COLLAR_DEF = "M 170 48 L 206 70 L 242 48 L 232 34 L 207 45 L 182 34 Z"


def _pil_open_image(data: bytes):
    if Image is None:
        raise RuntimeError("Pillow no disponible.")
    img = Image.open(io.BytesIO(data))
    if ImageOps is not None:
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
    return img.convert("RGB")


def _ffmpeg_decode_image(data: bytes):
    """
    Fallback para HEIC/HEIF problemáticos: intenta convertir con ffmpeg si está disponible.
    Devuelve PIL.Image RGB.
    """
    if Image is None:
        raise RuntimeError("Pillow no disponible.")
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "input.bin")
        dst = os.path.join(td, "out.png")
        with open(src, "wb") as f:
            f.write(data)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, dst],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Guardrail: si ffmpeg se cuelga (ficheros corruptos), no bloqueamos el worker.
                timeout=12,
            )
        except Exception as exc:
            raise RuntimeError("No se pudo decodificar la imagen (HEIC). Convierte a JPG/PNG e inténtalo de nuevo.") from exc
        img = Image.open(dst)
        if ImageOps is not None:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
        return img.convert("RGB")


def _decode_to_bgr(image_bytes: bytes) -> np.ndarray:
    # 1) Intento normal (Pillow con pillow-heif registrado en `football/views.py`).
    try:
        img = _pil_open_image(image_bytes)
    except Exception:
        # 2) Fallback: ffmpeg (si existe).
        img = _ffmpeg_decode_image(image_bytes)
    arr = np.array(img)  # RGB
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _grabcut_mask(bgr: np.ndarray) -> np.ndarray:
    """
    Segmentación best-effort con GrabCut.
    Devuelve máscara uint8 (0/255) del tamaño de la imagen original.
    """
    h0, w0 = bgr.shape[:2]
    # Downscale para rendimiento; mantenemos la relación.
    max_side = max(h0, w0)
    scale = 1.0
    if max_side > 1800:
        scale = 1800.0 / float(max_side)
    small = cv2.resize(bgr, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else bgr
    h, w = small.shape[:2]

    # Rectángulo inicial: excluye el borde superior (mesa/objetos) y el inferior (piernas/pies).
    rect = (int(w * 0.04), int(h * 0.12), int(w * 0.92), int(h * 0.83))
    mask = np.zeros((h, w), np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, rect, bgd_model, fgd_model, 6, cv2.GC_INIT_WITH_RECT)

    out = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)
    out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)

    if scale < 1.0:
        out = cv2.resize(out, (w0, h0), interpolation=cv2.INTER_LINEAR)
    return out


def _trim_bottom(mask_full: np.ndarray) -> np.ndarray:
    """
    Heurística para quitar piernas/pies cuando se cuelan:
    busca un 'cinturón' donde el ancho cae bruscamente en la parte baja.
    """
    contours, _ = cv2.findContours(mask_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return mask_full
    cont = max(contours, key=cv2.contourArea)
    pts = cont.reshape(-1, 2)
    ymin = int(pts[:, 1].min())
    ymax = int(pts[:, 1].max())
    if ymax <= ymin + 10:
        return mask_full

    spans = []
    for y in range(ymin, ymax + 1, 10):
        xs = pts[(pts[:, 1] >= y - 5) & (pts[:, 1] <= y + 5)][:, 0]
        if xs.size < 10:
            continue
        spans.append((y, int(xs.min()), int(xs.max()), int(xs.max() - xs.min())))
    if not spans:
        return mask_full

    maxw = max(s[3] for s in spans)
    cutoff = ymax
    for (y, _xmin, _xmax, ww) in spans:
        if y > ymin + (ymax - ymin) * 0.70 and ww < maxw * 0.72:
            cutoff = y
            break

    trimmed = mask_full.copy()
    trimmed[cutoff + 40 :, :] = 0
    return trimmed


def _mask_to_rgba_and_bbox(bgr: np.ndarray, mask_full: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Devuelve (bgra_crop, mask_crop) donde bgra_crop es uint8 HxWx4 (orden OpenCV: B,G,R,A).
    """
    contours, _ = cv2.findContours(mask_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No se pudo segmentar la camiseta en la imagen.")
    cont = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(cont)
    crop = bgr[y : y + bh, x : x + bw]
    alpha = mask_full[y : y + bh, x : x + bw]
    # Suaviza bordes para que el recorte quede menos "dentado".
    try:
        alpha = cv2.GaussianBlur(alpha, (0, 0), sigmaX=1.2, sigmaY=1.2)
    except Exception:
        pass
    bgra = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra, alpha


def _quantize_bgr(bgr: np.ndarray, mask: np.ndarray, k: int = 24) -> np.ndarray:
    """
    Reduce la paleta para que parezca más "kit 2D" (menos foto / menos sombras).
    `mask` es uint8 0..255, mismo tamaño que bgr.
    """
    h, w = bgr.shape[:2]
    if h <= 1 or w <= 1:
        return bgr
    k = int(k or 24)
    k = max(6, min(k, 48))
    flat = bgr.reshape((-1, 3)).astype(np.float32)
    m = (mask.reshape((-1,)) > 0)
    if int(m.sum()) < 200:
        return bgr
    # Muestreo para no hacer kmeans gigante.
    idx = np.where(m)[0]
    if idx.size > 35_000:
        idx = np.random.choice(idx, size=35_000, replace=False)
    samples = flat[idx]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 14, 1.0)
    _ret, _labels, centers = cv2.kmeans(samples, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    centers_u8 = np.clip(centers, 0, 255).astype(np.uint8)

    # Asigna cada pixel en máscara al centro más cercano.
    masked_pixels = flat[m]
    # Distancias cuadradas: (N, k)
    diffs = masked_pixels[:, None, :] - centers[None, :, :]
    d2 = np.sum(diffs * diffs, axis=2)
    nearest = np.argmin(d2, axis=1).astype(np.int32)
    out = bgr.copy().reshape((-1, 3))
    out[m] = centers_u8[nearest]
    return out.reshape((h, w, 3))


def _fm2d_stylize(bgra_crop: np.ndarray) -> np.ndarray:
    """
    Convierte el recorte en algo más parecido a un kit 2D (menos foto).
    Mantiene logos/diseño, pero aplana iluminación y reduce ruido.
    """
    if bgra_crop.shape[2] != 4:
        return bgra_crop
    bgr = bgra_crop[:, :, :3]
    alpha = bgra_crop[:, :, 3]
    mask = (alpha > 0).astype(np.uint8) * 255

    # 1) Aplana iluminación (quita sombras/faldones) para que no parezca una foto.
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    illum = cv2.GaussianBlur(gray, (0, 0), sigmaX=55, sigmaY=55)
    illum = np.clip(illum.astype(np.float32), 1.0, 255.0)
    base = bgr.astype(np.float32)
    # Ratio hacia la media del objeto.
    mean_illum = float(np.mean(illum[mask > 0])) if int(np.sum(mask > 0)) else 128.0
    scale = (mean_illum / illum)
    scale = np.clip(scale, 0.80, 1.25)
    base[:, :, 0] *= scale
    base[:, :, 1] *= scale
    base[:, :, 2] *= scale
    base = np.clip(base, 0, 255).astype(np.uint8)

    # 2) Suavizado preservando bordes.
    try:
        base = cv2.bilateralFilter(base, d=9, sigmaColor=85, sigmaSpace=85)
        base = cv2.bilateralFilter(base, d=7, sigmaColor=65, sigmaSpace=65)
    except Exception:
        pass

    # 3) Reduce paleta (parece "kit 2D", menos textura de tela).
    try:
        base = _quantize_bgr(base, mask, k=14)
    except Exception:
        pass

    # 4) Realce leve (evita aspecto "lavado").
    try:
        hsv = cv2.cvtColor(base, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.10, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.04, 0, 255)
        base = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    except Exception:
        pass

    # 5) Contorno: borde exterior + líneas internas suaves (para que a 44px siga legible).
    try:
        # Borde exterior (stroke).
        border = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8))
        border_mask = (border > 0)[:, :, None].astype(np.float32)
        # oscurece el borde (tipo FM).
        base = (base.astype(np.float32) * (1.0 - 0.45 * border_mask)).astype(np.uint8)

        edge = cv2.Canny(cv2.cvtColor(base, cv2.COLOR_BGR2GRAY), 70, 150)
        edge = cv2.dilate(edge, np.ones((2, 2), np.uint8), iterations=1)
        edge = cv2.bitwise_and(edge, mask)
        # negro con baja opacidad (mezcla).
        edge_mask = (edge > 0).astype(np.float32)[:, :, None]
        base = (base.astype(np.float32) * (1.0 - 0.20 * edge_mask)).astype(np.uint8)
    except Exception:
        pass

    out = np.zeros_like(bgra_crop)
    out[:, :, :3] = base
    out[:, :, 3] = alpha
    return out


def _apply_fm_finish(bgra: np.ndarray) -> np.ndarray:
    """
    Acabado tipo FM 2D: sombra suave + contorno negro marcado.
    """
    if bgra is None or bgra.size == 0 or bgra.shape[2] != 4:
        return bgra
    out = bgra.copy()
    alpha = out[:, :, 3]
    mask = (alpha > 0).astype(np.uint8) * 255
    if int(np.sum(mask > 0)) < 50:
        return out

    h, w = alpha.shape[:2]
    # Sombra (drop shadow) hacia abajo: muy sutil para que destaque sobre césped.
    try:
        sigma = max(1.0, min(4.5, (max(h, w) / 260.0)))
        shadow = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma * 1.25, sigmaY=sigma * 1.25)
        # desplazamiento
        dx = int(round(max(1, w * 0.006)))
        dy = int(round(max(1, h * 0.010)))
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shadow = cv2.warpAffine(shadow, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
        shadow = cv2.bitwise_and(shadow, cv2.bitwise_not(mask))
        strength = 0.33
        out[:, :, 0] = np.clip(out[:, :, 0].astype(np.float32) * (1.0 - strength * (shadow.astype(np.float32) / 255.0)), 0, 255).astype(np.uint8)
        out[:, :, 1] = np.clip(out[:, :, 1].astype(np.float32) * (1.0 - strength * (shadow.astype(np.float32) / 255.0)), 0, 255).astype(np.uint8)
        out[:, :, 2] = np.clip(out[:, :, 2].astype(np.float32) * (1.0 - strength * (shadow.astype(np.float32) / 255.0)), 0, 255).astype(np.uint8)
        out[:, :, 3] = np.maximum(out[:, :, 3], (shadow.astype(np.float32) * 0.55).astype(np.uint8))
    except Exception:
        pass

    # Contorno negro: borde exterior con alpha alto.
    try:
        k = max(2, int(round(max(h, w) / 180)))
        kernel = np.ones((k, k), np.uint8)
        dil = cv2.dilate(mask, kernel, iterations=1)
        ero = cv2.erode(mask, kernel, iterations=1)
        border = cv2.subtract(dil, ero)
        if int(np.sum(border > 0)) > 10:
            border_a = np.clip(border.astype(np.float32) * 1.15, 0, 255).astype(np.uint8)
            # compone negro solo donde hay borde (sin matar el interior).
            bmask = border_a > 0
            out[bmask, 0] = 0
            out[bmask, 1] = 0
            out[bmask, 2] = 0
            out[bmask, 3] = np.maximum(out[bmask, 3], border_a[bmask])
    except Exception:
        pass

    return out


def _extract_logo_patches(*, bgr_crop: np.ndarray, alpha: np.ndarray) -> dict:
    """
    Extrae parches (best-effort) de escudo/marca/sponsor desde la foto.
    Devuelve dict con keys: crest, brand, sponsor -> (patch_bgr, patch_alpha) en coords del crop.
    """
    h, w = bgr_crop.shape[:2]
    if h < 40 or w < 40:
        return {}
    mask = (alpha > 25).astype(np.uint8) * 255
    if int(np.sum(mask > 0)) < 800:
        return {}

    # Buscamos regiones con "detalle": bordes fuertes.
    gray = cv2.cvtColor(bgr_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (0, 0), 1.0)
    edges = cv2.Canny(gray, 60, 160)
    edges = cv2.bitwise_and(edges, mask)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {}

    candidates = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area < (h * w) * 0.002:
            continue
        if area > (h * w) * 0.25:
            continue
        ar = bw / float(max(1, bh))
        # descarta bandas muy largas (rayas).
        if ar > 6.0 or ar < 0.12:
            continue
        # requiere algo de bordes
        roi_e = edges[y : y + bh, x : x + bw]
        if int(np.sum(roi_e > 0)) < 120:
            continue
        cx = (x + bw / 2.0) / float(w)
        cy = (y + bh / 2.0) / float(h)
        candidates.append((x, y, bw, bh, area, ar, cx, cy))

    if not candidates:
        return {}

    # Scoring heurístico.
    def score_crest(item):
        _x, _y, bw, bh, area, _ar, cx, cy = item
        # zona pecho derecho (en tu ejemplo el escudo está a la derecha del observador)
        pos = 1.0 - min(1.0, abs(cx - 0.70) + abs(cy - 0.28))
        squarish = 1.0 - min(1.0, abs((bw / float(max(1, bh))) - 1.0))
        return (pos * 2.2) + (squarish * 1.0) + min(1.0, area / ((h * w) * 0.030))

    def score_brand(item):
        _x, _y, bw, bh, area, _ar, cx, cy = item
        pos = 1.0 - min(1.0, abs(cx - 0.30) + abs(cy - 0.28))
        return (pos * 2.0) + min(1.0, area / ((h * w) * 0.020))

    def score_sponsor(item):
        _x, _y, bw, bh, area, ar, cx, cy = item
        pos = 1.0 - min(1.0, abs(cx - 0.50) + abs(cy - 0.52))
        wide = min(1.0, max(0.0, (ar - 1.1) / 2.6))
        return (pos * 2.0) + (wide * 1.3) + min(1.0, area / ((h * w) * 0.10))

    def pick_best(score_fn):
        best = None
        best_s = -1e9
        for item in candidates:
            s = score_fn(item)
            if s > best_s:
                best_s = s
                best = item
        return best

    out = {}
    for key, fn in (("crest", score_crest), ("brand", score_brand), ("sponsor", score_sponsor)):
        item = pick_best(fn)
        if not item:
            continue
        x, y, bw, bh, *_rest = item
        pad = int(max(2, round(min(bw, bh) * 0.12)))
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + bw + pad)
        y1 = min(h, y + bh + pad)
        patch = bgr_crop[y0:y1, x0:x1].copy()
        patch_a = alpha[y0:y1, x0:x1].copy()
        # endurece alpha dentro de la camiseta
        patch_a = np.where(patch_a > 25, 255, 0).astype(np.uint8)
        out[key] = (patch, patch_a)
    return out


def _overlay_patch(
    base_bgra: np.ndarray,
    patch_bgr: np.ndarray,
    patch_alpha: np.ndarray,
    *,
    cx: float,
    cy: float,
    target_w_ratio: float,
) -> np.ndarray:
    """
    Overlay alfa (sin blending raro). Coords normales 0..1.
    """
    h, w = base_bgra.shape[:2]
    if patch_bgr is None or patch_bgr.size == 0:
        return base_bgra
    tw = int(round(w * float(target_w_ratio)))
    if tw < 8:
        return base_bgra
    ph, pw = patch_bgr.shape[:2]
    scale = tw / float(max(1, pw))
    th = max(1, int(round(ph * scale)))
    patch_bgr_r = cv2.resize(patch_bgr, (tw, th), interpolation=cv2.INTER_AREA)
    patch_a_r = cv2.resize(patch_alpha, (tw, th), interpolation=cv2.INTER_AREA)
    x0 = int(round((w * cx) - tw / 2.0))
    y0 = int(round((h * cy) - th / 2.0))
    x1 = x0 + tw
    y1 = y0 + th
    # clip
    bx0 = max(0, x0)
    by0 = max(0, y0)
    bx1 = min(w, x1)
    by1 = min(h, y1)
    if bx1 <= bx0 or by1 <= by0:
        return base_bgra
    px0 = bx0 - x0
    py0 = by0 - y0
    px1 = px0 + (bx1 - bx0)
    py1 = py0 + (by1 - by0)
    roi = base_bgra[by0:by1, bx0:bx1]
    pb = patch_bgr_r[py0:py1, px0:px1]
    pa = patch_a_r[py0:py1, px0:px1].astype(np.float32) / 255.0
    pa = pa[:, :, None]
    # alpha blend sobre base (solo color, alpha se mantiene como max)
    roi[:, :, 0:3] = np.clip((roi[:, :, 0:3].astype(np.float32) * (1.0 - pa)) + (pb.astype(np.float32) * pa), 0, 255).astype(np.uint8)
    roi[:, :, 3] = np.maximum(roi[:, :, 3], (pa[:, :, 0] * 255).astype(np.uint8))
    base_bgra[by0:by1, bx0:bx1] = roi
    return base_bgra


def _fit_square_rgba(rgba: np.ndarray, size: int = 1024, pad_ratio: float = 0.86) -> np.ndarray:
    # Nota: aunque el nombre diga RGBA, internamente trabajamos en BGRA para mantener consistencia con OpenCV.
    ch, cw = rgba.shape[:2]
    if ch <= 0 or cw <= 0:
        raise RuntimeError("Imagen vacía tras segmentación.")
    scale = min((size * pad_ratio) / float(cw), (size * pad_ratio) / float(ch))
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    resized = cv2.resize(rgba, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    offx = (size - new_w) // 2
    offy = (size - new_h) // 2
    canvas[offy : offy + new_h, offx : offx + new_w] = resized
    return canvas


def _tighten_alpha_padding(bgra: np.ndarray, *, pad_ratio: float = 0.95) -> np.ndarray:
    """
    Recorta bordes transparentes y vuelve a encajar en cuadrado (para que en 44px se vea más grande).
    """
    if bgra is None or bgra.size == 0 or bgra.shape[2] != 4:
        return bgra
    alpha = bgra[:, :, 3]
    try:
        ys, xs = np.where(alpha > 6)
        if ys.size < 10 or xs.size < 10:
            return bgra
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        crop = bgra[y0 : y1 + 1, x0 : x1 + 1]
        return _fit_square_rgba(crop, size=bgra.shape[0], pad_ratio=float(pad_ratio))
    except Exception:
        return bgra


def _encode_png(img_rgba: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img_rgba)
    if not ok:
        raise RuntimeError("No se pudo codificar PNG.")
    return bytes(buf.tobytes())


def _cubic_bezier(p0, p1, p2, p3, t: float):
    u = 1.0 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t
    x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    return (x, y)


def _svg_path_to_points(path_d: str, sample_per_curve: int = 26):
    """
    Parser mínimo para paths con M/L/C/Z (como nuestros defs).
    Devuelve lista de puntos (x,y) en coordenadas del path.
    """
    # Tokeniza letras y floats.
    tokens = []
    buf = ""
    for ch in str(path_d or ""):
        if ch.isalpha():
            if buf.strip():
                tokens.extend(buf.strip().split())
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf.strip():
        tokens.extend(buf.strip().split())

    def _next_float(i):
        return float(tokens[i]), i + 1

    pts = []
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = None
    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, str) and tok and tok[0].isalpha() and len(tok) == 1:
            cmd = tok
            i += 1
            if cmd in {"Z", "z"}:
                if start is not None:
                    pts.append(start)
                cur = start or cur
                continue
        if cmd in {"M", "m"}:
            x, i = _next_float(i)
            y, i = _next_float(i)
            cur = (x, y) if cmd == "M" else (cur[0] + x, cur[1] + y)
            start = cur
            pts.append(cur)
            cmd = "L" if cmd == "M" else "l"
        elif cmd in {"L", "l"}:
            x, i = _next_float(i)
            y, i = _next_float(i)
            cur = (x, y) if cmd == "L" else (cur[0] + x, cur[1] + y)
            pts.append(cur)
        elif cmd in {"C", "c"}:
            x1, i = _next_float(i)
            y1, i = _next_float(i)
            x2, i = _next_float(i)
            y2, i = _next_float(i)
            x3, i = _next_float(i)
            y3, i = _next_float(i)
            if cmd == "c":
                p1 = (cur[0] + x1, cur[1] + y1)
                p2 = (cur[0] + x2, cur[1] + y2)
                p3 = (cur[0] + x3, cur[1] + y3)
            else:
                p1 = (x1, y1)
                p2 = (x2, y2)
                p3 = (x3, y3)
            p0 = cur
            # Muestrea la curva (evita puntos duplicados al inicio).
            for s in range(1, max(6, int(sample_per_curve)) + 1):
                t = s / float(max(6, int(sample_per_curve)))
                pts.append(_cubic_bezier(p0, p1, p2, p3, t))
            cur = p3
        else:
            # Comando no soportado.
            break
    # Limpia duplicados secuenciales
    cleaned = []
    last = None
    for p in pts:
        q = (float(p[0]), float(p[1]))
        if last is None or (abs(q[0] - last[0]) + abs(q[1] - last[1])) > 1e-6:
            cleaned.append(q)
            last = q
    return cleaned


def _render_fm_template(
    *,
    size: int,
    style: str,
    base_bgr: tuple,
    stripe_bgr: tuple,
) -> np.ndarray:
    """
    Renderiza una camiseta "FM-like" (plantilla estándar) en RGBA.
    style: solid|striped
    """
    sz = int(size or 1024)
    sz = max(128, min(sz, 2048))
    canvas = np.zeros((sz, sz, 4), dtype=np.uint8)

    pts = _svg_path_to_points(JERSEY_PATH_DEF, sample_per_curve=28)
    if not pts:
        return canvas
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    # padding interno
    pad = int(sz * 0.10)
    sx = (sz - 2 * pad) / max(1e-6, (maxx - minx))
    sy = (sz - 2 * pad) / max(1e-6, (maxy - miny))
    scale = min(sx, sy)
    ox = (sz - (maxx - minx) * scale) / 2.0
    oy = (sz - (maxy - miny) * scale) / 2.0
    poly = np.array(
        [[int(round(ox + (x - minx) * scale)), int(round(oy + (y - miny) * scale))] for (x, y) in pts],
        dtype=np.int32,
    )
    mask = np.zeros((sz, sz), dtype=np.uint8)
    cv2.fillPoly(mask, [poly], 255)

    # Fondo camiseta
    if style == "striped":
        stripe_w = max(6, int(sz * 0.09))
        # alterna stripes verticales centradas
        x = 0
        toggle = True
        while x < sz:
            color = stripe_bgr if toggle else base_bgr
            cv2.rectangle(canvas, (x, 0), (x + stripe_w, sz), (*color, 255), thickness=-1)
            toggle = not toggle
            x += stripe_w
    elif style == "half":
        mid = sz // 2
        cv2.rectangle(canvas, (0, 0), (mid, sz), (*stripe_bgr, 255), thickness=-1)
        cv2.rectangle(canvas, (mid, 0), (sz, sz), (*base_bgr, 255), thickness=-1)
    elif style == "sash":
        # base primero
        canvas[:, :, 0] = base_bgr[0]
        canvas[:, :, 1] = base_bgr[1]
        canvas[:, :, 2] = base_bgr[2]
        canvas[:, :, 3] = 255
        # banda diagonal (izq arriba -> dcha abajo)
        band = np.zeros((sz, sz), np.uint8)
        thickness = max(18, int(sz * 0.11))
        cv2.line(band, (int(sz * 0.20), int(sz * 0.10)), (int(sz * 0.88), int(sz * 0.92)), 255, thickness=thickness)
        for c in range(3):
            canvas[:, :, c] = np.where(band > 0, stripe_bgr[c], canvas[:, :, c])
    else:
        canvas[:, :, 0] = base_bgr[0]
        canvas[:, :, 1] = base_bgr[1]
        canvas[:, :, 2] = base_bgr[2]
        canvas[:, :, 3] = 255

    # Aplica máscara de camiseta
    canvas[:, :, 3] = cv2.bitwise_and(canvas[:, :, 3], mask)

    # Contorno suave
    try:
        edge = cv2.Canny(mask, 40, 120)
        edge = cv2.dilate(edge, np.ones((2, 2), np.uint8), iterations=1)
        for c in range(3):
            canvas[:, :, c] = np.where(edge > 0, (canvas[:, :, c].astype(np.float32) * 0.55).astype(np.uint8), canvas[:, :, c])
    except Exception:
        pass
    return canvas


def _warp_cutout_to_jersey_template(*, bgra_crop: np.ndarray, alpha: np.ndarray, size: int = 1024) -> np.ndarray:
    """
    Proyecta la textura (foto recortada) a una silueta estándar de camiseta.
    Resultado: BGRA cuadrado `size` con fondo transparente.
    """
    sz = int(size or 1024)
    sz = max(128, min(sz, 2048))
    if bgra_crop is None or bgra_crop.size == 0:
        return np.zeros((sz, sz, 4), dtype=np.uint8)

    # 1) recorta al bbox real del alpha para minimizar bleeding.
    try:
        ys, xs = np.where(alpha > 32)
        if ys.size > 0 and xs.size > 0:
            y0, y1 = int(ys.min()), int(ys.max())
            x0, x1 = int(xs.min()), int(xs.max())
            bgra_crop = bgra_crop[y0 : y1 + 1, x0 : x1 + 1]
            alpha = bgra_crop[:, :, 3]
    except Exception:
        alpha = bgra_crop[:, :, 3]

    h, w = bgra_crop.shape[:2]
    if h < 4 or w < 4:
        return np.zeros((sz, sz, 4), dtype=np.uint8)

    # 2) target bbox del path en canvas cuadrado.
    pts = _svg_path_to_points(JERSEY_PATH_DEF, sample_per_curve=28)
    if not pts:
        return np.zeros((sz, sz, 4), dtype=np.uint8)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    # En kits 2D (FM) la camiseta suele ocupar mucho más área del cuadrado.
    pad = int(sz * 0.055)
    sx = (sz - 2 * pad) / max(1e-6, (maxx - minx))
    sy = (sz - 2 * pad) / max(1e-6, (maxy - miny))
    scale = min(sx, sy)
    ox = (sz - (maxx - minx) * scale) / 2.0
    oy = (sz - (maxy - miny) * scale) / 2.0
    tgt = np.array(
        [
            [ox, oy],
            [ox + (maxx - minx) * scale, oy],
            [ox + (maxx - minx) * scale, oy + (maxy - miny) * scale],
            [ox, oy + (maxy - miny) * scale],
        ],
        dtype=np.float32,
    )
    src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, tgt)

    # 3) premultiply para evitar que el fondo de la foto "sangre" por interpolación.
    rgb = bgra_crop[:, :, :3].astype(np.float32)
    a = (alpha.astype(np.float32) / 255.0)[:, :, None]
    premul = np.clip(rgb * a, 0, 255).astype(np.uint8)

    warped_p = cv2.warpPerspective(
        premul,
        M,
        (sz, sz),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    warped_a = cv2.warpPerspective(
        alpha,
        M,
        (sz, sz),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    # 4) silueta final (clip).
    poly = np.array([[int(round(ox + (x - minx) * scale)), int(round(oy + (y - miny) * scale))] for (x, y) in pts], dtype=np.int32)
    jersey_mask = np.zeros((sz, sz), dtype=np.uint8)
    cv2.fillPoly(jersey_mask, [poly], 255)
    warped_a = cv2.bitwise_and(warped_a, jersey_mask)

    # 5) unpremultiply
    out = np.zeros((sz, sz, 4), dtype=np.uint8)
    out[:, :, 3] = warped_a
    wa = (warped_a.astype(np.float32) / 255.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        for c in range(3):
            ch = warped_p[:, :, c].astype(np.float32)
            out[:, :, c] = np.where(wa > 1e-3, np.clip(ch / wa, 0, 255), 0).astype(np.uint8)

    # 6) suaviza borde un poco y aplica contorno suave.
    try:
        out[:, :, 3] = cv2.GaussianBlur(out[:, :, 3], (0, 0), 0.8)
    except Exception:
        pass
    try:
        edge = cv2.Canny(out[:, :, 3], 40, 120)
        edge = cv2.dilate(edge, np.ones((2, 2), np.uint8), iterations=1)
        for c in range(3):
            out[:, :, c] = np.where(edge > 0, (out[:, :, c].astype(np.float32) * 0.60).astype(np.uint8), out[:, :, c])
    except Exception:
        pass
    return out


def _infer_template_colors(bgr_crop: np.ndarray, alpha: np.ndarray) -> tuple:
    """
    Best-effort para sacar 2 colores (base, stripe) desde la camiseta.
    Devuelve (style, base_bgr, stripe_bgr).
    """
    h, w = bgr_crop.shape[:2]
    if h < 8 or w < 8:
        return ("solid", (248, 250, 252), (15, 122, 53))
    m = (alpha > 0)
    if int(m.sum()) < 200:
        return ("solid", (248, 250, 252), (15, 122, 53))
    # ROI central para evitar mangas/fondo.
    y0, y1 = int(h * 0.22), int(h * 0.78)
    x0, x1 = int(w * 0.22), int(w * 0.78)
    roi = bgr_crop[y0:y1, x0:x1]
    roi_m = m[y0:y1, x0:x1]
    pix = roi[roi_m]
    if pix.size < 500:
        pix = bgr_crop[m]
    pix = pix.reshape((-1, 3)).astype(np.float32)
    # kmeans 4: ayuda a separar números/sponsor (negro) de los colores del diseño.
    k = 4
    if pix.shape[0] > 50_000:
        idx = np.random.choice(pix.shape[0], size=50_000, replace=False)
        pix = pix[idx]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 16, 1.0)
    _ret, labels, centers = cv2.kmeans(pix, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k).astype(np.int64)
    order = np.argsort(-counts)
    centers_u8 = np.clip(centers, 0, 255).astype(np.uint8)
    # Calcula "saturación" para elegir color de raya (evita negro/blanco del dorsal/sponsor).
    hsv = cv2.cvtColor(centers_u8.reshape((-1, 1, 3)), cv2.COLOR_BGR2HSV).reshape((-1, 3))
    sat = hsv[:, 1].astype(np.float32)
    val = hsv[:, 2].astype(np.float32)

    # Base: el color más frecuente que no sea demasiado oscuro.
    base_idx = None
    for idx in order.tolist():
        if val[idx] < 35:
            continue
        base_idx = int(idx)
        break
    if base_idx is None:
        base_idx = int(order[0])

    # Stripe: el color con mayor saturación y presencia mínima (evita ruido).
    stripe_idx = None
    min_count = max(120, int(0.01 * pix.shape[0]))
    candidates = []
    for idx in range(k):
        if int(counts[idx]) < min_count:
            continue
        # descarta casi blanco/negro
        if val[idx] < 40 or val[idx] > 245:
            continue
        candidates.append(idx)
    if candidates:
        stripe_idx = int(max(candidates, key=lambda i: float(sat[i])))
    else:
        # fallback: segundo más frecuente distinto del base
        for idx in order.tolist():
            if int(idx) != int(base_idx):
                stripe_idx = int(idx)
                break
    if stripe_idx is None:
        stripe_idx = int(base_idx)

    base = tuple(int(x) for x in centers_u8[base_idx].tolist())
    stripe = tuple(int(x) for x in centers_u8[stripe_idx].tolist())

    # Detecta "rayas" por variación en columnas (gris).
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    col = gray.mean(axis=0)
    diff = np.abs(np.diff(col))
    stripey = float(np.mean(diff)) > 0.9 and float(np.std(col)) > 14.0
    style = "striped" if stripey else "solid"

    # Ajuste heurístico: si los dos colores son muy parecidos, forzamos solid.
    dist = float(np.linalg.norm(np.array(base, dtype=np.float32) - np.array(stripe, dtype=np.float32)))
    if dist < 18.0:
        style = "solid"
    return (style, base, stripe)


def generate_kit2d_tokens(
    *,
    image_bytes: bytes,
    club_size: int = 96,
    editor_size: int = 44,
    include_debug: bool = False,
    mode: str = "warp",
    pattern: str = "",
    base_color: str = "",
    stripe_color: str = "",
    logo_preset: str = "",
) -> Kit2DResult:
    if not image_bytes:
        raise RuntimeError("Imagen vacía.")
    club_size = int(club_size or 96)
    editor_size = int(editor_size or 44)
    club_size = max(32, min(club_size, 512))
    editor_size = max(24, min(editor_size, 256))

    bgr = _decode_to_bgr(image_bytes)
    mask = _grabcut_mask(bgr)
    mask = _trim_bottom(mask)

    rgba_crop, alpha_crop = _mask_to_rgba_and_bbox(bgr, mask)
    mode = str(mode or "warp").strip().lower()
    pattern = str(pattern or "").strip().lower()
    base_color = str(base_color or "").strip()
    stripe_color = str(stripe_color or "").strip()
    logo_preset = str(logo_preset or "").strip().lower()
    if mode == "cutout":
        rgba_crop = _fm2d_stylize(rgba_crop)
        master = _fit_square_rgba(rgba_crop, size=1024, pad_ratio=0.86)
    elif mode == "warp":
        # “Kit 2D” realista: conserva diseño/logos, pero con formato/silueta estándar tipo FM.
        master = _warp_cutout_to_jersey_template(bgra_crop=rgba_crop, alpha=alpha_crop, size=1024)
        master = _fm2d_stylize(master)
    else:
        # Plantilla FM sin "foto": colores/patrón configurables.
        style, base_bgr, stripe_bgr = _infer_template_colors(bgr_crop=rgba_crop[:, :, :3], alpha=alpha_crop)
        if base_color.startswith("#") and len(base_color) in {4, 7}:
            try:
                hexv = base_color.lstrip("#")
                if len(hexv) == 3:
                    hexv = "".join([c + c for c in hexv])
                r = int(hexv[0:2], 16)
                g = int(hexv[2:4], 16)
                b = int(hexv[4:6], 16)
                base_bgr = (b, g, r)
            except Exception:
                pass
        if stripe_color.startswith("#") and len(stripe_color) in {4, 7}:
            try:
                hexv = stripe_color.lstrip("#")
                if len(hexv) == 3:
                    hexv = "".join([c + c for c in hexv])
                r = int(hexv[0:2], 16)
                g = int(hexv[2:4], 16)
                b = int(hexv[4:6], 16)
                stripe_bgr = (b, g, r)
            except Exception:
                pass
        style = pattern or style or "striped"
        if style not in {"striped", "solid", "half", "sash"}:
            style = "striped"
        master = _render_fm_template(size=1024, style=style, base_bgr=base_bgr, stripe_bgr=stripe_bgr)
        # Logos: o bien desde assets (logo_preset) o best-effort desde la propia foto.
        def _load_logo_asset(rel_path: str):
            try:
                base_dir = os.path.dirname(__file__)
                abs_path = os.path.join(base_dir, "static", "football", "images", "kit_logos", rel_path)
                img = cv2.imread(abs_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    return None
                if img.shape[2] == 4:
                    return (img[:, :, :3], img[:, :, 3])
                return (img[:, :, :3], np.full((img.shape[0], img.shape[1]), 255, np.uint8))
            except Exception:
                return None

        logos = {}
        if logo_preset in {"benagalbon", "cd_benagalbon", "benagalbón"}:
            crest = _load_logo_asset("benagalbon_crest_alpha.png")
            brand = _load_logo_asset("nike_swoosh.png")
            sponsor = _load_logo_asset("grupo_modernia_black.png")
            if crest:
                logos["crest"] = crest
            if brand:
                logos["brand"] = brand
            if sponsor:
                logos["sponsor"] = sponsor
        else:
            try:
                extracted = _extract_logo_patches(bgr_crop=rgba_crop[:, :, :3], alpha=alpha_crop)
                for k, (pb, pa) in extracted.items():
                    logos[k] = (pb, pa)
            except Exception:
                logos = {}

        # Posiciones aproximadas en el kit FM.
        try:
            if "crest" in logos:
                master = _overlay_patch(master, logos["crest"][0], logos["crest"][1], cx=0.66, cy=0.29, target_w_ratio=0.14)
            if "brand" in logos:
                master = _overlay_patch(master, logos["brand"][0], logos["brand"][1], cx=0.34, cy=0.29, target_w_ratio=0.12)
            if "sponsor" in logos:
                master = _overlay_patch(master, logos["sponsor"][0], logos["sponsor"][1], cx=0.50, cy=0.53, target_w_ratio=0.36)
        except Exception:
            pass

    # Asegura que la camiseta ocupe el máximo posible del cuadrado (mejor legibilidad en 44px).
    try:
        master = _tighten_alpha_padding(master, pad_ratio=0.965 if mode == "warp" else 0.94)
    except Exception:
        pass
    try:
        master = _apply_fm_finish(master)
    except Exception:
        pass

    club_img = cv2.resize(master, (club_size, club_size), interpolation=cv2.INTER_AREA)
    editor_img = cv2.resize(master, (editor_size, editor_size), interpolation=cv2.INTER_AREA)

    debug_mask_png = _encode_png(mask) if include_debug else None
    return Kit2DResult(
        club_png=_encode_png(club_img),
        editor_png=_encode_png(editor_img),
        debug_mask_png=debug_mask_png,
    )
