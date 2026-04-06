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
    list_display = ('name', 'season', 'external_id')


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'game_format', 'group', 'is_primary', 'city')
    list_filter = ('game_format', 'group', 'is_primary')
    search_fields = ('name', 'short_name', 'slug', 'category')
    prepopulated_fields = {'slug': ('name',)}


class WorkspaceTeamInline(admin.TabularInline):
    model = models.WorkspaceTeam
    extra = 0
    autocomplete_fields = ('team',)
    fields = ('team', 'is_default')


@admin.register(models.Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'slug', 'is_active', 'primary_team', 'owner_user')
    list_filter = ('kind', 'is_active')
    search_fields = ('name', 'slug')
    autocomplete_fields = ('primary_team', 'owner_user')
    inlines = (WorkspaceTeamInline,)


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'number', 'position', 'injury', 'injury_date')


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
