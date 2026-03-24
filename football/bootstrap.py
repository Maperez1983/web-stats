from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.db import transaction

from football.models import AppUserRole


def _env_flag(name: str, default: str = 'false') -> bool:
    return str(os.getenv(name, default)).strip().lower() in {'1', 'true', 'yes', 'on'}


@transaction.atomic
def ensure_bootstrap_admin_from_env():
    username = str(os.getenv('BOOTSTRAP_ADMIN_USERNAME', '')).strip()
    password = str(os.getenv('BOOTSTRAP_ADMIN_PASSWORD', '')).strip()
    email = str(os.getenv('BOOTSTRAP_ADMIN_EMAIL', '')).strip()
    reset_password = _env_flag('BOOTSTRAP_ADMIN_RESET_PASSWORD', default='false')

    if not username or not password:
        return None

    user_model = get_user_model()
    user = user_model.objects.filter(username__iexact=username).first()
    created = False
    if not user:
        user = user_model.objects.create_user(
            username=username,
            password=password,
            email=email,
            is_active=True,
        )
        created = True
    else:
        update_fields = []
        if email and user.email != email:
            user.email = email
            update_fields.append('email')
        if not user.is_active:
            user.is_active = True
            update_fields.append('is_active')
        if not user.is_staff:
            user.is_staff = True
            update_fields.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            update_fields.append('is_superuser')
        if reset_password:
            user.set_password(password)
            update_fields.append('password')
        if update_fields:
            user.save(update_fields=update_fields)

    if created:
        user.is_staff = True
        user.is_superuser = True
        if email:
            user.email = email
        user.save(update_fields=['is_staff', 'is_superuser', 'email'] if email else ['is_staff', 'is_superuser'])

    AppUserRole.objects.update_or_create(
        user=user,
        defaults={'role': AppUserRole.ROLE_ADMIN},
    )
    return user
