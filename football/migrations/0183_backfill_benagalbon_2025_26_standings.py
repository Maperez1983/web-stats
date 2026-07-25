"""Remediación puntual: la clasificación 2025/2026 del grupo de Benagalbón quedó
revuelta en el snapshot (parser posicional RFAF con columnas desplazadas -> PJ=puntos,
PTS=0). Reescribe ese snapshot con la tabla FINAL correcta (capturada en
data/input/rfaf-standings.csv). Dirigida y con guardia: solo toca snapshots cuya
payload contiene a "Benagalbón" Y tiene el fingerprint imposible (PJ>45), así no
afecta a otros clubes y es idempotente (si ya está bien, no hay match).
"""
from django.db import migrations

# (posición, equipo, PJ, PG, PE, PP, GF, GC, DG, PTS) — final 2025/2026, Grupo 2.
_ROWS = [
    (1, "LOJA C.D.", 18, 13, 1, 4, 39, 15, 24, 40),
    (2, "C.D. CANTORIA 2017 F.C.", 18, 11, 4, 3, 32, 18, 14, 37),
    (3, "C.D. ATCO DE MARBELLA BALOMPIE", 18, 12, 1, 5, 41, 20, 21, 35),
    (4, "C.D. MÁLAGA JUNIORS F.C.", 18, 9, 6, 3, 31, 16, 15, 33),
    (5, "BENAGALBÓN DIVISIÓN DE HONOR", 18, 9, 4, 5, 29, 20, 9, 31),
    (6, "U.D. MARACENA", 18, 10, 1, 7, 31, 26, 5, 31),
    (7, "P.D. GARRUCHA", 18, 8, 3, 7, 29, 32, -3, 27),
    (8, "CUEVAS C.F.", 17, 6, 3, 8, 26, 25, 1, 21),
    (9, "C.D. CASABERMEJA", 18, 6, 1, 11, 26, 37, -11, 19),
    (10, "C.D. SANTA FE", 17, 4, 6, 7, 20, 23, -3, 18),
    (11, "C.P. ALMERIA", 18, 4, 6, 8, 11, 18, -7, 18),
    (12, "C.D. PIZARRA ATLÉTICO C.F.", 18, 5, 2, 11, 14, 31, -17, 17),
    (13, "ALHAURIN DE LA TORRE C.F.", 18, 5, 3, 10, 19, 29, -10, 15),
    (14, "BAEZA C.F.", 17, 4, 3, 10, 24, 41, -17, 15),
    (15, "C.D. VILLACARRILLO C.F", 17, 3, 4, 10, 13, 34, -21, 13),
    (16, "C.D. PVO. EL EJIDO 1969 S.A.D.", 0, 0, 0, 0, 0, 0, 0, 0),
]


def _correct_payload():
    payload = []
    for pos, name, pj, pg, pe, pp, gf, gc, dg, pts in _ROWS:
        payload.append(
            {
                "rank": pos,
                "team": name.upper(),
                "full_name": name,
                "team_code": "",
                "crest_url": "",
                "played": pj,
                "wins": pg,
                "draws": pe,
                "losses": pp,
                "goals_for": gf,
                "goals_against": gc,
                "goal_difference": dg,
                "points": pts,
            }
        )
    return payload


def _looks_broken(rows):
    """True si la payload es la tabla revuelta de este grupo: contiene a Benagalbón
    y tiene un PJ imposible (>45)."""
    if not isinstance(rows, list) or not rows:
        return False
    has_benagalbon = any(
        "benagalb" in str((r or {}).get("full_name") or (r or {}).get("team") or "").lower()
        for r in rows
        if isinstance(r, dict)
    )
    max_played = 0
    for r in rows:
        if isinstance(r, dict):
            try:
                max_played = max(max_played, int(r.get("played") or 0))
            except (TypeError, ValueError):
                pass
    return has_benagalbon and max_played > 45


def forwards(apps, schema_editor):
    Snapshot = apps.get_model("football", "WorkspaceCompetitionSnapshot")
    good = _correct_payload()
    for snap in Snapshot.objects.all().iterator():
        if _looks_broken(snap.standings_payload):
            snap.standings_payload = good
            snap.save(update_fields=["standings_payload", "updated_at"])


def backwards(apps, schema_editor):
    # No restauramos los datos revueltos.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("football", "0182_playerevaluation_parameter_scores"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
