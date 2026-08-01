from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TEAM_PHOTO = ROOT / "static" / "football" / "images" / "team-01.jpg"
FIELD = ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape_v2.png"
OUT = ROOT / "tmp" / "muestra_figura_fotografica_equipo_v1.png"


PLAYER_RECTS = [
    ("2", (315, 345, 230, 520), (410, 700), 0.66),
    ("8", (520, 340, 220, 500), (660, 520), 0.62),
    ("5", (705, 330, 240, 520), (820, 690), 0.66),
    ("7", (1120, 340, 220, 500), (1185, 525), 0.62),
    ("3", (1240, 335, 220, 520), (1380, 700), 0.66),
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


def extract_player(image_bgr: np.ndarray, rect: tuple[int, int, int, int]) -> Image.Image:
    x, y, w, h = rect
    crop = image_bgr[y : y + h, x : x + w].copy()
    mask = np.zeros(crop.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    inner = (12, 12, max(8, w - 24), max(8, h - 24))
    cv2.grabCut(crop, mask, inner, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)

    alpha = np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    alpha = cv2.medianBlur(alpha, 5)

    # Clean common turf spill.
    b, g, r = cv2.split(crop)
    turf_like = (g > r + 10) & (g > b + 8) & (g > 70)
    alpha[turf_like] = 0

    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    image = Image.fromarray(rgba, "RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    return image


def add_shadow(base: Image.Image, center: tuple[int, int], width: int, height: int) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    rx = max(34, width // 2)
    ry = max(12, height // 10)
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(132, 204, 22, 110))
    draw.ellipse((cx - int(rx * 0.72), cy - int(ry * 0.56), cx + int(rx * 0.72), cy + int(ry * 0.56)), fill=(24, 48, 18, 46))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(8)))


def add_badge(base: Image.Image, center_x: int, top_y: int, label: str) -> None:
    draw = ImageDraw.Draw(base)
    radius = 16
    cy = top_y - 14
    draw.ellipse(
        (center_x - radius, cy - radius, center_x + radius, cy + radius),
        fill=(15, 23, 42, 242),
        outline=(255, 255, 255, 80),
        width=2,
    )
    font = _font(20)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((center_x - tw / 2, cy - th / 2 - 1), label, font=font, fill=(248, 250, 252, 255))


def paste_player(base: Image.Image, player: Image.Image, center: tuple[int, int], scale: float, label: str) -> None:
    width = max(1, round(player.width * scale))
    height = max(1, round(player.height * scale))
    player = player.resize((width, height), Image.LANCZOS)
    cx, cy = center
    x = round(cx - width / 2)
    y = round(cy - height / 2)
    add_shadow(base, (cx, y + height - 12), width, height)
    base.alpha_composite(player, (x, y))
    add_badge(base, cx, y, label)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    field_path = FIELD if FIELD.exists() else ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape.png"
    field = Image.open(field_path).convert("RGBA")
    team_bgr = cv2.imread(str(TEAM_PHOTO), cv2.IMREAD_COLOR)
    if team_bgr is None:
        raise FileNotFoundError(TEAM_PHOTO)

    for label, rect, center, scale in PLAYER_RECTS:
        player = extract_player(team_bgr, rect)
        paste_player(field, player, center, scale, label)

    field.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
