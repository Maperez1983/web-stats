import re

from django.core.cache import cache

from .competition_season_services import current_season_name, pick_current_season_row, season_names_match
from .event_taxonomy import normalize_label
from .models import Group, WorkspaceCompetitionContext
from .query_helpers import _normalize_team_lookup_key
from .universo_catalog_services import build_universo_competition_catalog
from .universo_client import (
    fetch_universo_live_classification,
    fetch_universo_live_competitions,
    fetch_universo_live_delegations,
    fetch_universo_live_groups,
    fetch_universo_live_seasons,
)
from .universo_group_services import expand_team_lookup_variants


def context_team_lookup_keys(context, primary_team):
    keys = set()
    for raw_value in (
        getattr(primary_team, 'name', ''),
        getattr(primary_team, 'display_name', ''),
        getattr(context, 'external_team_name', ''),
    ):
        keys.update(expand_team_lookup_variants(raw_value))
    external_team_key = str(getattr(context, 'external_team_key', '') or '').strip()
    if external_team_key:
        keys.update(expand_team_lookup_variants(external_team_key.lower()))
    return {key for key in keys if key}


REBIND_THROTTLE_SECONDS = 6 * 3600


def binding_season_is_stale(context, primary_team):
    """
    True si el vínculo externo (grupo/equipo en Universo) apunta a una temporada que ya pasó.

    Dos señales independientes:
    - El contexto quedó atado a una `Season` distinta de la del grupo actual del equipo.
    - La temporada vinculada no es la vigente según el calendario.
    """
    if not context:
        return False
    team_season_id = int(getattr(getattr(primary_team, 'group', None), 'season_id', 0) or 0)
    context_season_id = int(getattr(context, 'season_id', 0) or 0)
    if team_season_id and context_season_id and team_season_id != context_season_id:
        return True
    season = getattr(context, 'season', None) or getattr(getattr(primary_team, 'group', None), 'season', None)
    bound_name = str(getattr(season, 'name', '') or '').strip()
    if not bound_name:
        return False
    return not season_names_match(bound_name, current_season_name())


def _should_rebind_for_season(context, primary_team):
    """Revincula como mucho una vez cada `REBIND_THROTTLE_SECONDS`: el rebind hace red."""
    if not binding_season_is_stale(context, primary_team):
        return False
    context_id = int(getattr(context, 'id', 0) or 0)
    if not context_id:
        return True
    cache_key = f'universo-context-rebind:{context_id}'
    try:
        if cache.get(cache_key):
            return False
        cache.set(cache_key, 1, REBIND_THROTTLE_SECONDS)
    except Exception:
        pass
    return True


def ensure_universo_context_binding(context, primary_team):
    if (
        not context
        or str(getattr(context, 'provider', '') or '').strip()
        != WorkspaceCompetitionContext.PROVIDER_UNIVERSO
    ):
        return context
    already_bound = bool(
        str(getattr(context, 'external_group_key', '') or '').strip()
        and (
            str(getattr(context, 'external_team_key', '') or '').strip()
            or str(getattr(context, 'external_team_name', '') or '').strip()
        )
    )
    # Antes se salía siempre que hubiera `external_group_key`, así que un club vinculado en
    # 2025/2026 seguía leyendo el grupo de esa temporada para siempre.
    if already_bound and not _should_rebind_for_season(context, primary_team):
        return context
    if not primary_team:
        return context

    competition = getattr(getattr(getattr(primary_team, 'group', None), 'season', None), 'competition', None)
    team_query = str(getattr(context, 'external_team_name', '') or getattr(primary_team, 'name', '') or '').strip()
    competition_query = str(getattr(competition, 'name', '') or '').strip()
    group_query = str(getattr(getattr(primary_team, 'group', None), 'name', '') or '').strip()

    best_group_match = _find_existing_group_match(
        group_query=group_query,
        competition_query=competition_query,
    )
    if best_group_match:
        update_fields = []
        if (
            best_group_match.external_id
            and getattr(context, 'external_group_key', '') != best_group_match.external_id
        ):
            context.external_group_key = best_group_match.external_id
            update_fields.append('external_group_key')
        if update_fields:
            context.save(update_fields=update_fields + ['updated_at'])
        if str(getattr(context, 'external_group_key', '') or '').strip():
            return context

    candidates = _catalog_binding_candidates(
        team_query=team_query,
        competition_query=competition_query,
        group_query=group_query,
    )
    if not candidates:
        candidates = _live_binding_candidates(
            team_query=team_query,
            competition_query=competition_query,
            group_query=group_query,
        )
    return _apply_best_binding_candidate(context, team_query, candidates)


def _find_existing_group_match(*, group_query, competition_query):
    candidate_groups = (
        Group.objects
        .select_related('season__competition')
        .exclude(external_id__exact='')
        .filter(name__iexact=group_query)
        .order_by('-season__is_current', '-id')
    )
    best_group_match = None
    best_group_score = -1
    for candidate_group in candidate_groups:
        competition = getattr(getattr(candidate_group, 'season', None), 'competition', None)
        candidate_competition_name = str(getattr(competition, 'name', '') or '').strip()
        score = 0
        if group_query:
            score += 25
        if competition_query:
            score += 25 if _query_matches_candidate(
                competition_query,
                candidate_competition_name,
                min_overlap=2,
            ) else 0
        # Desempate por temporada: entre dos grupos con el mismo nombre, gana el de la vigente.
        # Sin esto, revincular tras el cambio de temporada volvería a elegir el grupo antiguo.
        if season_names_match(getattr(getattr(candidate_group, 'season', None), 'name', ''), current_season_name()):
            score += 30
        if score > best_group_score:
            best_group_match = candidate_group
            best_group_score = score
    if best_group_match and best_group_score >= 25:
        return best_group_match
    return None


def _catalog_binding_candidates(*, team_query, competition_query, group_query):
    normalized_comp_query = normalize_label(competition_query)
    normalized_group_query = normalize_label(group_query)
    lookup_team_query = _normalize_team_lookup_key(team_query)
    catalog = build_universo_competition_catalog()
    competitions = catalog.get('competitions') or {}
    groups = catalog.get('groups') or {}
    classifications = catalog.get('classifications') or {}
    candidates = []
    for (competition_code, group_code), classification in classifications.items():
        competition_meta = competitions.get(competition_code) or {}
        group_meta = groups.get((competition_code, group_code)) or {}
        resolved_competition_name = str(
            classification.get('competition_name') or competition_meta.get('name') or ''
        ).strip()
        resolved_group_name = str(
            classification.get('group_name') or group_meta.get('group_name') or ''
        ).strip()
        if normalized_comp_query and normalized_comp_query not in normalize_label(resolved_competition_name):
            continue
        if normalized_group_query and normalized_group_query not in normalize_label(resolved_group_name):
            continue
        for row in classification.get('rows') or []:
            if not isinstance(row, dict):
                continue
            candidate = _candidate_from_row(
                row,
                team_query=team_query,
                competition_name=resolved_competition_name,
                group_name=resolved_group_name,
                season_name=str(competition_meta.get('season_name') or '').strip(),
                competition_code=competition_code,
                group_code=group_code,
                normalized_comp_query=normalized_comp_query,
                normalized_group_query=normalized_group_query,
            )
            if candidate:
                candidates.append(candidate)
    return _sort_candidates(candidates)


def _live_binding_candidates(*, team_query, competition_query, group_query):
    candidates = []
    seasons = fetch_universo_live_seasons()
    season_row = pick_current_season_row(seasons)
    season_id = str((season_row or {}).get('cod_temporada') or '').strip()
    season_name = str((season_row or {}).get('nombre') or '').strip()
    delegations = fetch_universo_live_delegations()
    if not season_id or not delegations:
        return candidates
    normalized_comp_query = normalize_label(competition_query)
    normalized_group_query = normalize_label(group_query)
    for delegation in delegations:
        competitions = fetch_universo_live_competitions(delegation.get('cod_delegacion'), season_id)
        for competition_row in competitions:
            competition_code = str(competition_row.get('codigo') or '').strip()
            resolved_competition_name = str(competition_row.get('nombre') or '').strip()
            if not competition_code or not resolved_competition_name:
                continue
            if competition_query and not _query_matches_candidate(
                competition_query,
                resolved_competition_name,
                min_overlap=2,
            ):
                continue
            groups = fetch_universo_live_groups(competition_code)
            for group_row in groups:
                group_code = str(group_row.get('codigo') or '').strip()
                resolved_group_name = str(group_row.get('nombre') or '').strip()
                if not group_code or not resolved_group_name:
                    continue
                if group_query and not _query_matches_candidate(group_query, resolved_group_name):
                    continue
                classification = fetch_universo_live_classification(group_code)
                for row in classification.get('clasificacion') or []:
                    if not isinstance(row, dict):
                        continue
                    candidate = _candidate_from_row(
                        row,
                        team_query=team_query,
                        competition_name=resolved_competition_name,
                        group_name=resolved_group_name,
                        season_name=season_name,
                        competition_code=competition_code,
                        group_code=group_code,
                        normalized_comp_query=normalized_comp_query,
                        normalized_group_query=normalized_group_query,
                        score_bonus=20,
                    )
                    if candidate:
                        candidates.append(candidate)
    return _sort_candidates(candidates)


def _candidate_from_row(
    row,
    *,
    team_query,
    competition_name,
    group_name,
    season_name,
    competition_code,
    group_code,
    normalized_comp_query,
    normalized_group_query,
    score_bonus=0,
):
    resolved_team_name = str(row.get('nombre') or '').strip()
    if not resolved_team_name:
        return None
    lookup_team_query = _normalize_team_lookup_key(team_query)
    lookup_team_name = _normalize_team_lookup_key(resolved_team_name)
    if lookup_team_query and not (
        lookup_team_query == lookup_team_name
        or lookup_team_query in lookup_team_name
        or lookup_team_name in lookup_team_query
    ):
        return None
    score = int(score_bonus or 0)
    if lookup_team_query:
        score += 60 if lookup_team_query == lookup_team_name else 30
    if normalized_group_query:
        score += 25 if normalized_group_query == normalize_label(group_name) else 12
    if normalized_comp_query:
        score += 25 if normalized_comp_query == normalize_label(competition_name) else 12
    return {
        'team_name': resolved_team_name,
        'competition_name': competition_name,
        'group_name': group_name,
        'season_name': season_name,
        'external_competition_key': competition_code,
        'external_group_key': group_code,
        'external_team_key': str(row.get('codequipo') or '').strip(),
        'external_team_name': resolved_team_name,
        'score': score,
    }


def _apply_best_binding_candidate(context, team_query, candidates):
    if not candidates:
        return context
    normalized_team = _normalize_team_lookup_key(team_query)
    exact_candidates = [
        candidate
        for candidate in candidates
        if _normalize_team_lookup_key(candidate.get('team_name')) == normalized_team
    ]
    candidate_pool = exact_candidates or candidates
    chosen = candidate_pool[0] if candidate_pool else None
    if not chosen:
        return context
    if (
        len(candidate_pool) > 1
        and int(candidate_pool[0].get('score') or 0) == int(candidate_pool[1].get('score') or 0)
    ):
        return context

    update_fields = []
    for field_name, raw_value in (
        ('external_competition_key', chosen.get('external_competition_key')),
        ('external_group_key', chosen.get('external_group_key')),
        ('external_team_key', chosen.get('external_team_key')),
        ('external_team_name', chosen.get('external_team_name') or chosen.get('team_name')),
    ):
        value = str(raw_value or '').strip()
        if value and getattr(context, field_name, '') != value:
            setattr(context, field_name, value)
            update_fields.append(field_name)
    if update_fields:
        context.save(update_fields=update_fields + ['updated_at'])
    return context


def _tokenize_label(value):
    return {
        token
        for token in re.split(r'[^a-z0-9]+', normalize_label(value))
        if token and token not in {'grupo', 'gr', 'senior', 's', 'cd', 'cf'}
    }


def _query_matches_candidate(query, candidate, *, min_overlap=1):
    query_tokens = _tokenize_label(query)
    candidate_tokens = _tokenize_label(candidate)
    if not query_tokens:
        return True
    overlap = query_tokens & candidate_tokens
    return len(overlap) >= min(min_overlap, len(query_tokens))


def _sort_candidates(candidates):
    candidates.sort(
        key=lambda item: (
            -int(item.get('score') or 0),
            item['competition_name'],
            item['group_name'],
            item['team_name'],
        )
    )
    return candidates
