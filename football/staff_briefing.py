from __future__ import annotations

from typing import Iterable

from football.services import compute_probable_eleven


def _safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _clean_text(value, fallback=''):
    text = str(value or '').strip()
    return text or fallback


def _pick_match_label(next_match: dict | None) -> dict:
    payload = next_match if isinstance(next_match, dict) else {}
    opponent = payload.get('opponent')
    if isinstance(opponent, dict):
        opponent_name = _clean_text(opponent.get('name'), 'Rival por confirmar')
    else:
        opponent_name = _clean_text(opponent, 'Rival por confirmar')
    return {
        'round': _clean_text(payload.get('round'), 'Jornada por confirmar'),
        'date': _clean_text(payload.get('date'), '--'),
        'time': _clean_text(payload.get('time'), '--:--'),
        'location': _clean_text(payload.get('location'), 'Campo por confirmar'),
        'opponent': opponent_name,
    }


def build_weekly_staff_brief(
    *,
    player_cards: Iterable[dict] | None,
    active_injury_ids: Iterable[int] | None,
    sanctioned_player_ids: Iterable[int] | None,
    convocation_player_ids: Iterable[int] | None,
    next_match: dict | None,
):
    cards = [dict(item) for item in (player_cards or []) if isinstance(item, dict)]
    injury_ids = {int(pid) for pid in (active_injury_ids or []) if pid}
    sanction_ids = {int(pid) for pid in (sanctioned_player_ids or []) if pid}
    convocation_ids = {int(pid) for pid in (convocation_player_ids or []) if pid}

    available_cards = [
        card
        for card in cards
        if _safe_int(card.get('player_id')) not in injury_ids | sanction_ids
    ]
    probable_eleven = compute_probable_eleven(available_cards)
    match_info = _pick_match_label(next_match)

    total_players = len(cards)
    available_count = len(available_cards)
    injury_count = len(injury_ids)
    sanction_count = len(sanction_ids)
    convoked_count = len(convocation_ids)

    starter_names = [
        _clean_text(player.get('name'), 'Jugador')
        for player in probable_eleven[:5]
    ]
    starter_label = ', '.join(starter_names) if starter_names else 'Pendiente de carga de minutos'

    alerts = []
    if injury_count:
        alerts.append(f'{injury_count} baja(s) por lesión activas.')
    if sanction_count:
        alerts.append(f'{sanction_count} jugador(es) sancionados para la próxima cita.')
    if convoked_count == 0:
        alerts.append('La convocatoria de la semana sigue sin cerrarse.')
    elif convoked_count < 16:
        alerts.append(f'Convocatoria corta: solo {convoked_count} disponibles confirmados.')
    if available_count < 11:
        alerts.append('No hay once limpio disponible con los datos actuales.')
    if not alerts:
        alerts.append('Disponibilidad estable para preparar la semana.')

    priorities = []
    if convoked_count == 0:
        priorities.append('Cerrar convocatoria y rival antes de diseñar la semana.')
    else:
        priorities.append('Ajustar la semana sobre la convocatoria ya guardada.')
    if injury_count or sanction_count:
        priorities.append('Preparar alternativas de once y cargas por bajas activas.')
    if available_count >= 11:
        priorities.append('Trabajar automatismos sobre un once probable ya identificable.')
    else:
        priorities.append('Priorizar disponibilidad y roles por línea antes del plan táctico.')

    return {
        'match': match_info,
        'availability': [
            {'label': 'Disponibles', 'value': available_count},
            {'label': 'Lesionados', 'value': injury_count},
            {'label': 'Sancionados', 'value': sanction_count},
            {'label': 'Convocados', 'value': convoked_count},
        ],
        'headline': (
            f"{available_count} disponibles de {total_players} "
            f"para {match_info['opponent']}"
        ),
        'alerts': alerts,
        'priorities': priorities,
        'probable_eleven_count': len(probable_eleven),
        'probable_eleven_preview': starter_label,
    }
