import base64
import json
import os
import urllib.error
import urllib.request


DEFAULT_OLLAMA_URL = 'http://127.0.0.1:11434'
DEFAULT_QWEN_MODEL = 'qwen3:1.7b'
DEFAULT_VISION_MODELS = (
    'llama3.2-vision',
    'qwen2.5-vl',
    'minicpm-v',
)


def local_llm_config():
    provider = str(os.getenv('AI_TRAINER_LOCAL_LLM_PROVIDER') or 'ollama').strip().lower()
    enabled = str(os.getenv('AI_TRAINER_LOCAL_LLM_ENABLED') or '1').strip().lower() not in {'0', 'false', 'no', 'off'}
    model = str(os.getenv('AI_TRAINER_LOCAL_LLM_MODEL') or os.getenv('OLLAMA_MODEL') or DEFAULT_QWEN_MODEL).strip() or DEFAULT_QWEN_MODEL
    base_url = str(os.getenv('AI_TRAINER_OLLAMA_URL') or DEFAULT_OLLAMA_URL).strip().rstrip('/') or DEFAULT_OLLAMA_URL
    timeout = 45
    try:
        timeout = max(2, min(int(os.getenv('AI_TRAINER_LOCAL_LLM_TIMEOUT') or 45), 120))
    except Exception:
        timeout = 45
    return {
        'enabled': enabled,
        'provider': provider,
        'model': model,
        'base_url': base_url,
        'timeout': timeout,
    }


def local_vision_models():
    raw = str(
        os.getenv('AI_TRAINER_LOCAL_VISION_MODELS')
        or os.getenv('OLLAMA_VISION_MODELS')
        or os.getenv('OLLAMA_IMAGE_MODELS')
        or ''
    ).strip()
    if raw:
        models = [str(item).strip() for item in raw.split(',')]
        models = [item for item in models if item]
        if models:
            return models[:5]
    return list(DEFAULT_VISION_MODELS)


def _compact_list(items, *, limit=8, max_len=220):
    out = []
    for item in items or []:
        text = str(item or '').strip()
        if not text:
            continue
        out.append(text[:max_len])
        if len(out) >= int(limit or 8):
            break
    return out


def _json_from_text(text):
    raw = str(text or '').strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except Exception:
            return None
    return None


def build_ai_trainer_context(*, team_name, profile, phase, goal, signals, club_model, learning_memory, suggestions, proposals, web_research=None):
    def _signal_labels(key):
        rows = signals.get(key) if isinstance(signals, dict) and isinstance(signals.get(key), list) else []
        return _compact_list([row.get('label') for row in rows if isinstance(row, dict)], limit=10, max_len=120)

    model = club_model if isinstance(club_model, dict) else {}
    suggested_tasks = []
    for task in suggestions or []:
        suggested_tasks.append(
            {
                'id': int(getattr(task, 'id', 0) or 0),
                'title': str(getattr(task, 'title', '') or '')[:160],
                'objective': str(getattr(task, 'objective', '') or '')[:500],
                'block': str(getattr(task, 'get_block_display', lambda: '')() or ''),
                'minutes': int(getattr(task, 'duration_minutes', 0) or 0),
                'score': int(getattr(task, 'ai_trainer_score', 0) or 0),
            }
        )
        if len(suggested_tasks) >= 8:
            break

    return {
        'team': str(team_name or '')[:120],
        'profile': str(profile or '')[:80],
        'phase': str(phase or '')[:80],
        'goal': str(goal or '')[:1200],
        'detected': {
            'principles': _signal_labels('principles'),
            'zones': _signal_labels('zones'),
            'phases': _signal_labels('phases'),
            'figures': _signal_labels('figures'),
        },
        'game_model': {
            'style': str(model.get('style') or '')[:80],
            'pressing': str(model.get('pressing') or '')[:80],
            'build_up': str(model.get('build_up') or '')[:80],
            'attack_principles': _compact_list(model.get('attack_principles') if isinstance(model.get('attack_principles'), list) else [], limit=8),
            'defense_principles': _compact_list(model.get('defense_principles') if isinstance(model.get('defense_principles'), list) else [], limit=8),
            'transition_principles': _compact_list(model.get('transition_principles') if isinstance(model.get('transition_principles'), list) else [], limit=8),
            'behavior_rules': _compact_list(model.get('behavior_rules') if isinstance(model.get('behavior_rules'), list) else [], limit=8),
        },
        'learning_memory': learning_memory if isinstance(learning_memory, dict) else {},
        'external_web_research': web_research if isinstance(web_research, list) else [],
        'candidate_tasks': suggested_tasks,
        'rule_proposals': [
            {
                'variant': str(p.get('variant') or '')[:20],
                'subtitle': str(p.get('subtitle') or '')[:160],
                'title': str(p.get('title') or '')[:180],
                'blocks': [
                    {
                        'title': str(b.get('title') or '')[:120],
                        'minutes': int(b.get('minutes') or 0),
                        'body': str(b.get('body') or '')[:260],
                    }
                    for b in (p.get('blocks') if isinstance(p.get('blocks'), list) else [])[:6]
                    if isinstance(b, dict)
                ],
            }
            for p in (proposals or [])[:3]
            if isinstance(p, dict)
        ],
    }


def build_ai_trainer_prompt(context):
    payload = json.dumps(context or {}, ensure_ascii=False, separators=(',', ':'))
    return (
        'Eres un entrenador senior de fútbol y preparador metodológico. '
        'Debes ayudar a planificar microciclos, sesiones y tareas con periodización táctica. '
        'No inventes datos externos. Usa solo el contexto recibido y si falta información, dilo como cautela. '
        'Si external_web_research contiene fuentes ok=true, úsalo como información web aportada por el sistema, '
        'citando la fuente por título o dominio cuando afecte a una recomendación. '
        'Si una fuente tiene ok=false, ignórala salvo para advertir que no pudo consultarse. '
        'Devuelve SOLO JSON válido con estas claves: '
        'summary:string, load_plan:list, task_recommendations:list, warnings:list, next_questions:list, source_notes:list. '
        'load_plan: máximo 5 items con {day, load, focus, reason}. '
        'task_recommendations: máximo 5 items con {title, why, load, adaptation}. '
        'warnings: máximo 4 strings. next_questions: máximo 3 strings. source_notes: máximo 4 strings. '
        'Sé concreto, en español, práctico y orientado a entrenador.\n\n'
        f'CONTEXTO_JSON={payload}'
    )


def call_ollama_json(prompt, *, model=None, base_url=None, timeout=8):
    model = str(model or os.getenv('OLLAMA_MODEL') or DEFAULT_QWEN_MODEL).strip() or DEFAULT_QWEN_MODEL
    base_url = str(base_url or DEFAULT_OLLAMA_URL).strip().rstrip('/') or DEFAULT_OLLAMA_URL
    body = {
        'model': model,
        'prompt': str(prompt or ''),
        'stream': False,
        'format': 'json',
        'options': {
            'temperature': 0.25,
            'num_ctx': 8192,
        },
    }
    req = urllib.request.Request(
        f'{base_url}/api/generate',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=max(2, int(timeout or 8))) as resp:
            data = json.loads(resp.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8')[:300]
        except Exception:
            detail = ''
        return None, f'ollama_http_{exc.code}:{detail}'
    except Exception as exc:
        return None, f'ollama_unavailable:{exc}'

    response = str(data.get('response') or '').strip() if isinstance(data, dict) else ''
    parsed = _json_from_text(response)
    if not isinstance(parsed, dict):
        return None, 'ollama_invalid_json'
    return parsed, ''


def call_ollama_vision_json(prompt, image_bytes, *, model=None, models=None, base_url=None, timeout=8):
    candidates = []
    if model:
        candidates.append(str(model).strip())
    for item in list(models or local_vision_models()):
        text = str(item or '').strip()
        if text and text not in candidates:
            candidates.append(text)
    if not candidates:
        candidates = list(DEFAULT_VISION_MODELS)
    base_url = str(base_url or DEFAULT_OLLAMA_URL).strip().rstrip('/') or DEFAULT_OLLAMA_URL
    image_payload = base64.b64encode(bytes(image_bytes or b'')).decode('ascii')
    last_error = 'ollama_invalid_json'
    for candidate in candidates[:5]:
        body = {
            'model': candidate,
            'prompt': str(prompt or ''),
            'stream': False,
            'format': 'json',
            'images': [image_payload],
            'options': {
                'temperature': 0.2,
                'num_ctx': 8192,
            },
        }
        req = urllib.request.Request(
            f'{base_url}/api/generate',
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=max(2, int(timeout or 8))) as resp:
                data = json.loads(resp.read().decode('utf-8') or '{}')
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8')[:300]
            except Exception:
                detail = ''
            last_error = f'ollama_http_{exc.code}:{detail}'
            continue
        except Exception as exc:
            last_error = f'ollama_unavailable:{exc}'
            continue

        response = str(data.get('response') or '').strip() if isinstance(data, dict) else ''
        parsed = _json_from_text(response)
        if isinstance(parsed, dict):
            parsed['model'] = candidate
            return parsed, ''
        last_error = 'ollama_invalid_json'
    return None, last_error


def ai_trainer_senior_local_advice(*, team_name, profile, phase, goal, signals, club_model, learning_memory=None, suggestions, proposals, web_research=None):
    cfg = local_llm_config()
    if not cfg.get('enabled'):
        return {
            'enabled': False,
            'provider': cfg.get('provider'),
            'model': cfg.get('model'),
            'available': False,
            'error': 'disabled',
            'advice': None,
        }
    if cfg.get('provider') != 'ollama':
        return {
            'enabled': True,
            'provider': cfg.get('provider'),
            'model': cfg.get('model'),
            'available': False,
            'error': 'unsupported_provider',
            'advice': None,
        }
    context = build_ai_trainer_context(
        team_name=team_name,
        profile=profile,
        phase=phase,
        goal=goal,
        signals=signals,
        club_model=club_model,
        learning_memory=learning_memory if isinstance(learning_memory, dict) else {},
        suggestions=suggestions,
        proposals=proposals,
        web_research=web_research if isinstance(web_research, list) else [],
    )
    parsed, error = call_ollama_json(
        build_ai_trainer_prompt(context),
        model=cfg.get('model'),
        base_url=cfg.get('base_url'),
        timeout=cfg.get('timeout'),
    )
    return {
        'enabled': True,
        'provider': cfg.get('provider'),
        'model': cfg.get('model'),
        'base_url': cfg.get('base_url'),
        'available': bool(isinstance(parsed, dict)),
        'error': str(error or ''),
        'advice': parsed if isinstance(parsed, dict) else None,
    }
