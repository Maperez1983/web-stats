from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from football.models import Player, Team
from football.views import save_player_license

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageOps = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


def _normalize_name(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^\w\sáéíóúüñ]+", " ", value, flags=re.IGNORECASE)
    value = value.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    value = value.replace("ü", "u").replace("ñ", "n")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _tokenize(value: str) -> set[str]:
    return {token for token in _normalize_name(value).split() if token and token not in {"de", "del", "la", "el"}}


def _extract_license_name(text: str) -> str:
    text = str(text or "")
    text = text.replace("\u00a0", " ")
    # Normaliza saltos
    compact = re.sub(r"[ \t]+", " ", text)

    def _find(label: str) -> str:
        match = re.search(rf"{label}\s*:?\s*([A-Za-zÁÉÍÓÚÜÑñ\- ]+)", compact, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    nombre = _find("Nombre")
    ap1 = _find("Apellido\\s*1")
    ap2 = _find("Apellido\\s*2")
    if nombre and ap1:
        parts = [nombre, ap1, ap2]
        return " ".join([part for part in parts if part]).strip()

    # Fallback: detecta líneas tipo "Nombre: X Apellido 1: Y Apellido 2: Z"
    match = re.search(
        r"Nombre\s*:?\s*(?P<n>[A-Za-zÁÉÍÓÚÜÑñ\- ]+)\s+Apellido\s*1\s*:?\s*(?P<a1>[A-Za-zÁÉÍÓÚÜÑñ\- ]+)(?:\s+Apellido\s*2\s*:?\s*(?P<a2>[A-Za-zÁÉÍÓÚÜÑñ\- ]+))?",
        compact,
        flags=re.IGNORECASE,
    )
    if match:
        parts = [match.group("n"), match.group("a1"), match.group("a2") or ""]
        return " ".join([part.strip() for part in parts if part and part.strip()]).strip()
    return ""


def _best_player_match(players: list[Player], license_name: str) -> tuple[Player | None, float]:
    if not license_name:
        return None, 0.0
    license_tokens = _tokenize(license_name)
    if not license_tokens:
        return None, 0.0
    best_player = None
    best_score = 0.0
    for player in players:
        player_tokens = _tokenize(player.full_name or player.name)
        if not player_tokens:
            continue
        overlap = len(license_tokens & player_tokens)
        union = len(license_tokens | player_tokens)
        score = (overlap / union) if union else 0.0
        # Boost si coincide nombre + primer apellido
        if overlap >= 2:
            score += 0.25
        if score > best_score:
            best_score = score
            best_player = player
    return best_player, float(best_score)


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def _ensure_tool(tool_name: str) -> str:
    path = shutil.which(tool_name) or ""
    if not path:
        raise RuntimeError(f"Falta dependencia del sistema: `{tool_name}` (instala Poppler / ImageMagick).")
    return path


def _render_page_pngs(pdf_path: str, out_dir: Path, *, dpi: int = 220) -> list[Path]:
    _ensure_tool("pdftoppm")
    prefix = out_dir / "page"
    cmd = ["pdftoppm", "-png", "-r", str(int(dpi)), pdf_path, str(prefix)]
    _run(cmd)
    pages = sorted(out_dir.glob("page-*.png"), key=lambda p: int(re.sub(r"\D+", "", p.stem) or "0"))
    return pages


def _pdf_page_text(pdf_path: str, page_num: int) -> str:
    _ensure_tool("pdftotext")
    cmd = ["pdftotext", "-f", str(page_num), "-l", str(page_num), "-layout", pdf_path, "-"]
    proc = _run(cmd, check=False)
    return (proc.stdout or "").strip()


def _ocr_text(image_path: Path) -> str:
    if pytesseract is None or Image is None:
        return ""
    try:
        img = Image.open(image_path)
        if ImageOps is not None:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
        return str(pytesseract.image_to_string(img, lang="spa") or "").strip()
    except Exception:
        return ""


def _prepare_license_jpeg(image_path: Path) -> bytes:
    if Image is None:
        return image_path.read_bytes()
    with Image.open(image_path) as img:
        if ImageOps is not None:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
        rgb = img.convert("RGB")
        # Auto-crop a contenido (reduce márgenes para que la cuadrícula sea más legible).
        try:
            gray = ImageOps.grayscale(rgb)
            inv = ImageOps.invert(gray)
            bbox = inv.getbbox()
            if bbox:
                left, top, right, bottom = bbox
                pad = 18
                left = max(0, left - pad)
                top = max(0, top - pad)
                right = min(rgb.width, right + pad)
                bottom = min(rgb.height, bottom + pad)
                rgb = rgb.crop((left, top, right, bottom))
        except Exception:
            pass
        rgb.thumbnail((1500, 1000))
        out = ContentFile(b"")
        # ContentFile doesn't expose buffer, use BytesIO.
        import io

        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", optimize=True, quality=78)
        return buffer.getvalue()


@dataclass
class PageResult:
    page: int
    card: int
    extracted_name: str
    player_id: int | None
    player_name: str
    score: float
    saved_as: str
    error: str


class Command(BaseCommand):
    help = "Importa licencias federativas desde un PDF (una licencia por página) y las asigna a jugadores."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", required=True, help="Ruta local al PDF con carnets (una licencia por página).")
        parser.add_argument("--team-slug", required=True, help="Slug del equipo (Team.slug).")
        parser.add_argument("--min-score", type=float, default=0.55, help="Score mínimo para asignar automáticamente.")
        parser.add_argument("--dry-run", action="store_true", help="No guarda nada, solo muestra el mapeo.")
        parser.add_argument("--out-json", default="", help="Ruta para guardar el mapping en JSON.")
        parser.add_argument("--export-dir", default="", help="Directorio para exportar JPGs normalizados (por página/nombre).")
        parser.add_argument("--dpi", type=int, default=220, help="DPI para rasterizar el PDF.")
        parser.add_argument(
            "--split",
            default="auto",
            choices=["auto", "off"],
            help="Detecta y separa múltiples licencias por página (auto recomendado).",
        )

    def handle(self, *args, **options):
        pdf_path = str(options["pdf"])
        team_slug = str(options["team_slug"])
        min_score = float(options["min_score"] or 0.0)
        dry_run = bool(options["dry_run"])
        out_json = str(options.get("out_json") or "").strip()
        export_dir = str(options.get("export_dir") or "").strip()
        dpi = int(options.get("dpi") or 220)
        split_mode = str(options.get("split") or "auto").strip().lower()

        pdf_file = Path(pdf_path).expanduser()
        if not pdf_file.exists():
            raise RuntimeError(f"PDF no encontrado: {pdf_file}")

        team = Team.objects.filter(slug=team_slug).first()
        if not team:
            raise RuntimeError(f"Team no encontrado con slug={team_slug}")

        players = list(Player.objects.filter(team=team).order_by("id"))
        if not players:
            raise RuntimeError("No hay jugadores en ese equipo.")

        results: list[PageResult] = []
        export_root = Path(export_dir).expanduser() if export_dir else None
        if export_root:
            export_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="2j-licenses-") as tmp:
            tmp_dir = Path(tmp)
            pages = _render_page_pngs(str(pdf_file), tmp_dir, dpi=dpi)
            if not pages:
                raise RuntimeError("No se pudieron rasterizar páginas del PDF.")

            for page_idx, img_path in enumerate(pages, start=1):
                if Image is None:
                    card_images = [img_path]
                else:
                    card_images = []
                    try:
                        with Image.open(img_path) as base_img:
                            if ImageOps is not None:
                                try:
                                    base_img = ImageOps.exif_transpose(base_img)
                                except Exception:
                                    pass
                            rgb = base_img.convert("RGB")
                            if split_mode == "off":
                                card_images = [rgb]
                            else:
                                card_images = _split_vertical_cards(rgb) or [rgb]
                    except Exception:
                        card_images = [img_path]

                for card_idx, card in enumerate(card_images, start=1):
                    extracted = ""
                    error = ""
                    jpeg_bytes = b""
                    try:
                        if isinstance(card, Path):
                            extracted = _extract_license_name(_pdf_page_text(str(pdf_file), page_idx))
                            if not extracted:
                                extracted = _extract_license_name(_ocr_text(card))
                            jpeg_bytes = _prepare_license_jpeg(card)
                        else:
                            extracted = _extract_license_name(_ocr_text_from_pil(card))
                            jpeg_bytes = _prepare_license_jpeg_from_pil(card)
                    except Exception as exc:
                        error = str(exc)

                    player, score = _best_player_match(players, extracted)
                    saved_as = ""
                    if player and score >= min_score and not dry_run and jpeg_bytes:
                        try:
                            content = ContentFile(jpeg_bytes)
                            content.name = f"license-player-{player.id}.jpg"
                            saved_as = save_player_license(player, content) or ""
                        except Exception as exc:
                            error = str(exc)
                            saved_as = ""
                    if export_root and jpeg_bytes:
                        safe_name = re.sub(r"[^a-z0-9]+", "-", _normalize_name(extracted) or "license").strip("-")
                        filename = f"page-{page_idx:02d}-card-{card_idx:02d}-{safe_name}.jpg"
                        try:
                            (export_root / filename).write_bytes(jpeg_bytes)
                        except Exception as exc:
                            error = error or str(exc)

                    results.append(
                        PageResult(
                            page=page_idx,
                            card=card_idx,
                            extracted_name=extracted,
                            player_id=int(player.id) if player else None,
                            player_name=str(player.name if player else ""),
                            score=float(score or 0.0),
                            saved_as=saved_as,
                            error=error,
                        )
                    )

        payload = [
            {
                "page": item.page,
                "card": item.card,
                "extracted_name": item.extracted_name,
                "player_id": item.player_id,
                "player_name": item.player_name,
                "score": round(item.score, 4),
                "saved_as": item.saved_as,
                "error": item.error,
            }
            for item in results
        ]
        assigned = sum(1 for item in results if item.player_id and item.score >= min_score and (dry_run or item.saved_as))
        self.stdout.write(self.style.SUCCESS(f"Procesadas {len(results)} páginas. Asignadas: {assigned}. Dry-run={dry_run}"))
        for item in results:
            self.stdout.write(
                f"- p{item.page:02d}/c{item.card:02d} score={item.score:.2f} player={item.player_name or '-'} name='{item.extracted_name or '-'}' {('saved='+item.saved_as) if item.saved_as else ''} {('ERR='+item.error) if item.error else ''}"
            )
        if out_json:
            Path(out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"JSON: {out_json}"))


def _ocr_text_from_pil(img) -> str:
    if pytesseract is None:
        return ""
    try:
        return str(pytesseract.image_to_string(img, lang="spa") or "").strip()
    except Exception:
        return ""


def _prepare_license_jpeg_from_pil(img) -> bytes:
    if Image is None:
        return b""
    rgb = img.convert("RGB")
    try:
        gray = ImageOps.grayscale(rgb) if ImageOps is not None else None
        if gray and ImageOps is not None:
            inv = ImageOps.invert(gray)
            bbox = inv.getbbox()
            if bbox:
                left, top, right, bottom = bbox
                pad = 18
                left = max(0, left - pad)
                top = max(0, top - pad)
                right = min(rgb.width, right + pad)
                bottom = min(rgb.height, bottom + pad)
                rgb = rgb.crop((left, top, right, bottom))
    except Exception:
        pass
    rgb.thumbnail((1500, 1000))
    import io

    buffer = io.BytesIO()
    rgb.save(buffer, format="JPEG", optimize=True, quality=78)
    return buffer.getvalue()


def _split_vertical_cards(rgb):
    """
    Detecta bloques verticales de contenido (p.ej. 4 licencias apiladas en una página).
    """
    if ImageOps is None:
        return [rgb]
    w, h = rgb.size
    gray = ImageOps.grayscale(rgb)
    inv = ImageOps.invert(gray)
    # Muestreo rápido: si en una fila hay algún píxel "oscuro" lo consideramos contenido.
    px = inv.load()
    step_x = 10 if w > 1200 else 6
    threshold = 18
    has = [False] * h
    for y in range(h):
        row_has = False
        for x in range(0, w, step_x):
            if px[x, y] > threshold:
                row_has = True
                break
        has[y] = row_has
    segments = []
    start = None
    for y, flag in enumerate(has):
        if flag and start is None:
            start = y
        if not flag and start is not None:
            end = y
            if end - start > max(160, int(h * 0.12)):
                segments.append((start, end))
            start = None
    if start is not None:
        end = h
        if end - start > max(160, int(h * 0.12)):
            segments.append((start, end))

    # Si no detecta múltiples, devuelve None para no forzar.
    if len(segments) <= 1:
        return []
    cards = []
    for top, bottom in segments:
        crop = rgb.crop((0, top, w, bottom))
        # Recorte horizontal adicional por bbox.
        try:
            g2 = ImageOps.grayscale(crop)
            inv2 = ImageOps.invert(g2)
            bbox = inv2.getbbox()
            if bbox:
                l, t, r, b = bbox
                pad = 14
                l = max(0, l - pad)
                t = max(0, t - pad)
                r = min(crop.width, r + pad)
                b = min(crop.height, b + pad)
                crop = crop.crop((l, t, r, b))
        except Exception:
            pass
        cards.append(crop)
    return cards
