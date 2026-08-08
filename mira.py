import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","webstats.settings"); django.setup()
from football.models import SessionTask, TaskBoardShot
from football import task_board_snapshot as f
from PIL import Image
t=SessionTask.objects.get(pk=1)
print("familia guardada:", repr(t.task_family))
print("imagen ahora:", t.task_preview_image.name)
print("la cuenta como foto buena?", f.snapshot_is_current(t))
t.task_preview_image.open('rb'); raw=t.task_preview_image.read(); t.task_preview_image.close()
open('/tmp/captura_cliente.bin','wb').write(raw)
im=Image.open('/tmp/captura_cliente.bin')
print("lo que guardo el navegador:", im.format, im.size, len(raw), "bytes")
im.convert('RGB').save('/tmp/captura_cliente.jpg', quality=95)
s=TaskBoardShot.objects.filter(task_id=1).first()
print("cola:", (s.state, s.attempts) if s else "-")
