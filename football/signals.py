from __future__ import annotations

from django.db.models.signals import post_migrate
from django.dispatch import receiver

from football.bootstrap import ensure_bootstrap_admin_from_env


@receiver(post_migrate)
def ensure_bootstrap_admin(sender, **kwargs):
    if getattr(sender, 'name', '') != 'football':
        return
    ensure_bootstrap_admin_from_env()
