from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
FIELD = Path("/Volumes/Mac Satecchi/Mac/Downloads/tactics_stadium_premium_real_stadium.png")
PLAYER = Path("/Volumes/Mac Satecchi/Mac/Downloads/player_sheet/Object_147.png")
GOALKEEPER = Path("/Volumes/Mac Satecchi/Mac/Downloads/player_sheet/Object_241.png")
OUT = ROOT / "tmp" / "player_3d_field_mock.png"


PLACEMENTS = [
    ("1", GOALKEEPER, 0.50, 0.78, 146),
    ("2", PLAYER, 0.29, 0.67, 128),
    ("3", PLAYER, 0.71, 0.67, 128),
    ("5", PLAYER, 0.43, 0.61, 122),
    ("6", PLAYER, 0.59, 0.60, 120),
    ("8", PLAYER, 0.38, 0.49, 114),
    ("10", PLAYER, 0.52, 0.49, 112),
    ("7", PLAYER, 0.66, 0.49, 114),
    ("9", PLAYER, 0.52, 0.35, 106),
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


def _shadow(base: Image.Image, center_x: int, center_y: int, target_h: int, tint=(132, 204, 22, 86)) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    rx = max(18, int(target_h * 0.24))
    ry = max(7, int(target_h * 0.07))
    draw.ellipse((center_x - rx, center_y - ry, center_x + rx, center_y + ry), fill=tint)
    draw.ellipse((center_x - int(rx * 0.68), center_y - int(ry * 0.64), center_x + int(rx * 0.68), center_y + int(ry * 0.64)), fill=(10, 18, 26, 54))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(5)))


def _add_player(base: Image.Image, label: str, sprite_path: Path, x_pct: float, y_pct: float, target_h: int) -> None:
    sprite = Image.open(sprite_path).convert("RGBA")
    bbox = sprite.getbbox()
    if bbox:
        sprite = sprite.crop(bbox)
    scale = target_h / max(1, sprite.height)
    target_w = max(1, round(sprite.width * scale))
    sprite = sprite.resize((target_w, target_h), Image.LANCZOS)

    x = round(base.width * x_pct)
    y = round(base.height * y_pct)
    _shadow(base, x, y + target_h // 2 - 3, target_h, tint=(132, 204, 22, 84) if sprite_path == PLAYER else (96, 165, 250, 84))
    base.alpha_composite(sprite, (x - target_w // 2, y - target_h // 2))

    draw = ImageDraw.Draw(base)
    badge_r = 14
    badge_y = y - target_h // 2 - 10
    draw.ellipse((x - badge_r, badge_y - badge_r, x + badge_r, badge_y + badge_r), fill=(17, 24, 39, 240), outline=(255, 255, 255, 46), width=2)
    font = _font(19)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x - tw / 2, badge_y - th / 2 - 1), label, font=font, fill=(248, 250, 252, 255))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    field = Image.open(FIELD).convert("RGBA")
    for placement in PLACEMENTS:
        _add_player(field, *placement)
    field.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
