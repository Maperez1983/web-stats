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


def _partidos_abiertos(equipo):
    """Los partidos a los que se le puede colgar una jugada: los que aún no se han cerrado."""
    try:
        from .query_helpers import _team_match_queryset

        filas = []
        for m in _team_match_queryset(equipo).filter(is_closed=False).order_by('date')[:20]:
            rival = ''
            for lado in ('away_team', 'home_team'):
                otro = getattr(m, lado, None)
                if otro and otro.id != equipo.id:
                    rival = otro.name
                    break
            filas.append({'id': m.id, 'label': f"{m.date:%d/%m} · {rival or 'rival por definir'}"})
        return filas
    except Exception:
        return []


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

    # Cuántos dibujos hay en la pizarra antigua. Se enseña el número, no se migra nada: decidir si
    # eso se jubila o se rescata es suyo, y con un número delante se decide mejor que a ciegas.
    dibujos_antiguos = 0
    try:
        from .models import TacticalPlaybookClip, Team

        sistema = Team.objects.filter(slug='pizarra').first()
        ids = [equipo.id] + ([sistema.id] if sistema else [])
        dibujos_antiguos = TacticalPlaybookClip.objects.filter(team_id__in=ids).count()
    except Exception:
        dibujos_antiguos = 0

    return render(request, 'football/tactical_play.html', {
        'team': equipo,
        'team_name': equipo.display_name,
        'crest_url': _escudo_de(equipo),
        'dibujos_antiguos': dibujos_antiguos,
        'partidos_json': json.dumps(_partidos_abiertos(equipo)),
        # Los clips del equipo, para poder decir cuáles son la ejecución de una jugada.
        'clips_json': json.dumps(_clips_de(equipo)),
        # El tipo con el que se entra: "Balón parado" del menú abre esta misma pantalla ya filtrada.
        'tipo_inicial': request.GET.get('tipo', ''),
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


@login_required
@require_POST
def tactical_play_match(request):
    """
    Pone (o quita) una jugada en la charla de un partido.

    El partido guarda una LISTA de jugadas, no una copia de cada una: retocar la jugada retoca lo
    que se enseña el domingo, y la misma jugada puede estar en varios partidos.
    """
    from .query_helpers import _team_match_queryset
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        jugada_id = int(datos.get('play_id') or 0)
        partido_id = int(datos.get('match_id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    jugada = TacticalPlay.objects.filter(team=equipo, id=jugada_id).first()
    if not jugada:
        return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)
    partido = _team_match_queryset(equipo).filter(id=partido_id).first()
    if not partido:
        return JsonResponse({'ok': False, 'error': 'Partido no encontrado'}, status=404)

    if datos.get('remove'):
        partido.plays.remove(jugada)
        puesta = False
    else:
        partido.plays.add(jugada)
        puesta = True
    return JsonResponse({'ok': True, 'attached': puesta, 'total': partido.plays.count()})


# --- la jugada en movimiento (GIF) ------------------------------------------------------------
#
# Se compone con Pillow, no con el navegador: el PNG de la pizarra necesita Playwright y hay
# servidores donde no arranca (ya nos pasó con las previews). Un GIF que se cae la mitad de las
# veces no sirve para mandarlo al grupo del staff.
GIF_ANCHO = 720           # menos de la mitad del campo real: se ve igual en un móvil y pesa mucho menos
GIF_FOTOGRAMAS = 12       # por tramo entre dos pasos
GIF_MS = 70               # duración de cada fotograma
GIF_PAUSA_MS = 900        # lo que se queda quieto al llegar a cada paso


def _suave(t):
    """La misma curva que la animación de la pantalla: sale y entra despacio."""
    return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t


def _fuente(tam):
    """Una fuente de verdad para los dorsales: la de Pillow por defecto es diminuta y fija."""
    from PIL import ImageFont

    for ruta in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ):
        try:
            return ImageFont.truetype(ruta, tam)
        except Exception:
            continue
    try:
        return ImageFont.load_default(tam)
    except Exception:
        return ImageFont.load_default()


def _cesped_gif(ancho):
    from django.contrib.staticfiles import finders
    from PIL import Image

    ruta = finders.find('football/images/pitch3d/coach_home_pitch_surface.png')
    alto = round(ancho * ALTO / ANCHO)
    if not ruta:
        return Image.new('RGB', (ancho, alto), (31, 122, 77))
    fondo = Image.open(ruta).convert('RGB')
    return fondo.resize((ancho, alto), Image.LANCZOS)


def _trocear(pares, largo_raya, largo_hueco):
    """Parte un camino en trocitos para pintarlo discontinuo."""
    import math

    tramos, actual, pintando, resto = [], [], True, largo_raya
    for i in range(1, len(pares)):
        (x1, y1), (x2, y2) = pares[i - 1], pares[i]
        largo = math.hypot(x2 - x1, y2 - y1)
        recorrido = 0.0
        while recorrido < largo:
            paso = min(resto, largo - recorrido)
            a = ((x1 + (x2 - x1) * (recorrido / largo)), (y1 + (y2 - y1) * (recorrido / largo)))
            recorrido += paso
            b = ((x1 + (x2 - x1) * (recorrido / largo)), (y1 + (y2 - y1) * (recorrido / largo)))
            if pintando:
                actual.extend([a, b] if not actual else [b])
            resto -= paso
            if resto <= 0.001:
                if pintando and actual:
                    tramos.append(actual)
                    actual = []
                pintando = not pintando
                resto = largo_raya if pintando else largo_hueco
    if actual:
        tramos.append(actual)
    return [t for t in tramos if len(t) >= 2]


def _pinta_fotograma(fondo, nuestros, rivales, formas, escala):
    from PIL import Image, ImageDraw

    lienzo = fondo.copy()
    dibujo = ImageDraw.Draw(lienzo, 'RGBA')

    def punto(x, y):
        return (x * escala, y * escala)

    for f in formas or []:
        if f['tipo'] == 'linea':
            puntos = []
            for trozo in f['d'].replace('M', ' ').replace('L', ' ').split():
                puntos.append(float(trozo))
            pares = [punto(puntos[i], puntos[i + 1]) for i in range(0, len(puntos) - 1, 2)]
            if len(pares) >= 2:
                grosor = max(2, round(5 * escala))
                if f.get('dash'):
                    # Pillow no sabe pintar discontinuo: se trocea el camino a mano. Si no, el
                    # desmarque saldría igual que un pase y el GIF contaría otra cosa que la pantalla.
                    for tramo in _trocear(pares, 9.0, 7.0):
                        dibujo.line(tramo, fill=f['color'], width=grosor, joint='curve')
                else:
                    dibujo.line(pares, fill=f['color'], width=grosor, joint='curve')
                # La punta de flecha: un triángulo orientado como el último tramo.
                (x1, y1), (x2, y2) = pares[-2], pares[-1]
                import math

                ang = math.atan2(y2 - y1, x2 - x1)
                largo = max(8, 16 * escala)
                dibujo.polygon([
                    (x2, y2),
                    (x2 - largo * math.cos(ang - 0.45), y2 - largo * math.sin(ang - 0.45)),
                    (x2 - largo * math.cos(ang + 0.45), y2 - largo * math.sin(ang + 0.45)),
                ], fill=f['color'])
        elif f['tipo'] == 'rect':
            x, y = float(f['x']) * escala, float(f['y']) * escala
            dibujo.rectangle([x, y, x + float(f['w']) * escala, y + float(f['h']) * escala],
                             outline=f['color'], width=max(2, round(3 * escala)))
        elif f['tipo'] == 'balon':
            x, y = float(f['cx']) * escala, float(f['cy']) * escala
            r = max(4, 11 * escala)
            dibujo.ellipse([x - r, y - r, x + r, y + r], fill='#ffffff', outline='#12211b', width=2)
        elif f['tipo'] == 'cono':
            x, y = float(f['d'].split()[0][1:]) * escala, float(f['d'].split()[1]) * escala
            r = max(4, 10 * escala)
            dibujo.polygon([(x, y), (x + r, y + 2 * r), (x - r, y + 2 * r)], fill='#ff9f43')
        elif f['tipo'] == 'texto':
            dibujo.text((float(f['x']) * escala, float(f['y']) * escala), f.get('text') or '',
                        fill=f['color'], anchor='mm', font=_fuente(max(11, round(0.024 * lienzo.width))),
                        stroke_width=2, stroke_fill=(0, 0, 0))

    radio = max(9, round(0.028 * lienzo.width))
    tipo = _fuente(max(10, round(radio * 1.1)))
    for fila, relleno, borde in ((nuestros, (15, 122, 82), (234, 255, 245)), (rivales, (140, 31, 43), (255, 233, 236))):
        for ficha in fila or []:
            x = float(ficha.get('x_pct') or 0) / 100.0 * lienzo.width
            y = float(ficha.get('y_pct') or 0) / 100.0 * lienzo.height
            dibujo.ellipse([x - radio, y - radio, x + radio, y + radio], fill=relleno, outline=borde, width=2)
            dorsal = str(ficha.get('number') or '')
            if dorsal:
                dibujo.text((x, y), dorsal, fill=(255, 255, 255), anchor='mm', font=tipo)
    return lienzo


@login_required
def tactical_play_gif(request, play_id):
    """La jugada en movimiento, en GIF: lo que se manda al grupo del staff."""
    from django.http import HttpResponse

    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    jugada = TacticalPlay.objects.filter(team=equipo, id=play_id).first() if equipo else None
    if not jugada:
        return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)

    pasos = jugada.steps_data if isinstance(jugada.steps_data, list) else []
    if len(pasos) < 2:
        return JsonResponse({'ok': False, 'error': 'Hacen falta al menos dos pasos para animarla'}, status=400)

    fondo = _cesped_gif(GIF_ANCHO)
    escala = fondo.width / float(ANCHO)

    def interpolar(a, b, t):
        por_id = {str(p.get('id') or p.get('code')): p for p in (b or [])}
        salida = []
        for p in (a or []):
            fin = por_id.get(str(p.get('id') or p.get('code')))
            if not fin:
                salida.append(p)
                continue
            salida.append({
                **p,
                'x_pct': p.get('x_pct', 0) + (fin.get('x_pct', 0) - p.get('x_pct', 0)) * t,
                'y_pct': p.get('y_pct', 0) + (fin.get('y_pct', 0) - p.get('y_pct', 0)) * t,
            })
        return salida

    fotogramas, tiempos = [], []
    for i in range(len(pasos) - 1):
        desde, hasta = pasos[i], pasos[i + 1]
        formas = _dibujo(desde.get('shapes'))
        for k in range(GIF_FOTOGRAMAS):
            t = _suave(k / float(GIF_FOTOGRAMAS - 1))
            fotogramas.append(_pinta_fotograma(
                fondo,
                interpolar(desde.get('starters'), hasta.get('starters'), t),
                interpolar(desde.get('rival'), hasta.get('rival'), t),
                formas, escala,
            ))
            # El primero y el último de cada tramo se quedan quietos: si no, no da tiempo a leerlo.
            tiempos.append(GIF_PAUSA_MS if k in (0, GIF_FOTOGRAMAS - 1) else GIF_MS)
    # El último paso, con su dibujo, para cerrar.
    ultimo = pasos[-1]
    fotogramas.append(_pinta_fotograma(fondo, ultimo.get('starters'), ultimo.get('rival'),
                                       _dibujo(ultimo.get('shapes')), escala))
    tiempos.append(GIF_PAUSA_MS * 2)

    # UNA sola paleta para todos los fotogramas. Sin esto cada fotograma lleva la suya (el césped es
    # una foto, no un dibujo plano) y el GIF se va a varios MB: inservible para mandarlo por WhatsApp.
    #
    # La paleta NO puede salir sólo del césped: es todo verde, y el granate del rival acababa
    # cayendo al verde más cercano -los dos equipos salían del mismo color-. Se le pegan antes las
    # tintas que usamos.
    from PIL import ImageDraw as _Draw

    muestrario = fondo.copy()
    tintas = ['#0f7a52', '#8c1f2b', '#eafff5', '#ffe9ec', COLOR_BALON, COLOR_JUGADOR,
              COLOR_CLARO, '#ff9f43', '#ffffff', '#12211b']
    pincel = _Draw.Draw(muestrario)
    for i, tinta in enumerate(tintas):
        pincel.rectangle([i * 20, 0, i * 20 + 19, 24], fill=tinta)
    paleta = muestrario.quantize(colors=128, method=2)
    reducidos = [f.quantize(palette=paleta, dither=0) for f in fotogramas]

    import io

    buffer = io.BytesIO()
    reducidos[0].save(
        buffer, format='GIF', save_all=True, append_images=reducidos[1:],
        duration=tiempos, loop=0, optimize=True, disposal=1,
    )
    nombre = (jugada.name or 'jugada').replace('"', '').replace('/', '-')
    resp = HttpResponse(buffer.getvalue(), content_type='image/gif')
    resp['Content-Disposition'] = f'attachment; filename="{nombre}.gif"'
    return resp


@login_required
@require_POST
def tactical_play_clip(request):
    """
    Dice que un clip de vídeo es una EJECUCIÓN de esta jugada (o deshace el enlace).

    Es el puente entre Táctica y Análisis: el dibujo dice lo que quieres que pase y el clip enseña
    lo que pasó de verdad. Sin esto, el playbook y el vídeo eran dos cajones que no se hablaban.
    """
    from .models import VideoClip
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        jugada_id = int(datos.get('play_id') or 0)
        clip_id = int(datos.get('clip_id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    jugada = TacticalPlay.objects.filter(team=equipo, id=jugada_id).first()
    if not jugada:
        return JsonResponse({'ok': False, 'error': 'Jugada no encontrada'}, status=404)
    # El clip tiene que ser del equipo: los clips personales de otro analista no son nuestros.
    clip = VideoClip.objects.filter(id=clip_id, team=equipo).first()
    if not clip:
        return JsonResponse({'ok': False, 'error': 'Clip no encontrado'}, status=404)

    clip.tactical_play = None if datos.get('remove') else jugada
    clip.save(update_fields=['tactical_play', 'updated_at'])
    return JsonResponse({'ok': True, 'linked': bool(clip.tactical_play_id), 'total': jugada.clips.count()})


def _clips_de(equipo, jugada=None, limite=30):
    """Los clips del equipo, marcando cuáles son ejecuciones de esta jugada."""
    from .models import VideoClip

    filas = []
    try:
        qs = VideoClip.objects.filter(team=equipo).select_related('video', 'tactical_play')
        for clip in qs.order_by('-updated_at')[:limite]:
            filas.append({
                'id': clip.id,
                'title': (clip.title or 'Clip sin nombre')[:80],
                'video': str(getattr(clip.video, 'title', '') or '')[:60],
                'play_id': clip.tactical_play_id,
                'mine': bool(jugada and clip.tactical_play_id == jugada.id),
                'url': reverse('analysis-video-clip-view', args=[clip.id]) if clip.id else '',
            })
    except Exception:
        return []
    return filas
