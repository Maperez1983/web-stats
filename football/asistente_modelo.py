"""Entender la frase cuando las palabras clave no llegan. Con Groq, gratis, y sin sacar datos.

QUÉ HACE Y QUÉ NO. El modelo **solo clasifica la intención**: dice si le estás pidiendo ir a un
sitio, buscar algo, que te sugiera tareas o que haga algo. Nada más. Quién es el jugador, qué
sesión, qué se escribe y con qué confirmación lo sigue decidiendo el código de siempre, contra
tu base de datos. El modelo nunca ejecuta, nunca ve datos del club y nunca escribe.

POR QUÉ HACE FALTA. El enrutador por palabras clave resuelve «llévame a entrenamientos» en 100
ms, pero «ponme donde los entrenos» se le escapa. Añadir sinónimos a mano es una carrera que no
se gana: siempre habrá otra forma de decirlo. Esto es exactamente el hueco, y el único sitio
donde un modelo aporta algo que el código no.

LOS NOMBRES NO SALEN. Antes de mandar la frase se sustituyen los nombres de tu plantilla por
«JUGADOR». «anota como ausente a Nico Ruiz» sale como «anota como ausente a JUGADOR». El modelo
no necesita saber quién es —eso lo resuelve el código mirando tu plantilla— y así ni un nombre
de un menor viaja a un tercero. Es la diferencia entre usar un servicio gratuito y regalarle
tus datos.

POR QUÉ GROQ Y NO GOOGLE. En su nivel gratuito, Google AI Studio usa lo que le mandas para
entrenar sus modelos y revisores humanos pueden verlo. Groq no. Manejas lesiones de niños: esa
diferencia no es una preferencia técnica.

SI NO HAY CLAVE, NO PASA NADA. Sin `GROQ_API_KEY` esto no se llama siquiera y el asistente
funciona exactamente igual que hoy.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Ultimo intento y ultimo error, para poder mirarlos desde fuera. Cuando se pone la clave y "no
# pasa nada" hay que poder distinguir si es que no se llama, si Groq dice que no, o si el modelo
# no existe. Sin esto se adivina.
ULTIMO = {"intentos": 0, "ok": 0, "error": "", "leido": ""}

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELO_POR_DEFECTO = "llama-3.3-70b-versatile"
# Corto a propósito: esto va DENTRO de tu petición. Si el modelo tarda más, no vale la pena
# esperarle: se cae al camino de siempre y contestas igual.
ESPERA_SEGUNDOS = 4

INTENCIONES = ("ir", "buscar", "sugerir", "orden", "consulta", "otro")

_INSTRUCCION = (
    "Clasificas la frase de un entrenador de fútbol que usa una aplicación de gestión. "
    "Devuelve SOLO un JSON con dos claves:\n"
    '  "intencion": una de ir | buscar | sugerir | orden | consulta | otro\n'
    '  "objetivo": de qué habla, en una o dos palabras y en minúsculas\n\n'
    "Qué significa cada una:\n"
    "  ir       = quiere abrir una pantalla (entrenamientos, plantilla, partidos, análisis, "
    "biblioteca, seguimiento)\n"
    "  buscar   = quiere encontrar algo concreto por su nombre\n"
    "  sugerir  = quiere que le propongas tareas o ejercicios de un tema\n"
    "  orden    = manda hacer un cambio (marcar, anotar, apuntar, convocar, borrar)\n"
    "  consulta = pregunta por datos de su equipo (lesionados, próximo partido, plantilla)\n"
    "  otro     = cualquier otra cosa\n\n"
    "Ejemplos:\n"
    '  "ponme donde los entrenos" -> {"intencion":"ir","objetivo":"entrenamientos"}\n'
    '  "necesito ejercicios para la salida de balon" -> {"intencion":"sugerir","objetivo":"salida de balon"}\n'
    '  "apunta que JUGADOR no vino" -> {"intencion":"orden","objetivo":"asistencia"}\n'
    '  "a ver la enfermeria" -> {"intencion":"consulta","objetivo":"lesionados"}\n'
)


def activo() -> bool:
    return bool(str(os.getenv("GROQ_API_KEY") or "").strip())


def tapar_nombres(frase: str, nombres) -> str:
    """Sustituye los nombres de la plantilla por JUGADOR antes de que la frase salga de aquí."""
    texto = str(frase or "")
    # De más largo a más corto: si no, "Nico" corta dentro de "Nico Ruiz" y deja un "Ruiz"
    # suelto, que es justo un apellido viajando.
    for nombre in sorted({str(n or "").strip() for n in (nombres or []) if len(str(n or "").strip()) >= 3},
                         key=len, reverse=True):
        texto = re.sub(re.escape(nombre), "JUGADOR", texto, flags=re.IGNORECASE)
    return texto


def clasificar(frase: str, *, nombres=None):
    """Devuelve {"intencion", "objetivo"} o None si no se puede o no procede."""
    if not activo():
        return None
    ULTIMO["intentos"] += 1
    frase = str(frase or "").strip()
    if len(frase) < 3 or len(frase) > 300:
        return None

    limpia = tapar_nombres(frase, nombres or [])
    cuerpo = {
        "model": str(os.getenv("GROQ_MODEL") or MODELO_POR_DEFECTO).strip(),
        "temperature": 0,
        "max_tokens": 80,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _INSTRUCCION},
            {"role": "user", "content": limpia},
        ],
    }
    peticion = urllib.request.Request(
        URL,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {str(os.getenv('GROQ_API_KEY') or '').strip()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=ESPERA_SEGUNDOS) as resp:
            datos = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        # 429 = te has pasado del nivel gratuito. No es un error del programa: se sigue sin él.
        detalle = ""
        try:
            detalle = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            detalle = ""
        ULTIMO["error"] = f"http_{getattr(exc, 'code', '?')}: {detalle}"
        logger.debug("groq respondio %s", getattr(exc, "code", "?"))
        return None
    except Exception as exc:
        ULTIMO["error"] = f"{exc.__class__.__name__}: {str(exc)[:160]}"
        logger.debug("groq no respondio a tiempo", exc_info=True)
        return None

    try:
        crudo = datos["choices"][0]["message"]["content"]
        salida = json.loads(crudo)
    except Exception as exc:
        ULTIMO["error"] = f"respuesta ilegible: {exc.__class__.__name__}"
        return None

    intencion = str(salida.get("intencion") or "").strip().lower()
    if intencion not in INTENCIONES or intencion in {"otro", "consulta"}:
        # "consulta" y "otro" se dejan al camino de siempre: el enrutador de datos ya sabe, y
        # no se gana nada metiendo al modelo por medio.
        return None
    ULTIMO["ok"] += 1
    ULTIMO["error"] = ""
    ULTIMO["leido"] = f"{intencion}:{str(salida.get('objetivo') or '')[:30]}"
    return {
        "intencion": intencion,
        "objetivo": str(salida.get("objetivo") or "").strip().lower()[:60],
    }
