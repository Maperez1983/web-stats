import logging
import re

from django.utils.text import slugify

from .competition_season_services import current_season_name, season_names_match
from .models import Competition, Group, Season, Team
from .query_helpers import _normalize_team_lookup_key

logger = logging.getLogger(__name__)


def unique_group_slug_for_season(season_obj, base_value):
    base_slug = slugify(str(base_value or '').strip())[:80] or 'grupo'
    candidate = base_slug
    suffix = 2
    while Group.objects.filter(season=season_obj, slug=candidate).exists():
        candidate = f'{base_slug}-{suffix}'
        suffix += 1
    return candidate


def expand_team_lookup_variants(raw_value):
    base_key = _normalize_team_lookup_key(raw_value)
    if not base_key:
        return set()
    variants = {base_key}
    variants.add(re.sub(r"[\"']?[a-d][\"']?$", "", base_key))

    trimmed = re.sub(r'^(cd|cf|ud|fc)+', '', base_key)
    trimmed = re.sub(r'(cd|cf|ud|fc)+$', '', trimmed)
    if trimmed:
        variants.add(trimmed)
        variants.add(f'cd{trimmed}')
        variants.add(f'{trimmed}cd')

    club_only = re.sub(r'(cd|cf|ud|fc)+', '', base_key)
    if club_only:
        variants.add(club_only)
        variants.add(re.sub(r"[\"']?[a-d][\"']?$", "", club_only))

    return {variant for variant in variants if variant}


def ensure_universo_group_models_from_live(*, group_key, live_payload, primary_team, context):
    if not group_key or not isinstance(live_payload, dict) or not primary_team or not context:
        return
    competition_name = str(live_payload.get('competicion') or '').strip()
    group_name = str(live_payload.get('grupo') or '').strip()
    competition_code = str(live_payload.get('codigo_competicion') or '').strip()
    if not competition_name:
        return
    try:
        season_name = str(
            getattr(getattr(getattr(primary_team, 'group', None), 'season', None), 'name', '') or ''
        ).strip()
    except Exception:
        season_name = ''
    season_name = (season_name or current_season_name())[:80]

    group_obj, season_obj = ensure_universo_group_models_from_candidate(
        group_key=group_key,
        competition_name=competition_name,
        group_name=group_name,
        season_name=season_name,
        competition_code=competition_code,
        primary_team=primary_team,
        context=context,
        return_models=True,
    )
    if not group_obj or not season_obj:
        return

    try:
        classification_rows = live_payload.get('clasificacion') if isinstance(live_payload, dict) else None
        if isinstance(classification_rows, list) and classification_rows:
            _bind_context_team_from_classification(context, primary_team, classification_rows)
    except Exception:
        logger.exception(
            'No se pudo fijar equipo externo Universo para context %s',
            getattr(context, 'id', None),
        )


def ensure_universo_group_models_from_candidate(
    *,
    group_key: str,
    competition_name: str = '',
    group_name: str = '',
    season_name: str = '',
    competition_code: str = '',
    primary_team=None,
    context=None,
    return_models=False,
):
    if not group_key or not primary_team or not context:
        return (None, None) if return_models else None
    competition_name = str(competition_name or '').strip() or 'Universo RFAF'
    group_name = str(group_name or '').strip() or f'Grupo {group_key}'
    season_name = (str(season_name or '').strip() or current_season_name())[:80]
    competition_code = str(competition_code or '').strip()

    comp_slug_source = f'universo-{competition_code}-{competition_name}' if competition_code else competition_name
    comp_slug = slugify(comp_slug_source)[:150] or slugify(competition_name)[:150] or 'universo'
    competition_obj, _ = Competition.objects.get_or_create(
        name=competition_name[:150],
        region='',
        defaults={'slug': comp_slug},
    )
    # Sólo marcamos la temporada nueva como vigente si de verdad lo es según el calendario, y en
    # ese caso desmarcamos las anteriores de la misma competición para no dejar dos `is_current`.
    season_is_current = season_names_match(season_name, current_season_name())
    season_obj, season_created = Season.objects.get_or_create(
        competition=competition_obj,
        name=season_name,
        defaults={'is_current': season_is_current},
    )
    if season_created and season_is_current:
        Season.objects.filter(competition=competition_obj, is_current=True).exclude(pk=season_obj.pk).update(
            is_current=False
        )
    group_obj = Group.objects.filter(season=season_obj, external_id=str(group_key).strip()).first()
    if not group_obj:
        group_slug = unique_group_slug_for_season(season_obj, group_name or f'grupo-{group_key}')
        group_obj = Group.objects.create(
            season=season_obj,
            name=group_name[:80],
            slug=group_slug,
            external_id=str(group_key).strip()[:80],
        )
    elif group_name and str(getattr(group_obj, 'name', '') or '').strip() != group_name:
        group_obj.name = group_name[:80]
        group_obj.save(update_fields=['name'])

    if getattr(primary_team, 'group_id', None) != getattr(group_obj, 'id', None):
        primary_team.group = group_obj
        primary_team.save(update_fields=['group'])

    ctx_updates = []
    if getattr(context, 'group_id', None) != getattr(group_obj, 'id', None):
        context.group = group_obj
        ctx_updates.append('group')
    if getattr(context, 'season_id', None) != getattr(season_obj, 'id', None):
        context.season = season_obj
        ctx_updates.append('season')
    if competition_code and str(getattr(context, 'external_competition_key', '') or '').strip() != competition_code:
        context.external_competition_key = competition_code
        ctx_updates.append('external_competition_key')
    if ctx_updates:
        context.save(update_fields=ctx_updates + ['updated_at'])

    if return_models:
        return group_obj, season_obj
    return None


def _bind_context_team_from_classification(context, primary_team, classification_rows):
    candidate_keys = set()
    for raw_value in (
        getattr(primary_team, 'name', ''),
        getattr(primary_team, 'display_name', ''),
        getattr(primary_team, 'short_name', ''),
        getattr(primary_team, 'slug', ''),
        getattr(context, 'external_team_name', ''),
    ):
        candidate_keys.update(expand_team_lookup_variants(raw_value))
    resolved_team_name = ''
    resolved_team_key = ''
    for row in classification_rows:
        if not isinstance(row, dict):
            continue
        row_team_name = str(row.get('nombre') or row.get('team') or row.get('NombreEquipo') or '').strip()
        row_team_key = str(row.get('codequipo') or row.get('cod_equipo') or row.get('CodEquipo') or '').strip()
        row_keys = expand_team_lookup_variants(row_team_name)
        if row_team_key:
            row_keys.update(expand_team_lookup_variants(row_team_key.lower()))
            row_keys.add(str(row_team_key).strip().lower())
        if candidate_keys & row_keys:
            resolved_team_name = row_team_name
            resolved_team_key = row_team_key
            break
    ctx_updates = []
    if resolved_team_name and str(getattr(context, 'external_team_name', '') or '').strip() != resolved_team_name:
        context.external_team_name = resolved_team_name
        ctx_updates.append('external_team_name')
    if resolved_team_key and str(getattr(context, 'external_team_key', '') or '').strip() != resolved_team_key:
        context.external_team_key = resolved_team_key
        ctx_updates.append('external_team_key')
    if ctx_updates:
        context.save(update_fields=ctx_updates + ['updated_at'])
