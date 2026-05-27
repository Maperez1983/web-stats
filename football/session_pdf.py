import base64
import html
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone
from django.utils.text import slugify

from .models import SessionTask, Team, TrainingSession, TrainingSessionAttendance
from .preview_render import render_task_preview_png
from .session_plan_fields import parse_session_plan_fields, serialize_session_plan_fields
from .session_import_services import extract_pdf_text as import_extract_pdf_text
from .session_canvas_recreate import recreate_canvas_state_from_preview_image_bytes

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


SESSION_PDF_DELEGATED_VIEW_NAMES = (
    '_build_session_pdf_context',
)


def session_plan_pdf(request, session_id):
    from .views import (
        _build_pdf_response_or_html_fallback,
        _can_access_sessions_workspace,
        _forbid_if_workspace_module_disabled,
    )

    if not _can_access_sessions_workspace(request.user):
        return HttpResponse('No tienes permisos para acceder a sesiones.', status=403)
    forbidden = _forbid_if_workspace_module_disabled(request, 'sessions', label='sesiones')
    if forbidden:
        return forbidden
    session = (
        TrainingSession.objects
        .select_related('microcycle__team')
        .prefetch_related('tasks')
        .filter(id=session_id)
        .first()
    )
    if not session:
        raise Http404('Sesión no encontrada')

    pdf_style = (request.GET.get('style') or 'uefa').strip().lower()
    if pdf_style not in {'uefa', 'club', 'hybrid'}:
        pdf_style = 'uefa'
    force_pdf = str(request.GET.get('force_pdf') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    inline = str(request.GET.get('inline') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    context = build_session_pdf_context(request, session.microcycle.team, session, pdf_style=pdf_style)
    html = render_to_string('football/session_plan_pdf.html', context)
    filename = slugify(f'sesion-{session.session_date}-{session.focus}') or f'sesion-{session.id}'
    return _build_pdf_response_or_html_fallback(request, html, filename, inline=inline, force_pdf=force_pdf)


def _views():
    from . import views

    return views


def _build_pdf_nav_urls(request):
    return _views()._build_pdf_nav_urls(request)


def _build_session_task_sheet(task):
    return _views()._build_session_task_sheet(task)


def _coerce_json_dict(value):
    return _views()._coerce_json_dict(value)


def _decode_canvas_data_url(data_url):
    return _views()._decode_canvas_data_url(data_url)


def _extract_canvas_state_for_preview(task):
    return _views()._extract_canvas_state_for_preview(task)


def _extract_preview_image_from_pdf(pdf_file, prefer_render=False):
    return _views()._extract_preview_image_from_pdf(pdf_file, prefer_render=prefer_render)


def _file_field_as_data_url(file_field):
    return _views()._file_field_as_data_url(file_field)


def _get_primary_team_for_request(request):
    return _views()._get_primary_team_for_request(request)


def _is_benagalbon_team(team):
    return _views()._is_benagalbon_team(team)


def _is_imported_task(task):
    return _views()._is_imported_task(task)


def _normalize_folded_text(value):
    return _views()._normalize_folded_text(value)


def _parse_int(value):
    return _views()._parse_int(value)


def _parse_session_plan_fields(raw_content):
    return parse_session_plan_fields(raw_content)


def _task_drills_for_pdf(meta):
    return _views()._task_drills_for_pdf(meta)


def _team_color_seed(team):
    return _views()._team_color_seed(team)


def _team_initials(label):
    return _views()._team_initials(label)


def _team_pdf_palette(team, pdf_style):
    return _views()._team_pdf_palette(team, pdf_style)


def resolve_team_crest_url(request, team, *, sync=False):
    return _views().resolve_team_crest_url(request, team, sync=sync)


def build_session_pdf_context(request, team, session, pdf_style='uefa'):
    def _safe_pdf_image_data_url(data_url: str, *, max_bytes: int = 6_000_000, max_side: int = 1800) -> str:
        """
        Normaliza imágenes embebidas para WeasyPrint.

        Motivo: ciertos binarios corruptos o extremadamente grandes pueden hacer que el motor
        nativo de imágenes (gdk-pixbuf/cairo) falle de forma no recuperable (500).
        Preferimos degradar a "sin representación gráfica" antes que tumbar el endpoint.
        """
        raw = str(data_url or '').strip()
        if not raw.startswith('data:image/') or ';base64,' not in raw:
            return raw
        raw_bytes, _ext = _decode_canvas_data_url(raw)
        if not raw_bytes:
            return ''
        if len(raw_bytes) > int(max_bytes or 0):
            return ''
        if Image is None:
            return raw
        try:
            import io as _io  # noqa: WPS433

            with Image.open(_io.BytesIO(raw_bytes)) as img:
                # Aplanamos sobre blanco para evitar problemas con alpha/transparencia.
                rgba = img.convert('RGBA')
                flat = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                try:
                    flat.alpha_composite(rgba)
                except Exception:
                    flat.paste(rgba, (0, 0), rgba)
                rgb = flat.convert('RGB')
                rgb.thumbnail((max(320, int(max_side)), max(320, int(max_side))))
                out = _io.BytesIO()
                rgb.save(out, format='JPEG', quality=84, optimize=True, progressive=True)
                payload = base64.b64encode(out.getvalue()).decode('ascii')
                return 'data:image/jpeg;base64,' + payload
        except Exception:
            return ''

    # Mantén el mismo orden que la "ficha de sesión" (training_session_detail_page):
    # orden por bloque/fase + orden dentro de bloque.
    tasks = list(session.tasks.filter(deleted_at__isnull=True).order_by('block', 'order', 'id'))
    block_order = [
        SessionTask.BLOCK_CONDITIONING,
        SessionTask.BLOCK_ACTIVATION,
        SessionTask.BLOCK_MAIN_1,
        SessionTask.BLOCK_MAIN_2,
        SessionTask.BLOCK_SET_PIECES,
        SessionTask.BLOCK_RECOVERY,
        SessionTask.BLOCK_VIDEO,
    ]
    block_rank = {key: idx for idx, key in enumerate(block_order)}
    tasks.sort(
        key=lambda t: (
            block_rank.get(str(getattr(t, 'block', '') or ''), 999),
            int(getattr(t, 'order', 0) or 0),
            int(getattr(t, 'id', 0) or 0),
        )
    )
    total_task_minutes = sum(int(getattr(task, 'duration_minutes', 0) or 0) for task in tasks)
    session_plan_fields = _parse_session_plan_fields(getattr(session, 'content', ''))
    coach_name = (
        request.user.get_full_name().strip()
        if hasattr(request.user, 'get_full_name') and request.user.get_full_name().strip()
        else getattr(request.user, 'username', '') or 'Entrenador'
    )
    primary_club_team = _get_primary_team_for_request(request) or Team.objects.filter(is_primary=True).first()
    club_logo_url = resolve_team_crest_url(request, primary_club_team, sync=True) if primary_club_team else ''
    # Para PDF "club" preferimos un escudo embebido (data URL) para evitar fallos de fetch/red en WeasyPrint.
    def _small_png_data_url(raw_bytes: bytes, *, max_side: int = 220) -> str:
        try:
            from io import BytesIO  # noqa: WPS433
            from PIL import Image  # noqa: WPS433

            bio = BytesIO(raw_bytes or b"")
            img = Image.open(bio)
            img = img.convert("RGBA")
            img.thumbnail((max_side, max_side))
            out = BytesIO()
            img.save(out, format="PNG", optimize=True)
            payload = base64.b64encode(out.getvalue()).decode("ascii")
            return "data:image/png;base64," + payload
        except Exception:
            return ''
    team_logo_url = ''
    try:
        if getattr(team, 'crest_image', None):
            team_logo_url = _file_field_as_data_url(getattr(team, 'crest_image', None)) or ''
            if team_logo_url.startswith('data:image/') and ';base64,' in team_logo_url:
                try:
                    header, payload = team_logo_url.split(';base64,', 1)
                    raw = base64.b64decode(payload.encode('ascii'))
                    team_logo_url = _small_png_data_url(raw, max_side=220) or team_logo_url
                except Exception:
                    pass
    except Exception:
        team_logo_url = ''
    if not team_logo_url and _is_benagalbon_team(team):
        try:
            crest_path = Path(getattr(settings, 'BASE_DIR', Path.cwd())) / 'static' / 'football' / 'images' / 'cdb-benagalbon-crest-pdf.png'
            raw = crest_path.read_bytes()
            if raw:
                team_logo_url = _small_png_data_url(raw, max_side=220) or ("data:image/png;base64," + base64.b64encode(raw).decode("ascii"))
        except Exception:
            team_logo_url = ''
    if not team_logo_url:
        try:
            hue = _team_color_seed(team)
            initials = _team_initials(getattr(team, 'display_name', '') or getattr(team, 'name', '') or '')
            crest_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="hsl({hue}, 70%, 42%)"/>
      <stop offset="100%" stop-color="hsl({(hue + 35) % 360}, 74%, 36%)"/>
    </linearGradient>
  </defs>
  <rect x="0" y="0" width="160" height="160" rx="32" fill="url(#g)"/>
  <rect x="10" y="10" width="140" height="140" rx="28" fill="rgba(2, 6, 23, 0.25)" stroke="rgba(255,255,255,0.26)" stroke-width="2"/>
  <text x="80" y="92" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, Roboto, Arial" font-size="56" font-weight="800" fill="rgba(255,255,255,0.92)" letter-spacing="2">{html.escape(str(initials or '').strip())}</text>
</svg>"""
            team_logo_url = "data:image/svg+xml;base64," + base64.b64encode(crest_svg.encode("utf-8")).decode("ascii")
        except Exception:
            team_logo_url = ''
    def _static_data_url(static_path: str, mime: str) -> str:
        try:
            from django.contrib.staticfiles import finders  # noqa: WPS433

            disk_path = finders.find(static_path)
            if not disk_path:
                return ''
            raw = Path(disk_path).read_bytes()
            if not raw:
                return ''
            return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
        except Exception:
            return ''

    uefa_badge_url = _static_data_url('football/images/uefa-badge.svg', 'image/svg+xml') or request.build_absolute_uri(static('football/images/uefa-badge.svg'))
    brand_mark_data_url = _static_data_url('football/images/2j-mark.svg', 'image/svg+xml')
    club_dragon_data_url = _static_data_url('football/images/cdb-dragon-watermark.png', 'image/png') if (pdf_style in {'club', 'hybrid'} and _is_benagalbon_team(team)) else ''
    task_sheets = [_build_session_task_sheet(task) for task in tasks]

    valid_blocks = {choice[0] for choice in SessionTask.BLOCK_CHOICES}

    def _infer_task_block_for_pdf(task, meta: dict) -> str:
        """
        Inferir bloque/fase cuando la tarea viene importada desde PDF y el bloque quedó en default.

        Caso real: PDFs "sesión" con varias tareas (calentamiento, activación, principal, vuelta a la calma).
        Si el usuario sube el PDF sin asignar bloque, todas quedan como Principal 1 y el PDF sale “desordenado”.
        """
        stored = str(getattr(task, 'block', '') or '').strip()
        if stored not in valid_blocks:
            stored = SessionTask.BLOCK_MAIN_1
        analysis_meta = meta.get('analysis') if isinstance(meta.get('analysis'), dict) else {}
        phase_tags = analysis_meta.get('phase_tags') if isinstance(analysis_meta.get('phase_tags'), list) else []
        phase_tags = [str(tag or '').strip().lower() for tag in phase_tags if str(tag or '').strip()]

        hint_parts = [
            str(getattr(task, 'title', '') or '').strip(),
            str(meta.get('pdf_segment_excerpt') or '').strip(),
            str(analysis_meta.get('summary') or '').strip(),
        ]
        try:
            sheet = analysis_meta.get('task_sheet') if isinstance(analysis_meta.get('task_sheet'), dict) else {}
            hint_parts.append(str(sheet.get('description') or '').strip())
        except Exception:
            pass
        hint = '\n'.join([p for p in hint_parts if p]).strip()
        folded = _normalize_folded_text(hint)

        def _has_any(*tokens: str) -> bool:
            return any(token in folded for token in tokens if token)

        inferred = ''

        # Cooldown / recuperación.
        if _has_any(
            'vueltacalma',
            'vueltaalacalma',
            'enfriamiento',
            'cooldown',
            'cool down',
            'estiramiento',
            'compensacion',
            'compensación',
            'recuperacion',
            'recuperación',
            'bajadapulsaciones',
            'relajacion',
            'relajación',
        ):
            inferred = SessionTask.BLOCK_RECOVERY

        # ABP.
        if not inferred and ('abp' in phase_tags or _has_any('abp', 'balonparado', 'balónparado', 'corner', 'saquedeesquina', 'faltalateral')):
            inferred = SessionTask.BLOCK_SET_PIECES

        # Warmup (Condicionante) vs Activación.
        if not inferred and _has_any('calentamiento', 'acondicionamiento', 'entradaencalor'):
            inferred = SessionTask.BLOCK_CONDITIONING
        if not inferred and ('activacion' in phase_tags or _has_any('activacion', 'activación', 'movilidad')):
            inferred = SessionTask.BLOCK_ACTIVATION

        # Principal 2 / Principal 1.
        if not inferred and _has_any('principal2', 'parteprincipal2', 'pp2', 'principal ii', 'principal 2'):
            inferred = SessionTask.BLOCK_MAIN_2
        if not inferred and _has_any('principal1', 'parteprincipal1', 'pp1', 'principal i', 'principal 1'):
            inferred = SessionTask.BLOCK_MAIN_1
        if not inferred and _has_any('parteprincipal', 'parte principal'):
            inferred = SessionTask.BLOCK_MAIN_1

        if not inferred and _has_any('video', 'vídeo'):
            inferred = SessionTask.BLOCK_VIDEO

        if inferred and inferred in valid_blocks:
            if _is_imported_task(task) and stored == SessionTask.BLOCK_MAIN_1 and inferred != stored:
                return inferred
        return stored

    def _task_preview_data_url_for_pdf(task):
        def _autocrop_preview_data_url(data_url: str) -> str:
            """
            Centra la pizarra eliminando márgenes blancos del PNG/JPEG.

            En algunos renders (según preset/zoom/orientación) el preview puede tener un área en blanco a la
            derecha/abajo. WeasyPrint centrará el <img>, pero si el "blanco" está dentro del propio bitmap,
            la pizarra seguirá viéndose desplazada. Autocrop arregla esto para el PDF UEFA.
            """
            if pdf_style == 'club':
                return data_url
            raw = str(data_url or '')
            if not raw.startswith('data:image/') or ';base64,' not in raw:
                return data_url
            try:
                header, payload = raw.split(';base64,', 1)
                mime = header.split(':', 1)[1].strip().lower()
                if mime not in {'image/png', 'image/jpeg', 'image/jpg', 'image/webp'}:
                    return data_url
                blob = base64.b64decode(payload.encode('ascii'))
            except Exception:
                return data_url
            try:
                from io import BytesIO  # noqa: WPS433
                from PIL import Image, ImageChops  # noqa: WPS433

                img = Image.open(BytesIO(blob))
                # Aplanamos sobre blanco para que el recorte funcione también con transparencia.
                rgba = img.convert('RGBA')
                flat = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                try:
                    flat.alpha_composite(rgba)
                except Exception:
                    # Compat: alpha_composite puede fallar en algunas modes.
                    flat.paste(rgba, (0, 0), rgba)
                rgb = flat.convert('RGB')
                bg = Image.new('RGB', rgb.size, (255, 255, 255))
                diff = ImageChops.difference(rgb, bg)
                # Filtra "casi blanco" para evitar que fondos #f5f5f5 o antialiasing impidan el recorte.
                diff_l = diff.convert('L').point(lambda p: 255 if p > 12 else 0)
                bbox = diff_l.getbbox()
                if not bbox:
                    return data_url
                pad = 10
                left = max(0, int(bbox[0]) - pad)
                top = max(0, int(bbox[1]) - pad)
                right = min(rgb.size[0], int(bbox[2]) + pad)
                bottom = min(rgb.size[1], int(bbox[3]) + pad)
                cropped = rgb.crop((left, top, right, bottom))
                out = BytesIO()
                cropped.save(out, format='PNG', optimize=True)
                return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')
            except Exception:
                return data_url

        # 1) Imagen ya guardada.
        preview = _file_field_as_data_url(getattr(task, 'task_preview_image', None))
        if preview:
            return _autocrop_preview_data_url(preview)
        layout = task.tactical_layout if isinstance(task.tactical_layout, dict) else {}
        if isinstance(layout, str):
            layout = _coerce_json_dict(layout) or {}
        if not isinstance(layout, dict):
            layout = {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        canvas_state, canvas_width, canvas_height = _extract_canvas_state_for_preview(task)
        # 2) Render server-side desde canvas_state (más robusto que depender de ficheros).
        if canvas_state and isinstance(canvas_state, dict) and canvas_state.get('objects'):
            try:
                pitch_preset = str(meta.get('pitch_preset') or 'full_pitch').strip() or 'full_pitch'
                pitch_orientation = str(meta.get('pitch_orientation') or 'landscape').strip().lower()
                pitch_grass_style = str(meta.get('pitch_grass_style') or 'classic').strip().lower()
                if pitch_grass_style not in {'classic', 'broadcast', 'realistic', 'pro', 'artificial', 'dry', 'wet', 'uefa_b', 'whiteboard', 'blackboard'}:
                    pitch_grass_style = 'classic'
                # En PDF no queremos recortes por zoom: forzamos a 1.0.
                pitch_zoom = 1.0
                canvas_width = max(320, min(_parse_int(canvas_width) or 1280, 3840))
                canvas_height = max(180, min(_parse_int(canvas_height) or 720, 2160))
                png_bytes = render_task_preview_png(
                    canvas_state=canvas_state,
                    pitch_preset=pitch_preset,
                    pitch_orientation="portrait" if pitch_orientation == "portrait" else "landscape",
                    pitch_grass_style=pitch_grass_style,
                    pitch_zoom=pitch_zoom,
                    world_width=canvas_width,
                    world_height=canvas_height,
                    max_side=3200,
                )
                if png_bytes:
                    return _autocrop_preview_data_url("data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"))
            except Exception:
                pass
        # 3) Fallback: extraer preview del PDF si existe.
        pdf_field = getattr(task, 'task_pdf', None)
        if pdf_field:
            try:
                payload = _extract_preview_image_from_pdf(pdf_field, prefer_render=True)
                if payload:
                    name, content = payload
                    try:
                        content.seek(0)
                    except Exception:
                        pass
                    raw = content.read() or b''
                    if raw:
                        ext = str(name or '').rsplit('.', 1)[-1].lower()
                        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}.get(ext, 'image/png')
                        return _autocrop_preview_data_url(f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"))
            except Exception:
                pass
        return ''

    task_cards = []
    for idx, task in enumerate(tasks):
        sheet = task_sheets[idx] if idx < len(task_sheets) else _build_session_task_sheet(task)
        preview_url = _safe_pdf_image_data_url(_task_preview_data_url_for_pdf(task))
        meta = {}
        try:
            if isinstance(getattr(task, 'tactical_layout', None), dict):
                meta = task.tactical_layout.get('meta') if isinstance(task.tactical_layout.get('meta'), dict) else {}
        except Exception:
            meta = {}
        effective_block = _infer_task_block_for_pdf(task, meta if isinstance(meta, dict) else {})
        task_cards.append(
            {
                'task': task,
                'sheet': sheet,
                'preview_url': preview_url,
                'drills': _task_drills_for_pdf(meta),
                'effective_block': effective_block,
            }
        )
    # Orden estándar de sesión: Calentamiento → Activación → Principal 1 → Principal 2 → Vuelta a la calma.
    section_specs = [
        {'key': 'warmup', 'label': 'Calentamiento', 'blocks': [SessionTask.BLOCK_CONDITIONING]},
        {'key': 'activation', 'label': 'Activación', 'blocks': [SessionTask.BLOCK_ACTIVATION]},
        {'key': 'main_1', 'label': 'Principal 1', 'blocks': [SessionTask.BLOCK_MAIN_1]},
        # ABP se considera dentro de "Principal 2" para mantener el orden esperado por el entrenador.
        {'key': 'main_2', 'label': 'Principal 2', 'blocks': [SessionTask.BLOCK_MAIN_2, SessionTask.BLOCK_SET_PIECES]},
        {'key': 'cooldown', 'label': 'Vuelta a la calma', 'blocks': [SessionTask.BLOCK_RECOVERY]},
    ]
    known_blocks = {block for spec in section_specs for block in spec['blocks']}
    task_sections = []
    for spec in section_specs:
        cards = [card for card in task_cards if str(card.get('effective_block') or getattr(card['task'], 'block', '') or '') in set(spec['blocks'])]
        cards.sort(key=lambda c: (int(getattr(c.get('task'), 'order', 0) or 0), int(getattr(c.get('task'), 'id', 0) or 0)))
        if cards:
            task_sections.append({'key': spec['key'], 'label': spec['label'], 'cards': cards})
    other_cards = [card for card in task_cards if str(card.get('effective_block') or getattr(card['task'], 'block', '') or '') not in known_blocks]
    other_cards.sort(key=lambda c: (int(getattr(c.get('task'), 'order', 0) or 0), int(getattr(c.get('task'), 'id', 0) or 0)))
    if other_cards:
        task_sections.append({'key': 'other', 'label': 'Otros', 'cards': other_cards})
    # Sugerencias para plantilla UEFA (no bloqueante).
    session_materials_summary = ', '.join(
        sorted(
            {
                str(sheet.get('materials_label') or '').strip()
                for sheet in task_sheets
                if str(sheet.get('materials_label') or '').strip() and str(sheet.get('materials_label') or '').strip() != '-'
            }
        )
    )
    session_objectives_summary = str(session.focus or '').strip()
    session_materials_override = str(session_plan_fields.get('materials') or '').strip()
    if session_materials_override:
        session_materials_summary = session_materials_override
    def _attendance_incidents_summary() -> str:
        """
        Convierte las marcas de asistencia (Ausente/Tarde/Lesionado/Justificado) en un resumen legible.

        Objetivo: que el PDF refleje lo marcado en "Asistencia" aunque el staff no copie/pegue a mano.
        """
        try:
            marks = list(
                TrainingSessionAttendance.objects
                .select_related('player')
                .filter(session=session)
                .exclude(status=TrainingSessionAttendance.STATUS_PRESENT)
                .order_by('player__number', 'player__name', 'id')
            )
        except Exception:
            marks = []
        if not marks:
            return ''
        buckets = {
            TrainingSessionAttendance.STATUS_ABSENT: [],
            TrainingSessionAttendance.STATUS_LATE: [],
            TrainingSessionAttendance.STATUS_INJURED: [],
            TrainingSessionAttendance.STATUS_EXCUSED: [],
        }
        for m in marks:
            st = str(getattr(m, 'status', '') or '').strip()
            if st not in buckets:
                continue
            p = getattr(m, 'player', None)
            if not p:
                continue
            try:
                num = int(getattr(p, 'number', 0) or 0) or 0
            except Exception:
                num = 0
            label = f'#{num} {p.name}'.strip() if num else str(getattr(p, 'name', '') or '').strip()
            note = str(getattr(m, 'notes', '') or '').strip()
            if note:
                label = f'{label} ({note})'
            buckets[st].append(label or 'Jugador')

        prefix = {
            TrainingSessionAttendance.STATUS_ABSENT: 'Ausentes',
            TrainingSessionAttendance.STATUS_LATE: 'Tarde',
            TrainingSessionAttendance.STATUS_INJURED: 'Lesionados',
            TrainingSessionAttendance.STATUS_EXCUSED: 'Justificados',
        }
        lines = []
        for key in [
            TrainingSessionAttendance.STATUS_ABSENT,
            TrainingSessionAttendance.STATUS_LATE,
            TrainingSessionAttendance.STATUS_INJURED,
            TrainingSessionAttendance.STATUS_EXCUSED,
        ]:
            items = buckets.get(key) or []
            if not items:
                continue
            lines.append(f'{prefix.get(key, key)}: {", ".join(items)}')
        return '\n'.join(lines).strip()

    session_absences_summary = str(session_plan_fields.get('absences') or '').strip()
    if not session_absences_summary:
        session_absences_summary = str(session_plan_fields.get('notes') or '').strip()
    attendance_incidents = _attendance_incidents_summary()
    if attendance_incidents:
        if session_absences_summary:
            if attendance_incidents not in session_absences_summary:
                session_absences_summary = (session_absences_summary.strip() + '\n' + attendance_incidents).strip()
        else:
            session_absences_summary = attendance_incidents
    session_player_count_display = str(session_plan_fields.get('player_count') or '').strip()
    if not session_player_count_display:
        assigned_ids = set()
        for task in tasks:
            layout = task.tactical_layout if isinstance(getattr(task, 'tactical_layout', None), dict) else {}
            meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
            raw_ids = meta.get('assigned_player_ids')
            if not isinstance(raw_ids, list):
                continue
            for raw_id in raw_ids:
                pid = _parse_int(raw_id)
                if pid:
                    assigned_ids.add(pid)
        if assigned_ids:
            session_player_count_display = str(len(assigned_ids))
    if not session_player_count_display:
        session_player_count_display = '-'
    session_display_name = str(getattr(session, 'focus', '') or '').strip()
    microcycle_display_title = str(getattr(getattr(session, 'microcycle', None), 'title', '') or '').strip()
    try:
        if session_display_name.lower().startswith('biblioteca pdf'):
            session_display_name = 'Repositorio de tareas (PDF)'
        if microcycle_display_title.lower().startswith('biblioteca '):
            microcycle_display_title = 'Repositorio'
    except Exception:
        pass
    return {
        **_build_pdf_nav_urls(request),
        'team_name': team.name,
        'session': session,
        'microcycle': session.microcycle,
        'session_display_name': session_display_name,
        'microcycle_display_title': microcycle_display_title,
        'session_plan_fields': session_plan_fields,
        'session_notes': str(session_plan_fields.get('notes') or '').strip(),
        'tasks': tasks,
        'task_sheets': task_sheets,
        'task_cards': task_cards,
        'task_sections': task_sections,
        'tasks_count': len(tasks),
        'task_minutes_total': total_task_minutes,
        'pdf_style': pdf_style,
        'pdf_palette': _team_pdf_palette(team, pdf_style),
        'coach_name': coach_name,
        'logo_url': team_logo_url if pdf_style in {'club', 'hybrid'} else uefa_badge_url,
        'brand_mark_url': brand_mark_data_url or request.build_absolute_uri(static('football/images/2j-mark.svg')),
        'club_dragon_url': club_dragon_data_url,
        'club_logo_url': club_logo_url,
        'generated_at': timezone.localtime(),
        'intensity_label': dict(TrainingSession.INTENSITY_CHOICES).get(session.intensity, session.intensity or '-'),
        'status_label': dict(TrainingSession.STATUS_CHOICES).get(session.status, session.status or '-'),
        'session_materials_summary': session_materials_summary,
        'session_objectives_summary': session_objectives_summary,
        'session_absences_summary': session_absences_summary,
        'session_player_count_display': session_player_count_display,
    }


def extract_pdf_text(pdf_file, max_chars=12000):
    return import_extract_pdf_text(pdf_file, max_chars=max_chars)
