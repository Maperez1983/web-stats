from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from football.models import AppUserRole, ServiceAccessToken, Workspace, WorkspaceMembership


class Command(BaseCommand):
    help = (
        'Crea un token de acceso de servicio para un usuario existente. '
        'El token se imprime una sola vez y sirve para abrir sesión como ese usuario.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='', help='Username del usuario al que asociar el token.')
        parser.add_argument('--user-id', type=int, default=0, help='ID del usuario al que asociar el token.')
        parser.add_argument('--name', default='ollana', help='Nombre legible del token.')
        parser.add_argument('--workspace-slug', default='', help='Workspace que debe quedar activo tras el login.')
        parser.add_argument('--workspace-id', type=int, default=0, help='Workspace que debe quedar activo tras el login.')
        parser.add_argument('--created-by', default='cli', help='Etiqueta de auditoría de quién crea el token.')
        parser.add_argument('--days', type=int, default=30, help='Caducidad en días. Usa 0 para sin expiración.')
        parser.add_argument(
            '--platform-access',
            action='store_true',
            help='Eleva el usuario a acceso de plataforma si todavía no lo tiene, para ver todos los workspaces.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = str(options.get('username') or '').strip()
        user_id = int(options.get('user_id') or 0)
        if not username and not user_id:
            self.stdout.write(self.style.ERROR('Debes indicar --username o --user-id.'))
            return

        user = None
        if user_id:
            user = User.objects.filter(id=user_id).first()
        if not user and username:
            user = User.objects.filter(username=username).first()
        if not user:
            self.stdout.write(self.style.ERROR('No se encontró el usuario indicado.'))
            return

        if bool(options.get('platform_access')) and not user.is_staff and not user.is_superuser:
            AppUserRole.objects.update_or_create(
                user=user,
                defaults={'role': AppUserRole.ROLE_ADMIN},
            )
            self.stdout.write(self.style.SUCCESS(f'Rol de plataforma ajustado a administrador para {user.username}.'))

        workspace = None
        workspace_slug = str(options.get('workspace_slug') or '').strip()
        workspace_id = int(options.get('workspace_id') or 0)
        if workspace_id:
            workspace = Workspace.objects.filter(id=workspace_id, is_active=True).first()
        elif workspace_slug:
            workspace = Workspace.objects.filter(slug=workspace_slug, is_active=True).first()
        if workspace and not WorkspaceMembership.objects.filter(workspace=workspace, user=user).exists():
            WorkspaceMembership.objects.get_or_create(
                workspace=workspace,
                user=user,
                defaults={'role': WorkspaceMembership.ROLE_VIEWER},
            )

        days = int(options.get('days') or 0)
        expires_at = None
        if days > 0:
            expires_at = timezone.now() + timedelta(days=days)

        token_obj, raw_token = ServiceAccessToken.create_for_user(
            user=user,
            name=str(options.get('name') or '').strip() or 'ollana',
            workspace=workspace,
            created_by=str(options.get('created_by') or '').strip() or 'cli',
            expires_at=expires_at,
        )

        self.stdout.write(self.style.SUCCESS(f'Token creado para {user.username}: {token_obj.id}'))
        if workspace:
            self.stdout.write(self.style.SUCCESS(f'Workspace activo: {workspace.slug}'))
        if expires_at:
            self.stdout.write(self.style.SUCCESS(f'Caduca: {expires_at.isoformat()}'))
        self.stdout.write(self.style.WARNING(f'Token raw: {raw_token}'))
        self.stdout.write(self.style.WARNING('Usa POST /service-login/ con service_token=... o Authorization: Bearer ...'))
