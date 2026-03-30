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

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('admin/', admin.site.urls),
    path('', include('football.urls')),
]

# En producción sin S3, seguimos sirviendo MEDIA_URL desde la app (Render no sirve /media/ por defecto).
# Se protege con login para que las fotos/archivos solo se vean con sesión iniciada.
if str(settings.MEDIA_URL).startswith('/') and not getattr(settings, 'USE_S3_MEDIA', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', login_required(serve), {'document_root': settings.MEDIA_ROOT}),
    ]
