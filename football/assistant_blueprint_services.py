import html
import re
import unicodedata
from pathlib import Path

from .models import SessionTask, TaskBlueprint
from . import task_library_services


def assistant_goal_specs():
    # Keywords mínimos para clasificar bullets a objetivos del Asistente.
    # No intenta ser perfecto; sirve para extraer ideas útiles de documentos subidos.
    return {
        'warmup': {
            'label': 'Calentamiento',
            'keywords': ['calent', 'activac', 'movil', 'prevenci', 'carrera', 'técnica de carrera', 'injury', 'warm up'],
            'category': TaskBlueprint.CATEGORY_PHYSICAL,
            'block': SessionTask.BLOCK_ACTIVATION,
        },
        'build_up': {
            'label': 'Salida de balón',
            'keywords': ['salida', 'portero', 'central', 'centrales', 'lateral', 'pivote', 'primer pase', 'reinicio', 'build up'],
            'category': TaskBlueprint.CATEGORY_BUILD,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'progression': {
            'label': 'Progresión',
            'keywords': [
                'progres', 'superar', 'línea', 'linea', 'romper', 'ruptura', 'line-breaking', 'romper líneas', 'romper lineas',
                'cambio de orientación', 'orientación', 'tercer hombre', 'entre líneas', 'between lines', 'switch',
                'carril interior', 'half space', 'intervalo', 'intervalos', 'perfil', 'perfilado', 'escalon',
                'fijar', 'soltar', 'apoyo', 'ángulo', 'angulo', 'apoyos',
            ],
            'category': TaskBlueprint.CATEGORY_BUILD,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'positional_play': {
            'label': 'Juego de posición',
            'keywords': [
                'juego de posición', 'juego de posicion', 'posicional', 'positional play', 'rondo', 'conservación', 'conservacion',
                'amplitud', 'profundidad', 'ocupación', 'ocupacion', 'altura', 'anchura', 'pasillo', 'carril',
                'tercer hombre', 'fijar', 'soltar', 'escalon', 'perfiles', 'perfilado', 'línea de pase', 'linea de pase',
            ],
            'category': TaskBlueprint.CATEGORY_BUILD,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'final_third': {
            'label': 'Último tercio / finalización',
            'keywords': ['finaliz', 'remate', 'tiro', 'disparo', 'centro', 'pase atrás', 'cutback', 'área', 'area', 'último tercio', 'final third'],
            'category': TaskBlueprint.CATEGORY_FINISH,
            'block': SessionTask.BLOCK_MAIN_2,
        },
        'pressing': {
            'label': 'Presión organizada',
            'keywords': ['presión', 'presion', 'press', 'trigger', 'triggers', 'orientar', 'cobertura', 'salt', 'sombra'],
            'category': TaskBlueprint.CATEGORY_PRESS,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'counterpress': {
            'label': 'Presión tras pérdida',
            'keywords': ['tras pérdida', 'tras perdida', 'pérdida', 'perdida', 'contra presión', 'contrapresión', '5s', '6s', 'counterpress'],
            'category': TaskBlueprint.CATEGORY_PRESS,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'defending': {
            'label': 'Defensa en bloque',
            'keywords': [
                'bloque', 'replieg', 'bascul', 'tempor', 'cerrar', 'líneas', 'lineas', 'coberturas', 'rest-defense', 'defend',
                'bloque alto', 'bloque medio', 'bloque bajo', 'compact', 'compacto', 'compactación', 'compactacion', 'distancias',
            ],
            'category': TaskBlueprint.CATEGORY_PRESS,
            'block': SessionTask.BLOCK_MAIN_1,
        },
        'transition_atd': {
            'label': 'Transición A→D',
            'keywords': ['transición ataque', 'transicion ataque', 'pérdida', 'perdida', 'reacción', 'reaccion', 'replegar', 'delay'],
            'category': TaskBlueprint.CATEGORY_TRANSITION,
            'block': SessionTask.BLOCK_MAIN_2,
        },
        'transition_dta': {
            'label': 'Transición D→A',
            'keywords': ['transición defensa', 'transicion defensa', 'recuper', 'contraataque', 'atacar espacio', 'first pass', 'counterattack'],
            'category': TaskBlueprint.CATEGORY_TRANSITION,
            'block': SessionTask.BLOCK_MAIN_2,
        },
        'duels': {
            'label': 'Duelos',
            'keywords': ['duelo', '1v1', '2v1', 'regate', 'entrada', 'tackle', 'protección', 'proteccion'],
            'category': TaskBlueprint.CATEGORY_FINISH,
            'block': SessionTask.BLOCK_MAIN_2,
        },
        'set_pieces': {
            'label': 'ABP',
            'keywords': ['abp', 'córner', 'corner', 'falta', 'saque de banda', 'kickoff', 'segundas jugadas', 'balón parado', 'balon parado'],
            'category': TaskBlueprint.CATEGORY_ABP,
            'block': SessionTask.BLOCK_SET_PIECES,
        },
        'coord': {
            'label': 'Coordinación / prevención',
            'keywords': ['coordin', 'prevenci', 'estabilidad', 'fuerza', 'core', 'equilibrio', 'balance', 'agilidad'],
            'category': TaskBlueprint.CATEGORY_PHYSICAL,
            'block': SessionTask.BLOCK_CONDITIONING,
        },
    }


def extract_assistant_bullets(text: str):
    lines = []
    try:
        raw_lines = str(text or '').splitlines()
    except Exception:
        raw_lines = []
    for raw in raw_lines:
        s = str(raw or '').strip()
        if not s:
            continue
        s = re.sub(r'\s+', ' ', s).strip()
        if len(s) < 8 or len(s) > 260:
            continue
        if re.match(r'^(\-|\•|\*|\–|\—|▪|■|▸|▶|✅|✔|☑)\s+', s) or re.match(r'^\d+(\.|\))\s+', s):
            s = re.sub(r'^(\-|\•|\*|\–|\—)\s+', '', s).strip()
            s = re.sub(r'^(▪|■|▸|▶|✅|✔|☑)\s+', '', s).strip()
            s = re.sub(r'^\d+(\.|\))\s+', '', s).strip()
            if s:
                lines.append(s)
                continue
        if len(s) <= 140 and any(ch in s for ch in ('.', ';', ':')) and not s.isupper():
            lines.append(s)
    seen = set()
    out = []
    for item in lines:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out[:800]


def pick_assistant_bullets_for_goal(bullets, keywords, limit=7):
    keys = [str(k or '').casefold() for k in (keywords or []) if str(k or '').strip()]
    picked = []
    for item in (bullets or []):
        low = str(item or '').casefold()
        if not low:
            continue
        if any(k in low for k in keys):
            picked.append(str(item).strip())
        if len(picked) >= limit:
            break
    if len(picked) < 3:
        return []
    return picked


def assistant_html_list(items):
    safe = [html.escape(str(v or '').strip()) for v in (items or []) if str(v or '').strip()]
    if not safe:
        return ''
    return '<ul>' + ''.join(f'<li>{item}</li>' for item in safe[:10]) + '</ul>'


def strip_accents(value: str) -> str:
    try:
        txt = str(value or '')
    except Exception:
        txt = ''
    if not txt:
        return ''
    try:
        norm = unicodedata.normalize('NFKD', txt)
    except Exception:
        return txt
    out = []
    for ch in norm:
        try:
            if unicodedata.category(ch) == 'Mn':
                continue
        except Exception:
            pass
        out.append(ch)
    return ''.join(out)


def normalize_ocr_line(value: str) -> str:
    try:
        raw = str(value or '')
    except Exception:
        raw = ''
    raw = strip_accents(raw).casefold()
    raw = (
        raw.replace('¢', 'c')
        .replace('©', 'c')
        .replace('ç', 'c')
        .replace('€', 'e')
        .replace('®', 'r')
        .replace('“', '"')
        .replace('”', '"')
        .replace('’', "'")
    )
    raw = re.sub(r'\s+', ' ', raw).strip()
    raw = re.sub(r'[\|·•]+', ' ', raw).strip()
    return raw


def split_assistant_sentences(text: str, limit: int = 12):
    out = []
    try:
        raw = str(text or '')
    except Exception:
        raw = ''
    raw = re.sub(r'\s+', ' ', raw).strip()
    if not raw:
        return out
    parts = re.split(r'(?<=[\.\;\:])\s+|\s+\-\s+|\s+\u2022\s+|\s+\•\s+', raw)
    for part in parts:
        item = str(part or '').strip(' -\t\r\n')
        if not item:
            continue
        item = re.sub(r'\s+', ' ', item).strip()
        if len(item) < 6 or len(item) > 220:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


def derive_compact_task_title(text: str) -> str:
    low = normalize_ocr_line(text)
    if not low:
        return ''
    match = re.search(r'\b(\d{1,2})\s*(c|vs)\s*(\d{1,2})\b', low)
    if not match:
        match = re.search(r'\b(\d{1,2})c(\d{1,2})\b', low)
    if not match:
        match = re.search(r'\b(\d{1,2})\s+(\d{1,2})\s+en\s+espacio\b', low)
    if not match:
        return ''
    try:
        first = int(match.group(1))
        if match.lastindex and match.lastindex >= 3 and match.group(3):
            second = int(match.group(3))
        else:
            second = int(match.group(2))
    except Exception:
        return ''

    try:
        start = max(0, int(match.start()) - 40)
        end = min(len(low), int(match.end()) + 120)
        ctx = low[start:end]
    except Exception:
        ctx = low

    plus_num = None
    try:
        plus_match = re.search(r'\+\s*(\d{1,2})\b', ctx)
        if plus_match:
            plus_num = int(plus_match.group(1))
    except Exception:
        plus_num = None

    suffix = ''
    if plus_num:
        suffix += f'+{plus_num}'
    if 'portero' in ctx or 'porteros' in ctx:
        suffix += '+porteros'
    if ('comodin' in ctx or 'comodines' in ctx or 'comodi' in ctx) and '+comod' not in suffix:
        suffix += '+comodines'

    out = (f'{first}c{second}' + suffix).strip('+')
    out = re.sub(r'[^0-9a-z\+]+', '', out)
    return out[:32]


def derive_task_theme(text: str) -> str:
    low = normalize_ocr_line(text)
    if not low:
        return ''
    if any(k in low for k in ('finalizacion', 'remate', 'gol', 'porteria', 'tiro', 'disparo')):
        return 'Finalización'
    if any(k in low for k in ('salida', 'progresion', 'organiza', 'inicio', 'construccion')):
        return 'Salida / progresión'
    if 'posesion' in low or 'conserva' in low:
        return 'Posesión'
    if any(k in low for k in ('presion', 'recuperacion', 'robo', 'intercepcion', 'perdida')):
        return 'Presión / recuperación'
    if 'transicion' in low:
        return 'Transición'
    if any(k in low for k in ('condicionante', 'fuerza', 'resistencia', 'velocidad', 'potencia')):
        return 'Condicionante físico'
    return ''


def extract_task_sheet_sections(text: str):
    lines = []
    try:
        raw_lines = str(text or '').splitlines()
    except Exception:
        raw_lines = []
    for raw in raw_lines:
        item = str(raw or '').strip()
        if not item:
            continue
        item = re.sub(r'\s+', ' ', item).strip()
        if len(item) < 2:
            continue
        if normalize_ocr_line(item).startswith('capitulo '):
            continue
        lines.append(item)
    if not lines:
        return {}

    headings = {
        'desc': [('descripcion',), ('desarrollo',), ('consigna',), ('explicacion',), ('reglas',)],
        'behaviors': [('tipo de comportamientos',), ('comportamientos preferenciados',), ('objetivos',)],
        'bio': [('caracteristicas',), ('bio',), ('condicionales',)],
        'considerations': [('consideraciones',), ('variantes',), ('consejos',)],
        'structural': [('condicionantes estructurales',), ('condicionantes', 'estructurales')],
        'provocation': [('reglas de provocacion',), ('reglas provocacion',)],
        'continuation': [('reglas de continuacion',), ('reglas continuacion',)],
        'info': [('jugadores',), ('espacio',), ('series',), ('duracion',), ('duracion',)],
    }
    indexes = {}
    norm_lines = [normalize_ocr_line(item) for item in lines]
    for key, variants in headings.items():
        for idx, low in enumerate(norm_lines):
            for words in variants:
                if all(word in low for word in words):
                    indexes[key] = idx
                    break
            if key in indexes:
                break

    compact = derive_compact_task_title('\n'.join(lines[:60]))
    theme = derive_task_theme('\n'.join(lines[:120]))
    if compact and theme:
        title = f'{compact} · {theme}'
    elif compact:
        title = compact
    else:
        title = ''
        for idx, item in enumerate(lines[:18]):
            letters = [ch for ch in item if ch.isalpha()]
            if len(letters) < 8:
                continue
            upper_ratio = sum(1 for ch in letters if ch.isupper()) / max(1, len(letters))
            low = normalize_ocr_line(item)
            if upper_ratio >= 0.78 or any(k in low for k in ('partido condicionado', 'tarea', 'ejercicio')):
                title = item
                if idx + 1 < len(lines):
                    nxt = str(lines[idx + 1] or '').strip()
                    nxt_low = normalize_ocr_line(nxt)
                    if nxt and len(nxt) <= 90 and (
                        nxt_low.startswith('para ')
                        or nxt_low.startswith('para trabajar')
                        or nxt_low.startswith('objetivo')
                    ):
                        title = f'{title} · {nxt}'
                break
        if not title:
            for item in lines[:12]:
                low = normalize_ocr_line(item)
                if re.search(r'\b\d+\s*(c|vs)\s*\d+\b', low) or 'portero' in low or 'mini' in low:
                    title = item
                    break
        if not title:
            title = lines[0]
    title = task_library_services.sanitize_task_text(title, multiline=False, max_len=90)

    def grab(start_key, end_keys):
        if start_key not in indexes:
            return []
        start = int(indexes[start_key]) + 1
        ends = [int(indexes[key]) for key in end_keys if key in indexes and int(indexes[key]) > int(indexes[start_key])]
        end = min(ends) if ends else len(lines)
        chunk = [value for value in lines[start:end] if value.strip()]
        if chunk and normalize_ocr_line(chunk[0]) == normalize_ocr_line(title):
            chunk = chunk[1:]
        return chunk

    return {
        'title': title,
        'desc': grab('desc', ['behaviors', 'bio', 'considerations', 'structural']),
        'behaviors': grab('behaviors', ['bio', 'considerations', 'structural']),
        'bio': grab('bio', ['considerations', 'structural']),
        'considerations': grab('considerations', ['structural']),
        'structural': grab('structural', []),
        'provocation': grab('provocation', ['continuation', 'behaviors', 'considerations', 'info', 'structural']),
        'continuation': grab('continuation', ['behaviors', 'considerations', 'info', 'structural']),
        'info': grab('info', ['behaviors', 'considerations']),
        'raw_lines': lines[:220],
    }


def guess_category_from_text(text: str) -> str:
    low = normalize_ocr_line(text)
    if any(k in low for k in ('finalizacion', 'remate', 'gol', 'porteria', 'tiro', 'disparo')):
        return TaskBlueprint.CATEGORY_FINISH
    if any(k in low for k in ('presion', 'recuperacion', 'robo', 'intercepcion')):
        return TaskBlueprint.CATEGORY_PRESS
    if 'transicion' in low:
        return TaskBlueprint.CATEGORY_TRANSITION
    if any(k in low for k in ('salida', 'progresion', 'construccion', 'inicio y progresion')):
        return TaskBlueprint.CATEGORY_BUILD
    if any(k in low for k in ('condicionante', 'fuerza', 'resistencia', 'velocidad', 'potencia')):
        return TaskBlueprint.CATEGORY_PHYSICAL
    if 'portero' in low:
        return TaskBlueprint.CATEGORY_GK
    return TaskBlueprint.CATEGORY_OTHER


def infer_goal_key_from_text(text: str, category_hint: str = '') -> str:
    haystack = normalize_ocr_line(text or '')
    best_key = ''
    best_score = 0
    for goal_key, spec in (assistant_goal_specs() or {}).items():
        hits = 0
        for keyword in spec.get('keywords') or []:
            normalized_keyword = normalize_ocr_line(str(keyword or ''))
            if normalized_keyword and normalized_keyword in haystack:
                hits += 1
        score = hits * 100
        try:
            if category_hint and str(spec.get('category') or '') == str(category_hint):
                score += 30
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best_key = goal_key

    if best_score < 200:
        category = str(category_hint or '').strip()
        if category == TaskBlueprint.CATEGORY_BUILD:
            return 'build_up'
        if category == TaskBlueprint.CATEGORY_PRESS:
            return 'pressing'
        if category == TaskBlueprint.CATEGORY_TRANSITION:
            return 'transition_atd'
        if category == TaskBlueprint.CATEGORY_ABP:
            return 'set_pieces'
        if category == TaskBlueprint.CATEGORY_PHYSICAL:
            return 'warmup'
        return 'auto'

    return best_key or 'auto'


def create_idea_blueprints_from_document(team, doc):
    created = 0
    updated = 0
    text = str(getattr(doc, 'extracted_text', '') or '')
    bullets = extract_assistant_bullets(text)
    if not bullets:
        return {'created': 0, 'updated': 0, 'skipped': 0}

    for goal_key, spec in assistant_goal_specs().items():
        picked = pick_assistant_bullets_for_goal(bullets, spec.get('keywords') or [])
        if not picked:
            continue
        label = str(spec.get('label') or goal_key).strip()
        name = f'{doc.title} · {label} · ideas'
        name = task_library_services.sanitize_task_text(name, multiline=False, max_len=160)
        if not name:
            continue
        tpl = {
            'title': f'{label} · ideas clave',
            'objective': picked[0][:8000] if picked else '',
            'minutes': 12,
            'block': str(spec.get('block') or SessionTask.BLOCK_MAIN_1),
            'training_type': label,
            'coaching_html': assistant_html_list(picked),
            'rules_html': '',
            'source_name': 'Documento del equipo',
        }
        payload = {
            'tpl': tpl,
            'meta': {
                'v': 1,
                'goal': goal_key,
                'subphase': 'auto',
                'approach': 'auto',
                'source_doc_id': int(doc.id),
            },
        }
        category = str(spec.get('category') or TaskBlueprint.CATEGORY_OTHER)
        try:
            _, was_created = TaskBlueprint.objects.update_or_create(
                team=team,
                name=name,
                defaults={
                    'category': category,
                    'description': task_library_services.sanitize_task_text(
                        f'Generado desde documento: {doc.title}',
                        multiline=False,
                        max_len=220,
                    ),
                    'payload': payload,
                    'created_by': 'assistant_docs',
                },
            )
        except Exception:
            continue
        if was_created:
            created += 1
        else:
            updated += 1

    return {'created': created, 'updated': updated, 'skipped': 0}


def create_blueprints_from_document(
    team,
    doc,
    pitch_diagram_score_func=None,
    canvas_state_func=None,
):
    text = str(getattr(doc, 'extracted_text', '') or '')
    if not text.strip():
        return {'created': 0, 'updated': 0, 'skipped': 0}

    lower_title = str(getattr(doc, 'title', '') or '').lower()
    mime = str(getattr(doc, 'mime_type', '') or '').lower()
    is_image = bool(
        mime.startswith('image/')
        or lower_title.endswith('.png')
        or lower_title.endswith('.jpg')
        or lower_title.endswith('.jpeg')
        or lower_title.endswith('.heic')
        or lower_title.endswith('.webp')
    )

    if is_image:
        raw_bytes = _read_document_file_bytes(doc)
        diagram_bytes = b''
        if raw_bytes and pitch_diagram_score_func is not None:
            try:
                if float(pitch_diagram_score_func(raw_bytes) or 0.0) >= 0.28:
                    diagram_bytes = raw_bytes
            except Exception:
                diagram_bytes = b''
        result = create_task_sheet_blueprint_from_document(
            team,
            doc,
            text,
            diagram_bytes=diagram_bytes,
            diagram_doc_id=int(getattr(doc, 'id', 0) or 0),
            pitch_diagram_score_func=pitch_diagram_score_func,
            canvas_state_func=canvas_state_func,
        )
        if int(result.get('created', 0) or 0) or int(result.get('updated', 0) or 0):
            return {
                'created': int(result.get('created', 0) or 0),
                'updated': int(result.get('updated', 0) or 0),
                'skipped': 0,
            }

    return create_idea_blueprints_from_document(team, doc)


def create_task_sheet_blueprint_from_document(
    team,
    doc,
    text: str,
    diagram_bytes: bytes = b'',
    diagram_doc_id: int = 0,
    pitch_diagram_score_func=None,
    canvas_state_func=None,
):
    def first_match(patterns: list[str], raw: str) -> str:
        for pattern in patterns:
            try:
                match = re.search(pattern, raw, flags=re.IGNORECASE)
            except Exception:
                match = None
            if match:
                try:
                    return str(match.group(1) or '').strip()
                except Exception:
                    return ''
        return ''

    sections = extract_task_sheet_sections(text)
    title = str(sections.get('title') or '').strip()
    if not title or len(title) < 6:
        return {'created': 0, 'updated': 0}

    raw_lines = sections.get('raw_lines') or []
    desc_lines = sections.get('desc') or []
    beh_lines = sections.get('behaviors') or []
    cons_lines = sections.get('considerations') or []
    struct_lines = sections.get('structural') or []
    prov_lines = sections.get('provocation') or []
    cont_lines = sections.get('continuation') or []
    info_lines = sections.get('info') or []

    raw_all = str(text or '')
    raw_norm = normalize_ocr_line(raw_all)

    if not desc_lines and raw_lines:
        title_norm = normalize_ocr_line(title)
        idx_title = None
        for idx, line in enumerate(raw_lines[:120]):
            if title_norm and normalize_ocr_line(str(line or '')) == title_norm:
                idx_title = idx
                break
        if idx_title is None:
            idx_title = 0
        try:
            desc_lines = [str(v or '').strip() for v in raw_lines[idx_title + 1: idx_title + 20] if str(v or '').strip()]
        except Exception:
            desc_lines = []

    players_raw = first_match(
        [
            r'jugadores\s*[:\-]?\s*([0-9]{1,2}\s*\+\s*[0-9]{1,2}\s*[a-z]{0,3})',
            r'jugadores\s*[:\-]?\s*([0-9]{1,2}\s*\+\s*[0-9]{1,2}\s*p)',
        ],
        raw_norm,
    )
    space_raw = first_match([r'espacio\s*[:\-]?\s*([0-9]{1,3}\s*[xX]\s*[0-9]{1,3})'], raw_all)
    series_raw = first_match([r'series\s*[:\-]?\s*([0-9]{1,2}\s*[xX]\s*[0-9]{1,2}\s*(\(\s*[0-9]{1,2}\s*\))?)'], raw_all)
    duration_raw = first_match([r'duraci[oó]n\s*[:\-]?\s*([0-9]{1,3})'], raw_all)

    try:
        joined_info = ' \n'.join([str(v or '') for v in info_lines[:40]])
    except Exception:
        joined_info = ''
    if not players_raw:
        players_raw = first_match([r'jugadores\s*([0-9]{1,2}\s*\+\s*[0-9]{1,2}\s*[a-z]{0,3})'], joined_info)
    if not space_raw:
        space_raw = first_match([r'espacio\s*([0-9]{1,3}\s*[xX]\s*[0-9]{1,3})'], joined_info)
    if not series_raw:
        series_raw = first_match([r'series\s*([0-9]{1,2}\s*[xX]\s*[0-9]{1,2}\s*(\(\s*[0-9]{1,2}\s*\))?)'], joined_info)
    if not duration_raw:
        duration_raw = first_match([r'duraci[oó]n\s*([0-9]{1,3})'], joined_info)

    sanitize = task_library_services.sanitize_task_text
    player_count = sanitize(players_raw, multiline=False, max_len=40) if players_raw else ''
    dimensions = sanitize(space_raw.replace('X', 'x').replace(' ', ''), multiline=False, max_len=24) if space_raw else ''
    series = sanitize(series_raw.replace('X', 'x').replace(' ', ''), multiline=False, max_len=40) if series_raw else ''
    try:
        minutes_val = int(re.sub(r'[^0-9]+', '', duration_raw or '') or 0)
    except Exception:
        minutes_val = 0
    minutes_val = minutes_val if 3 <= minutes_val <= 180 else 12

    objective_bullets = extract_assistant_bullets('\n'.join(beh_lines))
    if not objective_bullets and 'objetivo' in raw_norm:
        objective_bullets = extract_assistant_bullets(raw_all)
    objective_src = ' · '.join(objective_bullets[:2]).strip() or ' '.join(beh_lines[:2]).strip() or ' '.join(desc_lines[:2]).strip() or title
    objective = sanitize(objective_src, multiline=False, max_len=8000)

    coaching_items = []
    coaching_items.extend(split_assistant_sentences(' '.join(cons_lines), limit=8))
    coaching_items.extend(split_assistant_sentences(' '.join(beh_lines), limit=6))
    coaching_items = coaching_items[:10]

    description_items = []
    description_items.extend(split_assistant_sentences(' '.join(desc_lines), limit=12))
    if not description_items:
        description_items.extend(split_assistant_sentences(' '.join(struct_lines), limit=10))
    description_items = description_items[:12]

    rules_items = []
    rules_items.extend(split_assistant_sentences(' '.join(prov_lines), limit=10))
    rules_items.extend(split_assistant_sentences(' '.join(cont_lines), limit=10))
    if not rules_items:
        rules_items.extend(split_assistant_sentences(' '.join(struct_lines), limit=10))
    rules_items = rules_items[:12]

    text_for_infer = '\n'.join([title] + list(desc_lines[:40]) + list(beh_lines[:30]) + list(cons_lines[:30]) + list(struct_lines[:30]))
    category = guess_category_from_text(text_for_infer or text)
    goal_key = infer_goal_key_from_text(text_for_infer or text, category_hint=category)
    training_type = {
        TaskBlueprint.CATEGORY_FINISH: 'Finalización',
        TaskBlueprint.CATEGORY_BUILD: 'Inicio y progresión',
        TaskBlueprint.CATEGORY_PRESS: 'Presión y recuperación',
        TaskBlueprint.CATEGORY_TRANSITION: 'Transiciones',
        TaskBlueprint.CATEGORY_GK: 'Porteros',
        TaskBlueprint.CATEGORY_PHYSICAL: 'Condicionante físico',
    }.get(category, 'Otros')

    stem = Path(str(getattr(doc, 'title', '') or '')).stem.strip()
    stem = sanitize(stem, multiline=False, max_len=40)
    name = f'{stem} · {title}' if stem else title
    name = sanitize(f'{name} · ficha (doc {int(doc.id)})', multiline=False, max_len=160)
    if not name:
        return {'created': 0, 'updated': 0}

    tpl = {
        'title': title,
        'objective': objective,
        'minutes': minutes_val,
        'block': SessionTask.BLOCK_MAIN_2 if category == TaskBlueprint.CATEGORY_FINISH else SessionTask.BLOCK_MAIN_1,
        'training_type': training_type,
        **({'player_count': player_count} if player_count else {}),
        **({'dimensions': f'{dimensions} m' if dimensions and not dimensions.lower().endswith('m') else dimensions} if dimensions else {}),
        **({'series': series} if series else {}),
        'description_html': assistant_html_list(description_items),
        'coaching_html': assistant_html_list(coaching_items),
        'rules_html': assistant_html_list(rules_items),
        'source_name': 'Foto (OCR)',
    }

    diagram_doc_id_clean = int(diagram_doc_id or 0)
    if diagram_bytes and pitch_diagram_score_func is not None and canvas_state_func is not None:
        try:
            if float(pitch_diagram_score_func(diagram_bytes) or 0.0) >= 0.28:
                canvas_state, canvas_w, canvas_h = canvas_state_func(diagram_bytes)
                if canvas_state and canvas_w and canvas_h:
                    tpl['canvas_state'] = canvas_state
                    tpl['canvas_width'] = int(canvas_w)
                    tpl['canvas_height'] = int(canvas_h)
                    tpl['source_name'] = 'Foto (OCR + diagrama)'
                    if diagram_doc_id_clean <= 0:
                        diagram_doc_id_clean = int(getattr(doc, 'id', 0) or 0)
        except Exception:
            pass

    payload = {
        'tpl': tpl,
        'meta': {
            'v': 1,
            'goal': goal_key or 'auto',
            'subphase': 'auto',
            'approach': 'auto',
            'source_doc_id': int(doc.id),
            'kind': 'task_sheet',
            **({'diagram_doc_id': diagram_doc_id_clean} if int(diagram_doc_id_clean or 0) > 0 else {}),
        },
    }
    try:
        _, was_created = TaskBlueprint.objects.update_or_create(
            team=team,
            name=name,
            defaults={
                'category': category,
                'description': sanitize(f'Generado por OCR desde: {doc.title}', multiline=False, max_len=220),
                'payload': payload,
                'created_by': 'assistant_docs_ocr',
            },
        )
    except Exception:
        return {'created': 0, 'updated': 0}
    return {'created': 1 if was_created else 0, 'updated': 0 if was_created else 1}


def _read_document_file_bytes(doc) -> bytes:
    try:
        file_obj = getattr(doc, 'file', None)
        if not file_obj:
            return b''
        try:
            file_obj.open('rb')
        except Exception:
            pass
        try:
            return file_obj.read() or b''
        except Exception:
            return b''
    except Exception:
        return b''
