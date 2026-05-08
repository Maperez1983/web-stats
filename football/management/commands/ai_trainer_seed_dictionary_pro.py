from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Carga un diccionario PRO (senior competitivo) para IA‑Trainer en BD "
        "(AiTrainerDictionaryEntry). No requiere costes externos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--team-id", type=int, default=0, help="Filtra por Team.id (por defecto: primary team).")
        parser.add_argument("--workspace-id", type=int, default=0, help="Opcional: Workspace.id (0 = global / null).")
        parser.add_argument("--apply", action="store_true", help="Aplica cambios (sin esto es dry-run).")

    def handle(self, *args, **options):
        from football.models import AiTrainerDictionaryEntry, Team, Workspace

        team_id = int(options.get("team_id") or 0)
        workspace_id = int(options.get("workspace_id") or 0)
        apply = bool(options.get("apply"))

        team = Team.objects.filter(id=team_id).first() if team_id else Team.objects.filter(is_primary=True).first()
        if not team:
            self.stderr.write("Team no encontrado. Usa --team-id.")
            return

        workspace = Workspace.objects.filter(id=workspace_id).first() if workspace_id else None

        phases = {
            "build_up": {
                "label": "Inicio / construcción",
                "keywords": ["inicio", "salida", "construcción", "construccion", "salir jugando", "reinicio del juego"],
                "coaching_points": [
                    "Asegura 2 líneas de pase + 1 apoyo de seguridad.",
                    "Escalona alturas para progresar sin partirte.",
                ],
            },
            "progression": {
                "label": "Progresión",
                "keywords": ["progresión", "progresion", "avanzar", "superar línea", "superar linea", "entre líneas", "entre lineas"],
                "coaching_points": [
                    "Fija/atrae antes de jugar vertical.",
                    "Busca al hombre libre o tercer hombre para romper línea.",
                ],
            },
            "finishing": {
                "label": "Finalización",
                "keywords": ["finalización", "finalizacion", "remate", "último pase", "ultimo pase", "centro", "tiro", "zona 14"],
                "coaching_points": [
                    "Ocupa área (2+1) y frontal para segunda jugada.",
                    "Ataca con ventaja: decide rápido (tiro, pase, centro).",
                ],
            },
            "transition_a2d": {
                "label": "Transición ataque→defensa (pérdida)",
                "keywords": ["pérdida", "perdida", "tras pérdida", "tras perdida", "presión tras pérdida", "repliegue", "pre-pérdida", "pre perdida"],
                "coaching_points": [
                    "5–8s de reacción: o robo rápido o repliegue ordenado.",
                    "Protege el carril central y la profundidad.",
                ],
            },
            "transition_d2a": {
                "label": "Transición defensa→ataque (recuperación)",
                "keywords": ["recuperación", "recuperacion", "robo", "salida tras robo", "contraataque", "contragolpe"],
                "coaching_points": [
                    "Primer pase seguro y orientación corporal para jugar de cara.",
                    "Si hay ventaja: verticaliza en 6–8s; si no, pausa y ordena.",
                ],
            },
            "set_pieces": {
                "label": "ABP (acciones a balón parado)",
                "keywords": ["abp", "balón parado", "balon parado", "saque de banda", "córner", "corner", "falta"],
                "coaching_points": [
                    "Roles claros: lanzador, bloqueos, remate, vigilancia.",
                    "Tras ABP: rest defense preparada para evitar contra.",
                ],
            },
        }

        principles = {
            # Estructura y relaciones
            "identity_of_play": {
                "label": "Identidad de juego (reglas del equipo)",
                "keywords": ["identidad", "modelo de juego", "reglas", "principios", "patrones de orden"],
                "coaching_points": [
                    "Define 3–5 reglas por fase (con balón, sin balón, transiciones).",
                    "Que la decisión sea repetible: si pasa X, hacemos Y.",
                ],
            },
            "structure_vs_system": {
                "label": "Estructura vs sistema (roles y funciones)",
                "keywords": ["estructura", "sistema", "roles", "funciones", "organización", "organizacion"],
                "coaching_points": [
                    "Orden posicional + roles por situación (no solo “números”).",
                    "Mantén conexiones: triángulos/rombos y alturas escalonadas.",
                ],
            },
            "relative_distances": {
                "label": "Distancias relativas",
                "keywords": ["distancias", "distancia", "relación", "relacion", "cercanos", "intermedios"],
                "coaching_points": [
                    "No te estires sin sentido: mantén distancias útiles para jugar y presionar.",
                    "Ajusta según zona (más corto cerca del balón; más largo para amenazar).",
                ],
            },
            "heights_steps": {
                "label": "Alturas / escalones",
                "keywords": ["altura", "alturas", "escalón", "escalon", "entre líneas", "entre lineas"],
                "coaching_points": [
                    "Crea 2–3 escalones de pase (detrás, a la altura, entre líneas).",
                    "Si no puedes progresar: pausa y re-ocupa alturas.",
                ],
            },
            "equilibrium_rest_defense": {
                "label": "Equilibrio (rest defense / pre‑pérdida)",
                "keywords": ["equilibrio", "rest defense", "pre-pérdida", "pre perdida", "vigilancia", "cobertura"],
                "coaching_points": [
                    "Ataca con estructura: vigilancias detrás del balón antes de arriesgar.",
                    "La pérdida debe ser “defendible” (zona y apoyos cercanos).",
                ],
            },
            # Espacio
            "rational_occupation": {
                "label": "Ocupar racional e inteligentemente el terreno",
                "keywords": [
                    "ocupar racional",
                    "ocupar racionalmente",
                    "ocupar inteligentemente",
                    "ocupación del espacio",
                    "ocupacion del espacio",
                    "espacio de intervención",
                    "espacio de intervencion",
                ],
                "coaching_points": [
                    "No invadas espacios lógicos del compañero: respeta carril y altura.",
                    "Primero orden (ocupación) y después velocidad (acelerar con ventaja).",
                ],
            },
            "lane_priority": {
                "label": "Prioridad de carriles (balón y cercanos a portería)",
                "keywords": ["carriles", "carril", "carril del balón", "carril del balon", "carriles cercanos", "portería", "porteria"],
                "coaching_points": [
                    "Prioriza carril del balón + carriles cercanos a portería (central/interiores).",
                    "Si no hay ventaja: atrae y cambia de orientación para atacar lado débil.",
                ],
            },
            "strong_weak_side": {
                "label": "Zona fuerte / zona débil",
                "keywords": ["zona fuerte", "zona débil", "zona debil", "lado fuerte", "lado débil", "lado debil", "basculación", "basculacion"],
                "coaching_points": [
                    "Atrae en zona fuerte para liberar zona débil.",
                    "Ocupa zona débil antes del cambio (no llegar tarde).",
                ],
            },
            "between_lines_receive": {
                "label": "Recibir entre líneas",
                "keywords": ["entre líneas", "entre lineas", "perfilado", "giro", "de cara", "hombre libre"],
                "coaching_points": [
                    "Perfilado para jugar de cara o girar si hay tiempo/espacio.",
                    "Si te fijan por espalda: usa tercer hombre o descarga.",
                ],
            },
            # Superioridades
            "numerical_superiority": {
                "label": "Superioridad numérica (+1)",
                "keywords": ["superioridad numérica", "superioridad numerica", "+1", "4v3", "3v2", "2v1"],
                "coaching_points": [
                    "Genera +1 cerca del balón para salir de presión.",
                    "No te quedes estático: mueve el balón para activar la ventaja.",
                ],
            },
            "positional_superiority": {
                "label": "Superioridad posicional",
                "keywords": ["superioridad posicional", "intervalo", "escalón", "escalon", "línea", "linea"],
                "coaching_points": [
                    "Ocupar intervalos y escalones para recibir con ventaja.",
                    "Si estás a la misma altura que el rival: no hay ventaja real.",
                ],
            },
            "qualitative_superiority": {
                "label": "Superioridad cualitativa (1v1 favorable)",
                "keywords": ["1v1", "aislar", "duelo", "ventaja", "mano a mano"],
                "coaching_points": [
                    "Aísla a tu mejor desequilibrante (overload→isolate).",
                    "Dale tiempo/espacio: cambio de orientación + recepción orientada.",
                ],
            },
            # Progresar
            "fix": {
                "label": "Fijar",
                "keywords": ["fijar", "fijación", "fijacion", "amenaza", "profundidad"],
                "coaching_points": [
                    "Fija antes de soltar: si no atraes al rival, no generas espacio.",
                    "Fija con amenaza real (a la espalda o dentro).",
                ],
            },
            "attract": {
                "label": "Atraer",
                "keywords": ["atraer", "arrastrar", "juntar", "provocar", "basculación", "basculacion"],
                "coaching_points": [
                    "Atrae con conducción/circulación hasta que salten.",
                    "Cuando salten: juega al hombre libre o cambia de orientación.",
                ],
            },
            "release": {
                "label": "Liberar",
                "keywords": ["liberar", "soltar", "desmarque", "espacio libre", "abrir pasillo"],
                "coaching_points": [
                    "Sin balón: genera espacio (arrastre) para que otro reciba con ventaja.",
                    "Re-ocupa carril/altura tras liberar para sostener la jugada.",
                ],
            },
            "free_man": {
                "label": "Hombre libre",
                "keywords": ["hombre libre", "sin marca", "sin presión", "sin presion", "libre"],
                "coaching_points": [
                    "Escanea antes de recibir: detecta al libre y el lado ciego.",
                    "Pase al pie correcto del libre para mantener la ventaja.",
                ],
            },
            "third_man_pro": {
                "label": "Tercer hombre",
                "keywords": ["tercer hombre", "third man", "descarga", "de cara", "de primeras", "apoyo de cara"],
                "coaching_points": [
                    "1º fija/atrae, 2º apoya de cara, 3º ataca el espacio libre.",
                    "Temporaliza: si no hay 3º listo, protege balón y espera habilitación.",
                ],
            },
            "switch_play": {
                "label": "Cambio de orientación / girar el juego",
                "keywords": ["cambio de orientación", "cambio de orientacion", "girar el juego", "lado débil", "lado debil", "invertir"],
                "coaching_points": [
                    "Atrae en un lado para atacar el lado débil con ventaja.",
                    "Pase tenso y receptor perfilado para acelerar tras el cambio.",
                ],
            },
            # Construcción / progresión / finalización
            "play_out_under_pressure": {
                "label": "Salir bajo presión",
                "keywords": ["salir bajo presión", "salir bajo presion", "presión alta", "presion alta", "primer pase"],
                "coaching_points": [
                    "Apoyos cortos + tercer hombre para romper la 1ª presión.",
                    "Si no hay ventaja: pausa, atrae y reinicia (no rifar).",
                ],
            },
            "direct_play_structured": {
                "label": "Juego directo estructurado (2ª jugada)",
                "keywords": ["juego directo", "disputa", "segunda jugada", "2ª jugada", "balón largo", "balon largo"],
                "coaching_points": [
                    "Si vas largo: organiza 2ª jugada (3 cercanos + vigilancias).",
                    "Ataca el espacio donde cae el balón (no esperar parado).",
                ],
            },
            "indirect_play_zonal": {
                "label": "Juego indirecto / ataque zonal (ubicación)",
                "keywords": ["juego indirecto", "ataque zonal", "ubicación", "ubicacion", "juego de ubicación", "juego de ubicacion"],
                "coaching_points": [
                    "Ocupación racional (carril/altura) para sostener circulación.",
                    "Progresar generando hombres libres: amplitud, profundidad y tercer hombre.",
                ],
            },
            "carry_to_fix": {
                "label": "Conducir para fijar",
                "keywords": ["conducir", "conducción", "conduccion", "fijar", "atraer"],
                "coaching_points": [
                    "Conduce para atraer y soltar al libre (no conducir por conducir).",
                    "Tras conducción: decide rápido (pase, pared, cambio).",
                ],
            },
            "protect_ball": {
                "label": "Proteger balón",
                "keywords": ["proteger", "protección", "proteccion", "cuerpo", "espalda", "dar tiempo"],
                "coaching_points": [
                    "Si te presionan por espalda: cuerpo entre rival y balón.",
                    "Protege para habilitar apoyos; no te gires sin ventaja.",
                ],
            },
            "play_one_touch": {
                "label": "Jugar de cara / a 1–2 toques",
                "keywords": ["de cara", "a un toque", "de primeras", "descarga", "pared"],
                "coaching_points": [
                    "Jugar de cara para acelerar sin exponerte a presión por espalda.",
                    "Primer control orientado si necesitas 2º toque; si no, de primeras.",
                ],
            },
            # Finalización
            "occupy_box_2plus1": {
                "label": "Ocupar área (2+1)",
                "keywords": ["ocupar área", "ocupar area", "2+1", "segundo palo", "primer palo", "frontal"],
                "coaching_points": [
                    "2 en área (primer/segundo palo) + 1 en frontal (rebote).",
                    "Ataque coordinado: llegar a remate, no esperar dentro.",
                ],
            },
            "cutback_finishing": {
                "label": "Pase atrás (cutback)",
                "keywords": ["pase atrás", "pase atras", "cutback", "línea de fondo", "linea de fondo"],
                "coaching_points": [
                    "Llegar con ventaja al fondo y pase atrás al punto de penalti/frontal.",
                    "Receptor perfilado a portería para rematar de primera.",
                ],
            },
            "second_post_attack": {
                "label": "Atacar 2º palo",
                "keywords": ["segundo palo", "2º palo", "centro", "llegada"],
                "coaching_points": [
                    "Opuesto llega al 2º palo cuando el balón va al costado.",
                    "Si no hay centro: prepara segunda jugada en frontal.",
                ],
            },
            "zone14_shot": {
                "label": "Amenazar Zona 14 (pase/tiro)",
                "keywords": ["zona 14", "zona14", "frontal", "tiro frontal", "pase interior"],
                "coaching_points": [
                    "Fija fuera para liberar el pase/tiro desde frontal (zona 14).",
                    "Llegada del interior: temporiza para recibir perfilado.",
                ],
            },
            # Transiciones
            "counterpress": {
                "label": "Presión tras pérdida (5–8s)",
                "keywords": ["presión tras pérdida", "presion tras perdida", "tras pérdida", "tras perdida", "counterpress", "reacción", "reaccion"],
                "coaching_points": [
                    "Reacción inmediata del más cercano: cerrar pase interior y saltar.",
                    "Si no puedes robar: repliegue ordenado y compacto.",
                ],
            },
            "repliegue": {
                "label": "Repliegue organizado",
                "keywords": ["repliegue", "bloque medio", "bloque bajo", "juntarse", "compacto"],
                "coaching_points": [
                    "Cierra carril central primero, luego orienta hacia fuera.",
                    "No correr hacia atrás sin mirar: corre y ordena.",
                ],
            },
            "protect_depth": {
                "label": "Defender profundidad en transición",
                "keywords": ["profundidad", "a la espalda", "temporizar", "carrera hacia atrás", "carrera hacia atras"],
                "coaching_points": [
                    "Primero profundidad (no te ganen la espalda), luego presión.",
                    "Central más cercano temporiza; el resto repliega y orienta.",
                ],
            },
            "first_pass_after_recovery": {
                "label": "Primer pase tras recuperación",
                "keywords": ["primer pase", "tras recuperación", "tras recuperacion", "salida", "asegurar"],
                "coaching_points": [
                    "Asegura primer pase (cara) para no devolver la posesión.",
                    "Si hay ventaja: verticaliza; si no, pausa y re‑ordena.",
                ],
            },
            "attack_free_space": {
                "label": "Atacar espacio libre (tras robo)",
                "keywords": ["espacio libre", "tras robo", "contraataque", "contragolpe", "verticalizar"],
                "coaching_points": [
                    "Ocupar carriles en transición (dentro‑fuera‑profundidad).",
                    "Decisión en 6–8s: pase final, tiro o consolidar.",
                ],
            },
        }

        figures = {
            "third_man": {"label": "Tercer hombre (figura)", "keywords": ["tercer hombre", "descarga", "de cara", "pared"], "coaching_points": []},
            "switch": {"label": "Cambio de orientación (figura)", "keywords": ["cambio de orientación", "cambio de orientacion", "invertir", "girar el juego"], "coaching_points": []},
            "cutback": {"label": "Pase atrás (figura)", "keywords": ["pase atrás", "pase atras", "cutback"], "coaching_points": []},
        }

        total = len(phases) + len(principles) + len(figures)
        self.stdout.write(
            f"IA‑Trainer PRO dictionary: team={team.id} workspace={'null' if not workspace else workspace.id} "
            f"entries={total} apply={apply}"
        )

        if not apply:
            self.stdout.write("Dry-run: usa --apply para guardar en BD.")
            return

        created = 0
        updated = 0

        def _upsert(section: str, entry_key: str, payload: dict):
            nonlocal created, updated
            defaults = {
                "label": str(payload.get("label") or "")[:160],
                "keywords": payload.get("keywords") if isinstance(payload.get("keywords"), list) else [],
                "coaching_points": payload.get("coaching_points") if isinstance(payload.get("coaching_points"), list) else [],
                "created_by": None,
            }
            _, was_created = AiTrainerDictionaryEntry.objects.update_or_create(
                team=team,
                workspace=workspace,
                section=section,
                entry_key=str(entry_key)[:64],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        with transaction.atomic():
            for key, data in phases.items():
                _upsert("phases", key, data)
            for key, data in principles.items():
                _upsert("principles", key, data)
            for key, data in figures.items():
                _upsert("figures", key, data)

        self.stdout.write(f"OK: created={created} updated={updated}")

