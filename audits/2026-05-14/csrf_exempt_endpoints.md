# Superficie HTTP — endpoints con `csrf_exempt` (generado)

Total patterns: 261  
CSRF-exempt patterns: 61

| source | line | route | view | name | decorators |
|---|---:|---|---|---|---|
| football/urls.py | 22 | `api/match/video/marker/` | `views.match_video_marker_api` | `match-video-marker-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 29 | `stripe/webhook/` | `views.stripe_webhook` | `stripe-webhook` | `csrf_exempt; require_POST` |
| football/urls.py | 33 | `api/workspace/preferences/set/` | `views.workspace_preference_set_api` | `workspace-pref-set` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 45 | `task-studio/task/create/` | `views.task_studio_task_create` | `task-studio-task-create` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 48 | `task-studio/task/pdf-preview/` | `views.task_studio_task_pdf_preview` | `task-studio-task-pdf-preview` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 50 | `api/dashboard/refresh/` | `views.refresh_scraping` | `dashboard-refresh` | `csrf_exempt; authenticated_write; require_POST` |
| football/urls.py | 71 | `api/match/postmatch/to-blueprints/` | `views.match_postmatch_pro_to_blueprints_api` | `match-postmatch-pro-to-blueprints-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 96 | `api/system/settings/set/` | `views.system_setting_set_api` | `system-setting-set-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 104 | `api/analysis/rival-report/to-blueprints/` | `views.analysis_rival_report_to_blueprints_api` | `analysis-rival-report-to-blueprints-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 113 | `api/analysis/video-studio/projects/save/` | `views.analysis_video_studio_project_save_api` | `analysis-video-studio-project-save-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 114 | `api/analysis/video-studio/projects/delete/` | `views.analysis_video_studio_project_delete_api` | `analysis-video-studio-project-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 116 | `api/analysis/video-studio/clips/save/` | `views.analysis_video_studio_clip_save_api` | `analysis-video-studio-clip-save-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 117 | `api/analysis/video-studio/clips/delete/` | `views.analysis_video_studio_clip_delete_api` | `analysis-video-studio-clip-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 119 | `api/analysis/video-studio/voiceovers/upload/` | `views.analysis_video_studio_voiceover_upload_api` | `analysis-video-studio-voiceover-upload-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 120 | `api/analysis/video-studio/voiceovers/delete/` | `views.analysis_video_studio_voiceover_delete_api` | `analysis-video-studio-voiceover-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 122 | `api/analysis/video-studio/music/upload/` | `views.analysis_video_studio_music_upload_api` | `analysis-video-studio-music-upload-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 123 | `api/analysis/video-studio/music/delete/` | `views.analysis_video_studio_music_delete_api` | `analysis-video-studio-music-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 124 | `api/analysis/video-studio/assign/` | `views.analysis_video_studio_assign_api` | `analysis-video-studio-assign-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 125 | `api/analysis/video-studio/video/trim/` | `views.analysis_video_studio_video_trim_api` | `analysis-video-studio-video-trim-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 127 | `api/analysis/video-studio/timeline/save/` | `views.analysis_video_studio_timeline_save_api` | `analysis-video-studio-timeline-save-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 128 | `api/analysis/video-studio/timeline/delete/` | `views.analysis_video_studio_timeline_delete_api` | `analysis-video-studio-timeline-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 130 | `api/analysis/video-studio/timeline/import/` | `views.analysis_video_studio_timeline_import_api` | `analysis-video-studio-timeline-import-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 131 | `api/analysis/video-studio/timeline/clear/` | `views.analysis_video_studio_timeline_clear_api` | `analysis-video-studio-timeline-clear-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 132 | `api/analysis/video-studio/review/` | `views.analysis_video_studio_review_api` | `analysis-video-studio-review-api` | `csrf_exempt; login_required` |
| football/urls.py | 133 | `api/analysis/video-studio/ocr/dorsal/` | `views.analysis_video_studio_ocr_dorsal_api` | `analysis-video-studio-ocr-dorsal-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 135 | `api/kpi-explorer/query/` | `views.kpi_explorer_query_api` | `kpi-explorer-query-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 136 | `api/kpi-explorer/sources/` | `views.kpi_explorer_sources_api` | `kpi-explorer-sources-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 137 | `api/kpi-explorer/pdf/` | `views.kpi_explorer_pdf_api` | `kpi-explorer-pdf-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 138 | `api/analysis/video-studio/export/pdf/` | `views.analysis_video_studio_export_pdf_api` | `analysis-video-studio-export-pdf-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 139 | `api/analysis/video-studio/export/package/` | `views.analysis_video_studio_export_package_api` | `analysis-video-studio-export-package-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 141 | `api/analysis/video-studio/export/server/` | `views.analysis_video_studio_export_server_api` | `analysis-video-studio-export-server-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 142 | `api/analysis/video-studio/export/server-playlist/` | `views.analysis_video_studio_export_server_playlist_api` | `analysis-video-studio-export-server-playlist-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 143 | `api/analysis/video-studio/export/jobs/create/` | `views.analysis_video_studio_export_job_create_api` | `analysis-video-studio-export-job-create-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 145 | `api/analysis/video-studio/export/jobs/cancel/` | `views.analysis_video_studio_export_job_cancel_api` | `analysis-video-studio-export-job-cancel-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 146 | `api/analysis/video-studio/report/pdf/` | `views.analysis_video_studio_report_pdf_api` | `analysis-video-studio-report-pdf-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 147 | `api/analysis/video-studio/ai/` | `views.analysis_video_studio_ai_api` | `analysis-video-studio-ai-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 148 | `api/analysis/video-studio/autocut/` | `views.analysis_video_studio_autocut_api` | `analysis-video-studio-autocut-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 150 | `api/analysis/video-studio/frame-capture/` | `views.analysis_video_studio_frame_capture_api` | `analysis-video-studio-frame-capture-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 151 | `api/analysis/video-studio/track/players/` | `views.analysis_video_studio_track_players_api` | `analysis-video-studio-track-players-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 153 | `api/analysis/video-inbox/send/` | `views.analysis_video_inbox_send_api` | `analysis-video-inbox-send-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 154 | `api/analysis/video-inbox/comments/` | `views.analysis_video_inbox_comments_api` | `analysis-video-inbox-comments-api` | `csrf_exempt; login_required` |
| football/urls.py | 155 | `api/analysis/rival-videos/chunk/init/` | `views.analysis_rival_video_chunk_init_api` | `analysis-rival-video-chunk-init-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 156 | `api/analysis/rival-videos/chunk/put/` | `views.analysis_rival_video_chunk_put_api` | `analysis-rival-video-chunk-put-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 157 | `api/analysis/rival-videos/chunk/finish/` | `views.analysis_rival_video_chunk_finish_api` | `analysis-rival-video-chunk-finish-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 159 | `api/pdf-assets/upload/` | `views.pdf_graphic_asset_upload` | `pdf-graphic-asset-upload` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 160 | `api/pdf-assets/delete/` | `views.pdf_graphic_asset_delete_api` | `pdf-graphic-asset-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 162 | `api/task-assistant/blueprints/save/` | `views.task_assistant_blueprint_save_api` | `task-assistant-blueprint-save-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 164 | `api/task-assistant/knowledge/upload/` | `views.task_assistant_knowledge_upload_api` | `task-assistant-knowledge-upload-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 166 | `api/tactical-playbook/clips/save/` | `views.tactical_playbook_clip_save_api` | `tactical-playbook-clip-save-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 167 | `api/tactical-playbook/clips/delete/` | `views.tactical_playbook_clip_delete_api` | `tactical-playbook-clip-delete-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 168 | `api/tactical-playbook/clips/favorite/` | `views.tactical_playbook_clip_favorite_api` | `tactical-playbook-clip-favorite-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 169 | `api/tactical-playbook/clips/clone/` | `views.tactical_playbook_clip_clone_api` | `tactical-playbook-clip-clone-api` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 223 | `coach/sesiones/tareas/nueva/` | `views.sessions_task_create_page` | `sessions-task-create` | `csrf_exempt; login_required` |
| football/urls.py | 226 | `coach/sesiones/tareas/pdf-preview/` | `views.session_task_pdf_preview` | `sessions-task-pdf-preview` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 228 | `coach/sesiones/tareas/<int:task_id>/editar/` | `views.sessions_task_edit_page` | `sessions-task-edit` | `csrf_exempt; login_required` |
| football/urls.py | 230 | `coach/sesiones/porteros/tareas/nueva/` | `views.sessions_goalkeeper_task_create_page` | `sessions-goalkeeper-task-create` | `csrf_exempt; login_required` |
| football/urls.py | 231 | `coach/sesiones/porteros/tareas/<int:task_id>/editar/` | `views.sessions_goalkeeper_task_edit_page` | `sessions-goalkeeper-task-edit` | `csrf_exempt; login_required` |
| football/urls.py | 233 | `coach/sesiones/preparacion-fisica/tareas/nueva/` | `views.sessions_fitness_task_create_page` | `sessions-fitness-task-create` | `csrf_exempt; login_required` |
| football/urls.py | 234 | `coach/sesiones/preparacion-fisica/tareas/<int:task_id>/editar/` | `views.sessions_fitness_task_edit_page` | `sessions-fitness-task-edit` | `csrf_exempt; login_required` |
| football/urls.py | 255 | `coach/analisis/video/informe/<int:report_id>/export/pptx/` | `views.analysis_video_report_export_pptx` | `analysis-video-report-export-pptx` | `csrf_exempt; login_required; require_POST` |
| football/urls.py | 259 | `coach/analisis/video/informe/item/<int:item_id>/pizarra/video/upload/` | `views.analysis_video_report_item_tactical_video_upload_api` | `analysis-video-report-item-tactical-video-upload-api` | `csrf_exempt; login_required; require_POST` |
