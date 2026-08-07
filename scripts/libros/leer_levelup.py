#!/usr/bin/env python3
"""Lee el libro Level Up y saca una ficha por pagina, sin inventarse nada.

Cada pagina es un ejercicio con la misma plantilla: titulo numerado, Fase, Nº de jugadores,
Dimensiones, Objetivos (vinetas) y Desarrollo. Lo que no venga se queda vacio: es preferible
un hueco a un dato adivinado, porque estas columnas alimentan la biblioteca y el recomendador.
"""
import json, re, sys

RUTA = sys.argv[1] if len(sys.argv) > 1 else 'texto_levelup.txt'
paginas = open(RUTA, encoding='utf-8').read().split('\f')

ETIQUETAS = ['Fase', 'Nº de jugadores', 'Dimensiones', 'Objetivos', 'Desarrollo', 'Variantes', 'Reglas']

def trozo(lineas, etiqueta):
    """El texto que sigue a una etiqueta, hasta la siguiente etiqueta."""
    try:
        i = lineas.index(etiqueta)
    except ValueError:
        return ''
    out = []
    for l in lineas[i + 1:]:
        if l in ETIQUETAS:
            break
        out.append(l)
    return '\n'.join(out).strip()

fichas = []
for n, pag in enumerate(paginas, start=1):
    lineas = [l.strip() for l in pag.split('\n')]
    lineas = [l for l in lineas if l]
    if not lineas:
        continue
    m = re.match(r'^(\d+)\s*[-–]\s*(.+)$', lineas[0])
    if not m:
        continue
    objetivos = [o.lstrip('•').strip() for o in trozo(lineas, 'Objetivos').split('\n')]
    objetivos = [o for o in objetivos if o and o != '•']
    jugadores = trozo(lineas, 'Nº de jugadores')
    fichas.append({
        'numero': int(m.group(1)),
        'pagina': n,
        'titulo': m.group(2).strip()[:160],
        'fase': trozo(lineas, 'Fase'),
        'jugadores': jugadores,
        'dimensiones': trozo(lineas, 'Dimensiones'),
        'objetivos': objetivos,
        'desarrollo': trozo(lineas, 'Desarrollo'),
        'variantes': trozo(lineas, 'Variantes'),
    })

json.dump(fichas, open('fichas_levelup.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'fichas leidas: {len(fichas)} de {len(paginas)} paginas')
sin = [f['numero'] for f in fichas if not f['desarrollo']]
print(f'sin desarrollo: {len(sin)}')
from collections import Counter
print('fases:', dict(Counter(f['fase'] or '(vacia)' for f in fichas).most_common(6)))
