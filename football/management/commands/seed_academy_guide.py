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
        parser.add_argument("--team", type=int, default=0, help="Team (categoría) al que asignar las lecciones.")
        parser.add_argument("--publish", action="store_true", help="Publica las lecciones creadas.")
        parser.add_argument("--assign", action="store_true", help="Crea asignaciones en el workspace/team indicados.")
        parser.add_argument("--seed-blueprints", action="store_true", help="Crea plantillas del sistema (TaskBlueprint) en el team 'pizarra'.")
        parser.add_argument("--reset", action="store_true", help="Borra y recrea (solo lecciones con tag 'seed_v1').")

    def handle(self, *args, **options):
        publish = bool(options.get("publish"))
        assign = bool(options.get("assign"))
        seed_blueprints = bool(options.get("seed_blueprints"))
        workspace_id = int(options.get("workspace") or 0)
        team_id = int(options.get("team") or 0)
        reset = bool(options.get("reset"))

        pack = _mk_seed_pack()
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
            if not workspace_id:
                raise SystemExit("--assign requiere --workspace")
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
