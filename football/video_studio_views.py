from .view_delegates import install_view_delegates


VIDEO_STUDIO_VIEW_NAMES = (
    'analysis_video_studio_page',
    'analysis_video_studio_projects_api',
    'analysis_video_studio_project_save_api',
    'analysis_video_studio_project_delete_api',
    'analysis_video_studio_clips_api',
    'analysis_video_studio_clip_save_api',
    'analysis_video_studio_clip_delete_api',
    'analysis_video_studio_voiceovers_api',
    'analysis_video_studio_voiceover_upload_api',
    'analysis_video_studio_voiceover_delete_api',
    'analysis_video_studio_music_api',
    'analysis_video_studio_music_upload_api',
    'analysis_video_studio_music_delete_api',
    'analysis_video_studio_assign_api',
    'analysis_video_studio_video_trim_api',
    'analysis_video_studio_timeline_api',
    'analysis_video_studio_timeline_save_api',
    'analysis_video_studio_timeline_delete_api',
    'analysis_video_studio_timeline_export_api',
    'analysis_video_studio_timeline_import_api',
    'analysis_video_studio_timeline_clear_api',
    'analysis_video_studio_review_api',
    'analysis_video_studio_ocr_dorsal_api',
    'analysis_video_studio_export_pdf_api',
    'analysis_video_studio_export_package_api',
    'analysis_video_studio_export_upload_api',
    'analysis_video_studio_export_server_api',
    'analysis_video_studio_export_server_playlist_api',
    'analysis_video_studio_export_job_create_api',
    'analysis_video_studio_export_job_status_api',
    'analysis_video_studio_export_job_cancel_api',
    'analysis_video_studio_report_pdf_api',
    'analysis_video_studio_ai_api',
    'analysis_video_studio_ai_track_api',
    'analysis_video_studio_ai_pro_api',
    'analysis_video_studio_autocut_api',
    'analysis_video_studio_share_links_api',
    'analysis_video_studio_frame_capture_api',
    'analysis_video_studio_track_players_api',
)

install_view_delegates(globals(), VIDEO_STUDIO_VIEW_NAMES)

__all__ = VIDEO_STUDIO_VIEW_NAMES
