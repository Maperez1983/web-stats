"""
Sirve la figura de una ficha (la chapa) desde la tarea que ya la tiene guardada.

El editor no guarda una URL de la chapa: incrusta el PNG compuesto dentro del dibujo, unos 127 KB
por jugador. En el guion no cabe -22 fichas serían 2,8 MB, y el guion existe precisamente para
pesar 1 KB-, pero el reproductor tiene que pintar EXACTAMENTE la misma figura que la pizarra: dos
juegos de assets para el mismo tablero hacen que parezca otro programa.

La salida: el guion marca al actor con `img_embedded`, y la ficha pide la imagen aquí. El byte es
el mismo que dibuja el editor, no una recomposición, y viaja una sola vez porque la respuesta es
cacheable: la imagen de una tarea guardada no cambia hasta que se vuelve a guardar.
"""
from __future__ import annotations

import base64
import binascii
import re

from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .models import SessionTask
from .permissions import can_access_sessions_workspace

_DATA_URI = re.compile(r'^data:(image/(?:png|jpeg|webp|gif));base64,(.+)$', re.IGNORECASE | re.DOTALL)
# Un dibujo puede tener grupos anidados; mas de esto es basura, no una chapa.
MAX_HONDO = 5


def _canvas_states(layout):
    """Los lienzos donde puede estar la ficha: el actual y, si no, el primer paso."""
    if not isinstance(layout, dict):
        return []
    estados = []
    meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
    editor = meta.get('graphic_editor') if isinstance(meta.get('graphic_editor'), dict) else {}
    if isinstance(editor.get('canvas_state'), dict):
        estados.append(editor['canvas_state'])
    for paso in (layout.get('timeline') if isinstance(layout.get('timeline'), list) else [])[:3]:
        if isinstance(paso, dict) and isinstance(paso.get('canvas_state'), dict):
            estados.append(paso['canvas_state'])
    return estados


def _uid_de(obj):
    data = obj.get('data') if isinstance(obj.get('data'), dict) else {}
    for clave in ('layer_uid', 'token_id', 'tokenId', 'playerId', 'player_id', 'uid', 'id'):
        valor = data.get(clave)
        if valor:
            return str(valor)
    return ''


def _imagen_incrustada(nodo, hondo=0):
    if hondo > MAX_HONDO or not isinstance(nodo, dict):
        return ''
    src = nodo.get('src')
    if isinstance(src, str) and src.startswith('data:'):
        return src
    for hijo in (nodo.get('objects') if isinstance(nodo.get('objects'), list) else []):
        encontrada = _imagen_incrustada(hijo, hondo + 1)
        if encontrada:
            return encontrada
    return ''


def _buscar_ficha(layout, uid):
    for estado in _canvas_states(layout):
        for obj in (estado.get('objects') if isinstance(estado.get('objects'), list) else []):
            if isinstance(obj, dict) and _uid_de(obj) == uid:
                imagen = _imagen_incrustada(obj)
                if imagen:
                    return imagen
    return ''


@require_GET
@login_required
def session_task_token_image(request, task_id, uid):
    if not can_access_sessions_workspace(request.user):
        return HttpResponseForbidden('No disponible.')
    # `tactical_layout` va diferido en el manager por peso; aqui SI hace falta.
    task = (
        SessionTask.objects.filter(id=task_id, deleted_at__isnull=True)
        .only('id', 'tactical_layout')
        .first()
    )
    if not task:
        raise Http404
    imagen = _buscar_ficha(task.tactical_layout, str(uid or '')[:80])
    if not imagen:
        raise Http404
    m = _DATA_URI.match(imagen)
    if not m:
        raise Http404
    try:
        crudo = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError):
        raise Http404
    respuesta = HttpResponse(crudo, content_type=m.group(1))
    # La figura de una tarea guardada no cambia hasta que se vuelve a guardar: se cachea fuerte y
    # asi el reproductor la pide una vez aunque la ficha se abra veinte veces.
    respuesta['Cache-Control'] = 'private, max-age=86400'
    respuesta['Content-Length'] = str(len(crudo))
    return respuesta
