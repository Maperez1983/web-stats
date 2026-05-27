import logging

from django.db.models import Q
from django.utils import timezone

from .dashboard_cache import invalidate_team_dashboard_caches
from .models import Match, Team, Workspace, WorkspaceCompetitionContext, WorkspaceCompetitionSnapshot
from .query_helpers import _normalize_team_lookup_key
from .team_media_services import sync_team_crest_from_sources
from .universo_client import fetch_universo_live_classification

logger = logging.getLogger(__name__)


def sync_workspace_competition_context(workspace, primary_team=None):
    from . import views as core_views

    _bootstrap_workspace_competition_context = core_views._bootstrap_workspace_competition_context
    _ensure_universo_context_binding = core_views._ensure_universo_context_binding
    _ensure_universo_group_models_from_live = core_views._ensure_universo_group_models_from_live
    _build_universo_competition_catalog = core_views._build_universo_competition_catalog
    _ensure_universo_group_models_from_candidate = core_views._ensure_universo_group_models_from_candidate
    _universo_payload_matches_category = core_views._universo_payload_matches_category
    _serialize_universo_live_classification = core_views._serialize_universo_live_classification
    _resolve_standings_for_team = core_views._resolve_standings_for_team
    load_universo_snapshot = core_views.load_universo_snapshot
    _build_next_match_from_convocation = core_views._build_next_match_from_convocation
    _find_universo_next_match_for_context = core_views._find_universo_next_match_for_context
    load_preferred_next_match_payload = core_views.load_preferred_next_match_payload
    normalize_next_match_payload = core_views.normalize_next_match_payload
    _payload_opponent_name = core_views._payload_opponent_name
    _parse_payload_date = core_views._parse_payload_date
    build_match_payload = core_views.build_match_payload
    _build_workspace_schedule_payload = core_views._build_workspace_schedule_payload

    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return None, 'Este cliente no admite contexto competitivo.'
    primary_team = primary_team or workspace.primary_team
    context = _bootstrap_workspace_competition_context(workspace, primary_team=primary_team)
    if not context:
        return None, 'No se pudo preparar el contexto competitivo.'
    if not primary_team:
        context.sync_status = WorkspaceCompetitionContext.STATUS_ERROR
        context.sync_error = 'El cliente no tiene equipo vinculado.'
        context.last_sync_at = timezone.now()
        context.save(update_fields=['sync_status', 'sync_error', 'last_sync_at', 'updated_at'])
        return context, context.sync_error

    context = _ensure_universo_context_binding(context, primary_team)
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
                    _ensure_universo_group_models_from_live(
                        group_key=group_key,
                        live_payload=live_classification,
                        primary_team=primary_team,
                        context=context,
                    )
                else:
                    # Fallback sin red: usa el catálogo local (universo-rfaf-capture.json) si existe.
                    catalog = _build_universo_competition_catalog()
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
                    _ensure_universo_group_models_from_candidate(
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

    if not getattr(primary_team, 'group', None):
        context.sync_status = WorkspaceCompetitionContext.STATUS_ERROR
        if provider_key == WorkspaceCompetitionContext.PROVIDER_UNIVERSO and not str(getattr(context, 'external_group_key', '') or '').strip():
            context.sync_error = 'Falta el ID de grupo de Universo. Indícalo o usa “Buscar en Universo”.'
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
                    if team_category and not _universo_payload_matches_category(live_classification, team_category):
                        live_classification = {}
                    else:
                        # Asegurar que Competition/Season/Group en BD reflejan la competición real del grupo.
                        _ensure_universo_group_models_from_live(
                            group_key=group_key,
                            live_payload=live_classification,
                            primary_team=primary_team,
                            context=context,
                        )
                        standings_payload = _serialize_universo_live_classification(live_classification)
            except Exception:
                logger.exception('No se pudo sincronizar clasificación Universo para workspace %s', getattr(workspace, 'id', None))
                standings_payload = []
    if not standings_payload:
        standings_payload = _resolve_standings_for_team(
            primary_team,
            snapshot=load_universo_snapshot(),
            provider=getattr(context, 'provider', None),
        )
    convocation_next = _build_next_match_from_convocation(primary_team)
    provider_next = _find_universo_next_match_for_context(context, primary_team)
    preferred_next = load_preferred_next_match_payload(primary_team=primary_team, competition_context=context)
    def _next_ok_for_snapshot(payload):
        if not isinstance(payload, dict):
            return False
        status = str(payload.get('status') or '').strip().lower()
        if status != 'next':
            return False
        opponent_name = _payload_opponent_name(payload).strip().lower()
        if not opponent_name or opponent_name in {'rival por confirmar', 'rival desconocido'}:
            return False
        round_value = str(payload.get('round') or '').strip()
        if not round_value:
            return False
        return True
    snapshot_next = {}
    try:
        universo_snapshot = load_universo_snapshot()
        raw_snapshot_next = {}
        if isinstance(universo_snapshot, dict):
            raw_snapshot_next = universo_snapshot.get('next_match') if isinstance(universo_snapshot.get('next_match'), dict) else {}
        normalized_snapshot_next = normalize_next_match_payload(raw_snapshot_next) if raw_snapshot_next else {}
        if normalized_snapshot_next and _next_ok_for_snapshot(normalized_snapshot_next):
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
    def _db_next_for_snapshot():
        today = timezone.localdate()
        base_qs = (
            Match.objects
            .filter(Q(home_team=primary_team) | Q(away_team=primary_team))
            .select_related('home_team', 'away_team')
        )
        scoped_qs = base_qs.filter(group=primary_team.group) if getattr(primary_team, 'group_id', None) else base_qs
        match_obj = (
            scoped_qs.filter(date__gte=today).order_by('date', 'id').first()
            or base_qs.filter(date__gte=today).order_by('date', 'id').first()
        )
        if not match_obj:
            match_obj = (
                scoped_qs.exclude(date__isnull=True).order_by('-date', '-id').first()
                or base_qs.exclude(date__isnull=True).order_by('-date', '-id').first()
                or scoped_qs.order_by('-id').first()
                or base_qs.order_by('-id').first()
            )
        if not match_obj:
            return {}
        return build_match_payload(match_obj, primary_team, status='next')
    local_next = _db_next_for_snapshot() or {}
    next_match_payload = (
        (convocation_next if _next_ok_for_snapshot(convocation_next) else {})
        or (provider_next if _next_ok_for_snapshot(provider_next) else {})
        or (preferred_next if _next_ok_for_snapshot(preferred_next) else {})
        or (snapshot_next if _next_ok_for_snapshot(snapshot_next) else {})
        or local_next
        or {}
    )
    schedule_payload = _build_workspace_schedule_payload(primary_team)
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
