from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import User, Workspace, WorkspaceMembership
from app.schemas.auth import (
    MembershipRoleUpdate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("/current", response_model=WorkspaceResponse)
def read_current_workspace(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    result = db.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(WorkspaceMembership.user_id == current_user.id)
        .order_by(Workspace.created_at, Workspace.id)
        .limit(1)
    ).first()
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "workspace_not_found",
                "message": "No workspace is available for this account.",
            },
        )
    workspace, role = result
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        role=role,
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
)
def list_workspace_members(
    workspace_id: UUID,
    _role: str = Depends(require_workspace_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> list[WorkspaceMemberResponse]:
    rows = db.execute(
        select(User.id, User.email, User.display_name, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.workspace_id == workspace_id)
        .order_by(User.display_name, User.id)
    ).all()
    return [
        WorkspaceMemberResponse(
            user_id=row.id,
            email=row.email,
            display_name=row.display_name,
            role=row.role,
        )
        for row in rows
    ]


@router.patch(
    "/{workspace_id}/members/{member_user_id}/role",
    response_model=WorkspaceMemberResponse,
)
def update_member_role(
    workspace_id: UUID,
    member_user_id: UUID,
    request: MembershipRoleUpdate,
    _role: str = Depends(require_workspace_roles("owner")),
    db: Session = Depends(get_db),
) -> WorkspaceMemberResponse:
    membership = db.get(
        WorkspaceMembership, (workspace_id, member_user_id)
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "member_not_found",
                "message": "The workspace member was not found.",
            },
        )
    if membership.role == "owner":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "owner_role_protected",
                "message": "The workspace owner role cannot be changed.",
            },
        )

    user = db.get(User, member_user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "member_not_found",
                "message": "The workspace member was not found.",
            },
        )

    membership.role = request.role
    db.commit()
    return WorkspaceMemberResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
    )
