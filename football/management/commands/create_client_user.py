import secrets
from typing import Optional

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from football.models import AppUserRole, Workspace, WorkspaceMembership, WorkspaceTeam, WorkspaceTeamAccess


def _build_username(seed: str) -> str:
    value = slugify(seed or '').replace('-', '.')
    value = value.strip('.')
    return value or 'cliente'


def _unique_username(base: str) -> str:
    base = _build_username(base)
    candidate = base
    suffix = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f'{base}{suffix}'
        suffix += 1
    return candidate


def _pick_workspace(slug: Optional[str]) -> Optional[Workspace]:
    slug = str(slug or '').strip()
    if slug:
        return Workspace.objects.filter(slug=slug, is_active=True).first()
    active_club_workspaces = list(Workspace.objects.filter(kind=Workspace.KIND_CLUB, is_active=True).order_by('name', 'id'))
    if len(active_club_workspaces) == 1:
        return active_club_workspaces[0]
    return None


def _pick_default_team_for_workspace(workspace: Workspace):
    if not workspace:
        return None
    if getattr(workspace, 'primary_team_id', None):
        return workspace.primary_team
    default_link = (
        WorkspaceTeam.objects
        .select_related('team')
        .filter(workspace=workspace, is_default=True)
        .first()
    )
    if default_link and getattr(default_link, 'team', None):
        return default_link.team
    first_link = (
        WorkspaceTeam.objects
        .select_related('team')
        .filter(workspace=workspace)
        .order_by('id')
        .first()
    )
    return first_link.team if first_link and getattr(first_link, 'team', None) else None


class Command(BaseCommand):
    help = (
        'Crea un usuario "cliente" (NO plataforma) para testing: sin is_staff/is_superuser y con rol de app no-admin. '
        'Opcionalmente lo vincula a un Workspace como miembro.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--email', default='', help='Email del usuario cliente (opcional).')
        parser.add_argument('--username', default='', help='Username (si se omite, se deriva del email o se autogenera).')
        parser.add_argument(
            '--password',
            default='',
            help='Password (si se omite, se genera una aleatoria y se imprime).',
        )
        parser.add_argument(
            '--app-role',
            default=AppUserRole.ROLE_GUEST,
            help=(
                'Rol funcional dentro de la app (por defecto: invitado). '
                f'Opciones: {", ".join([r[0] for r in AppUserRole.ROLE_CHOICES])}.'
            ),
        )
        parser.add_argument(
            '--workspace-slug',
            default='',
            help=(
                'Slug del workspace al que asociar el usuario. '
                'Si se omite y existe exactamente 1 workspace club activo, se usa ese; si hay varios, se deja sin workspace.'
            ),
        )
        parser.add_argument(
            '--workspace-role',
            default=WorkspaceMembership.ROLE_VIEWER,
            help=(
                'Rol dentro del workspace (por defecto: viewer). '
                f'Opciones: {", ".join([r[0] for r in WorkspaceMembership.ROLE_CHOICES])}.'
            ),
        )
        parser.add_argument(
            '--set-default-team-access',
            action='store_true',
            help='Si se asocia a workspace, marca el equipo por defecto para el usuario (WorkspaceTeamAccess.is_default=True).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        email = str(options.get('email') or '').strip().lower()
        requested_username = str(options.get('username') or '').strip()
        username_seed = requested_username or (email.split('@', 1)[0] if '@' in email else '') or 'cliente'
        username = requested_username or _unique_username(username_seed)

        password = str(options.get('password') or '').strip()
        generated_password = False
        if not password:
            password = secrets.token_urlsafe(12)
            generated_password = True

        app_role = str(options.get('app_role') or AppUserRole.ROLE_GUEST).strip()
        valid_app_roles = {choice[0] for choice in AppUserRole.ROLE_CHOICES}
        if app_role not in valid_app_roles:
            self.stdout.write(self.style.WARNING(f'Rol de app inválido "{app_role}", usando "{AppUserRole.ROLE_GUEST}".'))
            app_role = AppUserRole.ROLE_GUEST

        workspace_slug = str(options.get('workspace_slug') or '').strip()
        workspace = _pick_workspace(workspace_slug)
        if workspace_slug and not workspace:
            self.stdout.write(self.style.ERROR(f'No existe workspace activo con slug "{workspace_slug}".'))
            return

        workspace_role = str(options.get('workspace_role') or WorkspaceMembership.ROLE_VIEWER).strip()
        valid_workspace_roles = {choice[0] for choice in WorkspaceMembership.ROLE_CHOICES}
        if workspace_role not in valid_workspace_roles:
            self.stdout.write(self.style.WARNING(f'Rol de workspace inválido "{workspace_role}", usando "{WorkspaceMembership.ROLE_VIEWER}".'))
            workspace_role = WorkspaceMembership.ROLE_VIEWER

        user = User.objects.filter(username=username).first()
        created = False
        if not user:
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                is_active=True,
            )
            created = True
        else:
            user.email = email
            user.is_active = True
            user.set_password(password)
            user.save(update_fields=['email', 'is_active', 'password'])

        # Aseguramos que NO sea plataforma.
        if user.is_staff or user.is_superuser:
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=['is_staff', 'is_superuser'])

        AppUserRole.objects.update_or_create(
            user=user,
            defaults={'role': app_role},
        )

        if workspace:
            WorkspaceMembership.objects.update_or_create(
                workspace=workspace,
                user=user,
                defaults={'role': workspace_role},
            )

            if bool(options.get('set_default_team_access')):
                team = _pick_default_team_for_workspace(workspace)
                if team:
                    WorkspaceTeamAccess.objects.update_or_create(
                        workspace=workspace,
                        team=team,
                        user=user,
                        defaults={'is_default': True},
                    )

        header = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(f'{header} usuario cliente: {user.username} ({user.email})'))
        if workspace:
            self.stdout.write(self.style.SUCCESS(f'Workspace: {workspace.slug} · rol={workspace_role} · app_role={app_role}'))
        else:
            self.stdout.write(self.style.WARNING(f'Sin workspace asignado · app_role={app_role}'))
        if generated_password:
            self.stdout.write(self.style.WARNING(f'Password generado: {password}'))
