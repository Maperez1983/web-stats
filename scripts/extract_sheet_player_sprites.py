from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SRC = Path("/Volumes/Mac Satecchi/Mac/Downloads/jugador.png")
OUT_DIR = ROOT / "tmp" / "player_sheet_extract"
FIELD_BG = ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape_v2.png"
FIELD_OUT = ROOT / "tmp" / "muestra_sprites_sheet_field_v1.png"


SPRITES = [
    ("idle", (96, 320, 220, 390), {"trim_bottom": 44}),
    ("run", (360, 320, 290, 390), {"trim_bottom": 40}),
    ("pass", (675, 300, 365, 405), {"trim_bottom": 18}),
    ("shoot", (1125, 185, 360, 470), {"trim_bottom": 8}),
]


def extract_rgba(
    image_bgr: np.ndarray,
    rect: tuple[int, int, int, int],
    *,
    trim_bottom: int = 0,
) -> Image.Image:
    x, y, w, h = rect
    crop = image_bgr[y:y + h, x:x + w].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    inner = (10, 10, max(8, w - 20), max(8, h - 20))
    cv2.grabCut(crop, mask, inner, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    alpha = cv2.medianBlur(alpha, 5)

    b, g, r = cv2.split(crop)
    dark_bg = (r < 120) & (g < 120) & (b < 120)
    alpha[dark_bg & (alpha < 220)] = 0

    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    if trim_bottom:
        rgba[max(0, rgba.shape[0] - trim_bottom):, :, 3] = 0
    image = Image.fromarray(rgba, "RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    return image


def add_ground_glow(base: Image.Image, center_x: int, center_y: int, width: int, tint=(132, 204, 22, 96)) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rx = max(18, width // 2)
    ry = max(8, width // 6)
    draw.ellipse((center_x - rx, center_y - ry, center_x + rx, center_y + ry), fill=tint)
    draw.ellipse((center_x - int(rx * 0.65), center_y - int(ry * 0.55), center_x + int(rx * 0.65), center_y + int(ry * 0.55)), fill=(12, 24, 18, 40))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8)))


def build_field_preview(sprite_paths: list[Path]) -> None:
    bg_path = FIELD_BG if FIELD_BG.exists() else ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape.png"
    field = Image.open(bg_path).convert("RGBA")
    placements = [
        (0.33, 0.66, 150),
        (0.44, 0.53, 168),
        (0.57, 0.53, 168),
        (0.70, 0.41, 185),
    ]
    for sprite_path, (xp, yp, target_h) in zip(sprite_paths, placements):
        sprite = Image.open(sprite_path).convert("RGBA")
        scale = target_h / max(1, sprite.height)
        target_w = max(1, round(sprite.width * scale))
        sprite = sprite.resize((target_w, target_h), Image.LANCZOS)
        cx = round(field.width * xp)
        cy = round(field.height * yp)
        x = cx - target_w // 2
        y = cy - target_h // 2
        add_ground_glow(field, cx, y + target_h - 8, target_w)
        field.alpha_composite(sprite, (x, y))
    field.save(FIELD_OUT)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image_bgr = cv2.imread(str(SRC), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise FileNotFoundError(SRC)

    sprite_paths: list[Path] = []
    for name, rect, options in SPRITES:
        sprite = extract_rgba(image_bgr, rect, **options)
        out = OUT_DIR / f"{name}.png"
        sprite.save(out)
        sprite_paths.append(out)

    build_field_preview(sprite_paths)
    print(FIELD_OUT)
    for path in sprite_paths:
        print(path)


if __name__ == "__main__":
    main()
