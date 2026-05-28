import html
import re

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
