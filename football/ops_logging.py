def request_context_extra(request=None, *, workspace=None, team=None, action=''):
    user = getattr(request, 'user', None) if request is not None else None
    return {
        'user_id': int(getattr(user, 'id', 0) or 0) or None,
        'workspace_id': int(getattr(workspace, 'id', 0) or 0) or None,
        'team_id': int(getattr(team, 'id', 0) or 0) or None,
        'path': str(getattr(request, 'path', '') or '') if request is not None else '',
        'action': str(action or ''),
    }


def log_exception(logger, message, request=None, *, workspace=None, team=None, action='', **extra):
    context = request_context_extra(request, workspace=workspace, team=team, action=action)
    context.update(extra)
    logger.exception('%s context=%s', message, context)
