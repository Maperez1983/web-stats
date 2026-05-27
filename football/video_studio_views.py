from django.utils.module_loading import import_string


def _legacy_view(name):
    def _wrapped(request, *args, **kwargs):
        view = import_string(f'football.views.{name}')
        return view(request, *args, **kwargs)

    _wrapped.__name__ = name
    return _wrapped


analysis_video_studio_page = _legacy_view('analysis_video_studio_page')
analysis_video_studio_projects_api = _legacy_view('analysis_video_studio_projects_api')
analysis_video_studio_project_save_api = _legacy_view('analysis_video_studio_project_save_api')
analysis_video_studio_project_delete_api = _legacy_view('analysis_video_studio_project_delete_api')
analysis_video_studio_clips_api = _legacy_view('analysis_video_studio_clips_api')
analysis_video_studio_clip_save_api = _legacy_view('analysis_video_studio_clip_save_api')
analysis_video_studio_clip_delete_api = _legacy_view('analysis_video_studio_clip_delete_api')
analysis_video_studio_voiceovers_api = _legacy_view('analysis_video_studio_voiceovers_api')
analysis_video_studio_voiceover_upload_api = _legacy_view('analysis_video_studio_voiceover_upload_api')
analysis_video_studio_voiceover_delete_api = _legacy_view('analysis_video_studio_voiceover_delete_api')
analysis_video_studio_music_api = _legacy_view('analysis_video_studio_music_api')
analysis_video_studio_music_upload_api = _legacy_view('analysis_video_studio_music_upload_api')
analysis_video_studio_music_delete_api = _legacy_view('analysis_video_studio_music_delete_api')
analysis_video_studio_assign_api = _legacy_view('analysis_video_studio_assign_api')
analysis_video_studio_video_trim_api = _legacy_view('analysis_video_studio_video_trim_api')
analysis_video_studio_timeline_api = _legacy_view('analysis_video_studio_timeline_api')
analysis_video_studio_timeline_save_api = _legacy_view('analysis_video_studio_timeline_save_api')
analysis_video_studio_timeline_delete_api = _legacy_view('analysis_video_studio_timeline_delete_api')
analysis_video_studio_timeline_export_api = _legacy_view('analysis_video_studio_timeline_export_api')
analysis_video_studio_timeline_import_api = _legacy_view('analysis_video_studio_timeline_import_api')
analysis_video_studio_timeline_clear_api = _legacy_view('analysis_video_studio_timeline_clear_api')
analysis_video_studio_review_api = _legacy_view('analysis_video_studio_review_api')
analysis_video_studio_ocr_dorsal_api = _legacy_view('analysis_video_studio_ocr_dorsal_api')
analysis_video_studio_export_pdf_api = _legacy_view('analysis_video_studio_export_pdf_api')
analysis_video_studio_export_package_api = _legacy_view('analysis_video_studio_export_package_api')
analysis_video_studio_export_upload_api = _legacy_view('analysis_video_studio_export_upload_api')
analysis_video_studio_export_server_api = _legacy_view('analysis_video_studio_export_server_api')
analysis_video_studio_export_server_playlist_api = _legacy_view('analysis_video_studio_export_server_playlist_api')
analysis_video_studio_export_job_create_api = _legacy_view('analysis_video_studio_export_job_create_api')
analysis_video_studio_export_job_status_api = _legacy_view('analysis_video_studio_export_job_status_api')
analysis_video_studio_export_job_cancel_api = _legacy_view('analysis_video_studio_export_job_cancel_api')
analysis_video_studio_report_pdf_api = _legacy_view('analysis_video_studio_report_pdf_api')
analysis_video_studio_ai_api = _legacy_view('analysis_video_studio_ai_api')
analysis_video_studio_autocut_api = _legacy_view('analysis_video_studio_autocut_api')
analysis_video_studio_share_links_api = _legacy_view('analysis_video_studio_share_links_api')
analysis_video_studio_frame_capture_api = _legacy_view('analysis_video_studio_frame_capture_api')
analysis_video_studio_track_players_api = _legacy_view('analysis_video_studio_track_players_api')
