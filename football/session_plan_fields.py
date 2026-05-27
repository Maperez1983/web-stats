SESSION_PLAN_MARKER = '[2J_SESSION]'
SESSION_PLAN_KEYS = [
    'warmup',
    'activation',
    'main',
    'cooldown',
    'objective',
    'success_criteria',
    'rpe_target',
    'player_count',
    'location',
    'materials',
    'absences',
    'agenda_hidden',
    'confirmed_at',
    'confirmed_by',
    'performed_repo_copied',
    'notes',
]


def parse_session_plan_fields(raw_content):
    content = str(raw_content or '')
    defaults = {key: '' for key in SESSION_PLAN_KEYS}
    defaults['notes'] = content.strip()
    if not content.strip():
        return defaults
    if SESSION_PLAN_MARKER not in content:
        return defaults
    _, payload = content.split(SESSION_PLAN_MARKER, 1)
    parsed = {key: '' for key in SESSION_PLAN_KEYS}
    current_key = None
    free_lines = []
    allowed_keys = set(SESSION_PLAN_KEYS)
    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current_key:
                parsed[current_key] = (parsed.get(current_key, '') + '\n').strip('\n')
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            normalized = key.strip().lower()
            if normalized in allowed_keys:
                current_key = normalized
                parsed[current_key] = value.strip()
                continue
        if current_key:
            parsed[current_key] = '\n'.join(filter(None, [parsed.get(current_key, '').strip(), line.strip()])).strip()
        else:
            free_lines.append(line.strip())
    if free_lines and not parsed.get('notes'):
        parsed['notes'] = '\n'.join(free_lines).strip()
    return parsed


def serialize_session_plan_fields(fields):
    clean = {key: str((fields or {}).get(key) or '').strip() for key in SESSION_PLAN_KEYS}
    if not any(clean.values()):
        return ''
    lines = [SESSION_PLAN_MARKER]
    for key in SESSION_PLAN_KEYS:
        lines.append(f'{key}:{clean[key]}')
    return '\n'.join(lines).strip()
