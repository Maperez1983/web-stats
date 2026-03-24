"""
ASGI config for webstats project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from webstats.runtime_env import configure_native_runtime

configure_native_runtime()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webstats.settings')

application = get_asgi_application()
