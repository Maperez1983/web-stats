import io
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Max
from django.utils.module_loading import import_string
from django.utils import timezone

from .library_repositories import (
    INBOX_MICROCYCLE_TITLE,
    INBOX_MICROCYCLE_WEEK_END,
    INBOX_MICROCYCLE_WEEK_START,
    LIBRARY_REPOSITORY_TRADITIONAL,
)
from .models import SessionTask, TrainingMicrocycle
from .session_plan_fields import serialize_session_plan_fields
from . import session_task_pdf_parser
from .task_library_services import (
    _split_joined_upper_token,
    analyze_preview_image_bytes,
    ensure_library_task_preview,
    polish_spanish_text,
    repair_joined_words_text,
)

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def _views_func(name):
    return import_string(f'football.views.{name}')


def apply_analysis_to_task(*args, **kwargs):
    return session_task_pdf_parser._apply_analysis_to_task(*args, **kwargs)


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
    previews = render_pdf_previews_with_pdftoppm(pdf_file, max_images=1)
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


def render_pdf_previews_with_pdftoppm(pdf_file, max_images=1, max_pages=10, scale_to=1700):
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
        scale_to = int(scale_to or 1700)
    except Exception:
        scale_to = 1700
    scale_to = max(900, min(scale_to, 3200))
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
                            optimized.thumbnail((1700, 1200))
                            buffer = io.BytesIO()
                            optimized.save(buffer, format='JPEG', quality=82, optimize=True)
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


def extract_tasks_from_pdf_text(*args, **kwargs):
    return session_task_pdf_parser._extract_tasks_from_pdf_text(*args, **kwargs)


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


def learn_task_blueprint_from_pdf_import(*args, **kwargs):
    return _views_func('_learn_task_blueprint_from_pdf_import')(*args, **kwargs)


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


def suggest_blocks_for_session_pdf_segments(*args, **kwargs):
    return session_task_pdf_parser._suggest_blocks_for_session_pdf_segments(*args, **kwargs)


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
    return _views_func('_get_or_create_library_session_with_repository')(*args, **kwargs)


def import_library_tasks_from_pdf_advanced(*args, **kwargs):
    return _views_func('_import_library_tasks_from_pdf_advanced')(*args, **kwargs)
