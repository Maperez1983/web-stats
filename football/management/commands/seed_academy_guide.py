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


def _seed_lesson_has_visual_step(item: SeedLesson) -> bool:
    for step in item.steps or []:
        if str(step.get("type") or "").strip() == AcademyLessonStep.TYPE_REPLAY_2D:
            return True
    return False


def _mk_visual_templates() -> list[dict]:
    """
    Plantillas de escenas 2D (texto) reutilizables. Se asignan por tags/título.
    Nota: esto NO genera una pizarra automáticamente; da un guion para montarla rápido.
    """
    return [
        {
            "key": "third_man",
            "match_any": {"tercer_hombre", "3er_hombre", "salida_presion", "progresion"},
            "title": "3er hombre (progresión estable)",
            "hint": (
                "Escena tipo (3 pasos):\n"
                "1) Central → pivote (recibe de espaldas) · marca perfil.\n"
                "2) Pivote devuelve de cara al central (1 toque).\n"
                "3) Central filtra al interior (3er hombre) que rompe entre líneas.\n\n"
                "Detalles: distancia apoyo (5–8m), pase tenso, 3er hombre orientado a jugar hacia delante.\n"
                "Variante: si el pivote está tapado → pared con lateral y 3er hombre por fuera."
            ),
        },
        {
            "key": "press_orient",
            "match_any": {"presion", "orientar", "cierre_interior", "bloque_alto"},
            "title": "Presión orientada (cuerpo + sombra)",
            "hint": (
                "Escena tipo (banda): receptor en banda con apoyo interior.\n"
                "- 1º defensor entra en DIAGONAL y tapa el pase interior con el cuerpo.\n"
                "- 2º defensor cierra la línea interior (cobertura) a distancia útil.\n"
                "- 3º defensor vigila espalda/cambio.\n\n"
                "Variante A: control largo → robo. Variante B: control bueno → temporiza y bloque acompaña."
            ),
        },
        {
            "key": "basculacion",
            "match_any": {"basculacion", "compacto", "lado_debil", "cambio_orientacion"},
            "title": "Basculación + vigilancia lado débil",
            "hint": (
                "Escena tipo (circulación rival de banda a banda):\n"
                "- Lado fuerte: bloque junto y cierre interior.\n"
                "- Lado débil: 1 vigilante (altura media) + 1 protege espalda (más bajo).\n"
                "- Marca distancia entre líneas (10–15m) y bloque (25–35m).\n\n"
                "Variante: si NO hay presión al balón → temporiza (no subas)."
            ),
        },
        {
            "key": "weakside_attack",
            "match_any": {"lado_debil", "overload", "isolate", "1v1"},
            "title": "Overload-to-isolate (lado débil)",
            "hint": (
                "Escena tipo (sobrecarga derecha → aislamiento izquierda):\n"
                "1) 3–4 jugadores en lado fuerte para atraer.\n"
                "2) Extremo lado débil: ALTO y ABIERTO (aislado).\n"
                "3) Cambio tenso al extremo: conduce para fijar → centro raso atrás.\n"
                "4) Llegadas: 1º palo + penalti/raso atrás + rechazo.\n\n"
                "Variante: si el 1v1 no sale → descarga y nuevo cambio (paciencia)."
            ),
        },
        {
            "key": "rest_defense",
            "match_any": {"rest_defense", "equilibrio", "transicion"},
            "title": "Rest defense (seguridad al atacar)",
            "hint": (
                "Escena tipo (ataque por banda):\n"
                "- Marca 2–3 jugadores por detrás del balón (seguridad).\n"
                "- Cobertura diagonal: si lateral sube, alguien cubre su espalda.\n"
                "- Lado débil cierra para interceptar el cambio.\n\n"
                "Variante: pérdida en banda → 5s de contra-presión o repliegue (según distancia)."
            ),
        },
        {
            "key": "zone14",
            "match_any": {"zona14", "entre_lineas", "juego_interior"},
            "title": "Zona 14 (pase atrás + decisión)",
            "hint": (
                "Escena tipo: balón en banda → pase atrás a frontal (zona 14).\n"
                "- Interior recibe de cara (perfilado) y elige: tiro / pase filtrado / centro raso atrás.\n"
                "- Si recibe presionado: descarga (1 toque) y 3er hombre rompe.\n\n"
                "Variante: central rival salta → desmarque del 9 a espalda."
            ),
        },
        {
            "key": "cross_defense_roles",
            "match_any": {"centros", "area", "defensa_area"},
            "title": "Defensa de centros (roles por zonas)",
            "hint": (
                "Escena tipo: centro desde banda.\n"
                "- Asigna 4 zonas: 1º palo · penalti · 2º palo · rechazo.\n"
                "- Marca quién ataca balón y quién asegura 2ª jugada.\n\n"
                "Variante: centro al 2º palo → llegada lado débil (defensa ajusta con vigilancia)."
            ),
        },
        {
            "key": "five_seconds",
            "match_any": {"5s", "5_segundos", "perdida", "recuperacion"},
            "title": "Transición 5 segundos (pérdida/recuperación)",
            "hint": (
                "Escena tipo: pérdida en carril central.\n"
                "- 1 presiona balón (3 pasos agresivos).\n"
                "- 2 corta pase interior.\n"
                "- 3 equilibra/cubre espalda.\n\n"
                "Variante: si la pérdida es lejos → repliegue + temporiza; si es cerca → contra-presión."
            ),
        },
        {
            "key": "set_piece_corner",
            "match_any": {"abp", "corner", "corners"},
            "title": "Corner MVP (1 remate + 2ª jugada)",
            "hint": (
                "Escena tipo (corner):\n"
                "- Roles mínimos: 1 saque · 1 primer palo · 1 segundo palo · 1 rechazo · 1 seguridad.\n"
                "- Centro tenso a zona definida.\n\n"
                "Variante: si despejan → segunda jugada (rechazo) y re-centro rápido."
            ),
        },
    ]


def _visual_hint_for_seed_lesson(item: SeedLesson) -> str:
    title = str(item.title or "").lower()
    tags = {str(t or "").strip().lower() for t in (item.tags or []) if str(t or "").strip()}

    # Heurística rápida por palabras clave en título.
    keyword_tags = set()
    for word, tag in [
        ("tercer", "tercer_hombre"),
        ("3er", "tercer_hombre"),
        ("presión", "presion"),
        ("presion", "presion"),
        ("bascul", "basculacion"),
        ("lado débil", "lado_debil"),
        ("lado debil", "lado_debil"),
        ("zona 14", "zona14"),
        ("entre líneas", "entre_lineas"),
        ("entre lineas", "entre_lineas"),
        ("corner", "corner"),
        ("saque de esquina", "corner"),
        ("centro", "centros"),
        ("área", "area"),
        ("area", "area"),
        ("transición", "transicion"),
        ("transicion", "transicion"),
        ("5 segundos", "5_segundos"),
        ("5s", "5_segundos"),
    ]:
        if word in title:
            keyword_tags.add(tag)

    merged = set(tags) | keyword_tags
    templates = _mk_visual_templates()

    def score(tpl: dict) -> int:
        match_any = {str(x).lower() for x in (tpl.get("match_any") or set())}
        return len(merged & match_any)

    best = None
    best_score = 0
    for tpl in templates:
        s = score(tpl)
        if s > best_score:
            best = tpl
            best_score = s

    if best and best_score > 0:
        base = str(best.get("hint") or "").strip()
        # Remate estándar para que todas las escenas tengan consistencia.
        return (
            f"Plantilla: {best.get('title')}\n\n{base}\n\n"
            "Checklist visual: ¿ancho/dentro/espalda? ¿cobertura si me superan? ¿quién rechace/seguridad?"
        )[:600]

    # Fallback (mejor que el genérico anterior, pero sin plantilla).
    clean_tags = [str(t or "").strip() for t in (item.tags or []) if str(t or "").strip()]
    tags_hint = (", ".join(clean_tags[:6]) if clean_tags else "").strip()
    hint = (
        f"Objetivo visual: representar '{item.title}'.\n"
        "1) Marca el balón y 3 referencias (carril/espacio/altura).\n"
        "2) Dibuja 2–3 movimientos con flechas (apoyo/ruptura/cobertura).\n"
        "3) Añade 1 variante: ¿qué cambia si el rival cierra dentro o bascula tarde?\n"
    )
    if tags_hint:
        hint += f"\nTags: {tags_hint}"
    return hint[:600]


def _seed_lesson_with_default_visual_step(item: SeedLesson) -> SeedLesson:
    """
    Asegura que todas las lecciones seed tengan un ejemplo visual (pizarra 2D).
    No toca las que ya incluyen replay2d.
    """
    if _seed_lesson_has_visual_step(item):
        return item

    hint = _visual_hint_for_seed_lesson(item)

    steps = list(item.steps or [])
    steps.append(
        {
            "type": AcademyLessonStep.TYPE_REPLAY_2D,
            "title": "Pizarra 2D (ejemplo visual)",
            "body": "Crea una escena rápida (15–30s) y guárdala como referencia para el campo.",
            "payload": {"hint": hint[:600]},
        }
    )
    return SeedLesson(
        title=item.title,
        summary=item.summary,
        min_category=item.min_category,
        max_category=item.max_category,
        tags=item.tags,
        steps=steps,
    )


def _seed_lesson_has_resources_step(item: SeedLesson) -> bool:
    for step in item.steps or []:
        title = str(step.get("title") or "").strip().lower()
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        if payload.get("seed_resources") is True:
            return True
        if title.startswith("recursos"):
            return True
    return False


def _seed_lesson_has_quick_card_step(item: SeedLesson) -> bool:
    for step in item.steps or []:
        title = str(step.get("title") or "").strip().lower()
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        if payload.get("seed_quick_card") is True:
            return True
        if title.startswith("tarjeta rápida") or title.startswith("tarjeta rapida"):
            return True
    return False


def _extract_first_text_step(item: SeedLesson, *, title_prefix: str) -> str:
    prefix = str(title_prefix or "").strip().lower()
    for step in item.steps or []:
        if str(step.get("type") or "").strip() != AcademyLessonStep.TYPE_TEXT:
            continue
        title = str(step.get("title") or "").strip().lower()
        if title.startswith(prefix):
            body = str(step.get("body") or "").strip()
            return body
    return ""


def _mk_quick_card_body(item: SeedLesson) -> str:
    objetivo = _extract_first_text_step(item, title_prefix="objetivo") or ""
    reglas = _extract_first_text_step(item, title_prefix="3 reglas") or ""
    if not objetivo:
        objetivo = f"Objetivo: {str(item.title or '').strip()}"

    if not reglas.strip():
        first_text = ""
        for step in item.steps or []:
            if str(step.get("type") or "").strip() == AcademyLessonStep.TYPE_TEXT:
                first_text = str(step.get("body") or "").strip()
                if first_text:
                    break
        if first_text:
            candidates = []
            for line in first_text.splitlines():
                s = line.strip()
                if not s:
                    continue
                if s.startswith("-"):
                    candidates.append(s)
                    continue
                prefix = s[:4]
                if any(ch.isdigit() for ch in prefix) and (")" in prefix or "." in prefix):
                    candidates.append(s)
            if candidates:
                reglas = "\n".join(candidates[:3])

    # Heurísticas ligeras para cues por tema (sin duplicar demasiado contenido).
    tags = {str(t or "").strip().lower() for t in (item.tags or []) if str(t or "").strip()}
    title = str(item.title or "").lower()
    merged = set(tags)
    if "presion" in title or "presión" in title:
        merged.add("presion")
    if "lado débil" in title or "lado debil" in title:
        merged.add("lado_debil")
    if "tercer" in title or "3er" in title:
        merged.add("tercer_hombre")
    if "transición" in title or "transicion" in title:
        merged.add("transicion")
    if "abp" in title or "corner" in title or "saque de esquina" in title:
        merged.add("abp")
    if "portero" in title or "gk" in title or "goalkeeper" in title:
        merged.add("porteros")
    if "centro" in title or "área" in title or "area" in title:
        merged.add("area")

    if not reglas.strip():
        if "abp" in merged:
            reglas = "- Roles claros (mínimo 5).\n- Centro tenso a zona.\n- 2ª jugada (rechace) + 1 seguridad."
        elif "transicion" in merged or "rest_defense" in merged:
            reglas = "- 3 pasos agresivos tras pérdida.\n- Decide: presiono 5s o repliego.\n- Tras robo: 1er pase seguro + amenaza."
        elif "presion" in merged:
            reglas = "- En diagonal (tapo interior).\n- Si no hay cobertura, temporizo.\n- Bloque acompaña (juntos)."
        elif "tercer_hombre" in merged:
            reglas = "- Perfil antes de recibir.\n- Apoyo a 1–2 toques.\n- 3er hombre ataca espacio."
        elif "lado_debil" in merged:
            reglas = "- Fija lado fuerte antes.\n- Lado débil alto y abierto.\n- Cambio tenso y a tiempo."
        elif "area" in merged:
            reglas = "- 2 llegadas (1º palo + penalti/raso atrás).\n- Siempre 1 al rechazo.\n- Ataca balón (no esperes)."
        elif "porteros" in merged:
            reglas = "- Primero ángulo.\n- Luego equilibrio.\n- Último paso antes del tiro."

    cues = []
    if "presion" in merged:
        cues.extend(["Diagonal", "Llega frenado", "Tapa interior"])
    if "tercer_hombre" in merged:
        cues.extend(["Perfil", "Apoyo", "3er hombre"])
    if "lado_debil" in merged:
        cues.extend(["Prepara lado débil", "Cambio tenso", "Llega al área"])
    if "transicion" in merged or "rest_defense" in merged:
        cues.extend(["3 pasos", "5 segundos", "Seguridad"])
    if "abp" in merged:
        cues.extend(["Roles claros", "Centro tenso", "Rechace"])
    if "porteros" in merged:
        cues.extend(["Ángulo", "Equilibrio", "Timing"])
    if "area" in merged:
        cues.extend(["1º palo", "Penalti", "Rechace"])
    if not cues:
        cues = ["Mira antes", "Perfil", "Juega fácil"]

    # Dedupe cues preservando orden.
    seen = set()
    cues_out = []
    for c in cues:
        k = c.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        cues_out.append(c.strip())
        if len(cues_out) >= 6:
            break

    cues_block = "- " + "\n- ".join(cues_out)
    reglas_block = reglas.strip() if reglas.strip() else "—"

    return (
        f"{objetivo.strip()}\n\n"
        "3 reglas (recuerda):\n"
        f"{reglas_block}\n\n"
        "Cues (palabras del entrenador):\n"
        f"{cues_block}\n\n"
        "Mini-check (10s):\n"
        "- ¿Tengo ancho/dentro/espalda?\n"
        "- ¿Hay cobertura si me superan?\n"
        "- ¿Quién rechace/seguridad?"
    ).strip()[:2200]


def _seed_lesson_with_quick_card_step(item: SeedLesson) -> SeedLesson:
    if _seed_lesson_has_quick_card_step(item):
        return item

    steps = list(item.steps or [])

    # Insertar antes de Recursos si existe; si no, al final.
    insert_at = len(steps)
    for i, step in enumerate(steps):
        title = str(step.get("title") or "").strip().lower()
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        if payload.get("seed_resources") is True or title.startswith("recursos"):
            insert_at = i
            break

    steps.insert(
        insert_at,
        {
            "type": AcademyLessonStep.TYPE_TEXT,
            "title": "Tarjeta rápida (banquillo/campo)",
            "body": _mk_quick_card_body(item),
            "payload": {"seed_quick_card": True},
        },
    )
    return SeedLesson(
        title=item.title,
        summary=item.summary,
        min_category=item.min_category,
        max_category=item.max_category,
        tags=item.tags,
        steps=steps,
    )


def _external_resources_for_seed_lesson(item: SeedLesson) -> list[tuple[str, str]]:
    """
    Recursos públicos para profundizar (mezcla: oficial + análisis + vídeos).
    Nota: evitamos enlaces dudosos (piratería, agregadores raros, etc.) y priorizamos fuentes de referencia.
    """
    title = str(item.title or "").lower()
    tags = {str(t or "").strip().lower() for t in (item.tags or []) if str(t or "").strip()}

    def has(*needles: str) -> bool:
        return any(n in title for n in needles) or any(n in tags for n in needles)

    resources: list[tuple[str, str]] = []

    # Puertas de entrada (siempre útiles, aunque luego se filtren por dedupe/cap).
    resources.extend(
        [
            ("FIFA Training Centre · Inicio", "https://www.fifatrainingcentre.com/"),
            ("FIFA Training Centre (FIFA) · Overview", "https://inside.fifa.com/technical/fifa-training-centre"),
            ("UEFA · Coaching & desarrollo (inicio)", "https://www.uefa.com/development/"),
            ("UEFA · The Technician (archivo)", "https://www.uefa.com/development/coaches/the-technician-magazine/"),
            ("The FA Boot Room · Recursos (inicio)", "https://www.thefa.com/bootroom/resources"),
        ]
    )

    # Defensa / presión / bloque.
    if has("presion", "orientar", "bloque_alto", "bloque_medio", "bloque_bajo", "defensa", "basculacion", "lado_debil", "zona", "compacto"):
        resources.extend(
            [
                ("FIFA Training Centre · Principios defensivos (Michael Johnson)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/out-of-possession/johnson-principios-defensivos.php"),
                ("FIFA Training Centre · Transiciones (Boothroyd 2)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/transition-to-attacking/transiciones.php"),
                ("FIFA Training Centre · Transición ofensiva (Jennings)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/transition-to-attacking/transicion-ofensiva-jennings.php"),
                ("UEFA · Setting the press (performance insights)", "https://www.uefa.com/uefachampionsleague/news/028a-1a1bf5c2d303-4a5106d81f09-1000--champions-league-performance-insights-setting-the-press/"),
                ("UEFA · Video: pressing trap (Europa League)", "https://www.uefa.com/uefaeuropaleague/video/028d-1adb46cedb92-ddb6c06004ab-1000--tactical-analysis-leverkusen-set-pressing-trap/"),
                ("The FA · Defendiendo zonas centrales (Boot Room)", "https://www.thefa.com/bootroom/resources/coaching/out-of-possession-defending-central-areas"),
                ("The FA · Pressing: delaying, denying (sesión)", "https://www.thefa.com/bootroom/resources/coaching/out-of-possession-pressing-delaying-denying"),
                ("The FA · When and how to press (sesión)", "https://www.thefa.com/bootroom/resources/coaching/out-of-possession-when-and-how-to-press"),
                ("RFEF · Contenido técnico entrenadores (tareas reales)", "https://rfef.es/index.php/es/noticias/contenido-tecnico-para-entrenadores-hoy-entrenamos-con-marcelino-garcia-toral"),
            ]
        )

    # Línea defensiva / basculación (4 atrás).
    if has("linea", "basculacion", "centros", "area", "defensa_area", "defensa_de_cuatro"):
        resources.append(
            ("FIFA Training Centre · Fundamentos defensa de cuatro (Jens Lehmann)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/out-of-possession/defensa-de-cuatro.php")
        )

    # Transiciones.
    if has("transicion", "perdida", "recuperacion", "rest_defense", "5s", "5_segundos"):
        resources.extend(
            [
                ("FIFA Training Centre · Transiciones (Boothroyd 2)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/transition-to-attacking/transiciones.php"),
                ("FIFA Training Centre · Transición ofensiva (Jennings)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/transition-to-attacking/transicion-ofensiva-jennings.php"),
                ("The FA · Out of possession: pressing (overview)", "https://www.thefa.com/bootroom/resources/england-dna/how-we-play/out-of-possession"),
            ]
        )

    # Construcción y progresión (salida).
    if has("salida", "build", "build-up", "progresion", "tercer_hombre", "3er_hombre", "juego_posicional", "ocupacion", "carriles"):
        resources.extend(
            [
                (
                    "FIFA Training Centre · 8v8: elaborar por el centro (bajo presión)",
                    "https://www.fifatrainingcentre.com/es/practice/talent-coach-programme/build-and-progress/8v8-team-game-building-up-through-middle-areas.php",
                ),
                ("Spielverlagerung · Pressing traps (análisis)", "https://spielverlagerung.com/2020/04/08/pressing-traps-available-in-a-3-4-3/"),
            ]
        )

    # Juego interior / zona 14.
    if has("zona14", "entre_lineas", "juego_interior"):
        resources.append(
            (
                "FIFA Training Centre · Principios defensivos (aplicables a proteger zona 14)",
                "https://www.fifatrainingcentre.com/es/practice/elite-sessions/out-of-possession/johnson-principios-defensivos.php",
            )
        )

    # ABP / set pieces.
    if has("abp", "corner", "corners", "saque_porteria", "saque_banda", "faltas"):
        resources.extend(
            [
                ("FIFA Training Centre · Set plays (análisis y rutinas)", "https://www.fifatrainingcentre.com/en/game/game-analysis/set-plays/set-play-routines/set-play-routines-home.php"),
                ("FIFA Training Centre · Sesión: set pieces (France U17)", "https://www.fifatrainingcentre.com/en/practice/elite-sessions/youth-national-teams/france-u17-men/wednesday-session-set-pieces.php"),
            ]
        )

    # Porteros.
    if has("porteros", "portero", "gk", "goalkeeper", "1v1"):
        resources.extend(
            [
                ("FIFA · Nuevas sesiones de porteros (ES)", "https://inside.fifa.com/es/news/tres-nuevas-sesiones-para-guardametas-disponibles-centro-entrenamiento-fifa"),
                ("FIFA Training Centre · Sesión porteros (Schalke)", "https://www.fifatrainingcentre.com/en/practice/elite-sessions/clubs-and-academies/german-academies/individual-goalkeeper-training-for-counter-attacking-from-a-corner.php"),
                ("UEFA · Goalkeeper Coaching (PDF)", "https://editorial.uefa.com/resources/0285-190a81f7e091-323e8bfbc968-1000/uefa_goalkeeper_coaching_en.pdf"),
            ]
        )

    # Metodología (PPP / constraints / didáctica).
    if has("metodologia", "didactica", "ppp", "constraints", "constraints-led", "no_lineal", "nonlinear"):
        resources.extend(
            [
                ("The FA · Cómo usar constraints en tu sesión", "https://www.thefa.com/bootroom/resources/coaching/how-to-use-constraints-in-your-coaching-session"),
                ("US Soccer · PPP Methodology (PDF)", "https://www.nmysa.net/wp-content/uploads/sites/206/2023/08/Play-Practice-Play-Methodology1.pdf"),
                ("US Soccer · Coaches session plans (resource hub)", "https://www.ussoccer.com/soccer-forward/resource-hub/coaches-session-plans"),
                ("CONMEBOL · Manual orientador (ES, PDF)", "https://www.conmebol.com/wp-content/uploads/documents/manual-orientador-esp.pdf"),
            ]
        )

    # Siempre: búsqueda guiada (para "todo lo que salga" sin llenar de spam).
    q_bits = [str(item.title or "").strip()]
    q_bits.extend([t for t in (item.tags or [])[:4] if str(t or "").strip()])
    query = " ".join([x for x in q_bits if x]).strip()
    if query:
        yt_q = query.replace(" ", "+")
        resources.extend(
            [
                ("YouTube · búsqueda del tema", f"https://www.youtube.com/results?search_query={yt_q}"),
                ("Google · búsqueda del tema", f"https://www.google.com/search?q={yt_q}"),
                ("Google · FIFA Training Centre (site)", f"https://www.google.com/search?q=site%3Afifatrainingcentre.com+{yt_q}"),
                ("Google · The FA Boot Room (site)", f"https://www.google.com/search?q=site%3Athefa.com%2Fbootroom+{yt_q}"),
                ("Google · UEFA (site)", f"https://www.google.com/search?q=site%3Auefa.com+{yt_q}"),
            ]
        )

    # Fallback mínimo (si nada encaja, pero siempre damos 1 puerta de entrada).
    if not resources:
        resources.append(
            ("FIFA Training Centre · Principios defensivos (entrada recomendada)", "https://www.fifatrainingcentre.com/es/practice/elite-sessions/out-of-possession/johnson-principios-defensivos.php")
        )

    # Dedupe preservando orden.
    seen = set()
    out: list[tuple[str, str]] = []
    for label, url in resources:
        key = (str(label).strip(), str(url).strip())
        if key in seen:
            continue
        seen.add(key)
        out.append((key[0], key[1]))
        if len(out) >= 10:
            break
    return out


def _seed_lesson_with_default_resources_step(item: SeedLesson) -> SeedLesson:
    if _seed_lesson_has_resources_step(item):
        return item

    links = _external_resources_for_seed_lesson(item)
    body = "\n".join([f"- {label}: {url}" for label, url in links]).strip() or "—"
    steps = list(item.steps or [])
    steps.append(
        {
            "type": AcademyLessonStep.TYPE_TEXT,
            "title": "Recursos (para profundizar)",
            "body": body,
            "payload": {"seed_resources": True},
        }
    )
    return SeedLesson(
        title=item.title,
        summary=item.summary,
        min_category=item.min_category,
        max_category=item.max_category,
        tags=item.tags,
        steps=steps,
    )


def _mk_guide(
    *,
    title: str,
    summary: str,
    min_category: str,
    max_category: str,
    tags: list[str],
    objective: str,
    rules: list[str],
    roles: list[str] | None = None,
    triggers: list[str] | None = None,
    checklist: list[str] | None = None,
    errors: list[str] | None = None,
    scene_hint: str = "",
    measure: list[str] | None = None,
) -> SeedLesson:
    def _bullets(items: list[str]) -> str:
        clean = [str(x or "").strip() for x in (items or []) if str(x or "").strip()]
        if not clean:
            return ""
        return "- " + "\n- ".join(clean)

    steps = [
        {"type": AcademyLessonStep.TYPE_TEXT, "title": "Objetivo (1 frase)", "body": str(objective or "").strip()},
        {"type": AcademyLessonStep.TYPE_TEXT, "title": "3 reglas simples", "body": _bullets((rules or [])[:6]) or "—"},
    ]
    if roles:
        steps.append({"type": AcademyLessonStep.TYPE_TEXT, "title": "Roles (quién hace qué)", "body": _bullets(roles) or "—"})
    if triggers:
        steps.append({"type": AcademyLessonStep.TYPE_TEXT, "title": "Triggers (cuándo sí/cuándo no)", "body": _bullets(triggers) or "—"})
    if checklist:
        steps.append({"type": AcademyLessonStep.TYPE_TEXT, "title": "Checklist (10 segundos)", "body": _bullets(checklist) or "—"})
    if errors:
        steps.append({"type": AcademyLessonStep.TYPE_TEXT, "title": "Errores típicos + corrección", "body": _bullets(errors) or "—"})
    if scene_hint:
        steps.append(
            {
                "type": AcademyLessonStep.TYPE_REPLAY_2D,
                "title": "Pizarra 2D (escena tipo)",
                "body": "Usa esta escena como referencia visual rápida (15–30s).",
                "payload": {"hint": str(scene_hint).strip()[:600]},
            }
        )
    if measure:
        steps.append({"type": AcademyLessonStep.TYPE_TEXT, "title": "Cómo medirlo (registro de acciones)", "body": _bullets(measure) or "—"})
    return SeedLesson(title=title, summary=summary, min_category=min_category, max_category=max_category, tags=tags, steps=steps)


def _mk_game_encyclopedia_core() -> list[SeedLesson]:
    """
    Enciclopedia del juego (núcleo): guías prácticas aplicables a cualquier club.
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Ataque · Ocupar carriles (ancho, dentro, profundidad)",
            summary="Guía práctica para no “amontonarse”: ocupar espacios y crear líneas de pase estables.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["ataque", "ocupacion", "carriles", "progresion"],
            objective="Tener siempre 2–3 líneas de pase (corto/dentro/espalda) sin perder equilibrio defensivo.",
            rules=[
                "Si el balón está por dentro → alguien da AMPLITUD (línea).",
                "Si el balón está por fuera → alguien ocupa INTERIOR (entre líneas).",
                "Siempre 1 amenaza PROFUNDIDAD (espalda) y 1 jugador de SEGURIDAD (por detrás).",
            ],
            roles=[
                "Lado fuerte: apoyo + interior + amplitud.",
                "Lado débil: amplitud lista + llegada al área.",
                "Seguridad: pivote/central para reiniciar y evitar transición.",
            ],
            checklist=["¿Tengo ancho? ¿Tengo dentro? ¿Tengo espalda?", "¿Hay alguien por detrás para evitar contra?"],
            errors=[
                "Todos al balón → “UNO DA ANCHO, UNO VA A ESPALDA”.",
                "Extremo se mete dentro sin ancho → “ABRE PARA ENTRAR”.",
                "Nadie de seguridad → “SIEMPRE UNO POR DETRÁS”.",
            ],
            scene_hint="Escena: balón por dentro. Marca 5 carriles. Muestra ocupación: extremo abierto, interior entre líneas, 9 amenaza espalda, pivote de seguridad.",
            measure=["Pases progresivos tras ocupación correcta.", "Pérdidas en salida por falta de apoyos (deberían bajar)."],
        ),
        _mk_guide(
            title="Ataque · Superioridades (numérica, posicional, cualitativa)",
            summary="Cómo crear ventaja de forma consciente (no por casualidad).",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["ataque", "superioridad", "decision"],
            objective="Crear una ventaja clara antes de acelerar (si no hay ventaja, se prepara).",
            rules=[
                "Numérica: crea 2v1 (apoyo) y juega rápido.",
                "Posicional: coloca a alguien entre líneas (a la espalda del medio).",
                "Cualitativa: aísla un 1v1 favorable (overload→isolate).",
            ],
            triggers=[
                "Si atraes 2 rivales al balón → hay hombre libre (jugarlo).",
                "Si el interior recibe entre líneas y gira → acelerar.",
                "Si el extremo está 1v1 con espacio → aislar y atacar.",
            ],
            errors=["Correr sin ventaja → “PRIMERO VENTAJA, LUEGO VELOCIDAD”.", "Buscar 1v1 sin espacio → “AISLA ANTES”."],
            scene_hint="Escena: overload en banda (3v2) para atraer; cambio al lado débil para 1v1 del extremo.",
            measure=["Cambios de orientación que terminan en tiro/centro.", "Pérdidas por forzar 1v1 sin ventaja (deberían bajar)."],
        ),
        _mk_guide(
            title="Defensa · Bloque bajo (proteger área y centro)",
            summary="Cómo defender cerca de tu portería sin hundirte mal: prioridades, distancias y salidas.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["defensa", "bloque_bajo", "area", "centro"],
            objective="Negar remate limpio en zona caliente y controlar el rechace.",
            rules=["Centro primero: pasillo interior protegido.", "Área: 1º palo + penalti + 2º palo (roles).", "Rechace: 1 jugador SIEMPRE."],
            roles=["1º defensor: temporiza y orienta fuera.", "Defensas: ganan posición y atacan balón.", "Mediocentro: rechace + primer pase."],
            checklist=["¿Estamos juntos (distancias cortas)?", "¿Quién protege el rechace?", "¿Defendemos el centro o perseguimos sombras?"],
            errors=["Todos hundidos → “SAL UN PASO, PROTEGE ZONA CALIENTE”.", "Nadie al rechace → “RECHACE ES NUESTRO”.", "Salto sin cobertura → “TEMPORIZA”.",],
            scene_hint="Escena: rival en banda para centrar. Dibuja 3 zonas y 1 jugador al rechace. Muestra salida tras despeje a banda.",
            measure=["Centros defendidos sin remate limpio.", "Segundas jugadas ganadas tras despeje."],
        ),
        _mk_guide(
            title="Defensa · Bloque alto (presión tras pase atrás)",
            summary="Presionar arriba sin suicidarse: triggers, cierres y coberturas.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["defensa", "bloque_alto", "presion", "triggers"],
            objective="Robar arriba o forzar balón largo (y ganar la segunda jugada).",
            rules=["Trigger: pase atrás al central/portero.", "1º orienta a banda; 2º cierra interior; 3º equilibra cambio.", "La línea acompaña (si no, temporiza)."],
            triggers=["Pase atrás lento.", "Portero perfil incómodo.", "Control largo del central."],
            checklist=["¿Interior cerrado?", "¿Cobertura si me superan?", "¿Listos para segunda jugada si juegan largo?"],
            errors=["Presión sin línea → “SI NO ACOMPAÑAS, TEMPORIZO”.", "Saltos descoordinados → “SOLO UNO SALTA; LOS DEMÁS CIERRAN”.",],
            scene_hint="Escena: pase atrás al portero. 9 orienta a banda, extremo salta a lateral, interior tapa dentro, central acompaña línea.",
            measure=["Recuperaciones altas (tercio ataque).", "Balones largos forzados + segundas jugadas ganadas."],
        ),
        _mk_guide(
            title="Transición · Rest defense (cómo no morir tras atacar)",
            summary="Guía práctica para estar protegidos mientras atacas: coberturas, distancias y quién se queda.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["transicion", "rest_defense", "equilibrio"],
            objective="Reducir contraataques peligrosos sin quitar gente al ataque.",
            rules=["Siempre 2–3 por detrás del balón (según riesgo).", "Cobertura diagonal: si lateral sube, alguien cubre su espalda.", "Lado débil cierra para interceptar cambios."],
            roles=["Pivote: ancla.", "Central libre: cobertura + segunda jugada.", "Lateral lado débil: más conservador si el lado fuerte está muy alto."],
            checklist=["¿Quién corta primera salida del rival?", "¿Quién protege espalda del lateral alto?", "¿Estamos preparados para pérdida en banda?"],
            errors=["Todos por delante del balón → “DOS POR DETRÁS SIEMPRE”.", "Pivote se mete demasiado → “ANCLA”.",],
            scene_hint="Escena: ataque por banda. Marca 3 de seguridad (pivote+2) y cobertura del lateral opuesto.",
            measure=["Contraataques recibidos tras pérdida (bajan).", "Recuperaciones en 5–8s tras pérdida (suben)."],
        ),
    ]


def _mk_game_encyclopedia_goalkeepers() -> list[SeedLesson]:
    """
    Enciclopedia del juego: Porteros (guías prácticas).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Porteros · Colocación (ángulo, distancia, timing)",
            summary="Guía práctica para colocarse: reducir ángulo sin regalar el palo corto ni el pase atrás.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["porteros", "portero", "gk", "colocacion"],
            objective="Estar en la mejor posición para parar y para reaccionar al siguiente evento (rebote/2º balón).",
            rules=[
                "Primero ángulo: entre balón y centro de portería.",
                "Luego distancia: ni pegado a línea ni fuera sin control.",
                "Último paso antes del tiro: equilibrio (listo para caer).",
            ],
            checklist=[
                "¿Veo el balón? ¿Tengo equilibrio?",
                "¿Estoy tapando el palo corto sin perder el largo?",
                "¿Qué pasa si hay rebote (dónde caigo)?",
            ],
            errors=[
                "Quedarse en línea siempre → “DA UN PASO, GANA ÁNGULO”.",
                "Salir demasiado sin control → “SALE SI PUEDES LLEGAR”.",
                "Pierna/cuerpo mal orientados → “CADERA HACIA BALÓN, LISTO”.",
            ],
            scene_hint="Escena: tiro desde banda vs tiro frontal. Dibuja 2 colocaciones distintas (ángulo) y el ‘último paso’ antes del golpeo.",
            measure=[
                "Tiros a puerta recibidos vs goles encajados (eficiencia).",
                "Rechaces concedidos (deberían bajar al blocar mejor).",
            ],
        ),
        _mk_guide(
            title="Porteros · 1v1 (salida, paciencia y achique)",
            summary="Cómo ganar 1v1: cuándo salir, cuándo aguantar y cómo orientar al atacante.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["porteros", "gk", "1v1", "defensa_area"],
            objective="Reducir opciones del atacante sin ser superado con un toque.",
            rules=[
                "Si estás a tiempo: achica en línea balón‑portería.",
                "Si no llegas: aguanta (no te tires pronto).",
                "Cierra el centro y obliga a decidir (tiro/pase).",
            ],
            triggers=[
                "Balón dividido/adelantado → salida agresiva.",
                "Atacante con control limpio y ventaja → aguantar y temporizar.",
            ],
            checklist=[
                "¿Llego primero? Si sí: voy fuerte y seguro.",
                "Si no: ¿puedo aguantar y ganar tiempo para mis defensas?",
            ],
            errors=[
                "Tirarse pronto → “AGUANTA, NO TE REGALAS”.",
                "Salir tarde a medias → “SI SALES, SALES”.",
            ],
            scene_hint="Escena: pase a la espalda. Variante A: portero llega primero (sale). Variante B: llega tarde (aguanta y orienta al atacante).",
            measure=[
                "1v1 concedidos vs paradas/errores (tendencia).",
                "Goles tras pase atrás o balón raso lateral (lectura 1v1).",
            ],
        ),
        _mk_guide(
            title="Porteros · Centros (decidir: salir o quedarse)",
            summary="Guía práctica para centros: lectura del vuelo, tráfico y coordinación con defensas.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["porteros", "gk", "centros", "area"],
            objective="Evitar remate limpio y dominar el área sin chocar ni dudar.",
            rules=[
                "Si puedes coger: ve con decisión (mano arriba) y bloquea.",
                "Si no puedes coger: despeja (puños) a banda/seguridad.",
                "Si no llegas: quédate y prepara el segundo acto (parada/2º balón).",
            ],
            roles=[
                "Portero: manda (“¡MÍA!”) y decide.",
                "Defensas: protegen zona caliente y bloquean rematador (sin estorbar al portero).",
                "Rechace: 1 jugador siempre fuera del área pequeña.",
            ],
            checklist=[
                "¿Llego a coger? ¿Hay tráfico?",
                "¿Dónde despejo si no puedo blocar?",
                "¿Quién va al rechace?",
            ],
            errors=[
                "Dudar y quedarse a medias → “DECIDE ANTES: MÍA O QUÉDATE”.",
                "Despejar al centro → “PUÑOS A BANDA”.",
            ],
            scene_hint="Escena: centro al 2º palo con tráfico. Marca decisión: blocaje vs puños y el jugador de rechace.",
            measure=[
                "Centros recibidos vs remates limpios concedidos.",
                "Goles de segunda jugada tras centros (deberían bajar).",
            ],
        ),
        _mk_guide(
            title="Porteros · Juego de pies (salida corta vs directa)",
            summary="Decidir rápido para ayudar al equipo: cuándo asegurar y cuándo progresar.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["porteros", "gk", "salida", "pase"],
            objective="Ser una solución, no un riesgo: elegir el pase que mantiene ventaja.",
            rules=[
                "Si el rival presiona: primer objetivo = seguridad (no regalar pérdida).",
                "Si hay hombre libre: jugar al lado débil o al pivote perfilado.",
                "Si no hay salida: directo a zona/duelo preparado (equipo listo para 2ª jugada).",
            ],
            triggers=[
                "Rival salta a central → portero activa 3er hombre (central‑portero‑pivote).",
                "Rival cierra por dentro → salida a banda o cambio al lado débil.",
            ],
            checklist=[
                "¿Tengo pase seguro? (siempre)",
                "¿Quién es el hombre libre?",
                "Si voy directo: ¿quién gana 2ª jugada?",
            ],
            errors=[
                "Pase interior sin perfil → “NO JUEGUES A UN COMPAÑERO DE ESPALDAS PRESIONADO”.",
                "Directo sin preparación → “SI VAS LARGO, PREPARA LA CAÍDA”.",
            ],
            scene_hint="Escena: saque corto con presión 2 delanteros. Dibuja salida por pivote vs salida a banda vs directo preparado.",
            measure=[
                "Pérdidas en salida (deberían bajar).",
                "Progresiones tras pase del portero (suben).",
            ],
        ),
        _mk_guide(
            title="Porteros · ABP (córners y faltas): mando y organización",
            summary="Qué debe ordenar el portero en ABP: zonas, marcas y quién va al rechace.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["porteros", "gk", "abp", "organizacion"],
            objective="Eliminar dudas: que todos tengan rol y que el portero mande la defensa del área.",
            rules=[
                "Define 3 zonas (1º/centro/2º palo) + 1 rechace.",
                "Nombra 2 marcas al hombre (mejores rematadores rivales).",
                "Ordena salida: despeje a banda y líneas para segunda jugada.",
            ],
            checklist=[
                "¿Quién ataca balón? ¿Quién cubre segundo?",
                "¿Quién está al rechace?",
                "¿Dónde despejamos si no blocamos?",
            ],
            errors=[
                "Silencio en ABP → “EL PORTERO MANDA: MÍA/NO MÍA”.",
                "Nadie al rechace → “1 FUERA SIEMPRE”.",
            ],
            scene_hint="Escena: córner en contra. Marca zonas, 2 marcas al hombre y 1 rechace. Añade ‘despeje a banda’ como salida.",
            measure=[
                "Goles/ocasiones concedidas en ABP (bajan).",
                "Segundas jugadas ganadas en ABP (suben).",
            ],
        ),
    ]


def _mk_game_encyclopedia_set_pieces_extra() -> list[SeedLesson]:
    """
    Enciclopedia del juego: ABP restante (penaltis, saques, faltas frontales).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="ABP · Penalti a favor (rutina + roles de rechace)",
            summary="Guía práctica para lanzar penaltis con rutina estable y equipo preparado al rechace.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "penalti", "ataque"],
            objective="Aumentar consistencia del lanzador y evitar contraataques tras rebote.",
            rules=[
                "Rutina fija (misma respiración, mismos pasos).",
                "Decisión antes de correr (no cambiar en el último paso).",
                "Rechace: 2 roles claros (zona frontal + segunda jugada) y 1 seguridad.",
            ],
            roles=[
                "Lanzador: rutina + decisión.",
                "Rechace 1: entra frontal al punto de penalti.",
                "Rechace 2: entra a segundo balón (banda/segunda jugada).",
                "Seguridad: evita contra y recoge despeje.",
            ],
            checklist=["¿Rutina lista?", "¿Quién entra al rechace?", "¿Quién se queda de seguridad?"],
            errors=["Cambiar decisión tarde → “DECIDE ANTES”.", "Todos entran al rechace → “UNO DE SEGURIDAD”."],
            scene_hint="Escena: penalti a favor. Marca 2 rutas de rechace y 1 jugador de seguridad por detrás.",
            measure=["Penaltis convertidos vs fallados.", "Contraataques tras penalti (deberían bajar)."],
        ),
        _mk_guide(
            title="ABP · Penalti en contra (portero + rechace)",
            summary="Guía práctica para defender penaltis: lectura del lanzador y roles para el rechace.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "penalti", "defensa", "porteros"],
            objective="Maximizar probabilidad de parada sin desordenar el equipo en el rebote.",
            rules=[
                "Portero: rutina propia (respira, fija, espera).",
                "Defensas: listos para rechace (sin invadir antes).",
                "Tras rebote: despeje a banda/seguridad y reorganizar.",
            ],
            roles=["Portero: decide timing.", "2 rechaces: uno frontal, uno a lado débil.", "1 seguridad: evita segunda jugada peligrosa."],
            checklist=["¿Quién rechaza?", "¿Dónde despejamos?", "¿Quién protege la transición?"],
            errors=["Todos miran el balón y nadie al rechace → “RECHACE ES NUESTRO”.", "Despeje al centro → “A BANDA”."],
            scene_hint="Escena: penalti en contra con rebote. Marca despeje a banda y salida del bloque.",
            measure=["Rechaces ganados tras penalti.", "Segundas jugadas concedidas tras penalti (bajan)."],
        ),
        _mk_guide(
            title="ABP · Saque de portería a favor (salida corta o directa)",
            summary="Guía práctica para sacar de portería: decidir según presión rival sin regalar pérdidas.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "saque_porteria", "salida", "ataque"],
            objective="Progresar con ventaja o, si no se puede, jugar directo con segunda jugada preparada.",
            rules=[
                "Si rival presiona alto: 1 salida clara (pivote o banda) + 1 plan B directo.",
                "Si sales corto: perfiles orientados (no recibir de espaldas presionado).",
                "Si vas largo: prepara la caída (2ª jugada) y rest defense.",
            ],
            checklist=["¿Dónde está el hombre libre?", "¿Hay perfil para recibir?", "Si voy largo, ¿quién gana la caída?"],
            errors=["Corto sin perfil → “NO A UN COMPAÑERO DE ESPALDAS”.", "Largo sin caída → “PREPARA LA CAÍDA”."],
            scene_hint="Escena: rival presiona 3‑2. Dibuja salida por pivote vs salida a lateral vs directo con 2ª jugada.",
            measure=["Pérdidas en salida (bajan).", "Progresiones tras saque de portería (suben)."],
        ),
        _mk_guide(
            title="ABP · Saque de portería en contra (presión y cierres)",
            summary="Guía práctica para presionar el saque rival: orientar, cerrar interior y estar listos para balón largo.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "saque_porteria", "defensa", "presion"],
            objective="Forzar pase incómodo o balón largo y ganar segunda jugada.",
            rules=[
                "Cierra interior primero (pivote rival).",
                "Orienta a banda/central débil.",
                "Si van largo: línea preparada para duelo + segunda jugada.",
            ],
            triggers=["Portero con perfil incómodo.", "Central de espaldas.", "Pase flotado."],
            checklist=["¿Interior cerrado?", "¿Quién salta al lateral?", "¿Quién gana la 2ª jugada si van largo?"],
            errors=["Presión sin segunda jugada → “SI VAN LARGO, LA CAÍDA ES NUESTRA”.", "Saltos sin cierres → “PRIMERO CIERRO, LUEGO SALTO”."],
            scene_hint="Escena: saque rival. Dibuja 9 orienta, extremos saltan, interiores cierran pivote y centrales listos para duelo aéreo.",
            measure=["Recuperaciones altas tras saque rival.", "Segundas jugadas ganadas tras balón largo rival."],
        ),
        _mk_guide(
            title="ABP · Saque de centro (2 planes simples)",
            summary="Guía práctica para iniciar: plan seguro y plan agresivo, sin regalar pérdidas.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "saque_centro", "ataque"],
            objective="Empezar con control o atacar ventaja preparada (según momento).",
            rules=[
                "Plan seguro: atrás → lado fuerte → progresar con apoyos.",
                "Plan agresivo: directo a zona preparada + 2ª jugada.",
                "Tras saque: rest defense (no partirse).",
            ],
            checklist=["¿Qué plan hacemos (seguro/agresivo)?", "¿Quién fija? ¿Quién ataca 2ª jugada?", "¿Quién queda de seguridad?"],
            errors=["Directo sin estructura → “SI VAMOS DIRECTO, HAY CAÍDA”.", "Todos corren hacia delante → “SEGURIDAD”."],
            scene_hint="Escena: saque de centro. Variante A: atrás y salida por banda. Variante B: balón directo a zona con 2ª jugada.",
            measure=["Pérdidas tras saque de centro (bajan).", "Llegadas al último tercio tras saque (suben)."],
        ),
        _mk_guide(
            title="ABP · Falta frontal directa (decisión: tiro, pase, centro)",
            summary="Guía práctica para faltas frontales: elegir opción según barrera, distancia y superioridad.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["abp", "falta_frontal", "ataque"],
            objective="Elegir la opción con mayor probabilidad (no tirar por tirar).",
            rules=[
                "Si hay tiro claro: rutina y golpeo (no cambiar tarde).",
                "Si no hay tiro: pase corto para cambiar ángulo o centro lateral.",
                "Siempre 1–2 al rechace + 1 seguridad.",
            ],
            triggers=["Barrera mal colocada.", "Portero tapado.", "Superioridad clara en banda para centro."],
            checklist=["¿Tiro real o engaño?", "¿Quién al rechace?", "¿Quién se queda de seguridad?"],
            errors=["Tiro sin probabilidad → “SI NO ES CLARO, CAMBIA ÁNGULO”.", "Sin rechace → “RECHACE”."],
            scene_hint="Escena: falta frontal. Variante tiro vs pase corto a banda para centro. Marca rechace y seguridad.",
            measure=["Tiros a puerta en faltas.", "Segundas jugadas ganadas tras faltas."],
        ),
    ]


def _mk_game_encyclopedia_positions() -> list[SeedLesson]:
    """
    Enciclopedia del juego: guías por posiciones (qué mirar / qué hacer / errores típicos).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Posición · Central (salida, cobertura y duelos)",
            summary="Guía práctica para centrales: salida limpia, coberturas y cuándo defender hacia delante.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "central", "defensa", "salida", "duelos"],
            objective="Dar seguridad al equipo: iniciar juego sin regalar pérdidas y proteger espalda/área.",
            rules=[
                "Antes de recibir: escaneo (hombre libre y presión).",
                "Si el rival aprieta: primer pase seguro + opción de 3er hombre.",
                "Sin balón: perfil para correr hacia atrás y proteger la espalda.",
            ],
            triggers=[
                "Si el 9 rival recibe de espaldas sin apoyo → saltar con cobertura.",
                "Si el balón está en banda y hay centro → prioriza zona caliente + rechace.",
            ],
            checklist=[
                "¿Tengo pase seguro? (pivote/lateral/portero)",
                "¿Quién cubre mi espalda si salto?",
                "¿Dónde está el 9 rival?",
            ],
            errors=[
                "Conducir sin ventaja → “FIJA Y SUELTA”.",
                "Saltar sin cobertura → “SI NO HAY COBERTURA, TEMPORIZA”.",
                "Despejar al centro → “A BANDA/SEGURIDAD”.",
            ],
            scene_hint="Escena: central recibe con presión. Variante A: pase al pivote perfilado. Variante B: pared con portero y salida al lateral. En defensa: central salta al 9 con mediocentro cubriendo.",
            measure=["Pérdidas en salida del central (bajan).", "Duelos defensivos ganados.", "Centros/remates evitados en zona caliente."],
        ),
        _mk_guide(
            title="Posición · Lateral (altura, 1v1 y cierres)",
            summary="Guía práctica para laterales: cuándo subir, cuándo fijar y cómo cerrar dentro sin regalar banda.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "lateral", "defensa", "ataque", "amplitud"],
            objective="Dar amplitud y profundidad sin romper el equilibrio defensivo.",
            rules=[
                "Con balón: si extremo viene dentro → tú das amplitud/altura.",
                "Sin balón: primero proteger interior, luego orientar a banda.",
                "Si el lateral contrario sube: el lado débil ajusta (rest defense).",
            ],
            triggers=["Si el extremo rival recibe pegado a línea → presión orientada fuera.", "Si el balón va a tu espalda → gira y corre (no mires)."],
            checklist=["¿Tengo cobertura (central/pivote)?", "¿Mi extremo me ayuda a cerrar dentro?", "¿Qué pasa si pierdo el balón arriba?"],
            errors=["Subir los dos laterales a la vez sin seguridad → “UNO SE QUEDA”.", "Defender mirando balón → “BALÓN‑HOMBRE‑PORTERÍA”."],
            scene_hint="Escena: ataque por banda (lateral alto + extremo dentro). Luego pérdida y lateral debe replegar con cobertura del central/pivote.",
            measure=["Centros generados y centros defendidos.", "1v1 defensivos ganados.", "Contraataques por tu banda (bajan)."],
        ),
        _mk_guide(
            title="Posición · Pivote (ancla, perfil y primer pase)",
            summary="Guía práctica para mediocentro: ser salida, proteger transiciones y ordenar al equipo.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "pivote", "salida", "transicion", "equilibrio"],
            objective="Ser el estabilizador: conectar líneas y cortar transiciones rivales.",
            rules=[
                "Perfilado siempre que puedas (ver campo).",
                "Si estás presionado: juega a 1–2 toques (apoyo/3er hombre).",
                "Tras pérdida: primera puerta que cierro es el pase interior/contraataque.",
            ],
            triggers=["Si recibes entre dos rivales → apoyo inmediato (no girar).", "Si hay pérdida cerca → contra‑presión; si lejos → repliegue y temporiza."],
            checklist=["¿Estoy perfilado?", "¿Dónde está el hombre libre?", "¿Quién protege mi espalda si salto?"],
            errors=["Recibir de espaldas presionado → “PERFIL O APOYO”.", "Ir al área y dejar vacío el ancla → “QUÉDATE COMO SEGURIDAD”."],
            scene_hint="Escena: central→pivote bajo presión. Variante: descarga a central y 3er hombre a interior. Tras pérdida: pivote corta pase interior.",
            measure=["Pases progresivos del pivote.", "Intercepciones/robos en transición.", "Pérdidas del pivote (bajan)."],
        ),
        _mk_guide(
            title="Posición · Interior/8 (entre líneas, giro y último pase)",
            summary="Guía práctica para interiores: recibir entre líneas, girar con criterio y dar el pase que rompe.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "interior", "ataque", "entre_lineas", "ultimo_pase"],
            objective="Recibir con ventaja y acelerar cuando toca (no antes).",
            rules=[
                "Antes de recibir: escaneo y perfil para girar si hay espacio.",
                "Si no hay giro: apoyo + 3er hombre.",
                "En zona 14: primero asegurar ventaja, luego filtrar/tiro.",
            ],
            triggers=["Si recibes de cara y el 6 rival está lejos → girar y conducir.", "Si el rival salta → jugar a la espalda (tercer hombre)."],
            checklist=["¿Puedo girar?", "¿Dónde está el 9 y el extremo del lado débil?", "¿Hay pase a la espalda o mejor pausa?"],
            errors=["Forzar pase imposible → “FIJA Y SUELTA, NO REGALAS”.", "Conducir hacia presión → “SAL DEL FOCO”."],
            scene_hint="Escena: interior recibe entre líneas. Variante A: gira y filtra. Variante B: 3er hombre al extremo/lateral profundo.",
            measure=["Pases clave / asistencias.", "Pérdidas en zona central (bajan).", "Progresiones (a tercio ataque) creadas."],
        ),
        _mk_guide(
            title="Posición · Extremo (1v1, amplitud y último gesto)",
            summary="Guía práctica para extremos: aislar 1v1, decidir centro/tiro/pase atrás y ayudar a presionar.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "extremo", "1v1", "centros", "finalizacion"],
            objective="Crear peligro constante sin perder balones tontos (1v1 con ventaja).",
            rules=[
                "Si hay 1v1 con espacio: atacar (cambio ritmo).",
                "Si atraes 2: suelta al hombre libre (pase atrás/2º palo).",
                "Sin balón: orientar presión para que el rival no juegue dentro.",
            ],
            triggers=["Si el lateral rival está solo → 1v1.", "Si llega el 2º defensor → descarga rápida."],
            checklist=["¿Tengo ventaja real (espacio)?", "¿Dónde está el centro más peligroso (raso atrás/2º palo)?", "¿Quién llega al área?"],
            errors=["Regate sin espacio → “AISLA ANTES”.", "Centro sin mirar → “MIRA 1 SEGUNDO: ¿1º/2º/ATRÁS?”."],
            scene_hint="Escena: extremo aislado en banda. Variante A: regate y centro raso atrás. Variante B: atrae y cambio al lado débil.",
            measure=["Regates con éxito (en ventaja).", "Centros útiles (tiro/ocasión tras centro).", "Pérdidas del extremo (bajan)."],
        ),
        _mk_guide(
            title="Posición · Delantero/9 (fijar, desmarque y presión)",
            summary="Guía práctica para el 9: fijar centrales, atacar espacios y ser el primer defensor inteligente.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["posicion", "delantero", "9", "presion", "finalizacion"],
            objective="Generar ventajas para el equipo: fijar, descargar y atacar área con intención.",
            rules=[
                "Si viene el balón a pie: fija y descarga (tercer hombre).",
                "Si el balón está en banda: ataca primer palo o punto penalti según centro.",
                "Sin balón: orientar presión para cerrar pase interior.",
            ],
            triggers=["Central recibe de espaldas → saltar a presión.", "Si el lateral rival recibe abierto → orientar y guiar a banda."],
            checklist=["¿Puedo fijar a dos centrales?", "¿Qué centro viene (raso atrás/primer/segundo palo)?", "¿Estoy activando presión con trigger o corriendo sin sentido?"],
            errors=["Bajar siempre al balón → “FIJA Y ATACA ESPALDA”.", "Presión recta abriendo interior → “CARRERA CURVA, CIERRA DENTRO”.",],
            scene_hint="Escena: 9 fija y descarga a interior, luego ataca área en centro lateral. En defensa: 9 orienta presión tras pase atrás.",
            measure=["Tiros y remates del 9.", "Asistencias/descargas que acaban en progresión.", "Recuperaciones altas forzadas por presión."],
        ),
    ]


def _mk_game_encyclopedia_formats() -> list[SeedLesson]:
    """
    Enciclopedia del juego: guías por formato (qué cambia en distancias, reglas y foco).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Formato · 5v5 (Baby/Preben): muchos duelos y decisiones simples",
            summary="Qué priorizar en 5v5: diversión, 1v1, conducción y finalización cerca.",
            min_category=L.CATEGORY_BABY,
            max_category=L.CATEGORY_PREBENJAMIN,
            tags=["formato", "5v5", "baby", "prebenjamin"],
            objective="Máxima participación: muchos contactos, muchos intentos y reglas muy simples.",
            rules=["Campos pequeños y porterías cerca.", "Premiar 1v1 y conducción.", "Transición: si la pierdes, corre al balón (3 pasos)."],
            checklist=["¿Hay colas? (si sí, mal)", "¿Muchos contactos por minuto?", "¿Goles/tiros frecuentes?"],
            errors=["Explicar mucho → “JUEGA Y CORRIGE 1 IDEA”.", "Campos enormes → “MÁS PEQUEÑO = MÁS ACCIONES”."],
            scene_hint="Escena: 2 mini‑porterías, 2v2+comodín. Mostrar regla de 3 pasos tras pérdida.",
            measure=["Acciones por minuto (sube).", "Tiros totales (suben)."],
        ),
        _mk_guide(
            title="Formato · 7v7 (Benjamín/Alevín): ocupar ancho y atacar espacios",
            summary="Qué cambia en 7v7: aparece más espacio, el ancho importa y las transiciones son clave.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_ALEVIN,
            tags=["formato", "7v7", "benjamin", "alevin"],
            objective="Enseñar principios: ancho/profundidad, apoyo y presión con cobertura.",
            rules=["Siempre 1 ancho + 1 profundidad.", "Tercer hombre simple para salir de presión.", "Presión orientada a banda (triángulo)."],
            checklist=["¿Tenemos ancho real?", "¿Quién da seguridad por detrás?", "¿Saltamos con cobertura?"],
            errors=["Todos por dentro → “ABRE PARA ENTRAR”.", "Presión 1v1 sin ayudas → “CUBRE DENTRO”.",],
            scene_hint="Escena: 7v7 con 3 carriles. Mostrar ancho (extremos) + profundidad (9) + pivote seguridad.",
            measure=["Pases progresivos.", "Recuperaciones tras presión orientada.", "Pérdidas en salida (bajan)."],
        ),
        _mk_guide(
            title="Formato · 8v8 (Infantil): líneas y distancias (compactar/bascular)",
            summary="En 8v8 se ven mejor las líneas: distancias, basculación y juego entre líneas.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_INFANTIL,
            tags=["formato", "8v8", "infantil"],
            objective="Consolidar: defender el centro, jugar entre líneas y ordenar transiciones.",
            rules=["Distancias cortas sin balón (compactar).", "Bascular juntos al lado del balón.", "Rest defense: 2–3 por detrás al atacar."],
            checklist=["¿Bloque partido? (malo)", "¿Rechace controlado?", "¿Quién corta la transición rival?"],
            errors=["Líneas separadas → “JUNTOS PARA DEFENDER”.", "Nadie al rechace → “RECHACE”."],
            scene_hint="Escena: 8v8 con 3 líneas. Mostrar basculación al lado del balón y el jugador de rechace.",
            measure=["Remates concedidos en zona caliente (bajan).", "Segundas jugadas ganadas."],
        ),
        _mk_guide(
            title="Formato · 11v11 (Cadete+): modelo, detalles y plan A/B/C",
            summary="En 11v11 mandan los detalles: alturas, ocupación, rest defense y ABP completo.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["formato", "11v11", "cadete", "juvenil", "senior"],
            objective="Sostener un modelo de juego: atacar con estructura y defender con coordinación.",
            rules=["Define altura de bloque (alto/medio/bajo) y triggers.", "Ocupación de carriles + lado débil preparado.", "ABP con roles + rechace + salida."],
            checklist=["¿Bloque acompaña la presión?", "¿Tenemos 2–3 de seguridad al atacar?", "¿ABP organizado en ambos sentidos?"],
            errors=["Modelo cambia cada 5 minutos → “POCAS REGLAS, MUY CLARAS”.", "ABP improvisado → “ROLES SIEMPRE”."],
            scene_hint="Escena: 11v11, salida bajo presión + cambio al lado débil; luego pérdida y rest defense.",
            measure=["Recuperaciones altas (si bloque alto).", "Contraataques recibidos (bajan con rest defense).", "Eficacia ABP."],
        ),
    ]


def _mk_game_encyclopedia_units() -> list[SeedLesson]:
    """
    Enciclopedia del juego: guías por líneas/unidades (defensa, medio, ataque).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Unidad · Línea defensiva (altura, coberturas y fuera de juego práctico)",
            summary="Guía práctica para la línea: cuándo subir, cuándo hundir y cómo coordinar coberturas sin regalar la espalda.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["unidad", "defensa", "linea_defensiva", "coberturas"],
            objective="Defender como unidad: compactar, proteger la espalda y evitar remates limpios.",
            rules=[
                "La línea se mueve junta (sube/baja a la vez).",
                "Si el balón está bajo presión: la línea puede subir; si no hay presión: temporiza y protege espalda.",
                "Cobertura: si un central salta, el otro cubre y el lateral ajusta dentro.",
            ],
            triggers=[
                "Pase atrás o control malo del rival → subir y achicar.",
                "Balón conducido sin oposición → no subir; temporizar.",
                "Amenaza a la espalda (desmarque) → orientar cuerpo y correr.",
            ],
            checklist=[
                "¿Hay presión al balón?",
                "¿Estamos alineados (no escalonados sin sentido)?",
                "¿Quién cubre la espalda si alguien salta?",
            ],
            errors=[
                "Uno sube y otro baja → “JUNTOS”.",
                "Lateral se queda abierto y rompe línea → “CIERRA Y ALINEA”.",
                "Central salta sin cobertura → “SI SALTAS, ALGUIEN CUBRE”.",
            ],
            scene_hint="Escena: rival en zona media. Variante A: hay presión → línea sube. Variante B: no hay presión → línea temporiza. Muestra salto de central y cobertura del otro + ajuste de lateral.",
            measure=["Balones a la espalda concedidos (bajan).", "Fuera de juego forzados (suben si procede).", "Remates limpios concedidos (bajan)."],
        ),
        _mk_guide(
            title="Unidad · Línea media (cerrar dentro y ayudar a la presión)",
            summary="Guía práctica del mediocampo: proteger carril central, orientar presión y ser salida tras robo.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["unidad", "medio", "equilibrio", "presion"],
            objective="Ser el equilibrio: negar pases entre líneas y conectar con el ataque tras recuperación.",
            rules=[
                "Dentro primero: el pase entre líneas es prioridad defensiva.",
                "Si el balón va a banda: bascular y cerrar interior (no correr por correr).",
                "Tras robo: primer pase seguro + amenaza (uno corre, uno apoya).",
            ],
            triggers=["Receptor de espaldas → salto con cobertura.", "Pase interior tapado → orientar al rival a banda.", "Recuperación con rival desordenado → acelerar."],
            checklist=["¿Está cerrado el pase interior?", "¿Tengo cobertura detrás?", "Tras robo: ¿primer pase seguro?"],
            errors=["Ir todos al balón → “UNO PRESIONA, OTRO CIERRA”.", "Recuperar y regalarla → “PRIMER PASE SEGURO”."],
            scene_hint="Escena: rival intenta jugar a mediapunta. Mediocentro cierra línea de pase y el interior salta al receptor de espaldas. Tras robo: pase seguro y desmarque de ruptura.",
            measure=["Pases interiores del rival interceptados.", "Recuperaciones en zona media.", "Progresiones tras recuperación (suben)."],
        ),
        _mk_guide(
            title="Unidad · Línea ofensiva (fijar, atacar área y primer defensor)",
            summary="Guía práctica del ataque: roles en área, fijación, desmarques y presión inicial.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["unidad", "ataque", "area", "presion"],
            objective="Generar peligro constante y ayudar a recuperar rápido tras pérdida.",
            rules=[
                "Siempre hay 1 que fija (al central) y 1 que ataca espacio.",
                "En centros: primer palo + punto penalti + raso atrás (al menos 2 llegadas).",
                "Sin balón: orientar la presión para que el rival no juegue dentro.",
            ],
            triggers=["Centro lateral → carreras coordinadas.", "Pase atrás rival → presión orientada.", "Pérdida cerca → 3 pasos de contra‑presión."],
            checklist=["¿Quién fija? ¿Quién ataca espacio?", "¿Quién llega al área? ¿Quién al rechace?", "¿Estamos cerrando el pase interior en presión?"],
            errors=["Todos corren al mismo sitio → “ZONAS DISTINTAS”.", "Nadie al raso atrás → “ALGUIEN ATRÁS”.", "Presión recta → “CARRERA CURVA”."],
            scene_hint="Escena: centro desde banda. Muestra 3 llegadas (1º palo, penalti, raso atrás) y 1 rechace. En defensa: presión del 9 orientando a banda y extremos saltando.",
            measure=["Tiros generados por centros.", "Recuperaciones altas tras presión.", "Segundas jugadas ganadas en ataque."],
        ),
    ]


def _mk_game_encyclopedia_tech_in_context() -> list[SeedLesson]:
    """
    Enciclopedia del juego: técnica en contexto (decisión + ejecución).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Técnica · Perfil corporal (recibir para jugar)",
            summary="Guía práctica: cómo perfilarse para ver el campo y jugar hacia delante.",
            min_category=L.CATEGORY_PREBENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "perfil", "recepcion", "decision"],
            objective="Recibir viendo el mayor número de opciones y reducir pérdidas por presión.",
            rules=["Mira antes (escaneo).", "Cuerpo de lado: una cadera al balón, otra al campo.", "Primer toque hacia ventaja (no al rival)."],
            triggers=["Si hay espacio → primer toque hacia delante.", "Si hay presión → primer toque de protección + apoyo."],
            checklist=["¿He mirado antes?", "¿Estoy de lado?", "¿Mi primer toque me saca de la presión?"],
            errors=["Recibir cuadrado → “DE LADO”.", "Primer toque al rival → “TOQUE A VENTAJA”."],
            scene_hint="Escena: pase al mediocentro. Variante A: perfilado y gira. Variante B: de espaldas, descarga y 3er hombre.",
            measure=["Pérdidas por mala recepción (bajan).", "Pases progresivos tras recepción (suben)."],
        ),
        _mk_guide(
            title="Técnica · Control orientado (salir del foco)",
            summary="Guía práctica para controlar orientado: cuándo sí, cuándo no, y hacia dónde.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "control_orientado", "salida_presion"],
            objective="Ganar tiempo/espacio con el primer toque sin perder la pelota.",
            rules=["Control hacia espacio libre (no hacia presión).", "Si no hay espacio: controla para proteger y jugar de cara.", "El control orientado debe conectar con el siguiente pase/acción."],
            triggers=["Rival lejos → control orientado para progresar.", "Rival cerca → control de seguridad y descarga."],
            checklist=["¿Dónde está la presión?", "¿Tengo salida tras el control?", "¿Estoy equilibrado para el segundo toque?"],
            errors=["Control largo sin ventaja → “CORTO Y SEGURO”.", "Control hacia banda cerrada → “SAL DEL FOCO”."],
            scene_hint="Escena: recepción en banda. Mostrar control orientado hacia dentro si está libre, o hacia atrás si hay trampa.",
            measure=["Controles que terminan en progresión.", "Pérdidas tras control (bajan)."],
        ),
        _mk_guide(
            title="Técnica · Pase (peso, superficie y intención)",
            summary="Guía práctica para pasar mejor: qué pase, cuándo y con qué peso.",
            min_category=L.CATEGORY_PREBENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "pase", "intencion"],
            objective="Mantener ventaja: pases que el compañero pueda jugar, no solo recibir.",
            rules=["Pase al pie si quieres continuidad; pase al espacio si quieres acelerar.", "Peso del pase = tiempo del receptor.", "Si el pase no mejora, mejor asegurar y recolocar."],
            triggers=["Hombre libre de cara → pase rápido y fuerte.", "Receptor de espaldas → pase seguro + apoyo cercano."],
            checklist=["¿Mi pase mejora la situación?", "¿El receptor puede jugar de primeras?", "¿Hay riesgo de interceptación?"],
            errors=["Pase flojo → “DA TIEMPO AL RIVAL”.", "Pase sin mirar → “MIRA ANTES”."],
            scene_hint="Escena: pared y 3er hombre. Mostrar diferencia de peso: pase tenso vs flojo y su efecto.",
            measure=["% pases OK (sube).", "Intercepciones del rival por pases flojos (bajan)."],
        ),
        _mk_guide(
            title="Técnica · Regate/1v1 (aislar y atacar ventaja)",
            summary="Guía práctica para regatear en el momento correcto: aislar, cambio ritmo y salida.",
            min_category=L.CATEGORY_PREBENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "regate", "1v1"],
            objective="Ganar metros o crear superioridad sin regalar pérdidas.",
            rules=["Regatea cuando hay espacio o 1v1 aislado.", "Primer movimiento: amenaza (cambio ritmo).", "Tras superar: cabeza arriba y decisión (pase/tiro/centro)."],
            triggers=["Si llega 2º defensor → descarga.", "Si el defensor está desequilibrado → atacar."],
            checklist=["¿Tengo espacio?", "¿Estoy aislado 1v1?", "¿Qué hago si lo supero?"],
            errors=["Regate rodeado → “AISLA ANTES”.", "Superar y seguir conduciendo sin mirar → “CABEZA ARRIBA”."],
            scene_hint="Escena: extremo aislado vs extremo con 2 ayudas rivales. Mostrar decisión: regate vs descarga.",
            measure=["Regates exitosos en ventaja.", "Pérdidas por regate sin ventaja (bajan)."],
        ),
        _mk_guide(
            title="Técnica · Tiro/remate (selección + ejecución)",
            summary="Guía práctica para finalizar: cuándo tirar, dónde y cómo atacar el balón.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "tiro", "remate", "finalizacion"],
            objective="Aumentar tiros de calidad (no tiros por tirar) y atacar el área con intención.",
            rules=["Tira si hay equilibrio y ángulo; si no, mejora y vuelve a tirar.", "En centros: atacar balón (no esperar).", "Tras tiro: 1 al rechace."],
            triggers=["Portero tapado → tiro fuerte a zona.", "Defensor cerca → tiro rápido (de primeras) o pase."],
            checklist=["¿Estoy equilibrado?", "¿Hay bloqueo/portero tapado?", "¿Quién va al rechace?"],
            errors=["Tirar sin equilibrio → “ASEGURA Y LUEGO”.", "Nadie al rechace → “RECHACE”."],
            scene_hint="Escena: centro raso atrás y remate. Mostrar llegada al área y jugador de rechace.",
            measure=["Tiros totales y a puerta.", "Goles/ocasiones tras rechace."],
        ),
        _mk_guide(
            title="Técnica · Duelos (cuerpo, tiempo y segunda jugada)",
            summary="Guía práctica para ganar duelos: posición, timing y qué pasa después.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["tecnica", "duelos", "segunda_jugada"],
            objective="Ganar el duelo o, como mínimo, que la caída sea nuestra.",
            rules=["Primero posición (entre rival y balón).", "Luego timing (salto/entrada en el momento).", "Después: segunda jugada (caída) preparada."],
            triggers=["Balón dividido → entrar fuerte y seguro.", "Sin ventaja → temporiza y espera apoyo."],
            checklist=["¿Estoy entre rival y balón?", "¿Tengo apoyo para la caída?", "¿Si no gano, dónde cae?"],
            errors=["Ir tarde → “POSICIÓN ANTES”.", "Ganar duelo y desconectar → “CAÍDA”."],
            scene_hint="Escena: duelo aéreo con caída. Marca 1 que salta y 1 que recoge la segunda jugada.",
            measure=["Duelos ganados (%).", "Segundas jugadas ganadas tras duelo."],
        ),
    ]


def _mk_game_encyclopedia_patterns_vs_blocks() -> list[SeedLesson]:
    """
    Enciclopedia del juego: patrones contra bloque alto/medio/bajo.
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Patrones · Atacar bloque alto (salida + lado débil)",
            summary="Superar presión alta: hombre libre, tercer hombre y cambio rápido al lado débil.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["patrones", "ataque", "bloque_alto", "salida"],
            objective="Salir de la presión sin regalar pérdidas y atacar con ventaja el lado débil.",
            rules=[
                "Primero seguridad: 1 salida clara + 1 plan B.",
                "Crea hombre libre: portero/pivote como 3er hombre.",
                "Si atraes presión a un lado: cambio rápido al lado débil.",
            ],
            triggers=[
                "Rival salta a central → activa portero como apoyo.",
                "Rival cierra interior → salida a banda y cambio.",
                "Rival persigue marca → usar tercer hombre.",
            ],
            checklist=["¿Dónde está el hombre libre?", "¿Mi receptor está perfilado?", "¿Tengo preparada la caída si voy directo?"],
            errors=["Jugar interior a un compañero de espaldas presionado → “PERFIL O NO”.", "Conducir sin fijar → “FIJA Y SUELTA”."],
            scene_hint="Escena: rival presiona 3‑1. Variante A: central→portero→pivote. Variante B: salida a lateral y cambio al lado débil.",
            measure=["Pérdidas en salida (bajan).", "Progresiones tras superar 1ª línea (suben)."],
        ),
        _mk_guide(
            title="Patrones · Atacar bloque medio (entre líneas + 3er hombre)",
            summary="Fijar fuera para encontrar dentro y acelerar solo cuando hay giro/ventaja.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["patrones", "ataque", "bloque_medio", "entre_lineas"],
            objective="Encontrar recepciones entre líneas y acelerar solo cuando hay ventaja.",
            rules=[
                "Atrae a banda para abrir carril interior.",
                "Entre líneas: recibir perfilado o jugar a 3er hombre.",
                "Si no hay giro: pausa, reinicia y vuelve a fijar.",
            ],
            triggers=["Interior libre entre líneas → buscarlo.", "Mediocentro rival salta → atacar su espalda.", "Rival bascula tarde → cambio."],
            checklist=["¿Tengo dentro?", "¿Mi receptor puede girar?", "¿Qué hago si me saltan?"],
            errors=["Forzar pase interior sin ventaja → “PRIMERO FIJA”.", "Girar siempre aunque pierdas → “DEPENDE DEL ESPACIO”."],
            scene_hint="Escena: balón en banda, interior entre líneas. Variante: pase al interior y descarga a 3er hombre que rompe.",
            measure=["Recepciones entre líneas con giro.", "Pases clave/tiros tras recibir entre líneas."],
        ),
        _mk_guide(
            title="Patrones · Atacar bloque bajo (centros, raso atrás y paciencia)",
            summary="Mover al rival, llegar a línea de fondo y finalizar con intención.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["patrones", "ataque", "bloque_bajo", "centros", "area"],
            objective="Crear remates de calidad sin desesperarse (evitar tiros sin ventaja).",
            rules=[
                "Mueve al bloque: lado fuerte → lado débil.",
                "Llega a zona de centro: raso atrás es oro.",
                "Área: 2 llegadas + 1 rechace (siempre).",
            ],
            triggers=["Si el rival hunde: atacar raso atrás.", "Si hay 1v1 con espacio: línea de fondo.", "Si zona 14 libre: pase atrás."],
            checklist=["¿He movido al bloque antes de centrar?", "¿Quién 1º palo y penalti?", "¿Quién al rechace?"],
            errors=["Centro sin llegadas → “PRIMERO LLEGA, LUEGO CENTRA”.", "Tiro sin ángulo → “PACIENCIA”."],
            scene_hint="Escena: centro raso atrás. Marca 1º palo, penalti, raso atrás y rechace.",
            measure=["Centros útiles (tiro/ocasión).", "Tiros lejanos sin ventaja (bajan)."],
        ),
    ]


def _mk_game_encyclopedia_area_and_crossing_advanced() -> list[SeedLesson]:
    """
    Enciclopedia del juego: área y centros (avanzado).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Área · Centros: raso atrás (regla de oro)",
            summary="Carreras, zonas y sincronización para rematar raso atrás.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["area", "centros", "ataque", "finalizacion"],
            objective="Generar remate limpio con carreras coordinadas y rechace asegurado.",
            rules=["Una carrera fija 1º palo.", "Una carrera llega a penalti.", "Una carrera llega al raso atrás + 1 al rechace."],
            roles=["1º palo: fija/arrastre.", "Penalti: remate.", "Raso atrás: pase/tiro.", "Rechace: 2ª jugada."],
            checklist=["¿Hay 2 llegadas mínimas?", "¿Alguien al raso atrás?", "¿Quién rechace?"],
            errors=["Todos al 1º palo → “ZONAS DISTINTAS”.", "Nadie al raso atrás → “RASO ATRÁS”."],
            scene_hint="Escena: línea de fondo. Marca 4 roles: 1º palo, penalti, raso atrás, rechace.",
            measure=["Tiros tras centro raso atrás.", "Goles/ocasiones de segunda jugada."],
        ),
        _mk_guide(
            title="Área · Centros: 2º palo (castigar lado débil)",
            summary="Ocupación del lado débil y timing del centro tenso al 2º palo.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["area", "centros", "lado_debil"],
            objective="Aprovechar el lado débil del rival (bascula tarde) para rematar.",
            rules=["2º palo ocupado ANTES del centro.", "Centro tenso (no globo fácil).", "Rechace siempre."],
            checklist=["¿Está ocupado el 2º palo?", "¿Centro con tensión?", "¿Quién rechace?"],
            errors=["Llegar tarde al 2º palo → “PREPARA ANTES”.", "Centro flojo → “TENSO”."],
            scene_hint="Escena: ataque por banda; lado débil llega al 2º palo. Marca llegada + centro tenso.",
            measure=["Remates en 2º palo.", "Segundas jugadas tras centro."],
        ),
        _mk_guide(
            title="Área · Finalización: de primeras (primer toque)",
            summary="Preparación, perfil y atacar el balón para rematar de primeras.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["finalizacion", "area", "tiro", "primer_toque"],
            objective="Aumentar remates de calidad y reducir controles innecesarios en área.",
            rules=["Micro‑pasos antes del pase/centro.", "Cuerpo listo para contacto.", "Atacar balón (no esperar)."],
            checklist=["¿Estoy en equilibrio?", "¿Veo balón/portería?", "¿Ataco o espero?"],
            errors=["Llegar parado → “LLEGA EN CARRERA”.", "Esperar el balón → “ATACA”."],
            scene_hint="Escena: pase atrás a penalti. Marca llegada en carrera y remate de primeras.",
            measure=["Tiros de primeras (suben).", "Controles en área (bajan)."],
        ),
    ]


def _mk_game_encyclopedia_rules_applied() -> list[SeedLesson]:
    """
    Enciclopedia del juego: reglamento aplicado.
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Reglamento aplicado · Fuera de juego (ataque y defensa)",
            summary="Temporizar desmarques y coordinar línea defensiva con presión.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["reglamento", "fuera_de_juego", "defensa", "ataque"],
            objective="Evitar offsides tontos y, en defensa, proteger espalda con coordinación.",
            rules=["Ataque: desmarque cuando el pasador está listo.", "Ataque: curva + mirar línea si se puede.", "Defensa: subir solo con presión al balón."],
            checklist=["¿El pasador está listo?", "¿Gano ventaja o solo corro?", "En defensa: ¿hay presión al balón?"],
            errors=["Desmarque temprano → “ESPERA LA SEÑAL”.", "Línea sin presión → “NO SUBAS SIN PRESIÓN”."],
            scene_hint="Escena: pase filtrado (desmarque tarde vs temprano). En defensa: línea sube con presión vs temporiza sin presión.",
            measure=["Fueras de juego cometidos (bajan).", "Balones a la espalda concedidos (bajan)."],
        ),
        _mk_guide(
            title="Reglamento aplicado · Ventaja y faltas tácticas (criterio)",
            summary="Cuándo parar una contra y cuándo temporizar para reducir tarjetas tontas.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["reglamento", "faltas", "tarjetas", "transicion"],
            objective="Gestionar transiciones: evitar contras claras y reducir tarjetas innecesarias.",
            rules=[
                "Si el rival corre a portería con ventaja y no hay cobertura: falta táctica inteligente.",
                "Si hay cobertura/rest defense: temporiza y orienta (no falta tonta).",
                "Evita faltas cerca del área: riesgo doble.",
            ],
            checklist=["¿Hay cobertura detrás?", "¿Es contra clara o la puedo temporizar?", "¿Dónde hago la falta (zona segura)?"],
            errors=["Falta por frustración → “DECIDE, NO REACCIONES”.", "Tarjeta por llegar tarde → “POSICIÓN ANTES”."],
            scene_hint="Escena: pérdida en medio campo. Variante A: sin cobertura → falta táctica. Variante B: con cobertura → temporizar y replegar.",
            measure=["Tarjetas innecesarias (bajan).", "Contraataques concedidos (bajan)."],
        ),
    ]
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
            title="Defensa · Bloque medio: temporizar o saltar",
            summary="Guía práctica para defender en bloque medio: alturas, referencias, y triggers para saltar sin partirse.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "bloque_medio", "temporizar", "triggers"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Objetivo (bloque medio)",
                    "body": (
                        "Bloque medio = proteger el centro, negar pases entre líneas y preparar robo.\n\n"
                        "Prioridad: que el rival juegue por fuera y de cara (sin girar)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Cuándo SALTAR (triggers)",
                    "body": (
                        "- Pase lento o flotado.\n"
                        "- Receptor de espaldas.\n"
                        "- Control malo.\n"
                        "- Línea interior cerrada (apoyos tapados).\n\n"
                        "Si no hay trigger: temporiza (no muerdas)."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Temporizar bien (sin regalar)",
                    "body": (
                        "Temporizar NO es retroceder: es orientar el juego donde te conviene.\n"
                        "1er defensor: cuerpo de lado, tapa dentro.\n"
                        "2º/3º defensor: cierran puertas y acortan distancias.\n\n"
                        "Frases: “DENTRO CERRADO”, “ACOMPAÑA”, “AHORA SÍ”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: bloque medio (salto por trigger)",
                    "body": "Escena tipo: rival intenta jugar dentro; interior cerrado; salto cuando el receptor recibe de espaldas.",
                    "payload": {"hint": "Dibuja dos momentos: (1) temporizar sin trigger (2) salto con cobertura cuando aparece el trigger."},
                },
            ],
        ),
        SeedLesson(
            title="Defensa · Defender centros (primer palo, penalti, segundo)",
            summary="Cómo defender centros sin caos: roles por zonas, orientación corporal y segunda jugada.",
            min_category=AcademyLesson.CATEGORY_INFANTIL,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["defensa", "centros", "area", "segunda_jugada"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Reglas simples del área",
                    "body": (
                        "1) Nadie remata solo en primer palo.\n"
                        "2) El punto de penalti es “zona caliente”.\n"
                        "3) Segundo palo: espalda protegida.\n"
                        "4) Rechace: 1 jugador SIEMPRE.\n\n"
                        "Regla: primero protejo remate, luego salgo."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Orientación corporal",
                    "body": (
                        "Balón–hombre–portería: escaneo constante.\n"
                        "Cuerpo entre rival y zona de remate.\n"
                        "Si el centro es tenso: ataca balón; si es bombeado: gana posición primero."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: defensa de centro",
                    "body": "Dibuja zonas (1º palo, penalti, 2º palo) y quién ataca el balón + quién va al rechace.",
                    "payload": {"hint": "Incluye 2 centros: raso atrás y bombeado. Marca el jugador de rechace en ambos."},
                },
            ],
        ),
        SeedLesson(
            title="Ataque · Salir de presión (perfil, giro y 3er hombre)",
            summary="Guía práctica para progresar bajo presión: escaneo, apoyo, fijar y soltar.",
            min_category=AcademyLesson.CATEGORY_BENJAMIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["ataque", "salida", "tercer_hombre", "perfil"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Principio",
                    "body": (
                        "Bajo presión, no gana el más rápido: gana el que crea una salida.\n\n"
                        "Checklist del receptor:\n"
                        "- escaneo (mirar antes)\n"
                        "- perfil (¿puedo girar?)\n"
                        "- si no giro: apoyo + 3er hombre."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "3 soluciones típicas",
                    "body": (
                        "1) Giro (si hay espacio) → romper línea.\n"
                        "2) Pared (apoyo) → salir del foco.\n"
                        "3) 3er hombre (pase-apoyo-progresión) → la más estable.\n\n"
                        "Regla: si no puedes progresar, mejora tu posición y vuelve a intentarlo."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: salida con tercer hombre",
                    "body": "Escena tipo: central → pivote (de espaldas) → devolución → interior rompe a la espalda.",
                    "payload": {"hint": "Dibuja 3 pasos y marca la orientación del receptor (perfil) en el 2º paso."},
                },
            ],
        ),
        SeedLesson(
            title="Ataque · Cambio de orientación (fijar para soltar)",
            summary="Cómo mover al rival antes de cambiar: fijar, atraer y cambiar a tiempo (no por cambiar).",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["ataque", "cambio_orientacion", "amplitud", "decision"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "La idea (simple)",
                    "body": (
                        "Cambiar de orientación funciona si antes has FIJADO al rival.\n"
                        "Si cambias sin fijar: solo mueves el balón, no al rival.\n\n"
                        "Regla: 2–3 pases para atraer → cambio rápido al lado débil."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Señales para cambiar",
                    "body": (
                        "- Rival bascula tarde.\n"
                        "- Lado débil con 1v1.\n"
                        "- Interior libre entre líneas.\n\n"
                        "Palabras: “ATRAE”, “CAMBIA”, “ATACA”."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: fijar y cambiar",
                    "body": "Escena tipo: lado fuerte atrae; pivote/central cambia al extremo del lado débil.",
                    "payload": {"hint": "Marca ‘lado fuerte’ y ‘lado débil’ y el timing del cambio (cuando rival bascula)."},
                },
            ],
        ),
        SeedLesson(
            title="Transición · Tras pérdida: ¿contra-presión o repliegue?",
            summary="Guía práctica para decidir tras pérdida: 3 preguntas y roles para no regalar la espalda.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["transicion", "perdida", "contrapresion", "repliegue"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Decisión en 2 segundos (3 preguntas)",
                    "body": (
                        "1) ¿Dónde se pierde? (cerca de balón o lejos)\n"
                        "2) ¿Tengo ayudas cerca?\n"
                        "3) ¿El rival puede correr hacia mi portería?\n\n"
                        "Si (1) cerca + (2) sí + (3) no → contra-presión.\n"
                        "Si no → repliegue + temporizar."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Roles",
                    "body": (
                        "- 1º: presión al balón (molestar).\n"
                        "- 2º: cortar pase de salida (primera opción).\n"
                        "- 3º: proteger espalda / falta táctica si es necesario.\n\n"
                        "Error típico: todos presionan → nadie protege la espalda."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_REPLAY_2D,
                    "title": "Pizarra 2D: pérdida y contra-presión",
                    "body": "Escena tipo: pérdida en carril central; 1 presiona, 2 corta pase, 3 equilibra.",
                    "payload": {"hint": "Dibuja dos variantes: pérdida cerca (contra-presión) y pérdida lejos (repliegue)."},
                },
            ],
        ),
        SeedLesson(
            title="Transición · Tras recuperación: primer pase + amenaza",
            summary="Cómo atacar tras recuperar: asegurar el primer pase y amenazar profundidad sin perderla al instante.",
            min_category=AcademyLesson.CATEGORY_ALEVIN,
            max_category=AcademyLesson.CATEGORY_SENIOR,
            tags=["transicion", "recuperacion", "primer_pase", "profundidad"],
            steps=[
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "2 reglas",
                    "body": (
                        "1) Primer pase: seguro y con ventaja (no regales otra pérdida).\n"
                        "2) Amenaza: alguien ataca espacio para fijar (aunque no reciba).\n\n"
                        "Error típico: correr todos al balón y cerrar tus propias líneas de pase."
                    ),
                },
                {
                    "type": AcademyLessonStep.TYPE_TEXT,
                    "title": "Opciones (orden)",
                    "body": (
                        "A) Pase adelante si hay ventaja clara.\n"
                        "B) Pase al apoyo y tercer hombre.\n"
                        "C) Reinicio rápido para atacar organizado.\n\n"
                        "Regla: velocidad con cabeza > velocidad sin plan."
                    ),
                },
            ],
        ),
        *_mk_game_encyclopedia_core(),
        *_mk_game_encyclopedia_goalkeepers(),
        *_mk_game_encyclopedia_set_pieces_extra(),
        *_mk_game_encyclopedia_positions(),
        *_mk_game_encyclopedia_formats(),
        *_mk_game_encyclopedia_units(),
        *_mk_game_encyclopedia_tech_in_context(),
        *_mk_game_encyclopedia_patterns_vs_blocks(),
        *_mk_game_encyclopedia_area_and_crossing_advanced(),
        *_mk_game_encyclopedia_rules_applied(),
        *_mk_game_encyclopedia_inner_game_and_gameplans(),
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


def _mk_game_encyclopedia_inner_game_and_gameplans() -> list[SeedLesson]:
    """
    Enciclopedia del juego: juego interior (zona 14/entre líneas) + planes de partido (A/B/C) y scouting rápido.
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Juego interior · Zona 14: recibir, girar y decidir",
            summary="Guía práctica para usar la zona 14 (frontal del área): cuándo recibir, cuándo soltar y cuándo finalizar.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["juego_interior", "zona14", "ataque", "entre_lineas", "decision"],
            objective="Crear ventaja en la frontal: pase clave/tiro/centro sin perder balones tontos.",
            rules=[
                "Zona 14 solo si hay ventaja: perfilado o apoyo cerca.",
                "Si recibes de cara y puedes girar: acelerar (pase/tiro).",
                "Si recibes presionado: 3er hombre (descarga y ruptura).",
            ],
            triggers=[
                "Mediocentro rival salta → atacar su espalda (entre líneas).",
                "Central rival sale de línea → filtrar al 9/ruptura.",
                "Rival hunde demasiado → pase atrás a zona 14 (tiro/pase).",
            ],
            checklist=[
                "¿Puedo girar?",
                "¿Tengo 1 apoyo a 1 toque?",
                "¿Qué opción es de más probabilidad: tiro, pase, centro raso atrás?",
            ],
            errors=[
                "Recibir de espaldas sin apoyo → “ENTRA SOLO CON APOYO”.",
                "Forzar pase imposible → “FIJA Y SUELTA”.",
                "Tiro sin equilibrio → “ASEGURA Y LUEGO”.",
            ],
            scene_hint="Escena: balón en banda → pase atrás a zona 14. Variante A: interior gira y filtra. Variante B: interior presionado descarga a pivote y 3er hombre rompe al área.",
            measure=[
                "Pases clave/asistencias desde zona 14.",
                "Tiros a puerta generados tras pase atrás.",
                "Pérdidas en zona central (bajan).",
            ],
        ),
        _mk_guide(
            title="Juego interior · Entre líneas (cómo aparecer sin estorbar)",
            summary="Guía práctica para ofrecerse entre líneas: orientación, distancia a rivales y conexión con el siguiente pase.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["juego_interior", "entre_lineas", "ataque", "perfil"],
            objective="Recibir entre líneas con ventaja (de cara o perfilado) para acelerar la jugada.",
            rules=[
                "No te escondas detrás del rival: muévete a su espalda y a su lado ciego.",
                "Distancia: ni pegado al 6 rival ni demasiado lejos (línea de pase clara).",
                "Tras recibir: 1 acción (giro/descarga) y vuelve a moverte.",
            ],
            triggers=[
                "Si el rival bascula a banda → aparece en half‑space interior.",
                "Si el pivote rival mira balón → muévete a su espalda.",
            ],
            checklist=["¿Estoy en lado ciego?", "¿Puedo jugar a 1 toque si me presionan?", "¿Qué hago tras recibir?"],
            errors=["Quedarse quieto entre líneas → “APARECE Y DESAPARECE”.", "Recibir sin perfil → “PERFIL O APOYO”."],
            scene_hint="Escena: 7v7/11v11. Interior se mueve al lado ciego del pivote rival para recibir. Tras recibir, descarga y ataca espacio.",
            measure=["Recepciones entre líneas con progresión.", "Pérdidas por recibir de espaldas presionado (bajan)."],
        ),
        _mk_guide(
            title="Patrones · Atacar por fuera (overlap/underlap + centro útil)",
            summary="Guía práctica para progresar por banda: crear 2v1, llegar a línea de fondo y centrar con intención.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["patrones", "ataque", "banda", "overlap", "underlap", "centros"],
            objective="Progresar por banda sin perder el balón: ventaja → línea de fondo → centro útil.",
            rules=[
                "Crea 2v1: extremo fija, lateral aparece (overlap) o interior rompe (underlap).",
                "Centro con intención: raso atrás / 2º palo según llegadas.",
                "Rest defense: 2–3 por detrás para evitar contra.",
            ],
            triggers=["Si el lateral rival salta al extremo → overlap.", "Si el lateral rival se queda → underlap interior.", "Si llega 2º defensor → descarga y cambio."],
            checklist=["¿Tengo 2v1 real?", "¿Quién llega al área?", "¿Quién se queda de seguridad?"],
            errors=["Centrar sin llegadas → “PRIMERO LLEGA”.", "Overlaps sin fijar → “FIJA ANTES”.", "Pérdida arriba sin seguridad → “REST DEFENSE”."],
            scene_hint="Escena: banda derecha. Variante A: overlap del lateral y centro raso atrás. Variante B: underlap del interior y pase a zona 14.",
            measure=["Centros útiles (tiro/ocasión).", "Pérdidas en banda (bajan).", "Contraataques tras pérdida en banda (bajan)."],
        ),
        _mk_guide(
            title="Patrones · Atacar por dentro (tercer hombre + ruptura)",
            summary="Guía práctica para progresar por dentro: paredes, tercer hombre y atacar la espalda del medio.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["patrones", "ataque", "interior", "tercer_hombre", "ruptura"],
            objective="Romper líneas por dentro sin regalar pérdidas: apoyo + 3er hombre + ruptura.",
            rules=[
                "Si el receptor está de espaldas: descarga y 3er hombre.",
                "El 3er hombre ataca espacio (no se queda al pie).",
                "Si no hay ventaja: reinicia y vuelve a fijar.",
            ],
            triggers=["Rival salta al pivote → interior rompe a su espalda.", "Central rival sale a cortar → pase a la espalda (9 o extremo)."],
            checklist=["¿Quién es el 3er hombre?", "¿Hay espacio a la espalda del medio?", "¿Tengo seguridad si pierdo?"],
            errors=["Forzar giro de espaldas → “3ER HOMBRE”.", "Jugar dentro sin apoyos → “APOYO CERCA”."],
            scene_hint="Escena: central→pivote (de espaldas)→descarga→interior rompe. Marca el timing de la ruptura.",
            measure=["Progresiones por carril central.", "Pases clave/tiros tras 3er hombre.", "Pérdidas en carril central (bajan)."],
        ),
        _mk_guide(
            title="Defensa · Negar juego interior (cierre de líneas y sombras)",
            summary="Guía práctica para evitar pases entre líneas: posiciones, sombras de pase y basculación.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["defensa", "juego_interior", "entre_lineas", "bloque"],
            objective="Que el rival juegue fuera y de cara; negar recepciones cómodas entre líneas.",
            rules=[
                "Dentro primero: el pase entre líneas es prioridad.",
                "Sombras de pase: cuerpo orientado para tapar al mediapunta/pivote rival.",
                "Si el balón va a banda: bascula y compacta, sin abrir interior.",
            ],
            roles=["Pivote: pantalla al 10.", "Interiores: saltan con cobertura.", "Defensas: protegen espalda y zona caliente."],
            checklist=["¿Está tapado el 10 rival?", "¿Bloque compacto (distancias cortas)?", "¿Quién cubre si salto?"],
            errors=["Perseguir balón y abrir interior → “DENTRO CERRADO”.", "Saltar sin cobertura → “TEMPORIZA”."],
            scene_hint="Escena: rival intenta jugar al 10. Pivote tapa línea, interior salta al receptor de espaldas y central protege espalda.",
            measure=["Pases entre líneas rivales completados (bajan).", "Intercepciones en carril central (suben)."],
        ),
        _mk_guide(
            title="Plan de partido · A/B/C (en 10 minutos)",
            summary="Guía práctica para preparar partido: plan base, ajustes por triggers y mensajes por líneas.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["partido", "plan", "ajustes", "scouting"],
            objective="Llegar al partido con claridad: 3 reglas y 2 ajustes, no 30 ideas.",
            rules=[
                "Plan A: tu modelo (3 reglas).",
                "Plan B: ajuste si el rival hace X (1–2 cambios).",
                "Plan C: escenario de partido (ganando/perdiendo) con 1 ajuste claro.",
            ],
            checklist=[
                "¿Cómo atacamos su bloque principal?",
                "¿Cómo defendemos su salida?",
                "¿Qué hacemos tras pérdida (contra‑presión o repliegue)?",
                "ABP: 1 corner a favor + 1 corner en contra (roles).",
            ],
            errors=[
                "Demasiadas ideas → “3 REGLAS, 2 AJUSTES”.",
                "Cambiar modelo cada 5' → “SOLO SI EL TRIGGER APARECE”.",
            ],
            scene_hint="Escena: plantilla de pizarra. Dibuja Plan A (modelo), Plan B (un trigger) y Plan C (ganando/perdiendo).",
            measure=["Acciones clave del plan (ej.: robos altos si presionas).", "ABP: segundas jugadas ganadas."],
        ),
        _mk_guide(
            title="Scouting rápido · 6 preguntas que valen oro",
            summary="Plantilla de análisis rival para fútbol base/semipro: rápido, accionable y sin humo.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["scouting", "partido", "analisis"],
            objective="Detectar 2 debilidades y 2 fortalezas del rival y convertirlo en un plan operativo.",
            rules=[
                "1) ¿Cómo salen? (corto/directo) 2) ¿Dónde pierden? 3) ¿Dónde atacan?",
                "4) ¿Qué bloque usan? 5) ¿Qué jugador marca diferencias? 6) ¿Cómo defienden ABP?",
                "Convierte cada respuesta en 1 regla de plan (máx. 6).",
            ],
            checklist=[
                "Salida rival: ¿a quién presiono y cómo oriento?",
                "Bloque rival: ¿por fuera o por dentro?",
                "Transición: ¿dónde hacen daño?",
                "ABP: ¿zona o al hombre? ¿quién remata?",
            ],
            errors=["Scouting de “opiniones” → “HECHOS Y CONSECUENCIAS”.", "Plan sin traducción al campo → “1 REGLA POR IDEA”."],
            scene_hint="Escena: hoja simple con 6 preguntas y debajo ‘Reglas del plan’.",
            measure=["Cumplimiento del plan (acciones objetivo).", "Errores repetidos del rival forzados."],
        ),
    ]


def _mk_game_encyclopedia_weakside_and_in_game_coaching() -> list[SeedLesson]:
    """
    Enciclopedia del juego: lado débil (preparación/ataque) + coaching en partido (ajustes rápidos).
    """
    L = AcademyLesson
    return [
        _mk_guide(
            title="Ataque · Preparar el lado débil (antes del cambio)",
            summary="El cambio de orientación funciona si el lado débil está ‘listo’: altura, amplitud y timing.",
            min_category=L.CATEGORY_ALEVIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["ataque", "lado_debil", "cambio_orientacion", "ocupacion"],
            objective="Atacar el lado débil con ventaja (tiempo/espacio), no solo ‘pasar al otro lado’.",
            rules=[
                "Antes del cambio: fija 2–3 pases en lado fuerte (atrae).",
                "Lado débil: 1 ancho (línea) + 1 interior + 1 profundidad (no todos a la misma altura).",
                "Cambio tenso y a tiempo: si llega tarde, el rival bascula y ya no hay ventaja.",
            ],
            roles=[
                "Lado fuerte: atraer y asegurar (no perder).",
                "Lado débil: amplitud lista + interior perfilado + amenaza de espalda.",
                "Seguridad: 1–2 por detrás por si se pierde en el cambio.",
            ],
            checklist=["¿El lado débil está colocado?", "¿He fijado antes?", "¿El cambio llega con tensión y a tiempo?"],
            errors=[
                "Cambiar sin fijar → “FIJA Y LUEGO CAMBIA”.",
                "Lado débil ‘apagado’ (todos por dentro) → “UNO ABIERTO SIEMPRE”.",
                "Cambio flojo → “TENSO”.",
            ],
            scene_hint="Escena: ataque por derecha, 3 pases para atraer y cambio rápido a izquierda. Marca altura del extremo y llegada del interior al área.",
            measure=["Cambios de orientación con progresión (suben).", "Pérdidas en el pase de cambio (bajan)."],
        ),
        _mk_guide(
            title="Ataque · Overload-to-isolate (sobrecargar para aislar 1v1)",
            summary="Saturar el lado fuerte para ‘liberar’ al extremo del lado débil en 1v1 con espacio.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["ataque", "lado_fuerte", "lado_debil", "1v1", "decision"],
            objective="Crear un 1v1 de calidad (con espacio) y una llegada al área coordinada.",
            rules=[
                "Sobrecarga: 3–4 jugadores cerca para atraer (sin perder estructura).",
                "Aislamiento: extremo lado débil alto y abierto (no viene al balón).",
                "Tras el cambio: 1 conduce para fijar y 2 atacan área (primer palo + penalti/raso atrás).",
            ],
            triggers=["Si el rival bascula demasiado al balón → cambio inmediato.", "Si el lateral rival queda 1v1 → ataca."],
            checklist=["¿Extremo aislado y con espacio?", "¿Llegadas al área preparadas?", "¿Quién asegura la pérdida?"],
            errors=["Extremo se mete dentro y pierde espacio → “ABRE PARA ATACAR”.", "Cambio y nadie llega → “PRIMERO LLEGA”.",],
            scene_hint="Escena: sobrecarga 4v3 en derecha, cambio a extremo izquierdo aislado, conducción y centro raso atrás con 2 llegadas + rechazo.",
            measure=["1v1 generados en lado débil.", "Centros útiles/ocasiones tras aislamiento."],
        ),
        _mk_guide(
            title="Defensa · Vigilar el lado débil (no ‘morir’ en el cambio)",
            summary="Regla práctica: el lado débil no defiende con la mirada; defiende con posición y comunicación.",
            min_category=L.CATEGORY_BENJAMIN,
            max_category=L.CATEGORY_SENIOR,
            tags=["defensa", "lado_debil", "vigilancia", "basculacion"],
            objective="Evitar cambios de orientación con ventaja y centros con tiempo.",
            rules=[
                "En lado débil: 1 vigila (altura media) y 1 protege espalda (más bajo).",
                "Si el balón está ‘sin presión’, no subimos línea: temporizamos.",
                "Comunicación: ‘solo’, ‘gira’, ‘cambio’ (3 palabras).",
            ],
            checklist=["¿El rival está ‘solo’ en lado débil?", "¿Hay presión al balón?", "¿Estoy a distancia de correr hacia mi portería?"],
            errors=["Todos mirando el balón → “UNO VIGILA”.", "Línea sube sin presión → “TEMPORIZA”.",],
            scene_hint="Escena: rival cambia de banda. Marca al vigilante del lado débil y al lateral que protege la espalda, ajustando altura.",
            measure=["Cambios del rival que acaban en centro (bajan).", "Centros concedidos con tiempo (bajan)."],
        ),
        _mk_guide(
            title="Coaching en partido · Ajustes rápidos (3 palancas)",
            summary="Guía de banquillo para ajustar sin ‘romper’ al equipo: altura, orientación y roles.",
            min_category=L.CATEGORY_CADETE,
            max_category=L.CATEGORY_SENIOR,
            tags=["coaching", "partido", "ajustes", "plan"],
            objective="Corregir un problema recurrente en 60–90 segundos sin saturar al jugador.",
            rules=[
                "Altura: sube/baja 5–10m (bloque).",
                "Orientación: forzar a banda o proteger dentro (decisión).",
                "Roles: cambia 1 rol (quién fija/quién llega/quién asegura).",
            ],
            triggers=["Te superan por dentro → protege interior y orienta fuera.", "Te ganan espalda → baja 5–10m o aumenta presión al balón.", "No generas ocasiones → prepara lado débil y llegadas."],
            checklist=["¿Cuál es el problema 1 (no 3)?", "¿Qué cambio mínimo lo toca?", "¿Quién lo ejecuta?"],
            errors=["Cambiar 5 cosas → “UNA PALANCA”.", "Mensaje largo → “1 FRASE + 1 CUE”.",],
            scene_hint="Escena: pizarra de banquillo con 3 palancas (altura/orientación/roles) y 1 ajuste aplicado.",
            measure=["Acciones del ajuste (ej.: presiones orientadas) suben.", "Concesiones del problema (ej.: pases interiores) bajan."],
        ),
        _mk_guide(
            title="Coaching en partido · Descanso: 3 mensajes (qué, cómo, por qué)",
            summary="Plantilla de 90 segundos para el descanso: concreto, accionable y medible.",
            min_category=L.CATEGORY_INFANTIL,
            max_category=L.CATEGORY_SENIOR,
            tags=["coaching", "descanso", "comunicacion"],
            objective="Salir del descanso con 1–2 ideas claras y un plan observable (no motivación vacía).",
            rules=[
                "1) Qué pasa (hecho): 1 frase.",
                "2) Cómo lo arreglamos (acción): 1 regla + 1 trigger.",
                "3) Por qué (beneficio): 1 frase corta.",
            ],
            checklist=["¿He dicho 1 cosa clave?", "¿Está claro el trigger?", "¿Podemos medirlo en 5 minutos?"],
            errors=["Hablar de todo → “SOLO 1–2 IDEAS”.", "Sin acción → “REGLA + TRIGGER”.",],
            scene_hint="Escena: descanso con pizarra simple: problema (hecho) + regla + trigger + beneficio.",
            measure=["Acciones objetivo en los primeros 5’ (suben).", "Errores repetidos (bajan)."],
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
        pack = [_seed_lesson_with_default_visual_step(x) for x in pack]
        pack = [_seed_lesson_with_quick_card_step(x) for x in pack]
        pack = [_seed_lesson_with_default_resources_step(x) for x in pack]
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
