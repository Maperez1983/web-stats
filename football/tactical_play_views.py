"""
Táctica · Jugadas: dibujar lo que pasa, por pasos, sobre el campo de siempre.

El Planteamiento cuenta DÓNDE se coloca cada uno. Esto cuenta QUÉ hace: el lateral sube por fuera,
el interior cae a recibir, el pase va al espacio. Eso son trazos, y hasta ahora la única forma de
dibujarlos era la "pizarra de jugadas", que es el editor de tareas de entrenamiento en modo playbook:
pedía RPE, carga y bloque, y acababa guardando la jugada como una tarea de entrenamiento en un equipo
de sistema llamado PIZARRA. Es decir, mezclaba jugadas con ejercicios.

Aquí la jugada es una jugada, parte de tu once real y se guarda por EQUIPO. Comparte campo, fichas,
pasos y animación con el Planteamiento a propósito: el área tiene que parecer un programa, no tres.
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Player, TacticalPlan, TacticalPlay
from .tactical_plan_views import (
    LIMITE_TITULARES,
    SLOTS,
    SLOTS_RIVAL,
    _bajas_del_equipo,
    _escudo_de,
    _foto_de,
    _pct,
)

# Las herramientas de dibujo. Son estas y no más a propósito: una pizarra con treinta pinceles no se
# usa, y cada trazo de aquí significa algo que un entrenador reconoce de un vistazo.
#   pase        línea continua con punta      el balón viaja
#   conduccion  línea ondulada con punta      el balón viaja CON el jugador
#   desmarque   línea discontinua con punta   se mueve el jugador, no el balón
#   zona        rectángulo                    el espacio del que hablamos
#   cono        marca                         material puesto en el campo
#   balon       marca                         dónde está el balón
#   texto       etiqueta                      lo que no cabe en un trazo
HERRAMIENTAS = ('pase', 'conduccion', 'desmarque', 'zona', 'cono', 'balon', 'texto')
UNA_MARCA = ('cono', 'balon', 'texto')  # de un solo punto

MAX_JUGADAS = 60
MAX_PASOS = 12
MAX_TRAZOS = 60
MAX_PUNTOS = 60


def _punto(item):
    if not isinstance(item, dict):
        return None
    return {'x': _pct(item.get('x'), 50), 'y': _pct(item.get('y'), 50)}


def _normalizar_trazo(item):
    if not isinstance(item, dict):
        return None
    herramienta = str(item.get('tool') or '').strip()
    if herramienta not in HERRAMIENTAS:
        return None
    puntos = []
    for p in (item.get('points') or [])[:MAX_PUNTOS]:
        punto = _punto(p)
        if punto:
            puntos.append(punto)
    if not puntos:
        return None
    # Una marca es un punto; un trazo necesita dos. Un "pase" de un solo punto no es nada y sólo
    # serviría para dejar basura invisible en el dibujo.
    if herramienta in UNA_MARCA:
        puntos = puntos[:1]
    elif len(puntos) < 2:
        return None
    return {
        'tool': herramienta,
        'points': puntos,
        'text': str(item.get('text') or '').strip()[:60],
    }


def _normalizar_ficha_nuestra(item, permitidos, indice):
    try:
        pid = int(item.get('id'))
    except (TypeError, ValueError):
        return None
    player = permitidos.get(pid)
    if player is None:
        return None
    x, y = SLOTS[indice % len(SLOTS)]
    return {
        'id': pid,
        'name': (player.nickname or player.name or '').strip()[:60],
        'number': str(player.number or '').strip()[:4],
        'position': (player.position or '').strip()[:12],
        'x_pct': _pct(item.get('x_pct'), x),
        'y_pct': _pct(item.get('y_pct'), y),
    }


def _normalizar_ficha_rival(item, indice):
    x, y = SLOTS_RIVAL[indice % len(SLOTS_RIVAL)]
    nombre = str(item.get('name') or '').strip()[:60]
    numero = str(item.get('number') or '').strip()[:4]
    if not nombre and not numero:
        return None
    return {
        'code': str(item.get('code') or f'r{indice}')[:60],
        'name': nombre,
        'number': numero,
        'position': str(item.get('position') or '').strip()[:24],
        'photo_url': str(item.get('photo_url') or '').strip()[:400],
        'x_pct': _pct(item.get('x_pct'), x),
        'y_pct': _pct(item.get('y_pct'), y),
    }


def _normalizar_pasos(payload, permitidos):
    filas = payload if isinstance(payload, list) else []
    pasos = []
    for i, item in enumerate(filas[:MAX_PASOS]):
        if not isinstance(item, dict):
            continue
        nuestros, vistos = [], set()
        for fila in (item.get('starters') or []):
            if not isinstance(fila, dict):
                continue
            ficha = _normalizar_ficha_nuestra(fila, permitidos, len(nuestros))
            if ficha and ficha['id'] not in vistos:
                vistos.add(ficha['id'])
                nuestros.append(ficha)
            if len(nuestros) >= LIMITE_TITULARES:
                break
        rivales = []
        for fila in (item.get('rival') or []):
            if not isinstance(fila, dict):
                continue
            ficha = _normalizar_ficha_rival(fila, len(rivales))
            if ficha:
                rivales.append(ficha)
            if len(rivales) >= LIMITE_TITULARES:
                break
        trazos = []
        for fila in (item.get('shapes') or [])[:MAX_TRAZOS]:
            trazo = _normalizar_trazo(fila)
            if trazo:
                trazos.append(trazo)
        pasos.append({
            'name': str(item.get('name') or f'Paso {i + 1}').strip()[:40] or f'Paso {i + 1}',
            'starters': nuestros,
            'rival': rivales,
            'shapes': trazos,
        })
    return pasos


def _jugada_json(jugada):
    return {
        'id': jugada.id,
        'name': jugada.name,
        'kind': jugada.kind,
        'kind_label': jugada.get_kind_display(),
        'notes': jugada.notes,
        'steps': jugada.steps_data if isinstance(jugada.steps_data, list) else [],
        'published': bool(jugada.published_to_players),
        'updated_at': jugada.updated_at.isoformat() if jugada.updated_at else '',
    }


# El campo en unidades de dibujo. Es el tamaño real de la foto del césped, y es el mismo viewBox
# que usa el editor: así un trazo se ve igual en pantalla y en el PNG.
ANCHO = 1664
ALTO = 945
COLOR_BALON = '#6fd3ff'    # lo que hace el balón: pase y conducción
COLOR_JUGADOR = '#ffd76a'  # lo que hace el jugador sin balón: el desmarque
COLOR_CLARO = '#eaf4ef'


def _xy(punto):
    return (float(punto.get('x') or 0) / 100.0 * ANCHO, float(punto.get('y') or 0) / 100.0 * ALTO)


def _n(valor):
    return f'{valor:.1f}'


def _ondular(puntos):
    """La conducción va ondulada. Sin esto, un pase y una conducción serían la misma raya."""
    salida = []
    amplitud, tramo, lado = 9.0, 26.0, 1
    for i in range(1, len(puntos)):
        ax, ay = puntos[i - 1]
        bx, by = puntos[i]
        dx, dy = bx - ax, by - ay
        largo = (dx * dx + dy * dy) ** 0.5
        if largo < 0.01:
            continue
        nx, ny = -dy / largo, dx / largo
        recorrido = 0.0
        while recorrido + tramo <= largo:
            recorrido += tramo
            t = recorrido / largo
            salida.append((ax + dx * t + nx * amplitud * lado, ay + dy * t + ny * amplitud * lado))
            lado *= -1
    return salida


def _dibujo(trazos):
    """Traduce los trazos guardados a formas listas para pintar.

    La geometría se resuelve AQUÍ y no en la plantilla: una plantilla con cuentas dentro es
    exactamente el sitio donde luego nadie encuentra por qué una flecha sale torcida.
    """
    formas = []
    for trazo in trazos or []:
        if not isinstance(trazo, dict):
            continue
        herramienta = trazo.get('tool')
        puntos = [_xy(p) for p in (trazo.get('points') or []) if isinstance(p, dict)]
        if not puntos:
            continue
        if herramienta == 'zona':
            (ax, ay), (bx, by) = puntos[0], puntos[-1]
            formas.append({
                'tipo': 'rect',
                'x': _n(min(ax, bx)), 'y': _n(min(ay, by)),
                'w': _n(abs(bx - ax)), 'h': _n(abs(by - ay)),
                'color': COLOR_CLARO,
            })
        elif herramienta == 'cono':
            x, y = puntos[0]
            formas.append({
                'tipo': 'cono',
                'd': f'M{_n(x)} {_n(y - 14)} L{_n(x + 12)} {_n(y + 10)} L{_n(x - 12)} {_n(y + 10)} z',
            })
        elif herramienta == 'balon':
            x, y = puntos[0]
            formas.append({'tipo': 'balon', 'cx': _n(x), 'cy': _n(y)})
        elif herramienta == 'texto':
            x, y = puntos[0]
            formas.append({'tipo': 'texto', 'x': _n(x), 'y': _n(y), 'text': trazo.get('text') or '', 'color': COLOR_CLARO})
        elif herramienta in ('pase', 'conduccion', 'desmarque'):
            if len(puntos) < 2:
                continue
            camino = [puntos[0]] + _ondular(puntos) + [puntos[-1]] if herramienta == 'conduccion' else puntos
            d = ' '.join(('L' if i else 'M') + _n(x) + ' ' + _n(y) for i, (x, y) in enumerate(camino))
            formas.append({
                'tipo': 'linea',
                'd': d,
                'color': COLOR_JUGADOR if herramienta == 'desmarque' else COLOR_BALON,
                'dash': '16 12' if herramienta == 'desmarque' else '',
                'punta': 'jugador' if herramienta == 'desmarque' else 'balon',
            })
    return formas


def _con_fotos(request, pasos, equipo):
    """Las caras de los jugadores no se guardan en la jugada: se resuelven al pintarla.

    Guardarlas dentro sería congelar una URL que cambia cada vez que se regenera un avatar.
    """
    porid = {p.id: p for p in Player.objects.filter(team=equipo, is_active=True)}
    fuera = []
    for paso in pasos or []:
        nuevos = []
        for fila in (paso.get('starters') or []):
            p = porid.get(fila.get('id'))
            nuevos.append({**fila, 'photo_url': _foto_de(request, p) if p else ''})
        fuera.append({**paso, 'starters': nuevos, 'formas': _dibujo(paso.get('shapes'))})
    return fuera


@login_required
def tactical_play_page(request):
    from .views import _forbid_if_no_coach_access, _forbid_if_workspace_module_disabled, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    forbidden = _forbid_if_workspace_module_disabled(request, 'tactics', label='táctica')
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return redirect('coach-roster')

    jugadores = list(Player.objects.filter(team=equipo, is_active=True).order_by('number', 'name'))
    bajas = _bajas_del_equipo(jugadores)
    jugadas = list(TacticalPlay.objects.filter(team=equipo))

    # Los planteamientos guardados sirven de punto de partida: una jugada casi siempre empieza con
    # el once que ya has colocado, no con el campo vacío.
    planes = [
        {
            'id': plan.id,
            'name': plan.name,
            'starters': (plan.lineup_data or {}).get('starters') or [],
            'rival': (plan.rival_lineup_data or {}).get('starters') or [],
        }
        for plan in TacticalPlan.objects.filter(team=equipo).select_related('rival_team')
    ]

    return render(request, 'football/tactical_play.html', {
        'team': equipo,
        'team_name': equipo.display_name,
        'crest_url': _escudo_de(equipo),
        'jugadas_json': json.dumps([_jugada_json(j) for j in jugadas]),
        'jugadores_json': json.dumps([
            {
                'id': p.id,
                'name': (p.nickname or p.name or '').strip(),
                'number': str(p.number or ''),
                'position': (p.position or '').strip(),
                'photo_url': _foto_de(request, p),
                'baja': bajas.get(p.id, ''),
            }
            for p in jugadores
        ]),
        'planes_json': json.dumps(planes),
        'slots_json': json.dumps([{'x': x, 'y': y} for x, y in SLOTS]),
        'tipos_json': json.dumps([{'key': k, 'name': n} for k, n in TacticalPlay.KIND_CHOICES]),
        'starters_limit': LIMITE_TITULARES,
        'max_pasos': MAX_PASOS,
    })


@login_required
@require_POST
def tactical_play_save(request):
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    nombre = str(datos.get('name') or '').strip()[:80]
    if not nombre:
        return JsonResponse({'ok': False, 'error': 'La jugada necesita un nombre'}, status=400)

    permitidos = {p.id: p for p in Player.objects.filter(team=equipo, is_active=True)}
    pasos = _normalizar_pasos(datos.get('steps'), permitidos)
    # Una jugada sin nadie y sin un solo trazo no es una jugada: sería una ficha en la lista que al
    # abrirla no enseña nada.
    if not any((p['starters'] or p['rival'] or p['shapes']) for p in pasos):
        return JsonResponse({'ok': False, 'error': 'La jugada está vacía: coloca a alguien o dibuja algo'}, status=400)

    jugada_id = datos.get('id')
    jugada = TacticalPlay.objects.filter(team=equipo, id=jugada_id).first() if jugada_id else None
    if jugada is None:
        if TacticalPlay.objects.filter(team=equipo).count() >= MAX_JUGADAS:
            return JsonResponse({'ok': False, 'error': 'Demasiadas jugadas guardadas'}, status=400)
        # Mismo nombre = misma jugada: guardar dos veces "Salida 3-2" no crea dos.
        jugada = TacticalPlay.objects.filter(team=equipo, name=nombre).first()
    if jugada is None:
        jugada = TacticalPlay(team=equipo, created_by=request.user if request.user.is_authenticated else None)

    tipos = {k for k, _ in TacticalPlay.KIND_CHOICES}
    jugada.name = nombre
    jugada.kind = datos.get('kind') if datos.get('kind') in tipos else TacticalPlay.KIND_ATAQUE
    jugada.notes = str(datos.get('notes') or '').strip()[:4000]
    jugada.steps_data = pasos
    jugada.save()
    return JsonResponse({'ok': True, 'play': _jugada_json(jugada)})


@login_required
@require_POST
def tactical_play_delete(request):
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        jugada_id = int(datos.get('id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)
    borrados, _ = TacticalPlay.objects.filter(team=equipo, id=jugada_id).delete()
    return JsonResponse({'ok': bool(borrados)})


@login_required
def tactical_play_board(request, play_id):
    """
    Sólo el campo, sin menús: la jugada paso a paso, que es lo que se enseña en la charla.

    Con `?paso=N` sale un único paso, que es lo que fotografía el PNG.
    """
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return redirect('coach-roster')
    jugada = TacticalPlay.objects.filter(team=equipo, id=play_id).first()
    if not jugada:
        return redirect('tactics-plays')

    pasos = _con_fotos(request, jugada.steps_data if isinstance(jugada.steps_data, list) else [], equipo)
    # El número va dentro del paso, no lo cuenta la plantilla: al pedir uno suelto seguiría diciendo
    # "1" aunque fuese el tercero.
    for i, p in enumerate(pasos, start=1):
        p['n'] = i
    try:
        pedido = int(request.GET.get('paso') or 0)
    except (TypeError, ValueError):
        pedido = 0
    if pedido:
        pasos = pasos[pedido - 1:pedido]

    return render(request, 'football/tactical_play_board.html', {
        'play': jugada,
        'team_name': equipo.display_name,
        'crest_url': _escudo_de(equipo),
        'pasos': pasos,
        'kind_label': jugada.get_kind_display(),
    })


@login_required
def tactical_play_image(request, play_id):
    """La jugada en PNG, para el grupo del staff o el vestuario."""
    from django.http import HttpResponse

    from .preview_render import _acquire_playwright_browser
    from .task_board_snapshot import session_cookies_for
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    jugada = TacticalPlay.objects.filter(team=equipo, id=play_id).first() if equipo else None
    if not jugada:
        return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)

    url = request.build_absolute_uri(reverse('tactics-play-board', args=[jugada.id]))
    try:
        with _acquire_playwright_browser() as (pw, browser):
            if browser is None:
                return JsonResponse({'ok': False, 'error': 'La foto no está disponible en este servidor'}, status=503)
            contexto = browser.new_context(viewport={'width': 1400, 'height': 1200}, device_scale_factor=2)
            try:
                cookies = session_cookies_for(request)
                if cookies:
                    contexto.add_cookies(cookies)
                pagina = contexto.new_page()
                pagina.goto(url, wait_until='networkidle', timeout=25000)
                nodo = pagina.query_selector('#tj-shot') or pagina
                imagen = nodo.screenshot(type='png')
            finally:
                try:
                    contexto.close()
                except Exception:
                    pass
    except Exception:
        return JsonResponse({'ok': False, 'error': 'No se pudo hacer la foto'}, status=500)

    nombre = (jugada.name or 'jugada').replace('"', '').replace('/', '-')
    resp = HttpResponse(imagen, content_type='image/png')
    resp['Content-Disposition'] = f'attachment; filename="{nombre}.png"'
    return resp


@login_required
@require_POST
def tactical_play_attach_task(request):
    """
    Engancha una jugada a una tarea de entrenamiento (o la desengancha).

    Es un ENLACE, no una copia: la tarea apunta a la jugada, así que retocar la jugada retoca lo
    que enseña el ejercicio. Copiarla habría creado la segunda fuente de siempre.
    """
    from .models import SessionTask
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        tarea_id = int(request.POST.get('task_id') or 0)
        jugada_id = int(request.POST.get('play_id') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    tarea = SessionTask.objects.filter(id=tarea_id, session__microcycle__team=equipo).first()
    if not tarea:
        return JsonResponse({'ok': False, 'error': 'Tarea no encontrada'}, status=404)

    if jugada_id:
        jugada = TacticalPlay.objects.filter(team=equipo, id=jugada_id).first()
        if not jugada:
            return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)
        tarea.tactical_play = jugada
    else:
        tarea.tactical_play = None
    tarea.save(update_fields=['tactical_play'])

    destino = request.POST.get('next') or ''
    if destino.startswith('/'):
        return redirect(destino)
    return JsonResponse({'ok': True, 'play_id': tarea.tactical_play_id})


@login_required
@require_POST
def tactical_play_publish(request):
    """
    Publica (o retira) la jugada en el espacio de los jugadores, y les avisa.

    Publicar es un gesto deliberado: que una jugada exista no significa que el equipo tenga que
    verla. Y el aviso va por el mismo camino que la convocatoria (PlayerNotification), no por uno
    nuevo.
    """
    from django.utils import timezone

    from .models import Player, PlayerNotification
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        jugada_id = int(datos.get('id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    jugada = TacticalPlay.objects.filter(team=equipo, id=jugada_id).first()
    if not jugada:
        return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)

    publicar = bool(datos.get('publish', True))
    jugada.published_to_players = publicar
    jugada.published_at = timezone.now() if publicar else None
    jugada.save(update_fields=['published_to_players', 'published_at'])

    avisados = 0
    if publicar:
        enlace = reverse('tactics-play-player', args=[jugada.id])
        workspace = None
        try:
            from .workspace_context import get_active_workspace

            workspace = get_active_workspace(request)
        except Exception:
            workspace = None
        for player in Player.objects.filter(team=equipo, is_active=True).select_related('user'):
            usuario = getattr(player, 'user', None)
            if not usuario:
                continue  # sin cuenta no hay a quién avisar; la jugada le espera igual en su espacio
            PlayerNotification.objects.create(
                workspace=workspace,
                team=equipo,
                target_user=usuario,
                created_by_user=request.user if request.user.is_authenticated else None,
                kind=PlayerNotification.KIND_GENERAL,
                title='Jugada nueva: ' + jugada.name,
                message='Tu entrenador ha publicado una jugada. Míratela antes del próximo entreno.',
                link_url=enlace,
            )
            avisados += 1

    return JsonResponse({'ok': True, 'published': publicar, 'notified': avisados})


@login_required
def tactical_play_player_board(request, play_id):
    """
    La jugada tal cual la ve un jugador: el mismo campo, sin nada que tocar.

    Dos llaves, como el resto del portal: la jugada tiene que estar PUBLICADA y ser de SU equipo.
    El cuerpo técnico también puede abrirla (así comprueba qué se ve).
    """
    from .models import Player
    from .permissions import can_access_coach_workspace

    jugada = TacticalPlay.objects.filter(id=play_id).first()
    if not jugada:
        return redirect('player-home')

    es_staff = False
    try:
        es_staff = bool(can_access_coach_workspace(request.user))
    except Exception:
        es_staff = False

    if not es_staff:
        suya = Player.objects.filter(user=request.user, team_id=jugada.team_id, is_active=True).exists()
        if not suya or not jugada.published_to_players:
            return redirect('player-home')

    pasos = _con_fotos(request, jugada.steps_data if isinstance(jugada.steps_data, list) else [], jugada.team)
    for i, p in enumerate(pasos, start=1):
        p['n'] = i

    return render(request, 'football/tactical_play_board.html', {
        'play': jugada,
        'team_name': jugada.team.display_name if jugada.team else '',
        'crest_url': _escudo_de(jugada.team),
        'pasos': pasos,
        'kind_label': jugada.get_kind_display(),
        'para_jugador': True,
    })
