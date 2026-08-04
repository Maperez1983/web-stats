"""Sembrado de fichas de rival a partir de la clasificación de la liga.

Cada equipo de la clasificación se materializa como un `Team` (is_primary=False) para que
tenga ficha propia (/coach/analisis/rival/<id>/), plantilla cacheada, informe, etc. Es
idempotente: busca por código externo / nombre / slug antes de crear, y solo actualiza
campos vacíos. Sirve tanto para Universo RFAF como para La Preferente (ambas filas traen
`full_name` y `team_code`).
"""

from django.db.models import Q
from django.utils.text import slugify

from .models import Team, resolve_or_create_team
from .query_helpers import _normalize_team_lookup_key


def seed_rivals_from_standings(primary_team, standings_rows):
    """Crea/actualiza una ficha (Team) por cada equipo de la clasificación.

    Devuelve {'created': int, 'updated': int, 'skipped': int}. No lanza: los errores por
    fila se cuentan como 'skipped' para no romper la sincronización que la invoca.
    """
    result = {"created": 0, "updated": 0, "skipped": 0}
    if not primary_team or not standings_rows:
        return result

    primary_keys = {
        _normalize_team_lookup_key(getattr(primary_team, "name", "") or ""),
        _normalize_team_lookup_key(getattr(primary_team, "display_name", "") or ""),
    }
    primary_keys = {key for key in primary_keys if key}

    for row in standings_rows:
        if not isinstance(row, dict):
            continue
        full_name = str(row.get("full_name") or row.get("team") or "").strip()
        if not full_name:
            continue
        if _normalize_team_lookup_key(full_name) in primary_keys:
            result["skipped"] += 1
            continue
        team_code = str(row.get("team_code") or "").strip()
        crest_url = str(row.get("crest_url") or "").strip()
        home_stadium = str(row.get("location") or row.get("field") or row.get("stadium") or "").strip()

        team_obj = None
        if team_code:
            team_obj = Team.objects.filter(external_id=team_code).first()
        if not team_obj:
            team_obj = Team.objects.filter(
                Q(name__iexact=full_name)
                | Q(short_name__iexact=full_name)
                | Q(slug__iexact=slugify(full_name))
            ).first()

        if not team_obj:
            # Por `resolve_or_create_team`, no por Team.objects.create: la búsqueda de arriba es
            # por nombre EXACTO y no reconocía al club escrito de otra forma por la fuente
            # ("PIZARRA" frente a "C.D. Pizarra Atlético C.F."), así que sembraba una ficha
            # nueva en cada sincronización. El helper añade name_key y los alias aprendidos.
            # Con el grupo del equipo primario, además, el rival nace con liga y categoría en
            # vez de suelto: son los rivales de ESA clasificación.
            try:
                team_obj, was_created = resolve_or_create_team(
                    name=full_name[:150],
                    external_id=team_code[:120] if team_code else "",
                    group=getattr(primary_team, "group", None),
                    defaults={
                        # sin 'slug': lo calcula el propio helper (pasarlo aquí lo duplicaría)
                        "crest_url": crest_url[:600] if crest_url else "",
                        "home_stadium": home_stadium[:200] if home_stadium else "",
                        "is_primary": False,
                    },
                )
            except Exception:
                result["skipped"] += 1
                continue
            if was_created:
                result["created"] += 1
                continue

        changed = False
        if team_code and (team_obj.external_id or "").strip() != team_code:
            team_obj.external_id = team_code[:120]
            changed = True
        if crest_url and not (team_obj.crest_url or "").strip():
            team_obj.crest_url = crest_url[:600]
            changed = True
        if home_stadium and not (team_obj.home_stadium or "").strip():
            team_obj.home_stadium = home_stadium[:200]
            changed = True
        if changed:
            try:
                team_obj.save(update_fields=["external_id", "crest_url", "home_stadium"])
                result["updated"] += 1
            except Exception:
                result["skipped"] += 1
        else:
            result["skipped"] += 1

    return result
