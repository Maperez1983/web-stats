from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import secrets


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
    preferente_url = models.URLField(blank=True, help_text='URL del equipo en LaPreferente')
    is_primary = models.BooleanField(default=False, help_text='Marcar si es el equipo de Benagalbón')

    def __str__(self):
        return self.name


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    name = models.CharField(max_length=120)
    full_name = models.CharField(max_length=180, blank=True)
    nickname = models.CharField(max_length=80, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=60, blank=True)
    injury = models.CharField(max_length=180, blank=True)
    injury_type = models.CharField(max_length=80, blank=True)
    injury_zone = models.CharField(max_length=80, blank=True)
    injury_side = models.CharField(max_length=20, blank=True)
    injury_date = models.DateField(null=True, blank=True)
    manual_sanction_active = models.BooleanField(default=False)
    manual_sanction_reason = models.CharField(max_length=180, blank=True)
    manual_sanction_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('team', 'name')

    def __str__(self):
        return f'{self.name} ({self.team.name})'


class PlayerInjuryRecord(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='injury_records')
    injury = models.CharField(max_length=180)
    injury_type = models.CharField(max_length=80, blank=True)
    injury_zone = models.CharField(max_length=80, blank=True)
    injury_side = models.CharField(max_length=20, blank=True)
    injury_date = models.DateField()
    return_date = models.DateField(null=True, blank=True, help_text='Fecha de alta médica/deportiva')
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-injury_date', '-id']

    def __str__(self):
        return f'{self.player.name} · {self.injury} ({self.injury_date:%d/%m/%Y})'


class PlayerPhysicalMetric(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='physical_metrics')
    recorded_on = models.DateField(default=timezone.localdate)
    workload = models.CharField(max_length=120, blank=True, help_text='Ej. Fuerza + resistencia')
    rpe = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Percepción del esfuerzo 1-10')
    wellness = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Bienestar 1-10')
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_on', '-id']

    def __str__(self):
        return f'{self.player.name} · métrica {self.recorded_on:%d/%m/%Y}'


class PlayerCommunication(models.Model):
    CATEGORY_CONVOCATION = 'convocatoria'
    CATEGORY_INTERNAL = 'interna'
    CATEGORY_MEDICAL = 'medica'
    CATEGORY_CHOICES = [
        (CATEGORY_CONVOCATION, 'Convocatoria'),
        (CATEGORY_INTERNAL, 'Comunicación interna'),
        (CATEGORY_MEDICAL, 'Parte médico'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='communications')
    match = models.ForeignKey('Match', on_delete=models.SET_NULL, null=True, blank=True, related_name='player_communications')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_INTERNAL)
    message = models.TextField()
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text='Fecha/hora objetivo de la comunicación')
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.player.name} · {self.category}'


class PlayerFine(models.Model):
    REASON_ABSENCE = 'absence'
    REASON_LATE = 'late'
    REASON_INDISCIPLINE = 'indiscipline'
    REASON_EXPULSION = 'expulsion'
    REASON_CHOICES = [
        (REASON_ABSENCE, 'Ausencia'),
        (REASON_LATE, 'Retraso'),
        (REASON_INDISCIPLINE, 'Indisciplina'),
        (REASON_EXPULSION, 'Expulsión'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='fines')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    amount = models.PositiveSmallIntegerField(help_text='Importe en euros, múltiplo de 5')
    note = models.CharField(max_length=220, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.player.name} · {self.get_reason_display()} · {self.amount}€'


class ConvocationRecord(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='convocations')
    match = models.ForeignKey(
        'Match',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='convocations',
    )
    round = models.CharField(max_length=60, blank=True)
    match_date = models.DateField(null=True, blank=True)
    match_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    opponent_name = models.CharField(max_length=150, blank=True)
    lineup_data = models.JSONField(default=dict, blank=True)
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
    period = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Parte del partido o periodo (1, 2, etc.)')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    minute = models.PositiveSmallIntegerField(null=True, blank=True)
    period = models.PositiveSmallIntegerField(null=True, blank=True)
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


class TrainingMicrocycle(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Borrador'),
        (STATUS_APPROVED, 'Aprobado'),
        (STATUS_CLOSED, 'Cerrado'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='microcycles')
    reference_match = models.ForeignKey(
        Match,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='microcycles',
    )
    title = models.CharField(max_length=140, default='Microciclo semanal')
    objective = models.CharField(max_length=200, blank=True)
    week_start = models.DateField()
    week_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'week_start')
        ordering = ['-week_start', '-id']

    def __str__(self):
        return f'{self.team.name} · {self.week_start:%d/%m} - {self.week_end:%d/%m}'


class TrainingSession(models.Model):
    INTENSITY_LOW = 'low'
    INTENSITY_MEDIUM = 'medium'
    INTENSITY_HIGH = 'high'
    INTENSITY_RECOVERY = 'recovery'
    INTENSITY_MATCHDAY = 'matchday'
    INTENSITY_CHOICES = [
        (INTENSITY_LOW, 'Baja'),
        (INTENSITY_MEDIUM, 'Media'),
        (INTENSITY_HIGH, 'Alta'),
        (INTENSITY_RECOVERY, 'Recuperación'),
        (INTENSITY_MATCHDAY, 'Pre-partido'),
    ]

    STATUS_PLANNED = 'planned'
    STATUS_DONE = 'done'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_PLANNED, 'Planificada'),
        (STATUS_DONE, 'Realizada'),
        (STATUS_CANCELED, 'Cancelada'),
    ]

    microcycle = models.ForeignKey(TrainingMicrocycle, on_delete=models.CASCADE, related_name='sessions')
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=90)
    intensity = models.CharField(max_length=20, choices=INTENSITY_CHOICES, default=INTENSITY_MEDIUM)
    focus = models.CharField(max_length=140)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session_date', 'start_time', 'order', 'id']

    def __str__(self):
        return f'{self.session_date:%d/%m} · {self.focus}'


class SessionTask(models.Model):
    BLOCK_ACTIVATION = 'activation'
    BLOCK_MAIN_1 = 'main_1'
    BLOCK_MAIN_2 = 'main_2'
    BLOCK_SET_PIECES = 'set_pieces'
    BLOCK_CONDITIONING = 'conditioning'
    BLOCK_RECOVERY = 'recovery'
    BLOCK_VIDEO = 'video'
    BLOCK_CHOICES = [
        (BLOCK_ACTIVATION, 'Activación'),
        (BLOCK_MAIN_1, 'Principal 1'),
        (BLOCK_MAIN_2, 'Principal 2'),
        (BLOCK_SET_PIECES, 'ABP'),
        (BLOCK_CONDITIONING, 'Condicionante'),
        (BLOCK_RECOVERY, 'Vuelta calma'),
        (BLOCK_VIDEO, 'Vídeo'),
    ]

    STATUS_PLANNED = 'planned'
    STATUS_DONE = 'done'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PLANNED, 'Planificada'),
        (STATUS_DONE, 'Hecha'),
        (STATUS_SKIPPED, 'No realizada'),
    ]

    session = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=160)
    block = models.CharField(max_length=30, choices=BLOCK_CHOICES, default=BLOCK_MAIN_1)
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    objective = models.CharField(max_length=180, blank=True)
    coaching_points = models.TextField(blank=True, help_text='Consignas clave para ejecutar la tarea')
    confrontation_rules = models.TextField(blank=True, help_text='Reglas de confrontación y puntuación')
    tactical_layout = models.JSONField(default=dict, blank=True)
    task_pdf = models.FileField(upload_to='session-tasks-pdf/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    order = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.session} · {self.title}'


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


class HomeCarouselImage(models.Model):
    title = models.CharField(max_length=120, blank=True)
    image = models.ImageField(upload_to='home-carousel/')
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at', '-id']
        verbose_name = 'Imagen carrusel home'
        verbose_name_plural = 'Imágenes carrusel home'

    def __str__(self):
        return self.title or f'Imagen {self.id}'


class RivalVideo(models.Model):
    SOURCE_UNIVERSO = 'universo'
    SOURCE_RFAF = 'rfaf'
    SOURCE_PREFERENTE = 'preferente'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_UNIVERSO, 'Universo RFAF'),
        (SOURCE_RFAF, 'RFAF'),
        (SOURCE_PREFERENTE, 'La Preferente'),
        (SOURCE_MANUAL, 'Manual'),
    ]

    rival_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='rival_videos')
    title = models.CharField(max_length=180)
    video = models.FileField(upload_to='rival-videos/')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        team_label = self.rival_team.name if self.rival_team else 'Rival'
        return f'{team_label} · {self.title}'


class RivalAnalysisReport(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_READY = 'ready'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Borrador'),
        (STATUS_READY, 'Listo para partido'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='rival_analysis_reports')
    rival_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analysis_reports_as_rival',
    )
    rival_name = models.CharField(max_length=180)
    report_title = models.CharField(max_length=180, blank=True)
    match_round = models.CharField(max_length=80, blank=True)
    match_date = models.CharField(max_length=60, blank=True)
    match_location = models.CharField(max_length=180, blank=True)
    tactical_system = models.CharField(max_length=80, blank=True, help_text='Ej: 1-4-2-3-1')
    attacking_patterns = models.TextField(blank=True, help_text='Cómo progresan, zonas, mecanismos')
    defensive_patterns = models.TextField(blank=True, help_text='Altura bloque, presión, ajustes')
    transitions = models.TextField(blank=True, help_text='Comportamiento en transición OF/DEF')
    set_pieces_for = models.TextField(blank=True, help_text='ABP ofensivas del rival')
    set_pieces_against = models.TextField(blank=True, help_text='ABP defensivas del rival')
    key_players = models.TextField(blank=True, help_text='Jugadores determinantes y perfil')
    weaknesses = models.TextField(blank=True, help_text='Puntos atacables')
    opportunities = models.TextField(blank=True, help_text='Dónde hacer daño')
    match_plan = models.TextField(blank=True, help_text='Plan de partido propuesto')
    individual_tasks = models.TextField(blank=True, help_text='Tareas por línea/jugador')
    alert_notes = models.TextField(blank=True, help_text='Alertas: sanciones, lesiones, riesgos')
    confidence_level = models.PositiveSmallIntegerField(default=3, help_text='1-5')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f'{self.rival_name} · {self.report_title or "Informe"}'


class UserInvitation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitations')
    token = models.CharField(max_length=120, unique=True, db_index=True)
    email = models.EmailField(blank=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe(32)

    def is_expired(self, now=None):
        reference = now or timezone.now()
        return bool(self.expires_at and self.expires_at <= reference)

    def can_be_used(self, now=None):
        return bool(self.is_active and not self.accepted_at and not self.is_expired(now=now))

    def __str__(self):
        return f'Invitación {self.user.username} · {self.created_at:%Y-%m-%d %H:%M}'


class AppUserRole(models.Model):
    ROLE_PLAYER = 'jugador'
    ROLE_GUEST = 'invitado'
    ROLE_COACH = 'entrenador'
    ROLE_FITNESS = 'preparador_fisico'
    ROLE_GOALKEEPER = 'preparador_portero'
    ROLE_ANALYST = 'analista'
    ROLE_ADMIN = 'administrador'
    ROLE_CHOICES = [
        (ROLE_PLAYER, 'Jugador'),
        (ROLE_GUEST, 'Invitado'),
        (ROLE_COACH, 'Entrenador'),
        (ROLE_FITNESS, 'Preparador físico'),
        (ROLE_GOALKEEPER, 'Preparador portero'),
        (ROLE_ANALYST, 'Analista'),
        (ROLE_ADMIN, 'Administrador'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='app_role')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_PLAYER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']
        verbose_name = 'Rol de usuario'
        verbose_name_plural = 'Roles de usuario'

    def __str__(self):
        return f'{self.user.username} · {self.get_role_display()}'


class TaskBlueprint(models.Model):
    CATEGORY_BUILD = 'build_up'
    CATEGORY_PRESS = 'pressing'
    CATEGORY_TRANSITION = 'transition'
    CATEGORY_FINISH = 'finishing'
    CATEGORY_ABP = 'abp'
    CATEGORY_GK = 'goalkeeper'
    CATEGORY_PHYSICAL = 'physical'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_BUILD, 'Inicio y progresión'),
        (CATEGORY_PRESS, 'Presión y recuperación'),
        (CATEGORY_TRANSITION, 'Transiciones'),
        (CATEGORY_FINISH, 'Finalización'),
        (CATEGORY_ABP, 'ABP'),
        (CATEGORY_GK, 'Porteros'),
        (CATEGORY_PHYSICAL, 'Condicionante físico'),
        (CATEGORY_OTHER, 'Otros'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='task_blueprints')
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    description = models.CharField(max_length=220, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name', '-updated_at']
        unique_together = ('team', 'name')

    def __str__(self):
        return f'{self.team.name} · {self.name}'
