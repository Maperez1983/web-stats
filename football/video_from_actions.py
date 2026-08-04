"""
Del registro de acciones a los clips del vídeo.

Esto es el "etiquetado en vivo" que venden Sportscode, Nacsport o Spiideo, pero sin pedirle al
entrenador que etiquete otra vez: **ya lo hizo el domingo**. El registro de acciones anota qué pasó,
quién y en qué minuto; lo único que faltaba era saber en qué segundo del vídeo cae ese minuto.

Con dos datos por grabación —el segundo del saque inicial y el de la segunda parte— cada acción
anotada se convierte en un corte. Lo que antes era cortar cincuenta clips a mano pasa a ser un botón.

Deliberadamente NO se inventa nada: si una acción no tiene minuto, se queda fuera y se dice cuántas.
"""
from __future__ import annotations

# Cuánto se coge antes y después del minuto anotado. El minuto es aproximado -se apunta mientras
# pasa el partido-, así que el corte tiene que ser generoso o la acción se queda fuera del clip.
ANTES_MS = 12000
DESPUES_MS = 8000
MAX_CLIPS = 200


def momento_de_video(evento, *, kickoff_ms, second_half_ms, minutos_por_parte=45):
    """En qué milisegundo del vídeo cae una acción anotada en el minuto X.

    La segunda parte se trata aparte porque entre partes la grabación sigue (o se corta) y el reloj
    del partido no: sin esto, todo lo del segundo tiempo saldría desplazado por el descanso.
    """
    minuto = getattr(evento, 'minute', None)
    if minuto is None:
        return None
    minuto = int(minuto)
    periodo = int(getattr(evento, 'period', None) or (2 if minuto > minutos_por_parte else 1))
    if periodo >= 2 and second_half_ms:
        return int(second_half_ms + max(0, minuto - minutos_por_parte) * 60000)
    return int(kickoff_ms + minuto * 60000)


def titulo_de(evento):
    """El nombre del clip: lo que se lee en la lista sin abrirlo."""
    partes = []
    minuto = getattr(evento, 'minute', None)
    if minuto is not None:
        partes.append(f"{int(minuto)}'")
    tipo = str(getattr(evento, 'event_type', '') or '').strip()
    if tipo:
        partes.append(tipo)
    jugador = getattr(evento, 'player', None)
    nombre = str(getattr(jugador, 'nickname', '') or getattr(jugador, 'name', '') or '').strip()
    if nombre:
        partes.append(nombre.split(' ')[0])
    return ' · '.join(partes)[:180] or 'Acción'


def etiquetas_de(evento):
    """Las etiquetas del clip salen de lo que ya se anotó: tipo, resultado y zona."""
    crudas = [
        getattr(evento, 'kind', ''),
        getattr(evento, 'event_type', ''),
        getattr(evento, 'result', ''),
        getattr(evento, 'zone', ''),
    ]
    fuera, vistas = [], set()
    for etiqueta in crudas:
        texto = str(etiqueta or '').strip()[:40]
        clave = texto.lower()
        if texto and clave not in vistas:
            vistas.add(clave)
            fuera.append(texto)
    return fuera


def clips_desde_el_registro(video, *, creado_por='', duracion_ms=None):
    """
    Crea un clip por cada acción del partido de ese vídeo. Devuelve (creados, saltados, sin_minuto).

    Idempotente: los clips llevan la marca de su acción, así que volver a pulsar no duplica nada.
    """
    from .models import MatchEvent, VideoClip

    if not video or not getattr(video, 'match_id', None):
        return (0, 0, 0)

    eventos = list(
        MatchEvent.objects.filter(match_id=video.match_id)
        .select_related('player')
        .order_by('period', 'minute', 'id')[:MAX_CLIPS]
    )
    ya = {
        str((c.tags or [])[-1]) if isinstance(c.tags, list) and c.tags else ''
        for c in VideoClip.objects.filter(video=video)
    }
    creados = saltados = sin_minuto = 0
    for evento in eventos:
        momento = momento_de_video(
            evento, kickoff_ms=video.kickoff_ms or 0, second_half_ms=video.second_half_ms or 0
        )
        if momento is None:
            sin_minuto += 1
            continue
        marca = f'accion:{evento.id}'
        if marca in ya:
            saltados += 1
            continue
        inicio = max(0, momento - ANTES_MS)
        fin = momento + DESPUES_MS
        if duracion_ms:
            # Un corte que empieza después de que el vídeo acabe no es un clip, es ruido: pasa
            # cuando el segundo del saque inicial está mal puesto.
            if inicio >= duracion_ms:
                saltados += 1
                continue
            fin = min(fin, duracion_ms)
        VideoClip.objects.create(
            team=video.team,
            video=video,
            title=titulo_de(evento),
            collection='Registro del partido',
            in_ms=inicio,
            out_ms=fin,
            tags=etiquetas_de(evento) + [marca],
            notes=str(getattr(evento, 'observation', '') or '')[:2000],
            created_by=str(creado_por or '')[:80],
        )
        creados += 1
    return (creados, saltados, sin_minuto)
