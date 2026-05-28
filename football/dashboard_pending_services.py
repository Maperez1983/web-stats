from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import AnalysisVideoReport, RivalAnalysisReport, TrainingSession


def build_team_pending_cards(primary_team, weekly_brief=None, weekly_brief_builder=None):
    if not primary_team:
        return []
    today = timezone.localdate()
    if not isinstance(weekly_brief, dict):
        weekly_brief = weekly_brief_builder(primary_team) if weekly_brief_builder else {}
    if not isinstance(weekly_brief, dict):
        weekly_brief = {}

    pending_cards = []

    def add_card(title, description, url, action):
        pending_cards.append(
            {
                'title': title,
                'description': description,
                'url': url,
                'action': action,
            }
        )

    if int(weekly_brief.get('convocated_count') or 0) <= 0:
        add_card(
            'Convocatoria pendiente',
            'Todavía no hay una convocatoria cerrada para el siguiente partido.',
            reverse('convocation'),
            'Abrir partido',
        )
    if int(weekly_brief.get('probable_eleven_count') or 0) <= 0:
        add_card(
            '11 inicial sin definir',
            'El partido no tiene todavía un 11 inicial o probable consolidado.',
            reverse('initial-eleven'),
            'Definir 11',
        )
    if int(weekly_brief.get('available_count') or 0) <= 0:
        add_card(
            'Disponibilidad sin consolidar',
            'La portada no tiene disponibilidad útil para leer la semana del equipo.',
            reverse('coach-role-trainer'),
            'Revisar estadísticas',
        )

    future_sessions = list(
        TrainingSession.objects
        .filter(microcycle__team=primary_team, session_date__gte=today)
        .prefetch_related('tasks')
        .order_by('session_date', 'id')[:6]
    )
    if not future_sessions:
        add_card(
            'Semana sin sesiones',
            'No hay sesiones futuras planificadas para sostener el microciclo actual.',
            reverse('sessions'),
            'Planificar semana',
        )
    elif not any(session.tasks.exists() for session in future_sessions):
        add_card(
            'Sesiones sin tareas',
            'Hay sesiones creadas, pero todavía no tienen tareas asociadas.',
            reverse('sessions') + '?tab=microcycles',
            'Completar sesiones',
        )

    next_match = weekly_brief.get('match') if isinstance(weekly_brief, dict) else {}
    rival_name = str(next_match.get('opponent') or '').strip() if isinstance(next_match, dict) else ''
    has_ready_manual_report = False
    has_any_pptx_report = False
    has_exported_pptx = False
    if rival_name:
        has_ready_manual_report = (
            RivalAnalysisReport.objects
            .filter(team=primary_team, status=RivalAnalysisReport.STATUS_READY)
            .filter(Q(rival_name__icontains=rival_name) | Q(rival_team__name__icontains=rival_name))
            .exists()
        )
        needle_q = _rival_report_needle_q(rival_name)
        has_any_pptx_report = AnalysisVideoReport.objects.filter(team=primary_team).filter(needle_q).exists()
        has_exported_pptx = (
            AnalysisVideoReport.objects
            .filter(team=primary_team)
            .filter(needle_q)
            .filter(pptx_file__isnull=False)
            .exclude(pptx_file='')
            .exists()
        )
    if rival_name and not (has_ready_manual_report or has_exported_pptx):
        subtitle = f'No hay un informe rival listo para {rival_name}.'
        if has_any_pptx_report and not has_exported_pptx:
            subtitle = f'Hay un informe rival creado para {rival_name}, pero falta exportar el PPTX.'
        add_card(
            'Informe rival pendiente',
            subtitle,
            reverse('analysis'),
            'Abrir análisis',
        )

    return pending_cards


def _rival_report_needle_q(needle: str) -> Q:
    value = (needle or '').strip()
    if not value:
        return Q(pk__in=[])
    short = value[:48]
    return (
        Q(folder__rival_team__name__icontains=short)
        | Q(folder__rival_team__short_name__icontains=short)
        | Q(title__icontains=short)
    )
