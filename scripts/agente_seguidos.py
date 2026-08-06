#!/usr/bin/env python3
"""Refresca cada semana los rivales de liga y los equipos en seguimiento.

Por que corre en el Mac y no en el servidor: hacen falta DOS llaves y las dos estan aqui.
laPreferente solo responde a una IP residencial, y la sesion de Universo RFAF vive en
`data/input/rfaf_storage_state.json`, que esta en el .gitignore y por tanto no existe en
produccion. Un cron en Render devolveria vacio siempre (ademas de costar dinero).

Que hace:
  1. Le pregunta a la app que equipos tocan: los rivales de liga de benjamin, cadete y senior,
     mas los que esten en seguimiento aunque sean de fuera (un amistoso, un jugador que gusto).
  2. Baja cada uno por su fuente: laPreferente si tiene codigo E (trae ademas minutos),
     Universo RFAF si tiene codigo numerico.
  3. Lo sube por el mismo endpoint de ingesta de siempre.

  python3 scripts/agente_seguidos.py            # prueba, no envia
  python3 scripts/agente_seguidos.py --enviar
"""
from __future__ import annotations

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

from football.rival_roster_services import parse_rival_squad, parse_team_crest  # noqa: E402
from football.services import _fetch_preferente_response  # noqa: E402
from football.universo_client import fetch_universo_team_stats  # noqa: E402


def pedir_lista(base, token):
    req = urllib.request.Request(
        base.rstrip("/") + "/api/rivales/a-refrescar/",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json", "X-Ingest-Token": token},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def bajar_de_preferente(equipo):
    url = equipo.get("preferente_url") or ""
    if not url:
        code = str(equipo.get("external_id") or "").strip()
        url = f"https://lapreferente.com/{code}/x" if code else ""
    if not url:
        return [], ""
    resp = _fetch_preferente_response(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return parse_rival_squad(resp.text), parse_team_crest(resp.text)


def main():
    enviar = "--enviar" in sys.argv
    base = os.environ.get("SJ_BASE_URL", "https://app.segundajugada.es")
    token = os.environ.get("SJ_INGEST_TOKEN", "")
    if not token:
        raise SystemExit("Falta SJ_INGEST_TOKEN (esta en ~/.sj_agente.env).")

    lista = pedir_lista(base, token)
    equipos = lista.get("teams") or []
    print(f"La app pide {len(equipos)} equipos: {lista.get('por_fuente')}")

    payload, fallos = [], []
    for eq in equipos:
        nombre = eq.get("name") or "?"
        fuente = eq.get("fuente") or ""
        etiqueta = f"{nombre[:30]:30} [{eq.get('motivo') or '-'}]"
        try:
            if fuente == "lapreferente":
                filas, escudo = bajar_de_preferente(eq)
            elif fuente == "universo":
                filas, escudo = fetch_universo_team_stats(eq.get("external_id") or ""), ""
            else:
                print(f"  · {etiqueta} sin codigo: no se puede refrescar")
                continue
        except Exception as exc:
            print(f"  · {etiqueta} error {type(exc).__name__}")
            fallos.append(nombre)
            continue
        if not filas:
            print(f"  · {etiqueta} {fuente} no devolvio plantilla")
            fallos.append(nombre)
            continue
        print(f"  · {etiqueta} {len(filas):3} jugadores por {fuente}")
        entrada = {
            "name": nombre,
            "code": eq.get("external_id") or "",
            "url": eq.get("preferente_url") or "",
            "players": filas,
            "source": fuente,
        }
        if escudo:
            entrada["crest_url"] = escudo
        payload.append(entrada)

    if fallos:
        print(f"\nSin datos esta semana: {', '.join(fallos[:12])}")
    if not payload:
        raise SystemExit("Nada que enviar.")
    if not enviar:
        print(f"\nPrueba: {len(payload)} equipos listos, no se ha enviado nada. Anade --enviar.")
        return 0

    req = urllib.request.Request(
        base.rstrip("/") + "/api/rivales/ingesta/",
        data=json.dumps({"season": os.environ.get("SJ_TEMPORADA", ""), "teams": payload}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-Ingest-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            res = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"El servidor respondio {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    t = res.get("totals") or {}
    print(f"\nEnviado: equipos={t.get('teams', 0)} nuevos={t.get('created', 0)} "
          f"actualizados={t.get('updated', 0)} bajas={t.get('deactivated', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
