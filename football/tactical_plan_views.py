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
from django.views.decorators.http import require_POST

from .models import Player, TacticalPlan, Team, TeamRosterSnapshot

LIMITE_TITULARES = 11
MAX_PLANTEAMIENTOS = 40

# La misma estructura base que el prepartido, en orientación 'lr' (campo horizontal, nosotros a la
# izquierda). Compartir las coordenadas es lo que permite volcar un planteamiento sobre un partido.
SLOTS = [
    (7, 50), (20, 18), (20, 39), (20, 61), (20, 82),
    (32, 30), (33, 50), (32, 70), (44, 18), (46, 50), (44, 82),
]
SLOTS_RIVAL = [(100 - x, 100 - y) for (x, y) in SLOTS]


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
    return {
        'code': str(item.get('code') or '')[:60],
        'name': nombre[:60],
        'number': str(item.get('number') or '').strip()[:4],
        'position': str(item.get('position') or '').strip()[:24],
        'photo_url': str(item.get('photo_url') or '').strip()[:400],
        'x_pct': _pct(item.get('x_pct'), x),
        'y_pct': _pct(item.get('y_pct'), y),
    }


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
        rivales.append({'id': snap.team_id, 'name': snap.team.name if snap.team else '—', 'players': len(filas)})

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
            }
            for p in jugadores
        ]),
        'rivales_json': json.dumps(rivales),
        'slots_json': json.dumps([{'x': x, 'y': y} for x, y in SLOTS]),
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

    return JsonResponse({
        'ok': True,
        'starters': len(normalizado.get('starters') or []),
        'added_to_convocation': len(faltan),
        'rival': len(rival_filas),
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
        jugadores.append({
            'code': str(row.get('code') or row.get('id') or f'row-{i}'),
            'name': nombre,
            'number': str(row.get('number') or row.get('dorsal') or '').strip(),
            'position': str(row.get('position') or '').strip(),
            'photo_url': str(row.get('photo_url') or '').strip(),
        })
    return JsonResponse({'ok': True, 'players': jugadores})
