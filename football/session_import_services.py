import io
import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
import unicodedata
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from .library_repositories import (
    INBOX_MICROCYCLE_TITLE,
    INBOX_MICROCYCLE_WEEK_END,
    INBOX_MICROCYCLE_WEEK_START,
    LIBRARY_MICROCYCLE_MARKER,
    LIBRARY_REPOSITORY_AI_TRAINER,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    normalize_library_repository,
)
from .models import PdfGraphicAsset, SessionTask, TrainingMicrocycle, TrainingSession
from .session_plan_fields import serialize_session_plan_fields
from . import session_task_pdf_parser
from . import task_library_services
from .services import _parse_int
from .task_library_services import (
    _split_joined_upper_token,
    analyze_preview_image_bytes,
    ensure_library_task_preview,
    polish_spanish_text,
    repair_joined_words_text,
)

logger = logging.getLogger(__name__)

ASSISTANT_KNOWLEDGE_PDF_SUFFIXES = frozenset({'.pdf'})
ASSISTANT_KNOWLEDGE_TEXT_SUFFIXES = frozenset({'.txt', '.md'})
ASSISTANT_KNOWLEDGE_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif'})
ASSISTANT_KNOWLEDGE_SUPPORTED_SUFFIXES = (
    ASSISTANT_KNOWLEDGE_PDF_SUFFIXES
    | ASSISTANT_KNOWLEDGE_TEXT_SUFFIXES
    | ASSISTANT_KNOWLEDGE_IMAGE_SUFFIXES
)
ASSISTANT_KNOWLEDGE_SUPPORTED_LABEL = '.pdf/.txt/.md/.png/.jpg/.jpeg/.webp/.heic/.heif'

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception:  # pragma: no cover
    Image = None
    ImageFilter = None
    ImageOps = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


apply_analysis_to_task = session_task_pdf_parser._apply_analysis_to_task


def assistant_document_suffix(value) -> str:
    try:
        return Path(str(value or '')).suffix.lower()
    except Exception:
        return ''


def is_assistant_pdf_document(value, mime_type: str = '') -> bool:
    suffix = assistant_document_suffix(value)
    mime = str(mime_type or '').lower()
    return bool(suffix in ASSISTANT_KNOWLEDGE_PDF_SUFFIXES or mime == 'application/pdf')


def is_assistant_image_document(value, mime_type: str = '') -> bool:
    suffix = assistant_document_suffix(value)
    mime = str(mime_type or '').lower()
    return bool(suffix in ASSISTANT_KNOWLEDGE_IMAGE_SUFFIXES or mime.startswith('image/'))


def is_supported_assistant_document(value, *, images_only: bool = False) -> bool:
    suffix = assistant_document_suffix(value)
    if images_only:
        return suffix in ASSISTANT_KNOWLEDGE_IMAGE_SUFFIXES
    return suffix in ASSISTANT_KNOWLEDGE_SUPPORTED_SUFFIXES


def extract_pdf_text_via_pdftotext(pdf_bytes: bytes) -> str:
    if not pdf_bytes:
        return ''
    if shutil.which('pdftotext') is not None:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
            tmp.write(pdf_bytes)
            tmp.flush()
            try:
                proc = subprocess.run(
                    ['pdftotext', '-layout', '-enc', 'UTF-8', tmp.name, '-'],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=45,
                )
            except Exception:
                proc = None
            if proc and proc.returncode == 0:
                try:
                    text = (proc.stdout or b'').decode('utf-8', errors='ignore')
                except Exception:
                    text = ''
                if text and len(text.strip()) >= 40:
                    return text

    if PdfReader is None:
        return ''
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return ''
    out = []
    for page in (getattr(reader, 'pages', None) or [])[:180]:
        try:
            chunk = page.extract_text() or ''
        except Exception:
            chunk = ''
        if chunk:
            out.append(chunk)
    return '\n'.join(out).strip()


def extract_image_text_via_tesseract(image_bytes: bytes) -> str:
    if not image_bytes or Image is None or pytesseract is None:
        return ''
    img = open_pil_rgb_from_bytes(image_bytes)
    if img is None:
        return ''
    try:
        img = _prepare_image_for_ocr(img)
    except Exception:
        pass

    configs = ['--psm 6', '--psm 4']
    langs = ['spa', 'spa+eng']
    variants = _image_ocr_variants(img)
    best_text = ''
    best_score = 0
    boost_keywords = (
        'descripcion',
        'reglas',
        'consideraciones',
        'condicionantes',
        'portero',
        'finaliza',
        'remate',
        'duelo',
    )
    for var_img in variants:
        for cfg in configs:
            for lang in langs:
                try:
                    text = pytesseract.image_to_string(var_img, lang=lang, config=cfg) or ''
                except Exception:
                    text = ''
                cleaned = str(text or '').strip()
                if len(cleaned) < 40:
                    continue
                alpha = sum(1 for ch in cleaned if ch.isalpha())
                alpha_ratio = alpha / max(1, len(cleaned))
                if alpha < 25 or alpha_ratio < 0.22:
                    continue
                low = _normalize_ocr_text(cleaned)
                hits = sum(1 for keyword in boost_keywords if keyword in low)
                score = int(alpha * 2.2 + len(cleaned) * 0.35 + (hits * 420))
                if score > best_score:
                    best_score = score
                    best_text = cleaned
                if best_score >= 2200 and hits >= 2 and len(best_text) >= 400:
                    return best_text.strip()
    return best_text.strip()


def open_pil_rgb_from_bytes(image_bytes: bytes):
    if not image_bytes or Image is None:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        proc = None
        try:
            if shutil.which('magick') is not None:
                proc = subprocess.run(
                    ['magick', 'heic:-', 'png:-'],
                    input=image_bytes,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=25,
                    check=False,
                )
        except Exception:
            proc = None
        if proc and proc.returncode == 0 and proc.stdout:
            try:
                img = Image.open(io.BytesIO(proc.stdout))
            except Exception:
                return None
        else:
            return None
    try:
        if ImageOps is not None:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
        return img.convert('RGB')
    except Exception:
        return None


def _open_pil_rgb_from_bytes(image_bytes: bytes):
    return open_pil_rgb_from_bytes(image_bytes)


def _prepare_image_for_ocr(img):
    try:
        max_side = max(int(img.size[0]), int(img.size[1]))
    except Exception:
        max_side = 0
    target_side = 1800
    if max_side and max_side < target_side:
        scale = float(target_side) / float(max_side)
        new_w = max(320, int(round(img.size[0] * scale)))
        new_h = max(240, int(round(img.size[1] * scale)))
        try:
            resample = getattr(Image, 'Resampling', Image).LANCZOS
        except Exception:
            resample = getattr(Image, 'LANCZOS', 1)
        try:
            return img.resize((new_w, new_h), resample=resample)
        except Exception:
            return img
    return img


def _image_ocr_variants(img):
    variants = [img]
    if ImageOps is not None:
        try:
            gray = ImageOps.grayscale(img)
            try:
                gray = ImageOps.autocontrast(gray)
            except Exception:
                pass
            variants.append(gray)
            if ImageFilter is not None:
                try:
                    variants.append(gray.filter(ImageFilter.SHARPEN))
                except Exception:
                    pass
        except Exception:
            pass
    rotated_variants = []
    for variant in variants:
        rotated_variants.append(variant)
        try:
            rotated_variants.append(variant.rotate(90, expand=True))
            rotated_variants.append(variant.rotate(270, expand=True))
        except Exception:
            pass
    if len(rotated_variants) > 4:
        try:
            rotated_variants = rotated_variants[-4:]
        except Exception:
            pass
    return rotated_variants


def _normalize_ocr_text(value):
    raw = str(value or '')
    try:
        raw = ''.join(
            ch for ch in unicodedata.normalize('NFKD', raw)
            if unicodedata.category(ch) != 'Mn'
        )
    except Exception:
        pass
    return raw.casefold()


def extract_pdf_text(pdf_file, max_chars=12000):
    if PdfReader is None:
        raise ValueError('Falta dependencia de lectura PDF. Instala `pypdf`.')

    def _ocr_text_from_image_bytes(raw_bytes):
        if not raw_bytes or Image is None or pytesseract is None:
            return ''
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                rgb = img.convert('RGB')
                return (pytesseract.image_to_string(rgb, lang='spa+eng') or '').strip()
        except Exception:
            return ''

    def _needs_ocr_boost(parsed_text):
        compact_hits = re.findall(r'\b[A-ZÁÉÍÓÚÜÑ]{10,}\b', str(parsed_text or ''))
        joined_hits = 0
        for token in compact_hits[:120]:
            repaired = _split_joined_upper_token(token)
            if repaired == token:
                joined_hits += 1
        return len(str(parsed_text or '')) < 500 or joined_hits >= 2

    def _looks_like_broken_table_layout(parsed_text):
        try:
            lines = [ln.strip() for ln in str(parsed_text or '').splitlines() if ln.strip()]
        except Exception:
            return False
        if len(lines) < 8:
            return False
        weird_lines = 0
        for ln in lines[:220]:
            alpha_tokens = re.findall(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+', ln)
            if len(alpha_tokens) < 4:
                continue
            one_letter = sum(1 for t in alpha_tokens if len(t) == 1)
            avg_len = sum(len(t) for t in alpha_tokens) / float(max(1, len(alpha_tokens)))
            if one_letter >= 3 and avg_len < 2.3:
                weird_lines += 1
        return weird_lines >= 2

    def _ocr_pdf_pages_with_pdftoppm(local_pdf_file, max_pages=4):
        if pytesseract is None or Image is None:
            return ''
        pdftoppm_bin = shutil.which('pdftoppm')
        if not pdftoppm_bin:
            return ''
        try:
            if hasattr(local_pdf_file, 'seek'):
                local_pdf_file.seek(0)
            pdf_bytes = local_pdf_file.read()
            if not pdf_bytes:
                return ''
            with tempfile.TemporaryDirectory(prefix='task-ocr-') as tmpdir:
                tmp_path = Path(tmpdir)
                source_pdf = tmp_path / 'source.pdf'
                source_pdf.write_bytes(pdf_bytes)
                ocr_chunks = []
                page_limit = max(1, int(max_pages or 1))
                for page_no in range(1, page_limit + 1):
                    out_base = tmp_path / f'page-{page_no}'
                    subprocess.run(
                        [
                            pdftoppm_bin,
                            '-jpeg',
                            '-r',
                            '170',
                            '-f',
                            str(page_no),
                            '-singlefile',
                            str(source_pdf),
                            str(out_base),
                        ],
                        check=True,
                        capture_output=True,
                        timeout=35,
                    )
                    page_img = tmp_path / f'page-{page_no}.jpg'
                    if not page_img.exists():
                        continue
                    raw = page_img.read_bytes()
                    ocr_text = _ocr_text_from_image_bytes(raw)
                    if ocr_text:
                        ocr_chunks.append(ocr_text)
                    if sum(len(c) for c in ocr_chunks) >= 9000:
                        break
                return '\n'.join(ocr_chunks).strip()
        except Exception:
            return ''

    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else b''
        if not pdf_bytes:
            raise ValueError('PDF vacío.')

        text = str(extract_pdf_text_via_pdftotext(pdf_bytes) or '').strip()
        if _looks_like_broken_table_layout(text):
            reader = PdfReader(io.BytesIO(pdf_bytes))
            chunks = []
            for page in reader.pages:
                chunks.append((page.extract_text() or '').strip())
            text = '\n'.join([item for item in chunks if item]).strip()
        text = re.sub(r'\n{3,}', '\n\n', text)
        if len(text) < 180:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            ocr_chunks = []
            for page in reader.pages[:5]:
                images = getattr(page, 'images', []) or []
                for image in images[:3]:
                    image_bytes = getattr(image, 'data', b'') or b''
                    ocr_text = _ocr_text_from_image_bytes(image_bytes)
                    if ocr_text:
                        ocr_chunks.append(ocr_text)
                if sum(len(c) for c in ocr_chunks) >= 5000:
                    break
            if ocr_chunks:
                text = '\n'.join([text, '\n'.join(ocr_chunks)]).strip() if text else '\n'.join(ocr_chunks)
                text = re.sub(r'\n{3,}', '\n\n', text)
        if _needs_ocr_boost(text):
            ocr_rendered = _ocr_pdf_pages_with_pdftoppm(io.BytesIO(pdf_bytes), max_pages=5)
            if ocr_rendered:
                merged = '\n'.join([text, ocr_rendered]).strip() if text else ocr_rendered
                text = re.sub(r'\n{3,}', '\n\n', merged)
        text = polish_spanish_text(repair_joined_words_text(text), multiline=True)
        return text[:max_chars]
    except Exception:
        raise ValueError('No se pudo leer el PDF. Verifica que no esté protegido o corrupto.')


def extract_preview_images_from_pdf(*args, **kwargs):
    pdf_file = args[0] if args else kwargs.get('pdf_file')
    max_images = kwargs.get('max_images', args[1] if len(args) > 1 else 8)
    prefer_render = kwargs.get('prefer_render', args[2] if len(args) > 2 else False)
    if pdf_file is None:
        return []
    try:
        max_images_int = max(1, int(max_images or 1))
    except Exception:
        max_images_int = 1
    should_render_first = bool(prefer_render) or (max_images_int > 1)
    if should_render_first:
        rendered_payloads = render_pdf_previews_with_pdftoppm(
            pdf_file,
            max_images=max_images_int,
            max_pages=10,
            scale_to=3000,
        )
        if rendered_payloads:
            return rendered_payloads

    payloads = []
    candidates = []
    if PdfReader is not None:
        try:
            if hasattr(pdf_file, 'seek'):
                pdf_file.seek(0)
            reader = PdfReader(pdf_file)
            seq = 0
            for page_idx, page in enumerate(reader.pages):
                images = getattr(page, 'images', []) or []
                for image in images:
                    seq += 1
                    raw = getattr(image, 'data', b'') or b''
                    if not raw:
                        continue
                    ext = str(getattr(image, 'name', 'img.bin') or 'img.bin').rsplit('.', 1)[-1].lower()
                    if ext not in {'png', 'jpg', 'jpeg', 'webp'}:
                        ext = 'png'
                    metrics = analyze_preview_image_bytes(raw)
                    score = float(metrics.get('score') or 0.0) if metrics else 0.0
                    candidates.append(
                        {
                            'raw': raw,
                            'ext': ext,
                            'score': score,
                            'page_idx': page_idx,
                            'seq': seq,
                        }
                    )
        except Exception:
            candidates = []
    if candidates:
        max_count = max(1, int(max_images_int or 1))
        good_candidates = [item for item in candidates if float(item.get('score') or 0.0) >= 12.0]
        if good_candidates:
            selected = sorted(good_candidates, key=lambda item: (int(item.get('page_idx') or 0), int(item.get('seq') or 0)))
        else:
            selected = sorted(candidates, key=lambda item: float(item.get('score') or 0.0), reverse=True)
        for item in selected[:max_count]:
            ext = str(item.get('ext') or 'jpg')
            filename = f'task-preview-{uuid.uuid4().hex[:10]}.{ext}'
            payloads.append((filename, ContentFile(item.get('raw') or b'')))
        if payloads:
            return payloads
    if payloads:
        return payloads

    fallback_payloads = render_pdf_previews_with_pdftoppm(pdf_file, max_images=max_images_int)
    if fallback_payloads:
        return fallback_payloads

    default_payload = default_task_preview_payload()
    if default_payload:
        return [default_payload]
    return payloads


def extract_preview_image_from_pdf(pdf_file, prefer_render=False):
    payloads = extract_preview_images_from_pdf(pdf_file, max_images=1, prefer_render=prefer_render)
    return payloads[0] if payloads else None


def render_pdf_preview_with_pdftoppm(pdf_file):
    previews = render_pdf_previews_with_pdftoppm(pdf_file, max_images=1, scale_to=3200)
    return previews[0] if previews else None


def split_board_page_image_bytes(raw_bytes, max_images=3):
    if not raw_bytes or Image is None:
        return []
    try:
        max_images = max(1, int(max_images or 1))
    except Exception:
        max_images = 3
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img = img.convert('RGB')
            w0, h0 = img.size
            if w0 <= 0 or h0 <= 0:
                return []
            probe_max = 420
            probe_scale = min(1.0, float(probe_max) / float(max(w0, h0)))
            probe = img
            if probe_scale < 1.0:
                probe = img.resize(
                    (max(1, int(round(w0 * probe_scale))), max(1, int(round(h0 * probe_scale)))),
                    Image.BILINEAR,
                )
            w, h = probe.size
            px = probe.load()
            visited = bytearray(w * h)

            def is_green(r, g, b):
                return g > 70 and g > r + 14 and g > b + 14

            components = []
            for y in range(h):
                row = y * w
                for x in range(w):
                    idx = row + x
                    if visited[idx]:
                        continue
                    r, g, b = px[x, y]
                    if not is_green(r, g, b):
                        continue
                    stack = [idx]
                    visited[idx] = 1
                    minx = maxx = x
                    miny = maxy = y
                    count = 0
                    while stack:
                        cur = stack.pop()
                        cy, cx = divmod(cur, w)
                        rr, gg, bb = px[cx, cy]
                        if not is_green(rr, gg, bb):
                            continue
                        count += 1
                        if cx < minx:
                            minx = cx
                        if cx > maxx:
                            maxx = cx
                        if cy < miny:
                            miny = cy
                        if cy > maxy:
                            maxy = cy
                        if cx > 0:
                            n = cur - 1
                            if not visited[n]:
                                visited[n] = 1
                                stack.append(n)
                        if cx + 1 < w:
                            n = cur + 1
                            if not visited[n]:
                                visited[n] = 1
                                stack.append(n)
                        if cy > 0:
                            n = cur - w
                            if not visited[n]:
                                visited[n] = 1
                                stack.append(n)
                        if cy + 1 < h:
                            n = cur + w
                            if not visited[n]:
                                visited[n] = 1
                                stack.append(n)
                    bw = maxx - minx + 1
                    bh = maxy - miny + 1
                    area = bw * bh
                    if count < 80 or area < int(0.012 * float(w * h)):
                        continue
                    aspect = float(bw) / float(max(1, bh))
                    if aspect < 0.22 or aspect > 4.2:
                        continue
                    components.append({'minx': minx, 'miny': miny, 'maxx': maxx, 'maxy': maxy, 'area': area})

            if not components:
                return []
            if len(components) < 2 and max_images > 1:
                return []
            components.sort(key=lambda c: (int(c['miny']), int(c['minx'])))
            components = sorted(components, key=lambda c: int(c['area']), reverse=True)[: max_images * 2]
            components.sort(key=lambda c: (int(c['miny']), int(c['minx'])))

            pad = int(round(0.02 * float(max(w, h))))
            sx = 1.0 / probe_scale
            crops = []
            for comp in components[:max_images]:
                minx = max(0, int((comp['minx'] - pad) * sx))
                miny = max(0, int((comp['miny'] - pad) * sx))
                maxx = min(w0, int((comp['maxx'] + 1 + pad) * sx))
                maxy = min(h0, int((comp['maxy'] + 1 + pad) * sx))
                if maxx <= minx + 40 or maxy <= miny + 40:
                    continue
                crop = img.crop((minx, miny, maxx, maxy))
                buf = io.BytesIO()
                crop.save(buf, format='JPEG', quality=86, optimize=True)
                crops.append(buf.getvalue())
            return crops
    except Exception:
        return []


def render_pdf_previews_with_pdftoppm(pdf_file, max_images=1, max_pages=10, scale_to=3200):
    if pdf_file is None:
        return []
    pdftoppm_bin = shutil.which('pdftoppm')
    if not pdftoppm_bin:
        return []
    try:
        max_images = max(1, int(max_images or 1))
    except Exception:
        max_images = 1
    try:
        max_pages = max(1, int(max_pages or 1))
    except Exception:
        max_pages = 10
    try:
        scale_to = int(scale_to or 3200)
    except Exception:
        scale_to = 3200
    scale_to = max(900, min(scale_to, 4096))
    try:
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return []
        with tempfile.TemporaryDirectory(prefix='task-preview-') as tmpdir:
            tmp_path = Path(tmpdir)
            source_pdf = tmp_path / 'source.pdf'
            output_base = tmp_path / 'preview'
            source_pdf.write_bytes(pdf_bytes)
            subprocess.run(
                [
                    pdftoppm_bin,
                    '-jpeg',
                    '-f',
                    '1',
                    '-l',
                    str(max_pages),
                    '-scale-to',
                    str(scale_to),
                    str(source_pdf),
                    str(output_base),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            rendered = []
            for page_idx in range(1, max_pages + 1):
                candidate_path = tmp_path / f'preview-{page_idx}.jpg'
                if not candidate_path.exists():
                    continue
                raw = candidate_path.read_bytes()
                if not raw:
                    continue
                metrics = analyze_preview_image_bytes(raw) or {}
                score = float(metrics.get('score') or 0.0)
                green_ratio = float(metrics.get('green_ratio') or 0.0)
                white_ratio = float(metrics.get('white_ratio') or 0.0)
                rendered.append(
                    {
                        'page_idx': page_idx,
                        'raw': raw,
                        'score': score,
                        'green_ratio': green_ratio,
                        'white_ratio': white_ratio,
                    }
                )
            if not rendered:
                return []

            board_pages = [
                item
                for item in rendered
                if float(item.get('green_ratio') or 0.0) >= 0.06
                and float(item.get('white_ratio') or 0.0) <= 0.82
                and float(item.get('score') or 0.0) >= 16.0
            ]
            if board_pages:
                selected = sorted(board_pages, key=lambda item: int(item.get('page_idx') or 0))
            else:
                good = [item for item in rendered if float(item.get('score') or 0.0) >= 12.0]
                if good:
                    selected = sorted(good, key=lambda item: int(item.get('page_idx') or 0))
                else:
                    selected = sorted(rendered, key=lambda item: float(item.get('score') or 0.0), reverse=True)

            if max_images > 1 and selected:
                expanded = []
                for item in selected:
                    remaining = max_images - len(expanded)
                    if remaining <= 0:
                        break
                    raw = item.get('raw') or b''
                    page_idx = int(item.get('page_idx') or 1)
                    if remaining > 1:
                        split = split_board_page_image_bytes(raw, max_images=min(remaining, 6))
                        if split and len(split) > 1:
                            for chunk in split[:remaining]:
                                expanded.append({'page_idx': page_idx, 'raw': chunk, 'score': 0.0})
                            continue
                    crop = split_board_page_image_bytes(raw, max_images=1)
                    if crop:
                        raw = crop[0]
                    expanded.append({'page_idx': page_idx, 'raw': raw, 'score': float(item.get('score') or 0.0)})
                if expanded:
                    selected = expanded

            payloads = []
            for item in selected[:max_images]:
                raw = item.get('raw') or b''
                if Image is not None and raw:
                    try:
                        with Image.open(io.BytesIO(raw)) as img:
                            optimized = img.convert('RGB')
                            optimized.thumbnail((3200, 2400))
                            buffer = io.BytesIO()
                            optimized.save(buffer, format='JPEG', quality=90, optimize=True)
                            raw = buffer.getvalue()
                    except Exception:
                        pass
                filename = f'task-preview-{uuid.uuid4().hex[:10]}.jpg'
                payloads.append((filename, ContentFile(raw)))
            return payloads
    except Exception:
        return []


def default_task_preview_payload():
    try:
        fallback_candidates = [
            Path(settings.BASE_DIR) / 'static' / 'football' / 'campo-futbol-fallback.jpg',
            Path(settings.BASE_DIR) / 'static' / 'football' / 'campo-futbol.jpg',
        ]
        fallback_path = next((p for p in fallback_candidates if p.exists() and p.is_file()), None)
        if not fallback_path:
            return None
        raw = fallback_path.read_bytes()
        if Image is not None:
            try:
                with Image.open(io.BytesIO(raw)) as img:
                    normalized = img.convert('RGB')
                    normalized.thumbnail((1200, 850))
                    buffer = io.BytesIO()
                    normalized.save(buffer, format='JPEG', quality=74, optimize=True)
                    raw = buffer.getvalue()
            except Exception:
                pass
        filename = f'task-preview-{uuid.uuid4().hex[:10]}.jpg'
        return filename, ContentFile(raw)
    except Exception:
        return None


def extract_pdf_graphic_assets_from_pdf(pdf_file, max_assets=60):
    if PdfReader is None or pdf_file is None:
        return []
    try:
        limit = max(1, min(int(max_assets or 1), 240))
    except Exception:
        limit = 60
    if hasattr(pdf_file, 'seek'):
        try:
            pdf_file.seek(0)
        except Exception:
            pass
    try:
        reader = PdfReader(pdf_file)
    except Exception:
        return []
    seen = set()
    assets = []
    seq = 0
    for page_idx, page in enumerate(reader.pages):
        images = getattr(page, 'images', []) or []
        for image in images:
            seq += 1
            raw = getattr(image, 'data', b'') or b''
            if not raw or len(raw) < 512:
                continue
            sha = hashlib.sha256(raw).hexdigest()
            if sha in seen:
                continue
            seen.add(sha)
            ext = str(getattr(image, 'name', 'img.bin') or 'img.bin').rsplit('.', 1)[-1].lower()
            name_hint = str(getattr(image, 'name', '') or '').rsplit('/', 1)[-1]
            if ext not in {'png', 'jpg', 'jpeg', 'webp'}:
                ext = 'png'
            metrics = analyze_preview_image_bytes(raw)
            if metrics:
                width = int(metrics.get('width') or 0)
                height = int(metrics.get('height') or 0)
                area = int(metrics.get('area') or 0)
                green_ratio = float(metrics.get('green_ratio') or 0.0)
                white_ratio = float(metrics.get('white_ratio') or 0.0)
                if width <= 0 or height <= 0:
                    continue
                if area < 18 * 18:
                    continue
                if max(width, height) > 1200 or area > (1200 * 1200):
                    continue
                if green_ratio > 0.22 and area > (520 * 380) and white_ratio < 0.55:
                    continue
            assets.append(
                {
                    'sha256': sha,
                    'raw': raw,
                    'ext': ext,
                    'name_hint': name_hint,
                    'page_idx': page_idx,
                    'seq': seq,
                    'width': int(metrics.get('width') or 0) if metrics else 0,
                    'height': int(metrics.get('height') or 0) if metrics else 0,
                }
            )
            if len(assets) >= limit:
                return assets
    return assets


def save_pdf_graphic_assets_to_library(*, team=None, owner=None, pdf_file=None, source_pdf_name='', max_assets=60):
    if not pdf_file:
        return {'saved': 0, 'skipped': 0, 'errors': 0}
    if not team and not owner:
        return {'saved': 0, 'skipped': 0, 'errors': 0}
    extracted = extract_pdf_graphic_assets_from_pdf(pdf_file, max_assets=max_assets)
    if not extracted:
        return {'saved': 0, 'skipped': 0, 'errors': 0}
    saved = 0
    skipped = 0
    errors = 0
    for item in extracted:
        sha = str(item.get('sha256') or '').strip()
        if not sha:
            continue
        ext = str(item.get('ext') or 'png').lower().strip() or 'png'
        name_hint = str(item.get('name_hint') or '').strip()
        raw = item.get('raw') or b''
        if not raw:
            continue
        filename = f'pdf-asset-{sha[:16]}.{ext if ext != "jpeg" else "jpg"}'
        embedded = ''
        try:
            embedded = task_library_services.build_embedded_preview_data_url(raw, max_w=1100, max_h=1100)
            obj = PdfGraphicAsset(
                team=team,
                owner=owner,
                sha256=sha,
                title=(Path(name_hint).stem if name_hint else '')[:160],
                source_pdf_name=str(source_pdf_name or '')[:220],
                embedded_data_url=embedded,
                width=int(item.get('width') or 0) or None,
                height=int(item.get('height') or 0) or None,
            )
            obj.file.save(filename, ContentFile(raw), save=False)
            obj.save()
            saved += 1
        except Exception:
            try:
                existing = PdfGraphicAsset.objects.filter(sha256=sha)
                if team:
                    existing = existing.filter(team=team)
                if owner:
                    existing = existing.filter(owner=owner)
                if existing.exists():
                    try:
                        if embedded and existing.filter(embedded_data_url='').exists():
                            existing.filter(embedded_data_url='').update(embedded_data_url=embedded)
                    except Exception:
                        pass
                    skipped += 1
                    continue
            except Exception:
                pass
            errors += 1
    return {'saved': saved, 'skipped': skipped, 'errors': errors}


def maybe_recreate_board_from_preview_bytes(task, preview_bytes):
    if not task or not preview_bytes or Image is None:
        return False
    try:
        portrait = False
        img_w = 0
        img_h = 0
        try:
            with Image.open(io.BytesIO(preview_bytes)) as im:
                img_w = int(getattr(im, 'width', 0) or 0)
                img_h = int(getattr(im, 'height', 0) or 0)
                portrait = bool(img_h > img_w) if img_w and img_h else False
        except Exception:
            portrait = False

        world_w = 684 if portrait else 1054
        world_h = 1054 if portrait else 684
        if img_w <= 0 or img_h <= 0:
            img_w = world_w
            img_h = world_h
        scale = min(float(world_w) / float(img_w or 1), float(world_h) / float(img_h or 1))
        try:
            scale = float(scale)
        except Exception:
            scale = 1.0
        scale = max(0.05, min(scale, 4.0))

        preview_src = ''
        try:
            preview_src = reverse('session-task-preview-file', args=[task.id])
            preview_name = str(getattr(getattr(task, 'task_preview_image', None), 'name', '') or '').strip()
            if preview_name:
                preview_src = f'{preview_src}?hd=1&v={quote(preview_name)}'
            else:
                preview_src = f"{preview_src}?hd=1&v={int(getattr(task, 'id', 0) or 0)}"
        except Exception:
            preview_src = ''
        if not preview_src:
            return False

        recreated = {
            'version': '5.3.0',
            'objects': [
                {
                    'type': 'image',
                    'left': int(round(world_w / 2)),
                    'top': int(round(world_h / 2)),
                    'originX': 'center',
                    'originY': 'center',
                    'scaleX': scale,
                    'scaleY': scale,
                    'angle': 0,
                    'opacity': 1,
                    'src': preview_src,
                    'selectable': False,
                    'evented': False,
                    'hasControls': False,
                    'hasBorders': False,
                    'objectCaching': False,
                    'data': {
                        'kind': 'pdf-background',
                        'base': True,
                        'locked': True,
                        'source': 'pdf_preview',
                    },
                }
            ],
        }
        layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        meta = dict(meta)
        meta.setdefault('pitch_preset', 'full_pitch')
        meta['pitch_orientation'] = 'portrait' if portrait else 'landscape'
        meta['graphic_editor'] = {
            'canvas_state': recreated,
            'canvas_width': world_w,
            'canvas_height': world_h,
        }
        layout['meta'] = meta
        task.tactical_layout = layout
        task.save(update_fields=['tactical_layout'])
        return True
    except Exception:
        return False


extract_tasks_from_pdf_text = session_task_pdf_parser._extract_tasks_from_pdf_text


def get_or_create_inbox_microcycle(*args, **kwargs):
    team = args[0] if args else kwargs.get('team')
    if not team:
        return None
    try:
        obj = TrainingMicrocycle.objects.filter(team=team, week_start=INBOX_MICROCYCLE_WEEK_START).first()
        if obj:
            changed = False
            if getattr(obj, 'week_end', None) != INBOX_MICROCYCLE_WEEK_END:
                obj.week_end = INBOX_MICROCYCLE_WEEK_END
                changed = True
            if str(getattr(obj, 'title', '') or '').strip() != INBOX_MICROCYCLE_TITLE:
                obj.title = INBOX_MICROCYCLE_TITLE
                changed = True
            if changed:
                try:
                    obj.save(update_fields=['title', 'week_end', 'updated_at'])
                except Exception:
                    obj.save()
            return obj
        return TrainingMicrocycle.objects.create(
            team=team,
            title=INBOX_MICROCYCLE_TITLE,
            objective='',
            week_start=INBOX_MICROCYCLE_WEEK_START,
            week_end=INBOX_MICROCYCLE_WEEK_END,
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes='(Sistema) Bandeja de sesiones sueltas.',
        )
    except Exception:
        return None


def week_bounds_for_date(value):
    if not value:
        return None, None
    try:
        weekday = int(value.weekday())
    except Exception:
        return None, None
    week_start = value - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_or_create_week_microcycle(*args, **kwargs):
    team = args[0] if args else kwargs.get('team')
    session_date = args[1] if len(args) > 1 else kwargs.get('session_date')
    title_hint = kwargs.get('title_hint', '')
    if not team or not session_date:
        return None
    week_start, week_end = week_bounds_for_date(session_date)
    if not week_start or not week_end:
        return None
    try:
        existing = TrainingMicrocycle.objects.filter(team=team, week_start=week_start).first()
        if existing:
            return existing
        return TrainingMicrocycle.objects.create(
            team=team,
            title=str(title_hint or 'Microciclo semanal').strip()[:140] or 'Microciclo semanal',
            objective='',
            week_start=week_start,
            week_end=week_end,
            status=TrainingMicrocycle.STATUS_DRAFT,
            notes='(Sistema) Microciclo creado automáticamente desde sesión importada.',
        )
    except Exception:
        return None


learn_task_blueprint_from_pdf_import = task_library_services.learn_task_blueprint_from_pdf_import


def next_session_task_order(*args, **kwargs):
    session = args[0] if args else kwargs.get('session')
    return (SessionTask.objects.filter(session=session, deleted_at__isnull=True).aggregate(Max('order')).get('order__max') or 0) + 1


def parse_pdf_session_header_fields(*args, **kwargs):
    extracted_text = args[0] if args else kwargs.get('extracted_text')
    text = str(extracted_text or '')
    if not text.strip():
        return {}
    cleaned = re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip()
    out = {}
    try:
        m = re.search(r'(?i)\bfecha\s*:\s*(\d{2}/\d{2}/\d{4})\b', cleaned)
        if m:
            out['date'] = datetime.strptime(m.group(1), '%d/%m/%Y').date()
    except Exception:
        pass
    try:
        m = re.search(r'(?i)\bhora\s*:\s*(\d{1,2})\s*[:h]\s*(\d{2})\b', cleaned)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                out['time'] = time(hh, mm)
    except Exception:
        pass
    for out_key, label in (('microcycle_number', 'micro'), ('mesocycle_number', 'meso')):
        try:
            m = re.search(rf'(?i)\b{label}[\s\-]*ciclo\s*:\s*(?:n[º°o]\s*)?0*(\d{{1,3}})\b', cleaned)
            if m:
                out[out_key] = int(m.group(1))
        except Exception:
            pass
    try:
        m = re.search(r'(?i)\bmd\s*:\s*([+\-]?\s*\d{1,2})\s*(?:n[º°o]\s*)?0*(\d{1,4})?\b', cleaned)
        if m:
            out['md'] = int(m.group(1).replace(' ', ''))
            if m.group(2):
                out['session_number'] = int(m.group(2))
    except Exception:
        pass
    try:
        m = re.search(r'(?i)\b(?:sesion|sesión)\s*(?:n[º°o]\s*)?0*(\d{1,4})\b', cleaned)
        if m:
            out['session_number'] = int(m.group(1))
    except Exception:
        pass
    return out


suggest_blocks_for_session_pdf_segments = session_task_pdf_parser._suggest_blocks_for_session_pdf_segments


def suggest_session_plan_fields_from_pdf_text(*args, **kwargs):
    extracted_text = args[0] if args else kwargs.get('extracted_text')
    imported_doc_id = kwargs.get('imported_doc_id')
    text = str(extracted_text or '').strip()
    if not text:
        fields = {'notes': ''}
        if imported_doc_id:
            fields['agenda_hidden'] = f'imported_doc_id:{int(imported_doc_id)}'
        return fields

    cleaned = polish_spanish_text(repair_joined_words_text(text), multiline=True)

    materials = ''
    try:
        match = re.search(r'(?is)material\s+de\s+entrenamiento\s*(.+?)(?:\n\s*\n|(?:tarea\s*1\b)|$)', cleaned)
        if match:
            materials = match.group(1).strip()
            materials = re.split(r'(?i)\btarea\s*1\b', materials, maxsplit=1)[0].strip()
            materials = re.sub(r'\n{3,}', '\n\n', materials).strip()
            if len(materials) > 800:
                materials = materials[:800].strip()
    except Exception:
        materials = ''

    objective = ''
    try:
        tail = cleaned
        pos = cleaned.lower().find('material de entrenamiento')
        if pos >= 0:
            tail = cleaned[pos + len('material de entrenamiento'):]
        lines = [ln.strip() for ln in tail.splitlines() if ln.strip()]
        for line in lines[:40]:
            if len(line) < 12:
                continue
            folded = session_task_pdf_parser._normalize_folded_text(line)
            if not folded:
                continue
            if any(tok in folded for tok in ('microciclo', 'mesociclo', 'fecha', 'hora', 'temporada', 'periodo', 'materialdeentrenamiento')):
                continue
            if re.search(r'\b\d{1,3}\s*(?:min|mins|minutos|[\'’`´])\b', line, re.IGNORECASE):
                objective = line[:8000].strip()
                break
    except Exception:
        objective = ''

    fields = {
        'warmup': '',
        'activation': '',
        'main': '',
        'cooldown': '',
        'objective': objective,
        'success_criteria': '',
        'rpe_target': '',
        'player_count': '',
        'location': '',
        'materials': materials,
        'absences': '',
        'agenda_hidden': cleaned[:8000].strip(),
        'notes': '',
    }
    if imported_doc_id:
        fields['agenda_hidden'] = (f'imported_doc_id:{int(imported_doc_id)}\n\n' + fields['agenda_hidden']).strip()
    return fields


def get_or_create_library_session_with_repository(*args, **kwargs):
    team = args[0] if args else kwargs.get('team')
    scope_key = args[1] if len(args) > 1 else kwargs.get('scope_key')
    repository = kwargs.get('repository', LIBRARY_REPOSITORY_TRADITIONAL)
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    scope_label = {
        'coach': 'Entrenador',
        'goalkeeper': 'Porteros',
        'fitness': 'Preparacion fisica',
    }.get(scope_key, 'Staff')
    repository = normalize_library_repository(repository, fallback=LIBRARY_REPOSITORY_TRADITIONAL)
    repo_label = {
        LIBRARY_REPOSITORY_TRADITIONAL: 'PDF',
        LIBRARY_REPOSITORY_INTERACTIVE: 'Interactiva',
        LIBRARY_REPOSITORY_AI_TRAINER: 'IA-Trainer',
    }.get(repository, 'PDF')

    microcycle, _ = TrainingMicrocycle.objects.get_or_create(
        team=team,
        week_start=week_start,
        defaults={
            'week_end': week_end,
            'title': f'Biblioteca {scope_label}',
            'objective': 'Repositorio de tareas (tradicionales, interactivas e IA-Trainer)',
            'status': TrainingMicrocycle.STATUS_DRAFT,
            'notes': f'{LIBRARY_MICROCYCLE_MARKER} Microciclo tecnico generado automaticamente para biblioteca.',
        },
    )
    try:
        notes = str(getattr(microcycle, 'notes', '') or '')
        if LIBRARY_MICROCYCLE_MARKER not in notes:
            microcycle.notes = (notes + '\n' if notes else '') + f'{LIBRARY_MICROCYCLE_MARKER}'
            microcycle.save(update_fields=['notes'])
    except Exception:
        pass
    if repository == LIBRARY_REPOSITORY_TRADITIONAL:
        legacy_focus = f'Biblioteca PDF · {scope_label}'
        legacy = TrainingSession.objects.filter(microcycle=microcycle, focus__iexact=legacy_focus).order_by('-session_date', '-id').first()
        if legacy:
            return legacy

    focus = f'Biblioteca {repo_label} · {scope_label}'
    session, _ = TrainingSession.objects.get_or_create(
        microcycle=microcycle,
        session_date=today,
        focus=focus,
        defaults={
            'duration_minutes': 90,
            'intensity': TrainingSession.INTENSITY_LOW,
            'content': 'Sesion tecnica para almacenar tareas subidas a biblioteca.',
            'order': 0,
        },
    )
    return session


def import_library_tasks_from_pdf_advanced(*args, **kwargs):
    primary_team = kwargs.get('primary_team')
    scope_key = kwargs.get('scope_key')
    target_session = kwargs.get('target_session')
    pdf_files = kwargs.get('pdf_files') or []
    title = kwargs.get('title') or ''
    objective = kwargs.get('objective') or ''
    block = kwargs.get('block')
    minutes = int(kwargs.get('minutes') or 15)
    recreate_board = bool(kwargs.get('recreate_board'))
    base_order = int(kwargs.get('base_order') or 0)

    created_count = 0
    processed_pdfs = 0
    for idx, pdf_file in enumerate(pdf_files, start=1):
        raw_name = str(getattr(pdf_file, 'name', '') or '').rsplit('/', 1)[-1]
        file_stem = raw_name.rsplit('.', 1)[0].strip() or f'Tarea PDF {idx}'
        task_title = title or file_stem
        if title and len(pdf_files) > 1:
            task_title = f'{title} · {file_stem}'

        extracted_text = ''
        try:
            extracted_text = extract_pdf_text(pdf_file, max_chars=60000)
        except Exception:
            logger.exception(
                'No se pudo extraer texto del PDF de biblioteca. pdf=%s team_id=%s scope=%s',
                raw_name,
                int(getattr(primary_team, 'id', 0) or 0) or None,
                scope_key,
            )
        parsed_tasks = extract_tasks_from_pdf_text(extracted_text, fallback_title=task_title)
        if not parsed_tasks:
            parsed_tasks = [
                {
                    'analysis': {
                        'title': task_title[:160],
                        'objective': objective[:8000],
                        'minutes': max(5, min(minutes, 90)),
                        'coaching_points': '',
                        'confrontation_rules': '',
                        'summary': '',
                        'work_contexts': [],
                        'objective_tags': [],
                        'exercise_types': [],
                        'phase_tags': [],
                        'players_count_estimate': None,
                        'players_band': '',
                        'duration_band': session_task_pdf_parser._duration_band_label(max(5, min(minutes, 90))),
                        'detected_materials': [],
                        'quality_score': 0,
                    },
                    'raw_text': '',
                    'segment_index': 1,
                    'segment_total': 1,
                }
            ]

        segment_blocks = suggest_blocks_for_session_pdf_segments(parsed_tasks, block)

        if hasattr(pdf_file, 'seek'):
            try:
                pdf_file.seek(0)
            except Exception:
                pass
        preview_payloads = extract_preview_images_from_pdf(
            pdf_file,
            max_images=max(1, len(parsed_tasks)),
            prefer_render=recreate_board,
        )
        try:
            save_pdf_graphic_assets_to_library(
                team=primary_team,
                owner=None,
                pdf_file=pdf_file,
                source_pdf_name=raw_name,
                max_assets=80,
            )
        except Exception:
            logger.exception(
                'No se pudieron guardar assets gráficos del PDF. pdf=%s team_id=%s scope=%s',
                raw_name,
                int(getattr(primary_team, 'id', 0) or 0) or None,
                scope_key,
            )

        first = parsed_tasks[0]
        first_analysis = first.get('analysis') or {}
        first_title = (first_analysis.get('title') or task_title or 'Tarea desde PDF')[:160]
        first_task = SessionTask.objects.create(
            session=target_session,
            title=first_title,
            block=(segment_blocks[0] if segment_blocks else block),
            duration_minutes=max(5, min((_parse_int(first_analysis.get('minutes')) or minutes), 90)),
            objective=((first_analysis.get('objective') or objective or '')[:8000]),
            coaching_points=(first_analysis.get('coaching_points') or ''),
            confrontation_rules=(first_analysis.get('confrontation_rules') or ''),
            tactical_layout={
                'meta': {
                    'scope': scope_key,
                    'pdf_source_name': raw_name,
                    'pdf_segment_index': first.get('segment_index') or 1,
                    'pdf_segments_total': first.get('segment_total') or 1,
                    'pdf_segment_excerpt': (first.get('raw_text') or '')[:1200],
                    'pdf_split_done': True,
                }
            },
            task_pdf=pdf_file,
            status=SessionTask.STATUS_PLANNED,
            order=base_order + created_count + 1,
            notes='Cargada desde Biblioteca PDF',
        )
        preview_bytes = b''
        if preview_payloads:
            preview_name, preview_content = preview_payloads[0]
            try:
                preview_content.seek(0)
            except Exception:
                pass
            try:
                preview_bytes = preview_content.read() or b''
            except Exception:
                preview_bytes = b''
            try:
                preview_content.seek(0)
            except Exception:
                pass
            try:
                first_task.task_preview_image.save(preview_name, preview_content, save=True)
            except Exception:
                logger.exception(
                    'No se pudo guardar preview de la primera tarea importada desde PDF. task_id=%s pdf=%s',
                    int(getattr(first_task, 'id', 0) or 0) or None,
                    raw_name,
                )
        try:
            apply_analysis_to_task(first_task, first_analysis)
        except Exception:
            logger.exception(
                'No se pudo aplicar análisis a la primera tarea importada desde PDF. task_id=%s pdf=%s',
                int(getattr(first_task, 'id', 0) or 0) or None,
                raw_name,
            )
        try:
            learn_task_blueprint_from_pdf_import(
                team=primary_team,
                task=first_task,
                analysis=first_analysis,
                scope_key=scope_key,
                actor_username='pdf_import',
            )
        except Exception:
            logger.exception(
                'No se pudo aprender blueprint de la primera tarea importada desde PDF. task_id=%s pdf=%s',
                int(getattr(first_task, 'id', 0) or 0) or None,
                raw_name,
            )
        if recreate_board and preview_bytes:
            maybe_recreate_board_from_preview_bytes(first_task, preview_bytes)
        created_count += 1
        processed_pdfs += 1

        shared_pdf_name = first_task.task_pdf.name if first_task.task_pdf else ''
        shared_preview_name = first_task.task_preview_image.name if first_task.task_preview_image else ''
        for extra in parsed_tasks[1:]:
            extra_analysis = extra.get('analysis') or {}
            extra_title = (extra_analysis.get('title') or f'{task_title} · Tarea {extra.get("segment_index") or 0}')[:160]
            segment_index = max(1, int(extra.get('segment_index') or 1))
            extra_task = SessionTask.objects.create(
                session=target_session,
                title=extra_title,
                block=(
                    segment_blocks[min(segment_index - 1, len(segment_blocks) - 1)]
                    if segment_blocks
                    else block
                ),
                duration_minutes=max(5, min((_parse_int(extra_analysis.get('minutes')) or minutes), 90)),
                objective=((extra_analysis.get('objective') or objective or '')[:8000]),
                coaching_points=(extra_analysis.get('coaching_points') or ''),
                confrontation_rules=(extra_analysis.get('confrontation_rules') or ''),
                tactical_layout={
                    'meta': {
                        'scope': scope_key,
                        'pdf_source_name': raw_name,
                        'pdf_segment_index': extra.get('segment_index') or 1,
                        'pdf_segments_total': extra.get('segment_total') or 1,
                        'pdf_segment_excerpt': (extra.get('raw_text') or '')[:1200],
                        'pdf_split_done': True,
                    }
                },
                task_pdf=shared_pdf_name or None,
                task_preview_image=shared_preview_name or None,
                status=SessionTask.STATUS_PLANNED,
                order=base_order + created_count + 1,
                notes='Extraída automáticamente desde PDF multi-tarea',
            )
            extra_preview_bytes = b''
            extra_preview_payload = None
            if preview_payloads:
                extra_preview_payload = preview_payloads[min(segment_index - 1, len(preview_payloads) - 1)]
            if extra_preview_payload:
                extra_preview_name, extra_preview_content = extra_preview_payload
                try:
                    extra_preview_content.seek(0)
                except Exception:
                    pass
                try:
                    extra_preview_bytes = extra_preview_content.read() or b''
                except Exception:
                    extra_preview_bytes = b''
                try:
                    extra_preview_content.seek(0)
                except Exception:
                    pass
                try:
                    extra_task.task_preview_image.save(extra_preview_name, extra_preview_content, save=True)
                except Exception:
                    logger.exception(
                        'No se pudo guardar preview de tarea extra importada desde PDF. task_id=%s pdf=%s segment=%s',
                        int(getattr(extra_task, 'id', 0) or 0) or None,
                        raw_name,
                        segment_index,
                    )
            elif shared_preview_name:
                extra_task.task_preview_image = shared_preview_name
                extra_task.save(update_fields=['task_preview_image'])
            try:
                apply_analysis_to_task(extra_task, extra_analysis)
            except Exception:
                logger.exception(
                    'No se pudo aplicar análisis a tarea extra importada desde PDF. task_id=%s pdf=%s segment=%s',
                    int(getattr(extra_task, 'id', 0) or 0) or None,
                    raw_name,
                    segment_index,
                )
            try:
                learn_task_blueprint_from_pdf_import(
                    team=primary_team,
                    task=extra_task,
                    analysis=extra_analysis,
                    scope_key=scope_key,
                    actor_username='pdf_import',
                )
            except Exception:
                logger.exception(
                    'No se pudo aprender blueprint de tarea extra importada desde PDF. task_id=%s pdf=%s segment=%s',
                    int(getattr(extra_task, 'id', 0) or 0) or None,
                    raw_name,
                    segment_index,
                )
            if recreate_board and extra_preview_bytes:
                maybe_recreate_board_from_preview_bytes(extra_task, extra_preview_bytes)
            created_count += 1

    feedback = (
        f'Se procesó 1 PDF y se creó 1 tarea.'
        if created_count == 1 and processed_pdfs == 1
        else f'Se procesaron {processed_pdfs} PDFs y se crearon {created_count} tareas.'
    )
    return {
        'created_count': created_count,
        'processed_pdfs': processed_pdfs,
        'feedback': feedback,
    }
