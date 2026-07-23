from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import secrets
import hashlib
import uuid

from .normalization import normalize_player_record, normalize_scouting_target_record


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
    external_id = models.CharField(max_length=80, blank=True, help_text='ID externo del grupo (Universo RFAF / LaPreferente)')

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
    crest_url = models.URLField(blank=True, help_text='URL sincronizada del escudo del equipo')
    crest_image = models.ImageField(upload_to='team-crests/', null=True, blank=True)
    home_stadium = models.CharField(max_length=200, blank=True, help_text='Campo/estadio habitual del equipo')
    home_stadium_address = models.CharField(max_length=260, blank=True, help_text='Dirección postal del campo/estadio')
    home_stadium_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    home_stadium_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    home_stadium_maps_url = models.URLField(blank=True, help_text='Enlace directo a Google Maps u otro mapa')
    cover_image = models.ImageField(upload_to='team-covers/', null=True, blank=True)
    cover_updated_at = models.DateTimeField(null=True, blank=True)
    is_primary = models.BooleanField(default=False, help_text='Marcar si es el equipo de Benagalbón')
    category = models.CharField(
        max_length=24,
        blank=True,
        help_text='Categoría del club (ej. Prebenjamín, Cadete, Senior). Solo se usa para equipos propios.',
    )
    GAME_FORMAT_F7 = 'f7'
    GAME_FORMAT_F11 = 'f11'
    GAME_FORMAT_CHOICES = [
        (GAME_FORMAT_F7, 'Fútbol 7'),
        (GAME_FORMAT_F11, 'Fútbol 11'),
    ]
    game_format = models.CharField(
        max_length=8,
        choices=GAME_FORMAT_CHOICES,
        default=GAME_FORMAT_F11,
        help_text='Formato de juego (afecta a convocatorias, 11/7 inicial y registro en vivo).',
    )

    @property
    def display_name(self):
        return (self.short_name or self.name or '').strip()

    def __str__(self):
        return self.name


class Workspace(models.Model):
    KIND_CLUB = 'club'
    KIND_TASK_STUDIO = 'task_studio'
    KIND_CHOICES = [
        (KIND_CLUB, 'Club'),
        (KIND_TASK_STUDIO, 'Task Studio'),
    ]

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES, default=KIND_CLUB)
    primary_team = models.OneToOneField(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workspace',
    )
    owner_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_workspaces',
    )
    enabled_modules = models.JSONField(default=dict, blank=True)
    trial_expires_at = models.DateTimeField(null=True, blank=True)
    subscription_status = models.CharField(
        max_length=24,
        default='trial',
        help_text='trial|active|past_due|canceled|expired',
    )
    plan_key = models.CharField(max_length=40, blank=True, help_text='Identificador interno del plan (ej: basic, pro).')
    # Stripe billing (opcional). Mantener campos vacíos si Stripe no está configurado.
    stripe_customer_id = models.CharField(max_length=80, blank=True)
    stripe_subscription_id = models.CharField(max_length=80, blank=True)
    stripe_price_id = models.CharField(max_length=80, blank=True)
    subscription_current_period_end = models.DateTimeField(null=True, blank=True)
    subscription_cancel_at_period_end = models.BooleanField(default=False)
    subscription_canceled_at = models.DateTimeField(null=True, blank=True)
    # Entitlements modulares (Core + add-ons). Solo se aplica si STRIPE_MODULAR_BILLING=1.
    paid_modules = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active_season = models.ForeignKey(
        'WorkspaceSeason',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_in_workspaces',
    )

    class Meta:
        ordering = ['kind', 'name', 'id']
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name


class WorkspaceSeason(models.Model):
    """
    Temporada interna del club (por workspace), independiente de la temporada de competición.

    Objetivo:
    - Mantener histórico por temporada.
    - Al iniciar nueva temporada, heredar plantilla como "pendiente de confirmar".
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='club_seasons')
    label = models.CharField(max_length=32, help_text='Ej. 2025/2026')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-start_date', '-id']
        unique_together = ('workspace', 'label')
        verbose_name = 'Temporada (club)'
        verbose_name_plural = 'Temporadas (club)'

    def __str__(self):
        suffix = ' (activa)' if self.is_active else ''
        return f'{self.workspace.name} · {self.label}{suffix}'


class WorkspaceSeasonTeam(models.Model):
    """
    Participación de un equipo/categoría en una temporada interna del club.

    `Team` permanece como entidad estable. Esta tabla guarda si ese equipo existió
    en una temporada concreta y si sigue operativo en ella, sin perder histórico.
    """

    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_NOT_CONTINUING = 'not_continuing'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Activo en temporada'),
        (STATUS_ARCHIVED, 'Archivado'),
        (STATUS_NOT_CONTINUING, 'No continúa'),
    ]

    season = models.ForeignKey(WorkspaceSeason, on_delete=models.CASCADE, related_name='season_teams')
    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='season_memberships')
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'team__name', 'id']
        unique_together = ('season', 'team')
        indexes = [
            models.Index(fields=['season', 'is_active'], name='wst_season_active_idx'),
            models.Index(fields=['team', '-created_at'], name='wst_team_created_idx'),
        ]
        verbose_name = 'Equipo de temporada (club)'
        verbose_name_plural = 'Equipos de temporada (club)'

    def __str__(self):
        return f'{self.season.label} · {self.team.display_name}'


class WorkspaceSeasonPlayer(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_INACTIVE = 'inactive'
    STATUS_LEFT = 'left'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_CONFIRMED, 'Confirmado'),
        (STATUS_INACTIVE, 'Inactivo'),
        (STATUS_LEFT, 'No continúa'),
    ]

    season = models.ForeignKey(WorkspaceSeason, on_delete=models.CASCADE, related_name='season_players')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='season_memberships')
    team = models.ForeignKey(
        'Team',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='season_player_memberships',
        help_text='Categoría/equipo del club en la que participa este jugador durante la temporada.',
    )
    is_confirmed = models.BooleanField(default=False, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='season_player_confirmations',
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    left_at = models.DateTimeField(null=True, blank=True)
    status_notes = models.CharField(max_length=220, blank=True)
    # Cuestionario básico de inicio de temporada (por jugador).
    # Se guarda como JSON para poder añadir campos sin migraciones adicionales.
    questionnaire_v = models.PositiveSmallIntegerField(default=1)
    questionnaire = models.JSONField(default=dict, blank=True)
    questionnaire_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_confirmed', 'status', 'player__name', 'id']
        unique_together = ('season', 'player')
        indexes = [
            models.Index(fields=['season', 'status'], name='wsp_season_status_idx'),
            models.Index(fields=['season', 'team', 'status'], name='wsp_season_team_status_idx'),
            models.Index(fields=['player', '-created_at'], name='wsp_player_created_idx'),
        ]
        verbose_name = 'Jugador de temporada (club)'
        verbose_name_plural = 'Jugadores de temporada (club)'

    def __str__(self):
        return f'{self.season.label} · {self.player.name}'


class WorkspaceSeasonPhase(models.Model):
    """
    Fases internas de una temporada de club (captación, pretemporada, liga, etc.).

    Se usan principalmente para planificación (agenda/sesiones) y UX del producto.
    """

    KEY_RECRUITMENT = 'recruitment'
    KEY_PRESEASON = 'preseason'
    KEY_REGULAR = 'regular'
    KEY_PLAYOFFS = 'playoffs'
    KEY_OFFSEASON = 'offseason'
    KEY_CUSTOM = 'custom'

    KEY_CHOICES = (
        (KEY_RECRUITMENT, 'Captación'),
        (KEY_PRESEASON, 'Pretemporada'),
        (KEY_REGULAR, 'Temporada regular'),
        (KEY_PLAYOFFS, 'Playoff / eliminatorias'),
        (KEY_OFFSEASON, 'Fuera de temporada'),
        (KEY_CUSTOM, 'Personalizada'),
    )

    season = models.ForeignKey(WorkspaceSeason, on_delete=models.CASCADE, related_name='phases')
    key = models.CharField(max_length=24, choices=KEY_CHOICES, default=KEY_CUSTOM, db_index=True)
    label = models.CharField(max_length=80, help_text='Nombre visible. Ej: Captación, Pretemporada…')
    start_date = models.DateField()
    end_date = models.DateField()
    sort_order = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['season_id', 'sort_order', 'start_date', 'id']
        verbose_name = 'Fase de temporada (club)'
        verbose_name_plural = 'Fases de temporada (club)'

    def __str__(self):
        return f'{self.season.label} · {self.label}'


def _infer_workspace_season_for_team_date(team_id, value):
    if not team_id or not value:
        return None
    if hasattr(value, 'date'):
        value = value.date()
    try:
        links = (
            WorkspaceTeam.objects
            .filter(team_id=int(team_id), workspace__kind=Workspace.KIND_CLUB)
            .select_related('workspace')
            .order_by('-is_default', 'id')
        )
        workspace_ids = [int(link.workspace_id) for link in links if getattr(link, 'workspace_id', None)]
    except Exception:
        workspace_ids = []
    if not workspace_ids:
        return None
    return (
        WorkspaceSeason.objects
        .filter(workspace_id__in=workspace_ids, start_date__lte=value)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=value))
        .order_by('-is_active', '-start_date', '-id')
        .first()
    )


class WorkspaceTeam(models.Model):
    """
    Vínculo entre un cliente (workspace club) y sus equipos/categorías.

    - Permite tener Senior, Prebenjamín, etc. dentro del mismo cliente.
    - El selector de equipo activo usa esta tabla para validar el cambio.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='teams')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='workspace_links')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', 'id']
        unique_together = ('workspace', 'team')
        verbose_name = 'Equipo del workspace'
        verbose_name_plural = 'Equipos del workspace'

    def __str__(self):
        return f'{self.workspace.name} · {self.team.display_name}'


class WorkspacePlayer(models.Model):
    """
    Base estable de jugadores de un club/workspace.

    `Player` conserva la ficha deportiva existente. Esta tabla limita qué jugadores
    pertenecen a cada club para no mezclar plantillas entre clientes.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='players')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='workspace_links')
    current_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workspace_player_current_links',
        help_text='Categoría/equipo actual sugerido dentro del club.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'player__name', 'id']
        unique_together = ('workspace', 'player')
        indexes = [
            models.Index(fields=['workspace', 'is_active'], name='wp_workspace_active_idx'),
            models.Index(fields=['current_team', 'is_active'], name='wp_team_active_idx'),
        ]
        verbose_name = 'Jugador del workspace'
        verbose_name_plural = 'Jugadores del workspace'

    def __str__(self):
        return f'{self.workspace.name} · {self.player.name}'


class StripeEventLog(models.Model):
    """
    Registro idempotente de eventos Stripe procesados.

    Evita procesar dos veces el mismo webhook cuando Stripe reintenta.
    """

    event_id = models.CharField(max_length=120, unique=True, db_index=True)
    event_type = models.CharField(max_length=120, blank=True)
    workspace = models.ForeignKey(Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name='stripe_events')
    ok = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.event_type} · {self.event_id}'


class WorkspaceTeamAccess(models.Model):
    """
    Acceso por categoría/equipo dentro de un cliente (workspace club).

    Objetivo:
    - Un entrenador del Prebenjamín sólo ve datos/tareas/plantilla del Prebenjamín.
    - Senior idem.
    - Admin/propietario del cliente puede ver todas las categorías.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='team_accesses')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='workspace_team_accesses')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_team_accesses')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['workspace__name', 'user__username', '-is_default', 'id']
        unique_together = ('workspace', 'team', 'user')
        verbose_name = 'Acceso por categoría'
        verbose_name_plural = 'Accesos por categorías'

    def __str__(self):
        return f'{self.workspace.name} · {self.team.display_name} · {self.user.username}'


class WorkspacePreference(models.Model):
    """
    Preferencias UI compartibles a nivel de club (workspace).

    Ejemplos:
    - Visibilidad de KPIs por pantalla/rol.
    - Configuración de keypad PRO para registro de acciones.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='preferences')
    key = models.CharField(max_length=80, db_index=True)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key', '-updated_at', '-id']
        unique_together = ('workspace', 'key')
        verbose_name = 'Preferencia del workspace'
        verbose_name_plural = 'Preferencias del workspace'

    def __str__(self):
        return f'{self.workspace_id}:{self.key}'


class WorkspaceCompetitionContext(models.Model):
    PROVIDER_MANUAL = 'manual'
    PROVIDER_RFAF = 'rfaf'
    PROVIDER_UNIVERSO = 'universo_rfaf'
    PROVIDER_PREFERENTE = 'lapreferente'
    PROVIDER_CHOICES = [
        (PROVIDER_MANUAL, 'Manual / base local'),
        (PROVIDER_RFAF, 'RFAF'),
        (PROVIDER_UNIVERSO, 'Universo RFAF'),
        (PROVIDER_PREFERENTE, 'La Preferente'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_READY = 'ready'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_READY, 'Sincronizado'),
        (STATUS_ERROR, 'Error'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='competition_contexts')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='competition_contexts')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='competition_contexts')
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, null=True, blank=True, related_name='competition_contexts')
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_MANUAL)
    external_competition_key = models.CharField(max_length=140, blank=True)
    external_group_key = models.CharField(max_length=140, blank=True)
    external_team_key = models.CharField(max_length=140, blank=True)
    external_team_name = models.CharField(max_length=160, blank=True)
    external_source_url = models.URLField(blank=True, help_text='URL pública (Universo/Preferente/etc.) para revalidar el contexto.')
    is_auto_sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    sync_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    sync_error = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['workspace__name']
        verbose_name = 'Contexto competitivo'
        verbose_name_plural = 'Contextos competitivos'
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'team'],
                condition=Q(team__isnull=False),
                name='uniq_workspace_team_competition_context',
            )
        ]

    def __str__(self):
        return f'{self.workspace.name} · {self.get_provider_display()}'


class WorkspaceCompetitionSnapshot(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='competition_snapshots')
    context = models.OneToOneField(
        WorkspaceCompetitionContext,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='snapshot',
    )
    standings_payload = models.JSONField(default=list, blank=True)
    next_match_payload = models.JSONField(default=dict, blank=True)
    schedule_payload = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Snapshot competitivo'
        verbose_name_plural = 'Snapshots competitivos'

    def __str__(self):
        return f'Snapshot · {self.workspace.name}'


class TeamRosterSnapshot(models.Model):
    PROVIDER_UNIVERSO = 'universo_rfaf'
    PROVIDER_PREFERENTE = 'lapreferente'
    PROVIDER_CHOICES = [
        (PROVIDER_UNIVERSO, 'Universo RFAF'),
        (PROVIDER_PREFERENTE, 'La Preferente'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='roster_snapshots')
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES, default=PROVIDER_UNIVERSO)
    roster_payload = models.JSONField(default=list, blank=True)
    source_url = models.URLField(blank=True)
    error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'provider')
        ordering = ['-updated_at']
        verbose_name = 'Snapshot plantilla (equipo)'
        verbose_name_plural = 'Snapshots plantilla (equipos)'

    def __str__(self):
        return f'Plantilla · {self.team.name} · {self.get_provider_display()}'


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    # Vínculo explícito con el usuario del jugador para evitar ambigüedades al resolver
    # la ficha en base a nombre/username (puede mezclar jugadores con nombres similares).
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_profile',
    )
    name = models.CharField(max_length=120)
    full_name = models.CharField(max_length=180, blank=True)
    nickname = models.CharField(max_length=80, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    origin_team = models.CharField(max_length=160, blank=True)
    current_club = models.CharField(max_length=160, blank=True)
    has_agent = models.BooleanField(default=False)
    agent_name = models.CharField(max_length=160, blank=True)
    agent_phone = models.CharField(max_length=40, blank=True)
    dominant_foot = models.CharField(max_length=16, blank=True)
    skin_tone = models.CharField(max_length=16, blank=True, help_text='Tono de piel para el avatar generado: light / medium / dark.')
    preferred_position = models.CharField(max_length=60, blank=True)
    previous_season_position = models.CharField(max_length=60, blank=True)
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
    # Control de caché de foto (para busting sin depender de caches por proceso).
    photo_updated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('team', 'name')

    def __str__(self):
        return f'{self.name} ({self.team.name})'

    def save(self, *args, **kwargs):
        changed_fields = normalize_player_record(self)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            merged = set(update_fields)
            merged.update(changed_fields)
            kwargs['update_fields'] = sorted(merged)
        super().save(*args, **kwargs)


class StaffMember(models.Model):
    """
    Miembro del cuerpo técnico por club (workspace) y opcionalmente por categoría/equipo.

    - workspace: club al que pertenece
    - team: si se deja vacío, se considera staff del club completo
    """

    workspace = models.ForeignKey('Workspace', on_delete=models.CASCADE, related_name='staff_members')
    team = models.ForeignKey('Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_profiles',
    )
    name = models.CharField(max_length=160)
    role_title = models.CharField(max_length=120, blank=True, help_text='Ej. Entrenador, Segundo, Fisio, Delegado')
    certification_level = models.CharField(max_length=160, blank=True, help_text='Ej. UEFA B, CAFYD, TAFAD…')
    dni = models.CharField(max_length=24, blank=True, help_text='Documento de identidad (opcional).')
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to='staff/photos/', null=True, blank=True)
    photo_updated_at = models.DateTimeField(null=True, blank=True)
    federation_license = models.FileField(upload_to='staff/licenses/', null=True, blank=True, help_text='PDF/JPG/PNG')
    federation_license_number = models.CharField(max_length=80, blank=True, help_text='Nº licencia federativa (opcional).')
    federation_license_expires_at = models.DateField(null=True, blank=True, help_text='Caducidad licencia federativa (opcional).')
    license_updated_at = models.DateTimeField(null=True, blank=True)
    certification_document = models.FileField(upload_to='staff/certifications/', null=True, blank=True, help_text='PDF/JPG/PNG de titulación (opcional).')
    certification_expires_at = models.DateField(null=True, blank=True, help_text='Caducidad titulación (opcional).')
    certification_updated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'role_title', 'name', '-updated_at', '-id']
        verbose_name = 'Miembro del staff'
        verbose_name_plural = 'Miembros del staff'

    def __str__(self):
        scope = self.workspace.name if self.workspace_id else 'Club'
        return f'{self.name} · {self.role_title or "Staff"} ({scope})'


class PlayerInjuryRecord(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='injury_records')
    catalog_entry = models.ForeignKey(
        'InjuryCatalogEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='records',
        help_text='Catálogo (opcional). Si se usa, permite métricas homogéneas.',
    )
    injury = models.CharField(max_length=180)
    injury_type = models.CharField(max_length=80, blank=True)
    injury_zone = models.CharField(max_length=80, blank=True)
    injury_side = models.CharField(max_length=20, blank=True)
    severity_grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Grado orientativo (1 leve · 2 moderada · 3 grave).',
    )
    injury_date = models.DateField()
    diagnosed_on = models.DateField(null=True, blank=True, help_text='Fecha de diagnóstico (opcional).')
    rehab_started_on = models.DateField(null=True, blank=True, help_text='Inicio de readaptación/rehab (opcional).')
    estimated_return_date = models.DateField(null=True, blank=True, help_text='Alta estimada (orientativa).')
    return_date = models.DateField(null=True, blank=True, help_text='Fecha de alta médica/deportiva')
    return_to_train_on = models.DateField(null=True, blank=True, help_text='Vuelta a entrenar (opcional).')
    return_to_play_on = models.DateField(null=True, blank=True, help_text='Vuelta a competir (opcional).')
    blocks_training = models.BooleanField(default=False, help_text='Marca si impide entrenar.')
    is_recovered = models.BooleanField(default=False, help_text='Marca si la lesión ya está recuperada.')
    training_status = models.CharField(
        max_length=20,
        blank=True,
        help_text='Estado funcional: disponible · carga modificada · rehab · baja.',
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-injury_date', '-id']

    def save(self, *args, **kwargs):
        if self.is_recovered:
            self.is_active = False
            if self.return_date is None:
                self.return_date = timezone.localdate()
        elif self.return_date:
            self.is_active = self.return_date > timezone.localdate()
        else:
            self.is_active = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.player.name} · {self.injury} ({self.injury_date:%d/%m/%Y})'


class InjuryMilestone(models.Model):
    record = models.ForeignKey(PlayerInjuryRecord, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=120)
    milestone_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'milestone_date', 'id']
        verbose_name = 'Hito de lesión'
        verbose_name_plural = 'Hitos de lesión'

    def __str__(self):
        return f'{self.record.player.name} · {self.title}'


class InjuryCatalogEntry(models.Model):
    """
    Catálogo unificado de lesiones (orientativo) para que el club mida bajas de forma homogénea.

    Importante: no sustituye criterio médico. Los rangos son aproximaciones para planificación.
    """

    CATEGORY_MUSCLE = 'muscle'
    CATEGORY_LIGAMENT = 'ligament'
    CATEGORY_TENDON = 'tendon'
    CATEGORY_BONE = 'bone'
    CATEGORY_CONCUSSION = 'concussion'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_MUSCLE, 'Muscular'),
        (CATEGORY_LIGAMENT, 'Ligamentosa'),
        (CATEGORY_TENDON, 'Tendinosa'),
        (CATEGORY_BONE, 'Ósea'),
        (CATEGORY_CONCUSSION, 'Conmoción'),
        (CATEGORY_OTHER, 'Otra'),
    ]

    REGION_ANKLE = 'ankle'
    REGION_KNEE = 'knee'
    REGION_HIP_GROIN = 'hip_groin'
    REGION_THIGH = 'thigh'
    REGION_CALF_ACHILLES = 'calf_achilles'
    REGION_FOOT_TOES = 'foot_toes'
    REGION_SHOULDER_CLAVICLE = 'shoulder_clavicle'
    REGION_HEAD = 'head'
    REGION_BACK = 'back'
    REGION_OTHER = 'other'
    REGION_CHOICES = [
        (REGION_ANKLE, 'Tobillo'),
        (REGION_KNEE, 'Rodilla'),
        (REGION_HIP_GROIN, 'Cadera / Aductores'),
        (REGION_THIGH, 'Muslo'),
        (REGION_CALF_ACHILLES, 'Gemelo / Aquiles'),
        (REGION_FOOT_TOES, 'Pie / Dedos'),
        (REGION_SHOULDER_CLAVICLE, 'Hombro / Clavícula'),
        (REGION_HEAD, 'Cabeza'),
        (REGION_BACK, 'Espalda'),
        (REGION_OTHER, 'Otra'),
    ]

    code = models.SlugField(max_length=64, unique=True, help_text='Identificador estable (p.ej. ankle-sprain).')
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    region = models.CharField(max_length=24, choices=REGION_CHOICES, default=REGION_OTHER)
    typical_min_days = models.PositiveSmallIntegerField(default=0, help_text='Mínimo orientativo (días).')
    typical_max_days = models.PositiveSmallIntegerField(default=0, help_text='Máximo orientativo (días).')
    notes = models.TextField(blank=True)
    reference_url = models.URLField(blank=True, help_text='Fuente pública (opcional).')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['region', 'category', 'name', 'id']
        verbose_name = 'Lesión (catálogo)'
        verbose_name_plural = 'Lesiones (catálogo)'

    def __str__(self):
        return self.name


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


class ScoutingTarget(models.Model):
    STATUS_TARGET = 'target'
    STATUS_WATCHLIST = 'watchlist'
    STATUS_ACTIVE = 'active'
    STATUS_REVIEW = 'review'
    STATUS_DISCARDED = 'discarded'
    STATUS_SIGNED = 'signed'
    STATUS_CHOICES = [
        (STATUS_TARGET, 'Objetivo'),
        (STATUS_WATCHLIST, 'En seguimiento'),
        (STATUS_ACTIVE, 'Seguimiento activo'),
        (STATUS_REVIEW, 'Revisar'),
        (STATUS_DISCARDED, 'Descartado'),
        (STATUS_SIGNED, 'Firmado'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Baja'),
        (PRIORITY_MEDIUM, 'Media'),
        (PRIORITY_HIGH, 'Alta'),
        (PRIORITY_URGENT, 'Urgente'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='scouting_targets')
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='scouting_targets')
    subject_name = models.CharField(max_length=160, help_text='Nombre del jugador ojeado, aunque no exista como ficha local.')
    subject_team_name = models.CharField(max_length=160, blank=True, help_text='Club actual o referencia del jugador.')
    position = models.CharField(max_length=60, blank=True)
    dominant_foot = models.CharField(max_length=16, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_WATCHLIST, db_index=True)
    available_for_coach_tools = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Si el ojeado puede aparecer en entrenos y en la pizarra del entrenador.',
    )
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_scouting_targets',
    )
    next_review_on = models.DateField(null=True, blank=True)
    budget_note = models.CharField(max_length=160, blank=True)
    summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_scouting_targets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'status', 'subject_name', '-updated_at', '-id']
        unique_together = ('workspace', 'player', 'subject_name')
        indexes = [
            models.Index(fields=['workspace', 'status', 'priority'], name='scout_ws_status_prio_idx'),
            models.Index(fields=['workspace', 'next_review_on'], name='scout_ws_review_idx'),
        ]
        verbose_name = 'Jugador ojeado'
        verbose_name_plural = 'Jugadores ojeados'

    @property
    def display_name(self):
        return (self.subject_name or getattr(self.player, 'name', '') or '').strip()

    def __str__(self):
        return f'{self.display_name} · {self.workspace.name}'

    def save(self, *args, **kwargs):
        changed_fields = normalize_scouting_target_record(self)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            merged = set(update_fields)
            merged.update(changed_fields)
            kwargs['update_fields'] = sorted(merged)
        super().save(*args, **kwargs)


class ScoutingReport(models.Model):
    RECOMMENDATION_SIGN = 'sign'
    RECOMMENDATION_FOLLOW = 'follow'
    RECOMMENDATION_DISCARD = 'discard'
    RECOMMENDATION_WAIT = 'wait'
    RECOMMENDATION_CHOICES = [
        (RECOMMENDATION_SIGN, 'Fichar'),
        (RECOMMENDATION_FOLLOW, 'Seguir'),
        (RECOMMENDATION_DISCARD, 'Descartar'),
        (RECOMMENDATION_WAIT, 'Esperar'),
    ]

    target = models.ForeignKey(ScoutingTarget, on_delete=models.CASCADE, related_name='reports')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scouting_reports')
    observed_on = models.DateField(default=timezone.localdate)
    opposition = models.CharField(max_length=160, blank=True)
    competition = models.CharField(max_length=160, blank=True)
    technical_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    tactical_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    physical_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    mental_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    potential_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    fit_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    recommendation = models.CharField(max_length=16, choices=RECOMMENDATION_CHOICES, default=RECOMMENDATION_WAIT)
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-observed_on', '-created_at', '-id']
        indexes = [
            models.Index(fields=['target', '-observed_on'], name='scout_report_target_idx'),
            models.Index(fields=['target', 'recommendation'], name='scout_report_reco_idx'),
        ]
        verbose_name = 'Informe de scouting'
        verbose_name_plural = 'Informes de scouting'

    def __str__(self):
        return f'{self.target.display_name} · {self.observed_on:%d/%m/%Y}'


class ScoutingFollowUp(models.Model):
    target = models.ForeignKey(ScoutingTarget, on_delete=models.CASCADE, related_name='followups')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scouting_followups')
    title = models.CharField(max_length=140)
    due_on = models.DateField(null=True, blank=True)
    completed_on = models.DateField(null=True, blank=True)
    is_done = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['is_done', 'due_on', '-created_at', '-id']
        indexes = [
            models.Index(fields=['target', 'is_done', 'due_on'], name='scout_followup_target_idx'),
        ]
        verbose_name = 'Seguimiento de scouting'
        verbose_name_plural = 'Seguimientos de scouting'

    def __str__(self):
        return f'{self.target.display_name} · {self.title}'


class ScoutingTargetSeasonStat(models.Model):
    """Histórico por temporada de un jugador OJEADO: partidos/goles/tarjetas
    que el ojeador anota a mano (el jugador de plantilla usa PlayerStatistic)."""
    target = models.ForeignKey(ScoutingTarget, on_delete=models.CASCADE, related_name='season_stats')
    season = models.CharField(max_length=40, blank=True, help_text='Temporada, ej. 2025/2026.')
    team = models.CharField(max_length=160, blank=True, help_text='Equipo/club en esa temporada.')
    division = models.CharField(max_length=120, blank=True, help_text='División o categoría.')
    matches_starter = models.PositiveSmallIntegerField(default=0, help_text='Partidos como titular.')
    matches_completed = models.PositiveSmallIntegerField(default=0, help_text='Partidos completados.')
    goals = models.PositiveSmallIntegerField(default=0)
    assists = models.PositiveSmallIntegerField(default=0)
    yellow_cards = models.PositiveSmallIntegerField(default=0)
    red_cards = models.PositiveSmallIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='scouting_season_stats')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-season', '-created_at', '-id']
        indexes = [
            models.Index(fields=['target', 'season'], name='scout_seasonstat_target_idx'),
        ]
        verbose_name = 'Temporada de ojeo'
        verbose_name_plural = 'Temporadas de ojeo'

    def __str__(self):
        return f'{self.target.display_name} · {self.season or "temporada"}'


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
    captain = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='captain_convocations',
    )
    goalkeeper = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goalkeeper_convocations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['team', 'match'], name='conv_team_match_idx'),
            models.Index(fields=['team', 'is_current', 'created_at'], name='conv_team_curr_idx'),
        ]

    def mark_replaced(self):
        if self.is_current:
            self.is_current = False
            self.save(update_fields=['is_current'])


class RivalConvocationRecord(models.Model):
    """
    Convocatoria/Alineación del rival asociada a un partido concreto.

    - Se alimenta desde TeamRosterSnapshot (Universo/Preferente) y se guarda en JSON para poder
      generar el acta aunque la fuente externa no esté disponible.
    - No enlaza a Player (nuestros jugadores) porque son rivales externos.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='rival_convocations')
    match = models.ForeignKey(
        'Match',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rival_convocations',
    )
    rival_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='as_rival_convocations',
    )
    provider = models.CharField(
        max_length=32,
        choices=TeamRosterSnapshot.PROVIDER_CHOICES,
        default=TeamRosterSnapshot.PROVIDER_UNIVERSO,
    )
    # Lista de jugadores convocados (dicts con {code,name,number,position}).
    convocation_data = models.JSONField(default=list, blank=True)
    # Alineación (dict con starters/bench, mismos dicts que convocation_data).
    lineup_data = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'match')
        ordering = ['-updated_at', '-id']
        verbose_name = 'Convocatoria rival'
        verbose_name_plural = 'Convocatorias rival'

    def __str__(self):
        base = self.rival_team.display_name if self.rival_team else 'Rival'
        return f'{base} · {self.match_id or "sin partido"}'


class Match(models.Model):
    CONTEXT_LEAGUE = 'league'
    CONTEXT_TOURNAMENT = 'tournament'
    CONTEXT_FRIENDLY = 'friendly'
    CONTEXT_CHOICES = [
        (CONTEXT_LEAGUE, 'Liga'),
        (CONTEXT_TOURNAMENT, 'Torneo'),
        (CONTEXT_FRIENDLY, 'Amistoso'),
    ]

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='matches')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='matches',
        help_text='Temporada interna del club para histórico y filtrado multitemporada.',
    )
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    round = models.CharField(max_length=50, blank=True, help_text='Jornada / ronda')
    context = models.CharField(
        max_length=16,
        choices=CONTEXT_CHOICES,
        default=CONTEXT_LEAGUE,
        help_text='Determina si el partido cuenta para la Liga (clasificación/próximo rival) o es Torneo/Amistoso.',
    )
    tournament_name = models.CharField(max_length=120, blank=True, help_text='Nombre del torneo (solo si context=Torneo).')
    tournament_stage = models.CharField(
        max_length=120,
        blank=True,
        help_text='Fase/ronda del torneo (grupo, cuartos, semifinal, final...).',
    )
    date = models.DateField(null=True, blank=True)
    kickoff_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    home_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='away_matches')
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    result = models.CharField(max_length=30, blank=True)
    staff_captain = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_captain_matches',
        help_text='Capitán destacado por el staff al cerrar el registro de acciones.',
    )
    staff_mvp = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_mvp_matches',
        help_text='Mejor jugador elegido por el staff al cerrar el registro de acciones.',
    )
    notes = models.TextField(blank=True)
    source = models.URLField(blank=True)

    class Meta:
        ordering = ['-date', 'round']
        indexes = [
            models.Index(fields=['home_team', 'date'], name='match_home_date_idx'),
            models.Index(fields=['away_team', 'date'], name='match_away_date_idx'),
            models.Index(fields=['season', 'date'], name='match_season_date_idx'),
            models.Index(fields=['club_season', 'date'], name='match_club_season_date_idx'),
        ]

    def __str__(self):
        if self.home_team and self.away_team:
            return f'{self.home_team} vs {self.away_team} - {self.round or self.date}'
        return f'Match {self.id}'

    def save(self, *args, **kwargs):
        if not self.club_season_id:
            team_id = getattr(self, 'home_team_id', None) or getattr(self, 'away_team_id', None)
            inferred = _infer_workspace_season_for_team_date(team_id, self.date)
            if inferred:
                self.club_season = inferred
        super().save(*args, **kwargs)


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
        indexes = [
            models.Index(fields=['context', 'match'], name='pstat_ctx_match_idx'),
            models.Index(fields=['player', 'match', 'context'], name='pstat_p_m_ctx_idx'),
        ]

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
        indexes = [
            models.Index(fields=['match', 'player'], name='me_match_player_idx'),
            models.Index(fields=['match', 'system', 'source_file', 'created_at'], name='me_m_sys_src_ca_idx'),
        ]

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
    TYPE_STANDARD = 'standard'
    TYPE_DOUBLE_MATCH = 'double_match'
    TYPE_LOAD = 'load'
    TYPE_TAPER = 'taper'
    TYPE_REGEN = 'regen'
    TYPE_PRESEASON = 'preseason'
    TYPE_CHOICES = [
        (TYPE_STANDARD, 'Competición'),
        (TYPE_DOUBLE_MATCH, 'Doble partido'),
        (TYPE_LOAD, 'Carga'),
        (TYPE_TAPER, 'Afinar'),
        (TYPE_REGEN, 'Regenerativo'),
        (TYPE_PRESEASON, 'Pretemporada'),
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
    cycle_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default=TYPE_STANDARD)
    game_model_focus = models.CharField(max_length=180, blank=True, default='')
    game_moment = models.CharField(max_length=40, blank=True, default='')
    principle = models.CharField(max_length=120, blank=True, default='')
    subprinciple = models.CharField(max_length=160, blank=True, default='')
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
    DAY_MD_PLUS_1 = 'md_plus_1'
    DAY_MD_PLUS_2 = 'md_plus_2'
    DAY_MD_MINUS_4 = 'md_minus_4'
    DAY_MD_MINUS_3 = 'md_minus_3'
    DAY_MD_MINUS_2 = 'md_minus_2'
    DAY_MD_MINUS_1 = 'md_minus_1'
    DAY_MD = 'md'
    DAY_CUSTOM = 'custom'
    DAY_CHOICES = [
        (DAY_MD_PLUS_1, 'MD+1 Recuperación'),
        (DAY_MD_PLUS_2, 'MD+2 Descanso / compensatorio'),
        (DAY_MD_MINUS_4, 'MD-4 Tensión'),
        (DAY_MD_MINUS_3, 'MD-3 Duración'),
        (DAY_MD_MINUS_2, 'MD-2 Velocidad'),
        (DAY_MD_MINUS_1, 'MD-1 Activación'),
        (DAY_MD, 'MD Partido'),
        (DAY_CUSTOM, 'Personalizado'),
    ]
    DOMINANT_LOAD_RECOVERY = 'recovery'
    DOMINANT_LOAD_TENSION = 'tension'
    DOMINANT_LOAD_DURATION = 'duration'
    DOMINANT_LOAD_SPEED = 'speed'
    DOMINANT_LOAD_ACTIVATION = 'activation'
    DOMINANT_LOAD_MIXED = 'mixed'
    DOMINANT_LOAD_CHOICES = [
        (DOMINANT_LOAD_RECOVERY, 'Recuperación'),
        (DOMINANT_LOAD_TENSION, 'Tensión'),
        (DOMINANT_LOAD_DURATION, 'Duración'),
        (DOMINANT_LOAD_SPEED, 'Velocidad'),
        (DOMINANT_LOAD_ACTIVATION, 'Activación'),
        (DOMINANT_LOAD_MIXED, 'Mixta'),
    ]

    microcycle = models.ForeignKey(TrainingMicrocycle, on_delete=models.CASCADE, related_name='sessions')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_sessions',
        help_text='Temporada interna del club para histórico y planificación por año.',
    )
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=90)
    intensity = models.CharField(max_length=20, choices=INTENSITY_CHOICES, default=INTENSITY_MEDIUM)
    md_day = models.CharField(max_length=24, choices=DAY_CHOICES, blank=True, default='')
    dominant_load = models.CharField(max_length=24, choices=DOMINANT_LOAD_CHOICES, blank=True, default='')
    game_moment = models.CharField(max_length=40, blank=True, default='')
    principle = models.CharField(max_length=120, blank=True, default='')
    subprinciple = models.CharField(max_length=160, blank=True, default='')
    focus = models.CharField(max_length=140)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    WORKFLOW_DRAFT = 'draft'
    WORKFLOW_PROPOSED = 'proposed'
    WORKFLOW_APPROVED = 'approved'
    WORKFLOW_LOCKED = 'locked'
    WORKFLOW_STATUS_CHOICES = [
        (WORKFLOW_DRAFT, 'Borrador'),
        (WORKFLOW_PROPOSED, 'Propuesta'),
        (WORKFLOW_APPROVED, 'Aprobada'),
        (WORKFLOW_LOCKED, 'Bloqueada'),
    ]
    workflow_status = models.CharField(max_length=20, choices=WORKFLOW_STATUS_CHOICES, default=WORKFLOW_DRAFT)
    workflow_reason = models.CharField(max_length=220, blank=True, default='')
    workflow_updated_at = models.DateTimeField(null=True, blank=True)
    workflow_updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_session_workflow_updates',
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='locked_training_sessions',
    )

    class Meta:
        ordering = ['session_date', 'start_time', 'order', 'id']
        constraints = [
            models.UniqueConstraint(
                'microcycle',
                'session_date',
                Lower('focus'),
                name='uniq_training_session_microcycle_date_focus_ci',
            )
        ]

    def __str__(self):
        return f'{self.session_date:%d/%m} · {self.focus}'

    def save(self, *args, **kwargs):
        if not self.club_season_id:
            team_id = None
            try:
                team_id = getattr(self.microcycle, 'team_id', None)
            except Exception:
                team_id = None
            inferred = _infer_workspace_season_for_team_date(team_id, self.session_date)
            if inferred:
                self.club_season = inferred
        super().save(*args, **kwargs)


class TrainingSessionReview(models.Model):
    """
    Post-sesión rápido (60s): lo mínimo para aprender y ajustar el microciclo.
    """

    session = models.OneToOneField(TrainingSession, on_delete=models.CASCADE, related_name='review')
    actual_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    rpe = models.PositiveSmallIntegerField(null=True, blank=True, help_text='RPE 1-10')
    what_worked = models.TextField(blank=True, default='')
    what_failed = models.TextField(blank=True, default='')
    next_adjustment = models.TextField(blank=True, default='')
    execution_score = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Ejecución del objetivo 1-10')
    physical_load = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Carga física percibida 1-10')
    cognitive_load = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Carga cognitiva percibida 1-10')
    emotional_load = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Carga emocional percibida 1-10')
    evidence_url = models.URLField(blank=True, default='')
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_session_reviews',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f'Post-sesión · {self.session}'


class AuditLogEntry(models.Model):
    """
    Auditoría ligera: quién cambió qué y cuándo, para sesiones/tareas (staff).
    """

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_STATUS = 'status'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Crear'),
        (ACTION_UPDATE, 'Actualizar'),
        (ACTION_STATUS, 'Estado/Workflow'),
        (ACTION_DELETE, 'Borrar'),
    ]

    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_object_id = models.PositiveIntegerField(db_index=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_UPDATE)
    message = models.CharField(max_length=240, blank=True, default='')
    meta = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='audit_log_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['target_content_type', 'target_object_id', '-created_at']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.get_action_display()} · {self.target_content_type_id}:{self.target_object_id}'

class TrainingSessionAttendance(models.Model):
    STATUS_PRESENT = 'present'
    STATUS_ABSENT = 'absent'
    STATUS_LATE = 'late'
    STATUS_INJURED = 'injured'
    STATUS_EXCUSED = 'excused'
    STATUS_CHOICES = [
        (STATUS_PRESENT, 'Presente'),
        (STATUS_ABSENT, 'Ausente'),
        (STATUS_LATE, 'Llega tarde'),
        (STATUS_INJURED, 'Lesionado'),
        (STATUS_EXCUSED, 'Justificado'),
    ]

    session = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='attendance_marks')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='training_session_attendance')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    notes = models.CharField(max_length=180, blank=True)
    marked_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_session_attendance_marks',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('session', 'player')
        ordering = ['-updated_at', '-id']

    def __str__(self):
        player_label = self.player.name if self.player else 'Jugador'
        return f'{self.session} · {player_label} · {self.status}'


class TrainingSessionTimelineSegment(models.Model):
    """
    Segmentos temporales "En vivo" de una sesión (activación, físico/preventivo, pausas, etc.).

    Fuente de verdad para contadores de carga realizada (no solo planificada).
    """

    TYPE_ACTIVATION = 'activation'
    TYPE_PHYSICAL = 'physical'
    TYPE_MAIN = 'main'
    TYPE_COOLDOWN = 'cooldown'
    TYPE_PAUSE = 'pause'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_ACTIVATION, 'Activación'),
        (TYPE_PHYSICAL, 'Físico / Preventivo'),
        (TYPE_MAIN, 'Tarea principal'),
        (TYPE_COOLDOWN, 'Vuelta a la calma'),
        (TYPE_PAUSE, 'Pausa'),
        (TYPE_OTHER, 'Otro'),
    ]

    session = models.ForeignKey(TrainingSession, on_delete=models.CASCADE, related_name='timeline_segments')
    segment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    notes = models.CharField(max_length=180, blank=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_session_timeline_segments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'started_at', 'id']
        indexes = [
            models.Index(fields=['session', 'segment_type', 'order']),
            models.Index(fields=['session', '-created_at']),
        ]

    def __str__(self):
        label = dict(self.TYPE_CHOICES).get(self.segment_type, self.segment_type or 'Segmento')
        return f'{self.session} · {label}'


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
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='session_tasks',
        help_text='Temporada interna del club heredada de la sesión o asignada por backfill.',
    )
    title = models.CharField(max_length=160)
    block = models.CharField(max_length=30, choices=BLOCK_CHOICES, default=BLOCK_MAIN_1)
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    objective = models.TextField(blank=True)
    coaching_points = models.TextField(blank=True, help_text='Consignas clave para ejecutar la tarea')
    confrontation_rules = models.TextField(blank=True, help_text='Reglas de confrontación y puntuación')
    tactical_layout = models.JSONField(default=dict, blank=True)
    task_pdf = models.FileField(upload_to='session-tasks-pdf/', null=True, blank=True)
    task_preview_image = models.ImageField(upload_to='session-tasks-preview/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    order = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    workflow_is_latest = models.BooleanField(default=True)
    workflow_status = models.CharField(max_length=12, default='draft')
    workflow_version_group = models.CharField(max_length=32, default='', blank=True)
    workflow_version_number = models.PositiveSmallIntegerField(default=1)
    # Soft-delete (papelera). No borrar físicamente por defecto para permitir restauración.
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_session_tasks')

    def save(self, *args, **kwargs):
        if not self.club_season_id:
            try:
                self.club_season_id = getattr(self.session, 'club_season_id', None)
            except Exception:
                self.club_season_id = None
        super().save(*args, **kwargs)


class SessionTaskBackup(models.Model):
    """
    Backups persistentes (BD) para evitar pérdidas en hosts con filesystem efímero.

    Se crean automáticamente ante acciones de riesgo (papelera, edición, etc.) y sirven
    para restaurar tareas desaparecidas por borrado accidental.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='session_task_backups')
    task_id = models.PositiveIntegerField(db_index=True)
    kind = models.CharField(max_length=40, db_index=True, default='session_task')
    reason = models.CharField(max_length=80, blank=True, default='')
    actor_username = models.CharField(max_length=80, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'kind', '-created_at']),
            models.Index(fields=['team', 'task_id', '-created_at']),
        ]

    def __str__(self):
        return f'Backup {self.kind} · task#{self.task_id} · {self.team.name}'


class AiTrainerEvent(models.Model):
    """
    Telemetría ligera de IA‑Trainer para “aprendizaje” (ranking/personalización) y auditoría.

    No guarda secretos; meta contiene señales y opciones seleccionadas.
    """

    EVENT_GENERATE = 'generate'
    EVENT_COPY = 'copy'
    EVENT_SAVE_TASK = 'save_task'
    EVENT_FEEDBACK = 'feedback'
    EVENT_OPEN_SUGGESTION = 'open_suggestion'
    EVENT_CHOICES = [
        (EVENT_GENERATE, 'Generate proposals'),
        (EVENT_COPY, 'Copy proposal'),
        (EVENT_SAVE_TASK, 'Save proposal as task'),
        (EVENT_FEEDBACK, 'Feedback'),
        (EVENT_OPEN_SUGGESTION, 'Open suggested task'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ai_trainer_events')
    workspace = models.ForeignKey(Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name='ai_trainer_events')
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='ai_trainer_events')
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES)
    meta = models.JSONField(default=dict, blank=True)
    session_key = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'event_type', '-created_at']),
            models.Index(fields=['workspace', 'event_type', '-created_at']),
            models.Index(fields=['user', 'event_type', '-created_at']),
        ]

    def __str__(self):
        return f'IA‑Trainer {self.event_type} · {self.team.name}'


class AiTrainerTokenWeight(models.Model):
    """
    “Aprendizaje” simple: pesos por token (palabras/conceptos) por equipo/workspace.
    Se actualiza con feedback positivo/negativo y con lo que el entrenador guarda.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ai_trainer_token_weights')
    workspace = models.ForeignKey(Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name='ai_trainer_token_weights')
    token = models.CharField(max_length=64)
    weight = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'workspace', 'token')
        indexes = [
            models.Index(fields=['team', 'workspace', 'token']),
            models.Index(fields=['team', '-updated_at']),
        ]

    def __str__(self):
        ws = f' · ws={self.workspace_id}' if self.workspace_id else ''
        return f'{self.team.name}{ws} · {self.token}={self.weight:.2f}'


class AiTrainerTaskIndex(models.Model):
    """
    Índice “RAG” (fase 2): documento normalizado por tarea para búsqueda semántica/lexical.

    Por ahora es lexical (tokens + score); se puede ampliar a embeddings si se añade proveedor.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ai_trainer_task_index')
    task = models.OneToOneField(SessionTask, on_delete=models.CASCADE, related_name='ai_trainer_index')
    repository = models.CharField(max_length=32, blank=True)
    content = models.TextField(blank=True)
    content_norm = models.TextField(blank=True)
    tokens = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', 'repository', '-updated_at']),
        ]

    def __str__(self):
        return f'Index {self.team.name} · task#{self.task_id}'


class AiTrainerDictionaryEntry(models.Model):
    """
    Overrides editables del diccionario base (coach_dictionary_es_v1.json).

    Se guardan en BD para persistir en Render y poder “entrenar” IA‑Trainer sin costes externos.
    """

    SECTION_PRINCIPLES = 'principles'
    SECTION_ZONES = 'zones'
    SECTION_PHASES = 'phases'
    SECTION_FIGURES = 'figures'
    SECTION_CHOICES = [
        (SECTION_PRINCIPLES, 'Principios'),
        (SECTION_ZONES, 'Zonas'),
        (SECTION_PHASES, 'Fases'),
        (SECTION_FIGURES, 'Figuras'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ai_trainer_dictionary_entries')
    workspace = models.ForeignKey(Workspace, null=True, blank=True, on_delete=models.SET_NULL, related_name='ai_trainer_dictionary_entries')
    section = models.CharField(max_length=24, choices=SECTION_CHOICES)
    entry_key = models.CharField(max_length=64)
    label = models.CharField(max_length=160, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    coaching_points = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='ai_trainer_dictionary_entries')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'workspace', 'section', 'entry_key')
        ordering = ['section', 'entry_key', '-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', 'workspace', 'section', 'entry_key']),
            models.Index(fields=['team', 'section', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.team.name} · {self.section}:{self.entry_key}'


class SessionTaskBookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_task_bookmarks')
    task = models.ForeignKey(SessionTask, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'task')
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user.username} ★ {self.task.title}'


class SessionTaskCollection(models.Model):
    REPO_TRADITIONAL = 'traditional'
    REPO_INTERACTIVE = 'interactive'
    REPO_CHOICES = [
        (REPO_TRADITIONAL, 'Tradicionales'),
        (REPO_INTERACTIVE, 'Interactivas'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='task_collections')
    repository = models.CharField(max_length=32, choices=REPO_CHOICES, default=REPO_TRADITIONAL)
    name = models.CharField(max_length=120)
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_collections')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'repository', 'name')
        ordering = ['name', 'id']

    def __str__(self):
        return f'{self.team.name} · {self.name}'


class SessionTaskCollectionItem(models.Model):
    collection = models.ForeignKey(SessionTaskCollection, on_delete=models.CASCADE, related_name='items')
    task = models.ForeignKey(SessionTask, on_delete=models.CASCADE, related_name='collection_items')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('collection', 'task')
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.collection.name} · {self.task.title}'


class ImportedSessionDocument(models.Model):
    REPO_TRADITIONAL = 'traditional'
    REPO_INTERACTIVE = 'interactive'
    REPO_CHOICES = [
        (REPO_TRADITIONAL, 'Clásicas'),
        (REPO_INTERACTIVE, 'Interactivas'),
    ]

    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='imported_session_documents')
    repository = models.CharField(max_length=20, choices=REPO_CHOICES, default=REPO_TRADITIONAL)
    title = models.CharField(max_length=180)
    session_date = models.DateField(null=True, blank=True)
    pdf = models.FileField(upload_to='imported-sessions-pdf/')
    preview_image = models.ImageField(upload_to='imported-sessions-preview/', null=True, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='imported_session_documents')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-session_date', '-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'repository', '-created_at']),
            models.Index(fields=['team', 'repository', '-session_date']),
        ]

    def __str__(self):
        return self.title or f'Sesión importada {self.id}'


class PdfGraphicAsset(models.Model):
    """
    Recursos gráficos extraídos de PDFs importados (imágenes embebidas).

    Se guardan por equipo (coach/club) o por usuario (Task Studio) para
    reutilizarlos en la pizarra sin depender de URLs externas (evita canvas tainting).
    """

    team = models.ForeignKey('Team', null=True, blank=True, on_delete=models.CASCADE, related_name='pdf_graphic_assets')
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='pdf_graphic_assets')
    title = models.CharField(max_length=160, blank=True)
    sha256 = models.CharField(max_length=64, db_index=True)
    file = models.ImageField(upload_to='pdf-graphic-assets/')
    # Fallback persistente para hosts con FS efímero (Render free): una versión compacta embebida en BD.
    # Se usa cuando `file` no existe o no se puede abrir.
    embedded_data_url = models.TextField(blank=True, default='')
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    source_pdf_name = models.CharField(max_length=220, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'sha256'],
                condition=Q(team__isnull=False),
                name='uniq_pdf_asset_team_sha256',
            ),
            models.UniqueConstraint(
                fields=['owner', 'sha256'],
                condition=Q(owner__isnull=False),
                name='uniq_pdf_asset_owner_sha256',
            ),
        ]

    def __str__(self):
        scope = self.team.name if self.team_id else (self.owner.username if self.owner_id else 'global')
        return self.title or f'PDF asset {self.id} · {scope}'


class DataImportLog(models.Model):
    file_name = models.CharField(max_length=200)
    imported_at = models.DateTimeField(default=timezone.now)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-imported_at']

    def __str__(self):
        return f'{self.file_name} ({self.imported_at:%Y-%m-%d %H:%M})'


class TacticalPlaybookClip(models.Model):
    """
    Clips de simulación (jugadas) reutilizables como Playbook.

    Se guardan por equipo. Para uso interno "global" del sistema, se usa el equipo especial `slug="pizarra"`.
    """

    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='tactical_playbook_clips')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tactical_playbook_clips',
        help_text='Temporada interna del club para plantillas y clips tácticos.',
    )
    name = models.CharField(max_length=160)
    folder = models.CharField(max_length=80, blank=True)
    tags = models.JSONField(default=list, blank=True)
    steps = models.JSONField(default=list, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    version_group = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    version_number = models.PositiveSmallIntegerField(default=1)
    is_latest = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', '-updated_at']),
            models.Index(fields=['team', 'version_group', 'is_latest']),
            models.Index(fields=['club_season', '-updated_at'], name='clip_club_season_updated_idx'),
        ]

    def __str__(self):
        team_label = getattr(self.team, 'name', '') or 'team'
        return f'{team_label} · {self.name}'


class TacticalPlaybookClipFavorite(models.Model):
    clip = models.ForeignKey(TacticalPlaybookClip, on_delete=models.CASCADE, related_name='favorite_rows')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tactical_playbook_favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        unique_together = ('clip', 'user')

    def __str__(self):
        return f'⭐ {self.user.username} · {self.clip.name}'


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


class AnalystVideoFolder(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='analysis_video_folders')
    rival_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analysis_video_folders_as_rival',
    )
    name = models.CharField(max_length=140)
    base_video = models.ForeignKey(
        'RivalVideo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='base_for_folders',
        help_text='Vídeo base de la carpeta (partido completo) para recortar clips.',
    )
    created_by = models.CharField(max_length=80, blank=True)
    is_visible_to_players = models.BooleanField(
        default=False,
        help_text='Si está activo, la carpeta (y sus vídeos) se muestra en el espacio de Jugadores del equipo.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', '-created_at', '-id']
        unique_together = ('team', 'rival_team', 'name')

    def __str__(self):
        base = self.rival_team.display_name if self.rival_team else self.team.display_name
        return f'{base} · {self.name}'


class RivalVideo(models.Model):
    SOURCE_UNIVERSO = 'universo'
    SOURCE_RFAF = 'rfaf'
    SOURCE_PREFERENTE = 'preferente'
    SOURCE_YOUTUBE = 'youtube'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [
        (SOURCE_UNIVERSO, 'Universo RFAF'),
        (SOURCE_RFAF, 'RFAF'),
        (SOURCE_PREFERENTE, 'La Preferente'),
        (SOURCE_YOUTUBE, 'YouTube'),
        (SOURCE_MANUAL, 'Manual'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='analysis_videos')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rival_videos',
        help_text='Temporada interna del club para biblioteca de análisis.',
    )
    owner_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_rival_videos',
        help_text='Propietario cuando el vídeo está en biblioteca personal (sin team/folder).',
    )
    rival_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='rival_videos')
    folder = models.ForeignKey(
        AnalystVideoFolder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='videos',
    )
    title = models.CharField(max_length=180)
    video = models.FileField(upload_to='rival-videos/', blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    source_url = models.URLField(max_length=600, blank=True, help_text='URL de origen (p.ej. YouTube) si aplica.')
    notes = models.TextField(blank=True)
    is_base = models.BooleanField(
        default=False,
        help_text='Marca el vídeo como “base” (partido completo) para que aparezca fijado arriba y sea fácil seguir recortando.',
    )
    trim_enabled = models.BooleanField(
        default=False,
        help_text='Si está activo, Video Studio limita la reproducción al rango IN/OUT definido.',
    )
    trim_in_ms = models.PositiveIntegerField(
        default=0,
        help_text='IN del corte base (ms) para trabajar sin relleno (anuncios, esperas, etc.).',
    )
    trim_out_ms = models.PositiveIntegerField(
        default=0,
        help_text='OUT del corte base (ms). 0 significa sin OUT.',
    )
    duration_ms = models.PositiveIntegerField(default=0)
    ingest_status = models.CharField(max_length=12, default='', blank=True)
    ingest_error = models.TextField(default='', blank=True)
    video_fps = models.FloatField(default=0)
    video_w = models.PositiveIntegerField(default=0)
    video_h = models.PositiveIntegerField(default=0)
    assigned_players = models.ManyToManyField(Player, blank=True, related_name='assigned_analysis_videos')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        team_label = self.rival_team.name if self.rival_team else 'Rival'
        return f'{team_label} · {self.title}'

class VideoTelestrationProject(models.Model):
    """
    Proyecto de telestración (anotaciones) sobre un vídeo.

    Se guarda por equipo (para multiclub) y opcionalmente vinculado a `RivalVideo`.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='video_telestration_projects')
    owner_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_video_telestration_projects',
        help_text='Propietario cuando el proyecto está en biblioteca personal.',
    )
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='telestration_projects')
    title = models.CharField(max_length=180, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', '-updated_at']),
            models.Index(fields=['video', '-updated_at']),
        ]

    def __str__(self):
        return self.title or f'Proyecto {self.id}'


class VideoTimelineEvent(models.Model):
    """
    Eventos/etiquetas en la línea de tiempo de un vídeo (para análisis rápido).

    Se guardan por equipo y vídeo para evitar mezclar contextos (Senior vs Prebenjamín).
    """

    KIND_TAG = 'tag'
    KIND_NOTE = 'note'
    KIND_GOAL = 'goal'
    KIND_SHOT = 'shot'
    KIND_PRESS = 'press'
    KIND_TURNOVER = 'turnover'
    KIND_SET_PIECE = 'abp'
    KIND_CHOICES = [
        (KIND_TAG, 'Tag'),
        (KIND_NOTE, 'Nota'),
        (KIND_GOAL, 'Gol'),
        (KIND_SHOT, 'Disparo'),
        (KIND_PRESS, 'Presión'),
        (KIND_TURNOVER, 'Pérdida'),
        (KIND_SET_PIECE, 'ABP'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='video_timeline_events')
    owner_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_video_timeline_events',
        help_text='Propietario cuando el evento está en biblioteca personal.',
    )
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='timeline_events')
    time_ms = models.PositiveIntegerField(default=0, db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_TAG)
    label = models.CharField(max_length=160, blank=True)
    color = models.CharField(max_length=16, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['time_ms', 'id']
        indexes = [
            models.Index(fields=['team', 'video', 'time_ms']),
            models.Index(fields=['video', 'time_ms']),
        ]

    @property
    def time_seconds(self) -> float:
        return float(self.time_ms or 0) / 1000.0

    def __str__(self):
        return f'{self.video_id} · {self.kind} · {self.time_ms}ms'


class VideoClip(models.Model):
    """
    Clip (segmento IN/OUT) de un vídeo, con anotación opcional.

    Nota: usamos milisegundos para evitar problemas de float al recortar.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='video_clips')
    owner_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_video_clips',
        help_text='Propietario cuando el clip está en biblioteca personal.',
    )
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='clips')
    title = models.CharField(max_length=180, blank=True)
    collection = models.CharField(max_length=120, blank=True, help_text='Nombre de la colección/playlist (simple).')
    in_ms = models.PositiveIntegerField(default=0)
    out_ms = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    overlay = models.JSONField(default=dict, blank=True, help_text='Estado de la pizarra (fabric/canvas) para este clip.')
    thumbnail = models.ImageField(
        upload_to='video-clips/thumbs/',
        null=True,
        blank=True,
        help_text='Carátula del clip (snapshot del primer frame en IN).',
    )
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-updated_at']),
            models.Index(fields=['video', 'in_ms']),
        ]

    @property
    def in_seconds(self) -> float:
        return float(self.in_ms or 0) / 1000.0

    @property
    def out_seconds(self) -> float:
        return float(self.out_ms or 0) / 1000.0

    def __str__(self):
        base = self.title or f'Clip {self.id}'
        return f'{base} · {self.in_ms}-{self.out_ms}ms'


class VideoAiInsight(models.Model):
    """
    Resultado de IA para un vídeo (resumen, momentos clave, sugerencias).

    Se guarda por equipo/vídeo para evitar mezclar contextos.
    """

    STATUS_OK = 'ok'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_OK, 'OK'),
        (STATUS_ERROR, 'Error'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_ai_insights')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='ai_insights')
    input_hash = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OK)
    provider = models.CharField(max_length=32, blank=True, help_text='openai|heuristic|...')
    model = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-updated_at']),
            models.Index(fields=['video', '-updated_at']),
        ]

    def __str__(self):
        return f'AI {self.team_id}·{self.video_id}·{self.status}'


class VideoAiTrackJob(models.Model):
    """
    Job asíncrono de AutoTrack IA.

    Permite procesar rangos largos sin bloquear la petición HTTP y conserva el
    resultado para que el cliente pueda reintentar/pollear.
    """

    ACTION_REID = 'reid'
    ACTION_BATCH = 'batch'
    ACTION_TRAIN = 'train'
    ACTION_DETECT_ACTIONS = 'detect_actions'
    ACTION_TRAIN_ACTIONS = 'train_actions'
    ACTION_EXPORT_FOLLOW = 'export_follow'
    ACTION_CHOICES = [
        (ACTION_REID, 'ReID'),
        (ACTION_BATCH, 'Batch'),
        (ACTION_TRAIN, 'Entrenamiento'),
        (ACTION_DETECT_ACTIONS, 'Detección de acciones'),
        (ACTION_TRAIN_ACTIONS, 'Entrenamiento de acciones'),
        (ACTION_EXPORT_FOLLOW, 'Exportar seguimiento'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En progreso'),
        (STATUS_DONE, 'Completado'),
        (STATUS_ERROR, 'Error'),
        (STATUS_CANCELED, 'Cancelado'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_ai_track_jobs')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='ai_track_jobs')
    clip = models.ForeignKey(VideoClip, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_track_jobs')
    action = models.CharField(max_length=24, choices=ACTION_CHOICES, default=ACTION_REID)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    progress = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=220, blank=True)
    error = models.TextField(blank=True)
    cancel_requested = models.BooleanField(default=False)
    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_ai_track_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['team', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'AI Track {self.team_id}·{self.video_id}·{self.status}'


class VideoAiCorrectionExample(models.Model):
    """
    Ejemplo supervisado creado por una corrección manual del analista.

    Se usa para entrenar/mejorar el seguimiento del jugador objetivo.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_ai_correction_examples')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='ai_correction_examples')
    clip = models.ForeignKey(VideoClip, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_correction_examples')
    marker_uid = models.CharField(max_length=100, blank=True)
    time_ms = models.PositiveIntegerField(default=0)
    x_rel = models.FloatField(default=0)
    y_rel = models.FloatField(default=0)
    label = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_ai_correction_examples',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['video', 'marker_uid', 'time_ms']),
            models.Index(fields=['team', '-created_at']),
        ]

    def __str__(self):
        return f'AI correction {self.video_id} · {self.marker_uid} · {self.time_ms}ms'


class VideoAiActionExample(models.Model):
    """
    Feedback supervisado del analista para acciones de juego.

    Permite construir dataset propio de acciones: positivos y negativos por etiqueta.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_ai_action_examples')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='ai_action_examples')
    clip = models.ForeignKey(VideoClip, on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_action_examples')
    action_key = models.CharField(max_length=80, db_index=True)
    label = models.CharField(max_length=120, blank=True)
    is_positive = models.BooleanField(default=True)
    start_ms = models.PositiveIntegerField(default=0)
    end_ms = models.PositiveIntegerField(default=0)
    confidence = models.FloatField(default=0)
    payload = models.JSONField(default=dict, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_ai_action_examples',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['team', 'action_key', '-created_at']),
            models.Index(fields=['video', 'start_ms', 'end_ms']),
        ]

    def __str__(self):
        sign = '+' if self.is_positive else '-'
        return f'AI action {sign}{self.action_key} · {self.video_id} · {self.start_ms}-{self.end_ms}ms'


class VideoAiKnowledgeEntry(models.Model):
    """
    Concepto táctico curado para que la IA de vídeo razone con conocimiento futbolístico.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='video_ai_knowledge_entries')
    source_key = models.CharField(max_length=80, db_index=True)
    concept_key = models.CharField(max_length=100, db_index=True)
    category = models.CharField(max_length=60, db_index=True)
    title = models.CharField(max_length=160)
    summary = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'title', 'id']
        unique_together = ('team', 'concept_key')
        indexes = [
            models.Index(fields=['team', 'category', 'is_active']),
            models.Index(fields=['team', 'concept_key']),
            models.Index(fields=['source_key', 'category']),
        ]

    def __str__(self):
        return f'{self.category}:{self.concept_key}'


class VideoAiGameCalibration(models.Model):
    """
    Contexto geométrico y táctico mínimo que el analista valida para un vídeo.

    Sin esta capa la IA no debe afirmar fases como progresión, transición o ABP:
    solo puede proponer hipótesis a revisar.
    """

    ATTACK_LTR = 'ltr'
    ATTACK_RTL = 'rtl'
    ATTACK_UNKNOWN = 'unknown'
    ATTACK_DIRECTION_CHOICES = [
        (ATTACK_LTR, 'Izquierda a derecha'),
        (ATTACK_RTL, 'Derecha a izquierda'),
        (ATTACK_UNKNOWN, 'Desconocida'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_ai_game_calibrations')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='ai_game_calibrations')
    attack_direction = models.CharField(max_length=12, choices=ATTACK_DIRECTION_CHOICES, default=ATTACK_UNKNOWN)
    phase = models.CharField(max_length=40, blank=True, help_text='Parte o tramo: first_half, second_half, custom...')
    field_points = models.JSONField(default=dict, blank=True, help_text='Puntos normalizados validados por el analista.')
    payload = models.JSONField(default=dict, blank=True)
    confidence = models.FloatField(default=0)
    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_ai_game_calibrations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        unique_together = ('team', 'video', 'phase')
        indexes = [
            models.Index(fields=['team', 'video', '-updated_at']),
            models.Index(fields=['video', 'phase']),
        ]

    def __str__(self):
        return f'AI calibration {self.video_id} · {self.phase or "default"} · {self.attack_direction}'


class VideoExportAsset(models.Model):
    """
    Export de vídeo generado desde Video Studio (segmento grabado con telestración).

    Nota: el render/encode se hace en cliente (MediaRecorder) y se sube aquí para compartirlo
    sin depender de descargas del navegador (iPad/iOS).
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_export_assets')
    video = models.ForeignKey(RivalVideo, on_delete=models.SET_NULL, null=True, blank=True, related_name='export_assets')
    clip = models.ForeignKey(VideoClip, on_delete=models.SET_NULL, null=True, blank=True, related_name='export_assets')
    title = models.CharField(max_length=180, blank=True)
    file = models.FileField(upload_to='video-exports/')
    mime_type = models.CharField(max_length=80, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', '-created_at']),
            models.Index(fields=['video', '-created_at']),
            models.Index(fields=['clip', '-created_at']),
        ]

    def __str__(self):
        return self.title or f'Export {self.id}'


class AnalysisVideoReport(models.Model):
    """
    Informe de análisis por carpeta (rival).

    Se usa para montar una presentación (PPTX) con clips, texto, capturas y recursos visuales.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='analysis_video_reports')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='analysis_video_reports',
        help_text='Temporada interna del club para informes de análisis.',
    )
    folder = models.ForeignKey(
        AnalystVideoFolder,
        on_delete=models.CASCADE,
        related_name='analysis_reports',
    )
    title = models.CharField(max_length=180)
    notes = models.TextField(blank=True)
    pptx_file = models.FileField(upload_to='analysis-reports/pptx/', null=True, blank=True)
    pptx_updated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['team', 'folder', '-updated_at']),
            models.Index(fields=['folder', '-updated_at']),
            models.Index(fields=['club_season', '-updated_at'], name='avr_club_season_updated_idx'),
        ]

    def __str__(self):
        return self.title or f'Informe {self.id}'


class AnalysisVideoReportItem(models.Model):
    report = models.ForeignKey(AnalysisVideoReport, on_delete=models.CASCADE, related_name='items')
    position = models.PositiveIntegerField(default=0)
    clip = models.ForeignKey(VideoClip, on_delete=models.SET_NULL, null=True, blank=True, related_name='analysis_report_items')
    export_asset = models.ForeignKey(
        VideoExportAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analysis_report_items',
        help_text='Export MP4 a incrustar en el PPTX. Si está vacío, se usa el último export del clip.',
    )
    title = models.CharField(max_length=180, blank=True)
    body = models.TextField(blank=True)
    tactical_layout = models.JSONField(default=dict, blank=True)
    tactical_preview_image = models.ImageField(upload_to='analysis-reports/tactics/', null=True, blank=True)
    tactical_video = models.FileField(upload_to='analysis-reports/tactics/video/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'id']
        indexes = [
            models.Index(fields=['report', 'position']),
            models.Index(fields=['clip', '-updated_at']),
        ]

    def __str__(self):
        return self.title or (self.clip.title if self.clip_id else f'Item {self.id}')


class AnalysisVideoReportItemImage(models.Model):
    item = models.ForeignKey(AnalysisVideoReportItem, on_delete=models.CASCADE, related_name='images')
    position = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='analysis-reports/images/')
    caption = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']
        indexes = [
            models.Index(fields=['item', 'position']),
        ]

    def __str__(self):
        return self.caption or f'Imagen {self.id}'


class VideoVoiceoverAsset(models.Model):
    """
    Voz en off subida/grabada para mezclarla en exports del Video Studio.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_voiceovers')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='voiceovers')
    title = models.CharField(max_length=180, blank=True)
    file = models.FileField(upload_to='video-voiceovers/')
    mime_type = models.CharField(max_length=80, blank=True)
    duration_ms = models.IntegerField(default=0)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['video', '-created_at']),
        ]

    def __str__(self):
        return self.title or f'Voiceover {self.id}'


class VideoMusicAsset(models.Model):
    """
    Música/BGM subida para mezclarla en exports del Video Studio.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_music_assets')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='music_assets')
    title = models.CharField(max_length=180, blank=True)
    file = models.FileField(upload_to='video-music/')
    mime_type = models.CharField(max_length=80, blank=True)
    duration_ms = models.IntegerField(default=0)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['video', '-created_at']),
        ]

    def __str__(self):
        return self.title or f'Music {self.id}'


class VideoInboxItem(models.Model):
    """
    Elemento compartido internamente (sin enlaces públicos) para staff.
    """

    KIND_CLIP = 'clip'
    KIND_EXPORT = 'export'
    KIND_PLAYLIST = 'playlist'
    KIND_REPORT = 'report'
    KIND_CHOICES = [
        (KIND_CLIP, 'Clip'),
        (KIND_EXPORT, 'Export'),
        (KIND_PLAYLIST, 'Playlist'),
        (KIND_REPORT, 'Informe'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='video_inbox_items')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_inbox_items')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_inbox')
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='video_inbox_sent')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_CLIP)
    title = models.CharField(max_length=180, blank=True)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    thread_key = models.CharField(
        max_length=40,
        blank=True,
        db_index=True,
        help_text='Clave compartida (entre destinatarios) para comentarios internos.',
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['workspace', 'target_user', '-created_at']),
            models.Index(fields=['team', 'target_user', '-created_at']),
            models.Index(fields=['target_user', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f'{self.target_user.username} · {self.kind} · {self.created_at:%Y-%m-%d}'


class VideoInboxComment(models.Model):
    """
    Comentarios internos para un elemento compartido (thread) en Bandeja de vídeo.

    `thread_key` permite que varios destinatarios compartan la misma conversación.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='video_inbox_comments')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_inbox_comments')
    thread_key = models.CharField(max_length=40, db_index=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_inbox_comments',
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['workspace', 'team', 'thread_key', 'created_at']),
        ]

    def __str__(self):
        return f'Comentario {self.id} · {self.thread_key}'


class ChunkedRivalVideoUpload(models.Model):
    """
    Subida por chunks para vídeos largos (evita timeouts y límites de proxy).
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='chunked_video_uploads')
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chunked_video_uploads')
    upload_id = models.CharField(max_length=64, unique=True, db_index=True)
    original_name = models.CharField(max_length=220, blank=True)
    mime_type = models.CharField(max_length=80, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    total_chunks = models.PositiveIntegerField(default=0)
    received_chunks = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', '-created_at']),
        ]

    def __str__(self):
        return f'{self.team_id} · upload {self.upload_id}'


class RivalAnalysisReport(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_READY = 'ready'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Borrador'),
        (STATUS_READY, 'Listo para partido'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='rival_analysis_reports')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rival_analysis_reports',
        help_text='Temporada interna del club para informes de rival.',
    )
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


class PlayerSeasonReport(models.Model):
    """
    Valoración cualitativa + ratings del cuerpo técnico para el informe de fin de temporada del jugador.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='player_season_reports')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='season_reports')
    season_label = models.CharField(max_length=80, blank=True, default='')
    scope = models.CharField(max_length=24, blank=True, default='')
    tournament_name = models.CharField(max_length=120, blank=True, default='')

    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    technical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    tactical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    physical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    mental_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    social_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    leadership_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')
    game_knowledge_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='1-10 (opcional)')

    strengths = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    objectives_next = models.TextField(blank=True)
    coach_comments = models.TextField(blank=True)
    is_final = models.BooleanField(default=False)
    ring_kpis = models.JSONField(default=list, blank=True, help_text='Listado (max 4) de KPIs en anillos (0-100).')
    manual_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text='Overrides manuales (stats/partidos) para el PDF cuando faltan datos o hay inconsistencias.',
    )

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_player_season_reports')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_player_season_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Informe de temporada (jugador)'
        verbose_name_plural = 'Informes de temporada (jugadores)'
        ordering = ['-updated_at', '-id']
        unique_together = ('team', 'player', 'season_label', 'scope', 'tournament_name')

    def __str__(self):
        label = self.season_label or 'Temporada'
        return f'{self.player_id} · {label}'


class PlayerEvaluation(models.Model):
    """
    Evaluaciones periódicas del cuerpo técnico durante la temporada.
    """

    TYPE_INITIAL = 'initial'
    TYPE_MONTHLY = 'monthly'
    TYPE_QUARTERLY = 'quarterly'
    TYPE_FINAL = 'final'
    TYPE_POST_ROUND = 'post_round'
    TYPE_CHOICES = [
        (TYPE_INITIAL, 'Inicial'),
        (TYPE_MONTHLY, 'Mensual'),
        (TYPE_QUARTERLY, 'Trimestral'),
        (TYPE_FINAL, 'Final'),
        (TYPE_POST_ROUND, 'Post-jornada'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Borrador'),
        (STATUS_CLOSED, 'Cerrada'),
    ]
    MATURATION_PRE = 'pre_phv'
    MATURATION_CIRCA = 'circa_phv'
    MATURATION_POST = 'post_phv'
    MATURATION_UNKNOWN = ''
    MATURATION_CHOICES = [
        (MATURATION_UNKNOWN, 'Sin definir'),
        (MATURATION_PRE, 'Pre-PHV'),
        (MATURATION_CIRCA, 'Circa-PHV'),
        (MATURATION_POST, 'Post-PHV'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='player_evaluations')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='evaluations')
    club_season = models.ForeignKey(
        WorkspaceSeason,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_evaluations',
    )
    evaluation_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default=TYPE_MONTHLY)
    evaluated_on = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    role = models.CharField(max_length=80, blank=True)
    evaluated_position = models.CharField(max_length=60, blank=True)
    recommended_position = models.CharField(max_length=60, blank=True)

    technical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    tactical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    physical_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    mental_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    social_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    wellness_sleep = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Sueño/descanso 1-10.')
    wellness_fatigue = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Fatiga percibida 1-10.')
    wellness_soreness = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Dolor muscular 1-10.')
    wellness_stress = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Estrés percibido 1-10.')
    wellness_motivation = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Motivación 1-10.')
    session_rpe = models.PositiveSmallIntegerField(null=True, blank=True, help_text='RPE sesión 1-10.')
    session_minutes = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Duración de sesión/partido en minutos.')

    yo_yo_ir1_m = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Yo-Yo IR1 en metros.')
    sprint_5m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sprint_10m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sprint_20m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    agility_505_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cmj_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Salto CMJ en cm.')
    copenhagen_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    single_leg_control_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='Control monopodal 1-10.')
    objective_performance_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='Síntesis objetiva 1-10 basada en KPIs/datos disponibles.')
    availability_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True, help_text='Disponibilidad/asistencia 1-10.')
    maturation_status = models.CharField(max_length=16, choices=MATURATION_CHOICES, blank=True, default='')
    maturity_offset_years = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text='Años estimados respecto al PHV.')
    growth_velocity_cm_year = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Velocidad de crecimiento cm/año.')
    evidence_notes = models.TextField(blank=True)

    strengths = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    objectives_next = models.TextField(blank=True)
    coach_comments = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_player_evaluations')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_player_evaluations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evaluación de jugador'
        verbose_name_plural = 'Evaluaciones de jugadores'
        ordering = ['-evaluated_on', '-updated_at', '-id']
        indexes = [
            models.Index(fields=['player', '-evaluated_on']),
            models.Index(fields=['team', 'club_season', '-evaluated_on']),
            models.Index(fields=['status', '-evaluated_on']),
        ]

    @property
    def average_rating(self):
        values = [
            self.technical_rating,
            self.tactical_rating,
            self.physical_rating,
            self.mental_rating,
            self.social_rating,
        ]
        values = [value for value in values if value is not None]
        if not values:
            return self.overall_rating
        return round(sum(values) / len(values), 1)

    @property
    def wellness_score(self):
        values = [
            self.wellness_sleep,
            self.wellness_fatigue,
            self.wellness_soreness,
            self.wellness_stress,
            self.wellness_motivation,
        ]
        values = [int(value) for value in values if value is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    @property
    def srpe_load(self):
        if self.session_rpe is None or self.session_minutes is None:
            return None
        return int(self.session_rpe) * int(self.session_minutes)

    @property
    def physical_screen_score(self):
        values = [
            self.single_leg_control_rating,
            self.objective_performance_rating,
            self.availability_rating,
        ]
        values = [float(value) for value in values if value is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    @property
    def assisted_score(self):
        parts = []
        coach = self.average_rating
        if coach is not None:
            parts.append((float(coach), 0.50))
        if self.objective_performance_rating is not None:
            parts.append((float(self.objective_performance_rating), 0.20))
        if self.availability_rating is not None:
            parts.append((float(self.availability_rating), 0.15))
        wellness = self.wellness_score
        if wellness is not None:
            parts.append((float(wellness), 0.10))
        if self.single_leg_control_rating is not None:
            parts.append((float(self.single_leg_control_rating), 0.05))
        total_weight = sum(weight for _value, weight in parts)
        if not total_weight:
            return self.overall_rating
        return round(sum(value * weight for value, weight in parts) / total_weight, 1)

    def __str__(self):
        return f'{self.player_id} · {self.get_evaluation_type_display()} · {self.evaluated_on}'


class AnalystMatchReport(models.Model):
    """
    Repositorio de informes de partido (PDF/JPG/PNG) que sube el analista.

    Se guarda por equipo y se puede vincular opcionalmente a un `Match`.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='match_reports')
    match = models.ForeignKey(
        Match,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analyst_reports',
    )
    title = models.CharField(max_length=180, blank=True)
    opponent_name = models.CharField(max_length=180, blank=True)
    match_date = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    document = models.FileField(upload_to='match-reports/')
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Informe de partido (analista)'
        verbose_name_plural = 'Informes de partido (analista)'

    def __str__(self):
        return self.title or f'Informe {self.id}'


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


class ShareLink(models.Model):
    KIND_TASK_PDF = 'task_pdf'
    KIND_CONVOCATION_PDF = 'convocation_pdf'
    KIND_TASK_SIMULATION = 'task_simulation'
    KIND_TACTICAL_PLAYBOOK_CLIP = 'tactical_playbook_clip'
    KIND_VIDEO_CLIP = 'video_clip'
    KIND_VIDEO_EXPORT = 'video_export'
    KIND_VIDEO_PLAYLIST = 'video_playlist'
    KIND_VIDEO_REPORT = 'video_report'
    KIND_CHOICES = [
        (KIND_TASK_PDF, 'PDF de tarea'),
        (KIND_CONVOCATION_PDF, 'PDF de convocatoria'),
        (KIND_TASK_SIMULATION, 'Simulación de tarea'),
        (KIND_TACTICAL_PLAYBOOK_CLIP, 'Clip Playbook'),
        (KIND_VIDEO_CLIP, 'Clip de vídeo'),
        (KIND_VIDEO_EXPORT, 'Export de vídeo'),
        (KIND_VIDEO_PLAYLIST, 'Lista de clips (vídeo)'),
        (KIND_VIDEO_REPORT, 'Informe PDF (vídeo)'),
    ]

    token = models.CharField(max_length=120, unique=True, db_index=True)
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, default=KIND_TASK_PDF)
    payload = models.JSONField(default=dict, blank=True)
    password_hash = models.CharField(max_length=180, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='share_links')
    is_active = models.BooleanField(default=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Enlace compartido'
        verbose_name_plural = 'Enlaces compartidos'

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe(32)

    def is_expired(self, now=None):
        reference = now or timezone.now()
        return bool(self.expires_at and self.expires_at <= reference)

    def can_be_used(self, now=None):
        return bool(self.is_active and not self.is_expired(now=now))

    def __str__(self):
        return f'{self.kind} · {self.created_at:%Y-%m-%d %H:%M}'


class VideoStudioExportJob(models.Model):
    """
    Job asíncrono de export (MP4) para Video Studio.

    Se usa para evitar timeouts en exports largos (playlist/timeline) y permitir progreso/cancelación.
    """

    KIND_PLAYLIST_MP4 = 'playlist_mp4'
    KIND_CHOICES = [
        (KIND_PLAYLIST_MP4, 'Playlist MP4'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_ERROR = 'error'
    STATUS_CANCELED = 'canceled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En progreso'),
        (STATUS_DONE, 'Completado'),
        (STATUS_ERROR, 'Error'),
        (STATUS_CANCELED, 'Cancelado'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_export_jobs')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='export_jobs')
    kind = models.CharField(max_length=40, choices=KIND_CHOICES, default=KIND_PLAYLIST_MP4)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    progress = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=220, blank=True)
    error = models.TextField(blank=True)
    cancel_requested = models.BooleanField(default=False)

    export_asset = models.ForeignKey(
        'VideoExportAsset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
    )
    share_link = models.ForeignKey(
        'ShareLink',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_export_jobs',
    )

    created_by = models.CharField(max_length=80, blank=True)
    created_by_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='video_export_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['team', 'video', '-created_at']),
            models.Index(fields=['team', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'VSJob {self.id} · {self.kind} · {self.status}'


class AuditEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    actor_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    actor = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=80)
    message = models.CharField(max_length=220, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    ip = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Evento de auditoría'
        verbose_name_plural = 'Eventos de auditoría'

    def __str__(self):
        return f'{self.action} · {self.created_at:%Y-%m-%d %H:%M}'


class VideoReviewMark(models.Model):
    """
    Marca de revisión por usuario (clips y eventos timeline).
    """

    KIND_CLIP = 'clip'
    KIND_EVENT = 'event'
    KIND_CHOICES = [
        (KIND_CLIP, 'Clip'),
        (KIND_EVENT, 'Timeline'),
    ]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='video_review_marks')
    video = models.ForeignKey(RivalVideo, on_delete=models.CASCADE, related_name='review_marks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_review_marks')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_CLIP)
    object_id = models.PositiveIntegerField(default=0, db_index=True)
    is_done = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        unique_together = ('team', 'video', 'user', 'kind', 'object_id')
        indexes = [
            models.Index(fields=['team', 'video', 'user', 'kind', 'object_id']),
            models.Index(fields=['user', 'video', 'kind', '-updated_at']),
        ]

    def __str__(self):
        return f'{self.user_id}·{self.video_id}·{self.kind}·{self.object_id}'


class AppUserRole(models.Model):
    ROLE_PLAYER = 'jugador'
    ROLE_GUEST = 'invitado'
    ROLE_TASK_STUDIO = 'task_studio'
    ROLE_COACH = 'entrenador'
    ROLE_FITNESS = 'preparador_fisico'
    ROLE_GOALKEEPER = 'preparador_portero'
    ROLE_ANALYST = 'analista'
    ROLE_ADMIN = 'administrador'
    ROLE_CHOICES = [
        (ROLE_PLAYER, 'Jugador'),
        (ROLE_GUEST, 'Invitado'),
        (ROLE_TASK_STUDIO, 'Task Studio'),
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


class WorkspaceMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Administrador'),
        (ROLE_MEMBER, 'Miembro'),
        (ROLE_VIEWER, 'Lector'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    # Permisos por miembro. Si una clave está a False, el miembro no puede acceder al módulo/route_key
    # aunque esté activado a nivel de workspace. Si la clave no existe, se asume permitido.
    module_access = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['workspace__name', 'user__username']
        unique_together = ('workspace', 'user')
        verbose_name = 'Miembro workspace'
        verbose_name_plural = 'Miembros workspace'

    def __str__(self):
        return f'{self.workspace.name} · {self.user.username}'


class ServiceAccessToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_access_tokens')
    name = models.CharField(max_length=140, blank=True)
    token_prefix = models.CharField(max_length=16, db_index=True)
    token_hash = models.CharField(max_length=180)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_access_tokens',
    )
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Token de acceso de servicio'
        verbose_name_plural = 'Tokens de acceso de servicio'
        indexes = [
            models.Index(fields=['token_prefix', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    @classmethod
    def generate_token(cls):
        return secrets.token_urlsafe(32)

    @staticmethod
    def _token_prefix(raw_token: str) -> str:
        return str(raw_token or '').strip()[:16]

    @classmethod
    def create_for_user(cls, *, user, name='', workspace=None, created_by='', expires_at=None):
        raw_token = cls.generate_token()
        token = cls(
            user=user,
            name=str(name or '').strip(),
            token_prefix=cls._token_prefix(raw_token),
            token_hash=make_password(raw_token),
            workspace=workspace,
            created_by=str(created_by or '').strip(),
            expires_at=expires_at,
            is_active=True,
        )
        token.save()
        return token, raw_token

    def set_token(self, raw_token: str):
        raw_token = str(raw_token or '').strip()
        self.token_prefix = self._token_prefix(raw_token)
        self.token_hash = make_password(raw_token)

    def check_token(self, raw_token: str) -> bool:
        raw_token = str(raw_token or '').strip()
        if not raw_token or not (self.token_hash or '').strip():
            return False
        try:
            return check_password(raw_token, self.token_hash)
        except Exception:
            return False

    def is_expired(self, now=None):
        reference = now or timezone.now()
        return bool(self.expires_at and self.expires_at <= reference)

    def can_be_used(self, now=None):
        return bool(self.is_active and not self.is_expired(now=now))

    def __str__(self):
        label = self.name or self.token_prefix or f'token-{self.id}'
        return f'{self.user.username} · {label}'


class TaskStudioProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='task_studio_profile')
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_studio_profiles')
    display_name = models.CharField(max_length=140, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    license_name = models.CharField(max_length=120, blank=True)
    club_name = models.CharField(max_length=140, blank=True)
    category_label = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    document_name = models.CharField(max_length=140, blank=True)
    document_footer = models.CharField(max_length=180, blank=True)
    signature = models.CharField(max_length=140, blank=True)
    crest_image = models.ImageField(upload_to='task-studio/crests/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#0f7a35')
    secondary_color = models.CharField(max_length=7, default='#f8fafc')
    accent_color = models.CharField(max_length=7, default='#102734')
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']
        verbose_name = 'Perfil Task Studio'
        verbose_name_plural = 'Perfiles Task Studio'

    def __str__(self):
        return self.document_name or self.display_name or self.user.get_username()


class TaskStudioRosterPlayer(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_studio_roster_players')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_studio_roster')
    name = models.CharField(max_length=120)
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=60, blank=True)
    dominant_foot = models.CharField(max_length=24, blank=True)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    photo = models.ImageField(upload_to='task-studio/roster/', null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['number', 'name', 'id']
        unique_together = ('owner', 'name')
        verbose_name = 'Jugador plantilla Task Studio'
        verbose_name_plural = 'Jugadores plantilla Task Studio'

    def __str__(self):
        return f'{self.owner.username} · {self.name}'


class TaskStudioTask(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True, related_name='task_studio_tasks')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_studio_tasks')
    title = models.CharField(max_length=160)
    block = models.CharField(max_length=30, choices=SessionTask.BLOCK_CHOICES, default=SessionTask.BLOCK_MAIN_1)
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    objective = models.TextField(blank=True)
    coaching_points = models.TextField(blank=True)
    confrontation_rules = models.TextField(blank=True)
    tactical_layout = models.JSONField(default=dict, blank=True)
    task_pdf = models.FileField(upload_to='task-studio/task-pdfs/', null=True, blank=True)
    task_preview_image = models.ImageField(upload_to='task-studio/task-previews/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Soft-delete (papelera): tareas privadas restaurables.
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='deleted_task_studio_tasks')

    class Meta:
        ordering = ['-updated_at', '-id']
        verbose_name = 'Tarea Task Studio'
        verbose_name_plural = 'Tareas Task Studio'

    def __str__(self):
        return f'{self.owner.username} · {self.title}'


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


class AssistantKnowledgeDocument(models.Model):
    """
    Documentos (PDF/otros) que el club/equipo sube para enriquecer el Asistente de tareas.

    Importante:
    - Estos documentos suelen estar protegidos por copyright (UEFA, federaciones, etc.).
      Se almacenan por equipo y solo se usan como referencia interna del propio equipo.
    """

    team = models.ForeignKey('Team', on_delete=models.CASCADE, related_name='assistant_knowledge_documents')
    title = models.CharField(max_length=220)
    file = models.FileField(upload_to='assistant-knowledge/')
    sha256 = models.CharField(max_length=64, db_index=True)
    mime_type = models.CharField(max_length=80, blank=True)
    extracted_text = models.TextField(blank=True)
    extracted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['team', 'sha256'], name='uniq_assistant_knowledge_team_sha256'),
        ]

    def __str__(self):
        return f'{self.team.name} · {self.title}'

    @staticmethod
    def sha256_for_bytes(data: bytes) -> str:
        return hashlib.sha256(data or b'').hexdigest()


class AcademyMediaAsset(models.Model):
    """
    Activo multimedia para Academia (vídeo genérico, imagen, etc.).

    Puede ser:
    - archivo subido (MEDIA: S3 si USE_S3_MEDIA=true)
    - URL externa (YouTube/Vimeo/CDN)
    """

    KIND_VIDEO = 'video'
    KIND_IMAGE = 'image'
    KIND_CHOICES = [
        (KIND_VIDEO, 'Vídeo'),
        (KIND_IMAGE, 'Imagen'),
    ]

    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_VIDEO)
    title = models.CharField(max_length=180, blank=True)
    file = models.FileField(upload_to='academy/assets/', null=True, blank=True)
    source_url = models.URLField(max_length=600, blank=True, help_text='URL externa (YouTube/Vimeo/CDN) si aplica.')
    mime_type = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        label = self.title or (self.source_url[:60] if self.source_url else '') or f'Asset {self.id}'
        return f'Academy · {label}'


class AcademyLesson(models.Model):
    """
    Lección interactiva para jugadores (Baby→Senior), reusable entre clubes.
    """

    CATEGORY_BABY = 'baby'
    CATEGORY_PREBENJAMIN = 'prebenjamin'
    CATEGORY_BENJAMIN = 'benjamin'
    CATEGORY_ALEVIN = 'alevin'
    CATEGORY_INFANTIL = 'infantil'
    CATEGORY_CADETE = 'cadete'
    CATEGORY_JUVENIL = 'juvenil'
    CATEGORY_SENIOR = 'senior'
    CATEGORY_CHOICES = [
        (CATEGORY_BABY, 'Baby'),
        (CATEGORY_PREBENJAMIN, 'Prebenjamín'),
        (CATEGORY_BENJAMIN, 'Benjamín'),
        (CATEGORY_ALEVIN, 'Alevín'),
        (CATEGORY_INFANTIL, 'Infantil'),
        (CATEGORY_CADETE, 'Cadete'),
        (CATEGORY_JUVENIL, 'Juvenil'),
        (CATEGORY_SENIOR, 'Senior'),
    ]

    key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, help_text='Identificador estable (auto).')
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True)
    min_category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default=CATEGORY_BABY)
    max_category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default=CATEGORY_SENIOR)
    tags = models.JSONField(default=list, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_by = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [
            models.Index(fields=['is_published', '-updated_at']),
        ]

    def __str__(self):
        return f'Academy · {self.title}'


class AcademyLessonStep(models.Model):
    """
    Paso dentro de una lección (texto, vídeo, quiz, replay 2D/3D, reto de campo).
    """

    TYPE_TEXT = 'text'
    TYPE_VIDEO = 'video'
    TYPE_QUIZ = 'quiz'
    TYPE_REPLAY_2D = 'replay2d'
    TYPE_REPLAY_3D = 'replay3d'
    TYPE_TASK = 'task'
    TYPE_CHOICES = [
        (TYPE_TEXT, 'Texto'),
        (TYPE_VIDEO, 'Vídeo'),
        (TYPE_QUIZ, 'Quiz'),
        (TYPE_REPLAY_2D, 'Replay 2D'),
        (TYPE_REPLAY_3D, 'Replay 3D'),
        (TYPE_TASK, 'Reto de campo'),
    ]

    lesson = models.ForeignKey(AcademyLesson, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(default=0)
    step_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_TEXT)
    title = models.CharField(max_length=220, blank=True)
    body = models.TextField(blank=True)
    media = models.ForeignKey(AcademyMediaAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='steps')
    payload = models.JSONField(default=dict, blank=True, help_text='Datos extra (p.ej. JSON replay2d, config 3D, etc.).')
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ['lesson_id', 'order', 'id']
        indexes = [
            models.Index(fields=['lesson', 'order']),
        ]

    def __str__(self):
        base = self.title or self.get_step_type_display()
        return f'{self.lesson.title} · {base}'


class AcademyQuizQuestion(models.Model):
    step = models.ForeignKey(AcademyLessonStep, on_delete=models.CASCADE, related_name='quiz_questions')
    prompt = models.CharField(max_length=320)
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['step_id', 'order', 'id']
        indexes = [
            models.Index(fields=['step', 'order']),
        ]

    def __str__(self):
        return f'Quiz · {self.prompt[:60]}'


class AcademyQuizOption(models.Model):
    question = models.ForeignKey(AcademyQuizQuestion, on_delete=models.CASCADE, related_name='options')
    label = models.CharField(max_length=240)
    is_correct = models.BooleanField(default=False)
    feedback = models.CharField(max_length=320, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['question_id', 'order', 'id']
        indexes = [
            models.Index(fields=['question', 'order']),
        ]

    def __str__(self):
        return self.label


class AcademyAssignment(models.Model):
    """
    Asigna una lección a un equipo (categoría) dentro de un workspace.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='academy_assignments')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='academy_assignments')
    lesson = models.ForeignKey(AcademyLesson, on_delete=models.CASCADE, related_name='assignments')
    title_override = models.CharField(max_length=220, blank=True)
    is_required = models.BooleanField(default=True)
    due_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='academy_assignments_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['workspace', 'is_active', '-created_at']),
        ]

    def __str__(self):
        team_label = self.team.display_name if self.team else 'Todos los equipos'
        return f'{self.workspace.name} · {team_label} · {self.lesson.title}'


class AcademyProgress(models.Model):
    """
    Progreso por jugador en una lección (dentro de un workspace/club).
    """

    STATUS_NOT_STARTED = 'not_started'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, 'No iniciado'),
        (STATUS_IN_PROGRESS, 'En progreso'),
        (STATUS_COMPLETED, 'Completado'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='academy_progress_rows')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='academy_progress_rows')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='academy_progress_rows')
    lesson = models.ForeignKey(AcademyLesson, on_delete=models.CASCADE, related_name='progress_rows')
    assignment = models.ForeignKey(AcademyAssignment, on_delete=models.SET_NULL, null=True, blank=True, related_name='progress_rows')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NOT_STARTED, db_index=True)
    answers = models.JSONField(default=dict, blank=True, help_text='Registro simple de respuestas: {question_id: option_id}')
    answer_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['workspace', 'user', 'lesson'], name='uniq_academy_progress_workspace_user_lesson'),
        ]
        indexes = [
            models.Index(fields=['workspace', 'user', 'status']),
            models.Index(fields=['workspace', 'lesson', 'status']),
        ]

    def __str__(self):
        return f'{self.workspace.name} · {self.user.username} · {self.lesson.title}'


class SystemSetting(models.Model):
    """
    Ajustes globales del sistema (uso interno).

    Se usan para activar plantillas/recursos compartidos sin depender de variables de entorno.
    """

    key = models.CharField(max_length=120, unique=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return self.key
