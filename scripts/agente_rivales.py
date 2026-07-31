#!/usr/bin/env python3
"""Agente de plantillas rivales: descarga desde una IP residencial y envia a la app.

Por que existe: laPreferente devuelve 403 al servidor de produccion (datacenter), asi
que la descarga y el parseo NO pueden correr alli. Este agente esta pensado para
ejecutarse en el Mac del club (IP residencial) de forma programada, y solo envia el
resultado ya parseado al endpoint /api/rivales/ingesta/.

Uso tipico (semanal):
    export SJ_BASE_URL="https://app.segundajugada.es"
    export SJ_INGEST_TOKEN="...el mismo valor que RIVAL_INGEST_TOKEN en el servidor..."
    export SJ_COMPETICION_URL="https://lapreferente.com/C26717/x"
    python3 scripts/agente_rivales.py

Opciones utiles:
    --dry-run          descarga y parsea, muestra el resumen y NO envia nada
    --limite 3         solo los tres primeros equipos (para probar)
    --fuente universo  reservado: cuando Universo RFAF publique plantillas

Nota sobre fotos: la fuente da la URL de la foto de cada jugador y se envia tal cual.
Si un jugador no trae foto, la app muestra un avatar neutro en su lugar.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webstats.settings")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("SECRET_KEY", "agente-local")
os.environ.setdefault("ALLOW_SQLITE_IN_PROD", "true")

import django  # noqa: E402

django.setup()

from football.rival_roster_services import parse_rival_squad  # noqa: E402
from football.services import _fetch_preferente_response  # noqa: E402

PREFERENTE_BASE = "https://lapreferente.com/"


def equipos_de_competicion(competicion_url: str, limite: int | None = None):
    """Equipos del grupo, leidos de la CLASIFICACION (que ya sabemos parsear).

    Se reutiliza parse_preferente_standings en vez de rascar los enlaces a mano: es la
    misma fuente que usa el importador del servidor, asi que si cambia el HTML se
    arregla en un solo sitio. Devuelve (nombre, codigo, url_de_plantilla).
    """
    import re

    from football.preferente_competition_services import parse_preferente_standings

    resp = _fetch_preferente_response(competicion_url, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"La competicion respondio HTTP {resp.status_code}. ¿IP bloqueada o URL mala?")
    comp = re.search(r"C(\d+)", competicion_url)
    if not comp:
        raise SystemExit("No pude extraer el codigo de competicion (C…) de la URL.")
    comp_code = comp.group(1)

    filas = parse_preferente_standings(resp.text)
    if not filas:
        raise SystemExit("No pude leer la clasificacion (¿HTML bloqueado o competicion vacia?).")

    salida = []
    for fila in filas:
        nombre = str(fila.get("full_name") or fila.get("team") or "").strip()
        code = str(fila.get("team_code") or "").strip()   # p. ej. "E282"
        if not nombre or not code:
            continue
        salida.append((nombre, code, f"{PREFERENTE_BASE}{code}C{comp_code}-1/x"))
        if limite and len(salida) >= limite:
            break
    return salida


def enviar(base_url: str, token: str, payload: dict) -> dict:
    datos = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/rivales/ingesta/",
        data=datos,
        method="POST",
        headers={"Content-Type": "application/json", "X-Ingest-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "ignore")[:200]
        raise SystemExit(f"El servidor respondio {e.code}: {cuerpo}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Actualiza las plantillas rivales desde una IP residencial.")
    ap.add_argument("--competicion", default=os.getenv("SJ_COMPETICION_URL", ""))
    ap.add_argument("--base-url", default=os.getenv("SJ_BASE_URL", "https://app.segundajugada.es"))
    ap.add_argument("--token", default=os.getenv("SJ_INGEST_TOKEN", ""))
    ap.add_argument("--temporada", default=os.getenv("SJ_TEMPORADA", ""))
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--saltar", default=os.getenv("SJ_SALTAR", ""),
                    help="Codigos de equipo a NO importar, separados por coma (tu propio equipo). Ej: E282")
    ap.add_argument("--fuente", choices=["preferente", "universo"], default="preferente")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.fuente == "universo":
        print("Universo RFAF todavia no publica plantillas por equipo: cuando lo haga, se")
        print("anade aqui como fuente alternativa sin tocar el resto del agente.")
        return 2
    if not args.competicion:
        raise SystemExit("Falta la competicion: --competicion o SJ_COMPETICION_URL.")
    if not args.dry_run and not args.token:
        raise SystemExit("Falta el token: --token o SJ_INGEST_TOKEN (o usa --dry-run).")

    saltar = {c.strip().upper() for c in str(args.saltar or "").split(",") if c.strip()}
    equipos = equipos_de_competicion(args.competicion, args.limite or None)
    if saltar:
        antes = len(equipos)
        equipos = [e for e in equipos if e[1].upper() not in saltar]
        print(f"Saltados por peticion: {antes - len(equipos)}")
    print(f"Equipos encontrados: {len(equipos)}")

    payload_equipos, sin_foto, total = [], 0, 0
    for nombre, code, url in equipos:
        try:
            resp = _fetch_preferente_response(url, timeout=30)
            if resp.status_code != 200:
                print(f"  · {nombre[:30]:30} HTTP {resp.status_code} — saltado")
                continue
            filas = parse_rival_squad(resp.text)
        except Exception as e:  # una plantilla rota no puede tumbar el resto
            print(f"  · {nombre[:30]:30} error {type(e).__name__} — saltado")
            continue
        n_sin = sum(1 for f in filas if not f.get("photo_url"))
        sin_foto += n_sin
        total += len(filas)
        print(f"  · {nombre[:30]:30} {len(filas):3} jugadores, {len(filas)-n_sin:3} con foto")
        payload_equipos.append({"name": nombre, "code": code, "url": url, "players": filas})

    if not payload_equipos:
        raise SystemExit("No se pudo leer ninguna plantilla. Nada que enviar.")

    print(f"\nTotal: {total} jugadores · {total - sin_foto} con foto · {sin_foto} sin foto (saldra avatar)")
    if args.dry_run:
        print("Modo prueba: no se ha enviado nada.")
        return 0

    res = enviar(args.base_url, args.token, {"season": args.temporada, "skip_codes": sorted(saltar), "teams": payload_equipos})
    t = res.get("totals") or {}
    print(f"Enviado a {args.base_url}: equipos={t.get('teams', 0)} nuevos={t.get('created', 0)} "
          f"actualizados={t.get('updated', 0)} dados de baja={t.get('deactivated', 0)}")
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
