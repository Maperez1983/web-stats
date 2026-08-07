#!/usr/bin/env python3
"""Lee el dibujo de un ejercicio del libro y devuelve DONDE esta cada cosa.

Los dibujos son graficos planos: cada elemento tiene su color exacto y las zonas son
rectangulos de linea recta. Asi que se puede leer, no estimar. Lo que no se reconozca se
queda fuera: prefiero una pizarra con menos elementos que una con inventos.

Dos lecturas independientes:
  - FICHAS por manchas de color (azules en posesion, verdes defensores, naranja comodin).
  - ZONAS por la rejilla de lineas negras/blancas que dibuja los rectangulos.
"""
import sys, json
from PIL import Image

# El libro usa CUATRO colores de ficha, no tres: azul, verde, amarillo y rojo (este ultimo
# en 22 de cada 60 dibujos). Yo solo miraba tres y ademas confundia el amarillo con el
# naranja, asi que dos equipos distintos caian en el mismo saco.
# NO hay una paleta unica en el libro: el mismo "azul" es (90,155,213) en un ejercicio y
# (42,119,165) en otro, y lo mismo el amarillo. Fijar colores a mano funcionaba en el dibujo
# con el que lo probe y fallaba en el siguiente. Asi que los colores se DESCUBREN en cada
# dibujo: se quita el verde del campo y el negro/blanco de las lineas, y lo que queda en
# cantidad suficiente son los equipos.
VERDE_CAMPO = (0, 132, 83)
TOLERANCIA = 26
AREA_MINIMA = 120


def _lejos_del_campo(c):
    r, g, b = c
    if sum(abs(a - b) for a, b in zip(c, VERDE_CAMPO)) <= 90:
        return False
    if r > 205 and g > 205 and b > 205:          # blanco de las lineas
        return False
    if r < 70 and g < 70 and b < 70:             # negro de las lineas
        return False
    if abs(r - g) < 18 and abs(g - b) < 18:      # grises
        return False
    return True


def paleta(im, minimo=400):
    """Los colores de FICHA que usa este dibujo, sacados de el mismo."""
    chico = im.resize((im.size[0] // 2, im.size[1] // 2))
    cuenta = {}
    for c in chico.getdata():
        if not _lejos_del_campo(c):
            continue
        clave = (c[0] // 16, c[1] // 16, c[2] // 16)
        d = cuenta.setdefault(clave, [0, 0, 0, 0])
        d[0] += c[0]; d[1] += c[1]; d[2] += c[2]; d[3] += 1
    fuera = []
    for clave, (r, g, b, n) in cuenta.items():
        if n * 4 >= minimo:
            fuera.append(((r // n, g // n, b // n), n))
    # Por CANTIDAD, no por brillo. Ordenando por brillo se colaban primero los halos que el
    # JPEG deja alrededor de cada circulo -colores lavados como (194,225,213)- y ocupaban las
    # cinco plazas, dejando fuera el verde de verdad de las fichas. El color de un equipo es
    # el que MAS pixeles tiene, no el mas claro.
    limpia = []
    for c, _n in sorted(fuera, key=lambda par: -par[1]):
        if all(sum(abs(a - b) for a, b in zip(c, o)) > 70 for o in limpia):
            limpia.append(c)
    # Ocho plazas y no cinco: entre los colores mas numerosos hay halos del JPEG, y con solo
    # cinco plazas los halos dejaban fuera un equipo entero. Sobrar candidatos no hace danio:
    # los que no son fichas no producen manchas redondas del tamanio correcto.
    return limpia[:8]


def _parecido(c, ref):
    return sum(abs(a - b) for a, b in zip(c, ref)) <= TOLERANCIA * 3


def manchas(im, ref):
    w, h = im.size
    px = im.load()
    visto = bytearray(w * h)
    salida = []
    for y0 in range(0, h, 2):
        for x0 in range(0, w, 2):
            if visto[y0 * w + x0] or not _parecido(px[x0, y0], ref):
                continue
            pila, xs, ys = [(x0, y0)], [], []
            visto[y0 * w + x0] = 1
            while pila:
                x, y = pila.pop()
                xs.append(x); ys.append(y)
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visto[ny*w+nx] and _parecido(px[nx, ny], ref):
                        visto[ny*w+nx] = 1
                        pila.append((nx, ny))
            if len(xs) >= AREA_MINIMA:
                # UNA FICHA ES REDONDA. Sin exigirlo, el texto de las estaciones y los trazos de
                # las flechas entraban como fichas y un dibujo devolvia 190 "jugadores". Se mide
                # la caja de la mancha: alto y ancho parecidos, y bastante relleno (un circulo
                # ocupa ~78% de su caja; una letra o un trazo, mucho menos).
                ancho = max(xs) - min(xs) + 1
                alto = max(ys) - min(ys) + 1
                # OVALADAS TAMBIEN: hay ejercicios donde el libro dibuja las fichas como
                # elipses anchas, no como circulos. Exigiendo casi-circulo, esos dibujos se
                # quedaban sin una sola ficha y acababan en el saco de "ilegibles". El relleno
                # de abajo es el que sigue dejando fuera letras y trazos.
                cuadrada = 0.5 <= (ancho / alto if alto else 9) <= 2.3
                relleno = len(xs) / float(ancho * alto)
                if cuadrada and relleno >= 0.55:
                    salida.append({'x': sum(xs)//len(xs), 'y': sum(ys)//len(ys), 'area': len(xs)})
    return salida


def balones(im, area_ficha):
    """Los balones: mancha clara, mas pequenia que un jugador y con negro dentro.

    El icono del libro es el balon de siempre -blanco con manchas negras-, y eso es lo que
    lo distingue. Buscarlo por color fallaba (hay jugadores amarillos) y por tamanio tambien
    (miden casi lo mismo).
    """
    w, h = im.size
    px = im.load()
    visto = bytearray(w * h)
    fuera = []
    claro = lambda c: c[0] > 195 and c[1] > 195 and c[2] > 190
    for y0 in range(0, h, 2):
        for x0 in range(0, w, 2):
            if visto[y0 * w + x0] or not claro(px[x0, y0]):
                continue
            pila, xs, ys = [(x0, y0)], [], []
            visto[y0 * w + x0] = 1
            while pila:
                x, y = pila.pop()
                xs.append(x); ys.append(y)
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visto[ny*w+nx] and claro(px[nx, ny]):
                        visto[ny*w+nx] = 1
                        pila.append((nx, ny))
            n = len(xs)
            # El balon es PEQUENIO: unos 40-60 pixeles frente a los 800 de una ficha. Con el
            # tope al 60% del tamanio de una ficha colaban las letras de las estaciones (la B
            # y la D miden 300). Al 15% no cabe una letra y si el balon.
            if not (25 <= n <= max(120, area_ficha * 0.15)):
                continue
            ancho = max(xs) - min(xs) + 1
            alto = max(ys) - min(ys) + 1
            if not (0.7 <= ancho / max(1, alto) <= 1.4):
                continue
            # Y RELLENO: las letras de las estaciones (A, B, C...) son blancas y casi
            # cuadradas, asi que pasaban por balones. Un balon llena su caja; una letra no.
            if n / float(ancho * alto) < 0.55:
                continue
            cx, cy = sum(xs)//n, sum(ys)//n
            # Con negro dentro: es lo que separa un balon de un hueco blanco cualquiera.
            negro = 0
            for x, y in zip(xs, ys):
                c = px[x, y]
                if c[0] < 90 and c[1] < 90 and c[2] < 90:
                    negro += 1
            vecino_negro = any(
                px[min(w-1, max(0, cx+dx)), min(h-1, max(0, cy+dy))][0] < 90
                for dx in range(-6, 7) for dy in range(-6, 7)
            )
            if vecino_negro:
                fuera.append({'x': cx, 'y': cy, 'area': n})
    # Las manchas negras del balon lo parten en varios trozos blancos, y cada trozo se contaba
    # como un balon distinto: la 11 devolvia dos balones separados por seis pixeles. Lo que
    # este pegado es el mismo balon.
    juntos = []
    for b in sorted(fuera, key=lambda b: -b['area']):
        if all(abs(b['x'] - o['x']) > 18 or abs(b['y'] - o['y']) > 18 for o in juntos):
            juntos.append(b)
    return juntos


def _es_linea(c):
    r, g, b = c
    return (r < 70 and g < 70 and b < 70) or (r > 200 and g > 200 and b > 200)


def _agrupa(v, junta=4):
    out = []
    for n in v:
        if out and n - out[-1][-1] <= junta:
            out[-1].append(n)
        else:
            out.append([n])
    return [sum(g)//len(g) for g in out]


def rejilla(im):
    """Las lineas largas que dibujan los rectangulos. El borde de la imagen no cuenta."""
    w, h = im.size
    px = im.load()
    filas = [y for y in range(h) if sum(1 for x in range(0, w, 3) if _es_linea(px[x, y])) > w / 9]
    cols = [x for x in range(w) if sum(1 for y in range(0, h, 3) if _es_linea(px[x, y])) > h / 9]
    margen = 30
    return (
        [y for y in _agrupa(filas) if margen < y < h - margen],
        [x for x in _agrupa(cols) if margen < x < w - margen],
    )


def forma_del_espacio(im, rejilla_xs=None, rejilla_ys=None):
    """Si el limite del espacio es un rectangulo o no.

    Medir el negro mas a la izquierda y mas a la derecha de cada fila NO sirve: ahi entran
    las fichas, las flechas y el texto, y daba que un espacio rectangular no lo era. Hay que
    mirar SOLO donde deberia estar el contorno si fuera un rectangulo: si en las cuatro
    esquinas del rectangulo que abarca las lineas hay trazo, es un rectangulo; si las
    esquinas estan vacias y el trazo aparece mas adentro, es otra figura (un octogono corta
    justo las esquinas).
    """
    if not rejilla_xs or not rejilla_ys or len(rejilla_xs) < 2 or len(rejilla_ys) < 2:
        return None
    w, h = im.size
    px = im.load()
    negro = lambda c: c[0] < 70 and c[1] < 70 and c[2] < 70

    def hay(x, y, r=6):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and negro(px[nx, ny]):
                    return True
        return False

    x1, x2 = rejilla_xs[0], rejilla_xs[-1]
    y1, y2 = rejilla_ys[0], rejilla_ys[-1]
    esquinas = [hay(x1, y1), hay(x2, y1), hay(x1, y2), hay(x2, y2)]
    return {'rectangular': all(esquinas), 'esquinas_con_trazo': sum(esquinas),
            'caja': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}}


def leer(ruta):
    im = Image.open(ruta).convert('RGB')
    crudo = []
    for n_color, ref in enumerate(paleta(im)):
        for m in manchas(im, ref):
            crudo.append({'tipo': f'color{n_color}', 'color': ref, 'x': m['x'], 'y': m['y'], 'area': m['area']})
    # El LOGO del libro comparte colores con las fichas y se colaba como dos jugadores mas.
    # Todas las fichas de un dibujo son del MISMO tamanio: lo que mida bastante menos que la
    # mediana no es una ficha. Umbral relativo, porque cada ejercicio dibuja a su escala.
    if crudo:
        # Un color que produce CIENTOS de manchas no es un equipo: es el cesped, una trama o
        # el ruido del JPEG. Ningun ejercicio tiene 300 jugadores. Se descarta entero antes de
        # que contamine la mediana, que es lo que decide el tamanio de una ficha.
        por_color = {}
        for f in crudo:
            por_color.setdefault(f['tipo'], []).append(f)
        crudo = [f for t, g in por_color.items() if len(g) <= 40 for f in g]
    if crudo:
        areas = sorted(f['area'] for f in crudo)
        mediana = areas[len(areas) // 2]
        crudo = [f for f in crudo if f['area'] >= mediana * 0.45]

        # FICHAS PEGADAS. En las ruedas de pases el libro dibuja los jugadores de dos en dos,
        # tocandose, y una mancha son DOS fichas. Se parte por tamanio: una mancha que mide el
        # doble son dos, y se colocan una a cada lado del centro que se midio.
        partidas = []
        for f in crudo:
            cuantas = max(1, round(f['area'] / mediana)) if mediana else 1
            # TOPE: el libro dibuja como mucho tres o cuatro fichas pegadas. Sin tope, una
            # mancha enorme -el cesped, una trama- se partia en CIENTOS de jugadores: habia
            # dibujos devolviendo 3.222 fichas. Lo que mida mas de seis fichas no es un grupo
            # de fichas, es otra cosa, y se descarta entero.
            if cuantas > 6:
                continue
            cuantas = min(cuantas, 4)
            if cuantas <= 1:
                partidas.append(f)
                continue
            ancho = int((f['area'] / cuantas) ** 0.5)
            for k in range(cuantas):
                desplazado = dict(f)
                desplazado['x'] = f['x'] + int((k - (cuantas - 1) / 2) * ancho)
                desplazado['area'] = f['area'] // cuantas
                partidas.append(desplazado)
        crudo = partidas

        # EL BALON NO SE BUSCA POR COLOR NI POR TAMANIO. Lo intente por las dos y las dos
        # fallan: hay discos amarillos que son jugadores de otro equipo y miden lo mismo que
        # los demas (775 frente a 873 en la 75). El balon del libro es el icono de siempre,
        # BLANCO CON MANCHAS NEGRAS, asi que se busca por eso: una mancha clara, pequenia y
        # con negro dentro.
        for f in balones(im, mediana):
            crudo.append({'tipo': 'balon', 'x': f['x'], 'y': f['y'], 'area': f['area']})
    ys, xs = rejilla(im)
    # Cada hueco entre dos lineas seguidas es un rectangulo del dibujo. Se descartan las
    # franjas mas finas que un jugador: son el grosor de la propia linea, no una zona.
    # LO QUE HAY EN EL LIBRO SON SEPARACIONES, NO ZONAS. El libro parte el espacio con
    # lineas -continuas o discontinuas-, y pintarlas como recuadros amarillos rellenos dice
    # otra cosa: en nuestro sistema un recuadro amarillo es una ZONA DE INTERVENCION. Asi que
    # se devuelven las LINEAS con su estilo, y el contorno como un rectangulo sin relleno.
    lineas = []
    contorno = None
    if len(ys) >= 2 and len(xs) >= 2:
        px = im.load()
        w, h = im.size

        def _pintado(x, y):
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and _es_linea(px[nx, ny]):
                        return True
            return False

        def _cuanto(fijo, desde, hasta, horizontal):
            puntos = range(desde + 5, hasta - 5, max(3, (hasta - desde) // 24))
            total = acierto = 0
            for p in puntos:
                total += 1
                if (_pintado(p, fijo) if horizontal else _pintado(fijo, p)):
                    acierto += 1
            return (acierto / total) if total else 0.0

        # El contorno SOLO si esta dibujado de verdad. La caja que abarca todas las lineas no
        # siempre es un rectangulo del dibujo: en los ejercicios con cuatro bandas alrededor,
        # el conjunto forma una CRUZ y las esquinas estan vacias. Dibujarlo como rectangulo
        # anadia una linea que el libro no tiene.
        forma = forma_del_espacio(im, xs, ys)
        contorno = ({'x1': xs[0], 'y1': ys[0], 'x2': xs[-1], 'y2': ys[-1]}
                    if (forma and forma.get('rectangular')) else None)
        # Las divisiones interiores, cada una con su estilo. Mas del 90% pintado es una linea
        # continua; entre el 45 y el 90, discontinua; por debajo, no hay linea.
        for y in ys[1:-1]:
            c = _cuanto(y, xs[0], xs[-1], True)
            if c >= 0.45:
                lineas.append({'x1': xs[0], 'y1': y, 'x2': xs[-1], 'y2': y,
                               'estilo': 'continua' if c >= 0.9 else 'discontinua'})
        for x in xs[1:-1]:
            c = _cuanto(x, ys[0], ys[-1], False)
            if c >= 0.45:
                lineas.append({'x1': x, 'y1': ys[0], 'x2': x, 'y2': ys[-1],
                               'estilo': 'continua' if c >= 0.9 else 'discontinua'})

    return {'imagen': im.size, 'fichas': crudo, 'contorno': contorno, 'lineas': lineas,
            'forma': forma_del_espacio(im, xs, ys), 'rejilla': {'y': ys, 'x': xs}}


if __name__ == '__main__':
    d = leer(sys.argv[1])
    from collections import Counter
    est = dict(Counter(l['estilo'] for l in d['lineas']))
    print('fichas:', dict(Counter(f['tipo'] for f in d['fichas'])), '· contorno:', bool(d['contorno']), '· divisiones:', est)
    if len(sys.argv) > 2:
        json.dump(d, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
