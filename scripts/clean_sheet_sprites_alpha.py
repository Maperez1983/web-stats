from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "tmp" / "player_sheet_extract"
OUT_DIR = ROOT / "tmp" / "player_sheet_clean"


FILES = ["idle.png", "run.png", "pass.png", "shoot.png"]


def _floodfill_bg_mask(bgr: np.ndarray) -> np.ndarray:
    h, w, _ = bgr.shape
    work = bgr.copy()
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    bg = np.zeros((h, w), dtype=np.uint8)
    seeds = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]
    lo = (18, 18, 18)
    hi = (18, 18, 18)
    for seed in seeds:
        ff_mask[:] = 0
        _, _, _, rect = cv2.floodFill(
            work,
            ff_mask,
            seedPoint=seed,
            newVal=(0, 0, 255),
            loDiff=lo,
            upDiff=hi,
            flags=4 | cv2.FLOODFILL_FIXED_RANGE,
        )
        flooded = ff_mask[1:-1, 1:-1] > 0
        bg[flooded] = 255
    return bg


def clean_sprite(path: Path, out_path: Path) -> None:
    rgba = Image.open(path).convert("RGBA")
    rgb = np.array(rgba)[:, :, :3]
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    bg = _floodfill_bg_mask(bgr)
    alpha = 255 - bg
    alpha = cv2.medianBlur(alpha, 5)
    kernel = np.ones((3, 3), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel, iterations=1)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)

    out = np.array(rgba)
    out[:, :, 3] = alpha
    image = Image.fromarray(out, "RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    image.save(out_path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        clean_sprite(SRC_DIR / name, OUT_DIR / name)
        print(OUT_DIR / name)


if __name__ == "__main__":
    main()
