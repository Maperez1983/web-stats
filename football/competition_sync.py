import logging

from django.utils import timezone

from .dashboard_cache import invalidate_team_dashboard_caches
from .preferente_competition_services import fetch_preferente_standings
from .match_payload_services import (
    build_local_next_match_payload,
    build_workspace_schedule_payload,
    normalize_next_match_payload,
    next_match_payload_is_usable,
)
from .models import Team, Workspace, WorkspaceCompetitionContext, WorkspaceCompetitionSnapshot
from .next_match_services import (
    build_next_match_from_convocation,
    find_universo_next_match_for_context,
    load_preferred_next_match_payload,
)
from .query_helpers import _normalize_team_lookup_key
from .standings_services import resolve_standings_for_team
from .team_media_services import sync_team_crest_from_sources
from .universo_catalog_services import build_universo_competition_catalog
from .universo_client import fetch_universo_live_classification
from .universo_competition_services import (
    serialize_universo_live_classification,
    universo_payload_matches_category,
)
from .universo_context_services import ensure_universo_context_binding
from .universo_group_services import (
    ensure_universo_group_models_from_candidate,
    ensure_universo_group_models_from_live,
)
from .universo_snapshot_services import load_universo_snapshot
from .workspace_competition_context_services import bootstrap_workspace_competition_context

logger = logging.getLogger(__name__)


def sync_workspace_competition_context(workspace, primary_team=None):
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return None, 'Este cliente no admite contexto competitivo.'
    primary_team = primary_team or workspace.primary_team
    context = bootstrap_workspace_competition_context(workspace, primary_team=primary_team)
    if not context:
        return None, 'No se pudo preparar el contexto competitivo.'
    if not primary_team:
        context.sync_status = WorkspaceCompetitionContext.STATUS_ERROR
        context.sync_error = 'El cliente no tiene equipo vinculado.'
        context.last_sync_at = timezone.now()
        context.save(update_fields=['sync_status', 'sync_error', 'last_sync_at', 'updated_at'])
        return context, context.sync_error

    context = ensure_universo_context_binding(context, primary_team)
    sync_team_crest_from_sources(
        primary_team,
        load_snapshot_func=load_universo_snapshot,
        invalidate_func=invalidate_team_dashboard_caches,
    )
    provider_key = str(getattr(context, 'provider', '') or '').strip().lower()
    # Universo: permitir sincronizar aunque el Team todavía no tenga Group en BD.
    # Usamos `external_group_key` para traer clasificación y crear Competition/Season/Group.
    if provider_key == WorkspaceCompetitionContext.PROVIDER_UNIVERSO and not getattr(primary_team, 'group', None):
        group_key = str(getattr(context, 'external_group_key', '') or '').strip()
        if group_key:
            try:
                live_classification = fetch_universo_live_classification(group_key)
                if isinstance(live_classification, dict) and live_classification.get('clasificacion'):
                    ensure_universo_group_models_from_live(
                        group_key=group_key,
                        live_payload=live_classification,
                        primary_team=primary_team,
                        context=context,
                    )
                else:
                    # Fallback sin red: usa el catálogo local (universo-rfaf-capture.json) si existe.
                    catalog = build_universo_competition_catalog()
                    groups = catalog.get('groups') or {}
                    competitions = catalog.get('competitions') or {}
                    found = None
                    for (comp_code, grp_code), meta in groups.items():
                        if str(grp_code or '').strip() == str(group_key).strip():
                            found = (str(comp_code or '').strip(), meta)
                            break
                    comp_code = str(found[0] or '').strip() if found else ''
                    group_meta = found[1] if found else {}
                    comp_meta = competitions.get(comp_code) or {}
                    ensure_universo_group_models_from_candidate(
                        group_key=group_key,
                        competition_name=str(comp_meta.get('name') or '').strip(),
                        group_name=str(group_meta.get('group_name') or group_meta.get('name') or '').strip(),
                        season_name=str(comp_meta.get('season_name') or '').strip(),
                        competition_code=comp_code,
                        primary_team=primary_team,
                        context=context,
                    )
            except Exception:
                logger.exception('No se pudo preparar grupo Universo para workspace %s', getattr(workspace, 'id', None))

    # La Preferente: se vincula por preferente_url, no por group local. Bajamos la clasificación aquí
    # (una sola vez, reutilizada abajo) para poder servirla vía snapshot aunque el equipo no tenga
    # Group en BD; así la clasificación "aparece" también en un club recién dado de alta en Preferente.
    preferente_standings = []
    if provider_key == WorkspaceCompetitionContext.PROVIDER_PREFERENTE:
        pref_url = str(getattr(context, 'external_source_url', '') or '').strip() or str(
            getattr(primary_team, 'preferente_url', '') or ''
        ).strip()
        if pref_url:
            try:
                preferente_standings, _pref_meta = fetch_preferente_standings(pref_url)
            except Exception:
                logger.exception(
                    'No se pudo sincronizar clasificación La Preferente para workspace %s',
                    getattr(workspace, 'id', None),
                )

    if not getattr(primary_team, 'group', None) and not preferente_standings:
        context.sync_status = WorkspaceCompetitionContext.STATUS_ERROR
        if provider_key == WorkspaceCompetitionContext.PROVIDER_UNIVERSO and not str(getattr(context, 'external_group_key', '') or '').strip():
            context.sync_error = 'Falta el ID de grupo de Universo. Indícalo o usa “Buscar en Universo”.'
        elif provider_key == WorkspaceCompetitionContext.PROVIDER_PREFERENTE:
            context.sync_error = 'No se pudo leer la clasificación de La Preferente. Revisa la URL del equipo.'
        else:
            context.sync_error = 'El cliente no tiene grupo/competición vinculada.'
        context.last_sync_at = timezone.now()
        context.save(update_fields=['sync_status', 'sync_error', 'last_sync_at', 'updated_at'])
        return context, context.sync_error

    if getattr(primary_team, 'group_id', None):
        for team in Team.objects.filter(group=primary_team.group).only('id', 'name', 'short_name', 'external_id', 'crest_url', 'crest_image', 'is_primary'):
            sync_team_crest_from_sources(
                team,
                load_snapshot_func=load_universo_snapshot,
                invalidate_func=invalidate_team_dashboard_caches,
            )
    standings_payload = []
    if provider_key == WorkspaceCompetitionContext.PROVIDER_UNIVERSO:
        group_key = str(getattr(context, 'external_group_key', '') or '').strip() or str(getattr(getattr(primary_team, 'group', None), 'external_id', '') or '').strip()
        if group_key:
            try:
                live_classification = fetch_universo_live_classification(group_key)
                if isinstance(live_classification, dict) and live_classification.get('clasificacion'):
                    # Guardrail: si la categoría no coincide, no aceptamos la clasificación (evita mezclar Senior/Prebenjamín).
                    team_category = str(getattr(primary_team, 'category', '') or '').strip()
                    if team_category and not universo_payload_matches_category(live_classification, team_category):
                        live_classification = {}
                    else:
                        # Asegurar que Competition/Season/Group en BD reflejan la competición real del grupo.
                        ensure_universo_group_models_from_live(
                            group_key=group_key,
                            live_payload=live_classification,
                            primary_team=primary_team,
                            context=context,
                        )
                        standings_payload = serialize_universo_live_classification(live_classification)
            except Exception:
                logger.exception('No se pudo sincronizar clasificación Universo para workspace %s', getattr(workspace, 'id', None))
                standings_payload = []
    elif provider_key == WorkspaceCompetitionContext.PROVIDER_PREFERENTE:
        # Reutiliza la clasificación ya bajada antes del guard (evita una segunda petición).
        if preferente_standings:
            standings_payload = preferente_standings
    if not standings_payload:
        standings_payload = resolve_standings_for_team(
            primary_team,
            snapshot=load_universo_snapshot(),
            provider=getattr(context, 'provider', None),
        )
    convocation_next = build_next_match_from_convocation(primary_team)
    provider_next = find_universo_next_match_for_context(context, primary_team)
    preferred_next = load_preferred_next_match_payload(primary_team=primary_team, competition_context=context)
    snapshot_next = {}
    try:
        universo_snapshot = load_universo_snapshot()
        raw_snapshot_next = {}
        if isinstance(universo_snapshot, dict):
            raw_snapshot_next = universo_snapshot.get('next_match') if isinstance(universo_snapshot.get('next_match'), dict) else {}
        normalized_snapshot_next = normalize_next_match_payload(raw_snapshot_next) if raw_snapshot_next else {}
        if normalized_snapshot_next and next_match_payload_is_usable(normalized_snapshot_next):
            # Validación ligera: aseguramos que el snapshot corresponde al equipo por nombre en standings.
            snapshot_rows = universo_snapshot.get('standings') if isinstance(universo_snapshot, dict) else []
            candidate_keys = {
                _normalize_team_lookup_key(getattr(primary_team, 'name', '') or ''),
                _normalize_team_lookup_key(getattr(primary_team, 'display_name', '') or ''),
            }
            candidate_keys = {key for key in candidate_keys if key}
            snapshot_ok = False
            if isinstance(snapshot_rows, list) and candidate_keys:
                for row in snapshot_rows:
                    if not isinstance(row, dict):
                        continue
                    row_keys = {
                        _normalize_team_lookup_key(row.get('team')),
                        _normalize_team_lookup_key(row.get('full_name')),
                    }
                    row_keys = {key for key in row_keys if key}
                    if candidate_keys & row_keys:
                        snapshot_ok = True
                        break
            if snapshot_ok:
                snapshot_next = normalized_snapshot_next
    except Exception:
        logger.exception('No se pudo resolver próximo partido desde snapshot Universo para workspace %s', getattr(workspace, 'id', None))
        snapshot_next = {}
    # No hacer scraping/red desde este flujo: puede ejecutarse durante navegación y provocar timeouts.
    # Además, el snapshot de Platform debe ser estable aunque el "próximo" partido ya haya pasado (tests con fechas fijas).
    local_next = build_local_next_match_payload(primary_team) or {}
    next_match_payload = (
        (convocation_next if next_match_payload_is_usable(convocation_next) else {})
        or (provider_next if next_match_payload_is_usable(provider_next) else {})
        or (preferred_next if next_match_payload_is_usable(preferred_next) else {})
        or (snapshot_next if next_match_payload_is_usable(snapshot_next) else {})
        or local_next
        or {}
    )
    schedule_payload = build_workspace_schedule_payload(primary_team)
    snapshot, _ = WorkspaceCompetitionSnapshot.objects.get_or_create(
        context=context,
        defaults={'workspace': workspace},
    )
    # `workspace` en snapshot es redundante, pero lo mantenemos para trazabilidad.
    if snapshot.workspace_id != getattr(workspace, 'id', None):
        snapshot.workspace = workspace
    snapshot.context = context
    snapshot.standings_payload = standings_payload or []
    snapshot.next_match_payload = next_match_payload or {}
    snapshot.schedule_payload = schedule_payload or []
    snapshot.save()
    if primary_team:
        invalidate_team_dashboard_caches(primary_team)

    context.group = primary_team.group
    context.season = getattr(primary_team.group, 'season', None)
    context.last_sync_at = timezone.now()
    context.sync_status = WorkspaceCompetitionContext.STATUS_READY
    context.sync_error = ''
    if not context.external_team_name:
        context.external_team_name = str(primary_team.name or '').strip()
    context.save(update_fields=['group', 'season', 'last_sync_at', 'sync_status', 'sync_error', 'external_team_name', 'updated_at'])
    return context, ''
