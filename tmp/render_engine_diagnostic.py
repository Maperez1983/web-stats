from pathlib import Path
from html import escape
import json

from football.models import SessionTask, TrainingSession
from football.render_engine import build_task_render_bundle

CANVAS_W = 1054
CANVAS_H = 684
OUT_PATH = Path('tmp/ficha_test_render_engine.html')


def circle(left, top, radius, fill, stroke='#ffffff', stroke_width=3):
    return {
        'type': 'circle',
        'left': left,
        'top': top,
        'radius': radius,
        'fill': fill,
        'stroke': stroke,
        'strokeWidth': stroke_width,
    }


def rect(left, top, width, height, fill, stroke='#ffffff', stroke_width=2):
    return {
        'type': 'rect',
        'left': left,
        'top': top,
        'width': width,
        'height': height,
        'scaleX': 1,
        'scaleY': 1,
        'fill': fill,
        'stroke': stroke,
        'strokeWidth': stroke_width,
    }


def line(points, stroke='#facc15', stroke_width=4):
    return {
        'type': 'line',
        'points': [{'x': x, 'y': y} for x, y in points],
        'stroke': stroke,
        'strokeWidth': stroke_width,
    }


base_objects = [
    circle(250, 220, 18, '#2563eb'),      # jugador 1
    circle(700, 420, 18, '#2563eb'),      # jugador 2
    circle(520, 320, 9, '#ffffff', '#1f2937', 2),  # balón
    rect(170, 140, 18, 18, '#f97316', '#ffffff', 2),
    rect(820, 510, 18, 18, '#f97316', '#ffffff', 2),
    line([(270, 235), (420, 300), (510, 320)], '#facc15', 4),
]

frame_1_objects = [
    circle(250, 220, 18, '#2563eb'),
    circle(700, 420, 18, '#2563eb'),
    circle(520, 320, 9, '#ffffff', '#1f2937', 2),
    rect(170, 140, 18, 18, '#f97316', '#ffffff', 2),
    rect(820, 510, 18, 18, '#f97316', '#ffffff', 2),
    line([(270, 235), (420, 300), (510, 320)], '#facc15', 4),
]

frame_2_objects = [
    circle(330, 260, 18, '#2563eb'),
    circle(650, 370, 18, '#2563eb'),
    circle(570, 340, 9, '#ffffff', '#1f2937', 2),
    rect(170, 140, 18, 18, '#f97316', '#ffffff', 2),
    rect(820, 510, 18, 18, '#f97316', '#ffffff', 2),
    line([(350, 275), (500, 330), (560, 342)], '#facc15', 4),
]

frame_3_objects = [
    circle(430, 300, 18, '#2563eb'),
    circle(600, 330, 18, '#2563eb'),
    circle(615, 332, 9, '#ffffff', '#1f2937', 2),
    rect(170, 140, 18, 18, '#f97316', '#ffffff', 2),
    rect(820, 510, 18, 18, '#f97316', '#ffffff', 2),
    line([(450, 310), (560, 332), (610, 332)], '#facc15', 4),
]

layout = {
    'version': '5.3.0',
    'objects': base_objects,
    'meta': {
        'pitch_orientation': 'landscape',
        'pitch_grass_style': 'broadcast_premium',
        'pitch_preset': 'full_pitch',
        'graphic_editor': {
            'canvas_width': CANVAS_W,
            'canvas_height': CANVAS_H,
        },
    },
    'timeline': [
        {
            'title': 'Inicio',
            'duration': 3,
            'canvas_width': CANVAS_W,
            'canvas_height': CANVAS_H,
            'canvas_state': {'version': '5.3.0', 'width': CANVAS_W, 'height': CANVAS_H, 'objects': frame_1_objects},
        },
        {
            'title': 'Progresión',
            'duration': 3,
            'canvas_width': CANVAS_W,
            'canvas_height': CANVAS_H,
            'canvas_state': {'version': '5.3.0', 'width': CANVAS_W, 'height': CANVAS_H, 'objects': frame_2_objects},
        },
        {
            'title': 'Finalización',
            'duration': 3,
            'canvas_width': CANVAS_W,
            'canvas_height': CANVAS_H,
            'canvas_state': {'version': '5.3.0', 'width': CANVAS_W, 'height': CANVAS_H, 'objects': frame_3_objects},
        },
    ],
}

session = TrainingSession.objects.order_by('id').first()
if session is None:
    raise SystemExit('No hay TrainingSession local para crear la tarea de prueba.')

SessionTask.objects.filter(title='[DIAG] Render Engine Test').delete()
task = SessionTask.objects.create(
    session=session,
    club_season=getattr(session, 'club_season', None),
    title='[DIAG] Render Engine Test',
    block=SessionTask.BLOCK_MAIN_1,
    duration_minutes=10,
    objective='Diagnóstico render engine',
    tactical_layout=layout,
)

bundle = build_task_render_bundle(task, request=None)

cards = {
    'Vista 2D': bundle.get('graphic_view_2d_url') or '',
    'Vista 3D': bundle.get('graphic_view_3d_url') or '',
    'Recreación 2D': bundle.get('recreation_2d_url') or '',
    'Recreación 3D': bundle.get('recreation_3d_url') or '',
}

notes = {
    'Vista 2D': [],
    'Vista 3D': [],
    'Recreación 2D': [],
    'Recreación 3D': [],
}

if not cards['Vista 2D']:
    notes['Vista 2D'].append('Falta graphic_view_2d_url')
if not cards['Vista 3D']:
    notes['Vista 3D'].append('Falta graphic_view_3d_url')
if not cards['Recreación 2D']:
    notes['Recreación 2D'].append('Sin recreación configurada o sin frames reales')
if not cards['Recreación 3D']:
    notes['Recreación 3D'].append('Sin recreación configurada o sin frames reales')
if cards['Vista 2D'] and cards['Vista 3D'] and cards['Vista 2D'] == cards['Vista 3D']:
    notes['Vista 3D'].append('Duplicada respecto a Vista 2D')
if cards['Recreación 2D'] and cards['Vista 2D'] and cards['Recreación 2D'] == cards['Vista 2D']:
    notes['Recreación 2D'].append('Duplicada respecto a Vista 2D')
if cards['Recreación 3D'] and cards['Vista 3D'] and cards['Recreación 3D'] == cards['Vista 3D']:
    notes['Recreación 3D'].append('Duplicada respecto a Vista 3D')
if cards['Recreación 2D'] and cards['Recreación 3D'] and cards['Recreación 2D'] == cards['Recreación 3D']:
    notes['Recreación 3D'].append('Duplicada respecto a Recreación 2D')

summary = {
    'task_id': task.id,
    'session_id': task.session_id,
    'timeline_frames': len(layout['timeline']),
    'animation_frame_cards': len(bundle.get('animation_frame_cards') or []),
    'has_graphic_view_2d': bool(bundle.get('graphic_view_2d_url')),
    'has_graphic_view_3d': bool(bundle.get('graphic_view_3d_url')),
    'has_recreation_2d': bool(bundle.get('recreation_2d_url')),
    'has_recreation_3d': bool(bundle.get('recreation_3d_url')),
}


def render_block(title, url):
    msg_items = ''.join(f'<li>{escape(m)}</li>' for m in notes[title])
    message = f'<ul class="notes">{msg_items}</ul>' if msg_items else '<div class="ok">Render correcto</div>'
    if url:
        body = f'<img src="{url}" alt="{escape(title)}" />'
    else:
        body = '<div class="placeholder">Sin imagen disponible</div>'
    return f'''
    <section class="card">
      <h2>{escape(title)}</h2>
      {body}
      {message}
    </section>
    '''

html = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Ficha test render engine</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background:#0f172a; color:#e5e7eb; }}
    .wrap {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    .meta {{ margin: 0 0 24px; color:#cbd5e1; }}
    .summary {{ background:#111827; border:1px solid #334155; border-radius:16px; padding:16px; margin-bottom:24px; }}
    pre {{ white-space:pre-wrap; word-break:break-word; color:#93c5fd; font-size:13px; margin:0; }}
    .grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:20px; }}
    .card {{ background:#111827; border:1px solid #334155; border-radius:18px; padding:16px; box-shadow:0 12px 30px rgba(0,0,0,.25); }}
    .card h2 {{ margin:0 0 12px; font-size:22px; color:#f8fafc; }}
    .card img {{ width:100%; height:auto; display:block; border-radius:12px; background:white; }}
    .placeholder {{ min-height:240px; display:flex; align-items:center; justify-content:center; border:2px dashed #475569; border-radius:12px; color:#cbd5e1; background:#0b1220; }}
    .notes, .ok {{ margin:12px 0 0; padding:0; }}
    .notes {{ padding-left:18px; color:#fca5a5; }}
    .ok {{ color:#86efac; font-weight:600; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Ficha test render engine</h1>
    <p class="meta">Task local de diagnóstico id {task.id} · session {task.session_id} · usando build_task_render_bundle()</p>
    <div class="summary"><pre>{escape(json.dumps(summary, indent=2, ensure_ascii=False))}</pre></div>
    <div class="grid">
      {render_block('Vista 2D', cards['Vista 2D'])}
      {render_block('Vista 3D', cards['Vista 3D'])}
      {render_block('Recreación 2D', cards['Recreación 2D'])}
      {render_block('Recreación 3D', cards['Recreación 3D'])}
    </div>
  </div>
</body>
</html>'''

OUT_PATH.write_text(html, encoding='utf-8')
print('HTML_OK', OUT_PATH)
print('TASK_ID', task.id)
print('SUMMARY', json.dumps(summary, ensure_ascii=False))
