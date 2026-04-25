from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CycleSessionTemplate:
    day_offset: int
    focus: str
    intensity: str = 'medium'
    duration_minutes: int = 90


@dataclass(frozen=True)
class CycleWeekTemplate:
    title: str
    objective: str = ''
    sessions: List[CycleSessionTemplate] = ()


@dataclass(frozen=True)
class CycleTemplate:
    key: str
    label: str
    weeks: int
    description: str = ''
    week_titles: Optional[List[str]] = None
    week_templates: Optional[List[CycleWeekTemplate]] = None


def cycle_templates_catalog() -> List[CycleTemplate]:
    # Plantillas "tipo CoachLab": suficientes para empezar y personalizar.
    # No son rígidas: el entrenador puede ajustar focos/días una vez creadas.
    return [
        CycleTemplate(
            key='competition_4w',
            label='Competición (4 semanas) · 3 sesiones + partido',
            weeks=4,
            description='Estructura semanal estándar: carga media → alta → activación + ABP → partido.',
            week_templates=[
                CycleWeekTemplate(
                    title='Semana 1',
                    objective='Consolidar salida + presión tras pérdida.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-5 · Técnica + salida de balón', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Presión + transiciones (SSG)', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Finalización + centros + vigilancia.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-5 · Finalización + centros', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Ataque organizado (SSG)', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Defensa del área + repliegue + contras.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-5 · Defensa del área', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Transición defensa→ataque', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Repaso modelo + ajustes rival.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-5 · Repaso modelo (técnico-táctico)', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Rival (patrones + ABP)', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · Activación + estrategia', intensity='low', duration_minutes=75),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90),
                    ],
                ),
            ],
        ),
        CycleTemplate(
            key='preseason_4w',
            label='Pretemporada (4 semanas) · 4 sesiones',
            weeks=4,
            description='Progresión físico-técnica con integración táctica básica.',
            week_templates=[
                CycleWeekTemplate(
                    title='Semana 1',
                    objective='Base aeróbica + técnica (orientación corporal).',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Base física + técnica', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=2, focus='Técnica + duelos', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='SSG + transiciones', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Velocidad + cambios de dirección + ataque rápido.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Velocidad + técnica', intensity='high', duration_minutes=85),
                        CycleSessionTemplate(day_offset=2, focus='SSG + finalización', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=3, focus='Modelo básico (salida + presión)', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Resistencia específica (SSG) + ABP.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='SSG resistencia específica', intensity='high', duration_minutes=90),
                        CycleSessionTemplate(day_offset=2, focus='ABP ofensiva/defensiva', intensity='medium', duration_minutes=80),
                        CycleSessionTemplate(day_offset=3, focus='Táctica: transiciones', intensity='medium', duration_minutes=90),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Afinar modelo + carga descendente.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Modelo: salida + presión', intensity='medium', duration_minutes=85),
                        CycleSessionTemplate(day_offset=2, focus='Activación + ABP', intensity='low', duration_minutes=70),
                        CycleSessionTemplate(day_offset=3, focus='SSG corto + finalización', intensity='medium', duration_minutes=75),
                        CycleSessionTemplate(day_offset=5, focus='Partido amistoso', intensity='matchday', duration_minutes=90),
                    ],
                ),
            ],
        ),
        CycleTemplate(
            key='kids_4w',
            label='Fútbol base (4 semanas) · 2 sesiones + partido',
            weeks=4,
            description='Plan simple para categorías pequeñas: técnica + juego + diversión.',
            week_templates=[
                CycleWeekTemplate(
                    title='Semana 1',
                    objective='Conducción + regate + orientación.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='Técnica: conducción y regate', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=3, focus='Juegos reducidos (SSG)', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=5, focus='Partido', intensity='matchday', duration_minutes=70),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Pase + recepción + finalización.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='Técnica: pase y recepción', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=3, focus='SSG + finalización', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=5, focus='Partido', intensity='matchday', duration_minutes=70),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Duelos + recuperación tras pérdida.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='Duelos 1v1 / 2v2', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=3, focus='SSG: robar y atacar rápido', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=5, focus='Partido', intensity='matchday', duration_minutes=70),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Repaso y mini-torneo.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='Repaso técnica + juegos', intensity='low', duration_minutes=65),
                        CycleSessionTemplate(day_offset=3, focus='Mini-torneo interno (SSG)', intensity='medium', duration_minutes=70),
                        CycleSessionTemplate(day_offset=5, focus='Partido', intensity='matchday', duration_minutes=70),
                    ],
                ),
            ],
        ),
    ]

