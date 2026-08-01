from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DOWNLOADS = Path("/Volumes/Mac Satecchi/Mac/Downloads")


def grabcut_extract(image_path: Path, rect: tuple[int, int, int, int]) -> Image.Image:
    image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise FileNotFoundError(image_path)

    mask = np.zeros(image_bgr.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(image_bgr, mask, rect, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)

    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    alpha = cv2.medianBlur(alpha, 5)

    rgba = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = alpha
    pil = Image.fromarray(rgba)
    bbox = pil.getbbox()
    if bbox:
        pil = pil.crop(bbox)
    return pil


def add_glow_shadow(base: Image.Image, player: Image.Image, xy: tuple[int, int], scale: float = 1.0) -> None:
    x, y = xy
    width = int(player.width * scale)
    height = int(player.height * scale)
    player = player.resize((width, height), Image.LANCZOS)

    shadow = Image.new("RGBA", (width + 80, height + 80), (0, 0, 0, 0))
    ellipse = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    ellipse_draw = Image.fromarray(np.zeros((shadow.height, shadow.width, 4), dtype=np.uint8))
    overlay = np.zeros((shadow.height, shadow.width, 4), dtype=np.uint8)
    cx = shadow.width // 2
    cy = shadow.height - 35
    rx = max(50, width // 2)
    ry = max(18, height // 10)
    yy, xx = np.ogrid[:shadow.height, :shadow.width]
    mask = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    overlay[mask] = (117, 214, 26, 105)
    glow = Image.fromarray(overlay, "RGBA").filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(glow, (x - 35, y + height - 25))
    base.alpha_composite(player, (x, y))


def main() -> None:
    field_path = ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape_v2.png"
    if not field_path.exists():
        field_path = ROOT / ".tmp_task_builder_editor_surface_stadium_native_landscape.png"
    field = Image.open(field_path).convert("RGBA")

    source = TMP / "image24_cw.png"
    player = grabcut_extract(source, (390, 205, 150, 225))

    cleaned = Image.new("RGBA", player.size, (0, 0, 0, 0))
    arr = np.array(player)
    # Remove turf spill and bright background contamination near legs.
    r, g, b, a = [arr[:, :, i] for i in range(4)]
    turf_like = (g > r + 12) & (g > b + 10) & (g > 70)
    washed = (r > 220) & (g > 220) & (b > 220)
    a[turf_like | washed] = 0
    arr[:, :, 3] = a
    player = Image.fromarray(arr, "RGBA")
    bbox = player.getbbox()
    if bbox:
        player = player.crop(bbox)

    positions = [
        (870, 510, 0.64, "7"),
        (680, 485, 0.66, "10"),
        (540, 540, 0.62, "8"),
        (1140, 730, 0.60, "3"),
        (410, 725, 0.60, "2"),
        (780, 930, 0.58, "1"),
    ]

    for x, y, scale, _ in positions:
        add_glow_shadow(field, player, (x, y), scale)

    out = ROOT / "tmp" / "muestra_figura_fotografica_v2.png"
    field.save(out)
    print(out)


if __name__ == "__main__":
    main()
