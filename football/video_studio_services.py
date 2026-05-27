import logging
import os
import threading

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.module_loading import import_string

from .models import RivalVideo, Team, VideoClip, VideoTimelineEvent, Workspace, WorkspacePreference


logger = logging.getLogger(__name__)


def autocut_enabled() -> bool:
    try:
        raw = str(os.getenv('ANALYSIS_AUTOCUT_ON_UPLOAD') or '').strip().lower()
    except Exception:
        raw = ''
    if raw and raw not in {'1', 'true', 'yes', 'on'}:
        return False
    return True


def autoclip_pref_key(*, team_id, pack: str) -> str:
    return f'vs_event_autoclip:v1:{int(team_id or 0)}:{str(pack or "own").strip().lower() or "own"}'


def autoclip_pack_from_clip(*, clip):
    collection = str(getattr(clip, 'collection', '') or '').strip().lower()
    tags = getattr(clip, 'tags', None)
    tags_norm = {str(tag or '').strip().lower() for tag in tags if str(tag or '').strip()} if isinstance(tags, list) else set()
    if 'rival' in tags_norm or collection == 'rival':
        return 'rival'
    if 'own' in tags_norm or collection in {'propio', 'own'}:
        return 'own'
    return ''


def median(values):
    data = sorted(float(value) for value in (values or []) if value is not None)
    if not data:
        return 0.0
    mid = len(data) // 2
    if len(data) % 2:
        return data[mid]
    return (data[mid - 1] + data[mid]) / 2.0


def apply_autocut_suggestions(**kwargs):
    return import_string('football.views._video_studio_apply_autocut_suggestions')(**kwargs)


def schedule_autocut_after_upload(*, video_id: int, team_id=None, owner_user_id=None, workspace_id=None, created_by: str = '') -> None:
    """
    Ejecuta AutoCut en background al subir un MP4, sin bloquear el request.
    """
    if not autocut_enabled():
        return

    def _runner():
        try:
            entry = RivalVideo.objects.filter(id=int(video_id)).first()
            if not entry or not getattr(entry, 'video', None):
                return
            scope_team = Team.objects.filter(id=int(team_id)).first() if team_id else None
            owner_user = User.objects.filter(id=int(owner_user_id)).first() if owner_user_id else None
            workspace = Workspace.objects.filter(id=int(workspace_id)).first() if workspace_id else None
            job_event = None
            try:
                job_event = VideoTimelineEvent.objects.create(
                    team=scope_team if scope_team else None,
                    owner_user=owner_user if owner_user else None,
                    video=entry,
                    time_ms=0,
                    kind=VideoTimelineEvent.KIND_NOTE,
                    label='AutoCut: analizando...',
                    color='#f4b400',
                    payload={'autocut': True, 'autocut_job': True, 'state': 'running'},
                    created_by=str(created_by or '')[:80],
                )
            except Exception:
                job_event = None

            pack = 'rival' if int(getattr(entry, 'rival_team_id', 0) or 0) else 'own'
            learned_pre = None
            learned_post = None
            learned_min_gap = None
            try:
                if workspace:
                    key = autoclip_pref_key(team_id=int(getattr(scope_team, 'id', 0) or 0) if scope_team else 0, pack=pack)
                    pref = WorkspacePreference.objects.filter(workspace=workspace, key=key).first()
                    val = pref.value if pref and isinstance(pref.value, dict) else {}
                    if isinstance(val, dict):
                        if str(val.get('pre') or '').strip():
                            learned_pre = float(val.get('pre') or 0)
                        if str(val.get('post') or '').strip():
                            learned_post = float(val.get('post') or 0)
            except Exception:
                learned_pre = None
                learned_post = None

            try:
                clip_qs = VideoClip.objects.all()
                if scope_team:
                    clip_qs = clip_qs.filter(team=scope_team)
                else:
                    clip_qs = clip_qs.filter(team__isnull=True, owner_user=owner_user) if owner_user else clip_qs.none()
                mids = []
                for clip in list(clip_qs.only('in_ms', 'out_ms', 'tags', 'collection', 'updated_at').order_by('-updated_at', '-id')[:260]):
                    tags = getattr(clip, 'tags', None)
                    if not isinstance(tags, list):
                        continue
                    tags_norm = {str(tag or '').strip().lower() for tag in tags[:60] if str(tag or '').strip()}
                    if 'autocut' in tags_norm or 'timeline' not in tags_norm:
                        continue
                    inferred_pack = autoclip_pack_from_clip(clip=clip)
                    if inferred_pack and inferred_pack != pack:
                        continue
                    start_ms = int(getattr(clip, 'in_ms', 0) or 0)
                    end_ms = int(getattr(clip, 'out_ms', 0) or 0)
                    if end_ms <= start_ms:
                        continue
                    mids.append(int((start_ms + end_ms) / 2))
                mids = sorted(mids)[:2400]
                gaps = []
                for idx in range(1, len(mids)):
                    gap_s = float(mids[idx] - mids[idx - 1]) / 1000.0
                    if gap_s > 0:
                        gaps.append(gap_s)
                if gaps and len(gaps) >= 6:
                    learned_min_gap = float(round(median(gaps)))
            except Exception:
                learned_min_gap = None

            result = apply_autocut_suggestions(
                video=entry,
                scope_team=scope_team,
                owner_user=owner_user,
                created_by=str(created_by or '')[:80],
                profile=str(os.environ.get('ANALYSIS_AUTOCUT_PROFILE') or 'balanced'),
                max_moments=18,
                min_gap_s=float(learned_min_gap) if learned_min_gap is not None else 25.0,
                pre_s=float(learned_pre) if learned_pre is not None else 8.0,
                post_s=float(learned_post) if learned_post is not None else 8.0,
                max_scan_s=None,
                replace=True,
            )
            if job_event:
                try:
                    if result.get('ok'):
                        job_event.delete()
                    else:
                        job_event.label = 'AutoCut: error'
                        job_event.payload = {'autocut': True, 'autocut_job': True, 'state': 'error'}
                        job_event.save(update_fields=['label', 'payload', 'updated_at'])
                except Exception:
                    pass
        except Exception:
            logger.exception('AutoCut after upload failed', extra={'video_id': video_id})

    def _start():
        try:
            thread = threading.Thread(target=_runner, name=f'autocut-video-{int(video_id)}', daemon=True)
            thread.start()
        except Exception:
            pass

    try:
        transaction.on_commit(_start)
    except Exception:
        _start()
