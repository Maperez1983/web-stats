"""
Modelo de ESCENA de una tarea (Fase 4 · card fotorrealista).

Extrae de tactical_layout una descripción de escena NEUTRAL y estructurada
(campo, jugadores, material, movimiento, anotaciones), desacoplada del render.
Esa misma escena puede alimentar:
  - el card 2D actual (fabric),
  - una recreación 2D animada,
  - un render 3D,
  - o un generador de imagen por IA.

Es de solo lectura y defensivo: nunca lanza; ante datos raros devuelve lo que puede.
"""
from __future__ import annotations


# --- clasificación de kinds del canvas ---
_PLAYER_KINDS = {"player_local", "player_away", "player_rival", "goalkeeper_local", "goalkeeper_rival"}
_GK_KINDS = {"goalkeeper_local", "goalkeeper_rival"}
_RIVAL_KINDS = {"player_rival", "goalkeeper_rival"}
_AWAY_KINDS = {"player_away"}
_PROP_KINDS = {"cone": "cone", "pole_marker": "pole", "goal": "goal", "mini_goal": "mini_goal"}
_BALL_KINDS = {"ball"}


def _num(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _txt(v, limit=200):
    try:
        s = str(v).strip() if v is not None else ""
    except Exception:
        s = ""
    return s[:limit]


def _team_of(token_kind):
    if token_kind in _RIVAL_KINDS:
        return "rival"
    if token_kind in _AWAY_KINDS:
        return "away"
    return "local"


def _iter_objects(tactical_layout):
    if not isinstance(tactical_layout, dict):
        return []
    objs = tactical_layout.get("tokens")
    if not isinstance(objs, list):
        objs = tactical_layout.get("objects")
    if not isinstance(objs, list):
        # algunos estados guardan el canvas anidado
        cv = tactical_layout.get("canvas_state") or tactical_layout.get("canvas")
        if isinstance(cv, dict) and isinstance(cv.get("objects"), list):
            objs = cv.get("objects")
    return objs if isinstance(objs, list) else []


def _center(obj):
    # los tokens usan originX/Y center → left/top ya son el centro; si no, aproximamos.
    x = _num(obj.get("left"))
    y = _num(obj.get("top"))
    if str(obj.get("originX") or "center") != "center":
        x += _num(obj.get("width")) * _num(obj.get("scaleX"), 1.0) / 2.0
    if str(obj.get("originY") or "center") != "center":
        y += _num(obj.get("height")) * _num(obj.get("scaleY"), 1.0) / 2.0
    return round(x, 2), round(y, 2)


def build_task_scene(tactical_layout):
    """Devuelve la escena estructurada de la tarea. Solo lectura; nunca lanza."""
    meta = {}
    try:
        if isinstance(tactical_layout, dict) and isinstance(tactical_layout.get("meta"), dict):
            meta = tactical_layout["meta"]
    except Exception:
        meta = {}

    scene = {
        "pitch": {
            "preset": _txt(meta.get("pitch_format") or meta.get("preset") or "full_pitch", 40),
            "orientation": _txt(meta.get("orientation") or "landscape", 20),
            "surface": _txt(meta.get("surface"), 40),
            "dimensions": _txt(meta.get("dimensions") or (meta.get("analysis", {}) or {}).get("task_sheet", {}).get("dimensions"), 60),
        },
        "actors": [],
        "props": [],
        "motion": [],
        "annotations": [],
        "balls": [],
    }

    for obj in _iter_objects(tactical_layout):
        if not isinstance(obj, dict):
            continue
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        if data.get("base"):
            continue
        kind = _txt(data.get("kind"), 40)
        token_kind = _txt(data.get("token_kind"), 40)
        x, y = _center(obj)
        angle = round(_num(obj.get("angle")), 1)

        # Jugadores
        if kind == "token" and (token_kind in _PLAYER_KINDS or token_kind == ""):
            scene["actors"].append({
                "x": x, "y": y,
                "team": _team_of(token_kind),
                "role": "goalkeeper" if token_kind in _GK_KINDS else "field",
                "facing_deg": round(_num(data.get("facing_deg")), 1),
                "style": _txt(data.get("token_style"), 20),
                "dorsal": _txt(data.get("playerNumber") or data.get("number"), 8),
                "name": _txt(data.get("playerName") or data.get("name"), 60),
                "color": _txt(data.get("token_stripe_color") or data.get("color"), 20),
            })
            continue

        # Balón
        if kind in _BALL_KINDS:
            scene["balls"].append({"x": x, "y": y})
            continue

        # Material (props)
        if kind in _PROP_KINDS:
            scene["props"].append({
                "type": _PROP_KINDS[kind], "x": x, "y": y, "angle": angle,
                "scale": round(_num(obj.get("scaleX"), 1.0), 3),
                "color": _txt(data.get("color") or obj.get("fill") or obj.get("stroke"), 24),
            })
            continue

        # Movimiento (flechas)
        if kind.startswith("arrow"):
            pts = obj.get("points") if isinstance(obj.get("points"), list) else None
            frm = to = None
            if pts and len(pts) >= 2 and isinstance(pts[0], dict):
                frm = [round(_num(pts[0].get("x")) + x, 2), round(_num(pts[0].get("y")) + y, 2)]
                to = [round(_num(pts[-1].get("x")) + x, 2), round(_num(pts[-1].get("y")) + y, 2)]
            scene["motion"].append({
                "type": kind, "from": frm, "to": to,
                "curved": bool(data.get("curved") or "curve" in kind),
            })
            continue

        # Anotaciones: zonas y textos
        if kind == "zone" or kind.startswith("shape"):
            scene["annotations"].append({"type": "zone", "x": x, "y": y,
                                         "w": round(_num(obj.get("width")) * _num(obj.get("scaleX"), 1.0), 1),
                                         "h": round(_num(obj.get("height")) * _num(obj.get("scaleY"), 1.0), 1)})
            continue
        if kind == "text" or obj.get("type") in ("text", "textbox", "i-text"):
            scene["annotations"].append({"type": "label", "x": x, "y": y, "text": _txt(obj.get("text"), 120)})
            continue

    return scene


def scene_summary(tactical_layout):
    """Resumen compacto (para logs / debug / índice)."""
    s = build_task_scene(tactical_layout)
    return {
        "actors": len(s["actors"]),
        "local": sum(1 for a in s["actors"] if a["team"] == "local"),
        "rival": sum(1 for a in s["actors"] if a["team"] in ("rival", "away")),
        "goalkeepers": sum(1 for a in s["actors"] if a["role"] == "goalkeeper"),
        "props": len(s["props"]),
        "motion": len(s["motion"]),
        "balls": len(s["balls"]),
        "annotations": len(s["annotations"]),
    }
