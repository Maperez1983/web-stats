"""
Política de visibilidad del portal del jugador.

Antes, "lo que ve el jugador" estaba escrito en el HTML: 23 condicionales repartidos por la
ficha decidían, uno a uno, qué se pintaba. Nadie del club podía cambiarlo y nadie podía
mirarlo de un vistazo.

Aquí hay UNA fuente: un mapa `sección -> estado` que resuelve tres capas, de menos a más
concreta:

    1. DEFAULTS      (este fichero; todo lo sensible cerrado)
    2. PlayerPortalPolicy del club   (por workspace, y opcionalmente por equipo/categoría)
    3. Player.portal_overrides       (la excepción de un jugador concreto)

La vista pregunta una vez y pasa el mapa a la plantilla; la plantilla obedece y no decide.

Tres estados por sección:

    HIDDEN          el jugador no ve la sección
    VISIBLE         ve el dato tal cual está
    PUBLISHED_ONLY  ve sólo los registros que el staff ha publicado a propósito

`PUBLISHED_ONLY` es la que sostiene el modelo entero: publicar es un gesto deliberado
(como "Publicar 11 y avisar"), no el estado crudo de la base de datos. La sección abierta y
el registro publicado son DOS llaves, y hacen falta las dos.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


HIDDEN = 'hidden'
VISIBLE = 'visible'
PUBLISHED_ONLY = 'published_only'

STATE_CHOICES = [
    (HIDDEN, 'Oculto'),
    (VISIBLE, 'Visible'),
    (PUBLISHED_ONLY, 'Sólo lo publicado'),
]
VALID_STATES = {HIDDEN, VISIBLE, PUBLISHED_ONLY}

# Secciones del portal. `states` limita los estados que tienen sentido para esa sección:
# "sólo lo publicado" no significa nada donde no hay registros que publicar (rendimiento,
# físico), así que allí sólo se ofrece visible/oculto y no se puede configurar un estado
# imposible desde el JSON.
SECTIONS = [
    {
        'key': 'performance',
        'label': 'Rendimiento',
        'help': 'Minutos, partidos, carga de entreno vs partido. Hechos suyos.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'evaluation',
        'label': 'Evaluación',
        'help': 'Valoraciones del cuerpo técnico. Incluye la media, los percentiles y todo lo derivado.',
        'default': PUBLISHED_ONLY,
        'states': (HIDDEN, PUBLISHED_ONLY),
    },
    {
        'key': 'physical',
        'label': 'Físico y wellness',
        'help': 'Wellness, RPE y tests físicos. Buena parte la rellena él.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'injuries',
        'label': 'Lesiones',
        'help': 'Su historial de lesiones y plazos.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'seasons',
        'label': 'Histórico',
        'help': 'Temporadas anteriores.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'communication',
        'label': 'Comunicación',
        'help': 'Mensajes del staff. Las notas internas y los partes médicos NUNCA son suyos.',
        'default': PUBLISHED_ONLY,
        'states': (HIDDEN, PUBLISHED_ONLY),
    },
    {
        'key': 'fines',
        'label': 'Multas',
        'help': 'Sanciones económicas. Le afectan, debe poder verlas.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'videos',
        'label': 'Vídeos',
        'help': 'Clips e informes que le manda el staff (el buzón ya funciona así).',
        'default': PUBLISHED_ONLY,
        'states': (HIDDEN, PUBLISHED_ONLY),
    },
    {
        'key': 'objectives',
        # Hoy TODO objetivo de la ficha lo asigna el entrenador: no existe el borrador, así
        # que "sólo lo publicado" sería una etiqueta vacía. Cuando la fase 3 añada el
        # borrador, esta sección pasa a PUBLISHED_ONLY sin tocar nada más.
        'label': 'Objetivos',
        'help': 'Los objetivos que el entrenador le asigna.',
        'default': VISIBLE,
        'states': (HIDDEN, VISIBLE),
    },
    {
        'key': 'documents',
        'label': 'Documentos',
        'help': 'Ficha federativa y demás papeles. Se abre a propósito.',
        'default': HIDDEN,
        'states': (HIDDEN, VISIBLE),
    },
]

SECTION_KEYS = tuple(section['key'] for section in SECTIONS)
_SECTION_BY_KEY = {section['key']: section for section in SECTIONS}


def default_sections() -> dict:
    """El arranque de cualquier club: lo sensible cerrado. Se enciende, no se apaga."""
    return {section['key']: section['default'] for section in SECTIONS}


def normalize_sections(raw, *, base=None) -> dict:
    """
    Funde un JSON cualquiera sobre `base` quedándose sólo con lo que tiene sentido.

    Tolerante a propósito: claves desconocidas, estados inventados o un JSON corrupto no
    pueden dejar el portal en un estado indefinido — se ignoran y manda el valor de abajo.
    Un estado no permitido para esa sección (p.ej. `visible` en evaluación) tampoco entra:
    ahí "visible" significaría enseñar valoraciones sin publicar.
    """
    resolved = dict(base) if base else default_sections()
    if not isinstance(raw, dict):
        return resolved
    for key, value in raw.items():
        section = _SECTION_BY_KEY.get(str(key))
        if not section:
            continue
        state = str(value or '').strip().lower()
        if state not in VALID_STATES or state not in section['states']:
            continue
        resolved[section['key']] = state
    return resolved


def policy_sections_for(workspace, team=None) -> dict:
    """Capa 2: la política del club, afinada por equipo si ese equipo tiene la suya."""
    resolved = default_sections()
    if not workspace:
        return resolved
    try:
        from .models import PlayerPortalPolicy

        rows = list(
            PlayerPortalPolicy.objects.filter(workspace=workspace).filter(
                models_q_team_filter(team)
            )
        )
    except Exception:
        logger.debug('No se pudo leer la política del portal del workspace %s',
                     getattr(workspace, 'id', None), exc_info=True)
        return resolved

    # La del club primero (team vacío) y encima la de la categoría, que es más concreta.
    rows.sort(key=lambda row: 1 if getattr(row, 'team_id', None) else 0)
    for row in rows:
        resolved = normalize_sections(getattr(row, 'sections', None), base=resolved)
    return resolved


def models_q_team_filter(team):
    """Filtro `team is null OR team = X` sin importar Q en el módulo de modelos."""
    from django.db.models import Q

    if team is None:
        return Q(team__isnull=True)
    try:
        return Q(team__isnull=True) | Q(team_id=int(getattr(team, 'id', team)))
    except Exception:
        return Q(team__isnull=True)


def player_portal_visibility(player, *, workspace=None, team=None) -> dict:
    """
    Mapa final de un jugador: `{'performance': 'visible', 'evaluation': 'hidden', ...}`.

    Nunca lanza: ante cualquier duda devuelve los defaults, que son los cerrados. Una
    política ilegible no puede convertirse en una fuga.
    """
    try:
        if team is None:
            team = getattr(player, 'team', None)
        resolved = policy_sections_for(workspace, team=team)
        overrides = getattr(player, 'portal_overrides', None) if player is not None else None
        return normalize_sections(overrides, base=resolved)
    except Exception:
        logger.debug('No se pudo resolver la visibilidad del portal para el jugador %s',
                     getattr(player, 'id', None), exc_info=True)
        return default_sections()


class PortalVisibility:
    """
    Envoltorio para las plantillas.

    Django no sabe llamar funciones con argumentos en un `{% if %}`, así que la vista deja
    esto en el contexto y la plantilla escribe lo que se lee solo:

        {% if vis.evaluation %}            la sección se pinta (visible o sólo-publicado)
        {% if vis.evaluation_published %}  además, sólo registros publicados
        {% if vis.communication_full %}    el dato entero, sin filtrar (staff)
    """

    def __init__(self, sections: dict, *, unrestricted: bool = False):
        self._sections = dict(sections or {})
        self._unrestricted = bool(unrestricted)

    @property
    def sections(self) -> dict:
        return dict(self._sections)

    @property
    def unrestricted(self) -> bool:
        """True para el staff: ve todo, la política sólo describe al jugador."""
        return self._unrestricted

    def state(self, key: str) -> str:
        if self._unrestricted:
            return VISIBLE
        return self._sections.get(str(key), HIDDEN)

    def __getattr__(self, name):
        # `vis.evaluation` / `vis.evaluation_published` / `vis.evaluation_full`
        raw = str(name or '')
        if raw.startswith('_'):
            raise AttributeError(name)
        for suffix, answer in (
            ('_published', lambda state: state == PUBLISHED_ONLY),
            ('_full', lambda state: state == VISIBLE),
        ):
            if raw.endswith(suffix):
                key = raw[: -len(suffix)]
                if key in _SECTION_BY_KEY:
                    return answer(self.state(key))
        if raw in _SECTION_BY_KEY:
            return self.state(raw) != HIDDEN
        raise AttributeError(name)

    def __contains__(self, key):
        return str(key) in _SECTION_BY_KEY

    def __repr__(self):
        return f'PortalVisibility(unrestricted={self._unrestricted}, sections={self._sections})'


def visibility_for_request(player, *, workspace=None, team=None, is_player_view: bool) -> PortalVisibility:
    """
    Lo que llama la vista.

    `is_player_view` es True cuando quien mira es el jugador (o el staff usando la
    previsualización, que debe ser fiel). Para el staff devuelve un envoltorio sin
    restricciones: la política describe qué ve el JUGADOR, no qué puede ver el entrenador.
    """
    if not is_player_view:
        return PortalVisibility(default_sections(), unrestricted=True)
    return PortalVisibility(player_portal_visibility(player, workspace=workspace, team=team))
