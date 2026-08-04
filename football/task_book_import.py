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


def _texto(valor, limite=8000):
    return str(valor or '').strip()[:limite]


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
        meta['graphic_editor'] = {'canvas_state': {'objects': objetos}}
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


def importar_fichas(team, fichas, *, coleccion=COLECCION_POR_DEFECTO, scope_key='coach', escribir=True):
    """Crea en la biblioteca del equipo una tarea por ficha y las agrupa en `coleccion`.

    Idempotente por título dentro de la colección: repetir la importación no duplica. Devuelve
    un resumen con lo creado, lo que ya estaba y lo que se descartó.
    """
    resumen = {'creadas': [], 'ya_estaban': [], 'descartadas': []}
    if not team or not fichas:
        return resumen

    session = get_or_create_library_session_with_repository(
        team, scope_key, repository=LIBRARY_REPOSITORY_INTERACTIVE
    ) if escribir else None

    estanteria = None
    if escribir:
        estanteria, _ = SessionTaskCollection.objects.get_or_create(
            team=team,
            repository=SessionTaskCollection.REPO_INTERACTIVE,
            name=str(coleccion or COLECCION_POR_DEFECTO)[:120],
        )
        titulos_previos = set(
            SessionTaskCollectionItem.objects.filter(collection=estanteria).values_list('task__title', flat=True)
        )
    else:
        titulos_previos = set()

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
            resumen['ya_estaban'].append(titulo)
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
