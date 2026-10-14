from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_workspace_roles
from app.models import Project, ProjectActivity, ProjectTask
from app.schemas.assistant import ProjectStatusDraftResponse
from app.services.project_summary import (
    ProjectSummaryContext,
    ProjectSummaryProvider,
    SummaryProviderError,
    get_project_summary_provider,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/assistant",
    tags=["Assistant"],
    dependencies=[Depends(require_workspace_roles("owner", "admin", "member"))],
)


@router.post(
    "/projects/{project_id}/status-draft",
    response_model=ProjectStatusDraftResponse,
)
def create_project_status_draft(
    workspace_id: UUID,
    project_id: UUID,
    db: Session = Depends(get_db),
    provider: ProjectSummaryProvider = Depends(get_project_summary_provider),
) -> ProjectStatusDraftResponse:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "project_not_found",
                "message": "The project was not found.",
            },
        )
    status_counts = db.execute(
        select(ProjectTask.status, func.count(ProjectTask.id))
        .where(
            ProjectTask.workspace_id == workspace_id,
            ProjectTask.project_id == project_id,
        )
        .group_by(ProjectTask.status)
    ).all()
    recent_activity = db.scalars(
        select(ProjectActivity.summary)
        .where(
            ProjectActivity.workspace_id == workspace_id,
            ProjectActivity.project_id == project_id,
        )
        .order_by(ProjectActivity.created_at.desc(), ProjectActivity.id.desc())
        .limit(5)
    ).all()
    context = ProjectSummaryContext(
        project_name=project.name,
        project_status=project.status,
        project_description=project.description,
        task_counts={task_status: count for task_status, count in status_counts},
        recent_activity=tuple(recent_activity),
    )
    try:
        draft = provider.create_draft(context)
    except SummaryProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "assistant_unavailable",
                "message": "The project update assistant is temporarily unavailable.",
            },
        ) from exc

    try:
        return ProjectStatusDraftResponse(draft=draft, provider=provider.name)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "assistant_invalid_output",
                "message": "The project update assistant returned an invalid draft.",
            },
        ) from exc
