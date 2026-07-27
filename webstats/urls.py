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
from django.views.static import serve
from django.contrib.auth.decorators import login_required
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
    # Recuperar contraseña (envía email; con SMTP sin configurar, el correo va a los logs).
    # Los nombres de URL son los estándar de Django para que sus vistas resuelvan solas los success_url.
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/enviado/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('reset/completado/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
    # Cambiar contraseña (usuario ya logueado).
    path('password-change/', login_required(auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change_form.html',
    )), name='password_change'),
    path('password-change/hecho/', login_required(auth_views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html',
    )), name='password_change_done'),
    path('admin/', admin.site.urls),
    path('', include('football.urls')),
]

# En producción sin S3, seguimos sirviendo MEDIA_URL desde la app (Render no sirve /media/ por defecto).
# Se protege con login para que las fotos/archivos solo se vean con sesión iniciada.
if str(settings.MEDIA_URL).startswith('/') and not getattr(settings, 'USE_S3_MEDIA', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', protected_media_serve),
    ]
