from django.utils.module_loading import import_string


def schedule_autocut_after_upload(*, video_id: int, team_id=None, owner_user_id=None, workspace_id=None, created_by: str = '') -> None:
    return import_string('football.views._video_studio_schedule_autocut_after_upload')(
        video_id=video_id,
        team_id=team_id,
        owner_user_id=owner_user_id,
        workspace_id=workspace_id,
        created_by=created_by,
    )
