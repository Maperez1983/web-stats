import io
import math

try:
    from PIL import Image, ImageFilter
except Exception:  # pragma: no cover
    Image = None
    ImageFilter = None


def recreate_canvas_state_from_preview_image_bytes(raw_bytes, canvas_width=1054, canvas_height=684):
    """
    Intenta reconstruir una pizarra editable a partir de una imagen raster (extraída del PDF).
    Es una aproximación basada en color/contornos (beta): zonas, conos, jugadores (local/visitante) y flechas simples.
    """
    if not raw_bytes or Image is None:
        return None
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.load()
        img = img.convert('RGB')
    except Exception:
        return None

    # Auto-crop al área del campo (dominante en verde) para mejorar el reconocimiento.
    # Muchos PDFs renderizados incluyen márgenes y tablas; sin recorte, los elementos quedan demasiado pequeños.
    try:
        w0, h0 = img.size
        if w0 > 0 and h0 > 0:
            probe_max = 320
            probe_scale = min(1.0, float(probe_max) / float(max(w0, h0)))
            probe = img
            if probe_scale < 1.0:
                probe = img.resize(
                    (max(1, int(round(w0 * probe_scale))), max(1, int(round(h0 * probe_scale)))),
                    Image.BILINEAR,
                )
            pw, ph = probe.size
            ppx = probe.load()

            minx = pw
            miny = ph
            maxx = -1
            maxy = -1
            green_count = 0
            for yy in range(ph):
                for xx in range(pw):
                    r, g, b = ppx[xx, yy]
                    if g > 70 and g > r + 14 and g > b + 14:
                        green_count += 1
                        if xx < minx:
                            minx = xx
                        if yy < miny:
                            miny = yy
                        if xx > maxx:
                            maxx = xx
                        if yy > maxy:
                            maxy = yy
            if maxx > minx and maxy > miny:
                area = float((maxx - minx + 1) * (maxy - miny + 1))
                total = float(max(1, pw * ph))
                # Recortamos si el área verde es sustancial (evita falsos positivos en PDFs sin pizarra).
                if area / total >= 0.12 and green_count / total >= 0.10:
                    pad = int(round(0.04 * float(max(pw, ph))))
                    minx = max(0, minx - pad)
                    miny = max(0, miny - pad)
                    maxx = min(pw - 1, maxx + pad)
                    maxy = min(ph - 1, maxy + pad)
                    sx = 1.0 / probe_scale
                    crop_box = (
                        int(minx * sx),
                        int(miny * sx),
                        int((maxx + 1) * sx),
                        int((maxy + 1) * sx),
                    )
                    # Clamp to image bounds
                    crop_box = (
                        max(0, min(int(crop_box[0]), w0 - 1)),
                        max(0, min(int(crop_box[1]), h0 - 1)),
                        max(1, min(int(crop_box[2]), w0)),
                        max(1, min(int(crop_box[3]), h0)),
                    )
                    if crop_box[2] > crop_box[0] + 20 and crop_box[3] > crop_box[1] + 20:
                        img = img.crop(crop_box)
    except Exception:
        pass

    try:
        world_w = max(320, int(canvas_width or 1054))
        world_h = max(180, int(canvas_height or 684))
    except Exception:
        world_w, world_h = 1054, 684

    w0, h0 = img.size
    if w0 <= 0 or h0 <= 0:
        return None
    # Más resolución => mejor detección de flechas/figuras (sin subir a tamaños que ralenticen demasiado).
    max_side = 780
    scale = min(1.0, float(max_side) / float(max(w0, h0)))
    if scale < 1.0:
        img = img.resize((max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))), Image.BILINEAR)
    w, h = img.size
    px = img.load()

    def _reservoir_sample_point(points, px_x, px_y, count, cap=1800):
        """
        Guarda una muestra representativa de puntos del componente (para endpoints/clasificación)
        sin sesgo de "los primeros píxeles explorados" por DFS/BFS.
        Usamos una variante determinista de reservoir sampling basada en hash.
        """
        if cap <= 0:
            return
        if len(points) < cap:
            points.append((px_x, px_y))
            return
        try:
            c = int(count or 0)
        except Exception:
            c = 0
        if c <= 0:
            return
        # Hash determinista "suficientemente aleatorio" para dispersar la muestra.
        h = ((int(px_x) + 1) * 73856093) ^ ((int(px_y) + 1) * 19349663) ^ (c * 83492791)
        j = int(h % c)
        if j < cap:
            points[j] = (px_x, px_y)

    def _iter_components(predicate, min_pixels=10, max_pixels=50000):
        visited = bytearray(w * h)
        components = []
        for y in range(h):
            row_base = y * w
            for x in range(w):
                idx = row_base + x
                if visited[idx]:
                    continue
                r, g, b = px[x, y]
                if not predicate(r, g, b):
                    continue
                queue = [idx]
                visited[idx] = 1
                minx = maxx = x
                miny = maxy = y
                count = 0
                sumx = sumy = 0
                sumr = sumg = sumb = 0
                points = []
                while queue:
                    cur = queue.pop()
                    cy, cx = divmod(cur, w)
                    rr, gg, bb = px[cx, cy]
                    if not predicate(rr, gg, bb):
                        continue
                    count += 1
                    sumx += cx
                    sumy += cy
                    sumr += rr
                    sumg += gg
                    sumb += bb
                    _reservoir_sample_point(points, cx, cy, count, cap=1800)
                    if cx < minx:
                        minx = cx
                    if cx > maxx:
                        maxx = cx
                    if cy < miny:
                        miny = cy
                    if cy > maxy:
                        maxy = cy
                    if cx > 0:
                        n = cur - 1
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cx + 1 < w:
                        n = cur + 1
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cy > 0:
                        n = cur - w
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cy + 1 < h:
                        n = cur + w
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if count > max_pixels:
                        break
                if count < min_pixels:
                    continue
                components.append(
                    {
                        'minx': minx,
                        'maxx': maxx,
                        'miny': miny,
                        'maxy': maxy,
                        'count': count,
                        'sumx': sumx,
                        'sumy': sumy,
                        'sumr': sumr,
                        'sumg': sumg,
                        'sumb': sumb,
                        'points': points,
                    }
                )
        return components

    def _iter_components_mask(mask_px, min_pixels=10, max_pixels=50000):
        """
        Igual que `_iter_components`, pero basado en una máscara binaria ya calculada.
        `mask_px[x, y]` debe ser >0 para considerar el pixel como parte del componente.
        """
        visited = bytearray(w * h)
        components = []
        for y in range(h):
            row_base = y * w
            for x in range(w):
                idx = row_base + x
                if visited[idx]:
                    continue
                if not mask_px[x, y]:
                    continue
                queue = [idx]
                visited[idx] = 1
                minx = maxx = x
                miny = maxy = y
                count = 0
                sumx = sumy = 0
                points = []
                while queue:
                    cur = queue.pop()
                    cy, cx = divmod(cur, w)
                    if not mask_px[cx, cy]:
                        continue
                    count += 1
                    sumx += cx
                    sumy += cy
                    _reservoir_sample_point(points, cx, cy, count, cap=1800)
                    if cx < minx:
                        minx = cx
                    if cx > maxx:
                        maxx = cx
                    if cy < miny:
                        miny = cy
                    if cy > maxy:
                        maxy = cy
                    if cx > 0:
                        n = cur - 1
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cx + 1 < w:
                        n = cur + 1
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cy > 0:
                        n = cur - w
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if cy + 1 < h:
                        n = cur + w
                        if not visited[n]:
                            visited[n] = 1
                            queue.append(n)
                    if count > max_pixels:
                        break
                if count < min_pixels:
                    continue
                components.append(
                    {
                        'minx': minx,
                        'maxx': maxx,
                        'miny': miny,
                        'maxy': maxy,
                        'count': count,
                        'sumx': sumx,
                        'sumy': sumy,
                        'points': points,
                    }
                )
        return components

    def _map_x(x):
        return float(x) / max(1, w) * float(world_w)

    def _map_y(y):
        return float(y) / max(1, h) * float(world_h)

    def _avg_rgb(comp):
        n = max(1, int(comp.get('count') or 1))
        return (
            int((comp.get('sumr') or 0) / n),
            int((comp.get('sumg') or 0) / n),
            int((comp.get('sumb') or 0) / n),
        )

    def _bbox(comp):
        return (
            int(comp.get('minx') or 0),
            int(comp.get('miny') or 0),
            int(comp.get('maxx') or 0),
            int(comp.get('maxy') or 0),
        )

    def _is_zone_color(r, g, b):
        return g >= 185 and r >= 120 and b <= 175 and (g - b) >= 35

    def _is_marker_color(r, g, b):
        if r <= 10 and g <= 10 and b <= 10:
            return False
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx < 85:
            return False
        if mx - mn < 55:
            return False
        if g > r and g > b and mx < 210 and (g - max(r, b)) < 70:
            return False
        return True

    def _is_ink_pixel(r, g, b):
        """
        Píxeles "tinta" (flechas/trazos) sobre el césped.
        - Excluye verdes dominantes (césped).
        - Incluye grises/negros incluso con anti-alias al reescalar.
        """
        # césped (verde dominante)
        if g > 70 and g > r + 14 and g > b + 14:
            return False
        # luminancia perceptual
        lum = 0.2126 * float(r) + 0.7152 * float(g) + 0.0722 * float(b)
        if lum <= 150:
            return True
        mx = max(r, g, b)
        mn = min(r, g, b)
        sat = mx - mn
        # Muchos PDFs rasterizan flechas/trazos en gris (no negro). Capturamos grises medios,
        # pero evitamos blancos puros para no "pillar" las líneas del campo.
        if lum <= 190 and sat <= 26 and mx <= 215:
            return True
        # colores medios saturados (p.ej. flechas oscuras no-grises)
        if lum <= 175 and sat >= 45 and mx <= 215:
            return True
        return False

    zones = _iter_components(_is_zone_color, min_pixels=180)
    markers = _iter_components(_is_marker_color, min_pixels=18, max_pixels=6000)
    ink_lines = []
    try:
        mask = Image.new('L', (w, h), 0)
        mp = mask.load()
        for yy in range(h):
            for xx in range(w):
                rr, gg, bb = px[xx, yy]
                if _is_ink_pixel(rr, gg, bb):
                    mp[xx, yy] = 255
        # Conecta trazos discontinuos (dash/dot) tras reescalar.
        if ImageFilter is not None:
            try:
                mask = mask.filter(ImageFilter.MaxFilter(3))
                mp = mask.load()
            except Exception:
                pass
        ink_lines = _iter_components_mask(mp, min_pixels=28, max_pixels=22000)
    except Exception:
        # Fallback sin máscara: no reconstruye flechas, pero no rompe el import.
        ink_lines = []

    objects = []

    for comp in zones:
        x1, y1, x2, y2 = _bbox(comp)
        bw = max(1, x2 - x1 + 1)
        bh = max(1, y2 - y1 + 1)
        if bw < 18 or bh < 14:
            continue
        if (bw * bh) < 260:
            continue
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        objects.append(
            {
                'type': 'rect',
                'left': _map_x(cx),
                'top': _map_y(cy),
                'originX': 'center',
                'originY': 'center',
                'width': _map_x(bw) - _map_x(0),
                'height': _map_y(bh) - _map_y(0),
                'rx': 12,
                'ry': 12,
                'fill': 'rgba(34,211,238,0.16)',
                'stroke': '#22d3ee',
                'strokeWidth': 3,
                'data': {'kind': 'zone', 'color': '#22d3ee'},
                'objectCaching': False,
            }
        )

    for comp in markers:
        x1, y1, x2, y2 = _bbox(comp)
        bw = max(1, x2 - x1 + 1)
        bh = max(1, y2 - y1 + 1)
        area = int(comp.get('count') or 0)
        if bw > 46 or bh > 46:
            continue
        if area > 2600:
            continue
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        r, g, b = _avg_rgb(comp)
        is_green = g > r + 35 and g > b + 35 and g >= 120
        is_purple = b >= 120 and r >= 80 and g <= 135 and (b - g) >= 25
        is_red = r >= 140 and g <= 120 and (r - g) >= 30
        is_orange = r >= 150 and g >= 80 and b <= 120 and (r - b) >= 35

        if (is_red or is_orange) and area <= 520:
            objects.append(
                {
                    'type': 'triangle',
                    'left': _map_x(cx),
                    'top': _map_y(cy),
                    'originX': 'center',
                    'originY': 'center',
                    'width': 24,
                    'height': 24,
                    'fill': '#f97316',
                    'stroke': '#7c2d12',
                    'strokeWidth': 1.6,
                    'data': {'kind': 'cone', 'color': '#f97316'},
                    'objectCaching': False,
                }
            )
            continue

        if is_green and area <= 900:
            objects.append(
                {
                    # Importante: usamos un grupo "token" mínimo para que el editor JS
                    # lo convierta automáticamente a la chapa oficial (player_local).
                    'type': 'group',
                    'left': _map_x(cx),
                    'top': _map_y(cy),
                    'originX': 'center',
                    'originY': 'center',
                    'objectCaching': False,
                    'data': {
                        'kind': 'token',
                        'token_kind': 'player_local',
                        'playerName': 'Jugador',
                        'playerNumber': '',
                    },
                    'objects': [
                        {
                            'type': 'circle',
                            'left': 0,
                            'top': 0,
                            'originX': 'center',
                            'originY': 'center',
                            'radius': 16,
                            'fill': '#1d4ed8',
                            'stroke': '#eff6ff',
                            'strokeWidth': 2,
                            'objectCaching': False,
                        }
                    ],
                }
            )
            continue

        if is_purple and area <= 1100:
            objects.append(
                {
                    # Token rival mínimo => conversión a chapa oficial (player_rival).
                    'type': 'group',
                    'left': _map_x(cx),
                    'top': _map_y(cy),
                    'originX': 'center',
                    'originY': 'center',
                    'objectCaching': False,
                    'data': {
                        'kind': 'token',
                        'token_kind': 'player_rival',
                        'playerName': 'Rival',
                        'playerNumber': '',
                    },
                    'objects': [
                        {
                            'type': 'circle',
                            'left': 0,
                            'top': 0,
                            'originX': 'center',
                            'originY': 'center',
                            'radius': 16,
                            'fill': '#dc2626',
                            'stroke': '#fff7ed',
                            'strokeWidth': 2,
                            'objectCaching': False,
                        }
                    ],
                }
            )
            continue

    for comp in ink_lines:
        x1, y1, x2, y2 = _bbox(comp)
        bw = max(1, x2 - x1 + 1)
        bh = max(1, y2 - y1 + 1)
        bbox_area = int(bw * bh)
        count = int(comp.get('count') or 0)
        if bw < 22 and bh < 22:
            continue
        if bbox_area < 260:
            continue
        # Densidad alta => normalmente etiquetas rectangulares o iconos rellenos (no flechas).
        density = float(count) / float(max(1, bbox_area))
        if density > 0.62 and bbox_area > 520:
            continue
        points = comp.get('points') or []
        if len(points) < 12:
            continue

        # Algunas figuras geométricas llegan como contorno (no relleno) y se confunden con diagonales.
        # Intentamos detectar rectángulos/círculos para convertirlos a "shape-*" editable.
        def _edge_hit_counts(_points, tol=4):
            left = right = top = bottom = 0
            for (pxx, pyy) in _points:
                if abs(pxx - x1) <= tol:
                    left += 1
                if abs(pxx - x2) <= tol:
                    right += 1
                if abs(pyy - y1) <= tol:
                    top += 1
                if abs(pyy - y2) <= tol:
                    bottom += 1
            return left, right, top, bottom

        def _looks_like_rect_outline(_points):
            if bw < 46 or bh < 46:
                return False
            left, right, top, bottom = _edge_hit_counts(_points, tol=4)
            total = max(1, len(_points))
            min_edge = max(12, int(round(0.05 * total)))
            if left < min_edge or right < min_edge or top < min_edge or bottom < min_edge:
                return False
            edge_sum = left + right + top + bottom
            # La mayoría de puntos deben estar cerca del perímetro.
            # Nota: tras `MaxFilter`/anti-alias puede haber "relleno" parcial; usamos umbral más laxo.
            if (edge_sum / float(total)) < 0.55:
                return False
            # Evita "marcos" muy finos (probablemente líneas del campo).
            if min(bw, bh) < 18:
                return False
            return True

        def _looks_like_circle_outline(_points):
            if bw < 44 or bh < 44:
                return False
            aspect = float(bw) / float(max(1, bh))
            if aspect < 0.78 or aspect > 1.28:
                return False
            # Si hay mucha presencia en los 4 bordes del bbox, no es un círculo (es un rectángulo).
            left, right, top, bottom = _edge_hit_counts(_points, tol=4)
            total = max(1, len(_points))
            min_edge = max(12, int(round(0.06 * total)))
            if left >= min_edge and right >= min_edge and top >= min_edge and bottom >= min_edge:
                return False
            cx0 = (x1 + x2) / 2.0
            cy0 = (y1 + y2) / 2.0
            stride = max(1, int(len(_points) / 220))
            dists = []
            for (pxx, pyy) in _points[::stride]:
                dx0 = float(pxx) - cx0
                dy0 = float(pyy) - cy0
                dists.append((dx0 * dx0 + dy0 * dy0) ** 0.5)
            if len(dists) < 10:
                return False
            mean = sum(dists) / float(len(dists))
            if mean < 18:
                return False
            var = sum((d - mean) ** 2 for d in dists) / float(len(dists))
            stdev = var ** 0.5
            return stdev <= mean * 0.18

        if _looks_like_rect_outline(points):
            cx0 = (x1 + x2) / 2.0
            cy0 = (y1 + y2) / 2.0
            world_wd = _map_x(bw) - _map_x(0)
            world_ht = _map_y(bh) - _map_y(0)
            kind = 'shape-rect'
            if 0.92 <= (float(bw) / float(max(1, bh))) <= 1.08:
                kind = 'shape-square'
            objects.append(
                {
                    'type': 'rect',
                    'left': _map_x(cx0),
                    'top': _map_y(cy0),
                    'originX': 'center',
                    'originY': 'center',
                    'width': world_wd,
                    'height': world_ht,
                    'rx': 10,
                    'ry': 10,
                    'fill': 'rgba(34,211,238,0.12)',
                    'stroke': '#22d3ee',
                    'strokeWidth': 3,
                    'data': {'kind': kind},
                    'objectCaching': False,
                }
            )
            continue

        if _looks_like_circle_outline(points):
            cx0 = (x1 + x2) / 2.0
            cy0 = (y1 + y2) / 2.0
            world_wd = _map_x(bw) - _map_x(0)
            world_ht = _map_y(bh) - _map_y(0)
            radius = max(12.0, min(world_wd, world_ht) / 2.0)
            objects.append(
                {
                    'type': 'circle',
                    'left': _map_x(cx0),
                    'top': _map_y(cy0),
                    'originX': 'center',
                    'originY': 'center',
                    'radius': radius,
                    'fill': 'rgba(34,211,238,0.12)',
                    'stroke': '#22d3ee',
                    'strokeWidth': 3,
                    'data': {'kind': 'shape-circle'},
                    'objectCaching': False,
                }
            )
            continue

        min_s = 1e9
        max_s = -1e9
        min_d = 1e9
        max_d = -1e9
        p_min_s = p_max_s = p_min_d = p_max_d = points[0]
        for (pxx, pyy) in points:
            s = pxx + pyy
            d = pxx - pyy
            if s < min_s:
                min_s = s
                p_min_s = (pxx, pyy)
            if s > max_s:
                max_s = s
                p_max_s = (pxx, pyy)
            if d < min_d:
                min_d = d
                p_min_d = (pxx, pyy)
            if d > max_d:
                max_d = d
                p_max_d = (pxx, pyy)
        candidates = [(p_min_s, p_max_s), (p_min_d, p_max_d)]
        best = None
        best_len = 0.0
        for a, b in candidates:
            dx = float(b[0] - a[0])
            dy = float(b[1] - a[1])
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > best_len:
                best_len = dist
                best = (a, b)
        if not best or best_len < 20:
            continue
        (ax, ay), (bx, by) = best
        x1w, y1w = _map_x(ax), _map_y(ay)
        x2w, y2w = _map_x(bx), _map_y(by)
        cx = (x1w + x2w) / 2.0
        cy = (y1w + y2w) / 2.0
        dx = x2w - x1w
        dy = y2w - y1w
        length = (dx * dx + dy * dy) ** 0.5
        if length < 52:
            continue
        angle = (180.0 / math.pi) * math.atan2(dy, dx)
        base_len = 102.0
        scale_x = max(0.55, min(6.2, float(length) / base_len))
        objects.append(
            {
                'type': 'group',
                'left': cx,
                'top': cy,
                'originX': 'center',
                'originY': 'center',
                'angle': angle,
                'scaleX': scale_x,
                'scaleY': 1.0,
                'data': {'kind': 'arrow'},
                'objectCaching': False,
                'objects': [
                    {
                        'type': 'line',
                        'x1': -50,
                        'y1': 0,
                        'x2': 40,
                        'y2': 0,
                        'originX': 'center',
                        'originY': 'center',
                        'stroke': '#22d3ee',
                        'strokeWidth': 4,
                        'objectCaching': False,
                    },
                    {
                        'type': 'triangle',
                        'left': 52,
                        'top': 0,
                        'width': 18,
                        'height': 18,
                        'angle': 90,
                        'fill': '#22d3ee',
                        'originX': 'center',
                        'originY': 'center',
                        'objectCaching': False,
                    },
                ],
            }
        )

    if not objects:
        return None
    objects_sorted = []
    objects_sorted.extend([obj for obj in objects if str(obj.get('type')) == 'rect'])
    objects_sorted.extend([obj for obj in objects if str(obj.get('type')) != 'rect'])
    return {'version': '5.3.0', 'objects': objects_sorted}


