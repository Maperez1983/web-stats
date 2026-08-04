"""
Táctica · Planteamiento: nuestro once frente al del rival, guardado por EQUIPO.

Hasta ahora el área de Táctica tenía la pizarra de dibujo (que es el editor de tareas en modo
playbook) y una tabla de roles cuyo "encaje" sale vacío sin evaluaciones. Lo que no había era lo
primero que hace un entrenador: colocar su once y ponerle enfrente el del rival.

Eso sí existía, pero enterrado en el prepartido de UN partido concreto, así que se rehacía en cada
partido. Aquí el planteamiento cuelga del equipo: se piensa una vez y se aplica a los partidos que
haga falta.

Vive en su propio módulo a propósito: `views.py` pasa de las 90.000 líneas y meter aquí una
pantalla nueva es garantizar que nadie la encuentre.
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Player, TacticalPlan, Team, TeamRosterSnapshot

LIMITE_TITULARES = 11
# Las fases de un planteamiento. Son fijas a proposito: si cada entrenador se inventa las suyas,
# dos planteamientos del mismo club dejan de poder compararse.
FASES = (
    ('base', 'Once base'),
    ('salida', 'Salida de balón'),
    ('presion', 'Presión alta'),
    ('repliegue', 'Repliegue'),
    ('abp', 'Balón parado'),
)
MAX_PLANTEAMIENTOS = 40

# La misma estructura base que el prepartido, en orientación 'lr' (campo horizontal, nosotros a la
# izquierda). Compartir las coordenadas es lo que permite volcar un planteamiento sobre un partido.
SLOTS = [
    (7, 50), (20, 18), (20, 39), (20, 61), (20, 82),
    (32, 30), (33, 50), (32, 70), (44, 18), (46, 50), (44, 82),
]
SLOTS_RIVAL = [(100 - x, 100 - y) for (x, y) in SLOTS]

# Biblioteca de estructuras. La competencia presume de "más de 100 formaciones"; la mayoría son la
# misma con otro nombre. Estas son las que se juegan, y colocan el once de un clic para no empezar
# arrastrando once fichas. El portero va primero, y el orden es de atrás hacia delante.
FORMACIONES = {
    '1-4-4-2': [(7,50),(20,18),(20,39),(20,61),(20,82),(34,18),(34,39),(34,61),(34,82),(46,38),(46,62)],
    '1-4-3-3': [(7,50),(20,18),(20,39),(20,61),(20,82),(32,30),(33,50),(32,70),(44,18),(46,50),(44,82)],
    '1-4-2-3-1': [(7,50),(20,18),(20,39),(20,61),(20,82),(30,40),(30,60),(42,20),(42,50),(42,80),(50,50)],
    '1-4-1-4-1': [(7,50),(20,18),(20,39),(20,61),(20,82),(29,50),(39,18),(39,39),(39,61),(39,82),(49,50)],
    '1-3-5-2': [(7,50),(20,32),(20,50),(20,68),(32,12),(32,36),(33,50),(32,64),(32,88),(45,40),(45,60)],
    '1-5-3-2': [(7,50),(19,14),(20,32),(20,50),(20,68),(19,86),(33,32),(34,50),(33,68),(45,40),(45,60)],
    '1-3-4-3': [(7,50),(20,32),(20,50),(20,68),(32,14),(32,40),(32,60),(32,86),(45,20),(47,50),(45,80)],
    '1-4-4-2 rombo': [(7,50),(20,18),(20,39),(20,61),(20,82),(29,50),(36,26),(36,74),(43,50),(50,38),(50,62)],
}


def _pct(valor, por_defecto):
    try:
        num = float(valor)
    except (TypeError, ValueError):
        return por_defecto
    if num != num:  # NaN
        return por_defecto
    return round(max(0.0, min(100.0, num)), 2)


def _fila_nuestra(item, permitidos, indice):
    """Una ficha nuestra: sólo jugadores del equipo, y con su posición en el campo."""
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


def _fila_rival(item, indice):
    nombre = str(item.get('name') or '').strip()
    if not nombre:
        return None
    x, y = SLOTS_RIVAL[indice % len(SLOTS_RIVAL)]
    fila = {
        'code': str(item.get('code') or '')[:60],
        'name': nombre[:60],
        'number': str(item.get('number') or '').strip()[:4],
        'position': str(item.get('position') or '').strip()[:24],
        'photo_url': str(item.get('photo_url') or '').strip()[:400],
        'x_pct': _pct(item.get('x_pct'), x),
        'y_pct': _pct(item.get('y_pct'), y),
    }
    for clave in ('pj', 'minutes', 'goals', 'yellow', 'red'):
        try:
            fila[clave] = max(0, min(9999, int(item.get(clave) or 0)))
        except (TypeError, ValueError):
            fila[clave] = 0
    return fila


def _normalizar(payload, permitidos):
    datos = payload if isinstance(payload, dict) else {}
    nuestros, vistos = [], set()
    for i, item in enumerate(datos.get('starters') or []):
        if not isinstance(item, dict):
            continue
        fila = _fila_nuestra(item, permitidos, len(nuestros))
        if fila and fila['id'] not in vistos:
            vistos.add(fila['id'])
            nuestros.append(fila)
        if len(nuestros) >= LIMITE_TITULARES:
            break
    return {'starters': nuestros, '_meta': {'orientation': 'lr'}}


def _normalizar_rival(payload):
    datos = payload if isinstance(payload, dict) else {}
    filas = []
    for item in datos.get('starters') or []:
        if not isinstance(item, dict):
            continue
        fila = _fila_rival(item, len(filas))
        if fila:
            filas.append(fila)
        if len(filas) >= LIMITE_TITULARES:
            break
    return {'starters': filas, '_meta': {'orientation': 'lr'}}


def _bajas_del_equipo(jugadores, match=None):
    """
    Quién no puede jugar: lesionado o sancionado. Devuelve {id: motivo}.

    La sanción por ciclo de tarjetas depende del partido (se arrastra de la jornada anterior), así
    que sólo se mira cuando hay partido; la sanción puesta a mano vale siempre.
    """
    from django.utils import timezone

    from .query_helpers import get_active_injury_player_ids, get_sanctioned_player_ids_from_previous_round

    ids = [p.id for p in jugadores]
    fuera = {}
    try:
        for pid in get_active_injury_player_ids(ids) or []:
            fuera[int(pid)] = 'lesionado'
    except Exception:
        pass
    hoy = timezone.localdate()
    for p in jugadores:
        if fuera.get(p.id):
            continue
        if getattr(p, 'manual_sanction_active', False):
            hasta = getattr(p, 'manual_sanction_until', None)
            if not hasta or hasta >= hoy:
                fuera[p.id] = 'sancionado'
    if match is not None:
        try:
            equipo = getattr(jugadores[0], 'team', None) if jugadores else None
            for pid in get_sanctioned_player_ids_from_previous_round(equipo, reference_match=match) or []:
                if int(pid) in set(ids):
                    fuera.setdefault(int(pid), 'sancionado')
        except Exception:
            pass
    return fuera


def _escudo_de(equipo):
    if not equipo:
        return ''
    try:
        if getattr(equipo, 'crest_image', None):
            return equipo.crest_image.url
    except Exception:
        pass
    return str(getattr(equipo, 'crest_url', '') or '')


def _foto_de(request, player):
    from .views import resolve_player_avatar_url, resolve_player_photo_url

    try:
        foto = resolve_player_photo_url(request, player)
        if foto:
            return foto
    except Exception:
        pass
    try:
        return resolve_player_avatar_url(player) or ''
    except Exception:
        return ''


def _normalizar_fases(payload, permitidos):
    """Las fases guardadas: sólo las del catálogo y sólo con jugadores del equipo."""
    validas = dict(FASES)
    filas = payload if isinstance(payload, list) else []
    fuera = []
    vistas = set()
    for item in filas:
        if not isinstance(item, dict):
            continue
        clave = str(item.get('key') or '').strip()
        if clave not in validas or clave in vistas:
            continue
        vistas.add(clave)
        fuera.append({
            'key': clave,
            'name': validas[clave],
            'starters': (_normalizar({'starters': item.get('starters')}, permitidos))['starters'],
            'rival': (_normalizar_rival({'starters': item.get('rival')}))['starters'],
        })
    return fuera


def _plan_json(plan):
    return {
        'id': plan.id,
        'name': plan.name,
        'formation': plan.formation,
        'notes': plan.notes,
        'is_default': plan.is_default,
        'lineup': plan.lineup_data or {'starters': []},
        'rival_team_id': plan.rival_team_id,
        'rival_team_name': plan.rival_team.name if plan.rival_team else '',
        'rival_lineup': plan.rival_lineup_data or {'starters': []},
        'phases': plan.phases_data if isinstance(plan.phases_data, list) else [],
        'updated_at': plan.updated_at.isoformat() if plan.updated_at else '',
    }


@login_required
def tactical_plan_page(request):
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

    jugadores = list(
        Player.objects.filter(team=equipo, is_active=True).order_by('number', 'name')
    )
    # Quién NO está. Esto es lo que una pizarra suelta no puede saber: TacticalPad dibuja
    # círculos; aquí el círculo es un jugador del club, con su parte médico y su sanción.
    bajas = _bajas_del_equipo(jugadores)
    planes = list(TacticalPlan.objects.filter(team=equipo).select_related('rival_team'))

    # Rivales con plantilla ya volcada: son los únicos a los que se les puede poner un once
    # enfrente sin escribir 11 nombres a mano.
    rivales = []
    vistos = set()
    for snap in TeamRosterSnapshot.objects.select_related('team').order_by('team__name', '-updated_at'):
        if not snap.team_id or snap.team_id in vistos or snap.team_id == equipo.id:
            continue
        filas = snap.roster_payload if isinstance(snap.roster_payload, list) else []
        if not filas:
            continue
        vistos.add(snap.team_id)
        rivales.append({
            'id': snap.team_id,
            'name': snap.team.name if snap.team else '—',
            'players': len(filas),
            'crest': _escudo_de(snap.team),
        })

    # Partidos a los que se puede volcar el planteamiento: los que aun no se han cerrado.
    partidos = []
    try:
        from .query_helpers import _team_match_queryset

        for m in _team_match_queryset(equipo).filter(is_closed=False).order_by('date')[:20]:
            rival_nombre = ''
            for lado in ('away_team', 'home_team'):
                otro = getattr(m, lado, None)
                if otro and otro.id != equipo.id:
                    rival_nombre = otro.name
                    break
            partidos.append({
                'id': m.id,
                'label': f"{m.date:%d/%m} · {rival_nombre or 'rival por definir'}",
            })
    except Exception:
        partidos = []

    return render(request, 'football/tactical_plan.html', {
        'partidos_json': json.dumps(partidos),
        'team': equipo,
        'team_name': equipo.display_name,
        'planes_json': json.dumps([_plan_json(p) for p in planes]),
        'jugadores_json': json.dumps([
            {
                'id': p.id,
                'name': (p.nickname or p.name or '').strip(),
                'number': str(p.number or ''),
                'position': (p.position or '').strip(),
                # La cara del jugador: es lo que hace que la pizarra sea SU equipo y no once
                # círculos de color. Primero su foto; si no tiene, la figura recoloreada.
                'photo_url': _foto_de(request, p),
                'baja': bajas.get(p.id, ''),
            }
            for p in jugadores
        ]),
        'crest_url': _escudo_de(equipo),
        'rivales_json': json.dumps(rivales),
        'slots_json': json.dumps([{'x': x, 'y': y} for x, y in SLOTS]),
        'fases_json': json.dumps([{'key': k, 'name': n} for k, n in FASES]),
        'formaciones_json': json.dumps({
            nombre: [{'x': x, 'y': y} for (x, y) in puestos] for nombre, puestos in FORMACIONES.items()
        }),
        'starters_limit': LIMITE_TITULARES,
    })


@login_required
@require_POST
def tactical_plan_save(request):
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
        return JsonResponse({'ok': False, 'error': 'El planteamiento necesita un nombre'}, status=400)

    permitidos = {p.id: p for p in Player.objects.filter(team=equipo, is_active=True)}
    lineup = _normalizar(datos.get('lineup'), permitidos)
    rival_lineup = _normalizar_rival(datos.get('rival_lineup'))

    rival = None
    try:
        rival_id = int(datos.get('rival_team_id') or 0)
        if rival_id:
            rival = Team.objects.filter(id=rival_id).first()
    except (TypeError, ValueError):
        rival = None

    plan_id = datos.get('id')
    plan = TacticalPlan.objects.filter(team=equipo, id=plan_id).first() if plan_id else None
    if plan is None:
        if TacticalPlan.objects.filter(team=equipo).count() >= MAX_PLANTEAMIENTOS:
            return JsonResponse({'ok': False, 'error': 'Demasiados planteamientos guardados'}, status=400)
        # Mismo nombre = mismo planteamiento: guardar dos veces "1-4-3-3" no crea dos.
        plan = TacticalPlan.objects.filter(team=equipo, name=nombre).first()
    if plan is None:
        plan = TacticalPlan(team=equipo, created_by=request.user if request.user.is_authenticated else None)

    plan.name = nombre
    plan.formation = str(datos.get('formation') or '').strip()[:24]
    plan.notes = str(datos.get('notes') or '').strip()[:4000]
    plan.lineup_data = lineup
    plan.rival_team = rival
    plan.rival_lineup_data = rival_lineup
    plan.is_default = bool(datos.get('is_default'))
    plan.phases_data = _normalizar_fases(datos.get('phases'), permitidos)
    plan.save()

    if plan.is_default:
        TacticalPlan.objects.filter(team=equipo).exclude(id=plan.id).update(is_default=False)

    return JsonResponse({'ok': True, 'plan': _plan_json(plan)})


@login_required
@require_POST
def tactical_plan_delete(request):
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        plan_id = int(datos.get('id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)
    borrados, _ = TacticalPlan.objects.filter(team=equipo, id=plan_id).delete()
    return JsonResponse({'ok': bool(borrados)})


@login_required
def tactical_plan_board(request, plan_id):
    """
    Sólo el campo, sin menús ni paneles: es lo que se fotografía para la charla.

    Se sirve como página propia en vez de recortar la pantalla completa porque así la imagen sale
    siempre igual, mida lo que mida la ventana de quien la pide.
    """
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return redirect('coach-roster')
    plan = TacticalPlan.objects.filter(team=equipo, id=plan_id).select_related('rival_team').first()
    if not plan:
        return redirect('tactics-plan')

    porid = {p.id: p for p in Player.objects.filter(team=equipo, is_active=True)}
    nuestros = []
    for fila in (plan.lineup_data or {}).get('starters') or []:
        p = porid.get(fila.get('id'))
        nuestros.append({**fila, 'photo_url': _foto_de(request, p) if p else ''})

    return render(request, 'football/tactical_plan_board.html', {
        'plan': plan,
        'team_name': equipo.display_name,
        'crest_url': _escudo_de(equipo),
        'rival_name': plan.rival_team.name if plan.rival_team else '',
        'rival_crest': _escudo_de(plan.rival_team),
        'nuestros': nuestros,
        'rivales': (plan.rival_lineup_data or {}).get('starters') or [],
    })


@login_required
def tactical_plan_image(request, plan_id):
    """La foto del planteamiento en PNG, para el vestuario o el grupo del staff."""
    from django.http import HttpResponse

    from .preview_render import _acquire_playwright_browser
    from .task_board_snapshot import session_cookies_for
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    plan = TacticalPlan.objects.filter(team=equipo, id=plan_id).first() if equipo else None
    if not plan:
        return JsonResponse({'ok': False, 'error': 'Planteamiento no encontrado'}, status=404)

    url = request.build_absolute_uri(reverse('tactics-plan-board', args=[plan.id]))
    try:
        with _acquire_playwright_browser() as (pw, browser):
            if browser is None:
                return JsonResponse({'ok': False, 'error': 'La foto no está disponible en este servidor'}, status=503)
            contexto = browser.new_context(viewport={'width': 1400, 'height': 860}, device_scale_factor=2)
            try:
                cookies = session_cookies_for(request)
                if cookies:
                    contexto.add_cookies(cookies)
                pagina = contexto.new_page()
                pagina.goto(url, wait_until='networkidle', timeout=20000)
                nodo = pagina.query_selector('#tp-shot') or pagina
                imagen = nodo.screenshot(type='png')
            finally:
                try:
                    contexto.close()
                except Exception:
                    pass
    except Exception:
        return JsonResponse({'ok': False, 'error': 'No se pudo hacer la foto'}, status=500)

    nombre = (plan.name or 'planteamiento').replace('"', '').replace('/', '-')
    resp = HttpResponse(imagen, content_type='image/png')
    resp['Content-Disposition'] = f'attachment; filename="{nombre}.png"'
    return resp


@login_required
@require_POST
def tactical_plan_apply(request):
    """
    Vuelca un planteamiento sobre un partido: el once, sus posiciones y el rival.

    Escribe por el MISMO camino que el prepartido -convocatoria + MatchLineup, la doble escritura
    que ya existia- en vez de inventarse un tercer sitio donde guardar el once. Si se guardara
    aparte, la pizarra del partido y esta pantalla acabarian diciendo cosas distintas.
    """
    from django.utils import timezone

    from .models import MatchLineup, RivalConvocationRecord
    from .query_helpers import _team_match_queryset
    from .views import (
        _ensure_matchday_convocation_record,
        _forbid_if_no_coach_access,
        _get_primary_team_for_request,
        _normalize_lineup_payload_with_limit,
    )

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return JsonResponse({'ok': False, 'error': 'Equipo no configurado'}, status=400)
    try:
        datos = json.loads((request.body or b'{}').decode('utf-8') or '{}')
        plan_id = int(datos.get('plan_id') or 0)
        match_id = int(datos.get('match_id') or 0)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Datos ilegibles'}, status=400)

    plan = TacticalPlan.objects.filter(team=equipo, id=plan_id).select_related('rival_team').first()
    if not plan:
        return JsonResponse({'ok': False, 'error': 'Planteamiento no encontrado'}, status=404)
    partido = _team_match_queryset(equipo).filter(id=match_id).first()
    if not partido:
        return JsonResponse({'ok': False, 'error': 'Partido no encontrado'}, status=404)

    titulares = (plan.lineup_data or {}).get('starters') or []
    if not titulares:
        return JsonResponse({'ok': False, 'error': 'Ese planteamiento no tiene a nadie colocado'}, status=400)

    convocatoria = _ensure_matchday_convocation_record(equipo, match=partido)
    if not convocatoria:
        return JsonResponse({'ok': False, 'error': 'No se pudo preparar la convocatoria del partido'}, status=400)

    # Un titular tiene que estar convocado: si no, el once seria invalido y se caeria al guardar.
    # Se anaden los que falten y se dice cuantos, que es informacion util, no un efecto oculto.
    ids_plan = [int(f.get('id')) for f in titulares if str(f.get('id') or '').isdigit()]
    ya = set(convocatoria.players.values_list('id', flat=True))
    faltan = [pid for pid in ids_plan if pid not in ya]
    if faltan:
        nuevos = list(Player.objects.filter(team=equipo, is_active=True, id__in=faltan))
        if nuevos:
            convocatoria.players.add(*nuevos)

    permitidos = list(convocatoria.players.all())
    normalizado = _normalize_lineup_payload_with_limit(
        {'starters': titulares, 'bench': []}, permitidos, starters_limit=LIMITE_TITULARES
    )
    normalizado['_meta'] = {
        'saved_at': timezone.now().isoformat(),
        'starters_limit': LIMITE_TITULARES,
        'match_id': partido.id,
        'source': 'tactics-plan-apply',
        'plan_id': plan.id,
        'orientation': 'lr',
    }
    convocatoria.lineup_data = normalizado
    convocatoria.save(update_fields=['lineup_data'])
    MatchLineup.objects.update_or_create(
        team=equipo, match=partido, defaults={'lineup_data': normalizado}
    )

    # El rival, si el planteamiento lo lleva.
    rival_filas = (plan.rival_lineup_data or {}).get('starters') or []
    if rival_filas and plan.rival_team_id:
        RivalConvocationRecord.objects.update_or_create(
            team=equipo, match=partido,
            defaults={
                'rival_team': plan.rival_team,
                'provider': 'plan',
                'convocation_data': [
                    {k: f.get(k) for k in ('code', 'name', 'number', 'position', 'photo_url')}
                    for f in rival_filas
                ],
                'lineup_data': {'starters': rival_filas, 'bench': []},
            },
        )

    # Avisar de quién no puede jugar ESE partido. No se bloquea el volcado -el entrenador manda,
    # y una sanción puede estar mal metida- pero no se le deja descubrirlo el domingo.
    puestos = [p for p in permitidos if p.id in {int(f['id']) for f in (normalizado.get('starters') or [])}]
    bajas = _bajas_del_equipo(puestos, match=partido)
    avisos = [
        {'name': (p.nickname or p.name or '').strip(), 'motivo': bajas[p.id]}
        for p in puestos if p.id in bajas
    ]

    return JsonResponse({
        'ok': True,
        'starters': len(normalizado.get('starters') or []),
        'added_to_convocation': len(faltan),
        'rival': len(rival_filas),
        'warnings': avisos,
    })


@login_required
def tactical_plan_rival_report(request, plan_id):
    """
    El rival en una hoja: su once probable, quién mete los goles y quién ve tarjetas.

    Wyscout hace esto con vídeo para la élite. Aquí sale de lo que ya está importado de
    laPreferente, que para Preferente no lo tiene nadie.
    """
    from .views import _forbid_if_no_coach_access, _get_primary_team_for_request

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    equipo = _get_primary_team_for_request(request)
    if not equipo:
        return redirect('coach-roster')
    plan = TacticalPlan.objects.filter(team=equipo, id=plan_id).select_related('rival_team').first()
    if not plan or not plan.rival_team_id:
        return redirect('tactics-plan')

    snap = TeamRosterSnapshot.objects.filter(team_id=plan.rival_team_id).order_by('-updated_at').first()
    filas = [r for r in ((snap.roster_payload if snap else []) or []) if isinstance(r, dict) and (r.get('name') or '').strip()]

    def num(row, clave):
        try:
            return int(str(row.get(clave) or 0).strip() or 0)
        except (TypeError, ValueError):
            return 0

    plantilla = [{
        'name': (r.get('name') or '').strip(),
        'number': str(r.get('number') or r.get('dorsal') or '').strip(),
        'position': (r.get('position') or '').strip(),
        'photo_url': (r.get('photo_url') or '').strip(),
        'pj': num(r, 'pj'),
        'minutes': num(r, 'minutes'),
        'goals': num(r, 'goals'),
        'yellow': num(r, 'yellow_cards'),
        'red': num(r, 'red_cards'),
    } for r in filas]

    # El once probable: los de más minutos. Pero si NADIE tiene minutos -la temporada no ha
    # empezado, que es justo lo que pasa en agosto- ordenar por minutos es ordenar alfabéticamente
    # y presentarlo como "once probable" sería mentir con formato de dato. En ese caso no hay once.
    hay_minutos = any(p['minutes'] or p['pj'] for p in plantilla)
    probable = sorted(plantilla, key=lambda x: (-x['minutes'], -x['pj'], x['name']))[:11] if hay_minutos else []
    goleadores = [p for p in sorted(plantilla, key=lambda x: -x['goals']) if p['goals']][:5]
    tarjetas = [p for p in sorted(plantilla, key=lambda x: -(x['yellow'] + x['red'] * 2)) if (p['yellow'] or p['red'])][:5]

    return render(request, 'football/tactical_plan_rival_report.html', {
        'plan': plan,
        'team_name': equipo.display_name,
        'crest_url': _escudo_de(equipo),
        'rival': plan.rival_team,
        'rival_crest': _escudo_de(plan.rival_team),
        'plantilla': plantilla,
        'probable': probable,
        'goleadores': goleadores,
        'tarjetas': tarjetas,
        'hay_minutos': hay_minutos,
        'plantilla_ordenada': sorted(plantilla, key=lambda x: (x['position'], x['name'])),
        'nuestro_once': (plan.lineup_data or {}).get('starters') or [],
        'total_jugadores': len(plantilla),
    })


@login_required
def tactical_plan_rival_roster(request):
    """La plantilla volcada de un rival, para poner su once enfrente sin teclear nada."""
    from .views import _forbid_if_no_coach_access

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    try:
        rival_id = int(request.GET.get('rival') or 0)
    except (TypeError, ValueError):
        rival_id = 0
    if not rival_id:
        return JsonResponse({'ok': False, 'players': []})
    snap = TeamRosterSnapshot.objects.filter(team_id=rival_id).order_by('-updated_at').first()
    filas = snap.roster_payload if (snap and isinstance(snap.roster_payload, list)) else []
    jugadores = []
    for i, row in enumerate(filas):
        if not isinstance(row, dict):
            continue
        nombre = str(row.get('name') or '').strip()
        if not nombre:
            continue
        # Lo que ya sabemos de él: minutos, goles y tarjetas vienen en el mismo volcado y hasta
        # ahora no los usaba nadie. Saber que su 9 lleva 12 goles cambia cómo lo marcas.
        def _num(clave):
            try:
                return int(str(row.get(clave) or 0).strip() or 0)
            except (TypeError, ValueError):
                return 0

        jugadores.append({
            'code': str(row.get('code') or row.get('id') or f'row-{i}'),
            'name': nombre,
            'number': str(row.get('number') or row.get('dorsal') or '').strip(),
            'position': str(row.get('position') or '').strip(),
            'photo_url': str(row.get('photo_url') or '').strip(),
            'pj': _num('pj'),
            'minutes': _num('minutes'),
            'goals': _num('goals'),
            'yellow': _num('yellow_cards'),
            'red': _num('red_cards'),
        })
    return JsonResponse({'ok': True, 'players': jugadores})
