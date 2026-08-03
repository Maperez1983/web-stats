from django.contrib import admin

from . import models


@admin.register(models.DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url')


@admin.register(models.Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'level')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(models.Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition', 'is_current')


@admin.register(models.Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'external_id', 'possible_duplicate_groups')
    search_fields = ('name', 'slug', 'external_id')
    actions = ('merge_selected_groups',)

    @admin.display(description='Posible mismo grupo')
    def possible_duplicate_groups(self, obj):
        # El mismo grupo real escrito distinto ('Grupo 2 (2025/2026)' vs '2025-2026'). Cruza
        # temporadas porque la temporada también puede estar duplicada.
        cands = models.fuzzy_duplicate_groups(obj, limit=3)
        if not cands:
            return '—'
        return '≈ ' + ', '.join(f'{c.name} · {c.season.name}' for c in cands)

    @admin.action(description='Fusionar grupos seleccionados (conserva el que tenga más datos)')
    def merge_selected_groups(self, request, queryset):
        from django.contrib import messages
        groups = list(queryset)
        if len(groups) < 2:
            self.message_user(request, 'Selecciona al menos 2 grupos para fusionar.', level=messages.WARNING)
            return

        def score(group):
            content = group.teams.count() + group.matches.count() + group.standings.count()
            return (content, 1 if group.external_id else 0, -group.id)

        keep = max(groups, key=score)
        merged = 0
        for drop in groups:
            if drop.pk == keep.pk:
                continue
            try:
                models.merge_groups(keep, drop)
                merged += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'No se pudo fusionar «{drop.name}»: {exc}', level=messages.ERROR)
        if merged:
            self.message_user(
                request,
                f'Fusionados {merged + 1} grupos en «{keep.name}» ({keep.season.name}); '
                'equipos, partidos y clasificación reasignados.',
                level=messages.SUCCESS,
            )


@admin.register(models.Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'name_key', 'team_count', 'possible_same_club', 'updated_at')
    search_fields = ('name', 'short_name', 'name_key', 'external_id', 'preferente_url')
    actions = ('reconcile_selected_clubs', 'merge_selected_clubs')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('teams')

    @admin.display(description='Equipos')
    def team_count(self, obj):
        return obj.teams.count()

    @admin.display(description='Posible mismo club (parecido)')
    def possible_same_club(self, obj):
        # Detector fuzzy: clubes de nombre PARECIDO (no exacto) que probablemente son el mismo real
        # escrito distinto — p. ej. un destino de traspaso/ojeo "Pizarra" vs el "C.D. Pizarra
        # Atlético C.F." que luego aparece por la liga. Se reconcilian con la acción de arriba.
        cands = models.fuzzy_duplicate_clubs(obj, limit=3)
        if not cands:
            return '—'
        return '≈ ' + ', '.join(c.name for c in cands)

    @admin.action(description='Fusionar clubes seleccionados en uno (el más antiguo)')
    def merge_selected_clubs(self, request, queryset):
        from django.contrib import messages
        clubs = list(queryset.order_by('id'))
        if len(clubs) < 2:
            self.message_user(request, 'Selecciona al menos 2 clubes para fusionar.', level=messages.WARNING)
            return
        keep = clubs[0]
        merged = 0
        for drop in clubs[1:]:
            try:
                models.merge_clubs(keep, drop)
                merged += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'No se pudo fusionar «{drop.name}»: {exc}', level=messages.ERROR)
        if merged:
            self.message_user(
                request,
                f'Fusionados {merged + 1} clubes en «{keep.name}» (id {keep.id}); sus equipos se reasignaron.',
                level=messages.SUCCESS,
            )

    @admin.action(description='Reconciliar: unificar conservando el club REAL (con equipos/oficial)')
    def reconcile_selected_clubs(self, request, queryset):
        # Para el caso "club referenciado (destino de traspaso u ojeo) que luego aparece de verdad
        # en la liga por scraping": fusiona conservando el club REAL — el que tiene equipos /
        # external_id / URL (no el más antiguo, que suele ser el tecleado a mano y vacío).
        from django.contrib import messages
        clubs = list(queryset)
        if len(clubs) < 2:
            self.message_user(request, 'Selecciona al menos 2 clubes para reconciliar.', level=messages.WARNING)
            return

        def score(club):
            return (club.teams.count(), 1 if club.external_id else 0, 1 if club.preferente_url else 0, -club.id)

        keep = max(clubs, key=score)
        merged = 0
        for drop in clubs:
            if drop.pk == keep.pk:
                continue
            try:
                models.merge_clubs(keep, drop)
                merged += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'No se pudo reconciliar «{drop.name}»: {exc}', level=messages.ERROR)
        if merged:
            self.message_user(
                request,
                f'Reconciliados {merged + 1} clubes en «{keep.name}» (id {keep.id}); '
                'equipos, traspasos y ojeos reasignados al club real.',
                level=messages.SUCCESS,
            )


@admin.register(models.ClubCategory)
class ClubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'club', 'order', 'game_format', 'team_count', 'name_key')
    search_fields = ('name', 'name_key', 'club__name', 'external_id')
    autocomplete_fields = ('club',)
    ordering = ('club__name', 'order', 'name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('club').prefetch_related('teams')

    @admin.display(description='Equipos')
    def team_count(self, obj):
        return obj.teams.count()


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'club', 'category', 'category_ref', 'name_key', 'external_id', 'possible_duplicates', 'possible_duplicates_fuzzy', 'group', 'is_primary')
    list_filter = ('game_format', 'group', 'is_primary')
    search_fields = ('name', 'short_name', 'slug', 'category', 'name_key', 'external_id', 'preferente_url')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('club', 'category_ref')
    ordering = ('name_key', 'name')
    actions = ('merge_selected_teams',)

    @admin.display(description='Posibles duplicados')
    def possible_duplicates(self, obj):
        # Otros equipos con la MISMA clave de nombre EN EL MISMO grupo (mismo club+categoría =
        # candidatos a fusionar). Distinto grupo = otra categoría del club, no es duplicado.
        if not obj.name_key:
            return '—'
        count = models.Team.objects.filter(name_key=obj.name_key, group=obj.group).exclude(pk=obj.pk).count()
        return f'⚠ {count}' if count else '—'

    @admin.display(description='Parecidos (posible dup.)')
    def possible_duplicates_fuzzy(self, obj):
        # Duplicados por PARECIDO en el mismo grupo (erratas/abreviaturas que name_key exacto no
        # caza: 'Torremoya' ~ 'Torrremoya'). Se fusionan con la acción de abajo.
        cands = models.fuzzy_duplicate_teams(obj, limit=3)
        if not cands:
            return '—'
        return '≈ ' + ', '.join(c.name for c in cands)

    @admin.action(description='Fusionar equipos seleccionados en uno (conserva el que tenga external_id, o el más antiguo)')
    def merge_selected_teams(self, request, queryset):
        from django.contrib import messages
        teams = list(queryset)
        if len(teams) < 2:
            self.message_user(request, 'Selecciona al menos 2 equipos para fusionar.', level=messages.WARNING)
            return
        # Conserva el equipo "oficial": primero el que tenga external_id (registrado en La
        # Preferente); si ninguno, el de nombre más largo/completo (suele ser el oficial).
        with_ext = sorted((t for t in teams if str(t.external_id or '').strip()), key=lambda t: t.id)
        keep = with_ext[0] if with_ext else sorted(teams, key=lambda t: (-len(t.name or ''), t.id))[0]
        merged = 0
        for drop in teams:
            if drop.id == keep.id:
                continue
            try:
                models.merge_teams(keep, drop)
                merged += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'No se pudo fusionar «{drop.name}»: {exc}', level=messages.ERROR)
        if merged:
            self.message_user(
                request,
                f'Fusionados {merged + 1} equipos en «{keep.name}» (id {keep.id}). Se reasignó todo y se borraron los duplicados.',
                level=messages.SUCCESS,
            )


class WorkspaceTeamInline(admin.TabularInline):
    model = models.WorkspaceTeam
    extra = 0
    autocomplete_fields = ('team',)
    fields = ('team', 'is_default', 'is_active')


@admin.register(models.Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'slug', 'is_active', 'primary_team', 'owner_user')
    list_filter = ('kind', 'is_active')
    search_fields = ('name', 'slug')
    autocomplete_fields = ('primary_team', 'owner_user')
    inlines = (WorkspaceTeamInline,)


@admin.register(models.WorkspaceSeason)
class WorkspaceSeasonAdmin(admin.ModelAdmin):
    list_display = ('label', 'workspace', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'workspace')
    search_fields = ('label', 'workspace__name')
    autocomplete_fields = ('workspace',)


@admin.register(models.WorkspaceSeasonTeam)
class WorkspaceSeasonTeamAdmin(admin.ModelAdmin):
    list_display = ('season', 'team', 'status', 'is_active', 'confirmed_at')
    list_filter = ('status', 'is_active', 'season')
    search_fields = ('team__name', 'team__short_name', 'season__label', 'season__workspace__name')
    autocomplete_fields = ('season', 'team')


@admin.register(models.WorkspaceSeasonPlayer)
class WorkspaceSeasonPlayerAdmin(admin.ModelAdmin):
    list_display = ('season', 'player', 'status', 'is_confirmed', 'confirmed_at', 'left_at')
    list_filter = ('status', 'is_confirmed', 'season')
    search_fields = ('player__name', 'player__full_name', 'season__label', 'season__workspace__name')
    autocomplete_fields = ('season', 'player', 'confirmed_by')


@admin.register(models.PlayerIdentity)
class PlayerIdentityAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'display_name', 'birth_date', 'record_count', 'record_teams', 'updated_at')
    search_fields = ('full_name', 'display_name', 'preferente_profile_url', 'transfermarkt_url', 'besoccer_url')
    list_filter = ('birth_date',)
    actions = ('merge_selected_identities',)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('player_records__team')

    @admin.display(description='Fichas')
    def record_count(self, obj):
        return obj.player_records.count()

    @admin.display(description='Equipos')
    def record_teams(self, obj):
        names = []
        for p in obj.player_records.all():
            team = getattr(p, 'team', None)
            label = getattr(team, 'name', None) or '—'
            if label not in names:
                names.append(label)
        return ', '.join(names[:6]) or '—'

    @admin.action(description='Fusionar seleccionadas en una sola persona')
    def merge_selected_identities(self, request, queryset):
        from django.contrib import messages
        identities = list(queryset.order_by('id'))
        if len(identities) < 2:
            self.message_user(request, 'Selecciona al menos 2 identidades para fusionar.', level=messages.WARNING)
            return
        keep = identities[0]
        merged = 0
        for drop in identities[1:]:
            try:
                models.merge_player_identities(keep, drop)
                merged += 1
            except Exception as exc:  # noqa: BLE001
                self.message_user(request, f'No se pudo fusionar «{drop}»: {exc}', level=messages.ERROR)
        if merged:
            self.message_user(
                request,
                f'Fusionadas {merged + 1} identidades en «{keep}» (se conserva la más antigua).',
                level=messages.SUCCESS,
            )


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'is_active', 'transferred_to_club', 'transferred_to_category', 'number', 'position', 'identity')
    list_filter = ('is_active', 'team')
    search_fields = ('name', 'full_name', 'nickname', 'team__name', 'transferred_to_club__name')
    autocomplete_fields = ('identity', 'transferred_to_club', 'transferred_to_category_ref')


@admin.register(models.PlayerAsset)
class PlayerAssetAdmin(admin.ModelAdmin):
    list_display = ('player', 'kind', 'has_image', 'updated_at')
    list_filter = ('kind',)
    search_fields = ('player__name', 'player__full_name')
    autocomplete_fields = ('player',)
    readonly_fields = ('source_key', 'updated_at')

    @admin.display(boolean=True, description='imagen')
    def has_image(self, obj):
        return bool(obj.image)


@admin.register(models.PlayerEvaluation)
class PlayerEvaluationAdmin(admin.ModelAdmin):
    list_display = ('player', 'team', 'club_season', 'evaluation_type', 'evaluated_on', 'status', 'overall_rating', 'objective_performance_rating', 'availability_rating')
    list_filter = ('evaluation_type', 'status', 'maturation_status', 'club_season', 'team')
    search_fields = ('player__name', 'player__full_name', 'team__name', 'club_season__label')
    autocomplete_fields = ('player', 'team', 'club_season', 'created_by', 'updated_by')


@admin.register(models.InjuryCatalogEntry)
class InjuryCatalogEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'region', 'typical_min_days', 'typical_max_days', 'is_active')
    list_filter = ('category', 'region', 'is_active')
    search_fields = ('name', 'code')


@admin.register(models.PlayerInjuryRecord)
class PlayerInjuryRecordAdmin(admin.ModelAdmin):
    list_display = ('player', 'injury', 'injury_date', 'return_date', 'is_active', 'severity_grade', 'training_status')
    list_filter = ('is_active', 'injury_type', 'injury_zone')
    search_fields = ('player__name', 'injury', 'injury_type', 'injury_zone')


@admin.register(models.PlayerPhysicalMetric)
class PlayerPhysicalMetricAdmin(admin.ModelAdmin):
    list_display = ('player', 'recorded_on', 'workload', 'rpe', 'wellness')
    list_filter = ('recorded_on',)


@admin.register(models.PlayerCommunication)
class PlayerCommunicationAdmin(admin.ModelAdmin):
    list_display = ('player', 'category', 'match', 'scheduled_for', 'created_at')
    list_filter = ('category', 'created_at')


@admin.register(models.Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('round', 'home_team', 'away_team', 'date', 'home_score', 'away_score')
    list_filter = ('round', 'date')


@admin.register(models.TeamStanding)
class TeamStandingAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'points', 'position')
    list_filter = ('season', 'group')


@admin.register(models.CustomMetric)
class CustomMetricAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'name', 'value', 'recorded_at')


admin.site.register(models.TeamStatistic)
admin.site.register(models.PlayerStatistic)
admin.site.register(models.MatchReport)
admin.site.register(models.DataImportLog)
admin.site.register(models.MatchEvent)
admin.site.register(models.ScrapeSource)
admin.site.register(models.ScrapeRun)


@admin.register(models.AiTrainerEvent)
class AiTrainerEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'event_type', 'team', 'workspace', 'user')
    list_filter = ('event_type', 'team')
    search_fields = ('team__name', 'user__username', 'meta')


@admin.register(models.AiTrainerTokenWeight)
class AiTrainerTokenWeightAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'team', 'workspace', 'token', 'weight')
    list_filter = ('team',)
    search_fields = ('token', 'team__name')


@admin.register(models.AiTrainerTaskIndex)
class AiTrainerTaskIndexAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'team', 'repository', 'task')
    list_filter = ('team', 'repository')
    search_fields = ('task__title', 'content')


@admin.register(models.AiTrainerDictionaryEntry)
class AiTrainerDictionaryEntryAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'team', 'workspace', 'section', 'entry_key', 'label', 'created_by')
    list_filter = ('team', 'section')
    search_fields = ('entry_key', 'label', 'keywords', 'coaching_points')


@admin.register(models.ServiceAccessToken)
class ServiceAccessTokenAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'name', 'workspace', 'token_prefix', 'is_active', 'expires_at', 'last_used_at')
    list_filter = ('is_active', 'workspace')
    search_fields = ('user__username', 'user__email', 'name', 'token_prefix')
    autocomplete_fields = ('user', 'workspace')
    readonly_fields = ('token_prefix', 'token_hash', 'created_at', 'last_used_at')

    def has_add_permission(self, request):
        return False


@admin.register(models.AcademyMediaAsset)
class AcademyMediaAssetAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'title', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'source_url')


class AcademyLessonStepInline(admin.TabularInline):
    model = models.AcademyLessonStep
    extra = 0
    fields = ('order', 'step_type', 'title', 'media', 'is_required')
    autocomplete_fields = ('media',)
    ordering = ('order', 'id')


@admin.register(models.AcademyLesson)
class AcademyLessonAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'title', 'min_category', 'max_category', 'is_published')
    list_filter = ('is_published', 'min_category', 'max_category')
    search_fields = ('title', 'summary', 'created_by')
    inlines = (AcademyLessonStepInline,)


@admin.register(models.AcademyAssignment)
class AcademyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'workspace', 'team', 'lesson', 'is_required', 'is_active', 'due_at')
    list_filter = ('is_active', 'is_required')
    search_fields = ('workspace__name', 'team__name', 'lesson__title')
    autocomplete_fields = ('workspace', 'team', 'lesson', 'created_by')


@admin.register(models.AcademyProgress)
class AcademyProgressAdmin(admin.ModelAdmin):
    list_display = ('updated_at', 'workspace', 'team', 'user', 'lesson', 'status', 'correct_count', 'answer_count')
    list_filter = ('status',)
    search_fields = ('workspace__name', 'user__username', 'lesson__title')
    autocomplete_fields = ('workspace', 'team', 'user', 'lesson', 'assignment')


@admin.register(models.PlayerObjective)
class PlayerObjectiveAdmin(admin.ModelAdmin):
    list_display = ('player', 'status', 'text', 'target_date', 'created_at')
    list_filter = ('status',)
    search_fields = ('player__name', 'text')
