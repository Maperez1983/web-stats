from __future__ import annotations

from typing import Iterable, List


_SYNONYMS = {
    # Fases
    'salida de balon': 'salida de balón',
    'salida de balón (build up)': 'salida de balón',
    'build up': 'salida de balón',
    'inicio': 'salida de balón',
    'presion': 'presión',
    'presión alta': 'presión',
    'presión media': 'presión',
    'transicion': 'transición',
    'transiciones': 'transición',
    'transición defensa ataque': 'transición',
    'transición ataque defensa': 'transición',
    'finalizacion': 'finalización',
    'defensa del area': 'defensa del área',
    'defensa area': 'defensa del área',
    # Tipos / ejercicios
    'ssg': 'SSG',
    'juego reducido': 'SSG',
    'juegos reducidos': 'SSG',
    'posesion': 'posesión',
    'posesión': 'posesión',
    'rondo': 'posesión',
    'rondos': 'posesión',
    'tecnica': 'técnica',
    'técnico': 'técnica',
    'técnico-táctico': 'técnica',
    # Objetivos / contextos
    'futbol base': 'fútbol base',
    'prebenjamin': 'fútbol base',
    'pre-benjamin': 'fútbol base',
    'benjamin': 'fútbol base',
    'alevin': 'fútbol base',
    'alevín': 'fútbol base',
    'fisico': 'físico',
    'preparacion fisica': 'físico',
    'preparación física': 'físico',
    'abp': 'ABP',
    'estrategia': 'ABP',
    'balon parado': 'ABP',
    'balón parado': 'ABP',
}


def normalize_tag(value: str) -> str:
    raw = str(value or '').strip()
    if not raw:
        return ''
    key = raw.lower().strip()
    key = key.replace('_', ' ').replace('-', ' ')
    key = ' '.join([chunk for chunk in key.split() if chunk])
    mapped = _SYNONYMS.get(key)
    if mapped:
        return mapped
    # Mantén abreviaturas en mayúsculas (SSG/ABP), resto en formato original.
    if raw.upper() in {'SSG', 'ABP'}:
        return raw.upper()
    return raw


def normalize_tags(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values or []:
        norm = normalize_tag(str(value))
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out

