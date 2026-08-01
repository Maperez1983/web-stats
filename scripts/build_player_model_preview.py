from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter, ImageOps, ImageDraw


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
SRC = ROOT / "tmp" / "player_men_sheet"
OUT_DIR = ROOT / "tmp" / "player_model_preview"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    ("man_a.png", "A"),
    ("man_b.png", "B"),
    ("man_c.png", "C"),
]


def crop_subject(im: Image.Image, pad: int = 24) -> Image.Image:
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return im.copy()
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(im.width, right + pad)
    bottom = min(im.height, bottom + pad)
    return im.crop((left, top, right, bottom))


def add_outline(im: Image.Image) -> Image.Image:
    alpha = im.getchannel("A")
    edge = alpha.filter(ImageFilter.MaxFilter(7))
    outline = Image.new("RGBA", im.size, (255, 255, 255, 0))
    opx = outline.load()
    apx = alpha.load()
    epx = edge.load()
    for y in range(im.height):
        for x in range(im.width):
            if epx[x, y] and not apx[x, y]:
                opx[x, y] = (245, 248, 255, 255)
    out = Image.alpha_composite(outline, im)
    return out


def build_card(im: Image.Image, label: str) -> Image.Image:
    card = Image.new("RGBA", (560, 760), (10, 16, 28, 255))
    inner = Image.new("RGBA", (520, 720), (16, 24, 38, 255))
    card.alpha_composite(inner, (20, 20))

    subject = crop_subject(im)
    subject = add_outline(subject)
    subject = ImageOps.contain(subject, (420, 560), Image.LANCZOS)

    shadow = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((subject.width * 0.22, subject.height * 0.84, subject.width * 0.78, subject.height * 0.96), fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))

    x = (560 - subject.width) // 2
    y = 80
    card.alpha_composite(shadow, (x, y))
    card.alpha_composite(subject, (x, y))

    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle((210, 24, 350, 64), radius=20, fill=(33, 41, 59, 230), outline=(148, 163, 184, 120), width=2)
    draw.text((278, 44), f"MODELO {label}", anchor="mm", fill=(248, 250, 252, 255))
    return card


def main() -> None:
    cards = []
    for filename, label in FILES:
        im = Image.open(SRC / filename).convert("RGBA")
        cards.append(build_card(im, label))

    sheet = Image.new("RGBA", (len(cards) * 560, 760), (6, 10, 18, 255))
    for i, card in enumerate(cards):
        sheet.alpha_composite(card, (i * 560, 0))

    sheet.save(OUT_DIR / "player_models_improved_sheet.png")

    # selected best option for further integration
    best = crop_subject(Image.open(SRC / "man_b.png").convert("RGBA"))
    best = add_outline(best)
    best = ImageOps.contain(best, (768, 1024), Image.LANCZOS)
    canvas = Image.new("RGBA", (900, 1100), (0, 0, 0, 0))
    x = (canvas.width - best.width) // 2
    y = 30
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((canvas.width * 0.34, 930, canvas.width * 0.66, 1010), fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(best, (x, y))
    canvas.save(OUT_DIR / "player_model_best_v1.png")


if __name__ == "__main__":
    main()
