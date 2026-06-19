from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CycleSessionTemplate:
    day_offset: int
    focus: str
    intensity: str = 'medium'
    duration_minutes: int = 90
    md_day: str = ''
    dominant_load: str = ''
    game_moment: str = ''
    principle: str = ''
    subprinciple: str = ''


@dataclass(frozen=True)
class CycleWeekTemplate:
    title: str
    objective: str = ''
    sessions: List[CycleSessionTemplate] = ()
    cycle_type: str = ''
    game_model_focus: str = ''
    game_moment: str = ''
    principle: str = ''
    subprinciple: str = ''


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
                    cycle_type='standard',
                    game_model_focus='Salida de balón y reacción inmediata tras pérdida.',
                    game_moment='offensive_organization',
                    principle='Salida de balón',
                    subprinciple='Generar hombre libre y preparar vigilancia tras pérdida.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Técnica + salida de balón', intensity='medium', duration_minutes=90, md_day='md_minus_4', dominant_load='tension', game_moment='offensive_organization', principle='Salida de balón', subprinciple='Crear línea de pase interior y hombre libre.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Presión + transiciones (SSG)', intensity='high', duration_minutes=90, md_day='md_minus_3', dominant_load='duration', game_moment='defensive_transition', principle='Presión tras pérdida', subprinciple='Acoso inmediato y cierre de pase interior.'),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75, md_day='md_minus_2', dominant_load='speed', game_moment='set_pieces', principle='ABP y activación', subprinciple='Roles claros y velocidad de ejecución.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Aplicar plan de partido.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Finalización + centros + vigilancia.',
                    cycle_type='standard',
                    game_model_focus='Atacar último tercio manteniendo vigilancias para controlar la pérdida.',
                    game_moment='offensive_organization',
                    principle='Finalización',
                    subprinciple='Llegadas coordinadas y vigilancia preventiva.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Finalización + centros', intensity='medium', duration_minutes=90, md_day='md_minus_4', dominant_load='tension', game_moment='offensive_organization', principle='Finalización', subprinciple='Ocupación de remate y pase atrás.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Ataque organizado (SSG)', intensity='high', duration_minutes=90, md_day='md_minus_3', dominant_load='duration', game_moment='offensive_organization', principle='Ataque organizado', subprinciple='Fijar, progresar y proteger la pérdida.'),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75, md_day='md_minus_2', dominant_load='speed', game_moment='set_pieces', principle='ABP ofensiva', subprinciple='Bloqueos, rechace y segunda jugada.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Aplicar plan de partido.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Defensa del área + repliegue + contras.',
                    cycle_type='standard',
                    game_model_focus='Proteger área, replegar con orden y salir con ventaja.',
                    game_moment='defensive_organization',
                    principle='Defensa del área',
                    subprinciple='Compactar, orientar y atacar transición.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Defensa del área', intensity='medium', duration_minutes=90, md_day='md_minus_4', dominant_load='tension', game_moment='defensive_organization', principle='Defensa del área', subprinciple='Cerrar zona de remate y proteger rechace.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Transición defensa-ataque', intensity='high', duration_minutes=90, md_day='md_minus_3', dominant_load='duration', game_moment='offensive_transition', principle='Contraataque', subprinciple='Primer pase de seguridad o ventaja.'),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · ABP + activación', intensity='low', duration_minutes=75, md_day='md_minus_2', dominant_load='speed', game_moment='set_pieces', principle='ABP defensiva', subprinciple='Marca, zona y segunda jugada.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90, md_day='md', dominant_load='mixed', game_moment='defensive_organization', principle='Competición', subprinciple='Aplicar plan de partido.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Repaso modelo + ajustes rival.',
                    cycle_type='taper',
                    game_model_focus='Afinar el modelo semanal y ajustar patrones del rival.',
                    game_moment='offensive_organization',
                    principle='Plan de partido',
                    subprinciple='Priorizar reglas simples y transferencia competitiva.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Repaso modelo (técnico-táctico)', intensity='medium', duration_minutes=90, md_day='md_minus_4', dominant_load='tension', game_moment='offensive_organization', principle='Modelo de juego', subprinciple='Reforzar comportamientos prioritarios.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Rival (patrones + ABP)', intensity='high', duration_minutes=90, md_day='md_minus_3', dominant_load='duration', game_moment='defensive_organization', principle='Ajuste rival', subprinciple='Reconocer patrones y responder con el plan.'),
                        CycleSessionTemplate(day_offset=4, focus='MD-2 · Activación + estrategia', intensity='low', duration_minutes=75, md_day='md_minus_2', dominant_load='speed', game_moment='set_pieces', principle='Estrategia', subprinciple='Activar automatismos y ABP.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=90, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Aplicar plan de partido.'),
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
                    cycle_type='preseason',
                    game_model_focus='Construir hábitos técnicos y orientación corporal para el modelo.',
                    game_moment='offensive_organization',
                    principle='Orientación corporal',
                    subprinciple='Recibir perfilado para jugar hacia ventaja.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Base física + técnica', intensity='medium', duration_minutes=90, md_day='custom', dominant_load='duration', game_moment='offensive_organization', principle='Orientación corporal', subprinciple='Perfil previo y primer control útil.'),
                        CycleSessionTemplate(day_offset=2, focus='Técnica + duelos', intensity='medium', duration_minutes=90, md_day='custom', dominant_load='tension', game_moment='defensive_organization', principle='Duelos', subprinciple='Temporizar, orientar y competir el contacto.'),
                        CycleSessionTemplate(day_offset=3, focus='SSG + transiciones', intensity='high', duration_minutes=90, md_day='custom', dominant_load='duration', game_moment='defensive_transition', principle='Transiciones', subprinciple='Reacción inmediata y orden tras pérdida.'),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Modelo base', subprinciple='Transferir reglas simples al juego.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Velocidad + cambios de dirección + ataque rápido.',
                    cycle_type='preseason',
                    game_model_focus='Acelerar acciones con control de estructura y vigilancia.',
                    game_moment='offensive_transition',
                    principle='Ataque rápido',
                    subprinciple='Acelerar cuando hay ventaja sin romper el equipo.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Velocidad + técnica', intensity='high', duration_minutes=85, md_day='custom', dominant_load='speed', game_moment='offensive_transition', principle='Velocidad de juego', subprinciple='Percibir ventaja y ejecutar rápido.'),
                        CycleSessionTemplate(day_offset=2, focus='SSG + finalización', intensity='high', duration_minutes=90, md_day='custom', dominant_load='tension', game_moment='offensive_organization', principle='Finalización', subprinciple='Llegar con ventaja y ocupar remate.'),
                        CycleSessionTemplate(day_offset=3, focus='Modelo básico (salida + presión)', intensity='medium', duration_minutes=90, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Salida y presión', subprinciple='Conectar inicio con reacción tras pérdida.'),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Modelo base', subprinciple='Transferir reglas simples al juego.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Resistencia específica (SSG) + ABP.',
                    cycle_type='preseason',
                    game_model_focus='Sostener esfuerzos específicos y ordenar ABP.',
                    game_moment='defensive_transition',
                    principle='Resistencia específica',
                    subprinciple='Repetir esfuerzos sin perder organización.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='SSG resistencia específica', intensity='high', duration_minutes=90, md_day='custom', dominant_load='duration', game_moment='defensive_transition', principle='Repetición específica', subprinciple='Mantener presión y distancias bajo fatiga.'),
                        CycleSessionTemplate(day_offset=2, focus='ABP ofensiva/defensiva', intensity='medium', duration_minutes=80, md_day='custom', dominant_load='activation', game_moment='set_pieces', principle='ABP', subprinciple='Roles, bloqueos y segunda jugada.'),
                        CycleSessionTemplate(day_offset=3, focus='Táctica: transiciones', intensity='medium', duration_minutes=90, md_day='custom', dominant_load='mixed', game_moment='offensive_transition', principle='Transición defensa-ataque', subprinciple='Primer pase y ocupación de profundidad.'),
                        CycleSessionTemplate(day_offset=5, focus='Partidillo controlado', intensity='matchday', duration_minutes=75, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Modelo base', subprinciple='Transferir reglas simples al juego.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Afinar modelo + carga descendente.',
                    cycle_type='taper',
                    game_model_focus='Reducir carga y fijar comportamientos prioritarios.',
                    game_moment='offensive_organization',
                    principle='Afinar modelo',
                    subprinciple='Claridad, frescura y transferencia al partido.',
                    sessions=[
                        CycleSessionTemplate(day_offset=0, focus='Modelo: salida + presión', intensity='medium', duration_minutes=85, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Salida y presión', subprinciple='Automatismos básicos con baja complejidad.'),
                        CycleSessionTemplate(day_offset=2, focus='Activación + ABP', intensity='low', duration_minutes=70, md_day='custom', dominant_load='activation', game_moment='set_pieces', principle='Activación', subprinciple='Velocidad corta y roles de ABP.'),
                        CycleSessionTemplate(day_offset=3, focus='SSG corto + finalización', intensity='medium', duration_minutes=75, md_day='custom', dominant_load='speed', game_moment='offensive_organization', principle='Finalización', subprinciple='Pocas acciones, mucha calidad.'),
                        CycleSessionTemplate(day_offset=5, focus='Partido amistoso', intensity='matchday', duration_minutes=90, md_day='custom', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Evaluar transferencia del modelo.'),
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
                    cycle_type='standard',
                    game_model_focus='Dominar balón, orientación y toma de decisión simple.',
                    game_moment='offensive_organization',
                    principle='Conducción y regate',
                    subprinciple='Levantar cabeza y atacar espacio libre.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Técnica: conducción y regate', intensity='medium', duration_minutes=70, md_day='md_minus_4', dominant_load='tension', game_moment='offensive_organization', principle='Conducción', subprinciple='Atacar espacio libre con balón controlado.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Juegos reducidos (SSG)', intensity='medium', duration_minutes=70, md_day='md_minus_3', dominant_load='duration', game_moment='offensive_organization', principle='Juego reducido', subprinciple='Decidir conducir, pasar o finalizar.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=70, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Disfrutar compitiendo con reglas simples.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 2',
                    objective='Pase + recepción + finalización.',
                    cycle_type='standard',
                    game_model_focus='Mejorar pase, recepción y finalización en situaciones simples.',
                    game_moment='offensive_organization',
                    principle='Pase y recepción',
                    subprinciple='Orientarse antes de recibir y jugar hacia ventaja.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Técnica: pase y recepción', intensity='medium', duration_minutes=70, md_day='md_minus_4', dominant_load='tension', game_moment='offensive_organization', principle='Pase y recepción', subprinciple='Perfil corporal y primer control.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · SSG + finalización', intensity='medium', duration_minutes=70, md_day='md_minus_3', dominant_load='duration', game_moment='offensive_organization', principle='Finalización', subprinciple='Elegir momento de tiro o pase.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=70, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Aplicar fundamentos en juego real.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 3',
                    objective='Duelos + recuperación tras pérdida.',
                    cycle_type='standard',
                    game_model_focus='Competir duelos y reaccionar tras pérdida.',
                    game_moment='defensive_transition',
                    principle='Recuperación tras pérdida',
                    subprinciple='Presionar cercano y proteger portería.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Duelos 1v1 / 2v2', intensity='medium', duration_minutes=70, md_day='md_minus_4', dominant_load='tension', game_moment='defensive_organization', principle='Duelos', subprinciple='Orientar y proteger balón/portería.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · SSG: robar y atacar rápido', intensity='medium', duration_minutes=70, md_day='md_minus_3', dominant_load='duration', game_moment='defensive_transition', principle='Recuperación tras pérdida', subprinciple='Robar y salir rápido con ventaja.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=70, md_day='md', dominant_load='mixed', game_moment='defensive_transition', principle='Competición', subprinciple='Reaccionar tras pérdida en juego real.'),
                    ],
                ),
                CycleWeekTemplate(
                    title='Semana 4',
                    objective='Repaso y mini-torneo.',
                    cycle_type='taper',
                    game_model_focus='Repasar fundamentos y competir con carga controlada.',
                    game_moment='offensive_organization',
                    principle='Repaso integrado',
                    subprinciple='Decidir jugando y disfrutar compitiendo.',
                    sessions=[
                        CycleSessionTemplate(day_offset=1, focus='MD-4 · Repaso técnica + juegos', intensity='low', duration_minutes=65, md_day='md_minus_4', dominant_load='activation', game_moment='offensive_organization', principle='Repaso técnico', subprinciple='Pase, conducción y finalización con baja carga.'),
                        CycleSessionTemplate(day_offset=3, focus='MD-3 · Mini-torneo interno (SSG)', intensity='medium', duration_minutes=70, md_day='md_minus_3', dominant_load='duration', game_moment='offensive_organization', principle='Competición formativa', subprinciple='Aplicar reglas simples en juego reducido.'),
                        CycleSessionTemplate(day_offset=5, focus='MD · Partido', intensity='matchday', duration_minutes=70, md_day='md', dominant_load='mixed', game_moment='offensive_organization', principle='Competición', subprinciple='Aplicar fundamentos en juego real.'),
                    ],
                ),
            ],
        ),
    ]
