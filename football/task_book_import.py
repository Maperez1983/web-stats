"""Meter en la biblioteca tareas sacadas de un libro, con su ficha y su pizarra.

Un libro de tareas no entra por el importador de PPTX: sus gráficos son imágenes rasterizadas
(un render 3D del campo), no formas vectoriales que se puedan traducir. Así que la ficha se
extrae fuera —texto y posiciones leídos del PDF— y aquí entra ya montada, incluidos los objetos
del editor, para que el dibujo quede EDITABLE y no una foto pegada.

Las tareas caen en una colección con nombre (`SessionTaskCollection`), que es lo que en la
biblioteca se ve como una estantería aparte: así lo importado no se mezcla con lo del club.
"""

import logging

from .library_repositories import LIBRARY_REPOSITORY_INTERACTIVE
from .models import SessionTask, SessionTaskCollection, SessionTaskCollectionItem
from .session_import_services import get_or_create_library_session_with_repository

logger = logging.getLogger(__name__)

COLECCION_POR_DEFECTO = 'Tareas importadas'

# Del texto del libro a la taxonomía del sistema. Sólo lo que se puede afirmar sin adivinar:
# lo que no venga claro se queda vacío antes que inventado, porque estas columnas alimentan
# los filtros de la biblioteca y el recomendador.
MOMENTOS = {
    'posesion': 'offensive_organization',
    'no_posesion': 'defensive_organization',
    'transicion_ofensiva': 'offensive_transition',
    'transicion_defensiva': 'defensive_transition',
    'abp': 'set_pieces',
}
ESTRUCTURAS = {
    'condicional': 'conditional',
    'coordinativa': 'coordinative',
    'cognitiva': 'cognitive',
    'socio_afectiva': 'socio_affective',
    'emotivo_volitiva': 'emotional_volitional',
    'creativo_expresiva': 'creative_expressive',
}
CONTENIDOS = {
    'tactico': 'tactical',
    'tecnico': 'technical',
    'fisico': 'physical',
    'psicologico': 'psychological',
}


# Estilo de las zonas y las líneas del editor. NO es cosmética opcional: un rect sin `fill`
# explícito lo pinta el lienzo NEGRO Y OPACO, y una zona así tapa el campo entero y las fichas
# que tiene debajo. Pasó con las dos primeras tareas del libro (2026-08-04): en el editor sólo
# se veía un rectángulo negro. Por eso se rellena aquí y no se confía en quien manda el lote.
ESTILO_ZONA = {'fill': 'rgba(56,189,248,0.16)', 'stroke': '#38bdf8', 'strokeDashArray': [8, 6]}
ESTILO_LINEA = {'stroke': '#38bdf8', 'strokeWidth': 3, 'fill': ''}


def _texto(valor, limite=8000):
    return str(valor or '').strip()[:limite]


# Cada pieza, con su forma y su color. El lienzo NO deduce nada de `data.kind`: un circulo sin
# `radius` se dibuja de tamaño cero y una ficha sin contenido es un envoltorio vacio. Las dos
# primeras tareas del libro entraron asi y el campo salia sin jugadores, conos ni balon.
RADIO_FICHA = 22
PIEZAS = {
    'player_local': {'color': '#2f7d32', 'borde': '#f8fafc', 'radio': RADIO_FICHA},
    'player_rival': {'color': '#e03127', 'borde': '#f8fafc', 'radio': RADIO_FICHA},
    # El comodín NO es de ningún equipo: juega con quien tenga la pelota, así que no puede salir
    # del color de los locales como si fuera uno más.
    'player_joker': {'color': '#facc15', 'borde': '#0f172a', 'radio': RADIO_FICHA},
    'goalkeeper_local': {'color': '#0ea5e9', 'borde': '#f8fafc', 'radio': RADIO_FICHA},
    'goalkeeper_rival': {'color': '#a855f7', 'borde': '#f8fafc', 'radio': RADIO_FICHA},
    'cone': {'color': '#f97316', 'borde': '#7c2d12', 'radio': 9},
    'ball': {'color': '#f8fafc', 'borde': '#0f172a', 'radio': 8},
}
# Las porterías pequeñas que el libro dibuja DENTRO del espacio reducido. Las del campo, al
# fondo, no sirven: la tarea se juega en el cuadrado, no en el campo entero.
PORTERIA = {'ancho': 14, 'alto': 86, 'color': '#f8fafc'}


def _ficha(kind, left, top, label=''):
    """Una ficha de jugador es un GRUPO: el disco de su equipo y, encima, su etiqueta."""
    pieza = PIEZAS[kind]
    radio = pieza['radio']
    hijos = [{
        'type': 'circle', 'radius': radio, 'left': -radio, 'top': -radio,
        'fill': pieza['color'], 'stroke': pieza['borde'], 'strokeWidth': 3,
    }]
    texto = str(label or '').strip()[:3]
    if texto:
        hijos.append({
            'type': 'text', 'text': texto, 'fontSize': 20, 'fontWeight': 'bold',
            'fill': pieza['borde'], 'left': -7 * len(texto), 'top': -11,
        })
    return {
        'type': 'group', 'left': left, 'top': top,
        'width': radio * 2, 'height': radio * 2,
        'objects': hijos, 'data': {'kind': kind, 'label': texto},
    }


def _normalizar_objeto(obj):
    """Completa lo que el lienzo necesita para pintar un objeto sin sorpresas."""
    if not isinstance(obj, dict):
        return None
    salida = dict(obj)
    kind = str((salida.get('data') or {}).get('kind') or '').strip().lower()
    left = salida.get('left', 0)
    top = salida.get('top', 0)

    if kind in {'goal', 'goal_mini'}:
        # Portería pequeña dentro del espacio: un rectángulo estrecho con su marco.
        alto = float(salida.pop('height', 0) or PORTERIA['alto'])
        ancho = float(salida.pop('width', 0) or PORTERIA['ancho'])
        salida['type'] = 'rect'
        salida['left'] = left - ancho / 2
        salida['top'] = top - alto / 2
        salida['width'] = ancho
        salida['height'] = alto
        salida.setdefault('fill', 'rgba(248,250,252,0.28)')
        salida.setdefault('stroke', PORTERIA['color'])
        salida.setdefault('strokeWidth', 4)
        return salida

    if kind in PIEZAS:
        etiqueta = str((salida.get('data') or {}).get('label') or '')
        if kind in {'cone', 'ball'}:
            pieza = PIEZAS[kind]
            salida.setdefault('type', 'circle')
            salida.setdefault('radius', pieza['radio'])
            salida.setdefault('fill', str((salida.get('data') or {}).get('color') or pieza['color']))
            salida.setdefault('stroke', pieza['borde'])
            salida.setdefault('strokeWidth', 2)
            return salida
        return _ficha(kind, left, top, etiqueta)

    if kind == 'zone':
        for clave, valor in ESTILO_ZONA.items():
            salida.setdefault(clave, valor)
    elif kind in {'line_solid', 'line_dashed', 'arrow_run', 'arrow_pass'}:
        for clave, valor in ESTILO_LINEA.items():
            salida.setdefault(clave, valor)
        if kind == 'line_dashed':
            salida.setdefault('strokeDashArray', [10, 8])
        # Una línea se dibuja por sus DOS EXTREMOS, no por posición y tamaño: con left/top/width/
        # height el lienzo no pinta nada. Por eso las subzonas de las tareas del libro salían sin
        # dividir, contradiciendo su propia descripción ("espacio dividido en 6 subzonas iguales").
        if 'x1' not in salida:
            ancho = float(salida.pop('width', 0) or 0)
            alto = float(salida.pop('height', 0) or 0)
            salida['x1'] = left
            salida['y1'] = top
            salida['x2'] = left + ancho
            salida['y2'] = top + alto
    elif salida.get('type') == 'rect':
        # Cualquier otro rectángulo sin relleno tendría el mismo problema.
        salida.setdefault('fill', 'rgba(255,255,255,0.10)')
        salida.setdefault('stroke', '#e2e8f0')
    elif salida.get('type') == 'circle':
        salida.setdefault('radius', 10)
        salida.setdefault('fill', '#e2e8f0')
    return salida


def _meta_de_la_ficha(ficha):
    """El JSON es la fuente de verdad: las columnas queryables las deriva SessionTask.save()
    desde `tactical_layout['meta']`, así que la metodología se escribe AQUÍ, no en el modelo."""
    meta = {
        'repository': LIBRARY_REPOSITORY_INTERACTIVE,
        'game_moment': MOMENTOS.get(str(ficha.get('momento') or '').strip().lower(), ''),
        'dominant_structure': ESTRUCTURAS.get(str(ficha.get('estructura') or '').strip().lower(), ''),
        'content_domain': CONTENIDOS.get(str(ficha.get('contenido') or '').strip().lower(), ''),
        'structure': _texto(ficha.get('situacion'), 40),
        'principle': _texto(ficha.get('principio'), 160),
        'subprinciple': _texto(ficha.get('subprincipio'), 200),
    }
    fuente = _texto(ficha.get('fuente'), 200)
    if fuente:
        # De dónde salió cada tarea. Sin esto, dentro de un año nadie sabe si una ficha la
        # escribió el club o vino de un libro, y eso importa para saber qué se puede compartir.
        meta['source'] = fuente
    objetos = ficha.get('objetos')
    if isinstance(objetos, list) and objetos:
        pintables = [o for o in (_normalizar_objeto(x) for x in objetos) if o]
        if pintables:
            meta['graphic_editor'] = {'canvas_state': {'objects': pintables}}
    return meta


def _notas_de_la_ficha(ficha):
    partes = []
    for etiqueta, clave in (('Bio-energético / condicional', 'bioenergetico'), ('Consideraciones', 'consideraciones')):
        valor = _texto(ficha.get(clave))
        if valor:
            partes.append(f'{etiqueta}: {valor}')
    fuente = _texto(ficha.get('fuente'), 200)
    if fuente:
        partes.append(f'Fuente: {fuente}')
    return '\n\n'.join(partes)


def importar_fichas(team, fichas, *, coleccion=COLECCION_POR_DEFECTO, scope_key='coach', escribir=True, actualizar=False):
    """Crea en la biblioteca del equipo una tarea por ficha y las agrupa en `coleccion`.

    Idempotente por título dentro de la colección: repetir la importación no duplica. Con
    `actualizar`, en vez de saltar la que ya existe le reescribe ficha y pizarra — que es lo que
    hace falta cuando el lote se corrige (p. ej. un dibujo que salía mal) y hay que reimportarlo.

    Devuelve un resumen con lo creado, lo actualizado, lo que ya estaba y lo que se descartó.
    """
    resumen = {'creadas': [], 'actualizadas': [], 'ya_estaban': [], 'descartadas': []}
    if not team or not fichas:
        return resumen

    session = get_or_create_library_session_with_repository(
        team, scope_key, repository=LIBRARY_REPOSITORY_INTERACTIVE
    ) if escribir else None

    estanteria = None
    previas = {}
    if escribir:
        estanteria, _ = SessionTaskCollection.objects.get_or_create(
            team=team,
            repository=SessionTaskCollection.REPO_INTERACTIVE,
            name=str(coleccion or COLECCION_POR_DEFECTO)[:120],
        )
        previas = {
            str(item.task.title): item.task
            for item in SessionTaskCollectionItem.objects.filter(collection=estanteria).select_related('task')
            if item.task
        }
    titulos_previos = set(previas.keys())

    orden = 0
    for ficha in fichas:
        if not isinstance(ficha, dict):
            resumen['descartadas'].append('entrada que no es una ficha')
            continue
        titulo = _texto(ficha.get('titulo'), 160)
        if not titulo:
            resumen['descartadas'].append('ficha sin título')
            continue
        if titulo in titulos_previos:
            if not (actualizar and escribir):
                resumen['ya_estaban'].append(titulo)
                continue
            tarea = previas.get(titulo)
            try:
                tarea.objective = _texto(ficha.get('descripcion'))
                tarea.coaching_points = _texto(ficha.get('comportamientos'))
                tarea.confrontation_rules = _texto(ficha.get('reglas'))
                tarea.notes = _notas_de_la_ficha(ficha)
                tarea.duration_minutes = int(ficha.get('minutos') or tarea.duration_minutes or 15)
                tarea.tactical_layout = {'meta': _meta_de_la_ficha(ficha)}
                tarea.save()
                resumen['actualizadas'].append(titulo)
            except Exception:
                logger.exception('No se pudo actualizar la tarea %s', titulo)
                resumen['descartadas'].append(titulo)
            continue

        if not escribir:
            resumen['creadas'].append(titulo)
            titulos_previos.add(titulo)
            continue

        orden += 1
        try:
            tarea = SessionTask.objects.create(
                session=session,
                title=titulo,
                block=_texto(ficha.get('bloque'), 30) or SessionTask.BLOCK_MAIN_1,
                duration_minutes=int(ficha.get('minutos') or 15),
                objective=_texto(ficha.get('descripcion')),
                coaching_points=_texto(ficha.get('comportamientos')),
                confrontation_rules=_texto(ficha.get('reglas')),
                notes=_notas_de_la_ficha(ficha),
                tactical_layout={'meta': _meta_de_la_ficha(ficha)},
                order=orden,
            )
            SessionTaskCollectionItem.objects.get_or_create(collection=estanteria, task=tarea)
            resumen['creadas'].append(titulo)
            titulos_previos.add(titulo)
        except Exception:
            logger.exception('No se pudo importar la tarea %s', titulo)
            resumen['descartadas'].append(titulo)
    return resumen
