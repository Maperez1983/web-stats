"""
Quemar la telestración DENTRO del vídeo, en el servidor.

Hasta ahora los dibujos vivían sólo encima del reproductor: el corte que salía del servidor iba
limpio, y la única forma de tener un vídeo con flechas era grabar la pantalla desde el navegador.
Eso ata la calidad al ordenador de quien exporta, no se puede regenerar, y en un móvil viejo
directamente no sale.

Aquí se pinta la capa de dibujo con Pillow —los mismos trazos que guardó el editor— y se compone
sobre el recorte con ffmpeg. El resultado es un MP4 con las flechas dentro, igual en cualquier sitio
y repetible: si mañana mueves una flecha, se vuelve a generar.

El formato de entrada es el que ya guarda el estudio: `fabricCanvas.toDatalessJSON()`, es decir
`{"objects": [...], "fx": {...}}` con coordenadas en píxeles del lienzo del editor. Como ese lienzo
mide lo que mide el reproductor de quien dibujó, se reescala al tamaño real del vídeo.
"""
from __future__ import annotations

import io
import logging
import math
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Sólo se pintan los tipos que el estudio sabe crear. Uno desconocido se ignora en vez de reventar
# la exportación entera: es preferible un vídeo sin una forma rara que ningún vídeo.
TIPOS = {'line', 'rect', 'circle', 'ellipse', 'path', 'polyline', 'polygon', 'text', 'i-text', 'textbox', 'triangle', 'group'}


# --- recursos gráficos ---------------------------------------------------------------------
#
# Una flecha de una línea recta con un triángulo pegado se ve casera. Lo que hace que la
# telestración de los programas caros parezca profesional no es magia: es cuerpo que se AFILA hacia
# la punta, una sombra por debajo que la despega del césped, y un borde oscuro que la hace legible
# igual sobre hierba clara que sobre el público.

SOMBRA = (0, 0, 0, 110)


def _perpendicular(x1, y1, x2, y2):
    largo = math.hypot(x2 - x1, y2 - y1) or 1.0
    return (-(y2 - y1) / largo, (x2 - x1) / largo)


def _cuerpo_de_flecha(puntos, grosor):
    """El polígono de una flecha que se afila: ancha en el origen, fina antes de la punta."""
    if len(puntos) < 2:
        return []
    (x1, y1), (x2, y2) = puntos[0], puntos[-1]
    nx, ny = _perpendicular(x1, y1, x2, y2)
    largo = math.hypot(x2 - x1, y2 - y1) or 1.0
    cabeza = min(largo * 0.42, max(16.0, grosor * 3.4))
    ux, uy = (x2 - x1) / largo, (y2 - y1) / largo
    bx, by = x2 - ux * cabeza, y2 - uy * cabeza     # donde acaba el cuerpo
    ancho_atras = grosor * 0.75
    ancho_delante = grosor * 0.42
    ala = grosor * 1.75
    return [
        (x1 + nx * ancho_atras, y1 + ny * ancho_atras),
        (bx + nx * ancho_delante, by + ny * ancho_delante),
        (bx + nx * ala, by + ny * ala),
        (x2, y2),
        (bx - nx * ala, by - ny * ala),
        (bx - nx * ancho_delante, by - ny * ancho_delante),
        (x1 - nx * ancho_atras, y1 - ny * ancho_atras),
    ]


def _flecha(dibujo, puntos, color, grosor):
    cuerpo = _cuerpo_de_flecha(puntos, grosor)
    if not cuerpo:
        return
    # Sombra desplazada: es lo que despega el dibujo del césped.
    desvio = max(2, int(grosor * 0.5))
    dibujo.polygon([(x + desvio, y + desvio) for (x, y) in cuerpo], fill=SOMBRA)
    dibujo.polygon(cuerpo, fill=color, outline=(10, 18, 28, 210))


def _foco_jugador(dibujo, cx, cy, radio, color):
    """Marcar a un jugador es un ANILLO a sus pies con halo, no un círculo plano encima."""
    for i in range(5, 0, -1):
        r = radio * (1 + i * 0.13)
        alfa = int(26 * (6 - i) / 5)
        dibujo.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55],
                       fill=(color[0], color[1], color[2], alfa))
    dibujo.ellipse([cx - radio, cy - radio * 0.55, cx + radio, cy + radio * 0.55],
                   outline=(10, 18, 28, 200), width=max(4, int(radio * 0.16)))
    dibujo.ellipse([cx - radio, cy - radio * 0.55, cx + radio, cy + radio * 0.55],
                   outline=color, width=max(2, int(radio * 0.1)))


def _zona(dibujo, caja, color):
    """Una zona es un espacio TEÑIDO con su borde, no un rectángulo hueco."""
    x1, y1, x2, y2 = caja
    dibujo.rectangle([x1, y1, x2, y2], fill=(color[0], color[1], color[2], 46))
    dibujo.rectangle([x1, y1, x2, y2], outline=(10, 18, 28, 160), width=6)
    dibujo.rectangle([x1, y1, x2, y2], outline=color, width=3)


def _placa_de_texto(dibujo, x, y, texto, fuente, color):
    """El texto va sobre una placa oscura: sobre hierba clara, sin ella, no se lee."""
    try:
        caja = dibujo.textbbox((x, y), texto, font=fuente)
    except Exception:
        return False
    margen = 10
    dibujo.rounded_rectangle(
        [caja[0] - margen, caja[1] - margen * 0.7, caja[2] + margen, caja[3] + margen * 0.7],
        radius=10, fill=(8, 15, 26, 205), outline=(color[0], color[1], color[2], 190), width=2,
    )
    dibujo.text((x, y), texto, font=fuente, fill=color)
    return True


def _color(valor, por_defecto=(255, 255, 255, 255)):
    """Traduce un color de Fabric ('#fff', 'rgba(...)') a una tupla RGBA."""
    texto = str(valor or '').strip().lower()
    if not texto or texto in {'none', 'transparent'}:
        return None
    if texto.startswith('#'):
        crudo = texto[1:]
        if len(crudo) == 3:
            crudo = ''.join(c * 2 for c in crudo)
        if len(crudo) >= 6:
            try:
                return (int(crudo[0:2], 16), int(crudo[2:4], 16), int(crudo[4:6], 16), 255)
            except ValueError:
                return por_defecto
    if texto.startswith('rgb'):
        try:
            partes = texto[texto.index('(') + 1:texto.index(')')].split(',')
            r, g, b = (int(float(p)) for p in partes[:3])
            a = int(float(partes[3]) * 255) if len(partes) > 3 else 255
            return (r, g, b, a)
        except Exception:
            return por_defecto
    return por_defecto


def _puntos_de(objeto, dx=0.0, dy=0.0, escala=1.0):
    """Los puntos de una forma, ya en píxeles del vídeo."""
    tipo = str(objeto.get('type') or '').lower()
    izq = float(objeto.get('left') or 0)
    arr = float(objeto.get('top') or 0)

    def punto(x, y):
        return ((izq + x + dx) * escala, (arr + y + dy) * escala)

    if tipo == 'line':
        # Fabric guarda la línea centrada en left/top: x1..x2 son relativos a su propio centro.
        x1, y1 = float(objeto.get('x1') or 0), float(objeto.get('y1') or 0)
        x2, y2 = float(objeto.get('x2') or 0), float(objeto.get('y2') or 0)
        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        return [punto(x1 - cx, y1 - cy), punto(x2 - cx, y2 - cy)]
    if tipo in {'polyline', 'polygon'}:
        return [punto(float(p.get('x') or 0), float(p.get('y') or 0)) for p in (objeto.get('points') or [])]
    if tipo == 'path':
        salida = []
        for tramo in (objeto.get('path') or []):
            if not isinstance(tramo, (list, tuple)) or len(tramo) < 3:
                continue
            salida.append(punto(float(tramo[-2]), float(tramo[-1])))
        return salida
    return []


def _pinta(dibujo, objeto, ancho, alto, dx=0.0, dy=0.0, escala=1.0):
    tipo = str(objeto.get('type') or '').lower()
    if tipo not in TIPOS:
        return
    trazo = _color(objeto.get('stroke'), (255, 255, 255, 255))
    relleno = _color(objeto.get('fill'), None)
    grosor = max(2, int(round(float(objeto.get('strokeWidth') or 3) * escala)))

    if tipo == 'group':
        for hijo in (objeto.get('objects') or []):
            _pinta(dibujo, hijo, ancho, alto,
                   dx + float(objeto.get('left') or 0), dy + float(objeto.get('top') or 0), escala)
        return

    izq = (float(objeto.get('left') or 0) + dx) * escala
    arr = (float(objeto.get('top') or 0) + dy) * escala
    anc = float(objeto.get('width') or 0) * float(objeto.get('scaleX') or 1) * escala
    alt = float(objeto.get('height') or 0) * float(objeto.get('scaleY') or 1) * escala

    if tipo in {'rect', 'triangle'}:
        _zona(dibujo, (izq, arr, izq + anc, arr + alt), trazo or (234, 244, 239, 255))
    elif tipo in {'circle', 'ellipse'}:
        radio = float(objeto.get('radius') or 0) * float(objeto.get('scaleX') or 1) * escala
        if not radio:
            radio = max(anc, alt) / 2.0
        _foco_jugador(dibujo, izq + radio, arr + radio, radio, trazo or (255, 215, 106, 255))
    elif tipo in {'text', 'i-text', 'textbox'}:
        from PIL import ImageFont

        fuente = None
        tam = max(14, int(float(objeto.get('fontSize') or 28) * escala))
        for ruta in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                     '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                     '/System/Library/Fonts/Helvetica.ttc'):
            try:
                fuente = ImageFont.truetype(ruta, tam)
                break
            except Exception:
                continue
        texto = str(objeto.get('text') or '')
        color = trazo or (255, 255, 255, 255)
        if not (fuente and _placa_de_texto(dibujo, izq, arr, texto, fuente, color)):
            dibujo.text((izq, arr), texto, fill=color, font=fuente,
                        stroke_width=max(1, grosor // 2), stroke_fill=(0, 0, 0, 220))
    else:
        puntos = _puntos_de(objeto, dx, dy, escala)
        if len(puntos) < 2:
            return
        datos = objeto.get('data') if isinstance(objeto.get('data'), dict) else {}
        clase = str(datos.get('kind') or objeto.get('vsKind') or '').lower()
        if clase in {'arrow', 'flecha', 'move', 'trayectoria'}:
            _flecha(dibujo, puntos, trazo or (111, 211, 255, 255), grosor)
        else:
            # Trazo libre: sombra debajo y borde oscuro, para que se lea sobre cualquier césped.
            desvio = max(2, int(grosor * 0.45))
            dibujo.line([(x + desvio, y + desvio) for (x, y) in puntos], fill=SOMBRA,
                        width=grosor + 2, joint='curve')
            dibujo.line(puntos, fill=(10, 18, 28, 200), width=grosor + 4, joint='curve')
            dibujo.line(puntos, fill=trazo, width=grosor, joint='curve')


def capa_png(overlay, *, ancho, alto, ancho_lienzo=0, alto_lienzo=0):
    """La capa de dibujo como PNG transparente del tamaño del vídeo. None si no hay nada que pintar."""
    from PIL import Image, ImageDraw

    objetos = (overlay or {}).get('objects') if isinstance(overlay, dict) else None
    if not objetos:
        return None
    # El lienzo del editor mide lo que medía el reproductor de quien dibujó; si no viene, se asume
    # que ya está en las medidas del vídeo.
    escala = (ancho / float(ancho_lienzo)) if ancho_lienzo else 1.0

    lienzo = Image.new('RGBA', (int(ancho), int(alto)), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(lienzo, 'RGBA')
    for objeto in objetos:
        if not isinstance(objeto, dict):
            continue
        try:
            _pinta(dibujo, objeto, ancho, alto, escala=escala)
        except Exception:
            logger.debug('No se pudo pintar un objeto de la telestración', exc_info=True)
    buffer = io.BytesIO()
    lienzo.save(buffer, 'PNG')
    return buffer.getvalue()


def quemar(*, source_path, start_s, end_s, overlay, ancho_lienzo=0, alto_lienzo=0, destino=None):
    """
    Recorta el segmento y le compone encima la telestración. Devuelve la ruta del MP4.

    Un solo paso de ffmpeg: recortar y componer a la vez. Hacerlo en dos escribiría el vídeo dos
    veces, y estos ficheros son grandes.
    """
    import json  # noqa: F401  (documenta que el overlay llega ya deserializado)

    duracion = max(0.1, float(end_s) - float(start_s))
    ancho, alto = _medidas(source_path)
    png = capa_png(overlay, ancho=ancho, alto=alto, ancho_lienzo=ancho_lienzo, alto_lienzo=alto_lienzo)
    salida = destino or tempfile.NamedTemporaryFile(suffix='.mp4', delete=False).name

    orden = ['ffmpeg', '-y', '-ss', str(float(start_s)), '-t', str(duracion), '-i', str(source_path)]
    if png:
        capa = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        capa.write(png)
        capa.close()
        orden += ['-i', capa.name, '-filter_complex', '[0:v][1:v]overlay=0:0:format=auto[v]',
                  '-map', '[v]', '-map', '0:a?']
    orden += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p',
              '-c:a', 'aac', '-movflags', '+faststart', str(salida)]
    subprocess.run(orden, check=True, capture_output=True, timeout=600)
    return salida


def _medidas(source_path):
    """Ancho y alto del vídeo. Si ffprobe no está, se asume 1280x720 y se sigue."""
    try:
        salida = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
             'stream=width,height', '-of', 'csv=p=0:s=x', str(source_path)],
            check=True, capture_output=True, timeout=30,
        ).stdout.decode().strip()
        ancho, alto = (int(v) for v in salida.split('x')[:2])
        return (ancho, alto)
    except Exception:
        return (1280, 720)
