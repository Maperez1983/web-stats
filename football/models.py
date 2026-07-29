from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.utils.text import slugify
import unicodedata
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


def normalize_team_name_key(name):
    """
    Clave canónica de un nombre de equipo, robusta a acentos, mayúsculas, puntuación y espacios,
    para detectar el MISMO equipo escrito distinto ("C.D. Rincón" == "CD Rincón" == "cd rincon").
    Solo [a-z0-9], sin espacios. Conservador: no elimina sufijos (CF/CD/UD) para no fusionar
    equipos distintos.
    """
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


class Club(models.Model):
    """
    Club real (Benagalbón, CD Rincón…), la entidad que agrupa sus EQUIPOS por categoría
    (senior, cadete, benjamín…). Un club no se duplica; cada `Team` es (club + categoría/liga).
    Distingue 'club' de 'equipo': dos equipos del mismo club en categorías distintas comparten
    Club pero son Team distintos.
    """

    name = models.CharField(max_length=150)
    name_key = models.CharField(max_length=160, blank=True, db_index=True)
    short_name = models.CharField(max_length=80, blank=True)
    external_id = models.CharField(max_length=120, blank=True)
    preferente_url = models.URLField(blank=True)
    crest_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = 'Club'
        verbose_name_plural = 'Clubes'

    def save(self, *args, **kwargs):
        self.name_key = normalize_team_name_key(self.name)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'name' in set(update_fields):
            kwargs['update_fields'] = sorted(set(update_fields) | {'name_key'})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


def resolve_or_create_club(name):
    """Devuelve el Club de `name` reutilizando el existente por name_key (o creándolo)."""
    key = normalize_team_name_key(name)
    if key:
        club = Club.objects.filter(name_key=key).first()
        if club:
            return club
    return Club.objects.create(name=str(name or '').strip()[:150] or 'Club', name_key=key)


class ClubCategory(models.Model):
    """
    Categoría (sección) dentro de un Club: Senior, Juvenil, Cadete A, Prebenjamín…

    Es la SUB-ENTIDAD del club, con id propio: agrupa los equipos de esa categoría a lo largo de
    las temporadas y sirve como destino ESTABLE (p. ej. de un traspaso) aunque no exista un `Team`
    en una liga concreta. Formaliza la jerarquía Club → Categoría → Equipo y escala mejor que
    llevar la categoría como texto suelto en cada sitio.
    """

    club = models.ForeignKey('Club', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=60)
    name_key = models.CharField(max_length=80, blank=True, db_index=True)
    order = models.PositiveSmallIntegerField(default=0, help_text='Orden por edad/nivel (0 = sin definir).')
    game_format = models.CharField(max_length=8, blank=True, help_text='F7/F11 si aplica.')
    external_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['club_id', 'order', 'name', 'id']
        unique_together = ('club', 'name_key')
        verbose_name = 'Categoría de club'
        verbose_name_plural = 'Categorías de club'

    def save(self, *args, **kwargs):
        self.name_key = normalize_team_name_key(self.name)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'name' in set(update_fields):
            kwargs['update_fields'] = sorted(set(update_fields) | {'name_key'})
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.club.name} · {self.name}'


def resolve_or_create_category(club, name):
    """Devuelve la `ClubCategory` de `name` DENTRO de `club`, reutilizando por name_key (o
    creándola). Dedup por (club, name_key): dos categorías del mismo club no se duplican, y la
    misma categoría de clubes distintos son entidades distintas."""
    if club is None:
        return None
    key = normalize_team_name_key(name)
    if not key:
        return None
    cat = ClubCategory.objects.filter(club=club, name_key=key).first()
    if cat is not None:
        return cat
    return ClubCategory.objects.create(club=club, name=str(name or '').strip()[:60], name_key=key)


class Team(models.Model):
    name = models.CharField(max_length=150)
    # Club real al que pertenece este equipo. Varios equipos por categoría comparten club.
    club = models.ForeignKey('Club', null=True, blank=True, on_delete=models.SET_NULL, related_name='teams')
    slug = models.SlugField(max_length=150, unique=True)
    short_name = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=100, blank=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')
    external_id = models.CharField(max_length=120, blank=True, help_text='Identificador oficial en la web')
    # Clave de nombre normalizada (identidad de equipo): para no duplicar el mismo equipo real
    # escrito con variaciones. Se calcula en save() (backfill en migración).
    name_key = models.CharField(max_length=160, blank=True, db_index=True)
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
    # Categoría como ENTIDAD (sub-id del club). Convive con el texto `category` durante la
    # transición; se autoenlaza en save() por (club, nombre). Additivo/nullable.
    category_ref = models.ForeignKey(
        'ClubCategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='teams',
        help_text='Categoría (sub-entidad del club) a la que pertenece este equipo.',
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

    def save(self, *args, **kwargs):
        self.name_key = normalize_team_name_key(self.name)
        # Enlaza el equipo a su Club (por name_key) si aún no lo tiene: agrupa las categorías
        # del mismo club sin fusionarlas como equipo.
        extra_fields = {'name_key'}
        if self.club_id is None:
            try:
                self.club = resolve_or_create_club(self.name)
                extra_fields.add('club')
            except Exception:
                pass
        # Autoenlaza la categoría-entidad (sub-id del club) desde el texto `category`, si falta.
        if self.category_ref_id is None and self.club_id and (self.category or '').strip():
            try:
                self.category_ref = resolve_or_create_category(self.club, self.category)
                extra_fields.add('category_ref')
            except Exception:
                pass
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'name' in set(update_fields):
            kwargs['update_fields'] = sorted(set(update_fields) | extra_fields)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


def _unique_team_slug(name):
    base = slugify(str(name or ''))[:140] or 'equipo'
    slug = base
    i = 2
    while Team.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"[:150]
        i += 1
    return slug


def resolve_or_create_team(*, name, external_id='', preferente_url='', group=None, defaults=None):
    """
    Devuelve (team, created) evitando duplicar el MISMO equipo real. Orden de identidad:
    external_id -> preferente_url -> nombre normalizado (name_key, priorizando el mismo grupo).
    Crea solo si no hay coincidencia. Reúne en un helper la lógica de dedup para todos los
    puntos de creación (importación de clasificación, rivales, etc.).
    """
    external_id = str(external_id or '').strip()
    preferente_url = str(preferente_url or '').strip()

    if external_id:
        team = Team.objects.filter(external_id=external_id).first()
        if team:
            return team, False
    if preferente_url:
        team = Team.objects.filter(preferente_url=preferente_url).first()
        if team:
            return team, False

    key = normalize_team_name_key(name)
    if key:
        # name_key SOLO desambigua dentro del mismo grupo (o cuando es único globalmente): dos
        # categorías del mismo club comparten name_key y NO deben fusionarse.
        if group is not None:
            team = Team.objects.filter(name_key=key, group=group).first()
            if team:
                return team, False
        else:
            candidates = list(Team.objects.filter(name_key=key)[:2])
            if len(candidates) == 1:
                return candidates[0], False

    values = dict(defaults or {})
    values.setdefault('external_id', external_id)
    if preferente_url:
        values.setdefault('preferente_url', preferente_url)
    if group is not None:
        values.setdefault('group', group)
    team = Team.objects.create(name=str(name or '').strip()[:150], slug=_unique_team_slug(name), **values)
    return team, True


def merge_clubs(keep, drop):
    """
    Fusiona el club `drop` dentro de `keep`: reasigna GENÉRICAMENTE todas sus relaciones inversas
    (equipos `Team.club`, destinos de traspaso `Player.transferred_to_club`, clubes de ojeo, y
    cualquier FK futuro a Club), completa en keep los campos de identidad vacíos y elimina drop.

    Un mismo club real escrito de dos formas ("Pizarra" y "C.D. Pizarra Atlético C.F.") pasa a ser
    uno solo SIN perder ninguna referencia. Reasignación por `_meta.related_objects` (no hay que
    enumerar los FKs). Operación IRREVERSIBLE: la vista/acción que la use debe confirmar antes.
    """
    from django.db import IntegrityError, transaction
    if keep is None or drop is None or keep.pk == drop.pk:
        return keep
    for rel in list(drop._meta.related_objects):
        field = rel.field
        model = rel.related_model
        for obj_pk in list(model.objects.filter(**{field.attname: drop.pk}).values_list('pk', flat=True)):
            try:
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).update(**{field.attname: keep.pk})
            except IntegrityError:
                # Ya existe el equivalente en keep -> el de drop es un duplicado: se descarta.
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).delete()
    changed = []
    for field in ('external_id', 'preferente_url', 'crest_url', 'short_name'):
        if not getattr(keep, field, '') and getattr(drop, field, ''):
            setattr(keep, field, getattr(drop, field))
            changed.append(field)
    if changed:
        keep.save(update_fields=changed + ['updated_at'])
    drop.delete()
    return keep


def _fuzzy_name_key_similar(a_key, b_key, *, min_len=5, ratio=0.82):
    """True si dos claves normalizadas se parecen lo bastante para ser el MISMO nombre escrito
    distinto — SIN ser idénticas (eso ya lo cubre name_key). Cubre dos casos:
    - abreviatura/sufijo: una contenida en la otra ('pizarra' ⊂ 'cdpizarraatleticocf').
    - erratas: alta similitud de secuencia ('torremoya' ~ 'torrremoya').
    Longitud mínima para evitar coincidencias triviales."""
    import difflib
    a_key = (a_key or '').strip()
    b_key = (b_key or '').strip()
    if not a_key or not b_key or a_key == b_key:
        return False
    short, long = (a_key, b_key) if len(a_key) <= len(b_key) else (b_key, a_key)
    if len(short) < min_len:
        return False
    if short in long:
        return True
    return difflib.SequenceMatcher(None, a_key, b_key).ratio() >= ratio


# Alias retrocompatible (antes solo hacía substring); ahora delega en el matcher genérico.
_fuzzy_club_key_match = _fuzzy_name_key_similar


def fuzzy_duplicate_clubs(club, *, limit=5):
    """Devuelve otros Club que probablemente son el MISMO club real que `club` pero escrito de
    otra forma (para reconciliar un club solo-referenciado con el que aparece en la liga)."""
    key = getattr(club, 'name_key', '') or normalize_team_name_key(getattr(club, 'name', ''))
    if not key:
        return []
    matches = []
    for other in Club.objects.exclude(pk=getattr(club, 'pk', None)).only('id', 'name', 'name_key'):
        if _fuzzy_name_key_similar(key, other.name_key):
            matches.append(other)
            if len(matches) >= limit:
                break
    return matches


def fuzzy_duplicate_teams(team, *, limit=5):
    """Otros Team del MISMO grupo con nombre PARECIDO (no exacto) — candidatos a fusionar por
    erratas/abreviaturas al importar la clasificación ('Torremoya' ~ 'Torrremoya'). Scoped al
    grupo A PROPÓSITO: dos categorías del mismo club comparten name_key y NO son duplicado."""
    key = getattr(team, 'name_key', '') or normalize_team_name_key(getattr(team, 'name', ''))
    if not key:
        return []
    qs = Team.objects.exclude(pk=getattr(team, 'pk', None))
    group_id = getattr(team, 'group_id', None)
    qs = qs.filter(group_id=group_id) if group_id is not None else qs.filter(group__isnull=True)
    matches = []
    for other in qs.only('id', 'name', 'name_key', 'group_id'):
        if _fuzzy_name_key_similar(key, other.name_key):
            matches.append(other)
            if len(matches) >= limit:
                break
    return matches


def merge_groups(keep, drop):
    """Fusiona el grupo `drop` en `keep`: reasigna GENÉRICAMENTE todas sus relaciones inversas
    (equipos, partidos, clasificaciones, contextos…) y elimina drop. Para grupos DUPLICADOS: el
    mismo grupo real escrito distinto ('Grupo 2 (2025/2026)' vs '2025-2026'). Reasigna la
    clasificación ANTES de borrar (TeamStanding tiene on_delete=CASCADE con Group). Si un objeto
    choca con una unicidad en keep, se descarta ese duplicado. IRREVERSIBLE: confirmar antes."""
    from django.db import IntegrityError, transaction
    if keep is None or drop is None or keep.pk == drop.pk:
        return keep
    for rel in list(drop._meta.related_objects):
        field = rel.field
        model = rel.related_model
        for obj_pk in list(model.objects.filter(**{field.attname: drop.pk}).values_list('pk', flat=True)):
            try:
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).update(**{field.attname: keep.pk})
            except IntegrityError:
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).delete()
    if not getattr(keep, 'external_id', '') and getattr(drop, 'external_id', ''):
        keep.external_id = drop.external_id
        keep.save(update_fields=['external_id'])
    drop.delete()
    return keep


def fuzzy_duplicate_groups(group, *, limit=5):
    """Otros Group que probablemente son el MISMO grupo real ('Grupo 2 (2025/2026)' vs
    'Grupo 2 (2025-2026)'): mismo nombre normalizado o muy parecido. Cruza temporadas A PROPÓSITO,
    porque la propia temporada puede estar duplicada."""
    key = normalize_team_name_key(getattr(group, 'name', ''))
    if not key:
        return []
    matches = []
    for other in Group.objects.exclude(pk=getattr(group, 'pk', None)).select_related('season'):
        okey = normalize_team_name_key(other.name)
        if okey == key or _fuzzy_name_key_similar(key, okey):
            matches.append(other)
            if len(matches) >= limit:
                break
    return matches


def merge_teams(keep, drop):
    """
    Fusiona el equipo `drop` dentro de `keep`: reasigna TODOS los objetos relacionados
    (jugadores, partidos, clasificaciones, memberships, vídeos…) de drop a keep y elimina drop.

    - Reasignación GENÉRICA vía las relaciones inversas de Django (no hay que enumerar 50+ FKs).
    - Si un objeto choca con una restricción de unicidad en keep (p. ej. ya existe ese jugador
      por nombre en keep), se descarta ese duplicado en lugar de romper.
    - NUNCA usa cascada para borrar datos: cuando se elimina `drop` ya no le cuelga nada.

    Devuelve `keep`. Operación IRREVERSIBLE: la vista/acción que la use debe confirmar antes.
    """
    from django.db import IntegrityError, transaction
    if keep is None or drop is None or keep.pk == drop.pk:
        return keep
    reassigned, dropped = 0, 0
    for rel in list(drop._meta.related_objects):
        field = rel.field
        model = rel.related_model
        for obj_pk in list(model.objects.filter(**{field.attname: drop.pk}).values_list('pk', flat=True)):
            try:
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).update(**{field.attname: keep.pk})
                reassigned += 1
            except IntegrityError:
                # Ya existe el equivalente en keep -> el de drop es un duplicado: se descarta.
                with transaction.atomic():
                    model.objects.filter(pk=obj_pk).delete()
                dropped += 1
    # Completa en keep los campos de identidad que tenga vacíos.
    changed = []
    for f in ('external_id', 'preferente_url', 'crest_url', 'short_name'):
        if not getattr(keep, f, '') and getattr(drop, f, ''):
            setattr(keep, f, getattr(drop, f))
            changed.append(f)
    if changed:
        keep.save(update_fields=changed)
    if getattr(keep, 'club_id', None) is None and getattr(drop, 'club_id', None):
        keep.club_id = drop.club_id
        keep.save(update_fields=['club'])
    drop.delete()
    return keep


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


class PlayerIdentity(models.Model):
    """
    Identidad GLOBAL de una persona-jugador, independiente de equipo, club (workspace),
    temporada o liga.

    Varias fichas `Player` (una por equipo/temporada/club) pueden apuntar a la MISMA
    persona: así, cuando un jugador cambia de equipo, de club o de liga, no se duplica su
    identidad — se reutiliza esta entidad y se conserva su historia.

    Claves de identidad (de más a menos fuerte): URL de perfil externo (La Preferente /
    Transfermarkt / BeSoccer), y nombre + fecha de nacimiento.
    """

    full_name = models.CharField(max_length=180)
    display_name = models.CharField(max_length=120, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    preferente_profile_url = models.URLField(max_length=300, blank=True, db_index=True)
    transfermarkt_url = models.URLField(max_length=300, blank=True, db_index=True)
    besoccer_url = models.URLField(max_length=300, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name', 'id']
        verbose_name = 'Identidad de jugador'
        verbose_name_plural = 'Identidades de jugador'

    def __str__(self):
        return self.display_name or self.full_name or f'Identidad #{self.pk}'


def _norm_identity_name(value):
    return " ".join(str(value or "").strip().lower().split())


def find_existing_player_identity(player, *, exclude_id=None):
    """
    Busca (SIN crear) la PlayerIdentity existente que corresponde a `player` por clave FUERTE:
    misma URL de perfil no vacía, o mismo nombre + misma fecha de nacimiento. None si no hay.
    """
    urls = [
        str(getattr(player, "preferente_profile_url", "") or "").strip(),
        str(getattr(player, "transfermarkt_url", "") or "").strip(),
        str(getattr(player, "besoccer_url", "") or "").strip(),
    ]
    urls = [u for u in urls if u]

    for url in urls:
        qs = PlayerIdentity.objects.filter(
            models.Q(preferente_profile_url=url)
            | models.Q(transfermarkt_url=url)
            | models.Q(besoccer_url=url)
        )
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        match = qs.first()
        if match:
            return match

    norm_name = _norm_identity_name(getattr(player, "full_name", "") or getattr(player, "name", ""))
    dob = getattr(player, "birth_date", None)
    if norm_name and dob is not None:
        qs = PlayerIdentity.objects.filter(birth_date=dob)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        for cand in qs.only("id", "full_name", "display_name"):
            if _norm_identity_name(cand.full_name) == norm_name or _norm_identity_name(cand.display_name) == norm_name:
                return cand
    return None


def resolve_or_create_player_identity(player):
    """
    Igual que find_existing_player_identity pero crea la identidad si no existe. Versión en
    tiempo de ejecución del backfill 0163: crear/importar un jugador no duplica la persona.
    No enlaza al player (eso lo hace Player.save()).
    """
    existing = find_existing_player_identity(player)
    if existing is not None:
        return existing
    dob = getattr(player, "birth_date", None)
    return PlayerIdentity.objects.create(
        full_name=str(getattr(player, "full_name", "") or getattr(player, "name", "") or "")[:180],
        display_name=str(getattr(player, "name", "") or "")[:120],
        birth_date=dob,
        preferente_profile_url=str(getattr(player, "preferente_profile_url", "") or "")[:300],
        transfermarkt_url=str(getattr(player, "transfermarkt_url", "") or "")[:300],
        besoccer_url=str(getattr(player, "besoccer_url", "") or "")[:300],
    )


def relink_player_identity(player):
    """
    Re-evalúa la identidad de un jugador YA existente (p. ej. tras añadirle una URL de perfil o
    la fecha de nacimiento). Si ahora coincide con OTRA identidad existente (misma persona), lo
    reenlaza y elimina la identidad anterior si queda huérfana. Devuelve True si cambió.
    """
    match = find_existing_player_identity(player, exclude_id=getattr(player, "identity_id", None))
    if match is None or match.id == getattr(player, "identity_id", None):
        return False
    old_id = getattr(player, "identity_id", None)
    Player.objects.filter(pk=player.pk).update(identity=match)
    player.identity_id = match.id
    if old_id and not Player.objects.filter(identity_id=old_id).exists():
        PlayerIdentity.objects.filter(pk=old_id).delete()
    return True


def merge_player_identities(keep, drop):
    """
    Fusiona la identidad `drop` en `keep`: reasigna todas las fichas Player de `drop` a `keep`,
    completa en `keep` los campos que tenga vacíos, y elimina `drop`. Seguro: la identidad tiene
    pocos dependientes (solo el FK identity de Player). No toca las fichas Player en sí.
    """
    if keep is None or drop is None or keep.id == drop.id:
        return keep
    Player.objects.filter(identity_id=drop.id).update(identity=keep)
    changed = []
    for field in ("full_name", "display_name", "preferente_profile_url", "transfermarkt_url", "besoccer_url"):
        if not getattr(keep, field, "") and getattr(drop, field, ""):
            setattr(keep, field, getattr(drop, field))
            changed.append(field)
    if keep.birth_date is None and drop.birth_date is not None:
        keep.birth_date = drop.birth_date
        changed.append("birth_date")
    if changed:
        keep.save(update_fields=changed + ["updated_at"])
    drop.delete()
    return keep


class Player(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    # Identidad global de persona: agrupa las fichas del MISMO jugador a través de equipos,
    # clubes y ligas para no duplicar su entidad. Nullable/aditivo (backfill en migración).
    identity = models.ForeignKey(
        'PlayerIdentity',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='player_records',
    )
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
    preferente_profile_url = models.URLField(max_length=300, blank=True, help_text='URL del perfil del jugador en La Preferente (para autoactualizar stats).')
    transfermarkt_url = models.URLField(max_length=300, blank=True, help_text='URL del perfil en Transfermarkt.')
    besoccer_url = models.URLField(max_length=300, blank=True, help_text='URL del perfil en BeSoccer.')
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
    # Personalización de avatar (estilo FM): grado de piel 1-6 y color de pelo (hex). El avatar se
    # recolorea en la app sobre la figura base usando las máscaras de piel/pelo.
    skin_grade = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Grado de piel 1 (muy clara) a 6 (muy oscura) para el avatar.')
    hair_color = models.CharField(max_length=16, blank=True, help_text='Color de pelo del avatar en hex (ej. #4a2d1a).')
    HAIRSTYLE_CHOICES = [('corto', 'Corto'), ('medio', 'Medio'), ('rizado', 'Rizado'), ('largo', 'Largo'), ('rapado', 'Rapado')]
    hairstyle = models.CharField(max_length=16, blank=True, choices=HAIRSTYLE_CHOICES, help_text='Forma del peinado del avatar (corto/medio/rizado).')
    # Avatar final generado OFFLINE (face-swap con la foto + peinado + color + altura). Se cachea como
    # imagen y avatar_source_key guarda el hash de las entradas para regenerar solo si cambian.
    avatar_generated = models.ImageField(upload_to='player-avatars/', null=True, blank=True, help_text='Avatar generado (face-swap) cacheado; lo produce el comando generate_player_avatars.')
    avatar_source_key = models.CharField(max_length=64, blank=True, help_text='Hash de las entradas del avatar generado (foto+peinado+color+piel+altura).')
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
    federation_license_number = models.CharField(max_length=80, blank=True, help_text='Nº licencia federativa (opcional).')
    federation_license_expires_at = models.DateField(null=True, blank=True, help_text='Caducidad de la licencia federativa (para avisos de renovación).')
    license_updated_at = models.DateTimeField(null=True, blank=True)
    # Ficha administrativa / dirección deportiva.
    contract_start = models.DateField(null=True, blank=True, help_text='Inicio de contrato/vinculación.')
    contract_end = models.DateField(null=True, blank=True, help_text='Fin de contrato (para avisos de renovación).')
    release_clause = models.CharField(max_length=80, blank=True, help_text='Cláusula de rescisión (texto libre, ej. "50.000 €").')
    contract_notes = models.CharField(max_length=200, blank=True, help_text='Notas de contrato/ficha (salario, bonus, vinculación…).')
    is_active = models.BooleanField(default=True)
    has_federative_license = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Tiene ficha federativa (licencia oficial de la temporada).',
    )
    # Traspaso: cuando el jugador SALE de la plantilla porque ficha por otro club, se registra el
    # club destino (del catálogo Club, sin duplicar) y la fecha. La ficha y su identidad de persona
    # (PlayerIdentity) se conservan intactas; solo se pone is_active=False. Nullable/aditivo.
    transferred_to_club = models.ForeignKey(
        'Club',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='incoming_transfers',
        help_text='Club por el que fichó el jugador al salir de la plantilla.',
    )
    transferred_at = models.DateField(
        null=True, blank=True, help_text='Fecha en que fichó por otro club (salida de la plantilla).'
    )
    # Categoría/equipo destino DENTRO del club (Senior, Juvenil, Cadete…). Un club agrupa varias
    # categorías: sin esto, "fichó por Rincón" se confundiría con la única categoría que tengamos
    # de ese club. Texto libre porque el equipo destino puede no existir en nuestro sistema.
    transferred_to_category = models.CharField(
        max_length=60, blank=True, help_text='Categoría/equipo dentro del club destino (ej. Senior, Cadete).'
    )
    # Destino del traspaso como ENTIDAD: la categoría (sub-id del club), estable aunque no exista
    # su equipo en ninguna liga. Convive con el texto durante la transición; se rellena en el
    # handler vía resolve_or_create_category(club, categoría).
    transferred_to_category_ref = models.ForeignKey(
        'ClubCategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='incoming_transfers',
        help_text='Categoría destino (sub-entidad del club) del traspaso.',
    )
    # Control de caché de foto (para busting sin depender de caches por proceso).
    photo_updated_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('team', 'name')

    def __str__(self):
        return f'{self.name} ({self.team.name})'

    @property
    def age(self):
        """Edad en años a partir de la fecha de nacimiento (None si no hay)."""
        if not self.birth_date:
            return None
        today = timezone.localdate()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    def save(self, *args, **kwargs):
        changed_fields = normalize_player_record(self)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            merged = set(update_fields)
            merged.update(changed_fields)
            kwargs['update_fields'] = sorted(merged)
        super().save(*args, **kwargs)
        # Identidad global de persona (Fase 2): si el jugador aún no tiene identidad, se
        # resuelve/crea reutilizando una existente cuando coincide una clave fuerte -> crear o
        # importar un jugador ya no duplica la persona. Guard por identity_id para no repetir
        # trabajo ni recursar; se escribe con UPDATE directo (no dispara save() de nuevo).
        if getattr(self, "identity_id", None) is None:
            try:
                identity = resolve_or_create_player_identity(self)
                if identity is not None and self.identity_id != identity.id:
                    Player.objects.filter(pk=self.pk).update(identity=identity)
                    self.identity_id = identity.id
            except Exception:
                pass


class PlayerAsset(models.Model):
    """Repositorio de recursos visuales por jugador (por ID). Una fila = UN recurso (avatar por
    equipación, chapa, foto o estado). Permite que un jugador tenga su set completo (titular,
    visitante, entreno, portero, chándal, lesionado) además del avatar principal (Player.avatar_generated).

    Los avatares con cara se generan offline (face-swap en Mac) y se suben aquí; las superficies
    (pizarra, 11, tareas) resuelven el recurso según la presentación elegida por el entrenador."""

    KIND_KIT_TITULAR = "kit_titular"
    KIND_KIT_VISITANTE = "kit_visitante"
    KIND_KIT_TURQUESA = "kit_turquesa"
    KIND_KIT_BLANCA = "kit_blanca"
    KIND_CHANDAL = "chandal"
    KIND_LESIONADO = "lesionado"
    KIND_GK_AZUL = "gk_azul"
    KIND_GK_NEGRA = "gk_negra"
    KIND_GK_MAGENTA = "gk_magenta"
    KIND_CHAPA_LOCAL = "chapa_local"
    KIND_CHAPA_AWAY = "chapa_away"
    KIND_CHAPA_GK = "chapa_gk"
    KIND_FOTO = "foto"

    KIND_CHOICES = [
        (KIND_KIT_TITULAR, "Avatar equipación titular"),
        (KIND_KIT_VISITANTE, "Avatar equipación visitante"),
        (KIND_KIT_TURQUESA, "Avatar entreno turquesa"),
        (KIND_KIT_BLANCA, "Avatar entreno blanca"),
        (KIND_CHANDAL, "Avatar chándal"),
        (KIND_LESIONADO, "Avatar lesionado"),
        (KIND_GK_AZUL, "Avatar portero azul"),
        (KIND_GK_NEGRA, "Avatar portero negra"),
        (KIND_GK_MAGENTA, "Avatar portero magenta"),
        (KIND_CHAPA_LOCAL, "Chapa local"),
        (KIND_CHAPA_AWAY, "Chapa visitante"),
        (KIND_CHAPA_GK, "Chapa portero"),
        (KIND_FOTO, "Foto"),
    ]

    player = models.ForeignKey("Player", on_delete=models.CASCADE, related_name="assets")
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    image = models.ImageField(upload_to="player-assets/", null=True, blank=True)
    source_key = models.CharField(
        max_length=64, blank=True,
        help_text="Hash de las entradas (foto+kit+características) para regenerar solo si cambian.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("player", "kind")]
        indexes = [models.Index(fields=["player", "kind"])]

    def __str__(self):
        return f"{self.player_id}:{self.kind}"


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
    rpe = models.PositiveSmallIntegerField(null=True, blank=True, help_text='RPE de la sesión 1-10')
    wellness = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Bienestar global 1-10')
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    session_minutes = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Duración de sesión/partido en minutos.')
    # Wellness por dimensiones (además del `wellness` global heredado).
    wellness_sleep = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Sueño/descanso 1-10.')
    wellness_fatigue = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Fatiga percibida 1-10.')
    wellness_soreness = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Dolor muscular 1-10.')
    wellness_stress = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Estrés percibido 1-10.')
    wellness_motivation = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Motivación 1-10.')
    # Tests físicos (unificados aquí: antes vivían enterrados en PlayerEvaluation).
    yo_yo_ir1_m = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Yo-Yo IR1 en metros.')
    sprint_5m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sprint_10m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sprint_20m_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    agility_505_s = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cmj_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Salto CMJ en cm.')
    copenhagen_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    # Madurez / PHV (antes solo en la evaluación, sin visualizar).
    MATURATION_CHOICES = [
        ('', 'Sin definir'),
        ('pre_phv', 'Pre-PHV'),
        ('circa_phv', 'Circa-PHV'),
        ('post_phv', 'Post-PHV'),
    ]
    maturation_status = models.CharField(max_length=16, choices=MATURATION_CHOICES, blank=True, default='')
    maturity_offset_years = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text='Años respecto al PHV.')
    growth_velocity_cm_year = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Velocidad de crecimiento cm/año.')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def srpe_load(self):
        """Carga sRPE = RPE × minutos (au). None si falta algún dato."""
        if self.rpe is None or self.session_minutes is None:
            return None
        return int(self.rpe) * int(self.session_minutes)

    class Meta:
        ordering = ['-recorded_on', '-id']

    def __str__(self):
        return f'{self.player.name} · métrica {self.recorded_on:%d/%m/%Y}'


class PlayerObjective(models.Model):
    """Objetivo de trabajo del jugador con seguimiento de estado. Antes `objectives_next` era un
    texto enterrado en el histórico de evaluaciones; ahora es una lista accionable."""

    STATUS_PENDING = 'pending'
    STATUS_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_PROGRESS, 'En curso'),
        (STATUS_DONE, 'Cumplido'),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='objectives')
    text = models.CharField(max_length=240)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    target_date = models.DateField(null=True, blank=True, help_text='Fecha objetivo (opcional).')
    created_at = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(null=True, blank=True)
    created_by = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['status', 'target_date', '-created_at', '-id']
        verbose_name = 'Objetivo de jugador'
        verbose_name_plural = 'Objetivos de jugador'

    def __str__(self):
        return f'{self.player.name} · {self.get_status_display()} · {self.text[:40]}'


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
    STATUS_SIGNED_OTHER = 'signed_other'
    STATUS_CHOICES = [
        (STATUS_TARGET, 'Objetivo'),
        (STATUS_WATCHLIST, 'En seguimiento'),
        (STATUS_ACTIVE, 'Seguimiento activo'),
        (STATUS_REVIEW, 'Revisar'),
        (STATUS_DISCARDED, 'Descartado'),
        (STATUS_SIGNED, 'Fichado'),
        (STATUS_SIGNED_OTHER, 'Fichado por otro equipo'),
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

    DISCARD_COACH = 'coach'
    DISCARD_SIGNED_OTHER = 'signed_other'
    DISCARD_LEVEL = 'level'
    DISCARD_ECONOMIC = 'economic'
    DISCARD_AGE = 'age'
    DISCARD_PHYSICAL = 'physical'
    DISCARD_ATTITUDE = 'attitude'
    DISCARD_OTHER = 'other'
    DISCARD_REASON_CHOICES = [
        (DISCARD_COACH, 'Descartado por el entrenador'),
        (DISCARD_SIGNED_OTHER, 'Fichó por otro club'),
        (DISCARD_LEVEL, 'Nivel insuficiente'),
        (DISCARD_ECONOMIC, 'Motivo económico'),
        (DISCARD_AGE, 'Edad'),
        (DISCARD_PHYSICAL, 'Lesión / condición física'),
        (DISCARD_ATTITUDE, 'Actitud / comportamiento'),
        (DISCARD_OTHER, 'Otro'),
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
    discard_reason = models.CharField(max_length=24, choices=DISCARD_REASON_CHOICES, blank=True, default='', db_index=True)
    discard_club = models.CharField(max_length=160, blank=True, help_text='Club que lo fichó, si el motivo es que fichó por otro.')
    # Identidad de club para el ojeo: mismo catálogo `Club` que la plantilla, para poder reconciliar
    # con los clubes reales de la liga (y no perder el vínculo si el club aparece luego por scraping).
    # Se autopueblan desde subject_team_name / discard_club en save().
    subject_club = models.ForeignKey(
        'Club', null=True, blank=True, on_delete=models.SET_NULL, related_name='scouting_current',
        help_text='Club actual del ojeado, enlazado al catálogo (autollenado desde el texto).',
    )
    signed_club = models.ForeignKey(
        'Club', null=True, blank=True, on_delete=models.SET_NULL, related_name='scouting_signed',
        help_text='Club que fichó al ojeado, si el descarte es "fichó por otro" (autollenado).',
    )
    discard_permanent = models.BooleanField(default=False, help_text='Descarte definitivo: no volver a por él.')
    phone = models.CharField(max_length=40, blank=True)
    has_agent = models.BooleanField(default=False)
    agent_name = models.CharField(max_length=160, blank=True)
    agent_phone = models.CharField(max_length=40, blank=True)
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
        status_will_persist = True
        if update_fields is not None:
            merged = set(update_fields)
            merged.update(changed_fields)
            kwargs['update_fields'] = sorted(merged)
            status_will_persist = 'status' in merged
        old_status = None
        if self.pk is not None and status_will_persist:
            old_status = (
                type(self).objects.filter(pk=self.pk).values_list('status', flat=True).first()
            )
        super().save(*args, **kwargs)
        if status_will_persist:
            self._sync_linked_player_active(old_status)
        # Auto-enlace al catálogo de clubes (identidad de club) para poder reconciliar el ojeo con
        # los clubes reales de la liga. No pisa un FK ya asignado a mano; se escribe con UPDATE
        # directo para no re-disparar save().
        club_updates = {}
        if self.subject_club_id is None and (self.subject_team_name or '').strip():
            try:
                club_updates['subject_club'] = resolve_or_create_club(self.subject_team_name)
            except Exception:
                pass
        if self.signed_club_id is None and (self.discard_club or '').strip():
            try:
                club_updates['signed_club'] = resolve_or_create_club(self.discard_club)
            except Exception:
                pass
        if club_updates:
            type(self).objects.filter(pk=self.pk).update(**club_updates)
            for key, val in club_updates.items():
                setattr(self, key, val)

    def _sync_linked_player_active(self, old_status):
        """Sincroniza la ficha (Player) enlazada con el estado del ojeo.

        Al DESCARTAR un ojeado, su jugador enlazado se desactiva (is_active=False) para que
        desaparezca de la home, la pizarra interactiva y la convocatoria. Al sacarlo de
        'descartado' (volver a 'a prueba' / seguir / fichar), se reactiva. Reversible y
        silencioso ante cualquier error (nunca debe romper el guardado del ojeo).
        """
        try:
            player = self.player
        except Exception:
            player = None
        if player is None:
            return
        now_discarded = self.status == self.STATUS_DISCARDED
        was_discarded = old_status == self.STATUS_DISCARDED
        try:
            if now_discarded and not was_discarded and player.is_active:
                player.is_active = False
                player.save(update_fields=['is_active'])
            elif was_discarded and not now_discarded and not player.is_active:
                player.is_active = True
                player.save(update_fields=['is_active'])
        except Exception:
            pass


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


class RivalPlayer(models.Model):
    """Jugador de un equipo RIVAL, importado de una fuente externa (laPreferente) para análisis.

    AISLADO a propósito: NO es un Player. Nunca entra en tu plantilla, home, convocatoria, asistencia
    ni dashboards; solo alimenta el 11 rival, el briefing y el scouting. La clave de identidad estable
    es `source_player_id` (el J-id de laPreferente, el MISMO entre equipos): permite refrescar sin
    duplicar y detectar que un rival es una persona ya conocida (ex-jugador propio u ojeado que ha
    fichado por un rival) sin fusionarla — se enlaza en `matched_player` a modo de "reconocido como".
    """

    SOURCE_LAPREFERENTE = 'lapreferente'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='rival_players')
    source = models.CharField(max_length=20, default=SOURCE_LAPREFERENTE)
    source_player_id = models.CharField(max_length=24, blank=True, default='', db_index=True)
    preferente_profile_url = models.CharField(max_length=300, blank=True, default='')

    full_name = models.CharField(max_length=140)
    alias = models.CharField(max_length=80, blank=True, default='')
    number = models.PositiveIntegerField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    photo_url = models.CharField(max_length=300, blank=True, default='')
    position = models.CharField(max_length=60, blank=True, default='')  # texto crudo de la fuente
    line = models.CharField(max_length=8, blank=True, default='')       # gk/def/mid/att (mapeado)

    matches_played = models.PositiveIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    goals = models.PositiveIntegerField(default=0)
    yellow_cards = models.PositiveIntegerField(default=0)
    red_cards = models.PositiveIntegerField(default=0)
    season_label = models.CharField(max_length=20, blank=True, default='')

    # "Reconocido como" (Nivel 1): si al importar coincide (por J-id o nombre) con alguien ya en el
    # sistema (ex-jugador propio, u ojeado enlazado a un Player que ha fichado por un rival), se enlaza
    # SIN duplicar ni fusionar. Base para las herramientas de ficha (marcar objetivo / Dirección).
    matched_player = models.ForeignKey(
        'Player', on_delete=models.SET_NULL, null=True, blank=True, related_name='rival_appearances'
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['line', 'number', 'full_name']
        indexes = [
            models.Index(fields=['team', 'is_active'], name='rivalplayer_team_active_idx'),
            models.Index(fields=['source', 'source_player_id'], name='rivalplayer_source_idx'),
        ]
        verbose_name = 'Jugador rival'
        verbose_name_plural = 'Jugadores rival'

    def __str__(self):
        return f'{self.full_name} ({self.team_id})'


class MatchLineup(models.Model):
    """Alineación (11 inicial + banquillo) de NUESTRO equipo para un partido concreto.

    Fuente de verdad propia, independiente del ciclo de vida de `ConvocationRecord`
    (is_current / match SET_NULL). Se escribe en paralelo a `ConvocationRecord.lineup_data`
    (compatibilidad hacia atrás) y se lee con preferencia sobre ella. `match` es CASCADE, así que
    la alineación no queda huérfana. `lineup_data` = dict {starters:[], bench:[], _meta:{}}.
    """

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='match_lineups')
    match = models.ForeignKey('Match', on_delete=models.CASCADE, related_name='team_lineups')
    lineup_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'match')
        ordering = ['-updated_at', '-id']
        indexes = [models.Index(fields=['team', 'match'], name='matchlineup_team_match_idx')]

    def __str__(self):
        return f'Alineación equipo {self.team_id} · partido {self.match_id}'


class Match(models.Model):
    CONTEXT_LEAGUE = 'league'
    CONTEXT_TOURNAMENT = 'tournament'
    CONTEXT_FRIENDLY = 'friendly'
    CONTEXT_CHOICES = [
        (CONTEXT_LEAGUE, 'Liga'),
        (CONTEXT_TOURNAMENT, 'Torneo'),
        (CONTEXT_FRIENDLY, 'Amistoso'),
    ]

    # Fuente ÚNICA de datos del partido: evita el doble conteo entre el registro en vivo y la
    # edición manual de la ficha. El agregador de estadísticas cuenta solo la fuente declarada.
    STATS_SOURCE_NONE = ''
    STATS_SOURCE_LIVE = 'live'          # Modo Partido (registro de acciones en vivo)
    STATS_SOURCE_MANUAL = 'manual'      # Edición manual desde la ficha del partido
    STATS_SOURCE_RESULT = 'result_only'  # Solo marcador (sin estadísticas de jugador)
    STATS_SOURCE_CHOICES = [
        (STATS_SOURCE_NONE, 'Sin datos'),
        (STATS_SOURCE_LIVE, 'En vivo'),
        (STATS_SOURCE_MANUAL, 'Manual'),
        (STATS_SOURCE_RESULT, 'Solo resultado'),
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
    stats_source = models.CharField(
        max_length=16,
        blank=True,
        default=STATS_SOURCE_NONE,
        choices=STATS_SOURCE_CHOICES,
        help_text='Fuente única de datos del partido (evita doble conteo): en vivo, manual, solo resultado o sin datos.',
    )
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


class ExternalSeasonStat(models.Model):
    """Estadisticas por temporada raspadas de una fuente externa (La Preferente,
    etc.). NO pisa las stats propias; es un historico de referencia que alimenta
    la pestana de historico de la ficha, tanto para jugadores de plantilla como
    para ojeados."""
    SOURCE_PREFERENTE = 'lapreferente'
    SOURCE_CHOICES = [(SOURCE_PREFERENTE, 'La Preferente')]

    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='external_season_stats', null=True, blank=True)
    scouting_target = models.ForeignKey('ScoutingTarget', on_delete=models.CASCADE, related_name='external_season_stats', null=True, blank=True)
    source = models.CharField(max_length=24, choices=SOURCE_CHOICES, default=SOURCE_PREFERENTE, db_index=True)
    season_label = models.CharField(max_length=16, db_index=True)
    team_name = models.CharField(max_length=160, blank=True)
    competition = models.CharField(max_length=160, blank=True)
    external_name = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=60, blank=True)
    matches = models.PositiveIntegerField(default=0)
    starts = models.PositiveIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    goals = models.PositiveIntegerField(default=0)
    goals_conceded = models.IntegerField(null=True, blank=True)
    yellow_cards = models.PositiveIntegerField(default=0)
    red_cards = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['player', 'source', 'season_label'], name='extstat_player_idx'),
            models.Index(fields=['scouting_target', 'source', 'season_label'], name='extstat_target_idx'),
        ]
        ordering = ['-season_label']
        verbose_name = 'Estadistica externa por temporada'
        verbose_name_plural = 'Estadisticas externas por temporada'

    def __str__(self):
        who = self.player or self.scouting_target or self.external_name
        return f'{who} · {self.season_label} · {self.get_source_display()}'


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
    # Tipo canónico de la acción (taxonomía tipada). Se rellena al registrar y para el histórico
    # por backfill. Fuente estable de clasificación (event_taxonomy.event_kind lo prefiere).
    kind = models.CharField(max_length=24, blank=True, default='', db_index=True)
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
    # Plantilla de sesión reutilizable (Biblioteca de sesiones). Vive en un microciclo-biblioteca
    # y se instancia en microciclos reales. No es una sesión "real" de una semana concreta.
    is_session_template = models.BooleanField(default=False, db_index=True)
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


class SessionTaskParticipation(models.Model):
    """Qué jugador participó en qué tarea de una sesión (Fase 5). La PRESENCIA de la fila = participó.
    Los minutos de la tarea = `SessionTask.duration_minutes`; los minutos de entreno de un jugador
    se agregan sumando la duración de las tareas en las que participó (Fase 6). Uno por (tarea, jugador)."""

    session_task = models.ForeignKey('SessionTask', on_delete=models.CASCADE, related_name='participations')
    player = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='task_participations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('session_task', 'player')
        indexes = [
            models.Index(fields=['player']),
            models.Index(fields=['session_task']),
        ]

    def __str__(self):
        return f'{self.session_task_id} · {self.player_id}'


class SessionTaskManager(models.Manager):
    """Perf: difiere por defecto los blobs base64 (preview 2D / portada IA) para que NINGUN
    listado/consulta los detoaste (pesan cientos de KB). Solo los 2 endpoints que sirven la
    imagen los necesitan, y acceden al campo por carga perezosa (o .undefer())."""

    def get_queryset(self):
        return super().get_queryset().defer('preview_data_b64', 'cover_data_b64')


class SessionTask(models.Model):
    BLOCK_ACTIVATION = 'activation'
    BLOCK_PHYSICAL_PREP = 'physical_prep'
    BLOCK_MAIN_1 = 'main_1'
    BLOCK_MAIN_2 = 'main_2'
    BLOCK_SET_PIECES = 'set_pieces'
    BLOCK_CONDITIONING = 'conditioning'
    BLOCK_RECOVERY = 'recovery'
    BLOCK_VIDEO = 'video'
    # Orden pedagógico (2026-07-28): Activación (previo: estiramientos/movilidad) · Preparación
    # física · Condicionante · Principal 1 · Principal 2 · ABP · Vuelta a la calma · Vídeo.
    BLOCK_CHOICES = [
        (BLOCK_ACTIVATION, 'Activación'),
        (BLOCK_PHYSICAL_PREP, 'Preparación física'),
        (BLOCK_CONDITIONING, 'Condicionante'),
        (BLOCK_MAIN_1, 'Principal 1'),
        (BLOCK_MAIN_2, 'Principal 2'),
        (BLOCK_SET_PIECES, 'ABP'),
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
    # --- Fase 2 · Modelo teórico: proyección QUERYABLE de la metodología ---
    # Se derivan automáticamente de tactical_layout['meta'] en save() (fuente única:
    # task_choices.derive_task_columns). El JSON sigue siendo la fuente de verdad; estas
    # columnas son un índice para poder filtrar/buscar (biblioteca de tareas).
    game_moment = models.CharField(max_length=40, blank=True, default='', db_index=True,
                                   help_text='Momento del juego (derivado del JSON)')
    principle = models.CharField(max_length=160, blank=True, default='')
    subprinciple = models.CharField(max_length=200, blank=True, default='')
    structure_periodization = models.CharField(max_length=40, blank=True, default='', db_index=True,
                                               help_text='Estructura (periodización táctica)')
    game_situation = models.CharField(max_length=40, blank=True, default='')
    content_domain = models.CharField(max_length=30, blank=True, default='', db_index=True,
                                      help_text='Contenido dominante: táctico/técnico/físico/psicológico')
    age_group = models.CharField(max_length=80, blank=True, default='', db_index=True)
    tactical_layout = models.JSONField(default=dict, blank=True)
    # Perf: los blobs base64 (preview 2D y portada IA) se guardan FUERA de tactical_layout,
    # en columnas dedicadas que se DIFIEREN en los listados de biblioteca (así la lista no
    # lee/parsea cientos de KB por tarea). save() los reubica solo desde meta; los lectores
    # usan preview_embedded_url()/cover_embedded_url() (campo primero, meta de reserva).
    preview_data_b64 = models.TextField(blank=True, default='')
    cover_data_b64 = models.TextField(blank=True, default='')
    cover_present = models.BooleanField(default=False, db_index=True,
                                        help_text='Flag barato para listados: hay portada IA embebida')
    # Perf: copia LIGERA de tactical_layout SIN el canvas pesado (tokens/graphic_editor/
    # original_version/timeline), que pesa ~165KB/tarea. Listados y presentacion solo necesitan
    # `meta` -> leen esta columna y DIFIEREN tactical_layout. El editor 2D usa el completo.
    task_layout_light = models.JSONField(default=dict, blank=True)
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

    objects = SessionTaskManager()

    def _embedded_from_meta(self, key):
        layout = self.tactical_layout if isinstance(self.tactical_layout, dict) else {}
        meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else {}
        return str((meta or {}).get(key) or '').strip()

    def preview_embedded_url(self):
        """Data-URL de la preview 2D: campo dedicado primero, meta de reserva (retrocompat)."""
        return (self.preview_data_b64 or '').strip() or self._embedded_from_meta('preview_data_embedded_v1')

    def cover_embedded_url(self):
        """Data-URL de la portada IA: campo dedicado primero, meta de reserva (retrocompat)."""
        return (self.cover_data_b64 or '').strip() or self._embedded_from_meta('cover_image_embedded_v1')

    def save(self, *args, **kwargs):
        if not self.club_season_id:
            try:
                self.club_season_id = getattr(self.session, 'club_season_id', None)
            except Exception:
                self.club_season_id = None
        # Fase 2: mantiene las columnas de metodología en sync con el JSON en cada guardado.
        # Cubre TODOS los sitios de guardado (create/update/clone) sin tocar views.py.
        try:
            from .task_choices import derive_task_columns
            for _k, _v in derive_task_columns(self.tactical_layout).items():
                setattr(self, _k, _v)
        except Exception:
            pass
        # Perf: saca los blobs base64 de tactical_layout.meta a columnas dedicadas. Centralizado
        # aquí para cubrir TODOS los sitios de guardado sin tocarlos. Mantiene update_fields.
        try:
            _moved = []
            layout = self.tactical_layout if isinstance(self.tactical_layout, dict) else None
            if isinstance(layout, dict):
                meta = layout.get('meta') if isinstance(layout.get('meta'), dict) else None
                if isinstance(meta, dict):
                    _pv = meta.pop('preview_data_embedded_v1', None)
                    if isinstance(_pv, str) and _pv.strip():
                        self.preview_data_b64 = _pv
                        _moved.append('preview_data_b64')
                    _cv = meta.pop('cover_image_embedded_v1', None)
                    if isinstance(_cv, str) and _cv.strip():
                        self.cover_data_b64 = _cv
                        _moved.append('cover_data_b64')
                    _ov = meta.get('original_version')
                    if isinstance(_ov, dict):
                        _ov.pop('preview_data_embedded_v1', None)
                        _ov.pop('cover_image_embedded_v1', None)
            _flag = bool((self.cover_data_b64 or '').strip())
            if _flag != bool(self.cover_present):
                self.cover_present = _flag
                _moved.append('cover_present')
            _uf = kwargs.get('update_fields')
            if _uf is not None and _moved:
                kwargs['update_fields'] = list(set(_uf) | set(_moved) | {'tactical_layout'})
        except Exception:
            pass
        # Perf: mantiene task_layout_light = tactical_layout SIN el canvas pesado, para que
        # listados/presentacion (que solo necesitan meta) no detoasten ~165KB por tarea.
        try:
            _lay = self.tactical_layout if isinstance(self.tactical_layout, dict) else None
            if isinstance(_lay, dict):
                _light = {k: v for k, v in _lay.items() if k not in ('tokens', 'timeline')}
                _m = _light.get('meta')
                if isinstance(_m, dict):
                    _light['meta'] = {k: v for k, v in _m.items() if k not in ('graphic_editor', 'original_version')}
                self.task_layout_light = _light
            else:
                self.task_layout_light = {}
            _uf2 = kwargs.get('update_fields')
            if _uf2 is not None:
                kwargs['update_fields'] = list(set(_uf2) | {'task_layout_light'})
        except Exception:
            pass
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


class PlayerNotification(models.Model):
    """
    Aviso personal para un usuario en su espacio (jugador o staff).

    Genérico y reutilizable: convocatoria, multas, sesiones... Sigue el mismo
    patrón que VideoInboxItem (target_user + is_read) para surtir badges/inbox.
    """

    KIND_CONVOCATION = 'convocatoria'
    KIND_LINEUP = 'alineacion'
    KIND_GENERAL = 'general'
    KIND_CHOICES = [
        (KIND_CONVOCATION, 'Convocatoria'),
        (KIND_LINEUP, 'Alineación'),
        (KIND_GENERAL, 'Aviso'),
    ]

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, null=True, blank=True, related_name='player_notifications'
    )
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True, related_name='player_notifications'
    )
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_notifications')
    created_by_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='player_notifications_sent'
    )
    match = models.ForeignKey(
        'Match', on_delete=models.CASCADE, null=True, blank=True, related_name='player_notifications'
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=KIND_GENERAL)
    title = models.CharField(max_length=180, blank=True)
    message = models.TextField(blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['target_user', 'is_read', '-created_at']),
            models.Index(fields=['target_user', 'kind', 'match']),
        ]

    def __str__(self):
        return f'{self.target_user_id} · {self.kind} · {self.created_at:%Y-%m-%d}'


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
    # Desglose por parámetros de cada área: {"physical": {"velocidad": 7, ...}, "technical": {...}, ...}
    # La nota de cada área (physical_rating, etc.) es por defecto la media de sus parámetros (ajustable).
    parameter_scores = models.JSONField(default=dict, blank=True)
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
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
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


class ScoutingPitchBoardLayout(models.Model):
    """Disposicion de la pizarra de ojeo (comparativa por posicion), compartida por equipo.
    positions es un dict {"<scouting_target_id>": [left_pct, top_pct]}."""
    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='scouting_board_layout')
    positions = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        verbose_name = 'Pizarra de ojeo'
        verbose_name_plural = 'Pizarras de ojeo'

    def __str__(self):
        return f'Pizarra ojeo · {self.team.name}'


class CoachPitchBoardLayout(models.Model):
    """
    Disposición de la pizarra de plantilla (portada del entrenador), compartida por equipo.

    Guarda dónde ha colocado el cuerpo técnico cada jugador sobre el campo, para que TODO el staff
    vea la misma disposición desde cualquier dispositivo (a diferencia de guardarlo solo en el
    navegador). `positions` es un dict {"<player_id>": [left_pct, top_pct]}.
    """

    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name='pitch_board_layout')
    positions = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        verbose_name = 'Pizarra de plantilla'
        verbose_name_plural = 'Pizarras de plantilla'

    def __str__(self):
        return f'Pizarra · {self.team.name}'
