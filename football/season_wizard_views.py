import logging
import re
from datetime import date
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from . import task_library_services
from . import workspace_context
from .host_redirects import redirect_to_app_host_if_landing
from .models import (
    Player,
    Team,
    Workspace,
    WorkspaceCompetitionContext,
    WorkspaceSeason,
    WorkspaceSeasonPhase,
    WorkspaceSeasonPlayer,
    WorkspaceTeam,
)
from .ops_logging import log_exception
from .query_helpers import _normalize_team_lookup_key
from .season_history_services import (
    close_workspace_season,
    ensure_active_workspace_team_seasons,
    ensure_season_team,
    ensure_team_roster_season_memberships,
    open_workspace_season,
)
from .season_wizard import build_questionnaire_rating_summary, parse_questionnaire_ratings
from .services import _parse_int

logger = logging.getLogger(__name__)


@login_required
def club_season_wizard(request):
    """
    Wizard de cierre de temporada del club:
    1) Cerrar temporada activa -> histórico
    2) Descargar informes PDF de jugadores 1 a 1
    3) Configurar nueva temporada + fases
    """
    redirect_response = redirect_to_app_host_if_landing(request, path='/onboarding/season/')
    if redirect_response:
        return redirect_response

    workspace = workspace_context.get_active_workspace(request)
    if not workspace or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return HttpResponse('Selecciona un club (workspace) antes de cerrar la temporada.', status=400)
    if not workspace_context.can_manage_workspace(request.user, workspace):
        return HttpResponse('No tienes permisos para cerrar la temporada de este club.', status=403)

    step = str(request.GET.get('step') or '').strip().lower() or 'close'
    if step not in {'close', 'reports', 'new', 'questionnaire'}:
        step = 'close'

    # Temporada activa (si existe).
    active_club_season = None
    try:
        active_club_season = getattr(workspace, 'active_season', None)
        if active_club_season and getattr(active_club_season, 'is_active', True) is False:
            active_club_season = None
    except Exception:
        active_club_season = None

    def _club_group_workspaces(root_workspace):
        group = [root_workspace]
        if not root_workspace or getattr(root_workspace, 'kind', None) != Workspace.KIND_CLUB:
            return group
        root_key = _normalize_team_lookup_key(getattr(root_workspace, 'name', '') or '')
        if not root_key:
            return group
        try:
            candidates = list(
                Workspace.objects
                .filter(kind=Workspace.KIND_CLUB)
                .exclude(id=root_workspace.id)
                .select_related('primary_team', 'active_season')
                .only('id', 'name', 'slug', 'notes', 'primary_team_id', 'active_season_id')
            )
        except Exception:
            candidates = []
        for candidate in candidates:
            candidate_name = str(getattr(candidate, 'name', '') or '').strip()
            candidate_notes = str(getattr(candidate, 'notes', '') or '').strip()
            source_match = re.search(r'Separado automáticamente desde\s+(.+?)(?:\.|$)', candidate_notes, flags=re.IGNORECASE)
            source_key = _normalize_team_lookup_key(source_match.group(1).strip()) if source_match else ''
            split_parent_key = _normalize_team_lookup_key(candidate_name.split('·', 1)[0].strip()) if '·' in candidate_name else ''
            if root_key and root_key in {source_key, split_parent_key}:
                group.append(candidate)
        return group

    def _club_rollover_teams(root_workspace):
        group_workspaces = _club_group_workspaces(root_workspace)
        group_ids = [int(item.id) for item in group_workspaces if getattr(item, 'id', None)]
        seen = set()
        resolved = []
        try:
            links = (
                WorkspaceTeam.objects
                .filter(workspace_id__in=group_ids)
                .select_related('workspace', 'team')
                .order_by('workspace_id', '-is_default', 'id')
            )
        except Exception:
            links = []
        for link in links:
            team = getattr(link, 'team', None)
            team_id = int(getattr(team, 'id', 0) or 0)
            if not team_id or team_id in seen:
                continue
            seen.add(team_id)
            resolved.append(team)
        fallback_team = getattr(root_workspace, 'primary_team', None)
        fallback_id = int(getattr(fallback_team, 'id', 0) or 0)
        if fallback_id and fallback_id not in seen:
            resolved.insert(0, fallback_team)
        return group_workspaces, resolved

    def _player_ids_for_teams(team_list):
        team_ids = [int(getattr(team, 'id', 0) or 0) for team in (team_list or []) if getattr(team, 'id', None)]
        if not team_ids:
            return []
        return list(
            Player.objects
            .filter(team_id__in=team_ids)
            .order_by('team__name', 'number', 'name', 'id')
            .values_list('id', flat=True)
        )

    # Equipos/categorías del club, incluyendo workspaces legacy agrupados bajo el club.
    workspace_group_members, teams = _club_rollover_teams(workspace)
    teams_by_id = {int(team.id): team for team in teams if getattr(team, 'id', None)}
    active_team = workspace_context.get_active_team_for_request(request) or getattr(workspace, 'primary_team', None)
    if active_team and int(getattr(active_team, 'id', 0) or 0) not in teams_by_id:
        active_team = getattr(workspace, 'primary_team', None)
    if active_team and int(getattr(active_team, 'id', 0) or 0) not in teams_by_id:
        active_team = None
    if not active_team and teams:
        active_team = teams[0]

    def _parse_date(value):
        raw = str(value or '').strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except Exception:
            return None

    def _get_state_map():
        raw = request.session.get('season_wizard_state:v1') if hasattr(request, 'session') else None
        return raw if isinstance(raw, dict) else {}

    def _get_state():
        raw = _get_state_map()
        state = raw.get(str(int(workspace.id))) if isinstance(raw, dict) else None
        return state if isinstance(state, dict) else {}

    def _save_state(state):
        if not hasattr(request, 'session'):
            return
        raw = _get_state_map()
        raw = dict(raw) if isinstance(raw, dict) else {}
        raw[str(int(workspace.id))] = dict(state or {})
        request.session['season_wizard_state:v1'] = raw

    def _clear_state():
        if not hasattr(request, 'session'):
            return
        raw = _get_state_map()
        if not isinstance(raw, dict):
            return
        raw.pop(str(int(workspace.id)), None)
        request.session['season_wizard_state:v1'] = raw

    state = _get_state()
    message = ''
    error = ''

    if request.method == 'POST':
        action = str(request.POST.get('action') or '').strip().lower()
        try:
            if action == 'close_season':
                if not active_club_season:
                    raise ValueError('No hay temporada activa para cerrar.')
                end_date = _parse_date(request.POST.get('season_end_date')) or timezone.localdate()
                closed = close_workspace_season(workspace, season=active_club_season, end_date=end_date)

                closed_ids = [int(closed.id)]
                for grouped_workspace in workspace_group_members:
                    if int(getattr(grouped_workspace, 'id', 0) or 0) == int(workspace.id):
                        continue
                    grouped_season = getattr(grouped_workspace, 'active_season', None)
                    if grouped_season and bool(getattr(grouped_season, 'is_active', True)):
                        try:
                            grouped_closed = close_workspace_season(grouped_workspace, season=grouped_season, end_date=end_date)
                            closed_ids.append(int(grouped_closed.id))
                        except Exception:
                            pass

                # Preparar listado de jugadores para informes de todas las categorías del club.
                report_team_ids = [int(getattr(team, 'id', 0) or 0) for team in teams if getattr(team, 'id', None)]
                player_ids = _player_ids_for_teams(teams)

                state = {
                    'closed_season_id': int(closed.id),
                    'closed_season_ids': closed_ids,
                    'report_team_id': int(getattr(active_team, 'id', 0) or 0),
                    'report_team_ids': report_team_ids,
                    'player_ids': [int(pid) for pid in player_ids if pid],
                    'player_idx': 0,
                }
                _save_state(state)
                return redirect(f"{reverse('club-season-wizard')}?step=reports")

            if action == 'reports_set_team':
                report_team_ids = [int(getattr(team, 'id', 0) or 0) for team in teams if getattr(team, 'id', None)]
                if not report_team_ids:
                    raise ValueError('No hay categorías del club para generar informes.')
                player_ids = _player_ids_for_teams(teams)
                state = dict(state or {})
                state['report_team_id'] = int(getattr(active_team, 'id', 0) or 0)
                state['report_team_ids'] = report_team_ids
                state['player_ids'] = [int(pid) for pid in player_ids if pid]
                state['player_idx'] = 0
                _save_state(state)
                return redirect(f"{reverse('club-season-wizard')}?step=reports")

            if action in {'reports_prev', 'reports_next', 'reports_skip'}:
                state = dict(state or {})
                idx = int(_parse_int(state.get('player_idx')) or 0)
                total = len(state.get('player_ids') or [])
                if action == 'reports_prev':
                    idx = max(0, idx - 1)
                else:
                    idx = min(max(total - 1, 0), idx + 1) if total else 0
                state['player_idx'] = idx
                _save_state(state)
                return redirect(f"{reverse('club-season-wizard')}?step=reports")

            if action == 'goto_new_season':
                return redirect(f"{reverse('club-season-wizard')}?step=new")

            if action in {'questionnaire_prev', 'questionnaire_next', 'questionnaire_skip'}:
                state = dict(state or {})
                idx = int(_parse_int(state.get('q_player_idx')) or 0)
                ids = [int(pid) for pid in (state.get('q_player_ids') or []) if _parse_int(pid)]
                total = len(ids)
                if action == 'questionnaire_prev':
                    idx = max(0, idx - 1)
                else:
                    idx = min(max(total - 1, 0), idx + 1) if total else 0
                state['q_player_idx'] = idx
                _save_state(state)
                return redirect(f"{reverse('club-season-wizard')}?step=questionnaire")

            if action in {'questionnaire_save', 'questionnaire_save_next', 'questionnaire_finish'}:
                state = dict(state or {})
                season_id = int(_parse_int(state.get('new_season_id')) or 0) or int(getattr(getattr(workspace, 'active_season', None), 'id', 0) or 0)
                if not season_id:
                    raise ValueError('No hay temporada activa para guardar el cuestionario.')
                membership_id = int(_parse_int(request.POST.get('membership_id')) or 0)
                if not membership_id:
                    raise ValueError('Falta el jugador de temporada para guardar el cuestionario.')
                membership = WorkspaceSeasonPlayer.objects.filter(id=int(membership_id), season_id=int(season_id)).select_related('player').first()
                if not membership:
                    raise ValueError('No se encontró el jugador en la temporada seleccionada.')

                def _clean_text(field, *, max_len=800):
                    return task_library_services.sanitize_task_text((request.POST.get(field) or '').strip(), multiline=True, max_len=max_len)

                role_pref = str(request.POST.get('q_role_pref') or '').strip()
                if role_pref and role_pref not in {'titular', 'rotacion', 'revulsivo', 'desarrollo', 'otro'}:
                    role_pref = ''
                foot = str(request.POST.get('q_foot') or '').strip()
                if foot and foot not in {'der', 'izq', 'amb'}:
                    foot = ''
                motivation = _parse_int(request.POST.get('q_motivation'))
                if motivation is not None:
                    try:
                        motivation = max(1, min(5, int(motivation)))
                    except Exception:
                        motivation = None

                questionnaire = dict(getattr(membership, 'questionnaire', None) or {})
                ratings = parse_questionnaire_ratings(request.POST)
                rating_summary = build_questionnaire_rating_summary({'ratings': ratings})
                questionnaire.update({
                    'role_pref': role_pref,
                    'position_secondary': _clean_text('q_position_secondary', max_len=120),
                    'foot': foot,
                    'motivation_1_5': int(motivation) if motivation is not None else None,
                    'strengths': _clean_text('q_strengths', max_len=700),
                    'improve': _clean_text('q_improve', max_len=700),
                    'objective_main': _clean_text('q_objective_main', max_len=700),
                    'availability_notes': _clean_text('q_availability', max_len=500),
                    'ratings': ratings,
                    'ratings_average': rating_summary['overall'],
                    'ratings_category': rating_summary['category'],
                })
                questionnaire = {k: v for k, v in questionnaire.items() if v not in (None, '', [])}
                membership.questionnaire_v = max(2, int(getattr(membership, 'questionnaire_v', 1) or 1))
                membership.questionnaire = questionnaire
                membership.questionnaire_completed_at = timezone.now()
                membership.save(update_fields=['questionnaire_v', 'questionnaire', 'questionnaire_completed_at', 'updated_at'])

                if action == 'questionnaire_finish':
                    _clear_state()
                    return redirect(f"{reverse('club-onboarding')}?season_created=1")

                if action == 'questionnaire_save_next':
                    ids = [int(pid) for pid in (state.get('q_player_ids') or []) if _parse_int(pid)]
                    idx = int(_parse_int(state.get('q_player_idx')) or 0)
                    total = len(ids)
                    idx = min(max(total - 1, 0), idx + 1) if total else 0
                    state['q_player_idx'] = idx
                    _save_state(state)
                    return redirect(f"{reverse('club-season-wizard')}?step=questionnaire")

                message = 'Cuestionario guardado.'

            if action == 'create_new_season':
                season_label = task_library_services.sanitize_task_text((request.POST.get('season_label') or '').strip(), multiline=False, max_len=32)
                start_date = _parse_date(request.POST.get('season_start_date'))
                if not season_label:
                    raise ValueError('Etiqueta de temporada obligatoria.')
                if not start_date:
                    raise ValueError('Fecha de inicio obligatoria.')

                reconvert_team = str(request.POST.get('reconvert_team') or '').strip().lower() in {'1', 'true', 'on', 'yes', 'si'}
                team_name_new = task_library_services.sanitize_task_text((request.POST.get('team_name_new') or '').strip(), multiline=False, max_len=150)
                team_category_new = task_library_services.sanitize_task_text((request.POST.get('team_category_new') or '').strip(), multiline=False, max_len=24)
                team_game_format_new = str(request.POST.get('team_game_format_new') or '').strip().lower()
                if team_game_format_new and team_game_format_new not in {Team.GAME_FORMAT_F7, Team.GAME_FORMAT_F11}:
                    team_game_format_new = ''
                reset_competition_context = str(request.POST.get('reset_competition_context') or '').strip().lower() in {'1', 'true', 'on', 'yes', 'si'}

                new_season = open_workspace_season(
                    workspace=workspace,
                    label=season_label,
                    start_date=start_date,
                    team=active_team,
                    inherit_teams=False,
                    inherit_roster=False,
                )

                # Reconversión del equipo activo (sin crear Team nuevo): subir de categoría, renombrar, etc.
                # Nota: afecta a cómo se muestra el equipo en navegación; el histórico del club se mantiene por WorkspaceSeason.
                try:
                    if reconvert_team and active_team:
                        update_fields = []
                        if team_name_new and team_name_new != str(getattr(active_team, 'name', '') or '').strip():
                            active_team.name = team_name_new
                            active_team.short_name = team_name_new[:60]
                            update_fields.extend(['name', 'short_name'])
                        if team_category_new and team_category_new != str(getattr(active_team, 'category', '') or '').strip():
                            active_team.category = team_category_new
                            update_fields.append('category')
                        if team_game_format_new and team_game_format_new != str(getattr(active_team, 'game_format', '') or '').strip():
                            active_team.game_format = team_game_format_new
                            update_fields.append('game_format')
                        if update_fields:
                            active_team.save(update_fields=sorted(set(update_fields)))

                        # Si el equipo cambia de categoría/competición, conviene resetear claves externas para reconfigurar.
                        if reset_competition_context:
                            try:
                                context = WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=active_team).first()
                            except Exception:
                                context = None
                            if context:
                                context.group = None
                                context.season = None
                                context.external_competition_key = ''
                                context.external_group_key = ''
                                context.external_team_key = ''
                                if team_name_new:
                                    context.external_team_name = team_name_new
                                context.external_source_url = ''
                                context.sync_status = WorkspaceCompetitionContext.STATUS_PENDING
                                context.sync_error = ''
                                context.save(update_fields=[
                                    'group',
                                    'season',
                                    'external_competition_key',
                                    'external_group_key',
                                    'external_team_key',
                                    'external_team_name',
                                    'external_source_url',
                                    'sync_status',
                                    'sync_error',
                                    'updated_at',
                                ])
                        else:
                            # Mantener claves, pero si renombramos, al menos ajustar el nombre externo para búsquedas.
                            if team_name_new:
                                try:
                                    context = WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=active_team).first()
                                except Exception:
                                    context = None
                                if context and str(getattr(context, 'external_team_name', '') or '').strip() != team_name_new:
                                    context.external_team_name = team_name_new
                                    context.sync_status = WorkspaceCompetitionContext.STATUS_PENDING
                                    context.sync_error = ''
                                    context.save(update_fields=['external_team_name', 'sync_status', 'sync_error', 'updated_at'])
                except Exception:
                    pass

                # Registra qué categorías participan en la nueva temporada del club y hereda sus plantillas
                # como pendientes de confirmar. También consolida enlaces legacy en el workspace principal.
                season_teams = teams or ([active_team] if active_team else [])
                for season_team in season_teams:
                    if not season_team:
                        continue
                    try:
                        WorkspaceTeam.objects.get_or_create(
                            workspace=workspace,
                            team=season_team,
                            defaults={'is_default': int(getattr(season_team, 'id', 0) or 0) == int(getattr(active_team, 'id', 0) or 0)},
                        )
                    except Exception:
                        pass
                    ensure_season_team(new_season, season_team)
                    ensure_team_roster_season_memberships(new_season, season_team, include_inactive=True)
                ensure_active_workspace_team_seasons(workspace, season=new_season)

                player_ids = _player_ids_for_teams(season_teams)

                # Fases (opcionales).
                phases = []
                phase_specs = [
                    (WorkspaceSeasonPhase.KEY_RECRUITMENT, 'Captación', 10),
                    (WorkspaceSeasonPhase.KEY_PRESEASON, 'Pretemporada', 20),
                    (WorkspaceSeasonPhase.KEY_REGULAR, 'Temporada regular', 30),
                    (WorkspaceSeasonPhase.KEY_PLAYOFFS, 'Playoff / eliminatorias', 40),
                ]
                for key, label, order in phase_specs:
                    sd = _parse_date(request.POST.get(f'phase_{key}_start'))
                    ed = _parse_date(request.POST.get(f'phase_{key}_end'))
                    if not sd or not ed:
                        continue
                    if ed < sd:
                        raise ValueError(f'La fase "{label}" tiene fin anterior al inicio.')
                    phases.append(
                        WorkspaceSeasonPhase(
                            season=new_season,
                            key=key,
                            label=label,
                            start_date=sd,
                            end_date=ed,
                            sort_order=int(order),
                        )
                    )
                if phases:
                    WorkspaceSeasonPhase.objects.bulk_create(phases)

                # Estado para cuestionario (por jugador) en la nueva temporada.
                # Nota: no borramos el estado hasta que el usuario termine/omita el cuestionario.
                q_state = {
                    'new_season_id': int(new_season.id),
                    'q_player_ids': [int(pid) for pid in player_ids if pid],
                    'q_player_idx': 0,
                }
                _save_state(q_state)
                return redirect(f"{reverse('club-season-wizard')}?step=questionnaire")

        except ValueError as exc:
            error = str(exc)
        except Exception:
            log_exception(logger, 'No se pudo completar el cierre de temporada.', request, workspace=workspace, team=active_team, action=action)
            error = 'No se pudo completar el cierre de temporada.'

    # Defaults para formulario de nueva temporada.
    season_form = {'label': '', 'start_date': ''}
    try:
        today = timezone.localdate()
        next_start_year = today.year if (today.month, today.day) < (7, 1) else (today.year + 1)
        default_start = date(next_start_year, 7, 1)
        season_form['label'] = f'{next_start_year}/{next_start_year + 1}'
        season_form['start_date'] = default_start.isoformat()
    except Exception:
        season_form['label'] = ''
        season_form['start_date'] = ''

    # Estado para step reports.
    closed_season = None
    try:
        closed_id = _parse_int((state or {}).get('closed_season_id'))
        if closed_id:
            closed_season = WorkspaceSeason.objects.filter(id=int(closed_id), workspace=workspace).first()
    except Exception:
        closed_season = None

    report_team = None
    player_ids = []
    player_idx = 0
    current_player = None
    try:
        report_team_id = int(getattr(active_team, 'id', 0) or 0)
        if report_team_id and int(report_team_id) in teams_by_id:
            report_team = teams_by_id[int(report_team_id)]
        player_ids = [int(pid) for pid in ((state or {}).get('player_ids') or []) if _parse_int(pid)]
        player_idx = int(_parse_int((state or {}).get('player_idx')) or 0)
        if player_ids:
            player_idx = max(0, min(player_idx, len(player_ids) - 1))
            current_player = Player.objects.filter(id=int(player_ids[player_idx])).select_related('team').first()
            if current_player and int(getattr(getattr(current_player, 'team', None), 'id', 0) or 0) in teams_by_id:
                report_team = teams_by_id[int(current_player.team_id)]
    except Exception:
        report_team = report_team or active_team
        player_ids = []
        player_idx = 0
        current_player = None

    pdf_url = ''
    try:
        if current_player:
            params = {}
            if closed_season:
                params['club_season_id'] = str(int(closed_season.id))
            if params:
                pdf_url = f"{reverse('player-pdf', args=[int(current_player.id)])}?{urlencode(params)}"
            else:
                pdf_url = reverse('player-pdf', args=[int(current_player.id)])
    except Exception:
        pdf_url = ''

    # Estado para step questionnaire (nueva temporada).
    q_season = None
    q_memberships = []
    q_idx = 0
    q_total = 0
    q_membership = None
    q_rating_summary = build_questionnaire_rating_summary({})
    try:
        q_season_id = int(_parse_int((state or {}).get('new_season_id')) or 0) or int(getattr(getattr(workspace, 'active_season', None), 'id', 0) or 0)
        if q_season_id:
            q_season = WorkspaceSeason.objects.filter(id=int(q_season_id), workspace=workspace).first()
        if q_season:
            q_memberships = list(
                WorkspaceSeasonPlayer.objects
                .filter(season=q_season)
                .select_related('player')
                .order_by('player__number', 'player__name', 'player__id')
            )
            q_total = len(q_memberships)
            ids_from_state = [int(pid) for pid in ((state or {}).get('q_player_ids') or []) if _parse_int(pid)]
            if not ids_from_state:
                ids_from_state = [int(m.player_id) for m in q_memberships if getattr(m, 'player_id', None)]
                state = dict(state or {})
                state['new_season_id'] = int(q_season.id)
                state['q_player_ids'] = ids_from_state
                state['q_player_idx'] = 0
                _save_state(state)
            q_idx = int(_parse_int((state or {}).get('q_player_idx')) or 0)
            q_idx = max(0, min(q_idx, max(q_total - 1, 0))) if q_total else 0
            q_membership = q_memberships[q_idx] if q_total else None
            if q_membership:
                q_rating_summary = build_questionnaire_rating_summary(getattr(q_membership, 'questionnaire', None) or {})
    except Exception:
        q_season = None
        q_memberships = []
        q_idx = 0
        q_total = 0
        q_membership = None
        q_rating_summary = build_questionnaire_rating_summary({})

    return render(
        request,
        'football/season_wizard.html',
        {
            'workspace': workspace,
            'step': step,
            'active_club_season': active_club_season,
            'closed_season': closed_season,
            'teams': teams,
            'team_count': len(teams or []),
            'active_team': active_team,
            'report_team': report_team,
            'current_player': current_player,
            'player_idx': player_idx,
            'player_total': len(player_ids or []),
            'pdf_url': pdf_url,
            'season_form': season_form,
            'q_season': q_season,
            'q_membership': q_membership,
            'q_rating_summary': q_rating_summary,
            'q_idx': q_idx,
            'q_total': q_total,
            'error': error,
            'message': message,
        },
        status=200,
    )
