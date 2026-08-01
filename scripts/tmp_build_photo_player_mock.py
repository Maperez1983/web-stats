from __future__ import annotations

from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
REF = Path("/Volumes/Mac Satecchi/.TemporaryItems/folders.501/TemporaryItems/NSIRD_screencaptureui_OBXxdD/Captura de pantalla 2026-07-02 a las 17.02.44.png")
OUT = Path("/Volumes/Mac Satecchi/Mac/Downloads/muestra_jugador_fotobase_v1.png")


def make_pitch(size=(1600, 900)) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (31, 45, 62, 255))
    draw = ImageDraw.Draw(img)
    margin = 34
    pitch = (margin, margin, w - margin, h - margin)
    draw.rounded_rectangle(pitch, radius=24, fill=(88, 168, 80, 255), outline=(245, 252, 245, 240), width=5)
    inner = (margin + 10, margin + 10, w - margin - 10, h - margin - 10)
    draw.rounded_rectangle(inner, radius=18, outline=(220, 255, 220, 70), width=10)
    stripe_w = (inner[2] - inner[0]) // 12
    colors = [(80, 158, 73, 255), (95, 175, 87, 255)]
    for i in range(12):
        x0 = inner[0] + i * stripe_w
        x1 = inner[0] + (i + 1) * stripe_w if i < 11 else inner[2]
        draw.rectangle((x0, inner[1], x1, inner[3]), fill=colors[i % 2])
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)
    # center glow
    o.ellipse((w * 0.17, h * 0.22, w * 0.83, h * 0.78), fill=(255, 255, 255, 20))
    # mow streaks
    for x in range(inner[0], inner[2], 42):
        o.line((x, inner[1] + 20, x + 130, inner[3] - 20), fill=(255, 255, 255, 18), width=2)
    overlay = overlay.filter(ImageFilter.GaussianBlur(1.2))
    img.alpha_composite(overlay)
    draw = ImageDraw.Draw(img)
    midx = w // 2
    midy = h // 2
    draw.line((midx, inner[1], midx, inner[3]), fill=(255, 255, 255, 238), width=4)
    draw.line((inner[0], midy, inner[2], midy), fill=(255, 255, 255, 238), width=4)
    draw.ellipse((midx - 92, midy - 92, midx + 92, midy + 92), outline=(255, 255, 255, 238), width=4)
    # penalty boxes
    box_w, box_h = 340, 160
    small_w, small_h = 140, 58
    draw.rectangle((midx - box_w / 2, inner[1], midx + box_w / 2, inner[1] + box_h), outline=(255, 255, 255, 238), width=4)
    draw.rectangle((midx - small_w / 2, inner[1], midx + small_w / 2, inner[1] + small_h), outline=(255, 255, 255, 238), width=4)
    draw.rectangle((midx - box_w / 2, inner[3] - box_h, midx + box_w / 2, inner[3]), outline=(255, 255, 255, 238), width=4)
    draw.rectangle((midx - small_w / 2, inner[3] - small_h, midx + small_w / 2, inner[3]), outline=(255, 255, 255, 238), width=4)
    # spots
    for y in (inner[1] + 105, midy, inner[3] - 105):
        draw.ellipse((midx - 5, y - 5, midx + 5, y + 5), fill=(255, 255, 255, 245))
    return img


def extract_grabcut(image_bgr: np.ndarray, rect: tuple[int, int, int, int]) -> Image.Image:
    x, y, w, h = rect
    crop = image_bgr[y : y + h, x : x + w].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    inner = (max(3, int(w * 0.12)), max(3, int(h * 0.06)), max(8, int(w * 0.76)), max(8, int(h * 0.88)))
    cv2.grabCut(crop, mask, inner, bgd_model, fgd_model, 6, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0 or len(ys) == 0:
      return Image.fromarray(rgba)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    pad = 6
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(rgba.shape[1], x1 + pad)
    y1 = min(rgba.shape[0], y1 + pad)
    return Image.fromarray(rgba[y0:y1, x0:x1])


def add_player(
    canvas: Image.Image,
    sprite: Image.Image,
    center: tuple[int, int],
    scale: float,
    number: str,
    rotate_deg: float = 0.0,
    glow=(132, 204, 22),
) -> None:
    sp = sprite.copy()
    if rotate_deg:
        sp = sp.rotate(rotate_deg, expand=True, resample=Image.Resampling.BICUBIC)
    new_w = max(18, int(sp.width * scale))
    new_h = max(18, int(sp.height * scale))
    sp = sp.resize((new_w, new_h), Image.Resampling.LANCZOS)

    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    x, y = center
    sd.ellipse((x - 28, y + new_h // 2 - 6, x + 28, y + new_h // 2 + 10), fill=(115, 185, 40, 105))
    sd.ellipse((x - 18, y + new_h // 2 - 2, x + 18, y + new_h // 2 + 7), fill=(10, 28, 18, 56))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(1.6))
    canvas.alpha_composite(shadow_layer)

    top_left = (int(x - new_w / 2), int(y - new_h / 2))
    canvas.alpha_composite(sp, top_left)

    overlay = ImageDraw.Draw(canvas)
    badge_y = top_left[1] + 16
    overlay.rounded_rectangle((x - 17, badge_y - 15, x + 17, badge_y + 15), radius=14, fill=(10, 20, 35, 240))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    bbox = overlay.textbbox((0, 0), str(number), font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    overlay.text((x - tw / 2, badge_y - th / 2 - 1), str(number), font=font, fill=(248, 250, 252, 255))


def main() -> None:
    image_bgr = cv2.imread(str(REF))
    if image_bgr is None:
        raise SystemExit(f"Cannot open {REF}")

    # manual bboxes from the user reference
    refs = [
        ((774, 333, 93, 190), "10", (800, 368), 0.78, 0),
        ((517, 289, 90, 190), "8", (550, 405), 0.76, -10),
        ((1060, 291, 92, 190), "7", (1045, 407), 0.76, 10),
        ((432, 534, 90, 205), "2", (420, 644), 0.78, -6),
        ((760, 580, 95, 220), "5", (720, 690), 0.78, -2),
        ((1106, 533, 94, 215), "6", (1048, 688), 0.78, 3),
        ((754, 150, 90, 190), "9", (800, 170), 0.76, 0),
    ]

    pitch = make_pitch()
    for rect, num, center, scale, angle in refs:
        sprite = extract_grabcut(image_bgr, rect)
        add_player(pitch, sprite, center, scale, num, angle)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pitch.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
