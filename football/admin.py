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
    list_display = ('name', 'group', 'is_primary', 'city')
    list_filter = ('group', 'is_primary')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'number', 'position')


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
