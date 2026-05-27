from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .event_taxonomy import normalize_label
from . import permissions, workspace_context
from .models import (
    AcademyAssignment,
    AcademyLesson,
    AcademyLessonStep,
    AcademyProgress,
    AcademyQuizOption,
)


CATEGORY_RANK = {
    AcademyLesson.CATEGORY_BABY: 0,
    AcademyLesson.CATEGORY_PREBENJAMIN: 1,
    AcademyLesson.CATEGORY_BENJAMIN: 2,
    AcademyLesson.CATEGORY_ALEVIN: 3,
    AcademyLesson.CATEGORY_INFANTIL: 4,
    AcademyLesson.CATEGORY_CADETE: 5,
    AcademyLesson.CATEGORY_JUVENIL: 6,
    AcademyLesson.CATEGORY_SENIOR: 7,
}


def _category_key_from_label(label: str) -> str:
    raw = normalize_label(label or "")
    if not raw:
        return AcademyLesson.CATEGORY_SENIOR
    if "baby" in raw:
        return AcademyLesson.CATEGORY_BABY
    if "preben" in raw or "pre ben" in raw or "pre-ben" in raw:
        return AcademyLesson.CATEGORY_PREBENJAMIN
    if "benj" in raw:
        return AcademyLesson.CATEGORY_BENJAMIN
    if "alev" in raw:
        return AcademyLesson.CATEGORY_ALEVIN
    if "infant" in raw:
        return AcademyLesson.CATEGORY_INFANTIL
    if "cadet" in raw:
        return AcademyLesson.CATEGORY_CADETE
    if "juven" in raw:
        return AcademyLesson.CATEGORY_JUVENIL
    if "senior" in raw or "sénior" in raw:
        return AcademyLesson.CATEGORY_SENIOR
    # Fallback: si no coincide, lo tratamos como categoría mayor para no “capar” contenido.
    return AcademyLesson.CATEGORY_SENIOR


def _rank_for_category_key(key: str) -> int:
    return int(CATEGORY_RANK.get(str(key or "").strip().lower(), 7))


def _lesson_matches_team(lesson: AcademyLesson, team) -> bool:
    team_key = _category_key_from_label(str(getattr(team, "category", "") or ""))
    team_rank = _rank_for_category_key(team_key)
    min_rank = _rank_for_category_key(lesson.min_category)
    max_rank = _rank_for_category_key(lesson.max_category)
    return min_rank <= team_rank <= max_rank


def _forbid_if_academy_disabled(request):
    return permissions.forbid_if_workspace_module_disabled(request, "academy", label="academia")


def _active_scope(request):
    workspace = workspace_context.get_active_workspace(request)
    team = workspace_context.get_active_team_for_request(request)
    return workspace, team


@dataclass(frozen=True)
class _LessonCard:
    lesson: AcademyLesson
    assignment: AcademyAssignment | None
    status: str
    correct_count: int
    answer_count: int


@login_required
@require_GET
def academy_home_page(request):
    forbidden = _forbid_if_academy_disabled(request)
    if forbidden:
        return forbidden
    workspace, team = _active_scope(request)
    if not workspace or not team:
        # Sin contexto no es usable.
        try:
            return redirect(reverse("dashboard-home"))
        except Exception:
            return redirect("/")

    assignments = list(
        AcademyAssignment.objects.filter(workspace=workspace, is_active=True, lesson__is_published=True)
        .filter(Q(team__isnull=True) | Q(team=team))
        .select_related("lesson")
        .order_by("-created_at", "-id")[:25]
    )
    assignment_lesson_ids = [int(a.lesson_id) for a in assignments if getattr(a, "lesson_id", None)]
    progresses = list(
        AcademyProgress.objects.filter(workspace=workspace, user=request.user, lesson_id__in=assignment_lesson_ids)
        .select_related("lesson", "assignment")
        .order_by("-updated_at")[:60]
    )
    progress_by_lesson_id = {int(p.lesson_id): p for p in progresses if getattr(p, "lesson_id", None)}

    cards = []
    for ass in assignments:
        lesson = ass.lesson
        progress = progress_by_lesson_id.get(int(lesson.id))
        status = str(getattr(progress, "status", "") or AcademyProgress.STATUS_NOT_STARTED)
        cards.append(
            _LessonCard(
                lesson=lesson,
                assignment=ass,
                status=status,
                correct_count=int(getattr(progress, "correct_count", 0) or 0),
                answer_count=int(getattr(progress, "answer_count", 0) or 0),
            )
        )

    # Recomendadas: publicadas y válidas para categoría.
    recommended = []
    try:
        candidates = list(AcademyLesson.objects.filter(is_published=True).order_by("-updated_at", "-id")[:60])
        for lesson in candidates:
            if int(lesson.id) in progress_by_lesson_id:
                continue
            if not _lesson_matches_team(lesson, team):
                continue
            recommended.append(lesson)
            if len(recommended) >= 10:
                break
    except Exception:
        recommended = []

    # Biblioteca (sistema): catálogo completo filtrado por categoría, agrupado por tags.
    query = str(request.GET.get("q") or "").strip()
    library_sections = []
    library_results = []
    try:
        all_lessons = list(AcademyLesson.objects.filter(is_published=True).order_by("title", "id")[:800])
        filtered = []
        q_low = query.casefold()
        for lesson in all_lessons:
            if not _lesson_matches_team(lesson, team):
                continue
            title = str(getattr(lesson, "title", "") or "")
            summary = str(getattr(lesson, "summary", "") or "")
            if q_low and (q_low not in title.casefold()) and (q_low not in summary.casefold()):
                continue
            filtered.append(lesson)

        buckets = {
            "Metodología": ["metodologia", "didactica", "constraints", "sesion", "planificacion"],
            "Ataque": ["ataque", "progresion", "salida", "finalizacion", "amplitud", "profundidad", "cambio_orientacion"],
            "Defensa": ["defensa", "zona", "presion", "bloque", "bloque_medio", "centros", "area"],
            "Transición": ["transicion", "perdida", "recuperacion", "contrapresion", "repliegue"],
            "ABP": ["abp", "corner", "falta_lateral", "banda", "penalti"],
            "Porteros": ["portero", "porteros", "gk"],
            "Partido": ["partido", "match", "descanso", "plan", "ajustes"],
            "Entorno": ["entorno", "motivacion", "valores", "safeguarding", "seguridad"],
            "Físico": ["fisico", "prevencion", "calentamiento", "fuerza"],
        }
        used_ids = set()
        for section_title, tags in buckets.items():
            rows = []
            for lesson in filtered:
                if int(lesson.id) in used_ids:
                    continue
                lesson_tags = getattr(lesson, "tags", None)
                if not isinstance(lesson_tags, list):
                    lesson_tags = []
                low_tags = [str(t or "").casefold() for t in lesson_tags if str(t or "").strip()]
                if any(tag in low_tags for tag in tags):
                    rows.append(lesson)
                    used_ids.add(int(lesson.id))
                if len(rows) >= 18:
                    break
            if rows:
                library_sections.append({"title": section_title, "lessons": rows})
        others = [lesson for lesson in filtered if int(lesson.id) not in used_ids]
        if others:
            library_sections.append({"title": "Otros", "lessons": others[:18]})
        library_results = filtered[:120] if q_low else []
    except Exception:
        library_sections = []
        library_results = []

    return render(
        request,
        "football/academy_home.html",
        {
            "academy_cards": cards,
            "academy_recommended": recommended,
            "academy_library_sections": library_sections,
            "academy_query": query,
            "academy_library_results": library_results,
            "academy_team": team,
            "academy_workspace": workspace,
            "now": timezone.now(),
        },
    )


@login_required
@require_GET
def academy_lesson_page(request, lesson_id: int):
    forbidden = _forbid_if_academy_disabled(request)
    if forbidden:
        return forbidden
    workspace, team = _active_scope(request)
    if not workspace or not team:
        return redirect("/")

    lesson = get_object_or_404(AcademyLesson, id=int(lesson_id))
    if not bool(getattr(lesson, "is_published", False)):
        # Para MVP: si no está publicada, solo permitir a admins/gestión.
        try:
            if not workspace_context.can_access_platform(request.user):
                return HttpResponse("Lección no publicada.", status=404)
        except Exception:
            return HttpResponse("Lección no publicada.", status=404)

    steps = list(
        AcademyLessonStep.objects.filter(lesson=lesson)
        .select_related("media")
        .prefetch_related("quiz_questions__options")
        .order_by("order", "id")
    )

    progress, _created = AcademyProgress.objects.get_or_create(
        workspace=workspace,
        user=request.user,
        lesson=lesson,
        defaults={
            "team": team,
            "status": AcademyProgress.STATUS_IN_PROGRESS,
            "started_at": timezone.now(),
        },
    )
    if progress.status == AcademyProgress.STATUS_NOT_STARTED:
        progress.status = AcademyProgress.STATUS_IN_PROGRESS
        progress.started_at = progress.started_at or timezone.now()
        progress.save(update_fields=["status", "started_at", "updated_at"])

    return render(
        request,
        "football/academy_lesson.html",
        {
            "lesson": lesson,
            "steps": steps,
            "progress": progress,
            "academy_team": team,
            "academy_workspace": workspace,
        },
    )


@login_required
@require_GET
def academy_today_api(request):
    forbidden = _forbid_if_academy_disabled(request)
    if forbidden:
        return JsonResponse({"ok": False, "error": "Academia no está activa."}, status=403)
    workspace, team = _active_scope(request)
    if not workspace or not team:
        return JsonResponse({"ok": False, "error": "Sin contexto de club/equipo."}, status=400)

    assignments = list(
        AcademyAssignment.objects.filter(workspace=workspace, is_active=True, lesson__is_published=True)
        .filter(Q(team__isnull=True) | Q(team=team))
        .select_related("lesson")
        .order_by("-created_at", "-id")[:25]
    )
    lesson_ids = [int(a.lesson_id) for a in assignments if getattr(a, "lesson_id", None)]
    progresses = list(
        AcademyProgress.objects.filter(workspace=workspace, user=request.user, lesson_id__in=lesson_ids)
        .order_by("-updated_at")[:60]
    )
    progress_by_lesson_id = {int(p.lesson_id): p for p in progresses if getattr(p, "lesson_id", None)}

    rows = []
    for ass in assignments:
        lesson = ass.lesson
        progress = progress_by_lesson_id.get(int(lesson.id))
        rows.append(
            {
                "assignment_id": int(ass.id),
                "lesson_id": int(lesson.id),
                "title": str(ass.title_override or lesson.title or "").strip(),
                "summary": str(lesson.summary or "").strip(),
                "status": str(getattr(progress, "status", "") or AcademyProgress.STATUS_NOT_STARTED),
                "answer_count": int(getattr(progress, "answer_count", 0) or 0),
                "correct_count": int(getattr(progress, "correct_count", 0) or 0),
                "url": reverse("academy-lesson", kwargs={"lesson_id": int(lesson.id)}),
            }
        )

    return JsonResponse({"ok": True, "items": rows})


@login_required
@require_POST
def academy_answer_api(request):
    forbidden = _forbid_if_academy_disabled(request)
    if forbidden:
        return JsonResponse({"ok": False, "error": "Academia no está activa."}, status=403)
    workspace, team = _active_scope(request)
    if not workspace or not team:
        return JsonResponse({"ok": False, "error": "Sin contexto de club/equipo."}, status=400)

    try:
        lesson_id = int(request.POST.get("lesson_id") or 0)
        question_id = int(request.POST.get("question_id") or 0)
        option_id = int(request.POST.get("option_id") or 0)
    except Exception:
        return JsonResponse({"ok": False, "error": "Parámetros inválidos."}, status=400)
    if not lesson_id or not question_id or not option_id:
        return JsonResponse({"ok": False, "error": "Faltan parámetros."}, status=400)

    option = get_object_or_404(AcademyQuizOption, id=int(option_id), question_id=int(question_id))
    lesson = get_object_or_404(AcademyLesson, id=int(lesson_id))

    progress, _created = AcademyProgress.objects.get_or_create(
        workspace=workspace,
        user=request.user,
        lesson=lesson,
        defaults={"team": team, "status": AcademyProgress.STATUS_IN_PROGRESS, "started_at": timezone.now()},
    )
    answers = dict(getattr(progress, "answers", None) or {})
    key = str(question_id)
    already_answered = key in answers
    answers[key] = int(option.id)

    if not already_answered:
        progress.answer_count = int(getattr(progress, "answer_count", 0) or 0) + 1
        if bool(getattr(option, "is_correct", False)):
            progress.correct_count = int(getattr(progress, "correct_count", 0) or 0) + 1

    progress.answers = answers
    progress.status = progress.status or AcademyProgress.STATUS_IN_PROGRESS
    if progress.status == AcademyProgress.STATUS_NOT_STARTED:
        progress.status = AcademyProgress.STATUS_IN_PROGRESS
        progress.started_at = progress.started_at or timezone.now()

    progress.save(update_fields=["answers", "answer_count", "correct_count", "status", "started_at", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "is_correct": bool(option.is_correct),
            "feedback": str(option.feedback or "").strip(),
            "answer_count": int(progress.answer_count),
            "correct_count": int(progress.correct_count),
        }
    )


@login_required
@require_POST
def academy_complete_api(request):
    forbidden = _forbid_if_academy_disabled(request)
    if forbidden:
        return JsonResponse({"ok": False, "error": "Academia no está activa."}, status=403)
    workspace, team = _active_scope(request)
    if not workspace or not team:
        return JsonResponse({"ok": False, "error": "Sin contexto de club/equipo."}, status=400)

    try:
        lesson_id = int(request.POST.get("lesson_id") or 0)
    except Exception:
        lesson_id = 0
    if not lesson_id:
        return JsonResponse({"ok": False, "error": "Falta lesson_id."}, status=400)

    lesson = get_object_or_404(AcademyLesson, id=int(lesson_id))
    progress, _created = AcademyProgress.objects.get_or_create(
        workspace=workspace,
        user=request.user,
        lesson=lesson,
        defaults={"team": team, "status": AcademyProgress.STATUS_IN_PROGRESS, "started_at": timezone.now()},
    )
    if progress.status != AcademyProgress.STATUS_COMPLETED:
        progress.status = AcademyProgress.STATUS_COMPLETED
        progress.completed_at = timezone.now()
        if not progress.started_at:
            progress.started_at = progress.completed_at
        progress.save(update_fields=["status", "completed_at", "started_at", "updated_at"])

    return JsonResponse({"ok": True, "status": progress.status, "completed_at": progress.completed_at.isoformat() if progress.completed_at else ""})
