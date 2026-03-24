from django.apps import AppConfig


class FootballConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'football'
    verbose_name = 'Football Intelligence'

    def ready(self):
        from . import signals  # noqa: F401
