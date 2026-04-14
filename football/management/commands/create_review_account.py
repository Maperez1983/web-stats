import secrets
from datetime import timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from football.models import (
    AppUserRole,
    Team,
    Workspace,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


def _unique_slug(model, base_text: str, *, field: str = 'slug', fallback: str = 'demo') -> str:
    base_slug = slugify(str(base_text or '').strip()) or fallback
    candidate = base_slug
    suffix = 2
    qs = model.objects.all()
    while qs.filter(**{field: candidate}).exists():
        candidate = f'{base_slug}-{suffix}'
        suffix += 1
    return candidate


@transaction.atomic
def _ensure_review_workspace(
    *,
    user: User,
    club_name: str,
    team_name: str,
    workspace_slug: Optional[str] = None,
):
    slug = str(workspace_slug or '').strip() or _unique_slug(Workspace, club_name, fallback='review-club')
    workspace = Workspace.objects.filter(slug=slug).first()
    modules = {}
    try:
        modules = {key: True for key in (Workspace().enabled_modules or {}).keys()}
    except Exception:
        modules = {}
    if not modules:
        # Módulos conocidos en la app (fallback si el modelo viene vacío).
        modules = {
            'dashboard': True,
            'sessions': True,
            'convocation': True,
            'match_actions': True,
            'players': True,
            'analysis': True,
            'staff': True,
        }

    if not workspace:
        workspace = Workspace.objects.create(
            name=club_name,
            slug=slug,
            kind=Workspace.KIND_CLUB,
            owner_user=user,
            enabled_modules=modules,
            subscription_status='trial',
            trial_expires_at=timezone.now() + timedelta(days=30),
            is_active=True,
        )
    else:
        workspace.name = club_name
        workspace.owner_user = user
        workspace.kind = Workspace.KIND_CLUB
        workspace.is_active = True
        try:
            if not getattr(workspace, 'enabled_modules', None):
                workspace.enabled_modules = modules
        except Exception:
            pass
        workspace.save()

    WorkspaceMembership.objects.update_or_create(
        workspace=workspace,
        user=user,
        defaults={'role': WorkspaceMembership.ROLE_OWNER},
    )

    primary_team = getattr(workspace, 'primary_team', None)
    if not primary_team:
        team_slug = _unique_slug(Team, team_name, fallback='review-team')
        primary_team = Team.objects.create(
            name=team_name,
            slug=team_slug,
            short_name=team_name[:60],
            is_primary=False,
        )
        workspace.primary_team = primary_team
        workspace.save(update_fields=['primary_team', 'updated_at'])
    else:
        if str(getattr(primary_team, 'name', '') or '').strip() != team_name:
            primary_team.name = team_name
            primary_team.short_name = team_name[:60]
            primary_team.save(update_fields=['name', 'short_name'])

    WorkspaceTeam.objects.get_or_create(
        workspace=workspace,
        team=primary_team,
        defaults={'is_default': True},
    )
    WorkspaceTeamAccess.objects.update_or_create(
        workspace=workspace,
        team=primary_team,
        user=user,
        defaults={'is_default': True},
    )

    return workspace, primary_team


class Command(BaseCommand):
    help = (
        'Crea (o actualiza) un usuario y un club demo para revisión de App Store / Google Play. '
        'Genera password si no se especifica.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', default='review.2j', help='Username del usuario demo.')
        parser.add_argument('--email', default='review@segundajugada.com', help='Email del usuario demo.')
        parser.add_argument('--password', default='', help='Password (si se omite, se genera y se imprime).')
        parser.add_argument('--club-name', default='2J Review Club', help='Nombre del club demo.')
        parser.add_argument('--team-name', default='2J Review Team', help='Nombre del equipo demo.')
        parser.add_argument('--workspace-slug', default='review-2j', help='Slug del workspace demo (idempotente).')

    def handle(self, *args, **options):
        username = str(options.get('username') or '').strip() or 'review.2j'
        email = str(options.get('email') or '').strip().lower()
        password = str(options.get('password') or '').strip()
        club_name = str(options.get('club_name') or '').strip() or '2J Review Club'
        team_name = str(options.get('team_name') or '').strip() or '2J Review Team'
        workspace_slug = str(options.get('workspace_slug') or '').strip() or 'review-2j'

        generated_password = False
        if not password:
            password = secrets.token_urlsafe(12)
            generated_password = True

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
            defaults={'role': AppUserRole.ROLE_COACH},
        )

        workspace, team = _ensure_review_workspace(
            user=user,
            club_name=club_name,
            team_name=team_name,
            workspace_slug=workspace_slug,
        )

        header = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(f'{header} usuario revisión: {user.username} ({user.email})'))
        self.stdout.write(self.style.SUCCESS(f'Workspace: {workspace.slug} · Equipo: {team.display_name}'))
        if generated_password:
            self.stdout.write(self.style.WARNING(f'Password generado: {password}'))
