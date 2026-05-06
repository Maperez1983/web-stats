#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class OptimizeResult:
    path: Path
    before: int
    after: int
    size: tuple[int, int]


def _optimize_jpeg(path: Path, *, max_size: tuple[int, int], quality: int) -> OptimizeResult:
    before = path.stat().st_size
    img = Image.open(path).convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    img.save(path, format="JPEG", quality=quality, optimize=True, progressive=True)
    after = path.stat().st_size
    return OptimizeResult(path=path, before=before, after=after, size=img.size)


def _optimize_png(path: Path, *, max_side: int) -> OptimizeResult:
    before = path.stat().st_size
    img = Image.open(path).convert("RGBA")
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img.save(path, format="PNG", optimize=True)
    after = path.stat().st_size
    return OptimizeResult(path=path, before=before, after=after, size=img.size)


def _human_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optimize big static images (lossy JPEG resize, PNG optimize/resize).",
    )
    parser.add_argument("--root", default=".", help="Repo root (default: .)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change, but don't write.")
    parser.add_argument("--jpeg-max-w", type=int, default=1600)
    parser.add_argument("--jpeg-max-h", type=int, default=1200)
    parser.add_argument("--jpeg-quality", type=int, default=72)
    parser.add_argument("--png-max-side", type=int, default=768)
    parser.add_argument("--min-bytes", type=int, default=600_000, help="Only optimize files >= this size.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    jpg_paths = [
        root / "static" / "football" / "images" / "team-01.jpg",
        root / "static" / "football" / "images" / "team-02.jpg",
        root / "static" / "football" / "images" / "team-03.jpg",
    ]
    png_dir = root / "static" / "football" / "images" / "players"

    results: list[OptimizeResult] = []

    def maybe_optimize_jpeg(path: Path) -> None:
        if not path.exists() or not path.is_file():
            return
        if path.stat().st_size < args.min_bytes:
            return
        if args.dry_run:
            img = Image.open(path)
            img.thumbnail((args.jpeg_max_w, args.jpeg_max_h), Image.LANCZOS)
            results.append(OptimizeResult(path=path, before=path.stat().st_size, after=-1, size=img.size))
            return
        results.append(
            _optimize_jpeg(
                path,
                max_size=(args.jpeg_max_w, args.jpeg_max_h),
                quality=max(40, min(90, int(args.jpeg_quality))),
            )
        )

    def maybe_optimize_png(path: Path) -> None:
        if not path.exists() or not path.is_file():
            return
        if path.stat().st_size < args.min_bytes:
            return
        if args.dry_run:
            img = Image.open(path)
            img.thumbnail((args.png_max_side, args.png_max_side), Image.LANCZOS)
            results.append(OptimizeResult(path=path, before=path.stat().st_size, after=-1, size=img.size))
            return
        results.append(_optimize_png(path, max_side=max(128, int(args.png_max_side))))

    for path in jpg_paths:
        maybe_optimize_jpeg(path)

    if png_dir.exists():
        for path in sorted(png_dir.glob("*.png")):
            maybe_optimize_png(path)

    if not results:
        print("No matching files.")
        return 0

    total_before = sum(r.before for r in results)
    total_after = sum((r.after if r.after >= 0 else r.before) for r in results)

    for r in results:
        rel = r.path.relative_to(root)
        if r.after >= 0:
            delta = r.before - r.after
            print(f"{rel}: {r.before} -> {r.after} bytes (Δ {delta}) size={r.size}")
        else:
            print(f"{rel}: {r.before} bytes (dry-run) target_size={r.size}")
    print(f"Total: {_human_mb(total_before)} -> {_human_mb(total_after)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

