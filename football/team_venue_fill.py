"""Rellenar de golpe el campo y la dirección de los equipos.

Los datos vienen de la ficha del club en la federación, que hay que leer desde un navegador
(el servidor recibe 403 de laPreferente). Así que se extraen fuera y entran aquí en UN lote,
en vez de ficha por ficha: abrir 66 formularios del admin tumba el servidor.

Regla: NO se pisa lo que ya hay. Un dato escrito a mano por el club vale más que el de la
federación; esto sólo rellena huecos, salvo que se pida `sobrescribir`.
"""

CAMPOS = {
    'campo': 'home_stadium',
    'direccion': 'home_stadium_address',
    'maps': 'home_stadium_maps_url',
}

LIMITES = {
    'home_stadium': 200,
    'home_stadium_address': 260,
    'home_stadium_maps_url': 600,
}


def _limpiar(valor, destino):
    texto = str(valor or '').strip()
    if not texto:
        return ''
    return texto[: LIMITES.get(destino, 200)]


def rellenar_campos(equipos_por_id, filas, *, sobrescribir=False, escribir=True):
    """Aplica `filas` (lista de dicts con id/campo/direccion/maps) sobre los equipos dados.

    `equipos_por_id`: {id: Team}. Devuelve un resumen con lo cambiado, lo respetado (ya tenía
    dato) y lo que no casó con ningún equipo. Con `escribir=False` no toca nada: sirve para
    ver antes qué haría.
    """
    resumen = {'actualizados': [], 'ya_tenian': [], 'sin_equipo': [], 'sin_datos': []}
    for fila in filas or []:
        if not isinstance(fila, dict):
            continue
        try:
            equipo_id = int(fila.get('id') or 0)
        except (TypeError, ValueError):
            equipo_id = 0
        equipo = equipos_por_id.get(equipo_id)
        if not equipo:
            resumen['sin_equipo'].append(fila.get('id'))
            continue

        cambios = {}
        for clave, destino in CAMPOS.items():
            nuevo = _limpiar(fila.get(clave), destino)
            if not nuevo:
                continue
            actual = str(getattr(equipo, destino, '') or '').strip()
            if actual and not sobrescribir:
                continue
            if actual == nuevo:
                continue
            cambios[destino] = nuevo

        if not cambios:
            tenia = any(str(getattr(equipo, d, '') or '').strip() for d in CAMPOS.values())
            (resumen['ya_tenian'] if tenia else resumen['sin_datos']).append(
                f'{equipo.id}:{equipo.name}'
            )
            continue

        if escribir:
            for destino, valor in cambios.items():
                setattr(equipo, destino, valor)
            equipo.save(update_fields=sorted(cambios.keys()))
        resumen['actualizados'].append(
            f'{equipo.id}:{equipo.name} · ' + ', '.join(sorted(cambios.keys()))
        )
    return resumen
