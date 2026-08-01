import hashlib, json
from football.models import SessionTask
from football.render_engine import build_task_render_bundle

t = SessionTask.objects.get(title='[DIAG] Render Engine Test')
b = build_task_render_bundle(t)
keys = ['graphic_view_2d_url', 'graphic_view_3d_url', 'recreation_2d_url', 'recreation_3d_url']
out = {}
for k in keys:
    v = str(b.get(k) or '')
    out[k] = {
        'present': bool(v),
        'len': len(v),
        'sha1': hashlib.sha1(v.encode()).hexdigest() if v else '',
    }
print(json.dumps(out, indent=2))
