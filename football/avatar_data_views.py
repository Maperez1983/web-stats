"""
"Datos del avatar": una pantalla para completar de una vez lo que falta en toda la plantilla.

El generador de avatares necesita seis datos por jugador —foto, fecha de nacimiento, complexión,
altura, peinado y color de pelo— y en este club casi todos están vacíos. Rellenarlos entrando
ficha por ficha son 68 viajes de ida y vuelta, así que nadie los rellena y el avatar nunca sale
bien.

Aquí se ven **sólo los que les falta algo**, con los campos al lado y un único guardado, y se
puede saltar de equipo a equipo sin salir de la pantalla: el club son siete equipos, no uno.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from .models import Player, Workspace, WorkspaceTeam

# El pelo se elige de una paleta corta (escribir un hex a mano en una tabla de 25 filas es pedir
# erratas), y es LA MISMA que ofrece la ficha del jugador: esta pantalla tenía su propia lista de
# tonos, así que "Rubio" aquí y "Rubio" allí guardaban dos colores distintos.

CAMPOS = ('build', 'height_cm', 'hairstyle', 'hair_color', 'skin_grade', 'birth_date')

# Lo que se puede saber sin preguntarle al almacenamiento. La foto se mira aparte porque cada
# comprobación es una llamada a S3: para los contadores de los otros equipos no compensa.
CAMPOS_EN_BASE = ('birth_date', 'build', 'height_cm', 'hairstyle', 'hair_color')


def _vacio(player, campo):
    valor = getattr(player, campo, None)
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    return False


def _falta_algo(player, tiene_foto):
    """Qué le falta a este jugador para tener un avatar suyo (lista de etiquetas)."""
    etiquetas = {
        'birth_date': 'fecha de nacimiento',
        'build': 'complexión',
        'height_cm': 'altura',
        'hairstyle': 'peinado',
        'hair_color': 'color de pelo',
    }
    faltan = [] if tiene_foto else ['foto']
    faltan += [etiquetas[c] for c in CAMPOS_EN_BASE if _vacio(player, c)]
    return faltan


def _equipos_del_club(request):
    """Los equipos del club activo, para poder cambiar de plantilla sin salir de aquí."""
    from .workspace_context import get_active_workspace

    workspace = None
    try:
        workspace = get_active_workspace(request)
    except Exception:
        workspace = None
    if workspace is None or getattr(workspace, 'kind', None) != Workspace.KIND_CLUB:
        return []
    enlaces = (
        WorkspaceTeam.objects.filter(workspace=workspace)
        .select_related('team')
        .order_by('team__name', 'id')
    )
    return [e.team for e in enlaces if getattr(e, 'team', None)]


@login_required
def coach_avatar_data_page(request):
    from .views import (
        AVATAR_HAIR_COLORS,
        _forbid_if_no_coach_access,
        _get_primary_team_for_request,
    )
    from .management.commands.generate_player_avatars import _find_player_photo_name, edad_de

    forbidden = _forbid_if_no_coach_access(request.user)
    if forbidden:
        return forbidden
    primary_team = _get_primary_team_for_request(request)
    if not primary_team:
        return redirect('coach-roster')

    equipos = _equipos_del_club(request)
    equipo = primary_team
    pedido = (request.POST.get('equipo') if request.method == 'POST' else request.GET.get('equipo')) or ''
    if str(pedido).isdigit():
        for t in equipos:
            if t.id == int(pedido):
                equipo = t
                break

    guardados = 0
    if request.method == 'POST':
        # Se guarda SOLO lo que viene con valor: un campo vacío en la tabla significa "no lo sé
        # todavía", no "bórralo". Si vaciara, cada guardado parcial destruiría lo ya puesto.
        ids = [int(x) for x in request.POST.getlist('player_id') if str(x).isdigit()]
        jugadores = {p.id: p for p in Player.objects.filter(id__in=ids, team=equipo)}
        with transaction.atomic():
            for pid, player in jugadores.items():
                tocados = []
                for campo in CAMPOS:
                    bruto = (request.POST.get(f'{campo}_{pid}') or '').strip()
                    if not bruto:
                        continue
                    if campo == 'birth_date':
                        # parse_date y no el ayudante de views.py: aquel vive ANIDADO dentro de
                        # una vista, así que importarlo revienta en tiempo de ejecución.
                        valor = parse_date(bruto)
                        if not valor:
                            continue
                    elif campo in ('height_cm', 'skin_grade'):
                        try:
                            valor = int(bruto)
                        except ValueError:
                            continue
                        if campo == 'height_cm' and not (90 <= valor <= 230):
                            continue
                        if campo == 'skin_grade' and not (1 <= valor <= 6):
                            continue
                    else:
                        valor = bruto[:16]
                    if getattr(player, campo, None) != valor:
                        setattr(player, campo, valor)
                        tocados.append(campo)
                if tocados:
                    player.save(update_fields=tocados)
                    guardados += 1
        url = reverse('coach-avatar-data')
        return redirect(f'{url}?equipo={equipo.id}&guardados={guardados}')

    filas = []
    completos = 0
    for player in Player.objects.filter(is_active=True, team=equipo).order_by('number', 'name'):
        tiene_foto = bool(_find_player_photo_name(player))
        faltan = _falta_algo(player, tiene_foto)
        if not faltan:
            completos += 1
            continue
        filas.append({
            'p': player,
            'edad': edad_de(player),
            'tiene_foto': tiene_foto,
            'faltan': faltan,
        })

    # Contador por equipo: sólo con lo que está en la base de datos. Comprobar la foto son cuatro
    # llamadas al almacenamiento por jugador; multiplicado por siete equipos, la pantalla tardaría
    # más en pintarse que lo que se tarda en rellenar una fila.
    pestanas = []
    for t in equipos:
        pendientes = 0
        total_t = 0
        for p in Player.objects.filter(is_active=True, team=t).only(*CAMPOS_EN_BASE):
            total_t += 1
            if any(_vacio(p, c) for c in CAMPOS_EN_BASE):
                pendientes += 1
        pestanas.append({
            'team': t,
            'pendientes': pendientes,
            'total': total_t,
            'activo': t.id == equipo.id,
        })

    return render(request, 'football/coach_avatar_data.html', {
        'team': equipo,
        'team_name': equipo.display_name,
        'pestanas': pestanas,
        'filas': filas,
        'completos': completos,
        'total': len(filas) + completos,
        'build_choices': Player.BUILD_CHOICES,
        'hairstyle_choices': Player.HAIRSTYLE_CHOICES,
        'colores_pelo': AVATAR_HAIR_COLORS,
        'guardados': request.GET.get('guardados'),
    })
