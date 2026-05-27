import io
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path

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
from .task_library_services import (
    _split_joined_upper_token,
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
    return _views_func('_apply_analysis_to_task')(*args, **kwargs)


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
    return _views_func('_extract_preview_images_from_pdf')(*args, **kwargs)


def extract_tasks_from_pdf_text(*args, **kwargs):
    return _views_func('_extract_tasks_from_pdf_text')(*args, **kwargs)


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
    return _views_func('_suggest_blocks_for_session_pdf_segments')(*args, **kwargs)


def suggest_session_plan_fields_from_pdf_text(*args, **kwargs):
    return _views_func('_suggest_session_plan_fields_from_pdf_text')(*args, **kwargs)


def get_or_create_library_session_with_repository(*args, **kwargs):
    return _views_func('_get_or_create_library_session_with_repository')(*args, **kwargs)


def import_library_tasks_from_pdf_advanced(*args, **kwargs):
    return _views_func('_import_library_tasks_from_pdf_advanced')(*args, **kwargs)
