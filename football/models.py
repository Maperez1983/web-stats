from django.db import models
from django.utils import timezone


class DataSource(models.Model):
    name = models.CharField(max_length=120, unique=True)
    base_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Data Source'
        verbose_name_plural = 'Data Sources'

    def __str__(self):
        return self.name


class Competition(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150)
    description = models.TextField(blank=True)
    level = models.PositiveSmallIntegerField(null=True, help_text='1=Top tier, higher numbers=lower tiers')
    region = models.CharField(max_length=120, blank=True)
    source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('name', 'region')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.region or "N/A"})'


class Season(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='seasons')
    name = models.CharField(max_length=80, help_text='Ej. 2025/2026')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        unique_together = ('competition', 'name')
        ordering = ['-start_date', '-name']

    def __str__(self):
        return f'{self.name} - {self.competition.name}'


class Group(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80)
    external_id = models.CharField(max_length=80, blank=True, help_text='ID que usa La Preferente')

    class Meta:
        unique_together = ('season', 'slug')

    def __str__(self):
        return f'{self.name} ({self.season.name})'


class Team(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    short_name = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=100, blank=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    external_id = models.CharField(max_length=120, blank=True, help_text='Identificador oficial en la web')
    is_primary = models.BooleanField(default=False, help_text='Marcar si es el equipo de Benagalbón')

    def __str__(self):
        return self.name


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    name = models.CharField(max_length=120)
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('team', 'name')

    def __str__(self):
        return f'{self.name} ({self.team.name})'


class ConvocationRecord(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='convocations')
    players = models.ManyToManyField(Player, related_name='convocations')
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def mark_replaced(self):
        if self.is_current:
            self.is_current = False
            self.save(update_fields=['is_current'])


class Match(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='matches')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    round = models.CharField(max_length=50, blank=True, help_text='Jornada / ronda')
    date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    home_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='away_matches')
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    result = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    source = models.URLField(blank=True)

    class Meta:
        ordering = ['-date', 'round']

    def __str__(self):
        if self.home_team and self.away_team:
            return f'{self.home_team} vs {self.away_team} - {self.round or self.date}'
        return f'Match {self.id}'


class TeamStanding(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='standings')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='standings')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='standings')
    position = models.PositiveSmallIntegerField()
    played = models.PositiveSmallIntegerField(default=0)
    wins = models.PositiveSmallIntegerField(default=0)
    draws = models.PositiveSmallIntegerField(default=0)
    losses = models.PositiveSmallIntegerField(default=0)
    goals_for = models.PositiveSmallIntegerField(default=0)
    goals_against = models.PositiveSmallIntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.PositiveSmallIntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('season', 'group', 'team')
        ordering = ['position']

    def __str__(self):
        return f'{self.team.name} ({self.season.name}) - {self.points} pts'


class TeamStatistic(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='statistics')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='team_statistics')
    name = models.CharField(max_length=120, help_text='p.ej. Posesión, disparos a puerta')
    value = models.FloatField()
    context = models.CharField(max_length=120, blank=True, help_text='Contexto específico (jornada, rival...)')
    source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('team', 'season', 'name', 'context')

    def __str__(self):
        return f'{self.team.name} - {self.name}: {self.value}'


class PlayerStatistic(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='statistics')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='player_statistics')
    match = models.ForeignKey(Match, on_delete=models.SET_NULL, null=True, blank=True, related_name='player_statistics')
    name = models.CharField(max_length=120, help_text='Goal, asistencia, min jugados, etc.')
    value = models.FloatField()
    context = models.CharField(max_length=120, blank=True)
    source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('player', 'season', 'match', 'name', 'context')

    def __str__(self):
        return f'{self.player.name} - {self.name}: {self.value}'


class CustomMetric(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='custom_metrics')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='custom_metrics')
    name = models.CharField(max_length=120)
    value = models.FloatField()
    recorded_at = models.DateTimeField(default=timezone.now)
    source_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Custom Metric'
        verbose_name_plural = 'Custom Metrics'
        ordering = ['-recorded_at']

    def __str__(self):
        return f'{self.team.name} - {self.name} = {self.value}'


class MatchReport(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='reports', null=True)
    source_file = models.CharField(max_length=200)
    imported_at = models.DateTimeField(default=timezone.now)
    raw_data = models.JSONField(default=dict)

    class Meta:
        ordering = ['-imported_at']

    def __str__(self):
        return f'Report {self.source_file} ({self.imported_at:%Y-%m-%d})'


class MatchEvent(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='events')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    minute = models.PositiveSmallIntegerField(null=True, blank=True)
    event_type = models.CharField(max_length=120)
    result = models.CharField(max_length=120, blank=True)
    zone = models.CharField(max_length=120, blank=True)
    tercio = models.CharField(max_length=120, blank=True)
    observation = models.CharField(max_length=255, blank=True)
    system = models.CharField(max_length=120, blank=True)
    source_file = models.CharField(max_length=200)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Match Event'
        verbose_name_plural = 'Match Events'
        ordering = ['match', 'minute']

    def __str__(self):
        player_label = self.player.name if self.player else 'Jugador desconocido'
        return f'{self.match} - {player_label} - {self.event_type}'


class DataImportLog(models.Model):
    file_name = models.CharField(max_length=200)
    imported_at = models.DateTimeField(default=timezone.now)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-imported_at']

    def __str__(self):
        return f'{self.file_name} ({self.imported_at:%Y-%m-%d %H:%M})'


class ScrapeSource(models.Model):
    name = models.CharField(max_length=150)
    url = models.URLField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Fuente de scraping'
        verbose_name_plural = 'Fuentes de scraping'

    def __str__(self):
        return self.name


class ScrapeRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running', 'En ejecución'
        SUCCESS = 'success', 'Completado'
        ERROR = 'error', 'Error'

    source = models.ForeignKey(ScrapeSource, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RUNNING)
    message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Ejecución de scraping'
        verbose_name_plural = 'Ejecuciones de scraping'

    def __str__(self):
        return f'{self.source.name} · {self.get_status_display()}'

    def to_dict(self):
        return {
            'source': self.source.name,
            'url': self.source.url,
            'status': self.status,
            'message': self.message,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
