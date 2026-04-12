from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.template.defaultfilters import slugify

from football.models import (
    StaffMember,
    Team,
    Workspace,
    WorkspaceCompetitionContext,
    WorkspaceCompetitionSnapshot,
    WorkspaceMembership,
    WorkspaceTeam,
    WorkspaceTeamAccess,
)


def unique_workspace_slug(base_text: str) -> str:
    base_slug = slugify(base_text or "workspace") or "workspace"
    candidate = base_slug
    suffix = 2
    qs = Workspace.objects.all()
    while qs.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


@dataclass(frozen=True)
class SplitWorkspacePlanRow:
    team_id: int
    team_name: str
    team_category: str
    new_workspace_name: str
    new_workspace_slug: str
    member_user_ids: tuple[int, ...]
    staff_count: int
    has_context: bool


def build_split_workspace_plan(workspace: Workspace, *, include_primary: bool = False) -> list[SplitWorkspacePlanRow]:
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return []
    links = list(
        WorkspaceTeam.objects.filter(workspace=workspace).select_related("team").order_by("-is_default", "id")
    )
    if len(links) <= 1:
        return []

    source_primary_team_id = int(getattr(workspace.primary_team, "id", 0) or 0)
    target_links = []
    for link in links:
        team = getattr(link, "team", None)
        if not team:
            continue
        if not include_primary and int(team.id) == source_primary_team_id:
            continue
        target_links.append(link)

    if not target_links:
        return []

    membership_by_user_id = {
        int(m.user_id): m
        for m in WorkspaceMembership.objects.filter(workspace=workspace).only("user_id", "role", "module_access")
    }
    owner_ids = {
        int(uid)
        for uid in WorkspaceMembership.objects.filter(
            workspace=workspace,
            role__in={WorkspaceMembership.ROLE_OWNER, WorkspaceMembership.ROLE_ADMIN},
        ).values_list("user_id", flat=True)
        if uid
    }
    base_name = str(getattr(workspace, "name", "") or "").strip() or "Club"

    rows: list[SplitWorkspacePlanRow] = []
    for link in target_links:
        team = link.team
        category = str(getattr(team, "category", "") or "").strip()
        team_label = category or str(getattr(team, "display_name", "") or getattr(team, "name", "") or "").strip()
        new_name = (
            f"{base_name} · {team_label}"
            if team_label and team_label.lower() not in base_name.lower()
            else f"{base_name} · {team.id}"
        )
        new_slug = unique_workspace_slug(new_name)

        team_access_user_ids = {
            int(uid)
            for uid in WorkspaceTeamAccess.objects.filter(workspace=workspace, team=team).values_list("user_id", flat=True)
        }
        selected_user_ids = set(owner_ids) | set(team_access_user_ids)
        if getattr(workspace, "owner_user_id", None):
            selected_user_ids.add(int(workspace.owner_user_id))
        selected_user_ids = {uid for uid in selected_user_ids if uid}

        # Staff: global + específico del equipo
        try:
            staff_count = int(
                StaffMember.objects.filter(workspace=workspace)
                .filter(team__isnull=True)
                .count()
                + StaffMember.objects.filter(workspace=workspace, team=team).count()
            )
        except Exception:
            staff_count = 0

        has_context = WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=team).exists()
        rows.append(
            SplitWorkspacePlanRow(
                team_id=int(team.id),
                team_name=str(team.name or "").strip(),
                team_category=category,
                new_workspace_name=new_name,
                new_workspace_slug=new_slug,
                member_user_ids=tuple(sorted({int(uid) for uid in selected_user_ids if uid})),
                staff_count=int(staff_count),
                has_context=bool(has_context),
            )
        )
    return rows


def apply_split_workspace_plan(
    workspace: Workspace,
    plan_rows: list[SplitWorkspacePlanRow],
    *,
    disable_source_workspace: bool = False,
    include_primary: bool = False,
) -> list[Workspace]:
    if not workspace or workspace.kind != Workspace.KIND_CLUB:
        return []
    if not plan_rows:
        return []

    created: list[Workspace] = []
    with transaction.atomic():
        # Avanzado: para incluir el primary_team hay que liberar el OneToOne.
        if include_primary and getattr(workspace, "primary_team_id", None):
            workspace.primary_team = None
            workspace.save(update_fields=["primary_team", "updated_at"])

        membership_by_user = {
            int(m.user_id): m
            for m in WorkspaceMembership.objects.filter(workspace=workspace).only("user_id", "role", "module_access")
        }

        for row in plan_rows:
            team = Team.objects.filter(id=row.team_id).first()
            if not team:
                continue

            new_workspace = Workspace.objects.create(
                name=row.new_workspace_name,
                slug=row.new_workspace_slug,
                kind=Workspace.KIND_CLUB,
                primary_team=team,
                owner_user=workspace.owner_user,
                enabled_modules=getattr(workspace, "enabled_modules", {}) or {},
                trial_expires_at=getattr(workspace, "trial_expires_at", None),
                subscription_status=str(getattr(workspace, "subscription_status", "") or "trial").strip() or "trial",
                plan_key=str(getattr(workspace, "plan_key", "") or "").strip(),
                is_active=True,
                notes=f"Creado al separar categorías desde {workspace.slug}.",
            )
            created.append(new_workspace)

            WorkspaceTeam.objects.update_or_create(
                workspace=new_workspace,
                team=team,
                defaults={"is_default": True},
            )

            for user_id in row.member_user_ids:
                membership = membership_by_user.get(int(user_id))
                role = membership.role if membership else WorkspaceMembership.ROLE_MEMBER
                module_access = dict(getattr(membership, "module_access", {}) or {}) if membership else {}
                WorkspaceMembership.objects.update_or_create(
                    workspace=new_workspace,
                    user_id=int(user_id),
                    defaults={"role": role, "module_access": module_access},
                )
                WorkspaceTeamAccess.objects.update_or_create(
                    workspace=new_workspace,
                    team=team,
                    user_id=int(user_id),
                    defaults={"is_default": True},
                )

            ctx = WorkspaceCompetitionContext.objects.filter(workspace=workspace, team=team).first()
            if ctx:
                ctx.workspace = new_workspace
                ctx.save(update_fields=["workspace", "updated_at"])
                snap = WorkspaceCompetitionSnapshot.objects.filter(context=ctx).first()
                if snap and snap.workspace_id != new_workspace.id:
                    snap.workspace = new_workspace
                    snap.save(update_fields=["workspace", "updated_at"])

            staff_rows = list(StaffMember.objects.filter(workspace=workspace, team__isnull=True)) + list(
                StaffMember.objects.filter(workspace=workspace, team=team)
            )
            for staff in staff_rows:
                StaffMember.objects.create(
                    workspace=new_workspace,
                    team=None,
                    user=staff.user,
                    name=staff.name,
                    role_title=staff.role_title,
                    certification_level=getattr(staff, "certification_level", ""),
                    dni=getattr(staff, "dni", ""),
                    phone=staff.phone,
                    email=staff.email,
                    photo=staff.photo,
                    photo_updated_at=getattr(staff, "photo_updated_at", None),
                    federation_license=getattr(staff, "federation_license", None),
                    federation_license_number=getattr(staff, "federation_license_number", ""),
                    federation_license_expires_at=getattr(staff, "federation_license_expires_at", None),
                    license_updated_at=getattr(staff, "license_updated_at", None),
                    certification_document=getattr(staff, "certification_document", None),
                    certification_expires_at=getattr(staff, "certification_expires_at", None),
                    certification_updated_at=getattr(staff, "certification_updated_at", None),
                    notes=staff.notes,
                    is_active=staff.is_active,
                )

            # Quitar vínculos antiguos: deja de ser "categoría" dentro del workspace origen.
            WorkspaceTeamAccess.objects.filter(workspace=workspace, team=team).delete()
            WorkspaceTeam.objects.filter(workspace=workspace, team=team).delete()

        if disable_source_workspace:
            workspace.is_active = False
            workspace.save(update_fields=["is_active", "updated_at"])

    return created
