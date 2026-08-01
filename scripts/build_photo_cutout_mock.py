from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
BASE_IMAGE = Path("/Volumes/Mac Satecchi/Mac/Downloads/tactics_stadium_premium_real_stadium.png")
OUT_IMAGE = ROOT / "tmp" / "photo_cutout_mock_preview.png"
PLAYERS_DIR = ROOT / "static" / "football" / "images" / "players"


PLAYERS: list[dict[str, object]] = [
    {"file": "tadeo-n1-cut.png", "number": "1", "x": 0.50, "y": 0.80, "h": 146},
    {"file": "antonio-n2-cut.png", "number": "2", "x": 0.28, "y": 0.66, "h": 126},
    {"file": "ayala-n3-cut.png", "number": "3", "x": 0.72, "y": 0.66, "h": 126},
    {"file": "nico-n5-cut.png", "number": "5", "x": 0.45, "y": 0.62, "h": 128},
    {"file": "martinez-n6-cut.png", "number": "6", "x": 0.60, "y": 0.61, "h": 132},
    {"file": "yaco-n7-cut.png", "number": "7", "x": 0.66, "y": 0.50, "h": 132},
    {"file": "nacho-n8-cut.png", "number": "8", "x": 0.40, "y": 0.50, "h": 132},
    {"file": "jorge-n15-cut.png", "number": "9", "x": 0.52, "y": 0.36, "h": 134},
    {"file": "francis-n17-cut.png", "number": "10", "x": 0.52, "y": 0.49, "h": 134},
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: Iterable[str] = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _add_shadow(base: Image.Image, alpha_mask: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    local = Image.new("RGBA", alpha_mask.size, (6, 12, 20, 150))
    shadow.paste(local, (x0, y0), alpha_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(shadow)


def _add_player(base: Image.Image, player_file: str, number: str, x_pct: float, y_pct: float, target_h: int) -> None:
    src = Image.open(PLAYERS_DIR / player_file).convert("RGBA")
    scale = target_h / max(1, src.height)
    target_w = max(1, round(src.width * scale))
    resized = src.resize((target_w, target_h), Image.LANCZOS)

    x = round(base.width * x_pct)
    y = round(base.height * y_pct)

    glow_w = max(68, round(target_w * 0.48))
    glow_h = max(18, round(target_h * 0.09))
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_box = (
        x - glow_w,
        y + target_h // 2 - glow_h // 2 + 14,
        x + glow_w,
        y + target_h // 2 + glow_h // 2 + 14,
    )
    glow_draw.ellipse(glow_box, fill=(144, 208, 35, 94))
    glow = glow.filter(ImageFilter.GaussianBlur(5))
    base.alpha_composite(glow)

    shadow_mask = resized.getchannel("A")
    shadow_box = (
        x - target_w // 2 + 8,
        y - target_h // 2 + 10,
        x + target_w // 2 + 8,
        y + target_h // 2 + 10,
    )
    _add_shadow(base, shadow_mask, shadow_box)

    paste_box = (x - target_w // 2, y - target_h // 2)
    base.alpha_composite(resized, paste_box)

    draw = ImageDraw.Draw(base)
    badge_r = 15
    badge_y = y - target_h // 2 - 14
    draw.ellipse((x - badge_r, badge_y - badge_r, x + badge_r, badge_y + badge_r), fill=(17, 24, 39, 240))
    draw.ellipse((x - badge_r, badge_y - badge_r, x + badge_r, badge_y + badge_r), outline=(255, 255, 255, 34), width=2)

    font = _font(20)
    bbox = draw.textbbox((0, 0), number, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw / 2, badge_y - th / 2 - 1), number, font=font, fill=(248, 250, 252, 255))


def main() -> None:
    OUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    base = Image.open(BASE_IMAGE).convert("RGBA")
    for spec in PLAYERS:
        _add_player(
            base,
            str(spec["file"]),
            str(spec["number"]),
            float(spec["x"]),
            float(spec["y"]),
            int(spec["h"]),
        )
    base.save(OUT_IMAGE)
    print(OUT_IMAGE)


if __name__ == "__main__":
    main()
