from __future__ import annotations

from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
MEDIA_DIR = ROOT / "tmp" / "ppt_extract" / "ppt" / "media"
OUT = ROOT / "tmp" / "ppt_contact_sheet.png"


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


def main() -> None:
    files = []
    for path in sorted(MEDIA_DIR.iterdir()):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        try:
            with Image.open(path) as im:
                w, h = im.size
            area = w * h
            if area < 180_000:
                continue
            files.append((path, w, h, area))
        except Exception:
            continue

    files.sort(key=lambda item: item[3], reverse=True)
    files = files[:24]

    cell_w = 280
    cell_h = 210
    cols = 4
    rows = ceil(len(files) / cols)
    margin = 16
    header = 50
    canvas = Image.new("RGB", (margin + cols * (cell_w + margin), header + margin + rows * (cell_h + 42 + margin)), (18, 24, 39))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(22)
    label_font = _font(15)
    draw.text((margin, 14), "PPT media contact sheet", fill=(248, 250, 252), font=title_font)

    for idx, (path, w, h, _) in enumerate(files):
        row = idx // cols
        col = idx % cols
        x = margin + col * (cell_w + margin)
        y = header + margin + row * (cell_h + 42 + margin)
        with Image.open(path) as im:
            thumb = im.convert("RGB")
            thumb.thumbnail((cell_w, cell_h), Image.LANCZOS)
            tx = x + (cell_w - thumb.width) // 2
            ty = y + (cell_h - thumb.height) // 2
            canvas.paste(thumb, (tx, ty))
        draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=10, outline=(71, 85, 105), width=2)
        draw.text((x, y + cell_h + 8), f"{path.name}  {w}x{h}", fill=(226, 232, 240), font=label_font)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
