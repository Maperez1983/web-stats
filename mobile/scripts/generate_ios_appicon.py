#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


SPECS: list[tuple[str, int]] = [
    ("Icon-20@1x.png", 20),
    ("Icon-20@2x.png", 40),
    ("Icon-20@3x.png", 60),
    ("Icon-29@1x.png", 29),
    ("Icon-29@2x.png", 58),
    ("Icon-29@3x.png", 87),
    ("Icon-40@1x.png", 40),
    ("Icon-40@2x.png", 80),
    ("Icon-40@3x.png", 120),
    ("Icon-60@2x.png", 120),
    ("Icon-60@3x.png", 180),
    ("Icon-76@1x.png", 76),
    ("Icon-76@2x.png", 152),
    ("Icon-83.5@2x.png", 167),
    ("AppIcon-512@2x.png", 1024),
]


def _to_rgb_no_alpha(img: Image.Image, bg_hex: str) -> Image.Image:
    bg_hex = (bg_hex or "").strip().lstrip("#")
    if len(bg_hex) != 6:
        bg_hex = "08111D"
    r = int(bg_hex[0:2], 16)
    g = int(bg_hex[2:4], 16)
    b = int(bg_hex[4:6], 16)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    base = Image.new("RGB", img.size, (r, g, b))
    base.paste(img, mask=img.split()[-1])
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate iOS AppIcon.appiconset PNGs from a source PNG.")
    parser.add_argument(
        "--src",
        default="static/football/pwa/icons/icon-512.png",
        help="Source PNG (ideally >= 512x512). Default: static/football/pwa/icons/icon-512.png",
    )
    parser.add_argument(
        "--out-dir",
        default="mobile/ios/App/App/Assets.xcassets/AppIcon.appiconset",
        help="Output AppIcon.appiconset directory.",
    )
    parser.add_argument(
        "--bg",
        default="#08111D",
        help="Background color to flatten alpha (App Store icons must not include alpha). Default: #08111D",
    )
    args = parser.parse_args()

    src_path = Path(str(args.src)).expanduser().resolve()
    out_dir = Path(str(args.out_dir)).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src_path)
    img = img.convert("RGBA")

    resample = getattr(Image, "Resampling", Image).LANCZOS
    for filename, size in SPECS:
        resized = img.resize((size, size), resample=resample)
        final = _to_rgb_no_alpha(resized, str(args.bg))
        target = out_dir / filename
        final.save(target, format="PNG", optimize=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

