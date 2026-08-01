from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
REFERENCE = Path("/Volumes/Mac Satecchi/Mac/Library/Mobile Documents/com~apple~CloudDocs/Captura de pantalla 2026-07-02 a las 9.38.56.png")
FIELD = Path("/Volumes/Mac Satecchi/Mac/Downloads/tactics_stadium_premium_real_stadium.png")
OUT = ROOT / "tmp" / "reference_player_extract_mock.png"


CROPS = [
    {
        "label": "2",
        "crop": (262, 250, 358, 379),
        "rect": (16, 10, 64, 112),
        "place": (0.40, 0.70, 156),
    },
    {
        "label": "6",
        "crop": (317, 171, 389, 286),
        "rect": (14, 10, 44, 96),
        "place": (0.51, 0.57, 142),
    },
    {
        "label": "7",
        "crop": (593, 119, 674, 245),
        "rect": (16, 10, 48, 106),
        "place": (0.64, 0.49, 150),
    },
]


def _font(size: int):
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _extract_player(spec: dict[str, object]) -> Image.Image:
    image = cv2.imread(str(REFERENCE), cv2.IMREAD_COLOR)
    x0, y0, x1, y1 = spec["crop"]  # type: ignore[index]
    crop = image[y0:y1, x0:x1].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    rx, ry, rw, rh = spec["rect"]  # type: ignore[index]
    cv2.grabCut(crop, mask, (rx, ry, rw, rh), bg_model, fg_model, 7, cv2.GC_INIT_WITH_RECT)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    pil = Image.fromarray(rgba)

    bbox = pil.getbbox()
    if bbox:
        pil = pil.crop(bbox)
    return pil


def _shadow_layer(size: tuple[int, int], center: tuple[int, int], target_h: int) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    rx = max(24, int(target_h * 0.22))
    ry = max(7, int(target_h * 0.06))
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(121, 177, 24, 88))
    draw.ellipse((cx - int(rx * 0.7), cy - int(ry * 0.62), cx + int(rx * 0.7), cy + int(ry * 0.62)), fill=(10, 18, 26, 56))
    return layer.filter(ImageFilter.GaussianBlur(5))


def _place_player(base: Image.Image, player: Image.Image, label: str, x_pct: float, y_pct: float, target_h: int) -> None:
    scale = target_h / max(1, player.height)
    target_w = max(1, round(player.width * scale))
    sprite = player.resize((target_w, target_h), Image.LANCZOS)

    x = round(base.width * x_pct)
    y = round(base.height * y_pct)

    shadow = _shadow_layer(base.size, (x, y + target_h // 2 - 4), target_h)
    base.alpha_composite(shadow)
    base.alpha_composite(sprite, (x - target_w // 2, y - target_h // 2))

    draw = ImageDraw.Draw(base)
    badge_r = 15
    badge_y = y - target_h // 2 - 12
    draw.ellipse((x - badge_r, badge_y - badge_r, x + badge_r, badge_y + badge_r), fill=(17, 24, 39, 245), outline=(255, 255, 255, 48), width=2)
    font = _font(21)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw / 2, badge_y - th / 2 - 1), label, font=font, fill=(248, 250, 252, 255))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    field = Image.open(FIELD).convert("RGBA")
    players = [(_extract_player(spec), spec) for spec in CROPS]
    for player_img, spec in players:
        x_pct, y_pct, target_h = spec["place"]  # type: ignore[index]
        _place_player(field, player_img, str(spec["label"]), float(x_pct), float(y_pct), int(target_h))
    field.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
