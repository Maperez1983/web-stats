from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.utils import OperationalError

from football.event_taxonomy import normalize_label
from football.models import (
    AcademyAssignment,
    AcademyLesson,
    AcademyLessonStep,
    AcademyQuizOption,
    AcademyQuizQuestion,
    Team,
    TaskBlueprint,
    Workspace,
)


@dataclass(frozen=True)
class SeedLesson:
    title: str
    summary: str
    min_category: str
    max_category: str
    tags: list[str]
    steps: list[dict]


def _mk_seed_pack() -> list[SeedLesson]:
    """
    Pack inicial (MVP) de una guía “top” reutilizable para todos los entrenadores.

    Nota copyright:
    - No copiamos texto de manuales UEFA/libros; se redacta de forma original y práctica.
    - Los manuales/documentos del club (AssistantKnowledgeDocument) quedan como biblioteca aparte.
    """
    return [
        SeedLesson(
            title="Metodología 2J · Cómo aprenden los niños",
            summary="Guía práctica para planificar, preguntar y corregir según la edad (Baby→Senior).",
            min_category=AcademyLesson.CATEGORY_BABY,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["metodologia", "didactica", "preguntas", "entorno"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Regla de oro (fútbol base)",
                    "body": (
                        "Objetivo: que el jugador *entienda* y *repita* la solución, no que “obedezca una vez”.\n\n"
                        "Estructura de sesión (simple):\n"
                        "1) Juego inicial (activar) · 2) Tarea principal (descubrir) · 3) Variante (retos) · 4) Partido condicionado (transferir).\n\n"
                        "Correcciones: 1 idea por parada · 10–20 segundos · vuelve al juego."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Coaching por edades (mini-guía)",
                    "body": (
                        "Baby/Prebenjamín: *explorar* (muchas repeticiones, pocas normas). Preguntas: “¿cómo lo hiciste?”.\n"
                        "Benjamín/Alevín: *decidir* (mirar antes, perfilarse). Preguntas: “¿qué opción era mejor y por qué?”.\n"
                        "Infantil/Cadete: *principios* (líneas, alturas, temporizar). Preguntas: “¿cuándo sí/cuándo no?”.\n"
                        "Juvenil/Senior: *modelo* (plan + lectura rival). Preguntas: “¿qué gatillo activó la acción?”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (metodología)",
                    "questions": [
                        {
                            "prompt": "En fútbol base, una corrección eficaz suele ser…",
                            "explanation": "Buscamos impacto rápido sin cortar el ritmo.",
                            "options": [
                                {"label": "Corta, concreta y vuelve al juego", "correct": True, "feedback": "Bien: 1 idea + volver a jugar."},
                                {"label": "Larga y con muchos detalles para que no haya dudas", "correct": False, "feedback": "Demasiado: baja intensidad y atención."},
                                {"label": "Solo dar órdenes sin preguntas", "correct": False, "feedback": "Mejor combinar guía y descubrimiento."},
                            ],
                        },
                        {
                            "prompt": "Para Baby/Prebenjamín, lo más importante es…",
                            "explanation": "A esas edades prima el disfrute + hábitos motores básicos.",
                            "options": [
                                {"label": "Muchos contactos y juegos sencillos", "correct": True, "feedback": "Correcto: repetición sin estrés."},
                                {"label": "Táctica avanzada y automatismos", "correct": False, "feedback": "Aún no: les falta base y atención sostenida."},
                                {"label": "Vídeo y pizarra largos", "correct": False, "feedback": "Mejor visual corto y jugar."},
                            ],
                        },
                    ],
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo (hoy)",
                    "body": (
                        "Elige una tarea que ya uses y cambia *solo una cosa*:\n"
                        "- Reduce reglas y formula 2 preguntas (no órdenes).\n"
                        "- Mide si hay más repeticiones útiles (más decisiones por minuto)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Biblioteca (UEFA/lecturas)",
                    "body": (
                        "Si tu club tiene documentos (manuales, libro, apuntes) en la app:\n"
                        "- Lee 1 página/idea.\n"
                        "- Convierte esa idea en 1 *regla de tarea* y 1 *pregunta* para el jugador.\n\n"
                        "Objetivo: pasar de teoría a campo en menos de 5 minutos."
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Play–Practice–Play · Sesión realista (game-based)",
            summary="Estructura simple para enseñar jugando: jugar → entrenar → volver a jugar (sin matar el ritmo).",
            min_category=AcademyLesson.CATEGORY_BABY,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["metodologia", "sesion", "gamebased", "transferencia"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "La idea",
                    "body": (
                        "En fútbol base, lo que más “pega” es lo que se practica *en contexto*.\n\n"
                        "Modelo simple:\n"
                        "1) PLAY: juego libre/condicionado (detecta el problema)\n"
                        "2) PRACTICE: tarea con 1–2 constraints (provoca la solución)\n"
                        "3) PLAY: vuelves a juego para ver *transferencia* (¿aparece sin recordarlo?).\n\n"
                        "Regla: si la tarea no se parece al partido, la transferencia se desploma."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Tiempos por categoría (orientativo)",
                    "body": (
                        "Baby/Preben: PLAY casi todo (mini-juegos), PRACTICE muy corto.\n"
                        "Benja/Alevín: PLAY 2 bloques + PRACTICE con reto claro.\n"
                        "Infantil+: PLAY con condiciones tácticas + PRACTICE más específica.\n\n"
                        "Señal de alarma: paradas largas y colas → baja la calidad de decisión."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo (hoy)",
                    "body": (
                        "Elige un tema (p.ej. “salir de presión”) y diseña:\n"
                        "- PLAY: 4v4/5v5 con regla de salida (2 pases en zona propia).\n"
                        "- PRACTICE: añade 1 comodín interior (superioridad) y puntúa giro.\n"
                        "- PLAY: quita el comodín y comprueba si aparece el giro/tercer hombre."
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Jugador completo · Las 4 esquinas (técnica, táctica, física, socio-emocional)",
            summary="Cómo planificar para desarrollar al jugador sin obsesionarse con una sola cosa.",
            min_category=AcademyLesson.CATEGORY_PREBENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["metodologia", "desarrollo", "holistico", "4_esquinas"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Qué es (en 30 segundos)",
                    "body": (
                        "Un jugador no “mejora” solo por tocar balón: también influye su confianza, su comprensión del juego, "
                        "su forma física *adecuada a la edad* y su entorno.\n\n"
                        "Usa 4 lentes para analizar un problema:\n"
                        "- Técnica: ¿puede ejecutar?\n"
                        "- Táctica: ¿entiende cuándo/por qué?\n"
                        "- Física: ¿llega a tiempo / se mueve bien?\n"
                        "- Socio-emocional: ¿se atreve / coopera / gestiona error?\n\n"
                        "Regla: si fallan 2 lentes a la vez, la corrección solo técnica no funciona."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Plantilla rápida (IDP semanal)",
                    "body": (
                        "Para cada jugador, elige SOLO 1 foco por semana:\n"
                        "- 1 comportamiento observable (p.ej. “mira antes de recibir”).\n"
                        "- 1 constraint que lo provoque (punto extra / regla simple).\n"
                        "- 1 frase de feedback (máx. 8 palabras).\n\n"
                        "En cantera: la consistencia gana a la sofisticación."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (4 esquinas)",
                    "questions": [
                        {
                            "prompt": "Si un jugador “no pasa” cuando debe, ¿qué es lo primero que miras?",
                            "explanation": "La decisión suele tener varias causas; buscamos el cuello de botella.",
                            "options": [
                                {"label": "Si ha visto opciones (escaneo) y está orientado", "correct": True, "feedback": "Bien: percepción + orientación antes que ejecución."},
                                {"label": "Si su pase es técnicamente perfecto", "correct": False, "feedback": "Importa, pero sin información previa no decide."},
                                {"label": "Si corre mucho", "correct": False, "feedback": "La intensidad ayuda, pero no sustituye la lectura."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="Clima de aprendizaje · Seguridad, diversión y exigencia",
            summary="Cómo crear un entorno que mejora el rendimiento: normas, refuerzo, error y roles del entrenador.",
            min_category=AcademyLesson.CATEGORY_BABY,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["entorno", "motivacion", "valores", "comunicacion"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "3 reglas que no fallan",
                    "body": (
                        "1) El error es *información* (no juicio).\n"
                        "2) Elogia el comportamiento que quieres repetir (no solo el resultado).\n"
                        "3) Claridad: 1 norma por tarea y un porqué.\n\n"
                        "Indicador: si los jugadores dejan de intentar, has matado el aprendizaje."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo (hoy)",
                    "body": (
                        "Elige una conducta a reforzar (p.ej. “apoyo tras pase”) y usa este patrón:\n"
                        "- Señal: “¡apoyo!”\n"
                        "- Refuerzo inmediato: “¡bien, ya tienes 2 opciones!”\n"
                        "- Pregunta: “¿qué viste antes de pasar?”\n\n"
                        "Mide: ¿suben las repeticiones útiles sin parar el juego?"
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Seguridad del menor · Protección y límites (safeguarding)",
            summary="Checklist práctico para entrenar en un entorno seguro e inclusivo (sin burocracia).",
            min_category=AcademyLesson.CATEGORY_BABY,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["entorno", "seguridad", "safeguarding", "club"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Checklist (entreno y partido)",
                    "body": (
                        "- Normas claras (contacto físico, vestuarios, fotos/vídeo, redes sociales).\n"
                        "- Visibilidad: evita estar a solas con un menor (siempre que sea posible).\n"
                        "- Comunicación: mensajes por canales oficiales y tono profesional.\n"
                        "- Transporte: no improvisar; acordar por escrito con familias/club.\n"
                        "- Señales de alerta: cambios bruscos de conducta, miedo, aislamiento.\n\n"
                        "Objetivo: que los niños disfruten el fútbol en un entorno seguro y respetuoso."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto (club)",
                    "body": (
                        "Crea/actualiza 5 reglas del equipo (1 página) y compártelas con familias y jugadores.\n"
                        "Incluye: horarios, recogidas, uso de móvil, redes, y a quién avisar si pasa algo."
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Prevención de lesiones · Calentamiento neuromuscular (inspirado en FIFA 11+ Kids)",
            summary="Rutina corta y repetible (8–12') para reducir riesgo y mejorar calidad de movimiento.",
            min_category=AcademyLesson.CATEGORY_BENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["fisico", "prevencion", "calentamiento"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Estructura (8–12 minutos)",
                    "body": (
                        "1) Activación (2–3'): carrera suave + cambios de dirección.\n"
                        "2) Control motor (3–4'): equilibrio 1 pierna, core simple, fuerza básica.\n"
                        "3) Saltos/aterrizajes (2–3'): caer “suave” (rodillas alineadas), mini vallas imaginarias.\n"
                        "4) Aceleración (1–2'): 3–4 sprints cortos (con y sin balón).\n\n"
                        "Regla: mejor poco y constante que mucho y esporádico."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Claves para que funcione",
                    "body": (
                        "- Técnica > intensidad: primero bien hecho.\n"
                        "- Progresión: sube dificultad cada 2–3 semanas.\n"
                        "- Variación con balón: en cantera mejora adherencia.\n"
                        "- Señal del entrenador: “alineo rodilla”, “tronco estable”, “caigo suave”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto (hoy)",
                    "body": (
                        "Antes de tu sesión, mete 1 bloque de 10' con 3 ejercicios:\n"
                        "- equilibrio (1 pierna) + pase corto\n"
                        "- sentadilla parcial controlada (8 rep)\n"
                        "- 4 sprints de 10–15m con frenada\n\n"
                        "Mide: ¿llegan más “finos” al juego inicial?"
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Defensa · Marcaje en zona (principios y roles)",
            summary="Guía práctica para defender en zona: referencias, comunicación, y cómo evitar los errores típicos.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "zona", "marcaje", "principios"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Qué significa “defender en zona” (sin humo)",
                    "body": (
                        "Zona NO es “cada uno se queda quieto en su sitio”. Zona es:\n"
                        "- protejo un ESPACIO prioritario,\n"
                        "- con una REFERENCIA (balón/rival/portería),\n"
                        "- y ENTREGO/MODIFICO mi marca cuando el balón cambia (cadena).\n\n"
                        "Objetivo: proteger el centro y el remate limpio."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "3 reglas operativas (fáciles de repetir)",
                    "body": (
                        "1) Centro primero: tu cuerpo orienta a proteger interior.\n"
                        "2) Distancias: si el balón va a banda, el bloque BASCULA y se compacta.\n"
                        "3) Balón–hombre–portería: escaneo constante (no mirar solo al balón).\n\n"
                        "Palabras clave: “DENTRO”, “JUNTOS”, “A LA ESPALDA”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Roles (muy prácticos)",
                    "body": (
                        "- 1er defensor (salta): orienta y frena.\n"
                        "- 2º defensor (cobertura): distancia + ángulo para tapar pase interior.\n"
                        "- 3º defensor (equilibrio): protege espalda/cambio de orientación.\n\n"
                        "Sin 2º y 3º defensor, el 1º defensor NO puede “morder”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Errores típicos (y la corrección concreta)",
                    "body": (
                        "Error: todos saltan al balón → Corrección: “solo 1 salta, 2 cubren”.\n"
                        "Error: bloque partido (mucho espacio entre líneas) → “si no acompaña, temporiza”.\n"
                        "Error: miran balón y pierden al hombre en espalda → “balón-hombre-portería”.\n"
                        "Error: basculación lenta → “primer paso rápido, luego ajustar”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: basculación + cobertura",
                    "body": "Úsalo como escena tipo: balón en banda, 1º defensor orienta, 2º cubre dentro, 3º equilibra.",
                    "payload": {"hint": "Dibuja 3 líneas (defensa/medio/ataque) y muestra 2 basculaciones: a derecha y a izquierda."},
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (zona)",
                    "questions": [
                        {
                            "prompt": "En defensa en zona, ¿qué priorizas cuando el balón entra a banda?",
                            "explanation": "La trampa es correr “a lo loco”; buscamos proteger dentro y llegar juntos.",
                            "options": [
                                {"label": "Bascular y proteger el pase interior", "correct": True, "feedback": "Sí: llegar juntos y tapar dentro."},
                                {"label": "Perseguir marcas sin mirar el balón", "correct": False, "feedback": "Sin referencias se abren huecos."},
                                {"label": "Quedarse en la posición inicial", "correct": False, "feedback": "Zona requiere ajuste constante."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="Defensa · Presión orientada (guiar a banda)",
            summary="Cómo orientar una presión: triggers, ángulos de carrera y apoyos para robar sin romper el equipo.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "presion", "orientacion", "triggers"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Objetivo real de la presión",
                    "body": (
                        "Presionar no es correr. Es:\n"
                        "- forzar al rival a una ZONA “pobre” (banda/atrás),\n"
                        "- con la LÍNEA preparada (cobertura),\n"
                        "- para ROBO o ERROR.\n\n"
                        "Si no hay cobertura, presionar = regalar la espalda."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Triggers (cuándo saltar)",
                    "body": (
                        "- Control orientado malo / balón “se va” del pie.\n"
                        "- Pase lento o flotado.\n"
                        "- Receptor de espaldas.\n"
                        "- Línea de pase interior cerrada.\n\n"
                        "Regla: si llegas tarde → temporiza y espera trigger."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Ángulo del 1er defensor (la clave)",
                    "body": (
                        "Carrera curva, cuerpo de lado: tapas pase interior y “invitas” a banda.\n"
                        "Distancia: lo bastante cerca para molestar, lo bastante lejos para no ser superado.\n\n"
                        "Frase de coaching: “CIERRA DENTRO, LLEVA FUERA”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "2º y 3º defensor (sin esto no hay presión)",
                    "body": (
                        "2º defensor: achica y salta si el rival entra por dentro.\n"
                        "3º defensor: equilibra (cambio de orientación + espalda).\n\n"
                        "Regla de oro: el 1º defensor manda el camino, los demás cierran puertas."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: presión a banda",
                    "body": "Escena tipo: balón al lateral rival, salto del extremo, 2º defensor tapa dentro, lateral listo para interceptar.",
                    "payload": {"hint": "Representa el “triángulo” de presión: 1º orienta, 2º cubre, 3º equilibra."},
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (presión)",
                    "questions": [
                        {
                            "prompt": "Si el 1º defensor presiona pero su línea NO acompaña, ¿qué hace?",
                            "explanation": "La presión sin bloque es un 1v1 perdido.",
                            "options": [
                                {"label": "Temporiza y orienta sin lanzarse", "correct": True, "feedback": "Correcto: guiar y esperar apoyo."},
                                {"label": "Se tira igual para robar", "correct": False, "feedback": "Normalmente te superan y rompes equipo."},
                                {"label": "Se para y deja jugar", "correct": False, "feedback": "Puedes temporizar y orientar, no regalar."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="ABP · Córner en contra (zona + referencias)",
            summary="Guía práctica para defender córners en zona: asignación, bloqueos, segundas jugadas y salidas.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "defensa", "corner", "zona"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Principio: proteger zona de remate",
                    "body": (
                        "En córner en contra, lo más peligroso es el remate limpio (primer contacto).\n"
                        "La zona se organiza para:\n"
                        "- ganar primer contacto,\n"
                        "- controlar el rechace,\n"
                        "- y salir (2º balón).\n\n"
                        "Regla: 1 contacto gana el córner; el 2º contacto gana el partido."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Asignación mínima (modelo simple)",
                    "body": (
                        "- 1 en primer palo (zona)\n"
                        "- 1 en zona central (zona)\n"
                        "- 1 en zona segundo palo (zona)\n"
                        "- 2–3 marcas al hombre (mejores rematadores)\n"
                        "- 1/2 fuera para salida (y vigilar rechace)\n\n"
                        "Ajusta según edad y altura; lo importante es que TODOS sepan su rol."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Errores típicos",
                    "body": (
                        "Error: todos miran balón → pierden bloqueos y pantalla.\n"
                        "Error: nadie ataca el balón → remate fácil.\n"
                        "Error: despeje “al centro” → segunda jugada rival.\n\n"
                        "Correcciones: “ataca balón”, “cuerpo entre rival y zona”, “despeja a banda”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: córner en contra",
                    "body": "Dibuja zonas (1º, centro, 2º palo) y 2 marcas al hombre. Marca a quién sale al rechace.",
                    "payload": {"hint": "Incluye 2 variantes: cerrado y abierto. Señala quién ataca balón en cada una."},
                },
            ],
        ),
        SeedLesson(
            title="ABP · Saque de banda a favor (3 opciones y 1 regla)",
            summary="Guía práctica para sacar de banda con continuidad: opción corta, tercer hombre y opción larga sin regalar transición.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "banda", "ataque", "salida"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "La regla #1 (que lo cambia todo)",
                    "body": (
                        "Un saque de banda a favor no es “tirar por tirar”. Es una REINICIACIÓN de posesión.\n\n"
                        "Regla #1: antes de sacar, define SIEMPRE 1 pase seguro (evita contraataque).\n"
                        "Si no hay pase seguro: saca atrás o reinicia a zona de seguridad."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Estructura simple (3 opciones)",
                    "body": (
                        "Opción A (segura): saque al apoyo corto → devolución → cambio de orientación.\n"
                        "Opción B (progresar): saque al apoyo corto → 3er hombre por dentro.\n"
                        "Opción C (larga): bloqueo y ataque del espacio (si hay ventaja real).\n\n"
                        "Roles mínimos: sacador + apoyo corto + apoyo interior + cobertura (seguridad)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Checklist del sacador (rápido)",
                    "body": (
                        "1) ¿Tengo pase atrás/seguro?\n"
                        "2) ¿Puedo jugar a 3er hombre?\n"
                        "3) ¿Hay ventaja para larga (espacio y timing)?\n\n"
                        "Palabras: “SEGURA”, “TERCER”, “LARGA SI HAY VENTAJA”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Errores típicos",
                    "body": (
                        "Error: sacar al pie marcado → pérdida inmediata.\n"
                        "Error: todos vienen al balón → no hay salida.\n"
                        "Error: larga sin ventaja → balón dividido y transición en contra.\n\n"
                        "Corrección: “apoyo + tercer hombre”, y 1 jugador SIEMPRE de seguridad."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: saque a favor (A/B/C)",
                    "body": "Dibuja 3 variantes: (A) segura atrás, (B) tercer hombre interior, (C) ataque largo con bloqueo.",
                    "payload": {"hint": "Incluye 1 jugador fijo de seguridad y marca el 3er hombre por dentro."},
                },
            ],
        ),
        SeedLesson(
            title="ABP · Saque de banda en contra (trampa + segunda jugada)",
            summary="Cómo defender saques de banda: evitar el saque rápido, orientar a banda, y ganar la segunda jugada.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "defensa", "banda", "segunda_jugada"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Prioridad",
                    "body": (
                        "En saque de banda en contra, el peligro real suele ser:\n"
                        "- saque rápido (desorden),\n"
                        "- pared/tercer hombre en banda,\n"
                        "- y la segunda jugada tras balón dividido.\n\n"
                        "Objetivo: que el rival reciba de espaldas y sin giro."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Reglas simples",
                    "body": (
                        "1) Evita saque rápido: balón fuera → 1 jugador “molesta” la reposición sin provocar falta.\n"
                        "2) Cierra dentro: el receptor no puede girar hacia interior.\n"
                        "3) Segunda jugada: 1 jugador a rechace SIEMPRE.\n\n"
                        "Frases: “DENTRO CERRADO”, “DE ESPALDAS”, “RECHACE”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "La trampa (banda)",
                    "body": (
                        "Cuando el rival recibe pegado a banda:\n"
                        "- 1 presiona orientando fuera,\n"
                        "- 2º cierra pase interior,\n"
                        "- 3º protege espalda/cambio.\n\n"
                        "Si no hay 2º defensor, el 1º temporiza (no se lanza)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: trampa en banda",
                    "body": "Escena tipo: saque corto a banda, presión orientada fuera y cierre interior, con jugador de rechace.",
                    "payload": {"hint": "Marca el 2º defensor cerrando el interior y el jugador de segunda jugada."},
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (banda en contra)",
                    "questions": [
                        {
                            "prompt": "¿Qué es lo más importante tras un saque de banda en contra?",
                            "explanation": "Muchas jugadas se deciden por el rechace.",
                            "options": [
                                {"label": "Ganar la segunda jugada (rechace)", "correct": True, "feedback": "Correcto: asegura continuidad defensiva."},
                                {"label": "Correr todos al balón", "correct": False, "feedback": "Eso abre interior y espalda."},
                                {"label": "Quedarse esperando para no romperse", "correct": False, "feedback": "Hay que ajustar con roles."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="ABP · Falta lateral a favor (1 remate + 1 rechace)",
            summary="Guía práctica para faltas laterales: señales, carreras, zonas de remate y plan B si no hay ventaja.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "ataque", "falta_lateral", "centro"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Objetivo (simple)",
                    "body": (
                        "Falta lateral a favor: buscamos 1 remate limpio y 1 segunda jugada.\n\n"
                        "No hace falta “jugada de pizarra” complicada:\n"
                        "- hace falta coordinación (timing),\n"
                        "- y roles claros."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Roles mínimos",
                    "body": (
                        "- Lanzador (define tipo de centro: tenso / segundo palo / corto)\n"
                        "- 2 atacantes de área (primer palo + penalti/segundo)\n"
                        "- 1 bloqueo (legal) o pantalla para liberar\n"
                        "- 2 fuera para rechace y prevención de contra\n\n"
                        "Regla: siempre hay “seguridad” (siempre)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Señales y timing",
                    "body": (
                        "Timing gana: el que llega con carrera suele rematar mejor.\n"
                        "Señal simple: ‘mano arriba’ = centro al segundo; ‘mano abajo’ = primer palo.\n\n"
                        "Si el rival defiende muy alto: opción corta + centro desde mejor ángulo."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Errores típicos",
                    "body": (
                        "Error: todos atacan la misma zona → se estorban.\n"
                        "Error: nadie al rechace → segundo balón del rival.\n"
                        "Error: centro “flojo” → despeje fácil.\n\n"
                        "Corrección: 2 zonas distintas + 2 fuera + centro tenso."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: falta lateral a favor",
                    "body": "Dibuja primer palo, punto penalti/segundo palo, 1 bloqueo y 2 jugadores fuera (rechace + seguridad).",
                    "payload": {"hint": "Marca 2 rutas de remate y 1 ruta de bloqueo/pantalla; deja 2 fuera bien colocados."},
                },
            ],
        ),
        SeedLesson(
            title="ABP · Falta lateral en contra (línea + zonas + rechace)",
            summary="Cómo defender faltas laterales: línea, referencias, evitar segundo remate y salir tras despeje.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "defensa", "falta_lateral", "zona"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Prioridades",
                    "body": (
                        "En falta lateral en contra, el rival busca:\n"
                        "- primer contacto (remate),\n"
                        "- segunda jugada (rechace),\n"
                        "- y desajuste de la línea.\n\n"
                        "Objetivo: 1) atacar balón, 2) despejar a zona segura, 3) ganar rechace."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Estructura simple (híbrida)",
                    "body": (
                        "- 2–3 zonas (primer palo, centro, segundo)\n"
                        "- 2 marcas al hombre (mejores rematadores)\n"
                        "- 1 para rechace + 1 para salida\n\n"
                        "Regla: nadie se queda “en tierra de nadie” mirando el balón."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "La línea (cuándo sí y cuándo no)",
                    "body": (
                        "Si hay tiempo y el lanzador está lejos: línea coordinada (subir juntos).\n"
                        "Si el lanzador está cerca o hay riesgo de centro rápido: prioriza zonas y remate.\n\n"
                        "Clave: una línea sin coordinación = te matan la espalda."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: falta lateral en contra",
                    "body": "Dibuja zonas + 2 marcas al hombre + 1 jugador de rechace. Marca dirección de despeje (a banda).",
                    "payload": {"hint": "Incluye 2 variantes: centro rápido (zonas) vs centro lento (línea coordinada)."},
                },
            ],
        ),
        SeedLesson(
            title="Diseño de tareas · Caja de herramientas (constraints)",
            summary="Cómo modificar una tarea sin rehacerla: espacio, tiempo, normas, puntuación y superioridades.",
            min_category=AcademyLesson.CATEGORY_PREBENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["tareas", "constraints", "metodologia"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "5 palancas (las que más funcionan)",
                    "body": (
                        "1) Espacio (ancho/profundidad) · 2) Tiempo (toques/segundos) · 3) Normas (orientar)\n"
                        "4) Puntuación (doble si…) · 5) Superioridades (comodín dentro/fuera).\n\n"
                        "Regla: cambia 1 palanca cada vez y observa (no cambies 5 cosas)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (constraints)",
                    "questions": [
                        {
                            "prompt": "Si quieres mejorar “mirar antes de recibir”, ¿qué constraint ayuda más?",
                            "explanation": "Forzamos percepción sin sermón.",
                            "options": [
                                {"label": "Obligar a orientar el cuerpo antes de recibir (punto extra)", "correct": True, "feedback": "Bien: premia el hábito."},
                                {"label": "Pedirlo en una charla de 3 minutos", "correct": False, "feedback": "Mejor dentro del juego."},
                                {"label": "Reducir el campo al máximo siempre", "correct": False, "feedback": "A veces ayuda, pero puede generar caos si es demasiado."},
                            ],
                        }
                    ],
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo (hoy)",
                    "body": (
                        "En tu tarea principal, añade un *punto extra* si el receptor:\n"
                        "- recibe perfilado, o\n"
                        "- juega a un tercer hombre.\n"
                        "Mide: ¿aparecen más apoyos y menos pérdidas?"
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Principios ofensivos · Jugar hacia delante con apoyo",
            summary="Perfil corporal, tercer hombre y progresión: del 1v1 al juego en línea.",
            min_category=AcademyLesson.CATEGORY_BENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["ataque", "progresion", "apoyos", "perfil"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Checklist de progresión (3 preguntas)",
                    "body": (
                        "Antes de recibir: ¿dónde está el rival más cercano?\n"
                        "Al recibir: ¿puedo girar o necesito apoyo?\n"
                        "Después: ¿puedo jugar hacia delante o fijo y doy continuidad?\n\n"
                        "Clave: *si no puedes avanzar, mejora tu posición para poder hacerlo en la siguiente*."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: tercer hombre (MVP)",
                    "body": (
                        "Este paso está preparado para una recreación 2D/3D.\n"
                        "En el MVP lo usamos como recordatorio: crea el escenario en el editor táctico y guárdalo como simulación."
                    ),
                    "payload": {
                        "hint": "Crea 3 pasos: (1) pase al apoyo (2) devolución (3) pase al 3º hombre.",
                    },
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (ataque)",
                    "questions": [
                        {
                            "prompt": "Si el jugador que recibe está de espaldas y presionado, ¿qué priorizas?",
                            "explanation": "Seguridad y continuidad para volver a progresar.",
                            "options": [
                                {"label": "Asegurar con apoyo cercano y salida", "correct": True, "feedback": "Bien: 2º toque para “salir”. "},
                                {"label": "Girar siempre aunque pierda el balón", "correct": False, "feedback": "No siempre: depende de espacio/ventaja."},
                                {"label": "Balón largo sin mirar", "correct": False, "feedback": "Solo si es parte del plan y hay ventaja."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="Amplitud y profundidad · Abrir para entrar",
            summary="Cómo crear pasillos y llegar a zona de finalización sin precipitarse.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["ataque", "amplitud", "profundidad", "ocupacion"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Reglas simples",
                    "body": (
                        "Amplitud: “pegado a la línea cuando el balón está por dentro”.\n"
                        "Profundidad: “alguien amenaza espalda (sin estar siempre en fuera de juego)”.\n\n"
                        "Error típico: todos vienen al balón → no hay pase hacia delante."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo",
                    "body": "En un 5v5, solo puedes marcar si antes has jugado a banda al menos 1 vez.",
                },
            ],
        ),
        SeedLesson(
            title="Principios defensivos · Presionar con cobertura",
            summary="Cómo apretar sin romper equipo: roles de primer, segundo y tercer defensor.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "presion", "cobertura", "equipo"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Roles defensivos (simple)",
                    "body": (
                        "1er defensor: orienta (no “muerde” por morder).\n"
                        "2º defensor: cobertura (distancia + ángulo).\n"
                        "3er defensor: equilibrio (cierra pase interior y vigila espalda).\n\n"
                        "Error típico: presionar 1v1 sin que el 2º defensor llegue."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo (hoy)",
                    "body": (
                        "En un 4v4/5v5, puntúa doble si recuperas tras orientar hacia banda.\n"
                        "Pista: “cuerpo de lado” + “mi compañero cubre dentro”."
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Defensa colectiva · Compactar y bascular",
            summary="Distancias entre líneas y orientación del bloque: proteger dentro, guiar fuera.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "bloque", "compacto", "basculacion"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Distancias (regla práctica)",
                    "body": (
                        "Sin balón: distancia entre líneas *corta* para proteger el pase interior.\n"
                        "Con presión: el bloque acompaña (si no acompaña, el 1º defensor temporiza).\n\n"
                        "Pista: “juntos para defender, separados para atacar”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (bloque)",
                    "questions": [
                        {
                            "prompt": "Si el rival cambia de lado rápido, ¿qué prioriza el bloque?",
                            "explanation": "Llegar juntos y proteger dentro.",
                            "options": [
                                {"label": "Proteger el pasillo interior y llegar con ayudas", "correct": True, "feedback": "Sí: dentro primero."},
                                {"label": "Saltar todos al balón sin orden", "correct": False, "feedback": "Eso rompe líneas."},
                                {"label": "Quedarse quietos para no desordenarse", "correct": False, "feedback": "Hay que bascular con timing."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="Transición · 5 segundos",
            summary="Qué hacer al perder y al recuperar: reglas claras por categoría.",
            min_category=AcademyLesson.CATEGORY_PREBENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["transicion", "perdida", "recuperacion"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Reglas por edades",
                    "body": (
                        "Baby/Preben: “si la pierdes, corre hacia el balón”.\n"
                        "Benja/Alevín: “si la pierdes, aprieta 3 pasos y si no, vuelve”.\n"
                        "Infantil+: “si la pierdes, decide: presiono / temporizo / cierro pase interior”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_QUIZ,
                    "title": "Mini-quiz (transición)",
                    "questions": [
                        {
                            "prompt": "Tras pérdida, ¿cuándo NO presiono directo?",
                            "explanation": "Si presionas sin opciones, rompes equipo.",
                            "options": [
                                {"label": "Si estoy solo y mi línea no acompaña", "correct": True, "feedback": "Bien: temporiza y vuelve."},
                                {"label": "Siempre hay que ir al balón", "correct": False, "feedback": "Depende de apoyo/cobertura."},
                                {"label": "Si el rival está en su área", "correct": False, "feedback": "Puede haber presión alta útil."},
                            ],
                        }
                    ],
                },
            ],
        ),
        SeedLesson(
            title="Finalización · Atacar el área",
            summary="Llegadas, centros y remate: cómo crear hábitos de gol por edad.",
            min_category=AcademyLesson.CATEGORY_BENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["finalizacion", "area", "remate"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "3 reglas",
                    "body": (
                        "1) Al centro: alguien primer palo, alguien punto de penalti.\n"
                        "2) Si el balón va a banda: 2 llegadas (una al área y otra al rechazo).\n"
                        "3) Remate: atacar el balón (no esperar).\n\n"
                        "En pequeños: premio a rematar (aunque no haya gol)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo",
                    "body": "Gol vale doble si el remate es de primeras o tras desmarque a primer palo.",
                },
            ],
        ),
        SeedLesson(
            title="ABP (base) · Saque de esquina a favor",
            summary="Una estructura simple y repetible (y cómo adaptarla por categoría).",
            min_category=AcademyLesson.CATEGORY_BENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["abp", "corners"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Estructura (simple)",
                    "body": (
                        "Objetivo: generar 1 remate limpio + 1 segunda jugada.\n\n"
                        "Roles (mínimo):\n"
                        "- 1 al saque · 1 primer palo · 1 segundo palo · 1 rechazo · 1 seguridad.\n\n"
                        "En pequeños: prioriza la *organización rápida* y un centro tenso.\n"
                        "En mayores: añade bloqueos legales y segundas jugadas dirigidas."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: corner simple (MVP)",
                    "body": "Crea el escenario en ABP/Pizarra y guárdalo como simulación.",
                    "payload": {"hint": "Paso 1 posiciones · Paso 2 desmarques · Paso 3 remate + rechazo."},
                },
            ],
        ),
        SeedLesson(
            title="Ruta Baby/Prebenjamín · 4 hábitos",
            summary="Motor + balón + diversión: lo que más acelera el aprendizaje a edades tempranas.",
            min_category=AcademyLesson.CATEGORY_BABY,
            max_category=AcademyLesson.CATEGORY_PREBENJAMIN,
            tags=["ruta", "baby", "prebenjamin"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Los 4 hábitos",
                    "body": (
                        "1) Conducir con ambas piernas.\n"
                        "2) Cambiar de dirección.\n"
                        "3) Proteger balón (cuerpo entre rival y balón).\n"
                        "4) Levantar la cabeza 1 vez antes de decidir.\n\n"
                        "Plan: 10–15 minutos de juegos cortos + partido condicionado."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TASK,
                    "title": "Reto de campo",
                    "body": "Juego 1v1/2v2: 1 punto si haces un cambio de dirección antes de marcar.",
                },
            ],
        ),
    ]


def _mk_category_curriculum() -> list[SeedLesson]:
    """
    Currículo completo por categoría (Baby→Senior).

    Nota:
    - Contenido original (no copiado de manuales). Se apoya en enfoques ampliamente aceptados:
      Play-Practice-Play, game-based learning y constraints-led practice design.
    """

    C = AcademyLesson
    base = [
        # Core transversal (sirve a todos).
        SeedLesson(
            title="Principios de diseño · Play–Practice–Play (PPP)",
            summary="Estructura simple de sesión: jugar → entrenar jugando → volver a jugar.",
            min_category=C.CATEGORY_BABY,
            max_category=C.CATEGORY_SENIOR,
            tags=["metodologia", "ppp", "sesion"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "PPP en 1 minuto",
                    "body": (
                        "PPP = 1) *Play* (juego real, observar) → 2) *Practice* (misma idea, con una condición) → "
                        "3) *Play* (volver al juego, comprobar si aparece lo aprendido).\n\n"
                        "Ventaja: el niño aprende *en contexto* y el entrenador corrige con menos paradas."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Preguntas que aceleran el aprendizaje",
                    "body": (
                        "En vez de “haz X”, prueba:\n"
                        "- ¿Qué viste antes de recibir?\n"
                        "- ¿Qué opción era la más segura/rápida?\n"
                        "- ¿Cuándo sí y cuándo no?\n\n"
                        "Regla: 1 pregunta + 1 repeticiones → no charla."
                    ),
                },
            ],
        ),
        SeedLesson(
            title="Caja de herramientas · Constraints (5 palancas)",
            summary="Cómo cambiar una tarea sin rehacerla: espacio, tiempo, reglas, puntuación y superioridades.",
            min_category=C.CATEGORY_PREBENJAMIN,
            max_category=C.CATEGORY_SENIOR,
            tags=["constraints", "tareas", "metodologia"],
            steps=[
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Las 5 palancas", "body": (
                    "1) Espacio (ancho/profundidad) · 2) Tiempo (toques/segundos) · 3) Reglas (orientar)\n"
                    "4) Puntuación (doble si…) · 5) Superioridades (comodín dentro/fuera).\n\n"
                    "Cambia 1 palanca cada vez y observa el comportamiento."
                )},
                {"type": AcademyLessonStep.TYPE_TASK, "title": "Reto rápido", "body": (
                    "En tu tarea principal, añade un punto extra por *perfil corporal* o *3º hombre*.\n"
                    "Comprueba si aumenta la calidad de decisión."
                )},
            ],
        ),
    ]

    def route_overview(cat_key: str, cat_label: str, *, focus: str, session_minutes: str, cues: str, must_have: list[str], avoid: list[str]) -> SeedLesson:
        return SeedLesson(
            title=f"Ruta {cat_label} · Prioridades",
            summary=f"Qué priorizar en {cat_label}: {focus}",
            min_category=cat_key,
            max_category=cat_key,
            tags=["ruta", cat_key],
            steps=[
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Objetivo de la categoría", "body": focus},
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Sesión tipo", "body": (
                    f"Duración orientativa: {session_minutes}.\n"
                    "Estructura recomendada: Play (5–10') → Practice (20–35') → Play (15–25').\n"
                    "En pequeños: más mini-juegos y menos explicación."
                )},
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Lenguaje del entrenador", "body": cues},
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Imprescindibles", "body": "- " + "\n- ".join(must_have)},
                {"type": AcademyLessonStep.TYPE_TEXT, "title": "Evitar", "body": "- " + "\n- ".join(avoid)},
            ],
        )

    routes = [
        route_overview(
            C.CATEGORY_BABY,
            "Baby",
            focus="Diversión + motricidad + muchos contactos con balón (sin miedo a fallar).",
            session_minutes="35–50 min",
            cues="Palabras: ‘conduce’, ‘cambia’, ‘mira’, ‘protege’ · Correcciones de 10s.",
            must_have=["Muchos 1v1/2v2", "Conducciones y cambios de dirección", "Goles cerca (muchos intentos)"],
            avoid=["Filas largas", "Charlas", "Tareas sin balón"],
        ),
        route_overview(
            C.CATEGORY_PREBENJAMIN,
            "Prebenjamín",
            focus="Hábito técnico en juego: conducir, pasar corto, recibir y girar cuando hay espacio.",
            session_minutes="45–60 min",
            cues="Palabras: ‘perfil’, ‘apoyo’, ‘hoy juego fácil’ · Premiar el intento.",
            must_have=["2v2/3v3 con porterías", "Perfil corporal básico", "Reglas simples de transición (3 pasos)"],
            avoid=["Táctica larga", "Demasiadas reglas", "Solo tiros sin decisión"],
        ),
        route_overview(
            C.CATEGORY_BENJAMIN,
            "Benjamín",
            focus="Decidir antes: mirar, perfilarse, jugar hacia delante si hay ventaja.",
            session_minutes="55–70 min",
            cues="‘Mira antes’, ‘si no puedes, apoya’, ‘pasa y muévete’.",
            must_have=["Rondos con intención", "3º hombre simple", "Defender orientando a banda"],
            avoid=["Ejercicios sin rival", "Paradas largas", "Pedir perfección técnica sin contexto"],
        ),
        route_overview(
            C.CATEGORY_ALEVIN,
            "Alevín",
            focus="Principios de juego: amplitud/profundidad, presión con cobertura, transiciones.",
            session_minutes="65–80 min",
            cues="‘Ancho para entrar’, ‘juntos para defender’, ‘5 segundos’.",
            must_have=["Juegos posicionales 4v4+3", "Transición 5s", "Llegadas al área (primer palo/rechazo)"],
            avoid=["Solo físico", "Tareas enormes sin objetivos", "Cambiar 5 constraints a la vez"],
        ),
        route_overview(
            C.CATEGORY_INFANTIL,
            "Infantil",
            focus="Juego por líneas: temporizar, fijar/saltar, compactar y orientar según el rival.",
            session_minutes="70–90 min",
            cues="‘Cuándo sí/cuándo no’, ‘temporiza’, ‘equilibrio’.",
            must_have=["Partidos condicionados por carriles", "Basculación y coberturas", "Salida (tercer hombre / giro)"],
            avoid=["Correcciones en público humillantes", "Exceso de táctica sin jugar", "Ignorar contexto emocional"],
        ),
        route_overview(
            C.CATEGORY_CADETE,
            "Cadete",
            focus="Modelo: automatismos + lectura; mejorar velocidad de juego y toma de decisión.",
            session_minutes="75–95 min",
            cues="‘Escanea’, ‘orienta’, ‘juega a 2 toques si hay ventaja’.",
            must_have=["Juegos con superioridad/inferioridad", "Presión tras pérdida organizada", "ABP simples con roles claros"],
            avoid=["Solo correr", "Repetir sin feedback", "No conectar tarea con partido"],
        ),
        route_overview(
            C.CATEGORY_JUVENIL,
            "Juvenil",
            focus="Rendimiento: plan semanal + microdetalles por posición y rival.",
            session_minutes="80–100 min",
            cues="‘Gatillos’, ‘siguiente acción’, ‘control del ritmo’.",
            must_have=["Análisis + tarea dirigida", "Transiciones por zona", "Finalización con oposición real"],
            avoid=["Sobrecargar con teoría", "Tareas irrelevantes", "No medir progreso"],
        ),
        route_overview(
            C.CATEGORY_SENIOR,
            "Senior",
            focus="Competición: eficacia, gestión de partido, identidad (modelo) y adaptación.",
            session_minutes="80–105 min",
            cues="‘Plan A/B’, ‘gestión del riesgo’, ‘control emocional’.",
            must_have=["Plan de partido", "ABP a favor/en contra", "Escenarios (ganando/perdiendo)"],
            avoid=["Cambiar modelo cada semana", "Entrenar lejos del juego", "No revisar postpartido"],
        ),
    ]

    def category_module(cat_key: str, cat_label: str, *, name: str, body: str, quiz=None, task=None) -> SeedLesson:
        steps = [{"type": AcademyLessonStep.TYPE_TEXT, "title": name, "body": body}]
        if quiz:
            steps.append({"type": AcademyLessonStep.TYPE_QUIZ, "title": "Mini-quiz", "questions": quiz})
        if task:
            steps.append({"type": AcademyLessonStep.TYPE_TASK, "title": "Reto de campo", "body": task})
        return SeedLesson(
            title=f"{cat_label} · {name}",
            summary=f"Guía práctica para {cat_label}: {name}.",
            min_category=cat_key,
            max_category=cat_key,
            tags=["categoria", cat_key, "guia"],
            steps=steps,
        )

    modules = []
    # 6 módulos por categoría: técnica aplicada, ataque, defensa, transición, finalización, ABP.
    for cat_key, cat_label in [
        (C.CATEGORY_BABY, "Baby"),
        (C.CATEGORY_PREBENJAMIN, "Prebenjamín"),
        (C.CATEGORY_BENJAMIN, "Benjamín"),
        (C.CATEGORY_ALEVIN, "Alevín"),
        (C.CATEGORY_INFANTIL, "Infantil"),
        (C.CATEGORY_CADETE, "Cadete"),
        (C.CATEGORY_JUVENIL, "Juvenil"),
        (C.CATEGORY_SENIOR, "Senior"),
    ]:
        modules.extend(
            [
                category_module(
                    cat_key, cat_label,
                    name="Técnica aplicada",
                    body=(
                        "Objetivo: técnica *para decidir*, no técnica aislada.\n\n"
                        "Diseño: 1v1/2v2/3v3 + reglas simples.\n"
                        "Corrección clave: primer toque hacia el espacio y cabeza arriba 1 vez antes de decidir."
                    ),
                ),
                category_module(
                    cat_key, cat_label,
                    name="Ataque (principio 1): avanzar con apoyo",
                    body=(
                        "Señal: si no puedes girar, usa apoyo y crea 3er hombre.\n"
                        "Constraint: apoyo a 2 toques, punto extra por jugar hacia delante tras devolución."
                    ),
                    quiz=[
                        {
                            "prompt": "Si recibes presionado de espaldas, lo primero es…",
                            "explanation": "Asegurar continuidad para poder progresar después.",
                            "options": [
                                {"label": "Asegurar con apoyo cercano", "correct": True, "feedback": "Bien: juego simple."},
                                {"label": "Girar siempre", "correct": False, "feedback": "Depende del espacio/ventaja."},
                                {"label": "Balón largo sin mirar", "correct": False, "feedback": "Solo si es parte del plan y hay ventaja."},
                            ],
                        }
                    ] if cat_key != C.CATEGORY_BABY else None,
                ),
                category_module(
                    cat_key, cat_label,
                    name="Defensa (principio 1): orientar con cobertura",
                    body=(
                        "1º defensor orienta; 2º defensor cubre; 3º equilibra.\n"
                        "Punto extra si recuperas tras orientar a banda."
                    ),
                ),
                category_module(
                    cat_key, cat_label,
                    name="Transición: 3 pasos / 5 segundos",
                    body=(
                        "Tras pérdida: 3 pasos agresivos → decide presionar o replegar.\n"
                        "Tras recuperación: 1 pase hacia delante si hay ventaja; si no, fija y descarga."
                    ),
                ),
                category_module(
                    cat_key, cat_label,
                    name="Finalización: atacar área",
                    body=(
                        "Centros: primer palo + punto de penalti + rechazo.\n"
                        "En categorías tempranas: premio a rematar (aunque no haya gol)."
                    ),
                ),
                category_module(
                    cat_key, cat_label,
                    name="ABP: corner simple",
                    body=(
                        "Roles mínimos: saque · primer palo · segundo palo · rechazo · seguridad.\n"
                        "Objetivo: 1 remate + 1 segunda jugada dirigida."
                    ),
                ),
            ]
        )

    return base + routes + modules


def _mk_seed_blueprints() -> list[dict]:
    """
    Plantillas del sistema (TaskBlueprint) que el editor/Asistente puede reutilizar.
    Se crean en el team especial `slug="pizarra"` para que aparezcan como scope=system.
    """
    return [
        {
            "name": "Tercer hombre · Progresión (3 pasos)",
            "category": TaskBlueprint.CATEGORY_BUILD,
            "description": "Apoyo + devolución + pase al 3º hombre (progresar sin riesgo).",
            "payload": {
                "objective": "Progresar por dentro usando apoyo y 3º hombre.",
                "coaching_points": [
                    "Perfil corporal antes de recibir.",
                    "Distancia de apoyo (ni encima ni lejos).",
                    "Pase tenso al pie y timing del desmarque.",
                ],
                "constraints": [
                    "Máximo 2 toques para el apoyo.",
                    "Punto extra si el 3º hombre juega de cara al espacio.",
                ],
                "tactical_layout": {
                    "meta": {"player_count": "6–10", "space": "30×20", "organization": "3 equipos de 2–3"},
                    "tokens": [],
                    "timeline": [],
                },
            },
        },
        {
            "name": "Presión + cobertura · 2º defensor",
            "category": TaskBlueprint.CATEGORY_PRESS,
            "description": "Orientar + cubrir línea de pase interior (no saltar sin red).",
            "payload": {
                "objective": "Recuperar tras orientar hacia banda con cobertura cercana.",
                "coaching_points": [
                    "1º defensor: cuerpo de lado y velocidad de frenada.",
                    "2º defensor: ángulo de cobertura, distancia útil.",
                    "3º defensor: equilibrio y vigilancia de espalda.",
                ],
                "constraints": [
                    "Doble puntuación si recuperas tras orientar a banda.",
                    "Si el 2º defensor no está, el 1º defensor temporiza (no entra).",
                ],
                "tactical_layout": {
                    "meta": {"player_count": "8–12", "space": "35×25", "organization": "4v4 + comodines"},
                    "tokens": [],
                    "timeline": [],
                },
            },
        },
        {
            "name": "Transición 5s · pérdida/recuperación",
            "category": TaskBlueprint.CATEGORY_TRANSITION,
            "description": "Reglas simples de 5 segundos para reaccionar tras pérdida/recuperación.",
            "payload": {
                "objective": "Reaccionar rápido: presionar 5s o replegar; y al recuperar, jugar hacia delante.",
                "coaching_points": [
                    "Tras pérdida: 3 pasos agresivos y decide.",
                    "Tras recuperación: primer pase seguro hacia delante o fijar y descargar.",
                ],
                "constraints": [
                    "Si recuperas en 5s, gol vale doble.",
                    "Si no recuperas en 5s, todos por detrás del balón.",
                ],
                "tactical_layout": {
                    "meta": {"player_count": "10–16", "space": "40×30", "organization": "5v5/6v6"},
                    "tokens": [],
                    "timeline": [],
                },
            },
        },
        {
            "name": "Corner simple a favor · 1 remate + 2ª jugada",
            "category": TaskBlueprint.CATEGORY_ABP,
            "description": "Estructura mínima: saque, primer/segundo palo, rechazo, seguridad.",
            "payload": {
                "objective": "Generar 1 remate claro + 1 segunda jugada dirigida.",
                "coaching_points": [
                    "Organización rápida (roles claros).",
                    "Centro tenso a zona definida.",
                    "Atacar el balón, no esperar el balón.",
                ],
                "constraints": [
                    "Si hay remate en 6s, cuenta como éxito aunque no haya gol.",
                    "Siempre deja 1 seguridad + 1 rechazo.",
                ],
                "tactical_layout": {
                    "meta": {"player_count": "7–11", "space": "Zona corner + área", "organization": "ABP"},
                    "tokens": [],
                    "timeline": [],
                },
            },
        },
    ]


class Command(BaseCommand):
    help = "Crea el pack inicial de Academia (guía fútbol base) y, opcionalmente, lo asigna al equipo activo."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", type=int, default=0, help="Workspace (club) al que asignar las lecciones.")
        parser.add_argument("--workspace-slug", type=str, default="", help="Slug de Workspace (alternativa a --workspace).")
        parser.add_argument("--team", type=int, default=0, help="Team (categoría) al que asignar las lecciones.")
        parser.add_argument("--team-slug", type=str, default="", help="Slug de Team (alternativa a --team).")
        parser.add_argument("--publish", action="store_true", help="Publica las lecciones creadas.")
        parser.add_argument("--assign", action="store_true", help="Crea asignaciones en el workspace/team indicados.")
        parser.add_argument("--seed-blueprints", action="store_true", help="Crea plantillas del sistema (TaskBlueprint) en el team 'pizarra'.")
        parser.add_argument("--full", action="store_true", help="Genera el currículo completo por categoría (además del pack base).")
        parser.add_argument("--reset", action="store_true", help="Borra y recrea (solo lecciones con tag 'seed_v1').")

    def handle(self, *args, **options):
        publish = bool(options.get("publish"))
        assign = bool(options.get("assign"))
        seed_blueprints = bool(options.get("seed_blueprints"))
        full = bool(options.get("full"))
        workspace_id = int(options.get("workspace") or 0)
        team_id = int(options.get("team") or 0)
        workspace_slug = str(options.get("workspace_slug") or "").strip()
        team_slug = str(options.get("team_slug") or "").strip()
        reset = bool(options.get("reset"))

        pack = _mk_seed_pack()
        if full:
            pack = pack + _mk_category_curriculum()
        seed_tag = "seed_v1"

        try:
            # Si no están aplicadas migraciones, evita traceback ruidoso.
            AcademyLesson.objects.all().exists()
        except OperationalError:
            raise SystemExit("Faltan migraciones (Academia). Ejecuta `python manage.py migrate` y reintenta.")

        if reset:
            # SQLite no soporta `JSONField__contains`; filtramos en Python.
            ids = []
            for row in AcademyLesson.objects.all().only("id", "tags"):
                tags = getattr(row, "tags", None)
                if isinstance(tags, list) and seed_tag in tags:
                    ids.append(int(row.id))
            count = len(ids)
            if ids:
                AcademyLesson.objects.filter(id__in=ids).delete()
            self.stdout.write(self.style.WARNING(f"Reset: borradas {count} lecciones seed."))

        created = 0
        updated = 0
        lesson_ids = []
        for item in pack:
            obj = AcademyLesson.objects.filter(title=item.title).first()
            if obj is not None:
                tags = getattr(obj, "tags", None)
                if not (isinstance(tags, list) and seed_tag in tags):
                    obj = None
            was_created = obj is None
            if obj is None:
                obj = AcademyLesson.objects.create(
                    title=item.title,
                    summary=item.summary,
                    min_category=item.min_category,
                    max_category=item.max_category,
                    tags=list(dict.fromkeys([seed_tag] + list(item.tags or []))),
                    is_published=publish,
                    created_by="seed",
                )
            else:
                obj.title = item.title
                obj.summary = item.summary
                obj.min_category = item.min_category
                obj.max_category = item.max_category
                obj.tags = list(dict.fromkeys([seed_tag] + list(item.tags or [])))
                obj.is_published = publish or bool(getattr(obj, "is_published", False))
                if not str(getattr(obj, "created_by", "") or "").strip():
                    obj.created_by = "seed"
                obj.save(update_fields=["title", "summary", "min_category", "max_category", "tags", "is_published", "created_by", "updated_at"])
            if was_created:
                created += 1
            else:
                updated += 1

            # Limpiamos steps y recreamos (MVP sencillo).
            AcademyLessonStep.objects.filter(lesson=obj).delete()
            for index, step in enumerate(item.steps):
                step_obj = AcademyLessonStep.objects.create(
                    lesson=obj,
                    order=index,
                    step_type=step.get("type") or AcademyLessonStep.TYPE_TEXT,
                    title=str(step.get("title") or "").strip(),
                    body=str(step.get("body") or "").strip(),
                    payload=step.get("payload") if isinstance(step.get("payload"), dict) else {},
                    is_required=True,
                )
                if step_obj.step_type == AcademyLessonStep.TYPE_QUIZ:
                    questions = step.get("questions") if isinstance(step.get("questions"), list) else []
                    for q_index, q in enumerate(questions[:12]):
                        qq = AcademyQuizQuestion.objects.create(
                            step=step_obj,
                            prompt=str(q.get("prompt") or "").strip()[:320],
                            explanation=str(q.get("explanation") or "").strip(),
                            order=q_index,
                        )
                        options_arr = q.get("options") if isinstance(q.get("options"), list) else []
                        for o_index, opt in enumerate(options_arr[:8]):
                            AcademyQuizOption.objects.create(
                                question=qq,
                                label=str(opt.get("label") or "").strip()[:240],
                                is_correct=bool(opt.get("correct")),
                                feedback=str(opt.get("feedback") or "").strip()[:320],
                                order=o_index,
                            )

            lesson_ids.append(int(obj.id))

        self.stdout.write(self.style.SUCCESS(f"Academia seed: {created} creadas, {updated} actualizadas."))

        if seed_blueprints:
            system_team, _ = Team.objects.get_or_create(slug="pizarra", defaults={"name": "PIZARRA"})
            bp_created = 0
            bp_updated = 0
            for bp in _mk_seed_blueprints():
                name = str(bp.get("name") or "").strip()[:160]
                if not name:
                    continue
                obj, was_created = TaskBlueprint.objects.update_or_create(
                    team=system_team,
                    name=name,
                    defaults={
                        "category": str(bp.get("category") or TaskBlueprint.CATEGORY_OTHER),
                        "description": str(bp.get("description") or "")[:220],
                        "payload": bp.get("payload") if isinstance(bp.get("payload"), dict) else {},
                        "created_by": "seed",
                    },
                )
                if was_created:
                    bp_created += 1
                else:
                    bp_updated += 1
            self.stdout.write(self.style.SUCCESS(f"Blueprints (system): {bp_created} creadas, {bp_updated} actualizadas."))

        if assign:
            if not workspace_id and workspace_slug:
                workspace = Workspace.objects.filter(slug=workspace_slug).first()
                workspace_id = int(workspace.id) if workspace else 0
            if not team_id and team_slug:
                team = Team.objects.filter(slug=team_slug).first()
                team_id = int(team.id) if team else 0
            if not workspace_id:
                raise SystemExit("--assign requiere --workspace o --workspace-slug")
            workspace = Workspace.objects.filter(id=workspace_id).first()
            if not workspace:
                raise SystemExit("Workspace no encontrado.")
            team = Team.objects.filter(id=team_id).first() if team_id else None
            for lid in lesson_ids:
                lesson = AcademyLesson.objects.filter(id=lid).first()
                if not lesson:
                    continue
                AcademyAssignment.objects.get_or_create(
                    workspace=workspace,
                    team=team,
                    lesson=lesson,
                    defaults={
                        "is_required": True,
                        "is_active": True,
                        "due_at": None,
                        "created_by": getattr(workspace, "owner_user", None),
                    },
                )
            self.stdout.write(self.style.SUCCESS("Asignaciones creadas/aseguradas."))
