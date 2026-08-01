import base64
import io
from functools import lru_cache
from pathlib import Path

from django.conf import settings

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None


NATIVE_STADIUM_FIELD_BOX = {
    'landscape': {'x': 0.268, 'y': 0.22, 'w': 0.462, 'h': 0.56},
    'portrait': {'x': 0.3558, 'y': 0.0683, 'w': 0.2883, 'h': 0.8771},
}

NATIVE_STADIUM_ASSETS = {
    'landscape': 'football/images/pitch3d/stadium_rosaleda_top_h.png',
    'portrait': 'football/images/pitch3d/stadium_rosaleda_top_v.png',
}

TASKBOARD_STADIUM_ASSETS = {
    'landscape': 'football/images/pitch3d/stadium_taskboard_top_h.png',
    'portrait': 'football/images/pitch3d/stadium_taskboard_top_v.png',
}

TASKBOARD_STADIUM_OVERLAY_ASSETS = {
    'landscape': 'football/images/pitch3d/stadium_taskboard_overlay_h.png',
    'portrait': 'football/images/pitch3d/stadium_taskboard_overlay_v.png',
}


def _normalize_orientation(value: object) -> str:
    return 'portrait' if str(value or '').strip().lower() == 'portrait' else 'landscape'


def _normalize_rgba(value: object, default):
    raw = str(value or '').strip()
    if not raw:
        return default
    if raw.startswith('#'):
        hex_value = raw[1:]
        if len(hex_value) == 3:
            hex_value = ''.join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            try:
                return tuple(int(hex_value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
            except Exception:
                return default
    if raw.startswith('rgba(') and raw.endswith(')'):
        try:
            parts = [part.strip() for part in raw[5:-1].split(',')]
            if len(parts) == 4:
                alpha = float(parts[3])
                return (
                    max(0, min(255, int(float(parts[0])))),
                    max(0, min(255, int(float(parts[1])))),
                    max(0, min(255, int(float(parts[2])))),
                    max(0, min(255, int(round(alpha * 255 if alpha <= 1 else alpha)))),
                )
        except Exception:
            return default
    if raw.startswith('rgb(') and raw.endswith(')'):
        try:
            parts = [part.strip() for part in raw[4:-1].split(',')]
            if len(parts) == 3:
                return (
                    max(0, min(255, int(float(parts[0])))),
                    max(0, min(255, int(float(parts[1])))),
                    max(0, min(255, int(float(parts[2])))),
                    255,
                )
        except Exception:
            return default
    return default


@lru_cache(maxsize=4)
def _load_background(static_rel_path: str):
    if Image is None:
        return None
    roots = [
        Path(settings.BASE_DIR) / 'static',
        Path(settings.BASE_DIR) / 'football' / 'static',
    ]
    for root in roots:
        asset_path = root / static_rel_path
        if not asset_path.exists():
            continue
        try:
            return Image.open(asset_path).convert('RGBA')
        except Exception:
            continue
    return None


def _map_box(img_w: int, img_h: int, orientation: str):
    ratios = NATIVE_STADIUM_FIELD_BOX[orientation]
    return (
        img_w * ratios['x'],
        img_h * ratios['y'],
        img_w * ratios['w'],
        img_h * ratios['h'],
    )


def _render_stadium_preview_data_url(
    canvas_state,
    *,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    pitch_orientation: str = 'landscape',
    asset_map=None,
):
    if Image is None or ImageDraw is None:
        return ''
    orientation = _normalize_orientation(pitch_orientation)
    asset_map = asset_map or NATIVE_STADIUM_ASSETS
    background = _load_background(asset_map[orientation])
    if background is None:
        return ''

    image = background.copy()
    draw = ImageDraw.Draw(image, 'RGBA')
    img_w, img_h = image.size
    field_x, field_y, field_w, field_h = _map_box(img_w, img_h, orientation)
    world_w = max(1, int(canvas_width or (720 if orientation == 'portrait' else 1280)))
    world_h = max(1, int(canvas_height or (1280 if orientation == 'portrait' else 720)))
    scale_x = field_w / world_w
    scale_y = field_h / world_h

    def _map_x(value):
        return field_x + (float(value or 0) * scale_x)

    def _map_y(value):
        return field_y + (float(value or 0) * scale_y)

    objects = canvas_state.get('objects') if isinstance(canvas_state, dict) and isinstance(canvas_state.get('objects'), list) else []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        obj_type = str(obj.get('type') or '').strip().lower()
        if obj_type == 'circle':
            left = _map_x(obj.get('left'))
            top = _map_y(obj.get('top'))
            rx = max(2.0, float(obj.get('radius') or 0) * scale_x)
            ry = max(2.0, float(obj.get('radius') or 0) * scale_y)
            fill = _normalize_rgba(obj.get('fill'), (31, 119, 255, 255))
            stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 255))
            stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 0) * max(scale_x, scale_y))))
            draw.ellipse((left - rx, top - ry, left + rx, top + ry), fill=fill, outline=stroke, width=stroke_width)
            continue
        if obj_type == 'rect':
            left = _map_x(obj.get('left'))
            top = _map_y(obj.get('top'))
            width = float(obj.get('width') or 0) * float(obj.get('scaleX') or 1.0) * scale_x
            height = float(obj.get('height') or 0) * float(obj.get('scaleY') or 1.0) * scale_y
            fill = _normalize_rgba(obj.get('fill'), (255, 255, 255, 32))
            stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 255))
            stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 0) * max(scale_x, scale_y))))
            draw.rectangle((left, top, left + width, top + height), fill=fill, outline=stroke, width=stroke_width)
            continue
        if obj_type == 'line':
            points = obj.get('points') if isinstance(obj.get('points'), list) else []
            mapped = []
            for point in points:
                if isinstance(point, dict):
                    mapped.extend((_map_x(point.get('x')), _map_y(point.get('y'))))
            if len(mapped) >= 4:
                stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 230))
                stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 2) * max(scale_x, scale_y))))
                draw.line(mapped, fill=stroke, width=stroke_width)

    output = io.BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def _draw_canvas_objects(draw, objects, *, map_x, map_y, scale_x, scale_y):
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        obj_type = str(obj.get('type') or '').strip().lower()
        if obj_type == 'circle':
            left = map_x(obj.get('left'))
            top = map_y(obj.get('top'))
            rx = max(2.0, float(obj.get('radius') or 0) * scale_x)
            ry = max(2.0, float(obj.get('radius') or 0) * scale_y)
            fill = _normalize_rgba(obj.get('fill'), (31, 119, 255, 255))
            stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 255))
            stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 0) * max(scale_x, scale_y))))
            draw.ellipse((left - rx, top - ry, left + rx, top + ry), fill=fill, outline=stroke, width=stroke_width)
        elif obj_type == 'rect':
            left = map_x(obj.get('left'))
            top = map_y(obj.get('top'))
            width = float(obj.get('width') or 0) * float(obj.get('scaleX') or 1.0) * scale_x
            height = float(obj.get('height') or 0) * float(obj.get('scaleY') or 1.0) * scale_y
            fill = _normalize_rgba(obj.get('fill'), (255, 255, 255, 32))
            stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 255))
            stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 0) * max(scale_x, scale_y))))
            draw.rectangle((left, top, left + width, top + height), fill=fill, outline=stroke, width=stroke_width)
        elif obj_type == 'line':
            points = obj.get('points') if isinstance(obj.get('points'), list) else []
            mapped = []
            for point in points:
                if isinstance(point, dict):
                    mapped.extend((map_x(point.get('x')), map_y(point.get('y'))))
            if len(mapped) >= 4:
                stroke = _normalize_rgba(obj.get('stroke'), (255, 255, 255, 230))
                stroke_width = max(1, int(round(float(obj.get('strokeWidth') or 2) * max(scale_x, scale_y))))
                draw.line(mapped, fill=stroke, width=stroke_width)


def render_flat_tactical_preview_data_url(
    canvas_state,
    *,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    pitch_orientation: str = 'landscape',
    grass_style: str = 'broadcast_premium',
):
    if Image is None or ImageDraw is None:
        return ''
    orientation = _normalize_orientation(pitch_orientation)
    out_w = max(320, int(canvas_width or (720 if orientation == 'portrait' else 1280)))
    out_h = max(180, int(canvas_height or (1280 if orientation == 'portrait' else 720)))
    image = Image.new('RGBA', (out_w, out_h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image, 'RGBA')

    margin = int(min(out_w, out_h) * 0.06)
    pitch_x = margin
    pitch_y = margin
    pitch_w = out_w - (margin * 2)
    pitch_h = out_h - (margin * 2)

    palette = {
        'classic': ((120, 165, 73, 255), (107, 151, 63, 255)),
        'broadcast': ((99, 152, 69, 255), (80, 133, 54, 255)),
        'broadcast_premium': ((188, 217, 111, 255), (151, 188, 82, 255)),
        'realistic': ((86, 145, 62, 255), (64, 119, 47, 255)),
        'pro': ((84, 153, 90, 255), (56, 118, 74, 255)),
        'stadium_native': ((82, 170, 118, 255), (51, 132, 82, 255)),
        'whiteboard': ((248, 250, 252, 255), (229, 231, 235, 255)),
        'blackboard': ((11, 18, 32, 255), (3, 7, 18, 255)),
    }
    normalized_grass = str(grass_style or 'broadcast_premium').strip().lower()
    stripe_a, stripe_b = palette.get(normalized_grass, palette['broadcast_premium'])
    line_color = (15, 23, 42, 230) if normalized_grass == 'whiteboard' else (248, 250, 252, 248)
    soft_line = (15, 23, 42, 140) if normalized_grass == 'whiteboard' else (255, 255, 255, 110)

    if normalized_grass == 'stadium_native':
        overlay = _load_background(TASKBOARD_STADIUM_OVERLAY_ASSETS[orientation])
        if overlay is not None:
            image = Image.new('RGBA', overlay.size, (226, 233, 240, 255))
            draw = ImageDraw.Draw(image, 'RGBA')
            pitch_x, pitch_y, pitch_w, pitch_h = _map_box(overlay.size[0], overlay.size[1], orientation)
            stripe_count = 10 if orientation == 'portrait' else 12
            for index in range(stripe_count):
                if orientation == 'portrait':
                    y0 = int(pitch_y + ((pitch_h * index) / stripe_count))
                    y1 = int(pitch_y + ((pitch_h * (index + 1)) / stripe_count))
                    draw.rectangle((int(pitch_x), y0, int(pitch_x + pitch_w), y1), fill=stripe_a if index % 2 == 0 else stripe_b)
                else:
                    x0 = int(pitch_x + ((pitch_w * index) / stripe_count))
                    x1 = int(pitch_x + ((pitch_w * (index + 1)) / stripe_count))
                    draw.rectangle((x0, int(pitch_y), x1, int(pitch_y + pitch_h)), fill=stripe_a if index % 2 == 0 else stripe_b)

            world_w = max(1, int(canvas_width or out_w))
            world_h = max(1, int(canvas_height or out_h))
            scale_x = pitch_w / world_w
            scale_y = pitch_h / world_h

            def _p(px: float, py: float):
                return (pitch_x + (pitch_w * px), pitch_y + (pitch_h * py))

            line_w = max(3, int(round(min(pitch_w, pitch_h) * 0.0042)))
            draw.rounded_rectangle(
                (pitch_x, pitch_y, pitch_x + pitch_w, pitch_y + pitch_h),
                radius=max(12, line_w * 3),
                outline=line_color,
                width=line_w,
            )
            if orientation == 'portrait':
                draw.line((*_p(0.0, 0.5), *_p(1.0, 0.5)), fill=line_color, width=line_w)
                center = _p(0.5, 0.5)
                penalty_depth = 16.5 / 105.0
                six_depth = 5.5 / 105.0
                penalty_width = 40.32 / 68.0
                six_width = 18.32 / 68.0
                spot_dist = 11.0 / 105.0
                circle_r = (9.15 / 68.0) * pitch_w
                center_r = max(3, int(line_w * 0.75))
                area_left = (1.0 - penalty_width) / 2.0
                six_left = (1.0 - six_width) / 2.0
                draw.ellipse((center[0] - circle_r, center[1] - circle_r, center[0] + circle_r, center[1] + circle_r), outline=line_color, width=line_w)
                draw.ellipse((center[0] - center_r, center[1] - center_r, center[0] + center_r, center[1] + center_r), fill=line_color)
                draw.rectangle((*_p(area_left, 0.0), *_p(area_left + penalty_width, penalty_depth)), outline=line_color, width=line_w)
                draw.rectangle((*_p(area_left, 1.0 - penalty_depth), *_p(area_left + penalty_width, 1.0)), outline=line_color, width=line_w)
                draw.rectangle((*_p(six_left, 0.0), *_p(six_left + six_width, six_depth)), outline=line_color, width=line_w)
                draw.rectangle((*_p(six_left, 1.0 - six_depth), *_p(six_left + six_width, 1.0)), outline=line_color, width=line_w)
                for y in (spot_dist, 1.0 - spot_dist):
                    sx, sy = _p(0.5, y)
                    draw.ellipse((sx - center_r, sy - center_r, sx + center_r, sy + center_r), fill=line_color)
            else:
                draw.line((*_p(0.5, 0.0), *_p(0.5, 1.0)), fill=line_color, width=line_w)
                center = _p(0.5, 0.5)
                penalty_depth = 16.5 / 105.0
                six_depth = 5.5 / 105.0
                penalty_width = 40.32 / 68.0
                six_width = 18.32 / 68.0
                spot_dist = 11.0 / 105.0
                circle_r = (9.15 / 105.0) * pitch_w
                center_r = max(3, int(line_w * 0.75))
                area_top = (1.0 - penalty_width) / 2.0
                six_top = (1.0 - six_width) / 2.0
                draw.ellipse((center[0] - circle_r, center[1] - circle_r, center[0] + circle_r, center[1] + circle_r), outline=line_color, width=line_w)
                draw.ellipse((center[0] - center_r, center[1] - center_r, center[0] + center_r, center[1] + center_r), fill=line_color)
                draw.rectangle((*_p(0.0, area_top), *_p(penalty_depth, area_top + penalty_width)), outline=line_color, width=line_w)
                draw.rectangle((*_p(1.0 - penalty_depth, area_top), *_p(1.0, area_top + penalty_width)), outline=line_color, width=line_w)
                draw.rectangle((*_p(0.0, six_top), *_p(six_depth, six_top + six_width)), outline=line_color, width=line_w)
                draw.rectangle((*_p(1.0 - six_depth, six_top), *_p(1.0, six_top + six_width)), outline=line_color, width=line_w)
                for x in (spot_dist, 1.0 - spot_dist):
                    sx, sy = _p(x, 0.5)
                    draw.ellipse((sx - center_r, sy - center_r, sx + center_r, sy + center_r), fill=line_color)

            objects = canvas_state.get('objects') if isinstance(canvas_state, dict) and isinstance(canvas_state.get('objects'), list) else []

            def _map_x(value):
                return pitch_x + (float(value or 0) * scale_x)

            def _map_y(value):
                return pitch_y + (float(value or 0) * scale_y)

            _draw_canvas_objects(draw, objects, map_x=_map_x, map_y=_map_y, scale_x=scale_x, scale_y=scale_y)
            image.alpha_composite(overlay)
            output = io.BytesIO()
            image.save(output, format='PNG')
            return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')

    stripe_count = 10 if orientation == 'portrait' else 12
    for index in range(stripe_count):
        if orientation == 'portrait':
            y0 = pitch_y + int((pitch_h * index) / stripe_count)
            y1 = pitch_y + int((pitch_h * (index + 1)) / stripe_count)
            draw.rectangle((pitch_x, y0, pitch_x + pitch_w, y1), fill=stripe_a if index % 2 == 0 else stripe_b)
        else:
            x0 = pitch_x + int((pitch_w * index) / stripe_count)
            x1 = pitch_x + int((pitch_w * (index + 1)) / stripe_count)
            draw.rectangle((x0, pitch_y, x1, pitch_y + pitch_h), fill=stripe_a if index % 2 == 0 else stripe_b)

    def _p(px: float, py: float):
        return (pitch_x + (pitch_w * px), pitch_y + (pitch_h * py))

    line_w = max(2, int(round(min(pitch_w, pitch_h) * 0.0045)))
    draw.rounded_rectangle((pitch_x, pitch_y, pitch_x + pitch_w, pitch_y + pitch_h), radius=max(10, line_w * 2), outline=line_color, width=line_w)

    if orientation == 'portrait':
        draw.line((*_p(0.0, 0.5), *_p(1.0, 0.5)), fill=line_color, width=line_w)
        center = _p(0.5, 0.5)
        penalty_depth = 16.5 / 105.0
        six_depth = 5.5 / 105.0
        penalty_width = 40.32 / 68.0
        six_width = 18.32 / 68.0
        spot_dist = 11.0 / 105.0
        circle_r = (9.15 / 68.0) * pitch_w
        center_r = max(3, int(line_w * 0.75))
        area_left = (1.0 - penalty_width) / 2.0
        six_left = (1.0 - six_width) / 2.0

        draw.ellipse((center[0] - circle_r, center[1] - circle_r, center[0] + circle_r, center[1] + circle_r), outline=line_color, width=line_w)
        draw.ellipse((center[0] - center_r, center[1] - center_r, center[0] + center_r, center[1] + center_r), fill=line_color)

        top_area = (*_p(area_left, 0.0), *_p(area_left + penalty_width, penalty_depth))
        bot_area = (*_p(area_left, 1.0 - penalty_depth), *_p(area_left + penalty_width, 1.0))
        top_six = (*_p(six_left, 0.0), *_p(six_left + six_width, six_depth))
        bot_six = (*_p(six_left, 1.0 - six_depth), *_p(six_left + six_width, 1.0))
        draw.rectangle(top_area, outline=line_color, width=line_w)
        draw.rectangle(bot_area, outline=line_color, width=line_w)
        draw.rectangle(top_six, outline=line_color, width=line_w)
        draw.rectangle(bot_six, outline=line_color, width=line_w)

        for y in (spot_dist, 1.0 - spot_dist):
            sx, sy = _p(0.5, y)
            draw.ellipse((sx - center_r, sy - center_r, sx + center_r, sy + center_r), fill=line_color)

        arc_r = circle_r
        arc_offset_x = (arc_r / pitch_w) if pitch_w else 0.0
        arc_offset_y = (arc_r / pitch_h) if pitch_h else 0.0
        top_arc_box = (*_p(0.5 - arc_offset_x, spot_dist - arc_offset_y), *_p(0.5 + arc_offset_x, spot_dist + arc_offset_y))
        bot_arc_box = (*_p(0.5 - arc_offset_x, 1.0 - spot_dist - arc_offset_y), *_p(0.5 + arc_offset_x, 1.0 - spot_dist + arc_offset_y))
        draw.arc(top_arc_box, start=20, end=160, fill=soft_line, width=line_w)
        draw.arc(bot_arc_box, start=200, end=340, fill=soft_line, width=line_w)
    else:
        draw.line((*_p(0.5, 0.0), *_p(0.5, 1.0)), fill=line_color, width=line_w)
        center = _p(0.5, 0.5)
        penalty_depth = 16.5 / 105.0
        six_depth = 5.5 / 105.0
        penalty_width = 40.32 / 68.0
        six_width = 18.32 / 68.0
        spot_dist = 11.0 / 105.0
        circle_r = (9.15 / 105.0) * pitch_w
        center_r = max(3, int(line_w * 0.75))
        area_top = (1.0 - penalty_width) / 2.0
        six_top = (1.0 - six_width) / 2.0

        draw.ellipse((center[0] - circle_r, center[1] - circle_r, center[0] + circle_r, center[1] + circle_r), outline=line_color, width=line_w)
        draw.ellipse((center[0] - center_r, center[1] - center_r, center[0] + center_r, center[1] + center_r), fill=line_color)

        left_area = (*_p(0.0, area_top), *_p(penalty_depth, area_top + penalty_width))
        right_area = (*_p(1.0 - penalty_depth, area_top), *_p(1.0, area_top + penalty_width))
        left_six = (*_p(0.0, six_top), *_p(six_depth, six_top + six_width))
        right_six = (*_p(1.0 - six_depth, six_top), *_p(1.0, six_top + six_width))
        draw.rectangle(left_area, outline=line_color, width=line_w)
        draw.rectangle(right_area, outline=line_color, width=line_w)
        draw.rectangle(left_six, outline=line_color, width=line_w)
        draw.rectangle(right_six, outline=line_color, width=line_w)

        for x in (spot_dist, 1.0 - spot_dist):
            sx, sy = _p(x, 0.5)
            draw.ellipse((sx - center_r, sy - center_r, sx + center_r, sy + center_r), fill=line_color)

        arc_r = circle_r
        arc_offset_x = (arc_r / pitch_w) if pitch_w else 0.0
        arc_offset_y = (arc_r / pitch_h) if pitch_h else 0.0
        left_arc_box = (*_p(spot_dist - arc_offset_x, 0.5 - arc_offset_y), *_p(spot_dist + arc_offset_x, 0.5 + arc_offset_y))
        right_arc_box = (*_p(1.0 - spot_dist - arc_offset_x, 0.5 - arc_offset_y), *_p(1.0 - spot_dist + arc_offset_x, 0.5 + arc_offset_y))
        draw.arc(left_arc_box, start=290, end=70, fill=soft_line, width=line_w)
        draw.arc(right_arc_box, start=110, end=250, fill=soft_line, width=line_w)

    world_w = max(1, int(canvas_width or out_w))
    world_h = max(1, int(canvas_height or out_h))
    scale_x = pitch_w / world_w
    scale_y = pitch_h / world_h

    def _map_x(value):
        return pitch_x + (float(value or 0) * scale_x)

    def _map_y(value):
        return pitch_y + (float(value or 0) * scale_y)

    objects = canvas_state.get('objects') if isinstance(canvas_state, dict) and isinstance(canvas_state.get('objects'), list) else []
    _draw_canvas_objects(draw, objects, map_x=_map_x, map_y=_map_y, scale_x=scale_x, scale_y=scale_y)

    output = io.BytesIO()
    image.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


def render_stadium_native_preview_data_url(
    canvas_state,
    *,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    pitch_orientation: str = 'landscape',
):
    return _render_stadium_preview_data_url(
        canvas_state,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pitch_orientation=pitch_orientation,
        asset_map=NATIVE_STADIUM_ASSETS,
    )


def render_stadium_taskboard_preview_data_url(
    canvas_state,
    *,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    pitch_orientation: str = 'landscape',
):
    return _render_stadium_preview_data_url(
        canvas_state,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pitch_orientation=pitch_orientation,
        asset_map=TASKBOARD_STADIUM_ASSETS,
    )


def render_stadium_native_perspective_preview_data_url(
    canvas_state,
    *,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    pitch_orientation: str = 'landscape',
):
    if Image is None or ImageDraw is None:
        return ''
    base_data_url = render_stadium_native_preview_data_url(
        canvas_state,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pitch_orientation=pitch_orientation,
    )
    if ';base64,' not in base_data_url:
        return ''
    try:
        raw = base64.b64decode(base_data_url.split(';base64,', 1)[1])
        source = Image.open(io.BytesIO(raw)).convert('RGBA')
    except Exception:
        return ''

    src_w, src_h = source.size
    out_w = src_w
    out_h = src_h
    canvas = Image.new('RGBA', (out_w, out_h), (233, 239, 245, 255))
    shadow = Image.new('RGBA', (out_w, out_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, 'RGBA')

    margin_x = int(out_w * 0.09)
    top_y = int(out_h * 0.10)
    bottom_y = int(out_h * 0.92)
    top_w = int(out_w * 0.62)
    bottom_w = int(out_w * 0.92)
    cx = out_w // 2
    dst_quad = (
        cx - top_w // 2,
        top_y,
        cx + top_w // 2,
        top_y,
        cx + bottom_w // 2,
        bottom_y,
        cx - bottom_w // 2,
        bottom_y,
    )

    shadow_quad = (
        dst_quad[0] + int(out_w * 0.02),
        dst_quad[1] + int(out_h * 0.02),
        dst_quad[2] + int(out_w * 0.02),
        dst_quad[3] + int(out_h * 0.02),
        dst_quad[4] + int(out_w * 0.02),
        dst_quad[5] + int(out_h * 0.02),
        dst_quad[6] + int(out_w * 0.02),
        dst_quad[7] + int(out_h * 0.02),
    )
    shadow_draw.polygon(shadow_quad, fill=(13, 24, 34, 55))
    try:
        shadow = shadow.filter(__import__('PIL.ImageFilter', fromlist=['GaussianBlur']).GaussianBlur(radius=max(8, int(out_w * 0.008))))
    except Exception:
        pass
    canvas.alpha_composite(shadow)

    transformed = source.transform(
        (out_w, out_h),
        Image.Transform.QUAD,
        data=dst_quad,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    canvas.alpha_composite(transformed)

    frame_draw = ImageDraw.Draw(canvas, 'RGBA')
    edge_width = max(2, int(out_w * 0.002))
    frame_draw.line((dst_quad[0], dst_quad[1], dst_quad[6], dst_quad[7]), fill=(8, 18, 28, 96), width=edge_width)
    frame_draw.line((dst_quad[2], dst_quad[3], dst_quad[4], dst_quad[5]), fill=(8, 18, 28, 96), width=edge_width)

    output = io.BytesIO()
    canvas.save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
