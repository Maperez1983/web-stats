from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/Volumes/Mac Satecchi/Mac/Downloads/jugador.png")
FIELD = ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape_v2.png"
OUT_DIR = ROOT / "tmp" / "premium_player_sprites"
PREVIEW = ROOT / "tmp" / "premium_player_sprites_preview.png"


SPRITES = [
    {
        "name": "idle",
        "crop": (85, 320, 325, 805),
        "rect": (34, 20, 140, 405),
        "place": (0.28, 0.68, 220),
    },
    {
        "name": "run",
        "crop": (355, 325, 630, 785),
        "rect": (34, 18, 185, 385),
        "place": (0.44, 0.55, 220),
    },
    {
        "name": "pass",
        "crop": (655, 320, 1065, 780),
        "rect": (30, 16, 265, 385),
        "place": (0.58, 0.57, 235),
    },
    {
        "name": "shoot",
        "crop": (1155, 185, 1508, 780),
        "rect": (28, 18, 255, 470),
        "place": (0.74, 0.42, 300),
    },
]


def extract_sprite(spec: dict[str, object]) -> Image.Image:
    source = cv2.imread(str(SOURCE), cv2.IMREAD_COLOR)
    if source is None:
        raise FileNotFoundError(SOURCE)

    x0, y0, x1, y1 = spec["crop"]  # type: ignore[index]
    crop = source[y0:y1, x0:x1].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    bg = np.zeros((1, 65), np.float64)
    fg = np.zeros((1, 65), np.float64)
    rx, ry, rw, rh = spec["rect"]  # type: ignore[index]
    cv2.grabCut(crop, mask, (rx, ry, rw, rh), bg, fg, 8, cv2.GC_INIT_WITH_RECT)

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
    alpha = np.where(alpha > 16, alpha, 0).astype(np.uint8)

    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    image = Image.fromarray(rgba, "RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    return image


def add_shadow(base: Image.Image, cx: int, cy: int, width: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rx = max(28, int(width * 0.34))
    ry = max(8, int(width * 0.12))
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(136, 192, 33, 100))
    draw.ellipse((cx - int(rx * 0.58), cy - int(ry * 0.46), cx + int(rx * 0.58), cy + int(ry * 0.46)), fill=(26, 42, 12, 55))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8)))


def build_preview() -> None:
    field = Image.open(FIELD).convert("RGBA").resize((1600, 900), Image.LANCZOS)
    for spec in SPRITES:
        name = str(spec["name"])
        sprite = Image.open(OUT_DIR / f"{name}.png").convert("RGBA")
        x_pct, y_pct, target_h = spec["place"]  # type: ignore[index]
        target_h = int(target_h)
        target_w = max(1, round(sprite.width * (target_h / sprite.height)))
        sprite = sprite.resize((target_w, target_h), Image.LANCZOS)
        x = round(field.width * float(x_pct))
        y = round(field.height * float(y_pct))
        add_shadow(field, x, y + target_h // 2 - 10, target_w)
        field.alpha_composite(sprite, (x - target_w // 2, y - target_h // 2))
    field.save(PREVIEW)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in SPRITES:
        sprite = extract_sprite(spec)
        sprite.save(OUT_DIR / f"{spec['name']}.png")
    build_preview()
    print(OUT_DIR)
    print(PREVIEW)


if __name__ == "__main__":
    main()
