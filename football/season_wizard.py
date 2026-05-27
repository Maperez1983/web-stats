QUESTIONNAIRE_RATING_GROUPS = [
    {
        'key': 'technical',
        'label': 'Técnica',
        'fields': [
            ('ball_control', 'Control de balón'),
            ('pass_control', 'Control de pase'),
            ('pass_distance', 'Distancia de pase'),
            ('coordination', 'Coordinación'),
            ('dribbling', 'Regate'),
        ],
    },
    {
        'key': 'tactical',
        'label': 'Táctica',
        'fields': [
            ('game_knowledge', 'Conocimiento del juego'),
            ('order', 'Orden'),
            ('positioning', 'Posicionamiento'),
        ],
    },
    {
        'key': 'physical',
        'label': 'Físico',
        'fields': [
            ('striking', 'Golpeo'),
            ('body_contact', 'Cuerpeo'),
            ('endurance', 'Resistencia'),
            ('speed', 'Velocidad'),
        ],
    },
    {
        'key': 'attitude',
        'label': 'Actitud',
        'fields': [
            ('behavior', 'Comportamiento'),
            ('bravery', 'Valentía'),
            ('extroversion', 'Extroversión'),
            ('obedience', 'Obediencia'),
        ],
    },
]


def questionnaire_category_for_average(avg):
    try:
        value = float(avg)
    except Exception:
        return ''
    if value >= 4.5:
        return 'Categoría superior / jugador diferencial'
    if value >= 3.8:
        return 'Categoría alta'
    if value >= 3.0:
        return 'Categoría actual consolidada'
    if value >= 2.2:
        return 'Categoría actual con plan de mejora'
    return 'Categoría de desarrollo'


def parse_rating_0_5(value):
    raw = '' if value is None else str(value).strip()
    if raw == '':
        return None
    try:
        return max(0, min(5, int(raw)))
    except Exception:
        return None


def parse_questionnaire_ratings(post_data):
    ratings = {}
    for group in QUESTIONNAIRE_RATING_GROUPS:
        for field_key, _field_label in group['fields']:
            value = parse_rating_0_5(post_data.get(f'q_rating_{field_key}') if post_data else None)
            if value is not None:
                ratings[field_key] = int(value)
    return ratings


def build_questionnaire_rating_summary(questionnaire):
    data = questionnaire if isinstance(questionnaire, dict) else {}
    ratings = data.get('ratings') if isinstance(data.get('ratings'), dict) else {}
    groups = []
    all_values = []
    for group in QUESTIONNAIRE_RATING_GROUPS:
        items = []
        values = []
        for field_key, field_label in group['fields']:
            value = parse_rating_0_5(ratings.get(field_key))
            if value is not None:
                values.append(value)
                all_values.append(value)
            items.append({
                'key': field_key,
                'label': field_label,
                'value': value,
                'options': [
                    {'value': score, 'selected': value == score}
                    for score in range(0, 6)
                ],
            })
        avg = round(sum(values) / len(values), 2) if values else None
        groups.append({
            'key': group['key'],
            'label': group['label'],
            'items': items,
            'average': avg,
            'average_display': f'{avg:.2f}' if avg is not None else '-',
        })
    overall = round(sum(all_values) / len(all_values), 2) if all_values else None
    return {
        'groups': groups,
        'overall': overall,
        'overall_display': f'{overall:.2f}' if overall is not None else '-',
        'category': questionnaire_category_for_average(overall),
        'chart_labels': [group['label'] for group in groups],
        'chart_values': [float(group['average'] or 0) for group in groups],
    }
