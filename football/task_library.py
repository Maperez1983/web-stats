from __future__ import annotations

from collections import defaultdict
from datetime import date

from football.tag_catalog import normalize_tags


def prepare_task_library(
    tasks,
    *,
    parse_int,
    sanitize_text,
    analysis_confidence_scores,
    task_upload_date,
    extract_effective_reference_date,
    detect_keyword_tags,
    task_type_keywords,
    task_phase_keywords,
    players_band_label,
    estimate_players_count,
    duration_band_label,
    phase_folder_key_for_task,
    phase_folder_meta,
    coerce_reference_date,
    is_imported_task,
):
    context_groups = defaultdict(list)
    objective_groups = defaultdict(list)
    type_groups = defaultdict(list)
    phase_groups = defaultdict(list)
    phase_folder_groups = defaultdict(list)
    players_band_groups = defaultdict(list)
    duration_band_groups = defaultdict(list)
    date_groups = defaultdict(list)

    for task in tasks:
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        task.analysis_meta = analysis_meta
        task_sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
        task.task_sheet = task_sheet
        task.is_imported = is_imported_task(task)
        task.analysis_summary = sanitize_text(
            str(analysis_meta.get('summary') or '').strip(),
            multiline=True,
            max_len=900,
        )
        confidence = analysis_meta.get('confidence') if isinstance(analysis_meta.get('confidence'), dict) else {}
        if not confidence:
            confidence = analysis_confidence_scores(
                {
                    'title': task.title or '',
                    'objective': task.objective or '',
                    'coaching_points': task.coaching_points or '',
                    'confrontation_rules': task.confrontation_rules or '',
                    'summary': task.analysis_summary or '',
                    'exercise_types': analysis_meta.get('exercise_types')
                    if isinstance(analysis_meta.get('exercise_types'), list)
                    else [],
                    'phase_tags': analysis_meta.get('phase_tags')
                    if isinstance(analysis_meta.get('phase_tags'), list)
                    else [],
                    'task_sheet': task_sheet if isinstance(task_sheet, dict) else {},
                }
            )
        task.analysis_confidence = confidence
        task.needs_review = bool(analysis_meta.get('needs_review', False))
        if not analysis_meta.get('needs_review'):
            task.needs_review = int(confidence.get('overall') or 0) < 62
        task.detected_materials = (
            analysis_meta.get('detected_materials')
            if isinstance(analysis_meta.get('detected_materials'), list)
            else []
        )
        task.exercise_types = normalize_tags(
            (
                analysis_meta.get('exercise_types')
                if isinstance(analysis_meta.get('exercise_types'), list)
                else []
            )
        )
        task.phase_tags = normalize_tags(
            (
                analysis_meta.get('phase_tags')
                if isinstance(analysis_meta.get('phase_tags'), list)
                else []
            )
        )
        upload_date = task_upload_date(task)
        effective_reference_date = extract_effective_reference_date(task, analysis_meta=analysis_meta)
        task.reference_date = effective_reference_date or upload_date
        task.reference_date_iso = task.reference_date.isoformat() if task.reference_date else ''
        task.reference_date_is_detected = bool(effective_reference_date)
        if not task.exercise_types or not task.phase_tags:
            fallback_haystack = '\n'.join(
                [
                    str(task.title or ''),
                    str(task.objective or ''),
                    str(task.coaching_points or ''),
                    str(task.confrontation_rules or ''),
                    task.analysis_summary,
                    str(task_sheet.get('description') or ''),
                ]
            )
            if not task.exercise_types:
                task.exercise_types = detect_keyword_tags(fallback_haystack, task_type_keywords)
            if not task.phase_tags:
                task.phase_tags = detect_keyword_tags(fallback_haystack, task_phase_keywords)
        task.exercise_types = normalize_tags(task.exercise_types)
        task.phase_tags = normalize_tags(task.phase_tags)
        task.players_count_estimate = parse_int(analysis_meta.get('players_count_estimate'))
        task.players_band = str(analysis_meta.get('players_band') or '').strip()
        if not task.players_band and task.task_sheet:
            task.players_band = players_band_label(
                estimate_players_count(task.task_sheet.get('players') or '', task.title)
            )
        task.duration_band = str(analysis_meta.get('duration_band') or '').strip()
        if not task.duration_band:
            task.duration_band = duration_band_label(task.duration_minutes)
        objective_summary = sanitize_text(str(task.objective or '').strip(), multiline=False, max_len=180)
        if not objective_summary:
            objective_summary = sanitize_text(
                str(task_sheet.get('description') or '').strip(),
                multiline=True,
                max_len=240,
            )
        if not objective_summary:
            objective_summary = sanitize_text(
                str(analysis_meta.get('summary') or '').strip(),
                multiline=True,
                max_len=240,
            )
        task.objective_summary = objective_summary or 'Sin objetivo extraído todavía.'
        card_summary = str(
            task.analysis_summary or task_sheet.get('description') or task.objective_summary or ''
        ).strip()
        task.card_summary = sanitize_text(card_summary, multiline=True, max_len=280)
        for ctx in analysis_meta.get('work_contexts') or []:
            for norm in normalize_tags([str(ctx)]):
                context_groups[str(norm)].append(task)
        for obj in analysis_meta.get('objective_tags') or []:
            for norm in normalize_tags([str(obj)]):
                objective_groups[str(norm)].append(task)
        for exercise_type in task.exercise_types:
            type_groups[str(exercise_type)].append(task)
        for phase_tag in task.phase_tags:
            phase_groups[str(phase_tag)].append(task)
        task.phase_folder_key = phase_folder_key_for_task(task)
        phase_folder_groups[task.phase_folder_key].append(task)
        if task.players_band:
            players_band_groups[task.players_band].append(task)
        if task.duration_band:
            duration_band_groups[task.duration_band].append(task)
        if task.reference_date:
            date_groups[task.reference_date.isoformat()].append(task)

    context_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in context_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    objective_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in objective_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    type_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in type_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    phase_group_rows = [
        {
            'key': item['key'],
            'label': item['label'],
            'count': len(phase_folder_groups.get(item['key'], [])),
        }
        for item in phase_folder_meta
    ]
    players_band_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in players_band_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    duration_band_group_rows = sorted(
        [{'key': key, 'count': len(items)} for key, items in duration_band_groups.items()],
        key=lambda row: row['count'],
        reverse=True,
    )
    date_group_rows = []
    for key, items in date_groups.items():
        raw_key = str(key or '').strip()
        if not raw_key:
            continue
        parsed_key = coerce_reference_date(raw_key)
        date_group_rows.append(
            {
                'key': parsed_key.isoformat() if parsed_key else raw_key,
                'count': len(items),
                'label': parsed_key.strftime('%d/%m/%Y') if parsed_key else raw_key,
                'sort_date': parsed_key or date.min,
            }
        )
    date_group_rows.sort(
        key=lambda row: (row.get('sort_date') or date.min, str(row.get('key') or '')),
        reverse=True,
    )
    for row in date_group_rows:
        row.pop('sort_date', None)
    quality_group_rows = [
        {'key': 'review', 'label': 'Revisión necesaria', 'count': len([item for item in tasks if getattr(item, 'needs_review', False)])},
        {'key': 'validated', 'label': 'Validadas', 'count': len([item for item in tasks if not getattr(item, 'needs_review', False)])},
    ]

    return {
        'task_library': tasks,
        'context_group_rows': context_group_rows,
        'objective_group_rows': objective_group_rows,
        'type_group_rows': type_group_rows,
        'phase_group_rows': phase_group_rows,
        'players_band_group_rows': players_band_group_rows,
        'duration_band_group_rows': duration_band_group_rows,
        'date_group_rows': date_group_rows,
        'quality_group_rows': quality_group_rows,
    }


def filter_task_library(tasks, *, library_view, library_key):
    filtered = list(tasks)
    if library_view == 'phase' and library_key:
        filtered = [item for item in filtered if str(getattr(item, 'phase_folder_key', '') or '') == library_key]
    elif library_view == 'phase' and not library_key:
        filtered = []
    elif library_view == 'type' and library_key:
        filtered = [item for item in filtered if library_key in (item.exercise_types or [])]
    elif library_view == 'players' and library_key:
        filtered = [item for item in filtered if str(item.players_band or '') == library_key]
    elif library_view == 'duration' and library_key:
        filtered = [item for item in filtered if str(item.duration_band or '') == library_key]
    elif library_view == 'quality' and library_key:
        if library_key == 'review':
            filtered = [item for item in filtered if bool(getattr(item, 'needs_review', False))]
        elif library_key == 'validated':
            filtered = [item for item in filtered if not bool(getattr(item, 'needs_review', False))]
    elif library_view == 'date' and library_key:
        filtered = [item for item in filtered if str(getattr(item, 'reference_date_iso', '') or '') == library_key]

    filtered.sort(
        key=lambda item: (
            getattr(item, 'reference_date', None) or getattr(getattr(item, 'session', None), 'session_date', None) or date.min,
            int(getattr(item, 'id', 0) or 0),
        ),
        reverse=True,
    )
    return filtered


def filter_task_library_advanced(
    tasks,
    *,
    query: str = '',
    phase_keys=None,
    type_keys=None,
    context_keys=None,
    objective_keys=None,
    players_band: str = '',
    duration_band: str = '',
    quality: str = '',
    reference_date: str = '',
    sort_key: str = 'recent',
):
    filtered = list(tasks)
    q = str(query or '').strip().lower()
    phase_keys = [str(item).strip() for item in (phase_keys or []) if str(item).strip()]
    type_keys = [str(item).strip() for item in (type_keys or []) if str(item).strip()]
    context_keys = [str(item).strip() for item in (context_keys or []) if str(item).strip()]
    objective_keys = [str(item).strip() for item in (objective_keys or []) if str(item).strip()]
    players_band = str(players_band or '').strip()
    duration_band = str(duration_band or '').strip()
    quality = str(quality or '').strip()
    reference_date = str(reference_date or '').strip()

    if q:

        def _haystack(task):
            parts = [
                getattr(task, 'title', ''),
                getattr(task, 'objective', ''),
                getattr(task, 'objective_summary', ''),
                getattr(task, 'coaching_points', ''),
                getattr(task, 'confrontation_rules', ''),
                getattr(task, 'analysis_summary', ''),
            ]
            try:
                sheet = getattr(task, 'task_sheet', None) or {}
                if isinstance(sheet, dict):
                    parts.append(sheet.get('description') or '')
            except Exception:
                pass
            return '\n'.join([str(p or '') for p in parts]).lower()

        filtered = [item for item in filtered if q in _haystack(item)]

    if phase_keys:
        filtered = [item for item in filtered if str(getattr(item, 'phase_folder_key', '') or '') in phase_keys]

    if type_keys:
        filtered = [item for item in filtered if set(type_keys).intersection(set(item.exercise_types or []))]

    if context_keys:

        def _contexts(task):
            meta = getattr(task, 'analysis_meta', None) or {}
            if isinstance(meta, dict):
                raw = meta.get('work_contexts') or []
                if isinstance(raw, list):
                    return [str(x) for x in raw]
            return []

        filtered = [item for item in filtered if set(context_keys).intersection(set(_contexts(item)))]

    if objective_keys:

        def _objectives(task):
            meta = getattr(task, 'analysis_meta', None) or {}
            if isinstance(meta, dict):
                raw = meta.get('objective_tags') or []
                if isinstance(raw, list):
                    return [str(x) for x in raw]
            return []

        filtered = [item for item in filtered if set(objective_keys).intersection(set(_objectives(item)))]

    if players_band:
        filtered = [item for item in filtered if str(getattr(item, 'players_band', '') or '') == players_band]

    if duration_band:
        filtered = [item for item in filtered if str(getattr(item, 'duration_band', '') or '') == duration_band]

    if quality:
        if quality == 'review':
            filtered = [item for item in filtered if bool(getattr(item, 'needs_review', False))]
        elif quality == 'validated':
            filtered = [item for item in filtered if not bool(getattr(item, 'needs_review', False))]

    if reference_date:
        filtered = [item for item in filtered if str(getattr(item, 'reference_date_iso', '') or '') == reference_date]

    if sort_key == 'title':
        filtered.sort(key=lambda item: (str(getattr(item, 'title', '') or '').lower(), int(getattr(item, 'id', 0) or 0)))
        return filtered

    if sort_key == 'quality':
        def _score(item):
            meta = getattr(item, 'analysis_meta', None) or {}
            if isinstance(meta, dict):
                try:
                    return int(meta.get('quality_score') or 0)
                except Exception:
                    return 0
            return 0

        filtered.sort(
            key=lambda item: (
                _score(item),
                getattr(item, 'reference_date', None) or getattr(getattr(item, 'session', None), 'session_date', None) or date.min,
                int(getattr(item, 'id', 0) or 0),
            ),
            reverse=True,
        )
        return filtered

    if sort_key == 'confidence':
        def _conf(item):
            conf = getattr(item, 'analysis_confidence', None) or {}
            if isinstance(conf, dict):
                try:
                    return int(conf.get('overall') or 0)
                except Exception:
                    return 0
            return 0

        filtered.sort(
            key=lambda item: (
                _conf(item),
                getattr(item, 'reference_date', None) or getattr(getattr(item, 'session', None), 'session_date', None) or date.min,
                int(getattr(item, 'id', 0) or 0),
            ),
            reverse=True,
        )
        return filtered

    filtered.sort(
        key=lambda item: (
            getattr(item, 'reference_date', None) or getattr(getattr(item, 'session', None), 'session_date', None) or date.min,
            int(getattr(item, 'id', 0) or 0),
        ),
        reverse=True,
    )
    return filtered


def suggest_related_tasks(tasks, base_task, *, limit: int = 8):
    base_id = int(getattr(base_task, 'id', 0) or 0)
    base_types = set(getattr(base_task, 'exercise_types', None) or [])
    base_phases = set(getattr(base_task, 'phase_tags', None) or [])
    base_meta = getattr(base_task, 'analysis_meta', None) or {}
    base_ctx = set(base_meta.get('work_contexts') or []) if isinstance(base_meta, dict) else set()
    base_obj = set(base_meta.get('objective_tags') or []) if isinstance(base_meta, dict) else set()
    base_players = str(getattr(base_task, 'players_band', '') or '')
    base_duration = str(getattr(base_task, 'duration_band', '') or '')

    scored = []
    for candidate in tasks:
        cid = int(getattr(candidate, 'id', 0) or 0)
        if not cid or cid == base_id:
            continue
        score = 0
        cand_types = set(getattr(candidate, 'exercise_types', None) or [])
        cand_phases = set(getattr(candidate, 'phase_tags', None) or [])
        cand_meta = getattr(candidate, 'analysis_meta', None) or {}
        cand_ctx = set(cand_meta.get('work_contexts') or []) if isinstance(cand_meta, dict) else set()
        cand_obj = set(cand_meta.get('objective_tags') or []) if isinstance(cand_meta, dict) else set()
        score += 3 * len(base_types.intersection(cand_types))
        score += 2 * len(base_phases.intersection(cand_phases))
        score += 2 * len(base_obj.intersection(cand_obj))
        score += 1 * len(base_ctx.intersection(cand_ctx))
        if base_players and base_players == str(getattr(candidate, 'players_band', '') or ''):
            score += 1
        if base_duration and base_duration == str(getattr(candidate, 'duration_band', '') or ''):
            score += 1
        if score <= 0:
            continue
        scored.append((score, candidate))

    scored.sort(key=lambda row: (row[0], int(getattr(row[1], 'id', 0) or 0)), reverse=True)
    return [row[1] for row in scored[: max(0, int(limit or 0))]]
