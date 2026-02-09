from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard_page, name='dashboard-home'),
    path('api/dashboard/', views.dashboard_data, name='dashboard-data'),
    path('api/dashboard/refresh/', views.refresh_scraping, name='dashboard-refresh'),
    path('players/', views.player_dashboard_page, name='player-dashboard'),
    path('coach/', views.coach_overview_page, name='coach-detail'),
    path('player/<int:player_id>/', views.player_detail_page, name='player-detail'),
    path('player/<int:player_id>/pdf/', views.player_pdf, name='player-pdf'),
    path('player/<int:player_id>/presentacion/', views.player_presentation, name='player-presentation'),
    path('player/<int:player_id>/match/<int:match_id>/', views.player_match_stats_page, name='player-match-stats'),
    path('match/<int:match_id>/', views.match_stats_page, name='match-stats'),
    path('incidencias/', views.incident_page, name='incident-page'),
    path('registro-acciones/', views.match_action_page, name='match-action-page'),
    path('registro-acciones/guardar/', views.register_match_action, name='match-action-record'),
    path('registro-acciones/eliminar/', views.delete_match_action, name='match-action-delete'),
    path('registro-acciones/finalizar/', views.finalize_match_actions, name='match-action-finalize'),
    path('convocatoria/', views.convocation_page, name='convocation'),
    path('convocatoria/save/', views.save_convocation, name='convocation-save'),
    path('coach/cards/', views.coach_cards_page, name='coach-cards'),
    path('coach/11-inicial/', views.initial_eleven_page, name='initial-eleven'),
    path('coach/sesiones/', views.sessions_page, name='sessions'),
    path('coach/multas/', views.fines_page, name='fines'),
    path('coach/analisis/', views.analysis_page, name='analysis'),
]
