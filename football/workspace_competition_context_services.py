from .models import Workspace, WorkspaceCompetitionContext


def bootstrap_workspace_competition_context(
    workspace,
    *,
    primary_team=None,
    provider=None,
    external_competition_key=None,
    external_group_key=None,
    external_team_key=None,
    external_team_name=None,
    external_source_url=None,
    auto_sync_enabled=None,
):
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return None
    primary_team = primary_team or workspace.primary_team
    if not primary_team:
        return None
    group = getattr(primary_team, 'group', None)
    season = getattr(group, 'season', None)
    context, _ = WorkspaceCompetitionContext.objects.get_or_create(
        workspace=workspace,
        team=primary_team,
        defaults={
            'group': group,
            'season': season,
            'provider': provider or WorkspaceCompetitionContext.PROVIDER_MANUAL,
            'external_competition_key': external_competition_key or '',
            'external_group_key': external_group_key or '',
            'external_team_key': external_team_key or '',
            'external_team_name': external_team_name or str(getattr(primary_team, 'name', '') or '').strip(),
            'external_source_url': external_source_url or '',
            'is_auto_sync_enabled': True if auto_sync_enabled is None else bool(auto_sync_enabled),
        },
    )
    changed = False
    if context.group_id != getattr(group, 'id', None):
        context.group = group
        changed = True
    if context.season_id != getattr(season, 'id', None):
        context.season = season
        changed = True
    if provider and context.provider != provider:
        context.provider = provider
        changed = True
    if external_competition_key is not None and context.external_competition_key != (external_competition_key or ''):
        context.external_competition_key = external_competition_key or ''
        changed = True
    if external_group_key is not None and context.external_group_key != (external_group_key or ''):
        context.external_group_key = external_group_key or ''
        changed = True
    if external_team_key is not None and context.external_team_key != (external_team_key or ''):
        context.external_team_key = external_team_key or ''
        changed = True
    if external_source_url is not None and getattr(context, 'external_source_url', '') != (external_source_url or ''):
        context.external_source_url = external_source_url or ''
        changed = True
    desired_external_team_name = context.external_team_name
    if external_team_name is not None:
        desired_external_team_name = external_team_name or str(getattr(primary_team, 'name', '') or '').strip()
    elif not desired_external_team_name:
        desired_external_team_name = str(getattr(primary_team, 'name', '') or '').strip()
    if context.external_team_name != desired_external_team_name:
        context.external_team_name = desired_external_team_name
        changed = True
    if auto_sync_enabled is not None and context.is_auto_sync_enabled != bool(auto_sync_enabled):
        context.is_auto_sync_enabled = bool(auto_sync_enabled)
        changed = True
    if changed:
        context.save()
    return context
