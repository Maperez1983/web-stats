"""
URL configuration for webstats project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.urls import re_path
from django.contrib.auth import views as auth_views

from football.auth_views import RoleAwareLoginView, service_token_login_page
from football import views as football_views
from webstats.media import protected_media_serve
from webstats.health import healthz

urlpatterns = [
    path('healthz', healthz, name='healthz'),
    path('healthz/', healthz, name='healthz-slash'),
    path('.well-known/apple-app-site-association', football_views.apple_app_site_association, name='apple-app-site-association'),
    path('apple-app-site-association', football_views.apple_app_site_association, name='apple-app-site-association-root'),
    path('login/', RoleAwareLoginView.as_view(), name='login'),
    path('service-login/', service_token_login_page, name='service-login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/', admin.site.urls),
    path('', include('football.urls')),
]

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
        *urlpatterns,
    ]

# En producción sin S3, seguimos sirviendo MEDIA_URL desde la app (Render no sirve /media/ por defecto).
# Se protege con login para que las fotos/archivos solo se vean con sesión iniciada.
if str(settings.MEDIA_URL).startswith('/') and not getattr(settings, 'USE_S3_MEDIA', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', protected_media_serve),
    ]
