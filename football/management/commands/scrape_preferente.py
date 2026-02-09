from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from football.models import (
    Competition,
    DataSource,
    Group,
    Season,
    Team,
    TeamStanding,
)


def normalize_key(value: str) -> str:
    if not value:
        return ''
    return ''.join(ch.lower() for ch in value if ch.isalnum())


def parse_number(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip().replace(',', '.')
    if not text:
        return None
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = 'Extrae la clasificación del Grupo 2 de División de Honor Andaluza desde lapreferente.com'

    def add_arguments(self, parser):
        parser.add_argument('--url', required=True, help='URL de la clasificación que se consultará.')
        parser.add_argument(
            '--competition',
            dest='competition_name',
            default='División de Honor Andaluza',
            help='Nombre de la competición (usa para crear/actualizar el modelo)',
        )
        parser.add_argument('--season', default='2025/2026')
        parser.add_argument('--group', default='Grupo 2')
        parser.add_argument('--source-name', default='La Preferente')

    def handle(self, *args, **options):
        url = options['url']
        source_name = options['source_name']
        competition_name = options['competition_name']
        season_name = options['season']
        group_name = options['group']

        data_source, _ = DataSource.objects.get_or_create(
            name=source_name,
            defaults={'base_url': url, 'notes': 'Datos públicos ofrecidos por la web oficial.'},
        )

        competition, _ = Competition.objects.get_or_create(
            name=competition_name,
            defaults={
                'slug': slugify(competition_name),
                'region': 'Andalucía',
                'level': 5,
                'source': data_source,
            },
        )

        season, _ = Season.objects.get_or_create(
            competition=competition,
            name=season_name,
            defaults={'is_current': True},
        )

        group_slug = slugify(group_name)
        group, _ = Group.objects.get_or_create(
            season=season,
            slug=group_slug,
            defaults={'name': group_name},
        )

        response = requests.get(url, headers={'User-Agent': 'webstats-crm/1.0'})
        if response.status_code != 200:
            raise CommandError(f'No se pudo descargar la URL ({response.status_code}).')

        soup = BeautifulSoup(response.text, 'html.parser')
        standings_table = self.find_standings_table(soup)
        if standings_table is None:
            raise CommandError('No se encontró la tabla de clasificación en la página.')

        header_cells = [
            cell.get_text(strip=True) for cell in standings_table.find('tr').find_all(['th', 'td'])
        ]
        normalized_headers = [normalize_key(cell) or f'column_{idx}' for idx, cell in enumerate(header_cells)]

        updated = []
        for row in standings_table.find_all('tr')[1:]:
            cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
            if not cells or len(cells) < 2:
                continue

            row_data = {normalized_headers[idx]: cells[idx] for idx in range(min(len(cells), len(normalized_headers)))}

            team_name = self.get_value(row_data, ('equipo', 'team', 'club', 'clubes'))
            if not team_name:
                continue

            team, _ = Team.objects.update_or_create(
                slug=slugify(team_name),
                defaults={
                    'name': team_name,
                    'group': group,
                    'is_primary': 'benagalbon' in team_name.lower(),
                },
            )

            standing_values = {
                'position': parse_number(
                    self.get_value(row_data, ('pos', 'posición', 'position', 'puesto', 'clasificacion'))
                ),
                'played': parse_number(self.get_value(row_data, ('pj', 'jugados', 'played'))),
                'wins': parse_number(self.get_value(row_data, ('pg', 'victorias', 'wins'))),
                'draws': parse_number(self.get_value(row_data, ('pe', 'empates', 'draws'))),
                'losses': parse_number(self.get_value(row_data, ('pp', 'derrotas', 'losses'))),
                'goals_for': parse_number(self.get_value(row_data, ('gf', 'golsfavor', 'favor'))),
                'goals_against': parse_number(
                    self.get_value(row_data, ('gc', 'golscontra', 'contra'))
                ),
                'goal_difference': parse_number(self.get_value(row_data, ('dg', 'dif', 'goal_difference'))),
                'points': parse_number(self.get_value(row_data, ('pts', 'points', 'puntos'))),
            }

            position_value = standing_values.get('position')
            if position_value is None:
                position_value = parse_number(cells[0])
                standing_values['position'] = position_value

            if position_value is None:
                continue
            wins = standing_values.get('wins') or 0
            draws = standing_values.get('draws') or 0
            if standing_values.get('points') is None and wins is not None and draws is not None:
                standing_values['points'] = wins * 3 + draws

            gf = standing_values.get('goals_for')
            ga = standing_values.get('goals_against')
            if standing_values.get('goal_difference') is None and gf is not None and ga is not None:
                standing_values['goal_difference'] = gf - ga

            TeamStanding.objects.update_or_create(
                season=season,
                group=group,
                team=team,
                defaults={**{k: v for k, v in standing_values.items() if v is not None}, 'last_updated': timezone.now()},
            )
            updated.append(team.name)

        self.stdout.write(
            self.style.SUCCESS(
                f'Actualizada clasificación ({len(updated)} equipos) para {group_name} {season_name}'
            )
        )

    @staticmethod
    def find_standings_table(soup: BeautifulSoup) -> Optional[Any]:
        candidates = []
        for table in soup.find_all('table'):
            header = table.find('tr')
            if not header:
                continue
            header_texts = ' '.join(
                cell.get_text(strip=True).lower() for cell in header.find_all(['th', 'td'])
            )
            if 'equipo' in header_texts or ('pts' in header_texts and 'pj' in header_texts):
                candidates.append(table)

        return candidates[0] if candidates else None

    @staticmethod
    def get_value(data: Dict[str, str], keys: tuple) -> Optional[str]:
        for key in keys:
            normalized = normalize_key(key)
            if normalized in data and data[normalized]:
                return data[normalized]
        return None
