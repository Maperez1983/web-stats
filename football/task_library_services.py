import io
import re
import unicodedata

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.utils.module_loading import import_string

from .services import _parse_int

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

TASK_PDF_PARSE_VERSION = 4

TASK_JOINED_WORD_VOCAB = [
    'TAREA', 'EJERCICIO', 'SESION', 'BLOQUE', 'BLOQUES', 'PARTE', 'PRINCIPAL',
    'DESCRIPCION', 'OBJETIVO', 'CONSIGNAS', 'REGLAS', 'DOSIFICACION',
    'TIEMPO', 'TOTAL', 'TRABAJO', 'PAUSA', 'SERIE', 'SERIES', 'REPETICIONES',
    'JUGADORES', 'COMODIN', 'COMODINES', 'MATERIAL', 'MATERIALES',
    'PETO', 'PETOS', 'ROJO', 'ROJOS', 'AMARILLO', 'AMARILLOS', 'AZUL', 'AZULES',
    'VERDE', 'VERDES', 'BANDA', 'BANDAS', 'FIT', 'VALLA', 'VALLAS', 'PICA',
    'PICAS', 'ARO', 'AROS', 'ESCALERA', 'ESCALERAS', 'MINIPORTERIA',
    'MINIPORTERIAS', 'PESA', 'PESAS', 'PORTERIA', 'PORTERIAS', 'PORTERO',
    'PORTEROS', 'MOVIL', 'BALON', 'CONO', 'ARCO', 'PRECISION', 'FINALIZACION',
    'DUELO', 'DUELOS', 'AEREOS', 'AEREO', 'TRANSICION', 'DEFENSA', 'ATAQUE',
    'OFENSIVA', 'DEFENSIVA', 'CAMPO', 'MEDIO', 'ZONA', 'ESPACIO', 'MEDIDAS',
    'FRENTE', 'ORIENTADOS', 'TRABAJAMOS', 'TRABAJAR', 'GENERA', 'GENERAMOS',
    'HACEMOS', 'DONDE', 'CUANDO', 'CON', 'SIN', 'PARA', 'POR', 'DEL', 'AL',
    'LA', 'EL', 'LOS', 'LAS', 'UN', 'UNA', 'UNO', 'Y', 'DE', 'EN', 'SALIR',
    'SALE', 'SE', 'QUE', 'YA', 'VEZ', 'MAS', 'CAIDA', 'DESPEJE', 'ORIENTADO',
    'INFERIORIDAD', 'SUPERIORIDAD', 'REACCION', 'PRESION', 'RECUPERACION',
    'PASE', 'APOYO', 'PAREDES', 'RAPIDO', 'JUEGO', 'DIRECTO', 'CAIDAS',
    'DESMARQUE', 'RUPTURA', 'DELIMITADA', 'HIDRATACION', 'ENTRENAMIENTO',
    'MOVILIDAD', 'ACTIVACION', 'DEFENDER', 'INCIDIMOS', 'PERDIDA',
    'TRABAJADOS', 'EQUIPOS', 'PREMISAS', 'FOMENTAR', 'FUERA',
]

TASK_JOINED_WORD_VOCAB_ES = [
    'a', 'al', 'algo', 'algunos', 'ante', 'antes', 'asi', 'aun', 'bajo',
    'bien', 'cada', 'cambio', 'casi', 'como', 'con', 'contra', 'cuando',
    'de', 'del', 'desde', 'donde', 'dos', 'durante', 'e', 'el', 'ella',
    'ellas', 'ellos', 'en', 'entre', 'era', 'es', 'esa', 'ese', 'eso',
    'esta', 'estaba', 'estado', 'estan', 'estar', 'este', 'esto', 'final',
    'frente', 'fue', 'ha', 'hacia', 'hasta', 'hay', 'hacer', 'hacemos',
    'igual', 'la', 'las', 'le', 'les', 'lo', 'los', 'mas', 'media', 'medio',
    'mientras', 'misma', 'mismo', 'muy', 'nada', 'ni', 'no', 'nos',
    'nosotros', 'o', 'otra', 'otro', 'para', 'pero', 'poca', 'poco', 'por',
    'porque', 'primera', 'primero', 'puede', 'que', 'quien', 'rapido', 'se',
    'segun', 'si', 'sin', 'sobre', 'solo', 'su', 'sus', 'te', 'todo',
    'trabajo', 'tras', 'tu', 'un', 'una', 'uno', 'unos', 'ya', 'y',
]

from .library_repositories import (
    LIBRARY_MICROCYCLE_MARKER,
    LIBRARY_REPOSITORY_AI_TRAINER,
    LIBRARY_REPOSITORY_CHOICES,
    LIBRARY_REPOSITORY_INTERACTIVE,
    LIBRARY_REPOSITORY_TRADITIONAL,
    library_repository_for_task,
    normalize_library_repository,
)


def _views_func(name):
    return import_string(f'football.views.{name}')


def _normalize_upper_compact(value):
    raw = str(value or '').strip().upper()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    stripped = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z]+', '', stripped)


def _normalize_lower_compact(value):
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    stripped = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'[^a-z]+', '', stripped)


JOINED_WORD_MAP = {
    _normalize_upper_compact(word): str(word).upper()
    for word in TASK_JOINED_WORD_VOCAB
    if _normalize_upper_compact(word)
}

JOINED_WORD_MAP_LOWER = {}
for _word in (TASK_JOINED_WORD_VOCAB + TASK_JOINED_WORD_VOCAB_ES):
    _compact = _normalize_lower_compact(_word)
    if _compact:
        JOINED_WORD_MAP_LOWER[_compact] = _compact


def _split_joined_upper_token(token):
    compact = _normalize_upper_compact(token)
    if len(compact) < 10:
        return token
    n = len(compact)
    best = [None] * (n + 1)
    best[0] = (0, [])
    max_len = min(18, n)
    for i in range(n):
        if best[i] is None:
            continue
        base_score, base_words = best[i]
        for step in range(1, max_len + 1):
            j = i + step
            if j > n:
                break
            mapped = JOINED_WORD_MAP.get(compact[i:j])
            if not mapped:
                continue
            bonus = (step * step) + (4 if step >= 4 else 0)
            candidate = (base_score + bonus, base_words + [mapped])
            if best[j] is None or candidate[0] > best[j][0]:
                best[j] = candidate
    if best[n] is None or len(best[n][1]) < 2:
        return token
    words = best[n][1]
    if len(words) >= 7 and (len(compact) / max(1, len(words))) < 2.2:
        return token
    return ' '.join(words).strip() or token


def _split_joined_alpha_token(token):
    compact = _normalize_lower_compact(token)
    if len(compact) < 8:
        return token
    n = len(compact)
    best = [None] * (n + 1)
    best[0] = (0, [])
    max_len = min(20, n)
    for i in range(n):
        if best[i] is None:
            continue
        base_score, base_words = best[i]
        for step in range(1, max_len + 1):
            j = i + step
            if j > n:
                break
            mapped = JOINED_WORD_MAP_LOWER.get(compact[i:j])
            if not mapped:
                continue
            bonus = (step * step) + (6 if step >= 4 else 0) + (4 if step >= 6 else 0)
            candidate = (base_score + bonus, base_words + [mapped])
            if best[j] is None or candidate[0] > best[j][0]:
                best[j] = candidate
    if best[n] is None or len(best[n][1]) < 2:
        return token
    words = best[n][1]
    avg_len = len(compact) / max(1, len(words))
    if len(words) >= 8 and avg_len < 2.1:
        return token
    if avg_len < 2.5 and len(words) > 5:
        return token
    if str(token).isupper():
        return ' '.join(word.upper() for word in words).strip()
    if str(token)[:1].isupper():
        joined = ' '.join(words).strip()
        return joined[:1].upper() + joined[1:]
    return ' '.join(words).strip()


def repair_joined_words_text(value):
    text = str(value or '')
    if not text:
        return ''
    cleaned = text.replace('\r\n', '\n').replace('\r', '\n')
    try:
        raw_lines = cleaned.split('\n')
        repaired_lines = []
        short_piece = re.compile(r'^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{1,3}$')
        for raw in raw_lines:
            piece = str(raw or '').strip()
            if repaired_lines and piece and short_piece.match(piece):
                prev_stripped = str(repaired_lines[-1] or '').rstrip()
                allow_join = False
                if prev_stripped and prev_stripped[-1:].isalpha():
                    if len(piece) == 1:
                        allow_join = True
                    elif (' ' not in prev_stripped) and (len(prev_stripped) <= 14):
                        allow_join = True
                    else:
                        tail = prev_stripped.split()[-1] if prev_stripped.split() else ''
                        if tail and tail.isalpha() and len(tail) <= 6:
                            allow_join = True
                if allow_join:
                    repaired_lines[-1] = prev_stripped + piece
                    continue
            repaired_lines.append(raw)
        cleaned = '\n'.join(repaired_lines)
    except Exception:
        pass
    cleaned = re.sub(
        r'(?<=[a-záéíóúüñ])([A-ZÁÉÍÓÚÜÑ])(?=[a-záéíóúüñ])',
        lambda m: m.group(1).lower(),
        cleaned,
    )
    cleaned = re.sub(r'(?<=\d)(?=[A-Za-zÁÉÍÓÚÜÑ])', ' ', cleaned)
    cleaned = re.sub(r'(?<=[A-Za-zÁÉÍÓÚÜÑ])(?=\d)', ' ', cleaned)
    cleaned = re.sub(r'(?<=\d)\s*[xX×]\s*(?=\d)', ' x ', cleaned)
    cleaned = re.sub(r'([,:;])(?=\S)', r'\1 ', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = re.sub(r' *\n *', '\n', cleaned)
    cleaned = re.sub(r'\b[A-ZÁÉÍÓÚÜÑ]{10,}\b', lambda m: _split_joined_upper_token(m.group(0)), cleaned)
    cleaned = re.sub(r'\b[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{8,}\b', lambda m: _split_joined_alpha_token(m.group(0)), cleaned)
    cleaned = re.sub(r'([\.!?])(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])', r'\1 ', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = re.sub(r' *\n *', '\n', cleaned)
    return cleaned.strip()


def polish_spanish_text(value, multiline=True, max_len=None):
    text = str(value or '')
    if not text:
        return ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('’', "'").replace('`', "'")
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)
    text = re.sub(r'([,.;:!?])(?=[^\s\n])', r'\1 ', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r' *\n *', '\n', text)
    if not multiline:
        text = text.replace('\n', ' ')
    acronym_words = {
        'ABP', 'RPE', 'GPS', 'TRX', 'MD', 'SSG', 'UEFA',
        '1V1', '2V2', '3V3', '4V4', '5V5', '6V6', '7V7', '8V8', '9V9', '11V11',
    }
    polished_lines = []
    for line in [ln.strip() for ln in text.split('\n')]:
        if not line:
            continue
        bullet_prefix = ''
        bullet_match = re.match(r'^([\-•\*]\s+)', line)
        if bullet_match:
            bullet_prefix = bullet_match.group(1)
            line = line[len(bullet_prefix):].strip()
        if len(line) >= 10 and line.isupper():
            fixed = []
            for idx, token in enumerate(line.lower().split()):
                upper_token = token.upper()
                if upper_token in acronym_words:
                    fixed.append(upper_token)
                elif idx == 0:
                    fixed.append(token.capitalize())
                else:
                    fixed.append(token)
            line = ' '.join(fixed)
        line = re.sub(r'([.!?])([A-Za-zÁÉÍÓÚÜÑáéíóúüñ])', r'\1 \2', line)
        line = line[:1].upper() + line[1:] if line else line
        polished_lines.append(f'{bullet_prefix}{line}'.strip())
    result = '\n'.join(polished_lines).strip()
    if max_len:
        result = result[:int(max_len)]
    return result


def sanitize_task_text(value, multiline=True, max_len=None):
    return polish_spanish_text(
        repair_joined_words_text(value),
        multiline=multiline,
        max_len=max_len,
    )


def task_scope_for_item(task):
    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    scope = str(meta.get('scope') or '').strip()
    return scope or 'coach'


def task_preview_needs_refresh(task):
    if not task:
        return False
    preview_name = str(getattr(task, 'task_preview_image', '') or '').strip()
    if not preview_name:
        return True
    try:
        if not default_storage.exists(preview_name):
            return True
    except Exception:
        return True
    cache_key = f'football:preview-quality:{preview_name}'
    cached = cache.get(cache_key)
    if cached is not None:
        return bool(cached)
    try:
        with default_storage.open(preview_name, 'rb') as handle:
            raw = handle.read()
        needs_refresh = is_preview_quality_low(raw)
    except Exception:
        needs_refresh = True
    cache.set(cache_key, bool(needs_refresh), 60 * 60 * 6)
    return bool(needs_refresh)


def is_preview_quality_low(raw_bytes):
    metrics = analyze_preview_image_bytes(raw_bytes)
    if not metrics:
        return False
    score = float(metrics.get('score') or 0.0)
    area = int(metrics.get('area') or 0)
    white_ratio = float(metrics.get('white_ratio') or 0.0)
    green_ratio = float(metrics.get('green_ratio') or 0.0)
    if area < 260 * 170:
        return True
    if score < 10.0:
        return True
    if white_ratio > 0.72 and green_ratio < 0.08:
        return True
    return False


def task_analysis_needs_refresh(task):
    if not task or not getattr(task, 'task_pdf', None):
        return False
    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    parser_version = _parse_int(analysis_meta.get('parser_version')) or 0
    if parser_version < TASK_PDF_PARSE_VERSION:
        return True
    summary = str(analysis_meta.get('summary') or '')
    if text_has_quality_issues(summary):
        return True
    if text_has_quality_issues(str(getattr(task, 'title', '') or '')):
        return True
    if text_has_quality_issues(str(getattr(task, 'objective', '') or '')):
        return True
    return False


def text_has_quality_issues(value):
    text = str(value or '').strip()
    if not text:
        return False
    if re.search(r'\b[A-ZÁÉÍÓÚÜÑ]{12,}\b', text):
        return True
    if re.search(r'[,;:](\S)', text):
        return True
    if re.search(r'\s{2,}', text):
        return True
    if len(text) >= 8 and text.isupper():
        return True
    return False


def ensure_library_task_preview(task, force=False, prefer_render=False):
    return _views_func('_ensure_library_task_preview')(task, force=force, prefer_render=prefer_render)


def maybe_render_task_preview_server_side(task, *, force=False):
    return _views_func('_maybe_render_task_preview_server_side')(task, force=force)


def analyze_preview_image_bytes(raw_bytes):
    if Image is None or not raw_bytes:
        return None
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            rgb = img.convert('RGB')
            width, height = rgb.size
            if width <= 0 or height <= 0:
                return None
            sample = rgb.copy()
            sample.thumbnail((128, 128))
            pixels = list(sample.getdata())
            total = max(1, len(pixels))
            greenish = 0
            whitish = 0
            darkish = 0
            colorful = 0
            for r, g, b in pixels:
                if g > 70 and g > (r + 14) and g > (b + 10):
                    greenish += 1
                if r > 232 and g > 232 and b > 232:
                    whitish += 1
                if r < 30 and g < 30 and b < 30:
                    darkish += 1
                if (max(r, g, b) - min(r, g, b)) >= 24:
                    colorful += 1
            green_ratio = greenish / total
            white_ratio = whitish / total
            dark_ratio = darkish / total
            color_ratio = colorful / total
            area = width * height
            aspect = width / max(1.0, float(height))

            score = 0.0
            score += min(area / float(1280 * 720), 2.6) * 28.0
            score += green_ratio * 46.0
            score += color_ratio * 16.0
            if 0.95 <= aspect <= 2.35:
                score += 8.0
            if 1.15 <= aspect <= 2.05:
                score += 6.0
            score -= white_ratio * 44.0
            if min(width, height) < 210:
                score -= 26.0
            if white_ratio > 0.78 and green_ratio < 0.06:
                score -= 48.0
            if dark_ratio > 0.88:
                score -= 20.0

            return {
                'width': int(width),
                'height': int(height),
                'area': int(area),
                'aspect': float(aspect),
                'green_ratio': float(green_ratio),
                'white_ratio': float(white_ratio),
                'dark_ratio': float(dark_ratio),
                'score': float(score),
            }
    except Exception:
        return None


def cleanup_task_joined_text_fields(task):
    if not task:
        return False
    changed = False

    def _clean_attr(attr_name, max_len=None):
        nonlocal changed
        current = str(getattr(task, attr_name, '') or '')
        cleaned = polish_spanish_text(
            repair_joined_words_text(current),
            multiline=(attr_name in {'coaching_points', 'confrontation_rules'}),
        )
        if max_len:
            cleaned = cleaned[:max_len]
        if cleaned != current:
            setattr(task, attr_name, cleaned)
            changed = True

    _clean_attr('title', 160)
    _clean_attr('objective', 180)
    _clean_attr('coaching_points')
    _clean_attr('confrontation_rules')

    layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
    if layout:
        layout_copy = dict(layout)
        meta = layout_copy.get('meta') if isinstance(layout_copy.get('meta'), dict) else {}
        meta = dict(meta)
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        analysis_meta = dict(analysis_meta)
        summary_raw = str(analysis_meta.get('summary') or '')
        summary_clean = polish_spanish_text(repair_joined_words_text(summary_raw), multiline=True, max_len=900)
        if summary_clean != summary_raw:
            analysis_meta['summary'] = summary_clean
            changed = True
        task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
        if task_sheet:
            task_sheet_copy = dict(task_sheet)
            for key in ('description', 'players', 'space', 'dimensions', 'materials'):
                raw_val = str(task_sheet_copy.get(key) or '')
                clean_val = polish_spanish_text(
                    repair_joined_words_text(raw_val),
                    multiline=(key == 'description'),
                )
                if clean_val != raw_val:
                    task_sheet_copy[key] = clean_val
                    changed = True
            analysis_meta['task_sheet'] = task_sheet_copy
        meta['analysis'] = analysis_meta
        layout_copy['meta'] = meta
        if layout_copy != layout:
            task.tactical_layout = layout_copy
            changed = True

    if changed:
        task.save(
            update_fields=[
                'title',
                'objective',
                'coaching_points',
                'confrontation_rules',
                'tactical_layout',
            ]
        )
    return changed


def refresh_task_from_pdf_analysis(task):
    if not task or not getattr(task, 'task_pdf', None):
        return False
    try:
        from . import session_import_services
        from .session_task_pdf_parser import _suggest_task_from_pdf

        extracted_text = session_import_services.extract_pdf_text(task.task_pdf, max_chars=60000)
        parsed_tasks = session_import_services.extract_tasks_from_pdf_text(
            extracted_text,
            fallback_title=task.title or 'Tarea desde PDF',
        )
        selected = None
        if parsed_tasks:
            meta = task.tactical_layout.get('meta') if isinstance(task.tactical_layout, dict) else {}
            segment_index = _parse_int(meta.get('pdf_segment_index')) or 1
            segment_index = max(1, min(segment_index, len(parsed_tasks)))
            selected = parsed_tasks[segment_index - 1]
        if not selected:
            selected = {'analysis': _suggest_task_from_pdf(extracted_text), 'raw_text': extracted_text[:2500]}
        analysis = selected.get('analysis') or {}
        task.title = sanitize_task_text(
            str(analysis.get('title') or task.title or 'Tarea desde PDF'),
            multiline=False,
            max_len=160,
        )
        task.duration_minutes = max(5, min((_parse_int(analysis.get('minutes')) or task.duration_minutes or 15), 90))
        task.objective = sanitize_task_text(
            str(analysis.get('objective') or task.objective or ''),
            multiline=True,
            max_len=8000,
        )
        task.coaching_points = sanitize_task_text(
            str(analysis.get('coaching_points') or task.coaching_points or ''),
            multiline=True,
        )
        task.confrontation_rules = sanitize_task_text(
            str(analysis.get('confrontation_rules') or task.confrontation_rules or ''),
            multiline=True,
        )
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        layout = dict(layout)
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        meta = dict(meta)
        raw_excerpt = str(selected.get('raw_text') or extracted_text or '')[:1200]
        if raw_excerpt:
            meta['pdf_segment_excerpt'] = raw_excerpt
        layout['meta'] = meta
        task.tactical_layout = layout
        task.save(
            update_fields=[
                'title',
                'duration_minutes',
                'objective',
                'coaching_points',
                'confrontation_rules',
                'tactical_layout',
            ]
        )
        session_import_services.apply_analysis_to_task(task, analysis)
        if not task.task_preview_image:
            ensure_library_task_preview(task, force=False, prefer_render=True)
        return True
    except Exception:
        return False


def learn_task_blueprint_from_task(*, team, task, scope_key: str = '', actor_username: str = ''):
    return _views_func('_learn_task_blueprint_from_task')(
        team=team,
        task=task,
        scope_key=scope_key,
        actor_username=actor_username,
    )


def ensure_library_task_preview_legacy(task, force=False, prefer_render=False):
    return ensure_library_task_preview(task, force=force, prefer_render=prefer_render)
