from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path("/Volumes/Mac Satecchi/Mac/Web-stats")
SRC_DIR = Path("/Volumes/Mac Satecchi/Mac/Downloads")
OUT_DIR = ROOT / "static" / "football" / "images" / "token-sprites"

SOURCE_FILES = {
    "idle": SRC_DIR / "sprite_idle_v1.png",
    "run": SRC_DIR / "sprite_run_v1.png",
    "pass": SRC_DIR / "sprite_pass_v1.png",
    "shoot": SRC_DIR / "sprite_shoot_v1.png",
}

TARGETS = {
    "local": (26, 138, 76),
    "rival": (188, 42, 53),
    "goalkeeper": (212, 165, 35),
    "blue": (18, 92, 214),
}

CANVAS = (384, 512)
FIGURE_POSE = "idle"


def _load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _crop_alpha(im: Image.Image) -> Image.Image:
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im.copy()


def _pad_subject(
    im: Image.Image,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
    left: int = 0,
) -> Image.Image:
    src = _crop_alpha(im)
    canvas = Image.new(
        "RGBA",
        (src.width + left + right, src.height + top + bottom),
        (0, 0, 0, 0),
    )
    canvas.alpha_composite(src, (left, top))
    return canvas


def _fit_canvas(im: Image.Image, height: int = 430) -> Image.Image:
    src = _crop_alpha(im)
    scale = height / max(1, src.height)
    target = src.resize((max(1, round(src.width * scale)), height), Image.LANCZOS)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    x = (CANVAS[0] - target.width) // 2
    y = CANVAS[1] - target.height - 18
    canvas.alpha_composite(target, (x, y))
    return canvas


def _trim_for_figure_pose(im: Image.Image) -> Image.Image:
    src = _crop_alpha(im)
    if FIGURE_POSE == "idle":
        # La fuente llega demasiado pegada al borde; damos aire para no cortar
        # cabeza ni botas al escalarla en el token final.
        return _pad_subject(src, top=18, bottom=18, left=10, right=10)
    # El sprite "run" trae un balón residual en el borde inferior derecho.
    # En vez de recortar por abajo y cargarnos las botas, vaciamos solo esa zona.
    if src.mode != "RGBA":
        src = src.convert("RGBA")
    px = src.load()
    cut_x = int(src.width * 0.64)
    cut_y = int(src.height * 0.78)
    for y in range(cut_y, src.height):
        for x in range(cut_x, src.width):
            r, g, b, a = px[x, y]
            if a < 8:
                continue
            px[x, y] = (r, g, b, 0)
    return src


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0
    mx = max(rf, gf, bf)
    mn = min(rf, gf, bf)
    diff = mx - mn
    if diff == 0:
        h = 0.0
    elif mx == rf:
        h = (60 * ((gf - bf) / diff) + 360) % 360
    elif mx == gf:
        h = (60 * ((bf - rf) / diff) + 120) % 360
    else:
        h = (60 * ((rf - gf) / diff) + 240) % 360
    s = 0.0 if mx == 0 else diff / mx
    v = mx
    return h, s, v


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    c = v * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = v - c
    if 0 <= h < 60:
        rp, gp, bp = c, x, 0
    elif 60 <= h < 120:
        rp, gp, bp = x, c, 0
    elif 120 <= h < 180:
        rp, gp, bp = 0, c, x
    elif 180 <= h < 240:
        rp, gp, bp = 0, x, c
    elif 240 <= h < 300:
        rp, gp, bp = x, 0, c
    else:
        rp, gp, bp = c, 0, x
    return (
        max(0, min(255, round((rp + m) * 255))),
        max(0, min(255, round((gp + m) * 255))),
        max(0, min(255, round((bp + m) * 255))),
    )


def _recolor_shirt(im: Image.Image, target_rgb: tuple[int, int, int]) -> Image.Image:
    out = im.copy()
    target_h, target_s, _target_v = _rgb_to_hsv(*target_rgb)
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 12:
                continue
            h, s, v = _rgb_to_hsv(r, g, b)
            blueish = (185 <= h <= 250 and s > 0.28 and v > 0.16)
            cyan_trim = (160 <= h < 185 and s > 0.22 and v > 0.25)
            if not (blueish or cyan_trim):
                continue
            next_s = min(1.0, max(0.35, target_s * (0.9 if blueish else 0.6)))
            next_v = min(1.0, max(0.10, v * 0.96 + 0.02))
            nr, ng, nb = _hsv_to_rgb(target_h, next_s, next_v)
            px[x, y] = (nr, ng, nb, a)
    return out


def _write_variant(base_key: str, pose: str, target: tuple[int, int, int]) -> Path:
    src = _load_rgba(SOURCE_FILES[pose])
    fitted = _fit_canvas(_recolor_shirt(src, target))
    out = OUT_DIR / f"premium-{base_key}-{pose}.png"
    fitted.save(out)
    return out


def _write_figure_variant(base_key: str, target: tuple[int, int, int]) -> Path:
    src = _load_rgba(SOURCE_FILES[FIGURE_POSE])
    recolored = _recolor_shirt(src, target)
    trimmed = _trim_for_figure_pose(recolored)
    fitted = _fit_canvas(trimmed, height=446)
    out = OUT_DIR / f"premium-{base_key}-figure.png"
    fitted.save(out)
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for variant, rgb in TARGETS.items():
        for pose in SOURCE_FILES:
            generated.append(_write_variant(variant, pose, rgb))
        generated.append(_write_figure_variant(variant, rgb))
    for path in generated:
        print(path)


if __name__ == "__main__":
    main()
