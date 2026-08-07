#!/usr/bin/env python3
"""Encuentra las FLECHAS de una rueda de pases.

En estos ejercicios el dibujo ES la secuencia: colocar las fichas sin las flechas vacía el
ejercicio. Detectar lineas sueltas en una imagen es un problema feo, pero aqui hay un atajo
honesto: las flechas UNEN ESTACIONES. Asi que en vez de buscar lineas, se toma cada pareja de
estaciones y se pregunta si el camino recto entre ellas esta pintado. Lo que no este pintado
casi entero, no es una flecha.
"""
from PIL import Image

VERDE_CAMPO = (0, 132, 83)


def _tinta(c):
    """Pixel de trazo: negro, rojo o amarillo. No el cesped ni el blanco de las lineas."""
    r, g, b = c
    if r < 80 and g < 80 and b < 80:
        return 'negro'
    if r > 150 and g < 90 and b < 90:
        return 'rojo'
    if r > 190 and g > 160 and b < 110:
        return 'amarillo'
    return ''


def _hay_tinta(px, w, h, x, y, radio=5):
    # Margen ANCHO a proposito: la flecha sale del borde de la estacion, no de su centro
    # exacto, asi que el camino recto entre centros pasa un poco al lado del trazo. Con un
    # margen corto, media rueda de pases se quedaba sin flechas.
    for dx in range(-radio, radio + 1):
        for dy in range(-radio, radio + 1):
            nx, ny = int(x + dx), int(y + dy)
            if 0 <= nx < w and 0 <= ny < h:
                t = _tinta(px[nx, ny])
                if t:
                    return t
    return ''


def agrupar_estaciones(fichas, junta=70):
    """Las fichas pegadas son UNA estacion.

    En las ruedas de pases el libro dibuja dos jugadores juntos por puesto, y la flecha sale
    del puesto, no de cada jugador. Midiendo desde el centro de cada ficha, la mitad de los
    caminos pasaban por al lado del trazo y no se reconocian.
    """
    grupos = []
    for f in fichas:
        for g in grupos:
            if abs(g['x'] - f['x']) <= junta and abs(g['y'] - f['y']) <= junta:
                g['xs'].append(f['x']); g['ys'].append(f['y'])
                g['x'] = sum(g['xs']) // len(g['xs']); g['y'] = sum(g['ys']) // len(g['ys'])
                break
        else:
            grupos.append({'x': f['x'], 'y': f['y'], 'xs': [f['x']], 'ys': [f['y']]})
    return [(g['x'], g['y']) for g in grupos]


def _cobertura(px, w, h, x1, y1, x2, y2):
    """Que parte del camino recto entre dos puntos esta pintada, y de que color."""
    largo = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if largo < 50:
        return 0.0, ''
    pasos = max(12, int(largo / 12))
    colores = {}
    aciertos = 0
    for k in range(2, pasos - 1):
        t = k / float(pasos)
        col = _hay_tinta(px, w, h, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        if col:
            aciertos += 1
            colores[col] = colores.get(col, 0) + 1
    total = max(1, pasos - 3)
    return aciertos / total, (max(colores, key=colores.get) if colores else '')


def flechas_entre(im, estaciones, minimo=0.8):
    """Parejas de estaciones unidas por un trazo.

    La flecha sale del BORDE de la estacion, no de su centro, asi que el camino recto entre
    centros pasa un poco al lado del trazo. En vez de ensanchar el margen -que hace colar
    caminos que solo rozan una flecha ajena- se prueban varias salidas alrededor de cada
    estacion y se ELIGE LA MEJOR: si hay flecha, alguna de esas lineas la sigue entera.
    """
    px = im.load()
    w, h = im.size
    desvios = [(0, 0), (30, 0), (-30, 0), (0, 30), (0, -30), (22, 22), (-22, -22), (22, -22), (-22, 22)]
    fuera = []
    for i in range(len(estaciones)):
        for j in range(i + 1, len(estaciones)):
            ax, ay = estaciones[i]
            bx, by = estaciones[j]
            mejor, color_mejor, extremos = 0.0, '', None
            for dax, day in desvios:
                for dbx, dby in desvios:
                    c, col = _cobertura(px, w, h, ax + dax, ay + day, bx + dbx, by + dby)
                    if c > mejor:
                        mejor, color_mejor, extremos = c, col, (ax + dax, ay + day, bx + dbx, by + dby)
            if mejor >= minimo and extremos:
                fuera.append({'x1': extremos[0], 'y1': extremos[1], 'x2': extremos[2], 'y2': extremos[3],
                              'color': color_mejor or 'negro', 'seguro': round(mejor, 2)})
    return fuera


if __name__ == '__main__':
    import sys, json
    import leer_dibujo as L
    ruta = sys.argv[1]
    im = Image.open(ruta).convert('RGB')
    d = L.leer(ruta)
    est = agrupar_estaciones([f for f in d['fichas'] if f['tipo'] != 'balon'])
    fl = flechas_entre(im, est)
    print(f'estaciones: {len(est)} · flechas encontradas: {len(fl)}')
    for f in sorted(fl, key=lambda f: -f['seguro'])[:14]:
        print(f"   {f['color']:8} ({f['x1']},{f['y1']}) -> ({f['x2']},{f['y2']})  {f['seguro']}")
