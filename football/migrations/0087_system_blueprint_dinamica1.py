from django.db import migrations


def seed_system_blueprint_dinamica1(apps, schema_editor):
    Team = apps.get_model('football', 'Team')
    TaskBlueprint = apps.get_model('football', 'TaskBlueprint')

    # Equipo "sistema" usado como repositorio global de plantillas.
    system_team, _ = Team.objects.get_or_create(slug='pizarra', defaults={'name': 'PIZARRA'})

    name = 'DINÁMICA 1 · Iniciación (Salida + presión)'

    # Nota: texto inspirado en el formato de manual (caja + explicación),
    # pero redactado para uso interno sin copiar literal.
    description_html = (
        '<div><strong>Salida de balón + presión rival</strong></div>'
        '<div style="opacity:0.9; margin-top:0.25rem;">'
        'Objetivo: superar la primera presión y progresar con ventaja.'
        '</div>'
        '<ul>'
        '<li>Equipo en inicio: 2 centrales + 2 medios, portero como apoyo.</li>'
        '<li>Rivales: 4 presionantes (ajusta nº según edad/nivel).</li>'
        '<li>Gana punto si se supera línea de presión y se progresa con pase.</li>'
        '</ul>'
    )
    coaching_html = (
        '<ul>'
        '<li>Primer control orientado y perfil corporal antes de recibir.</li>'
        '<li>Genera triángulos de apoyo (dentro/fuera) y cambia orientación si aprietan.</li>'
        '<li>Si no hay pase, atrae y devuelve (tercer hombre).</li>'
        '</ul>'
    )
    rules_html = (
        '<ul>'
        '<li>Máx. 2 toques en iniciación (opcional).</li>'
        '<li>Tras robo, rival finaliza rápido a miniportería (transición).</li>'
        '<li>Reinicia con portero si sale el balón.</li>'
        '</ul>'
    )

    # Canvas_state (Fabric.js): solo piezas (la previsualización ya pone el campo de fondo).
    canvas_state = {
        "version": "5.3.0",
        "objects": [
            # Línea de presión (discontinua)
            {
                "type": "line",
                "left": 0,
                "top": 0,
                "x1": 240,
                "y1": 180,
                "x2": 1040,
                "y2": 180,
                "stroke": "rgba(248, 250, 252, 0.95)",
                "strokeWidth": 4,
                "strokeDashArray": [16, 12],
                "selectable": False,
                "evented": False,
            },
            # Equipo iniciación (verde)
            {"type": "circle", "left": 620, "top": 520, "radius": 16, "fill": "rgba(34,197,94,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 520, "top": 520, "radius": 16, "fill": "rgba(34,197,94,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 720, "top": 520, "radius": 16, "fill": "rgba(34,197,94,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 560, "top": 440, "radius": 16, "fill": "rgba(34,197,94,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 680, "top": 440, "radius": 16, "fill": "rgba(34,197,94,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            # Rivales presión (rojo)
            {"type": "circle", "left": 560, "top": 260, "radius": 16, "fill": "rgba(239,68,68,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 680, "top": 260, "radius": 16, "fill": "rgba(239,68,68,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 500, "top": 300, "radius": 16, "fill": "rgba(239,68,68,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            {"type": "circle", "left": 740, "top": 300, "radius": 16, "fill": "rgba(239,68,68,0.92)", "stroke": "rgba(15,23,42,0.35)", "strokeWidth": 2},
            # Balón
            {"type": "circle", "left": 620, "top": 560, "radius": 8, "fill": "rgba(248,250,252,0.96)", "stroke": "rgba(15,23,42,0.40)", "strokeWidth": 2},
        ],
    }

    tpl = {
        'title': 'Dinámica 1 · Iniciación',
        'objective': 'Salida bajo presión: progresar y evitar robo.',
        'minutes': 12,
        'block': 'activation',
        'player_count': '6v4 (+portero)',
        'dimensions': '1/2 campo',
        'materials': 'Balones, petos, 2 miniporterías (opcional)',
        'space': 'Medio campo',
        'training_type': 'Inicio y progresión',
        'strategy': '',
        'dynamics': 'Juego posicional',
        'structure': '',
        'coordination': '',
        'coordination_skills': '',
        'tactical_intent': '',
        'organization_html': '',
        'description_html': description_html,
        'coaching_html': coaching_html,
        'rules_html': rules_html,
        'progression_html': '<ul><li>Reduce toques o aumenta presión.</li><li>Añade comodín exterior para dar salida.</li></ul>',
        'regression_html': '<ul><li>Amplía espacio o elimina un presionante.</li></ul>',
        'success_criteria_html': '<ul><li>5 salidas limpias en 2 minutos.</li></ul>',
        'drills': [],
        'canvas_state': canvas_state,
        'canvas_width': 1280,
        'canvas_height': 720,
        'source_name': 'Manual (formato Dinámica)',
    }

    meta = {
        'v': 1,
        'goal': 'build_up',
        'subphase': 'init',
        'approach': 'auto',
        # Pista para el recomendador/UX: priorizar plantillas con pizarra.
        'has_board': True,
        'style': 'dynamics_boxed',
    }

    TaskBlueprint.objects.update_or_create(
        team=system_team,
        name=name,
        defaults={
            'category': 'build_up',
            'description': 'Plantilla tipo manual: salida de balón bajo presión.',
            'payload': {'meta': meta, 'tpl': tpl},
            'created_by': 'system_seed',
        },
    )


def unseed_system_blueprint_dinamica1(apps, schema_editor):
    Team = apps.get_model('football', 'Team')
    TaskBlueprint = apps.get_model('football', 'TaskBlueprint')
    system_team = Team.objects.filter(slug='pizarra').first()
    if not system_team:
        return
    TaskBlueprint.objects.filter(team=system_team, name='DINÁMICA 1 · Iniciación (Salida + presión)').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0086_trainingsession_timeline_segments'),
    ]

    operations = [
        migrations.RunPython(seed_system_blueprint_dinamica1, reverse_code=unseed_system_blueprint_dinamica1),
    ]

