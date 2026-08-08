TASK_SURFACE_CHOICES = [
    ('natural_grass', 'Hierba natural'),
    ('hybrid_grass', 'Hierba híbrida'),
    ('artificial_turf', 'Césped artificial'),
    ('futsal', 'Pista futsal'),
    ('sand', 'Arena'),
    ('indoor', 'Indoor'),
    ('gym', 'Gimnasio'),
    ('dirt', 'Tierra'),
    ('street', 'Asfalto'),
]
TASK_PITCH_FORMAT_CHOICES = [
    ('11v11_full', '11v11 · Campo completo'),
    ('11v11_half', '11v11 · Medio campo'),
    ('9v9', '9v9'),
    ('8v8', '8v8'),
    ('7v7', '7v7'),
    ('5v5', '5v5'),
    # El club es mayoria de futbol base: el 4v4 y el 3v3 son el formato REAL del prebenjamin,
    # y hasta ahora habia que meterlos en 5v5.
    ('4v4', '4v4'),
    ('3v3', '3v3'),
    ('quarter', 'Cuarto de campo'),
    ('corridor', 'Carril / pasillo'),
    ('abp', 'ABP'),
    ('specific_zone', 'Zona específica'),
]
TASK_METHODOLOGY_CHOICES = [
    ('analytical', 'Analítica'),
    ('integrated', 'Integrada'),
    ('global', 'Global'),
    ('competition', 'Competitiva'),
    ('coadjuvant', 'Coadyuvante'),
]
TASK_COMPLEXITY_CHOICES = [
    ('low', 'Baja'),
    ('medium', 'Media'),
    ('high', 'Alta'),
]
TASK_STRATEGY_CHOICES = [
    ('abp', 'Acciones a Balón Parado'),
    ('combined', 'Acciones Combinadas'),
    # Cuatro que ya escribia a mano en el titulo de sus tareas porque no estaban en la lista.
    ('activation', 'Activación / calentamiento'),
    ('circuit', 'Circuito'),
    ('conservation', 'Conservación'),
    ('gk_specific', 'Específico de portero'),
    ('adapted', 'Juego Adaptado al Fútbol'),
    ('positional', 'Juego de Posición'),
    ('positional_specific', 'Juego de Posición Específico'),
    ('waves', 'Oleadas'),
    ('matches', 'Partidos'),
    ('possession', 'Posesión'),
    ('preventive', 'Preventivo / readaptación'),
    ('rondo', 'Rondo'),
    ('passing_wheel', 'Rueda de Pases'),
    ('reduced_games', 'Situaciones Reducidas'),
    ('lines_work', 'Trabajo de Líneas'),
]
TASK_COORDINATION_SKILLS_CHOICES = [
    ('offball', 'Actuación por Desmarcación'),
    ('start_stop', 'Arrancar/Frenar'),
    ('heading', 'Cabeceo'),
    ('direction_change', 'Cambiar de Dirección'),
    ('cross', 'Centro'),
    ('carry', 'Conducción'),
    ('control', 'Control'),
    ('clearances', 'Despejes'),
    ('movements', 'Desplazamientos'),
    ('shots', 'Disparos'),
    ('tackles', 'Entrada'),
    ('balance', 'Equilibrarse'),
    ('feint', 'Finta'),
    ('turns', 'Giros'),
    ('interceptions', 'Intercepción'),
    ('pass', 'Pase'),
    ('protection', 'Protección'),
    ('dribble', 'Regate'),
    ('jumps', 'Saltos'),
    # Portero: el club tiene catalogo propio de valoracion de porteros y aqui no habia forma
    # de decir que entrena una tarea suya.
    ('gk_save', 'Portero · Parada'),
    ('gk_catch', 'Portero · Blocaje'),
    ('gk_exit', 'Portero · Salida'),
    ('gk_punch', 'Portero · Despeje de puños'),
    ('gk_distribution', 'Portero · Saque y distribución'),
]
TASK_TACTICAL_INTENT_CHOICES = [
    ('1v1', '1 vs 1'),
    ('2v1', '2 vs 1'),
    ('2v2', '2 vs 2'),
    ('3v2', '3 vs 2'),
    ('3v3', '3 vs 3'),
    ('4v3', '4 vs 3'),
    ('4v4', '4 vs 4'),
    ('5v5', '5 vs 5'),
    ('abp_def', 'ABP Defensiva'),
    ('abp_att', 'ABP Ofensiva'),
    ('compact', 'Achique de espacios'),
    ('width', 'Amplitud'),
    ('supports', 'Apoyos'),
    ('organized_attack', 'Ataque Organizado'),
    ('shift', 'Basculación'),
    ('cover', 'Cobertura'),
    ('keep', 'Conservar'),
    ('counter', 'Contraataque'),
    ('def_build', 'Defensa Inicio de Juego'),
    ('def_direct', 'Defensa de Juego Directo'),
    ('def_organized', 'Defensa Organizada'),
    ('runs', 'Desmarques'),
    ('split', 'Dividir'),
    ('avoid_progress', 'Evitar Progresión'),
    ('phase_def', 'Fase Defensiva'),
    ('phase_att', 'Fase Ofensiva'),
    ('fix', 'Fijar'),
    ('finish', 'Finalizar'),
    ('build', 'Inicio de Juego'),
    ('direct', 'Juego Directo'),
    ('maintain', 'Mantener'),
    ('marking', 'Marcaje'),
    ('orient', 'Orientar'),
    ('swap', 'Permuta'),
    ('press', 'Presionar'),
    ('first_attacker', 'Primer Atacante'),
    ('first_defender', 'Primer Defensor'),
    ('depth', 'Profundidad'),
    ('progress', 'Progresar'),
    ('protect_goal', 'Proteger Portería'),
    ('recover', 'Recuperar'),
    ('restart', 'Reinicio de Juego'),
    ('retreat', 'Replegar'),
    ('press_escape', 'Salida de presión'),
    ('second_attacker', 'Segundo Atacante'),
    ('second_defender', 'Segundo Defensor'),
    ('delay', 'Temporizar'),
    ('third_attacker', 'Tercer Atacante'),
    ('third_defender', 'Tercer Defensor'),
    ('cover_watch', 'Vigilancias defensivas'),
]
TASK_DYNAMICS_CHOICES = [
    ('adm', 'ADM'),
    ('extensive', 'Extensiva'),
    ('strength', 'Fuerza'),
    ('intense_action', 'Intensiva (acción)'),
    ('intense_interaction', 'Intensiva (interacción)'),
    ('recovery', 'Recuperación'),
    ('endurance', 'Resistencia'),
    ('speed', 'Velocidad'),
    ('tension', 'Tensión'),
    ('duration', 'Duración'),
]
TASK_STRUCTURE_CHOICES = [
    ('individual', 'Individual'),
    ('group', 'Grupal'),
    ('complete', 'Estructura Completa'),
    ('intersectorial', 'Intersectorial'),
    ('sectorial', 'Sectorial'),
]
TASK_COORDINATION_CHOICES = [
    ('team', 'Coordinación Equipo'),
    ('player', 'Coordinación Jugador/a'),
    ('players', 'Coordinación Jugadores/as'),
]
TASK_USEFULNESS_CHOICES = [
    ('1', '1 · Baja'),
    ('2', '2'),
    ('3', '3 · Media'),
    ('4', '4'),
    ('5', '5 · Top'),
]
# Como salio la tarea DESPUES de entrenarla. Se rellena al cerrar la sesion, no al crearla:
# es lo unico que convierte una biblioteca de 700 tareas en una biblioteca con criterio.
TASK_EXECUTION_RATING_CHOICES = [
    ('ok', 'Salió bien'),
    ('adjust', 'Ajustar'),
    ('drop', 'No repetir'),
]
TASK_CONSTRAINT_CHOICES = [
    ('two_touches', '2 toques'),
    ('one_touch_zone', '1 toque zona final'),
    ('mandatory_switch', 'Cambio de orientación obligatorio'),
    ('finish_under_10', 'Finalizar < 10 segundos'),
    ('press_6_seconds', 'Presionar 6 segundos tras pérdida'),
    ('bonus_recovery_high', 'Bonus por recuperación alta'),
    ('max_3_passes_before_finish', 'Máx. 3 pases antes de finalizar'),
    ('free_touch', 'Toque libre'),
    ('min_passes', 'Mínimo de pases antes de finalizar'),
    ('jokers', 'Comodines'),
    ('keeper_support', 'Portero como apoyo'),
    ('forbidden_zone', 'Zona prohibida'),
    ('first_time_finish', 'Gol de primera'),
    ('man_marking', 'Marcaje individual'),
    ('double_goal_high_recovery', 'Gol doble tras recuperación alta'),
]


# ============================================================
# Fase 2 — Taxonomía canónica del modelo teórico + proyección a columnas.
# Fuente de verdad para las columnas queryables de SessionTask (biblioteca/filtros).
# ============================================================

# Momentos del juego (las 5 fases del modelo de juego).
# FAMILIA de la tarea: el "que tipo de tarea es" que faltaba. Siete grupos acordados con el
# club a partir de leer sus 179 tareas del PPT una a una; el detalle fino (rondo en octogono,
# rueda con estaciones numeradas...) va en el texto de la tarea, no aqui.
TASK_FAMILY_CHOICES = [
    ("rondo", "Rondo / posesión"),
    ("posicion", "Juego de posición"),
    ("circuito", "Circuito / rueda de pases"),
    ("finalizacion", "Finalización y ABP"),
    ("partido", "Partido condicionado"),
    ("transicion", "Transición"),
    ("estructural", "Tarea estructural"),
]

GAME_MOMENT_CHOICES = [
    ("offensive_organization", "Organización ofensiva"),
    ("defensive_transition", "Transición ataque-defensa"),
    ("defensive_organization", "Organización defensiva"),
    ("offensive_transition", "Transición defensa-ataque"),
    ("set_pieces", "ABP"),
]

# Contenido dominante de la tarea (dominio principal que se entrena).
TASK_CONTENT_CHOICES = [
    ("tactical", "Táctico"),
    ("technical", "Técnico"),
    ("physical", "Físico-condicional"),
    ("psychological", "Psicológico-cognitivo"),
]

# Estructura (periodización táctica): la dimensión del jugador que la tarea moviliza.
TASK_PERIODIZATION_CHOICES = [
    ("conditional", "Condicional"),
    ("coordinative", "Coordinativa"),
    ("cognitive", "Cognitiva"),
    ("socio_affective", "Socio-afectiva"),
    ("emotional_volitional", "Emotivo-volitiva"),
    ("creative_expressive", "Creativo-expresiva"),
]


def _task_col_str(value, limit):
    try:
        s = str(value).strip() if value is not None else ""
    except Exception:
        s = ""
    return s[:limit]


def derive_task_columns(tactical_layout):
    """Proyecta los campos de metodología de tactical_layout['meta'] a un dict de columnas
    queryables de SessionTask. Fuente única usada por SessionTask.save() y por la migración
    de backfill, para que columnas y JSON estén siempre sincronizados."""
    meta = {}
    try:
        if isinstance(tactical_layout, dict):
            m = tactical_layout.get("meta")
            if isinstance(m, dict):
                meta = m
    except Exception:
        meta = {}
    return {
        "game_moment": _task_col_str(meta.get("game_moment"), 40),
        "task_family": _task_col_str(meta.get("task_family"), 30),
        "principle": _task_col_str(meta.get("principle"), 160),
        "subprinciple": _task_col_str(meta.get("subprinciple"), 200),
        "structure_periodization": _task_col_str(meta.get("dominant_structure"), 40),
        "game_situation": _task_col_str(meta.get("structure"), 40),
        "content_domain": _task_col_str(meta.get("content_domain"), 30),
        "age_group": _task_col_str(meta.get("age_group"), 80),
    }


# "Fase del juego" era un vocabulario PARALELO al de "Momento del juego", con otras claves para
# lo mismo (`organization_attack` frente a `offensive_organization`). Dos vocabularios acaban
# partiendo la biblioteca en dos, asi que se queda uno solo. El nombre sobrevive para el codigo
# que lo importa, pero apunta al canonico.
TASK_GAME_PHASE_CHOICES = GAME_MOMENT_CHOICES
