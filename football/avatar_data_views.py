"""
"Datos del avatar": una pantalla para completar de una vez lo que falta en toda la plantilla.

El generador de avatares necesita cinco datos por jugador —foto, fecha de nacimiento, complexión,
altura y pelo— y en este club casi todos están vacíos. Rellenarlos entrando ficha por ficha son 68
viajes de ida y vuelta, así que nadie los rellena y el avatar nunca sale bien.

Aquí se ven **sólo los que les falta algo**, con los campos al lado y un único guardado.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import Player

# El pelo del avatar se elige de una paleta corta: escribir un hex a mano en una tabla de 25 filas
# es pedir erratas. Son los tonos que usa el recoloreado.
COLORES_PELO = [
    ('#1b1512', 'Negro'),
    ('#4a2d1a', 'Castaño oscuro'),
    ('#7a4a24', 'Castaño'),
    ('#b07a3c', 'Rubio oscuro'),
    ('#d9b26a', 'Rubio'),
    ('#8c3b1e', 'Pelirrojo'),
    ('#9aa0a6', 'Canoso'),
]

CAMPOS = ('build', 'height_cm', 'hairstyle', 'hair_color', 'skin_grade')


def _falta_algo(player, tiene_foto):
    """Qué le falta a este jugador para tener un avatar suyo (lista de etiquetas)."""
    faltan = []
    if not tiene_foto:
        faltan.append('foto')
    if not getattr(player, 'birth_date', None):
        faltan.append('fecha de nacimiento')
    if not (getattr(player, 'build', '') or '').strip():
        faltan.append('complexión')
    if not getattr(player, 'height_cm', None):
        faltan.append('altura')
    if not (getattr(player, 'hairstyle', '') or '').strip():
        faltan.append('peinado')
    if not (getattr(player, 'hair_color', '') or '').strip():
        faltan.append('color de pelo')
    return faltan


@login_required
def coach_avatar_data_page(request):
    from .views import (
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

    guardados = 0
    if request.method == 'POST':
        # Se guarda SOLO lo que viene con valor: un campo vacío en la tabla significa "no lo sé
        # todavía", no "bórralo". Si vaciara, cada guardado parcial destruiría lo ya puesto.
        ids = [int(x) for x in request.POST.getlist('player_id') if str(x).isdigit()]
        jugadores = {p.id: p for p in Player.objects.filter(id__in=ids, team=primary_team)}
        with transaction.atomic():
            for pid, player in jugadores.items():
                tocados = []
                for campo in CAMPOS:
                    bruto = (request.POST.get(f'{campo}_{pid}') or '').strip()
                    if not bruto:
                        continue
                    if campo in ('height_cm', 'skin_grade'):
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
        return redirect(f'{url}?team={primary_team.id}&guardados={guardados}')

    filas = []
    completos = 0
    for player in Player.objects.filter(is_active=True, team=primary_team).order_by('number', 'name'):
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

    return render(request, 'football/coach_avatar_data.html', {
        'team_name': primary_team.display_name,
        'filas': filas,
        'completos': completos,
        'total': len(filas) + completos,
        'build_choices': Player.BUILD_CHOICES,
        'hairstyle_choices': Player.HAIRSTYLE_CHOICES,
        'colores_pelo': COLORES_PELO,
        'guardados': request.GET.get('guardados'),
    })
