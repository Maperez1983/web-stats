import html
import re
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser

from django.utils import timezone

from . import task_library_services
from .models import SessionTask
from .services import _parse_int

TASK_PDF_PARSE_VERSION = 4

TASK_JOINED_WORD_VOCAB = task_library_services.TASK_JOINED_WORD_VOCAB
TASK_JOINED_WORD_VOCAB_ES = task_library_services.TASK_JOINED_WORD_VOCAB_ES


TASK_MATERIAL_LIBRARY = [
    {'label': 'CONO', 'title': 'Cono alto', 'kind': 'cone', 'category': 'delimitacion', 'icon': '△'},
    {'label': 'SETA', 'title': 'Seta baja', 'kind': 'marker', 'category': 'delimitacion', 'icon': '◉'},
    {'label': 'DISCO', 'title': 'Disco plano', 'kind': 'marker-flat', 'category': 'delimitacion', 'icon': '◍'},
    {'label': 'PICA', 'title': 'Pica', 'kind': 'pole', 'category': 'delimitacion', 'icon': '┃'},
    {'label': 'CINTA', 'title': 'Cinta delimitación', 'kind': 'tape', 'category': 'delimitacion', 'icon': '═'},
    {'label': 'ARO', 'title': 'Aro coordinación', 'kind': 'ring', 'category': 'coordinacion', 'icon': '◯'},
    {'label': 'ESC', 'title': 'Escalera coordinación', 'kind': 'ladder', 'category': 'coordinacion', 'icon': '☷'},
    {'label': 'VALLA', 'title': 'Valla coordinación', 'kind': 'hurdle', 'category': 'coordinacion', 'icon': '⊓'},
    {'label': 'SLALOM', 'title': 'Palo slalom', 'kind': 'slalom', 'category': 'coordinacion', 'icon': '╽'},
    {'label': 'MINI', 'title': 'Mini valla velocidad', 'kind': 'mini-hurdle', 'category': 'coordinacion', 'icon': '⫍'},
    {'label': 'BAL', 'title': 'Balón', 'kind': 'ball', 'category': 'juego', 'icon': '●'},
    {'label': 'MED', 'title': 'Balón medicinal', 'kind': 'medicine-ball', 'category': 'fisico', 'icon': '◒'},
    {'label': 'PORT', 'title': 'Portería móvil', 'kind': 'goal', 'category': 'porterias', 'icon': '⌷'},
    {'label': 'MPORT', 'title': 'Mini portería', 'kind': 'mini-goal', 'category': 'porterias', 'icon': '⌸'},
    {'label': 'PGK', 'title': 'Portería portero', 'kind': 'gk-goal', 'category': 'porterias', 'icon': '▭'},
    {'label': 'MANIQ', 'title': 'Maniquí', 'kind': 'mannequin', 'category': 'oposicion', 'icon': '♞'},
    {'label': 'DUMMY', 'title': 'Dummie inflable', 'kind': 'dummy', 'category': 'oposicion', 'icon': '♜'},
    {'label': 'MURO', 'title': 'Muro faltas', 'kind': 'wall', 'category': 'oposicion', 'icon': '▥'},
    {'label': 'PETO', 'title': 'Petos', 'kind': 'bib', 'category': 'organizacion', 'icon': '▣'},
    {'label': 'GPS', 'title': 'GPS chaleco', 'kind': 'gps', 'category': 'control', 'icon': '⌖'},
    {'label': 'CRONO', 'title': 'Cronómetro', 'kind': 'timer', 'category': 'control', 'icon': '◷'},
    {'label': 'SILB', 'title': 'Silbato', 'kind': 'whistle', 'category': 'control', 'icon': '⌇'},
    {'label': 'TAB', 'title': 'Pizarra coach', 'kind': 'board', 'category': 'control', 'icon': '▤'},
    {'label': 'GOMA', 'title': 'Goma resistencia', 'kind': 'band', 'category': 'fisico', 'icon': '∞'},
    {'label': 'TRX', 'title': 'Suspensión TRX', 'kind': 'trx', 'category': 'fisico', 'icon': '⟂'},
    {'label': 'CAJON', 'title': 'Cajón pliometría', 'kind': 'box', 'category': 'fisico', 'icon': '▧'},
    {'label': 'TRINEO', 'title': 'Trineo arrastre', 'kind': 'sled', 'category': 'fisico', 'icon': '⎍'},
    {'label': 'ESTACA', 'title': 'Estaca zona', 'kind': 'stake', 'category': 'delimitacion', 'icon': '⎸'},
    {'label': 'ARCO', 'title': 'Arco precisión', 'kind': 'arc', 'category': 'finalizacion', 'icon': '◠'},
    {'label': 'OBJ', 'title': 'Objetivo diana', 'kind': 'target', 'category': 'finalizacion', 'icon': '◎'},
]

TASK_CONTEXT_KEYWORDS = {
    'presion_alta': ['presion alta', 'presión alta', 'repliegue tras perdida', 'robo alto'],
    'salida_balon': ['salida de balon', 'salida de balón', 'inicio juego', 'construccion'],
    'finalizacion': ['finalizacion', 'finalización', 'remate', 'tiro', 'gol'],
    'transicion_ofensiva': ['transicion ofensiva', 'transición ofensiva', 'contraataque'],
    'transicion_defensiva': ['transicion defensiva', 'transición defensiva', 'balance defensivo'],
    'abp': ['abp', 'balon parado', 'balón parado', 'corner', 'falta lateral'],
    'porteros': ['portero', 'porteria', 'porteria', 'blocaje', 'despeje'],
    'fisico': ['fuerza', 'resistencia', 'velocidad', 'aceleracion', 'aceleración', 'potencia'],
}

TASK_OBJECTIVE_KEYWORDS = {
    'perfil_corporal': ['perfil corporal', 'orientacion corporal', 'orientación corporal'],
    'tercer_hombre': ['tercer hombre', 'hombre libre'],
    'amplitud': ['amplitud', 'carril exterior', 'lado debil', 'lado débil'],
    'temporizacion': ['temporizacion', 'temporización', 'esperar salto'],
    'duelo': ['duelo', '1v1', '1x1'],
    'coordinacion': ['coordinacion', 'coordinación', 'sincronizacion', 'sincronización'],
}

TASK_TYPE_KEYWORDS = {
    'rondo': ['rondo'],
    'posesion': ['posesion', 'posesión', 'conservacion', 'conservación'],
    'juego_posicional': ['juego de posicion', 'juego de posición', 'posicional'],
    'transicion': ['transicion', 'transición', 'contraataque', 'ataque rapido', 'ataque rápido'],
    'finalizacion': ['finalizacion', 'finalización', 'remate', 'tiro', 'gol'],
    'circuito': ['circuito', 'estacion', 'estación', 'posta'],
    'abp': ['abp', 'balon parado', 'balón parado', 'corner', 'falta lateral', 'saque de esquina'],
    'partido_reducido': ['partido reducido', 'ssg', 'small sided', 'juego reducido'],
}

TASK_PHASE_KEYWORDS = {
    'activacion': ['activacion', 'activación', 'calentamiento', 'entrada en calor', 'movilidad inicial'],
    'abp': ['abp', 'balon parado', 'balón parado', 'corner', 'falta lateral', 'saque de esquina'],
    'posesion': ['posesion', 'posesión', 'conservacion', 'conservación', 'rondo', 'juego de posicion', 'juego de posición'],
    'ataque': ['ataque', 'ofensiva', 'ofensivo', 'con balon', 'con balón'],
    'defensa': ['defensa', 'defensiva', 'defensivo', 'sin balon', 'sin balón'],
    'transicion': ['transicion', 'transición', 'tras perdida', 'tras pérdida', 'tras robo'],
    'mixta': ['ida y vuelta', 'ataque y defensa', 'mixto'],
}


def _normalize_folded_text(value):
    raw = str(value or '').strip().lower()
    if not raw:
        return ''
    normalized = unicodedata.normalize('NFKD', raw)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


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
    compact = _normalize_lower_compact(_word)
    if compact:
        JOINED_WORD_MAP_LOWER[compact] = compact


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
            chunk = compact[i:j]
            mapped = JOINED_WORD_MAP.get(chunk)
            if not mapped:
                continue
            bonus = (step * step) + (4 if step >= 4 else 0)
            candidate = (base_score + bonus, base_words + [mapped])
            if best[j] is None or candidate[0] > best[j][0]:
                best[j] = candidate
    if best[n] is None:
        return token
    words = best[n][1]
    if len(words) < 2:
        return token
    joined = ' '.join(words).strip()
    # Keep guardrails: avoid over-splitting into too many tiny pieces.
    if len(words) >= 7 and (len(compact) / max(1, len(words))) < 2.2:
        return token
    return joined or token


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
            chunk = compact[i:j]
            mapped = JOINED_WORD_MAP_LOWER.get(chunk)
            if not mapped:
                continue
            bonus = (step * step) + (6 if step >= 4 else 0) + (4 if step >= 6 else 0)
            candidate = (base_score + bonus, base_words + [mapped])
            if best[j] is None or candidate[0] > best[j][0]:
                best[j] = candidate
    if best[n] is None:
        return token
    words = best[n][1]
    if len(words) < 2:
        return token
    avg_len = len(compact) / max(1, len(words))
    if len(words) >= 8 and avg_len < 2.1:
        return token
    if avg_len < 2.5 and len(words) > 5:
        return token
    if token.isupper():
        return ' '.join(word.upper() for word in words).strip()
    if token[:1].isupper():
        joined = ' '.join(words).strip()
        return joined[:1].upper() + joined[1:]
    return ' '.join(words).strip()


def _repair_joined_words_text(value):
    return task_library_services.repair_joined_words_text(value)


def _polish_spanish_text(value, multiline=True, max_len=None):
    return task_library_services.polish_spanish_text(value, multiline=multiline, max_len=max_len)


def _sanitize_task_text(value, multiline=True, max_len=None):
    return task_library_services.sanitize_task_text(value, multiline=multiline, max_len=max_len)


_RICH_ALLOWED_TAGS = {
    'b',
    'strong',
    'i',
    'em',
    'u',
    's',
    'br',
    'p',
    'ul',
    'ol',
    'li',
    'div',
    'span',
    'sub',
    'sup',
}


class _RichTextSanitizer(HTMLParser):
    def __init__(self, allowed_tags):
        super().__init__()
        self.allowed = set(allowed_tags or [])
        self.out = []

    def handle_starttag(self, tag, attrs):
        name = str(tag or '').lower()
        if name not in self.allowed:
            return
        if name == 'br':
            self.out.append('<br>')
            return
        self.out.append(f'<{name}>')

    def handle_startendtag(self, tag, attrs):
        name = str(tag or '').lower()
        if name not in self.allowed:
            return
        if name == 'br':
            self.out.append('<br>')
            return
        self.out.append(f'<{name}></{name}>')

    def handle_endtag(self, tag):
        name = str(tag or '').lower()
        if name not in self.allowed or name == 'br':
            return
        self.out.append(f'</{name}>')

    def handle_data(self, data):
        if data is None:
            return
        self.out.append(html.escape(str(data)))


def _sanitize_task_rich_html(value, max_len=6000):
    raw = str(value or '').strip()
    if not raw:
        return ''
    sanitizer = _RichTextSanitizer(_RICH_ALLOWED_TAGS)
    try:
        sanitizer.feed(raw)
        sanitizer.close()
    except Exception:
        return html.escape(raw)[: int(max_len)]
    cleaned = ''.join(sanitizer.out).strip()
    if max_len:
        cleaned = cleaned[: int(max_len)]
    return cleaned


def _rich_html_from_plain_text(value, max_len=6000):
    raw = str(value or '').strip()
    if not raw:
        return ''
    if max_len:
        raw = raw[: int(max_len)]
    return html.escape(raw).replace('\n', '<br>')


def _text_has_quality_issues(value):
    return task_library_services.text_has_quality_issues(value)


MONTHS_ES = {
    'enero': 1,
    'febrero': 2,
    'marzo': 3,
    'abril': 4,
    'mayo': 5,
    'junio': 6,
    'julio': 7,
    'agosto': 8,
    'septiembre': 9,
    'setiembre': 9,
    'octubre': 10,
    'noviembre': 11,
    'diciembre': 12,
}


def _coerce_reference_date(raw_value):
    value = str(raw_value or '').strip()
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None
    if parsed.year < 2000 or parsed.year > 2100:
        return None
    return parsed


def _parse_2digit_year(year_value):
    year_int = int(year_value)
    if year_int >= 100:
        return year_int
    return 2000 + year_int if year_int <= 69 else 1900 + year_int


def _extract_dates_from_text(raw_text):
    text = str(raw_text or '')
    if not text:
        return []
    found = []

    for line in text.splitlines():
        if 'fecha' not in _normalize_folded_text(line):
            continue
        line_dates = _extract_dates_line_parser(line)
        if line_dates:
            return line_dates
    return _extract_dates_line_parser(text)


def _extract_dates_line_parser(segment):
    text = str(segment or '')
    dates_found = []
    for match in re.finditer(r'\b([0-3]?\d)[\/\-.]([01]?\d)[\/\-.](\d{2,4})\b', text):
        day_val = _parse_int(match.group(1))
        month_val = _parse_int(match.group(2))
        year_val = _parse_int(match.group(3))
        if not day_val or not month_val or year_val is None:
            continue
        year_val = _parse_2digit_year(year_val)
        try:
            parsed = date(year_val, month_val, day_val)
        except ValueError:
            continue
        if 2000 <= parsed.year <= 2100:
            dates_found.append(parsed)
    for match in re.finditer(r'\b(\d{4})[\/\-.]([01]?\d)[\/\-.]([0-3]?\d)\b', text):
        year_val = _parse_int(match.group(1))
        month_val = _parse_int(match.group(2))
        day_val = _parse_int(match.group(3))
        if not year_val or not month_val or not day_val:
            continue
        try:
            parsed = date(year_val, month_val, day_val)
        except ValueError:
            continue
        if 2000 <= parsed.year <= 2100:
            dates_found.append(parsed)
    month_regex = '|'.join(MONTHS_ES.keys())
    for match in re.finditer(
        rf'\b([0-3]?\d)\s*(?:de\s+)?({month_regex})\s*(?:de\s+)?(\d{{2,4}})\b',
        _normalize_folded_text(text),
        flags=re.IGNORECASE,
    ):
        day_val = _parse_int(match.group(1))
        month_val = MONTHS_ES.get(str(match.group(2) or '').lower())
        year_val = _parse_int(match.group(3))
        if not day_val or not month_val or year_val is None:
            continue
        year_val = _parse_2digit_year(year_val)
        try:
            parsed = date(year_val, month_val, day_val)
        except ValueError:
            continue
        if 2000 <= parsed.year <= 2100:
            dates_found.append(parsed)
    return dates_found


def _detect_reference_date_in_text(raw_text):
    candidates = _extract_dates_from_text(raw_text)
    if not candidates:
        return None
    return candidates[0]


def _task_upload_date(task):
    created = getattr(task, 'created_at', None)
    if created:
        try:
            return timezone.localtime(created).date()
        except Exception:
            try:
                return created.date()
            except Exception:
                pass
    session_obj = getattr(task, 'session', None)
    if session_obj and getattr(session_obj, 'session_date', None):
        return session_obj.session_date
    return timezone.localdate()


def _build_task_date_haystack(task, analysis_meta=None):
    sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta, dict) and isinstance(analysis_meta.get('task_sheet'), dict) else {}
    return '\n'.join(
        [
            str(getattr(task, 'title', '') or ''),
            str(getattr(task, 'objective', '') or ''),
            str(getattr(task, 'coaching_points', '') or ''),
            str(getattr(task, 'confrontation_rules', '') or ''),
            str((analysis_meta or {}).get('summary') or ''),
            str(sheet.get('description') or ''),
        ]
    ).strip()


def _extract_effective_reference_date(task, analysis_meta=None):
    upload_date = _task_upload_date(task)
    meta = analysis_meta if isinstance(analysis_meta, dict) else {}
    stored_date = _coerce_reference_date(meta.get('reference_date'))
    if stored_date and stored_date != upload_date:
        return stored_date
    detected = _detect_reference_date_in_text(_build_task_date_haystack(task, meta))
    if detected and detected != upload_date:
        return detected
    return None


def _ensure_task_reference_date(task):
    if not task:
        return False
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    layout_copy = dict(layout)
    meta = layout_copy.get('meta') if isinstance(layout_copy.get('meta'), dict) else {}
    meta = dict(meta)
    analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
    analysis_meta = dict(analysis_meta)
    upload_date = _task_upload_date(task)
    detected = _extract_effective_reference_date(task, analysis_meta=analysis_meta)
    current = _coerce_reference_date(analysis_meta.get('reference_date'))
    changed = False
    if detected and detected != upload_date:
        if current != detected:
            analysis_meta['reference_date'] = detected.isoformat()
            analysis_meta['reference_date_source'] = 'content'
            changed = True
    elif analysis_meta.get('reference_date'):
        analysis_meta.pop('reference_date', None)
        analysis_meta.pop('reference_date_source', None)
        changed = True
    if changed:
        meta['analysis'] = analysis_meta
        layout_copy['meta'] = meta
        task.tactical_layout = layout_copy
        task.save(update_fields=['tactical_layout'])
    return changed


def _detect_keyword_tags(text, taxonomy):
    haystack = _normalize_folded_text(text)
    tags = []
    for tag, keys in (taxonomy or {}).items():
        for key in keys:
            if _normalize_folded_text(key) in haystack:
                tags.append(tag)
                break
    return tags


def _detect_materials_in_text(text):
    haystack = _normalize_folded_text(text)
    detected = []
    for item in TASK_MATERIAL_LIBRARY:
        label = _normalize_folded_text(item.get('label'))
        title = _normalize_folded_text(item.get('title'))
        kind = _normalize_folded_text(item.get('kind'))
        if any(token and token in haystack for token in {label, title, kind}):
            detected.append(
                {
                    'label': item.get('label') or '',
                    'title': item.get('title') or '',
                    'kind': item.get('kind') or '',
                    'category': item.get('category') or '',
                }
            )
    return detected


def _analysis_quality_score(analysis):
    if not isinstance(analysis, dict):
        return 0
    score = 0
    if analysis.get('title'):
        score += 20
    if analysis.get('objective'):
        score += 20
    if analysis.get('coaching_points'):
        score += 20
    if analysis.get('confrontation_rules'):
        score += 20
    if analysis.get('work_contexts'):
        score += 10
    if analysis.get('objective_tags'):
        score += 5
    if analysis.get('detected_materials'):
        score += 5
    if analysis.get('exercise_types'):
        score += 5
    if analysis.get('phase_tags'):
        score += 5
    task_sheet = analysis.get('task_sheet') if isinstance(analysis.get('task_sheet'), dict) else {}
    if task_sheet.get('description'):
        score += 5
    if task_sheet.get('players') or task_sheet.get('dimensions') or task_sheet.get('materials'):
        score += 5
    return min(100, score)


def _analysis_confidence_scores(analysis):
    data = analysis if isinstance(analysis, dict) else {}
    sheet = data.get('task_sheet') if isinstance(data.get('task_sheet'), dict) else {}
    title = str(data.get('title') or '').strip()
    objective = str(data.get('objective') or '').strip()
    coaching = str(data.get('coaching_points') or '').strip()
    rules = str(data.get('confrontation_rules') or '').strip()
    summary = str(data.get('summary') or '').strip()
    players = str(sheet.get('players') or '').strip()
    dimensions = str(sheet.get('dimensions') or '').strip()
    materials = str(sheet.get('materials') or '').strip()
    exercise_types = data.get('exercise_types') if isinstance(data.get('exercise_types'), list) else []
    phase_tags = data.get('phase_tags') if isinstance(data.get('phase_tags'), list) else []

    def _value_conf(text_value, max_len=220):
        text_value = str(text_value or '').strip()
        if not text_value:
            return 0
        score = 38
        score += min(len(text_value), max_len) / max_len * 42
        if re.search(r'\b[A-ZÁÉÍÓÚÜÑ]{12,}\b', text_value):
            score -= 32
        if re.search(r'[,;:]\S', text_value):
            score -= 8
        return max(0, min(100, int(round(score))))

    scores = {
        'title': _value_conf(title, 120),
        'objective': _value_conf(objective, 180),
        'coaching': _value_conf(coaching, 280),
        'rules': _value_conf(rules, 280),
        'summary': _value_conf(summary, 320),
        'players': _value_conf(players, 120),
        'dimensions': _value_conf(dimensions, 100),
        'materials': _value_conf(materials, 180),
    }
    semantic_bonus = 0
    if exercise_types:
        semantic_bonus += 8
    if phase_tags:
        semantic_bonus += 8
    base_values = [scores['title'], scores['objective'], scores['coaching'], scores['summary']]
    overall = int(round(sum(base_values) / max(1, len(base_values)) + semantic_bonus))
    scores['overall'] = max(0, min(100, overall))
    return scores


def _analysis_needs_review(analysis):
    if not isinstance(analysis, dict):
        return True
    conf = _analysis_confidence_scores(analysis)
    if int(conf.get('overall') or 0) < 62:
        return True
    if int(conf.get('title') or 0) < 55:
        return True
    if int(conf.get('objective') or 0) < 45:
        return True
    if re.search(r'\b[A-ZÁÉÍÓÚÜÑ]{12,}\b', str(analysis.get('summary') or '')):
        return True
    return False



def _apply_analysis_to_task(task, analysis):
    layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    confidence = _analysis_confidence_scores(analysis)
    summary_clean = _sanitize_task_text((analysis.get('summary') or '')[:900], multiline=True, max_len=900)
    task_sheet_raw = analysis.get('task_sheet') if isinstance(analysis.get('task_sheet'), dict) else {}
    description_plain = _sanitize_task_text(task_sheet_raw.get('description') or '', multiline=True, max_len=1200)
    players_plain = _sanitize_task_text(task_sheet_raw.get('players') or '', multiline=False, max_len=120)
    space_plain = _sanitize_task_text(task_sheet_raw.get('space') or '', multiline=False, max_len=120)
    dimensions_plain = _sanitize_task_text(task_sheet_raw.get('dimensions') or '', multiline=False, max_len=120)
    materials_plain = _sanitize_task_text(task_sheet_raw.get('materials') or '', multiline=False, max_len=300)

    description_html_raw = str(task_sheet_raw.get('description_html') or '').strip()
    coaching_html_raw = str(task_sheet_raw.get('coaching_html') or '').strip()
    rules_html_raw = str(task_sheet_raw.get('rules_html') or '').strip()

    description_html_clean = _sanitize_task_rich_html(description_html_raw) if description_html_raw else _rich_html_from_plain_text(description_plain)
    coaching_html_clean = _sanitize_task_rich_html(coaching_html_raw) if coaching_html_raw else _rich_html_from_plain_text(str(analysis.get('coaching_points') or ''))
    rules_html_clean = _sanitize_task_rich_html(rules_html_raw) if rules_html_raw else _rich_html_from_plain_text(str(analysis.get('confrontation_rules') or ''))

    task_sheet_clean = {
        'description': description_plain,
        'description_html': description_html_clean,
        'coaching_html': coaching_html_clean,
        'rules_html': rules_html_clean,
        'players': players_plain,
        'space': space_plain,
        'dimensions': dimensions_plain,
        'materials': materials_plain,
    }
    upload_date = _task_upload_date(task)
    reference_date = _coerce_reference_date(analysis.get('reference_date'))
    if not reference_date:
        text_for_date = '\n'.join(
            [
                str(analysis.get('title') or ''),
                str(analysis.get('objective') or ''),
                str(analysis.get('coaching_points') or ''),
                str(analysis.get('confrontation_rules') or ''),
                str(analysis.get('summary') or ''),
                str(task_sheet_clean.get('description') or ''),
            ]
        )
        reference_date = _detect_reference_date_in_text(text_for_date)
    reference_date_iso = ''
    if reference_date and reference_date != upload_date:
        reference_date_iso = reference_date.isoformat()

    meta['analysis'] = {
        'work_contexts': analysis.get('work_contexts') or [],
        'objective_tags': analysis.get('objective_tags') or [],
        'detected_materials': analysis.get('detected_materials') or [],
        'exercise_types': analysis.get('exercise_types') or [],
        'phase_tags': analysis.get('phase_tags') or [],
        'players_count_estimate': analysis.get('players_count_estimate') or None,
        'players_band': analysis.get('players_band') or '',
        'duration_band': analysis.get('duration_band') or '',
        'quality_score': analysis.get('quality_score') or 0,
        'confidence': confidence,
        'needs_review': _analysis_needs_review(analysis),
        'pdf_template': analysis.get('pdf_template') or 'generic',
        'summary': summary_clean,
        'task_sheet': task_sheet_clean,
        'reference_date': reference_date_iso,
        'reference_date_source': 'content' if reference_date_iso else '',
        'analyzed_at': timezone.now().isoformat(),
        'parser_version': TASK_PDF_PARSE_VERSION,
    }
    layout['meta'] = meta
    task.tactical_layout = layout
    task.save(update_fields=['tactical_layout'])



def _extract_section_block(text, section_aliases):
    """
    Extrae un bloque de texto bajo una cabecera (alias) hasta que detecta otra cabecera.
    Esta versión es más robusta para PDFs: corta por "Dosificación", "Tiempo total", "Material", etc.
    """
    lines = [ln.strip() for ln in str(text or '').splitlines()]
    if not lines:
        return ''
    aliases = [str(a or '').strip().lower() for a in (section_aliases or []) if str(a or '').strip()]
    start = None
    for idx, line in enumerate(lines):
        low = str(line or '').lower()
        if any(re.search(rf'^{re.escape(alias)}\s*[:\-]?\s*$', low) for alias in aliases):
            start = idx + 1
            break
        if any(low.startswith(f'{alias}:') or low.startswith(f'{alias} -') for alias in aliases):
            inline = re.split(r'[:\-]', line, maxsplit=1)
            if len(inline) == 2 and inline[1].strip():
                return inline[1].strip()
    if start is None:
        return ''

    stop_tokens = {
        'objetivo',
        'objective',
        'descripcion',
        'descripción',
        'desarrollo',
        'consignas',
        'dosificacion',
        'dosificación',
        'tiempo total',
        'tiempototal',
        'tiempo total de trabajo',
        'tiempototaldetrabajo',
        'material',
        'materiales',
        'reglas',
        'normas',
        'observaciones',
        'parteprincipal',
        'parte principal',
        'partefinal',
        'parte final',
        'ausentes',
        'lesionados',
    }

    end = len(lines)
    for idx in range(start, len(lines)):
        folded = _normalize_folded_text(lines[idx])
        if not folded:
            continue
        if re.match(r'^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\b', folded):
            end = idx
            break
        if any(
            folded.startswith(token.replace(' ', ''))
            or folded.startswith(token)
            for token in {t.replace(' ', '') for t in stop_tokens}.union(stop_tokens)
        ):
            # Evita cortar por bullets "- ..." o "1) ..." que son contenido.
            raw = str(lines[idx] or '').strip()
            if raw.startswith(('-', '•', '*')) or re.match(r'^\d+[\).\s-]', raw):
                continue
            # Solo cortar si realmente parece cabecera.
            if ':' in raw or re.match(r'^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{3,34}\s*$', raw):
                end = idx
                break
    return '\n'.join([ln for ln in lines[start:end] if ln]).strip()


def _clean_task_notes_block(value):
    """
    Limpia bloques de texto tipo consignas/normas para evitar que "Dosificación", "Tiempo total", etc.
    contaminen el contenido.
    """
    raw = str(value or '').strip()
    if not raw:
        return ''
    cleaned = []
    noise_prefixes = (
        'dosificacion',
        'tiempototal',
        'tiempo total',
        'tiempototaldetrabajo',
        'tiempo total de trabajo',
        'tiempodetrabajo',
        'tiempo de trabajo',
        'hidratacion',
        'hidratación',
        'bloques',
        'partefinal',
        'parte final',
        'ausentes',
        'lesionados',
        'observaciones',
    )
    for line in raw.splitlines():
        ln = str(line or '').strip()
        if not ln:
            continue
        folded = _normalize_folded_text(ln)
        if any(folded.startswith(prefix) for prefix in noise_prefixes):
            continue
        # Suprime líneas sueltas de tiempo tipo "Tiempo total: 30"
        if re.match(r'(?i)^tiempo\s*total\s*[:\-]?\s*\d{1,3}', ln):
            continue
        cleaned.append(ln)
    text = '\n'.join(cleaned).strip()
    # Compacta saltos
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _pick_bullets_or_sentences(raw_text, limit=5):
    lines = [ln.strip() for ln in str(raw_text or '').splitlines() if ln.strip()]
    items = []
    for line in lines:
        clean = re.sub(r'^[\-\•\*\d\)\.\s]+', '', line).strip()
        if not clean:
            continue
        if len(clean) < 4:
            continue
        items.append(clean)
        if len(items) >= limit:
            break
    return '\n'.join(items)


def _extract_inline_field(text, aliases, max_len=240):
    raw = str(text or '')
    if not raw:
        return ''
    alias_pattern = '|'.join(re.escape(alias) for alias in aliases)
    patterns = [
        rf'(?im)^\s*(?:{alias_pattern})\s*[:\-]\s*(.+?)\s*$',
        rf'(?i)\b(?:{alias_pattern})\s*[:\-]\s*([^\n\r]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            value = ' '.join(str(match.group(1) or '').split()).strip(' ,.;:-')
            if value:
                return value[:max_len]
    return ''


def _extract_first_dimension_text(text):
    raw = str(text or '')
    if not raw:
        return ''
    match = re.search(
        r'(?i)\b(\d{1,3}(?:[.,]\d{1,2})?\s*(?:m|metros?)?)\s*[xX×]\s*(\d{1,3}(?:[.,]\d{1,2})?\s*(?:m|metros?)?)\b',
        raw,
    )
    if not match:
        return ''
    left = str(match.group(1) or '').strip()
    right = str(match.group(2) or '').strip()
    return f'{left} x {right}'


def _extract_players_text(text):
    raw = str(text or '')
    if not raw:
        return ''
    explicit = _extract_inline_field(
        raw,
        ['jugadores', 'participantes', 'n jugadores', 'num jugadores', 'nº jugadores', 'numero jugadores'],
        max_len=120,
    )
    if explicit:
        return explicit
    pattern = re.search(r'(?i)\b(\d{1,2}\s*v\s*\d{1,2}(?:\s*\+\s*\d{1,2})?)\b', raw)
    if pattern:
        return str(pattern.group(1)).replace(' ', '')
    # "8x8", "8 x 8", "8×8" también es habitual en PDFs.
    pattern = re.search(r'(?i)\b(\d{1,2}\s*[xX×]\s*\d{1,2}(?:\s*\+\s*\d{1,2})?)\b', raw)
    if pattern:
        return re.sub(r'\s+', '', str(pattern.group(1)))
    total = re.search(r'(?i)\b(\d{1,2})\s*(?:jugadores?|participantes?)\b', raw)
    if total:
        return f'{total.group(1)} jugadores'
    return ''


def _estimate_players_count(players_text, fallback_text=''):
    source = ' '.join([str(players_text or ''), str(fallback_text or '')]).strip()
    if not source:
        return None
    cleaned = source.replace('vs', 'v').replace('x', 'v')
    total = 0
    matched = False
    for group in re.findall(r'(\d{1,2}\s*v\s*\d{1,2}(?:\s*\+\s*\d{1,2})?)', cleaned, flags=re.IGNORECASE):
        nums = [_parse_int(n) for n in re.findall(r'\d{1,2}', group)]
        nums = [n for n in nums if n is not None]
        if nums:
            total += sum(nums)
            matched = True
    if matched and total > 0:
        return total
    explicit_total = re.search(r'(?i)\b(\d{1,2})\s*(?:jugadores?|participantes?)\b', cleaned)
    if explicit_total:
        parsed = _parse_int(explicit_total.group(1))
        if parsed:
            return parsed
    nums = [_parse_int(n) for n in re.findall(r'\b\d{1,2}\b', cleaned)]
    nums = [n for n in nums if n is not None]
    plausible = [n for n in nums if 4 <= n <= 30]
    if plausible:
        return max(plausible)
    return None


def _players_band_label(players_count):
    value = _parse_int(players_count)
    if not value:
        return ''
    if value <= 6:
        return 'micro (1-6)'
    if value <= 12:
        return 'grupo (7-12)'
    if value <= 18:
        return 'equipo (13-18)'
    return 'ampliado (19+)'


def _duration_band_label(minutes):
    value = _parse_int(minutes)
    if not value:
        return ''
    if value <= 12:
        return 'corta (5-12m)'
    if value <= 20:
        return 'media (13-20m)'
    if value <= 35:
        return 'larga (21-35m)'
    return 'extendida (36m+)'


def _detect_pdf_template(text):
    raw = _normalize_folded_text(text)
    if not raw:
        return 'generic'
    markers = {
        'sesion_sheet_compact': [
            'dosificacion',
            'tiempototaldetrabajo',
            'parteprincipal',
            'materialdeentrenamiento',
        ],
        'session_es_verbose': [
            'objetivo',
            'consignas',
            'reglas',
            'material',
            'jugadores',
        ],
    }
    best_key = 'generic'
    best_score = 0
    for key, keys in markers.items():
        score = sum(1 for token in keys if token in raw)
        if score > best_score:
            best_score = score
            best_key = key
    return best_key


def _extract_task_sheet_from_pdf(text, detected_materials=None, template_key='generic'):
    description_aliases = ['descripcion', 'descripción', 'desarrollo', 'organizacion', 'organización', 'estructura', 'dinamica', 'dinámica']
    if template_key == 'sesion_sheet_compact':
        # En plantillas compactas, "Consignas" suele ser una sección aparte (no la descripción general).
        description_aliases = ['descripcion', 'descripción', 'desarrollo', 'organizacion', 'organización']
    description = _extract_section_block(
        text,
        description_aliases,
    )
    if template_key == 'sesion_sheet_compact' and not description:
        # Fallback específico: usa el bloque antes de "Consignas"/"Dosificación" como descripción.
        lines = [ln.strip() for ln in str(text or '').splitlines() if ln.strip()]
        if lines:
            # Quita encabezados tipo "Tarea2:..."
            while lines and re.match(r'(?i)^(?:tarea|ejercicio|task|drill)\s*\d{1,2}\b', lines[0]):
                lines = lines[1:]
            stop_idx = len(lines)
            for idx, ln in enumerate(lines[:70]):
                folded = _normalize_folded_text(ln)
                if folded.startswith('consignas') or folded.startswith('dosificacion') or folded.startswith('tiempototal'):
                    stop_idx = idx
                    break
            if stop_idx > 1:
                candidate = '\n'.join(lines[:stop_idx]).strip()
                # Si es demasiado largo, recorta dejando lo más descriptivo.
                description = candidate[:1400]
    if not description:
        description = _pick_bullets_or_sentences(text, limit=6)

    players = _extract_players_text(text)
    space = _extract_inline_field(text, ['espacio', 'superficie', 'zona', 'campo', 'area', 'área'], max_len=120)
    dimensions = _extract_inline_field(text, ['medidas', 'dimensiones', 'tamano', 'tamaño'], max_len=120)
    if not dimensions:
        dimensions = _extract_first_dimension_text(text)

    material_section = _extract_section_block(text, ['material', 'materiales', 'elementos', 'recursos'])
    material_detected = []
    for item in detected_materials or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get('title') or item.get('label') or item.get('kind') or '').strip()
        if label:
            material_detected.append(label)
    if material_section:
        materials = material_section
    else:
        materials = ', '.join(sorted(set(material_detected)))[:300]

    return {
        'description': _polish_spanish_text(_repair_joined_words_text((description or '')[:1400]), multiline=True, max_len=1200),
        'players': _polish_spanish_text(_repair_joined_words_text(players), multiline=False, max_len=120),
        'space': _polish_spanish_text(_repair_joined_words_text(space), multiline=False, max_len=120),
        'dimensions': _polish_spanish_text(_repair_joined_words_text(dimensions), multiline=False, max_len=120),
        'materials': _polish_spanish_text(_repair_joined_words_text(materials), multiline=False, max_len=300),
    }


def _normalize_pdf_task_text(value):
    """
    La extracción de PDF a veces concatena títulos + secciones (Consignas/Dosificación/etc.) en una sola línea.
    Insertamos saltos de línea en cabeceras comunes y normalizamos bullets para mejorar el parsing.
    """
    text = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    if not text.strip():
        return ''
    # Asegura que cabeceras típicas empiecen en línea nueva.
    headings = [
        'Objetivo',
        'Objective',
        'Descripción',
        'Descripcion',
        'Consignas',
        'Dosificación',
        'Dosificacion',
        'Tiempo total',
        'Tiempo total de trabajo',
        'Material',
        'Materiales',
        'Reglas',
        'Normas',
        'Observaciones',
    ]
    for heading in headings:
        text = re.sub(
            rf'(?i)(?<!^)(?<!\n)\s+(?={re.escape(heading)}\s*[:\-])',
            '\n',
            text,
        )
    # Normaliza listas inline: "Consignas: - a - b" -> "Consignas:\n- a\n- b"
    text = re.sub(r'(?i)(consignas\s*[:\-])\s*-\s*', r'\1\n- ', text)
    text = re.sub(r'(?i)((?:reglas|normas)\s*[:\-])\s*-\s*', r'\1\n- ', text)
    # Si hay múltiples "- " seguidos en la misma línea, fuerza salto.
    text = re.sub(r'(?<!\n)\s-\s+', '\n- ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _suggest_task_from_pdf(pdf_text):
    text = _polish_spanish_text(_repair_joined_words_text(pdf_text or ''), multiline=True)
    text = _normalize_pdf_task_text(text)
    text = str(text or '').strip()
    template_key = _detect_pdf_template(text)
    if not text:
        return {
            'title': '',
            'objective': '',
            'minutes': 15,
            'coaching_points': '',
            'confrontation_rules': '',
            'summary': '',
            'pdf_template': template_key,
            'reference_date': '',
        }

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ''
    title_idx = None
    title_from_marker = False
    skip_title_tokens = [
        'parteprincipal',
        'materialdeentrenamiento',
        'tiempototaldesesion',
        'tiempo total de sesion',
        'fecha:',
        'hora:',
        'micro-ciclo',
        'meso-ciclo',
    ]
    if template_key == 'sesion_sheet_compact':
        skip_title_tokens.extend(['tiempototaldetrabajo', 'dosificacion', 'hidratacion'])
    for idx_line, line in enumerate(lines[:24]):
        # Permite títulos largos (a veces el PDF concatena el nombre completo en una sola línea).
        if len(line) > 260 or re.search(r'^\d+$', line):
            continue
        folded = _normalize_folded_text(line)
        if not folded or folded in {',', '.', ';'}:
            continue
        # Salta marcadores tipo "Tarea 2" sin título real.
        if re.match(r'^(?:tarea|ejercicio|task|drill)\s*\d{1,2}\s*$', folded, flags=re.IGNORECASE):
            continue
        if any(token in folded for token in skip_title_tokens):
            continue
        if (
            folded.startswith('2bloques')
            or folded.startswith('3bloques')
            or folded.startswith('tiempototal')
            or re.match(r'^tiempo\s*total', folded)
        ):
            continue
        # Si la línea empieza por "Tarea 2: ..." o "Tarea 2 ..." nos quedamos con el resto como título.
        marker = re.match(
            r'(?i)^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\s*[:\-]?\s*(.+)$',
            line,
        )
        if marker and marker.group(1) and marker.group(1).strip():
            candidate_title = marker.group(1).strip()
            if len(candidate_title) >= 4:
                title = candidate_title
            else:
                title = line
            title_from_marker = True
        else:
            title = line
        title_idx = idx_line
        break

    # En PDFs tipo "sesión" es común: "Tarea 1: TRABAJO DE" (línea) + "SALIDA DE BALÓN" (línea siguiente).
    # Si el título desde marcador queda muy corto, concatenamos 1-2 líneas siguientes si parecen continuación.
    if title and title_from_marker:
        try:
            idx = title_idx if isinstance(title_idx, int) else None
            if idx is None:
                # fallback: intenta localizar el título actual
                idx = next((i for i, ln in enumerate(lines[:24]) if title in ln), None)
        except Exception:
            idx = None
        if isinstance(idx, int) and 0 <= idx < len(lines):
            tail = title.strip().lower()
            wants_more = (len(title.strip()) < 22) or tail.endswith((' de', ' del', ' la', ' el', ' los', ' las', ' con', ' sin', ' para', ' por'))
            if wants_more:
                extras = []
                for nxt in lines[idx + 1: idx + 4]:
                    folded = _normalize_folded_text(nxt)
                    if not folded:
                        continue
                    if any(token in folded for token in skip_title_tokens):
                        break
                    if re.match(r'^(?:dosificacion|tiempo|parteprincipal|parte\s+principal)\b', folded):
                        break
                    if len(nxt) > 90:
                        break
                    # Continuación típica: mayúsculas o frase corta.
                    if nxt.isupper() or len(nxt.split()) <= 6:
                        extras.append(nxt)
                    else:
                        break
                    # Tras la 1ª línea de continuación, normalmente ya tenemos el título completo.
                    combined = f"{title} {' '.join(extras)}".strip()
                    combined_tail = combined.lower().strip()
                    if len(extras) >= 1 and not combined_tail.endswith((' de', ' del', ' la', ' el', ' los', ' las', ' con', ' sin', ' para', ' por')):
                        break
                    if len(extras) >= 2:
                        break
                    if len(' '.join([title] + extras)) >= 90:
                        break
                if extras:
                    title = f"{title} {' '.join(extras)}".strip()
    # Fallback: si no encontramos título por límites de línea (PDFs con textos concatenados),
    # toma la primera línea útil, incluso si es larga (se truncará a max_len más tarde).
    if not title:
        for line in lines[:10]:
            if not line or re.search(r'^\d+$', line):
                continue
            folded = _normalize_folded_text(line)
            if re.match(r'^(?:tarea|ejercicio|task|drill)\s*\d{1,2}\s*$', folded, flags=re.IGNORECASE):
                continue
            if any(token in folded for token in skip_title_tokens):
                continue
            marker = re.match(
                r'(?i)^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\s*[:\-]?\s*(.+)$',
                line,
            )
            if marker and marker.group(1) and marker.group(1).strip():
                candidate_title = marker.group(1).strip()
                if len(candidate_title) >= 4:
                    title = candidate_title
                    break
            title = line
            break
    # Limpia títulos que vienen concatenados con bullets/dosificación.
    if title:
        title = re.split(r'\s*[•●]\s*', title, maxsplit=1)[0].strip()
        minutes_in_title = re.search(r'\b\d{1,3}\s*[\'’`´]', title)
        if minutes_in_title and minutes_in_title.start() > 10:
            title = title[: minutes_in_title.start()].strip()

    objective_aliases = ['objetivo', 'objective', 'finalidad', 'meta']
    if template_key == 'sesion_sheet_compact':
        # Importante: NO usar "consignas" como alias de objetivo (si no, se mezcla con la sección de consignas).
        objective_aliases.extend(['descripcion', 'desarrollo'])
    objective = _extract_section_block(text, objective_aliases)
    if not objective:
        objective_match = re.search(r'(objetivo|objective)\s*[:\-]\s*(.+)', text, re.IGNORECASE)
        if objective_match:
            objective = objective_match.group(2).strip()
        elif len(lines) > 1:
            for candidate in lines[1:10]:
                folded = _normalize_folded_text(candidate)
                if len(candidate.strip(' ,.;:-')) < 4:
                    continue
                if folded.startswith('consignas') or folded.startswith('dosificacion') or folded.startswith('tiempototal'):
                    continue
                if re.match(r'^(dosificacion|tiempo\s*total|parteprincipal)\b', folded):
                    continue
                if re.match(r'^\d+\s*bloques', folded):
                    continue
                objective = candidate[:8000]
                break

    minutes = 15
    dosage_line = re.search(r'dosificaci[oó]n\s*[:\-]?\s*([^\n]{0,120})', text, re.IGNORECASE)
    if dosage_line:
        nums = [_parse_int(num) for num in re.findall(r'\d{1,3}', dosage_line.group(1))]
        nums = [n for n in nums if n is not None]
        plausible = [n for n in nums if 5 <= n <= 90]
        if plausible:
            minutes = max(plausible)
    if minutes == 15:
        minute_match = re.search(
            r'tiempo\s*total\s*[:\-]?\s*(\d{1,3})\s*(?:min|mins|minutos|minutes|[\'’`´])?',
            text,
            re.IGNORECASE,
        )
        if not minute_match:
            minute_match = re.search(r'(\d{1,3})\s*(?:min|mins|minutos|minutes|[\'’`´])', text, re.IGNORECASE)
        if minute_match:
            parsed = _parse_int(minute_match.group(1)) or 15
            minutes = max(5, min(parsed, 90))

    coaching_points = _extract_section_block(
        text,
        ['consignas', 'coaching points', 'puntos clave', 'indicaciones', 'correcciones'],
    )
    confrontation_rules = _extract_section_block(
        text,
        ['reglas', 'reglas de confrontacion', 'puntuacion', 'normas', 'restricciones'],
    )
    has_consignas = bool(re.search(r'(?im)^\s*consignas\s*[:\-]?\s*$', text) or re.search(r'(?i)\bconsignas\s*[:\-]\s*\S', text))
    has_rules = bool(
        re.search(r'(?im)^\s*(?:reglas|normas)\s*[:\-]?\s*$', text) or re.search(r'(?i)\b(?:reglas|normas)\s*[:\-]\s*\S', text)
    )

    # Si el objetivo ha quedado contaminado por bullets o por cabeceras, aplica fallback más simple.
    if objective and (objective.lstrip().startswith(('-', '•', '*')) or '\n-' in objective[:60]):
        objective = ''
    if objective:
        objective = re.sub(r'(?i)^(?:tarea\s*\d+\s*)$', '', objective).strip()
        if _normalize_folded_text(objective) in {'consignas', 'dosificacion', 'tiempototal', 'tiempodetrabajo'}:
            objective = ''
    if not objective:
        # Fallback: toma la primera frase útil antes de "Consignas"/"Dosificación".
        obj_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if obj_lines:
            # Salta títulos/markers iniciales
            obj_candidates = []
            for ln in obj_lines[:40]:
                folded = _normalize_folded_text(ln)
                if not folded:
                    continue
                if re.match(r'^(?:tarea|ejercicio|task|drill)\s*\d{1,2}\b', folded):
                    continue
                if folded.startswith('consignas') or folded.startswith('dosificacion') or folded.startswith('tiempototal'):
                    break
                if ln.startswith(('-', '•', '*')) or re.match(r'^\d+[\).\s-]', ln):
                    continue
                if len(ln.strip(' ,.;:-')) < 4:
                    continue
                obj_candidates.append(ln)
                if len(' '.join(obj_candidates)) >= 140:
                    break
            if obj_candidates:
                objective = ' '.join(obj_candidates)[:8000]
    if not coaching_points or not confrontation_rules:
        # En plantillas compactas, solo rellenamos consignas/normas si hay cabecera explícita
        # (si no, nos llevamos "Dosificación" y otros bloques no deseados).
        if template_key != 'sesion_sheet_compact' or has_consignas or has_rules:
            bullet_like = []
            for line in lines:
                if line.startswith(('-', '•', '*')) or re.match(r'^\d+[\).\s-]', line):
                    bullet_like.append(re.sub(r'^[\-\•\*\d\)\.\s]+', '', line).strip())
                if len(bullet_like) >= 10:
                    break
            if not coaching_points:
                coaching_points = '\n'.join(bullet_like[:5])
            if not confrontation_rules:
                confrontation_rules = '\n'.join(bullet_like[5:10])
    if not coaching_points and template_key != 'sesion_sheet_compact':
        coaching_points = _pick_bullets_or_sentences(text, limit=4)
    if not confrontation_rules:
        confrontation_rules = ''

    coaching_points = _clean_task_notes_block(coaching_points)
    confrontation_rules = _clean_task_notes_block(confrontation_rules)

    summary = '\n'.join(lines[:12])[:900]
    work_contexts = _detect_keyword_tags(text, TASK_CONTEXT_KEYWORDS)
    objective_tags = _detect_keyword_tags(' '.join([objective, coaching_points, confrontation_rules]), TASK_OBJECTIVE_KEYWORDS)
    exercise_types = _detect_keyword_tags(text, TASK_TYPE_KEYWORDS)
    phase_tags = _detect_keyword_tags(' '.join([text, objective, coaching_points]), TASK_PHASE_KEYWORDS)
    detected_materials = _detect_materials_in_text(text)
    task_sheet = _extract_task_sheet_from_pdf(text, detected_materials=detected_materials, template_key=template_key)
    # Para el editor/PDF actual guardamos también versión HTML (rich) desde el import.
    try:
        task_sheet = dict(task_sheet or {})
        description_plain = str(task_sheet.get('description') or '').strip()
        task_sheet['description_html'] = _rich_html_from_plain_text(description_plain) if description_plain else ''
        task_sheet['coaching_html'] = _rich_html_from_plain_text(coaching_points) if str(coaching_points or '').strip() else ''
        task_sheet['rules_html'] = _rich_html_from_plain_text(confrontation_rules) if str(confrontation_rules or '').strip() else ''
    except Exception:
        pass
    players_count_estimate = _estimate_players_count(task_sheet.get('players'), text)
    players_band = _players_band_label(players_count_estimate)
    duration_band = _duration_band_label(minutes)
    reference_date = _detect_reference_date_in_text(text)

    analysis = {
        'title': _polish_spanish_text(_repair_joined_words_text((title or 'Tarea desde PDF')[:220]), multiline=False, max_len=160),
        'objective': _polish_spanish_text(_repair_joined_words_text(objective), multiline=True, max_len=8000),
        'minutes': minutes,
        'coaching_points': _polish_spanish_text(_repair_joined_words_text(coaching_points), multiline=True),
        'confrontation_rules': _polish_spanish_text(_repair_joined_words_text(confrontation_rules), multiline=True),
        'summary': _polish_spanish_text(_repair_joined_words_text(summary), multiline=True),
        'work_contexts': work_contexts,
        'objective_tags': objective_tags,
        'exercise_types': exercise_types,
        'phase_tags': phase_tags,
        'players_count_estimate': players_count_estimate,
        'players_band': players_band,
        'duration_band': duration_band,
        'detected_materials': detected_materials,
        'task_sheet': task_sheet,
        'pdf_template': template_key,
        'reference_date': reference_date.isoformat() if reference_date else '',
    }
    analysis['quality_score'] = _analysis_quality_score(analysis)
    return analysis


def _split_pdf_into_task_sections(pdf_text):
    text = str(pdf_text or '').strip()
    if not text:
        return []
    # Algunos PDFs concatenan "Tarea 1 Tarea 2 ..." en una sola línea: forzamos saltos para detectar boundaries.
    text = re.sub(
        r'(?i)(?<!^)(?<!\n)(?=\s*(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\b)',
        '\n',
        text,
    )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 6:
        return [text]

    start_patterns = [
        re.compile(r'^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*\d{1,2}\b', re.IGNORECASE),
        re.compile(r'^\d{1,2}\s*[\)\.\-]\s*(?:tarea|ejercicio|task|drill)\b', re.IGNORECASE),
        re.compile(r'^(?:task|drill)\s*\d{1,2}\b', re.IGNORECASE),
        re.compile(r'^(?:primera|segunda|tercera|cuarta)\s+tarea\b', re.IGNORECASE),
    ]

    boundaries = []
    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in start_patterns):
            boundaries.append(idx)

    # Elimina boundaries duplicados tipo "Tarea 3" repetido (cabeceras/pies de página).
    if boundaries:
        filtered = []
        prev_num = None
        prev_has_rest = False
        prev_idx = None
        for idx in boundaries:
            line = lines[idx]
            match = re.match(
                r'(?i)^(?:tarea|ejercicio|task|drill)\s*(?:n[\.\s]*[oº°])?\s*(\d{1,2})\b(.*)$',
                line,
            )
            num = int(match.group(1)) if match else None
            rest = (match.group(2) or '').strip() if match else ''
            has_rest = bool(rest.strip(' :.-'))
            if num and prev_num == num and prev_idx is not None:
                close = (idx - prev_idx) <= 8
                if close and prev_has_rest and not has_rest:
                    continue
            filtered.append(idx)
            prev_num = num
            prev_has_rest = has_rest
            prev_idx = idx
        boundaries = filtered

    if len(boundaries) < 2:
        objective_indices = []
        for idx, line in enumerate(lines):
            if re.match(r'^(?:objetivo|objective)\s*[:\-]', line, re.IGNORECASE):
                objective_indices.append(max(0, idx - 1))
        boundaries = sorted(set(objective_indices))

    if len(boundaries) < 2:
        return [text]

    sections = []
    seen = set()
    stop_keywords = (
        'estiramientos',
        'partefinal',
        'parte final',
        'tiempototaldesesion',
        'tiempo total de sesion',
        'observaciones',
        'ausentes',
        'lesionados',
    )
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
        if end <= start:
            continue
        chunk = '\n'.join(lines[start:end]).strip()
        folded = _normalize_folded_text(chunk)
        has_load_or_task_data = (
            'dosificacion' in folded
            or 'tiempototaldetrabajo' in folded
            or 'consignas' in folded
            or 'tarea' in folded
        )
        if any(word in folded for word in stop_keywords) and not has_load_or_task_data:
            continue
        normalized = _normalize_folded_text(chunk)
        if len(chunk) < 80 or normalized in seen:
            continue
        seen.add(normalized)
        sections.append(chunk)

    # Heuristic: añade el bloque previo (calentamiento/activación) si tiene carga/tiempos y queda antes de la 1ª tarea.
    if boundaries:
        prefix_lines = lines[: boundaries[0]]
        if prefix_lines:
            prefix_text = '\n'.join(prefix_lines).strip()
            prefix_folded = _normalize_folded_text(prefix_text)
            start_idx = None
            for idx, line in enumerate(prefix_lines):
                folded = _normalize_folded_text(line)
                if any(token in folded for token in ('acondicionamiento', 'calentamiento', 'activacion', 'activación', 'partepreparatoria', 'parte preparatoria')):
                    if start_idx is None:
                        start_idx = idx
            if start_idx is not None:
                candidate = '\n'.join(prefix_lines[start_idx:]).strip()
                # Si el PDF venía con cabecera en la misma línea, recorta desde el inicio del bloque preparatorio.
                trim_match = re.search(r'(?i)(acondicionamiento|calentamiento|activaci[oó]n)', candidate)
                if trim_match:
                    candidate = candidate[trim_match.start():].strip()
                cand_folded = _normalize_folded_text(candidate)
                if (
                    len(candidate) >= 220
                    and ('tiempodetrabajo' in cand_folded or re.search(r'\b\d{1,3}\s*[\'’`´]\b', candidate))
                    and 'tiempototaldesesion' not in cand_folded
                ):
                    # En PDFs de sesión, a veces el "pre" incluye 2 tareas: físico + activación (a menudo "con balón").
                    # Si detectamos un encabezado de Activación dentro del bloque preparatorio, lo separamos en dos secciones.
                    try:
                        activation_match = re.search(
                            r'(?i)(?:^|\n)\s*activaci[oó]n(?:\s+con\s+bal[oó]n)?\b',
                            candidate,
                        )
                    except Exception:
                        activation_match = None
                    if activation_match:
                        act_start = activation_match.start()
                        pre_folded = _normalize_folded_text(candidate[:act_start])
                        has_pre_conditioning = any(
                            token in pre_folded
                            for token in (
                                'acondicionamiento',
                                'calentamiento',
                                'movilidad',
                                'circuito',
                                'fuerza',
                                'elongacion',
                                'elongación',
                            )
                        )
                    else:
                        act_start = 0
                        has_pre_conditioning = False
                    if activation_match and has_pre_conditioning and act_start >= 80:
                        act_end = len(candidate)
                        try:
                            tail = candidate[act_start:]
                            cut_points = []
                            for pat in (r'(?i)\bparte\s+principal\b', r'(?i)\btrabajo\s+f[ií]sic'):
                                m = re.search(pat, tail)
                                if m and m.start() >= 40:
                                    cut_points.append(m.start())
                            # En algunos formatos la siguiente sección ya empieza como "Tarea 1".
                            m = re.search(r'(?i)\btarea\s*1\b', tail)
                            if m and m.start() >= 40:
                                cut_points.append(m.start())
                            if cut_points:
                                act_end = act_start + min(cut_points)
                        except Exception:
                            act_end = len(candidate)
                        activation_text = candidate[act_start:act_end].strip()
                        conditioning_text = (candidate[:act_start].strip() + '\n' + candidate[act_end:].strip()).strip()
                        if len(conditioning_text) >= 160 and len(activation_text) >= 120:
                            sections[0:0] = [conditioning_text, activation_text]
                        else:
                            sections.insert(0, candidate)
                    else:
                        sections.insert(0, candidate)

    # Heuristic for session sheets where "Tarea 1" is implicit and first explicit marker is Tarea 2.
    if sections:
        first_folded = _normalize_folded_text(sections[0])
        looks_like_second = any(token in first_folded for token in ('tarea2', 'tarea 2', 'segunda tarea'))
        has_first_marker = any(any(token in _normalize_folded_text(sec) for token in ('tarea1', 'tarea 1', 'primera tarea')) for sec in sections)
        if looks_like_second and not has_first_marker:
            prefix_lines = lines[:boundaries[0]]
            prefix_text = '\n'.join(prefix_lines)
            prefix_folded = _normalize_folded_text(prefix_text)
            if 'parteprincipal' in prefix_folded:
                idx = prefix_folded.rfind('parteprincipal')
                candidate = prefix_text[idx:].strip()
            else:
                candidate = '\n'.join(prefix_lines[-28:]).strip()
            candidate_folded = _normalize_folded_text(candidate)
            if (
                len(candidate) >= 140
                and ('dosificacion' in candidate_folded or 'tiempototaldetrabajo' in candidate_folded)
                and 'estiramientos' not in candidate_folded
            ):
                sections.insert(0, candidate)

    cleaned_sections = []
    for chunk in sections:
        folded = _normalize_folded_text(chunk)
        if any(word in folded for word in stop_keywords):
            if not ('dosificacion' in folded or 'tiempototaldetrabajo' in folded):
                continue
        cleaned_sections.append(chunk)
    sections = cleaned_sections

    if len(sections) < 2:
        return [text]
    return sections[:8]


def _extract_tasks_from_pdf_text(pdf_text, fallback_title='Tarea desde PDF'):
    sections = _split_pdf_into_task_sections(pdf_text)
    analyses = []
    for idx, section in enumerate(sections, start=1):
        analysis = _suggest_task_from_pdf(section)
        title = (analysis.get('title') or '').strip()
        if not title or title.lower() == 'tarea desde pdf':
            if len(sections) > 1:
                title = f'{fallback_title} · Tarea {idx}'
            else:
                title = fallback_title
            analysis['title'] = title[:160]
        analyses.append(
            {
                'analysis': analysis,
                'raw_text': section[:2500],
                'segment_index': idx,
                'segment_total': len(sections),
            }
        )
    return analyses


def _suggest_blocks_for_session_pdf_segments(parsed_tasks, fallback_block):
    """
    PDFs de "sesión" suelen contener varios bloques (condicionante/activación/principal 1/principal 2).
    Cuando detectamos ese patrón, devolvemos un listado de bloques por segmento para crear 1 tarea por bloque.
    """
    if not isinstance(parsed_tasks, list) or len(parsed_tasks) < 2:
        return None
    try:
        segments = []
        for item in parsed_tasks:
            if not isinstance(item, dict):
                continue
            analysis = item.get('analysis') if isinstance(item.get('analysis'), dict) else {}
            raw_text = str(item.get('raw_text') or '')
            joined = ' '.join(
                part for part in [
                    raw_text,
                    str(analysis.get('title') or ''),
                    str(analysis.get('objective') or ''),
                    str(analysis.get('summary') or ''),
                ] if part
            )
            segments.append(_normalize_folded_text(joined))
    except Exception:
        return None
    if len(segments) < 2:
        return None

    # Heurística: solo activamos "auto-bloques" si hay señales claras de sesión.
    is_sessionish = any('microciclo' in seg or 'mesociclo' in seg or 'materialdeentrenamiento' in seg for seg in segments[:2])
    has_activation_ball = any(('activacion' in seg and 'balon' in seg) for seg in segments[:3])
    has_conditioning = any(any(tok in seg for tok in ('acondicionamiento', 'trabajofisico', 'fuerza', 'metabol')) for seg in segments[:3])
    if not (is_sessionish or (has_activation_ball and has_conditioning)):
        return None

    blocks = []
    main_blocks = [SessionTask.BLOCK_MAIN_1, SessionTask.BLOCK_MAIN_2]
    next_main = 0
    for seg in segments:
        if any(tok in seg for tok in ('estiramientos', 'vueltaalacalma', 'partefinal', 'parte final', 'recuperacion', 'recuperación')):
            blocks.append(SessionTask.BLOCK_RECOVERY)
            continue
        if any(tok in seg for tok in ('acondicionamiento', 'trabajofisico', 'circuitofuerza', 'intermitente', 'metabol')):
            blocks.append(SessionTask.BLOCK_CONDITIONING)
            continue
        if 'activacion' in seg and ('balon' in seg or 'pases' in seg or 'rueda' in seg):
            blocks.append(SessionTask.BLOCK_ACTIVATION)
            continue
        if 'abp' in seg or 'balonparado' in seg or 'balónparado' in seg or 'corner' in seg or 'córner' in seg:
            blocks.append(SessionTask.BLOCK_SET_PIECES)
            continue
        if next_main < len(main_blocks):
            blocks.append(main_blocks[next_main])
            next_main += 1
            continue
        blocks.append(fallback_block)

    if len(set(blocks)) < 2:
        return None
    return blocks

