"""
Terreno de juego de un equipo, desde Universo RFAF.

`teams/detail` devuelve la ficha COMPLETA del equipo y hasta ahora sólo se le sacaba la
plantilla (`fetch_universo_team_roster`). El campo de juego venía en el mismo sitio y se
tiraba: por eso ninguno de los equipos importados tenía estadio.

El extractor es tolerante a propósito, igual que el de la plantilla: la API no publica
esquema y las claves cambian entre delegaciones, así que se busca por NOMBRE de clave
recorriendo el árbol, en vez de fiarlo a una ruta fija que se rompa en la siguiente
temporada.
"""

from __future__ import annotations

import logging
import re


logger = logging.getLogger(__name__)


CLAVES_CAMPO = (
    'instalacion',
    'instalación',
    'campo',
    'estadio',
    'terreno',
    'terreno_juego',
    'campo_juego',
    'nombre_instalacion',
    'nombre_campo',
    'des_instalacion',
)
CLAVES_DIRECCION = (
    'direccion',
    'dirección',
    'domicilio',
    'direccion_instalacion',
    'des_direccion',
    'calle',
)
CLAVES_LOCALIDAD = ('localidad', 'poblacion', 'población', 'municipio', 'ciudad')
CLAVES_CP = ('cp', 'codigo_postal', 'código_postal', 'cod_postal')
# Ruido que aparece con esas mismas palabras y no es el campo del equipo.
VALORES_DESCARTABLES = {'', '-', '--', 'n/a', 'na', 'null', 'none', 'sin datos', '0'}


def _normalizar_clave(clave):
    texto = str(clave or '').strip().lower()
    return re.sub(r'[^a-z0-9]+', '_', texto).strip('_')


def _texto_util(valor):
    if isinstance(valor, (int, float)):
        return ''
    texto = str(valor or '').strip()
    if texto.lower() in VALORES_DESCARTABLES:
        return ''
    if len(texto) > 260:
        return ''
    return texto


def _buscar_por_claves(payload, claves, *, profundidad_max=6):
    """Primer valor de texto útil cuya clave contenga alguna de las buscadas."""
    objetivo = {_normalizar_clave(c) for c in claves}

    def _walk(nodo, profundidad):
        if profundidad > profundidad_max:
            return ''
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                clave_norm = _normalizar_clave(clave)
                if any(o in clave_norm for o in objetivo):
                    texto = _texto_util(valor)
                    if texto:
                        return texto
            for valor in list(nodo.values())[:120]:
                encontrado = _walk(valor, profundidad + 1)
                if encontrado:
                    return encontrado
            return ''
        if isinstance(nodo, list):
            for item in nodo[:80]:
                encontrado = _walk(item, profundidad + 1)
                if encontrado:
                    return encontrado
        return ''

    return _walk(payload, 0)


def extraer_campo_de_juego(payload):
    """
    Devuelve {'name', 'address', 'maps_url'} a partir de la ficha de equipo de Universo.

    La dirección se compone con lo que haya (calle + código postal + localidad): en la
    ficha vienen en campos separados y sueltos no sirven para llegar al campo.
    """
    if not isinstance(payload, (dict, list)):
        return {'name': '', 'address': '', 'maps_url': ''}

    nombre = _buscar_por_claves(payload, CLAVES_CAMPO)
    calle = _buscar_por_claves(payload, CLAVES_DIRECCION)
    localidad = _buscar_por_claves(payload, CLAVES_LOCALIDAD)
    cp = _buscar_por_claves(payload, CLAVES_CP)

    partes = [p for p in (calle, cp, localidad) if p]
    direccion = ', '.join(partes)[:260]

    maps_url = ''
    consulta = ', '.join([p for p in (nombre, direccion or localidad) if p])
    if consulta:
        from urllib.parse import quote_plus

        maps_url = f'https://www.google.com/maps/search/?api=1&query={quote_plus(consulta)}'

    return {'name': nombre[:200], 'address': direccion, 'maps_url': maps_url}


def aplicar_campo_de_juego(team, datos, *, sobrescribir=False):
    """
    Escribe el campo en el equipo. Devuelve la lista de campos tocados.

    Con `sobrescribir=False` sólo rellena huecos; el usuario puede pedir que se corrija lo
    que ya había (un dato mal copiado es peor que un hueco: manda a alguien a otro pueblo).
    """
    cambios = []
    nombre = str(datos.get('name') or '').strip()
    direccion = str(datos.get('address') or '').strip()
    maps_url = str(datos.get('maps_url') or '').strip()

    if nombre and (sobrescribir or not str(getattr(team, 'home_stadium', '') or '').strip()):
        if nombre != getattr(team, 'home_stadium', ''):
            team.home_stadium = nombre[:200]
            cambios.append('home_stadium')
    if direccion and (sobrescribir or not str(getattr(team, 'home_stadium_address', '') or '').strip()):
        if direccion != getattr(team, 'home_stadium_address', ''):
            team.home_stadium_address = direccion[:260]
            cambios.append('home_stadium_address')
    if maps_url and (sobrescribir or not str(getattr(team, 'home_stadium_maps_url', '') or '').strip()):
        if maps_url != getattr(team, 'home_stadium_maps_url', ''):
            team.home_stadium_maps_url = maps_url
            cambios.append('home_stadium_maps_url')

    if cambios:
        team.save(update_fields=cambios)
    return cambios


def sincronizar_campos_de_equipos(teams, *, sobrescribir=False, fetch=None):
    """
    Recorre equipos y les pone su campo de juego. `fetch` se inyecta para poder probarlo
    sin red. Devuelve un resumen legible: lo que se hizo y lo que no, y por qué.
    """
    if fetch is None:
        from .universo_client import universo_internal_post

        def fetch(codigo):
            return universo_internal_post('teams/detail', {'cod_equipo': codigo})

    resumen = {'actualizados': [], 'sin_codigo': [], 'sin_datos': [], 'errores': []}
    for team in teams:
        codigo = str(getattr(team, 'external_id', '') or '').strip()
        if not codigo:
            resumen['sin_codigo'].append(team.name)
            continue
        try:
            payload = fetch(codigo)
        except Exception as exc:
            logger.warning('Universo falló para el equipo %s: %s', team.name, exc)
            resumen['errores'].append(f'{team.name}: {exc}')
            continue
        datos = extraer_campo_de_juego(payload)
        if not datos.get('name') and not datos.get('address'):
            resumen['sin_datos'].append(team.name)
            continue
        cambios = aplicar_campo_de_juego(team, datos, sobrescribir=sobrescribir)
        if cambios:
            resumen['actualizados'].append(f"{team.name} → {datos.get('name') or datos.get('address')}")
        else:
            resumen['sin_datos'].append(f'{team.name} (ya lo tenía)')
    return resumen
