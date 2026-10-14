from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import (
    Project,
    ProjectActivity,
    ProjectTask,
    TaskComment,
    User,
    WorkspaceMembership,
)
from app.schemas.projects import (
    CommentCreate,
    CommentResponse,
    ProjectActivityResponse,
    ProjectCreate,
    ProjectMemberResponse,
    ProjectPage,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskPage,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/projects",
    tags=["Projects"],
    dependencies=[Depends(require_workspace_roles("owner", "admin", "member"))],
)


@router.get("/members", response_model=list[ProjectMemberResponse])
def list_project_members(
    workspace_id: UUID,
    db: Session = Depends(get_db),
) -> list[ProjectMemberResponse]:
    rows = db.execute(
        select(User.id, User.display_name)
        .join(WorkspaceMembership, WorkspaceMembership.user_id == User.id)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            User.is_active.is_(True),
        )
        .order_by(User.display_name, User.id)
    ).all()
    return [ProjectMemberResponse(id=row.id, display_name=row.display_name) for row in rows]


@router.get("", response_model=ProjectPage)
def list_projects(
    workspace_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    project_status: Literal["active", "on_hold", "completed"] | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ProjectPage:
    query = select(Project).where(Project.workspace_id == workspace_id)
    if project_status is not None:
        query = query.where(Project.status == project_status)
    if q and q.strip():
        pattern = _search_pattern(q)
        query = query.where(
            or_(
                Project.name.ilike(pattern, escape="\\"),
                Project.description.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Project.updated_at.desc(), Project.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProjectPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    workspace_id: UUID,
    request: ProjectCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(
        workspace_id=workspace_id,
        created_by=actor.id,
        **request.model_dump(),
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectActivity(
            workspace_id=workspace_id,
            project_id=project.id,
            actor_id=actor.id,
            event_type="project_created",
            summary=f"Project '{project.name}' was created.",
        )
    )
    db.commit()
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    workspace_id: UUID,
    project_id: UUID,
    request: ProjectUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = _get_project(db, workspace_id, project_id)
    changes = request.model_dump(exclude_unset=True)
    previous_status = project.status
    for field, value in changes.items():
        setattr(project, field, value)
    if "status" in changes and changes["status"] != previous_status:
        db.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                actor_id=actor.id,
                event_type="project_status_changed",
                summary=f"Project status changed from {previous_status} to {project.status}.",
            )
        )
    updated_fields = [field for field in changes if field != "status"]
    if updated_fields:
        field_names = ", ".join(
            field.replace("_", " ") for field in updated_fields
        )
        db.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                actor_id=actor.id,
                event_type="project_updated",
                summary=f"Project details updated: {field_names}.",
            )
        )
    db.commit()
    return project


@router.get("/{project_id}/tasks", response_model=TaskPage)
def list_tasks(
    workspace_id: UUID,
    project_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    task_status: Literal["todo", "in_progress", "done"] | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    due_before: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TaskPage:
    _get_project(db, workspace_id, project_id)
    query = select(ProjectTask).where(
        ProjectTask.workspace_id == workspace_id,
        ProjectTask.project_id == project_id,
    )
    if task_status is not None:
        query = query.where(ProjectTask.status == task_status)
    if priority is not None:
        query = query.where(ProjectTask.priority == priority)
    if due_before is not None:
        query = query.where(ProjectTask.due_date <= due_before)
    if q and q.strip():
        pattern = _search_pattern(q)
        query = query.where(
            or_(
                ProjectTask.title.ilike(pattern, escape="\\"),
                ProjectTask.description.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(
            ProjectTask.due_date.asc().nulls_last(),
            ProjectTask.created_at.desc(),
            ProjectTask.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TaskPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    workspace_id: UUID,
    project_id: UUID,
    request: TaskCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectTask:
    project = _get_project(db, workspace_id, project_id)
    _validate_assignee(db, workspace_id, request.assigned_to)
    task = ProjectTask(
        workspace_id=workspace_id,
        project_id=project.id,
        created_by=actor.id,
        **request.model_dump(),
    )
    db.add(task)
    db.flush()
    db.add(
        ProjectActivity(
            workspace_id=workspace_id,
            project_id=project.id,
            task_id=task.id,
            actor_id=actor.id,
            event_type="task_created",
            summary=f"Task '{task.title}' was created.",
        )
    )
    db.commit()
    return task


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    workspace_id: UUID,
    project_id: UUID,
    task_id: UUID,
    request: TaskUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectTask:
    project = _get_project(db, workspace_id, project_id)
    task = _get_task(db, workspace_id, project.id, task_id)
    changes = request.model_dump(exclude_unset=True)
    if "assigned_to" in changes:
        _validate_assignee(db, workspace_id, changes["assigned_to"])
    previous_status = task.status
    for field, value in changes.items():
        setattr(task, field, value)
    if "status" in changes and changes["status"] != previous_status:
        db.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor_id=actor.id,
                event_type="task_status_changed",
                summary=f"Task status changed from {previous_status} to {task.status}.",
            )
        )
    updated_fields = [field for field in changes if field != "status"]
    if updated_fields:
        field_names = ", ".join(
            field.replace("_", " ") for field in updated_fields
        )
        db.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor_id=actor.id,
                event_type="task_updated",
                summary=f"Task details updated: {field_names}.",
            )
        )
    db.commit()
    return task


@router.get(
    "/{project_id}/tasks/{task_id}/comments",
    response_model=list[CommentResponse],
)
def list_task_comments(
    workspace_id: UUID,
    project_id: UUID,
    task_id: UUID,
    db: Session = Depends(get_db),
) -> list[TaskComment]:
    _get_task(db, workspace_id, project_id, task_id)
    return list(
        db.scalars(
            select(TaskComment)
            .where(
                TaskComment.workspace_id == workspace_id,
                TaskComment.task_id == task_id,
            )
            .order_by(TaskComment.created_at.desc(), TaskComment.id)
        ).all()
    )


@router.post(
    "/{project_id}/tasks/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_comment(
    workspace_id: UUID,
    project_id: UUID,
    task_id: UUID,
    request: CommentCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskComment:
    task = _get_task(db, workspace_id, project_id, task_id)
    comment = TaskComment(
        workspace_id=workspace_id,
        task_id=task.id,
        author_id=actor.id,
        body=request.body,
    )
    db.add(comment)
    db.flush()
    db.add(
        ProjectActivity(
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task.id,
            actor_id=actor.id,
            event_type="task_comment_added",
            summary=f"A comment was added to '{task.title}'.",
        )
    )
    db.commit()
    return comment


@router.get(
    "/{project_id}/activities",
    response_model=list[ProjectActivityResponse],
)
def list_project_activities(
    workspace_id: UUID,
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ProjectActivity]:
    _get_project(db, workspace_id, project_id)
    return list(
        db.scalars(
            select(ProjectActivity)
            .where(
                ProjectActivity.workspace_id == workspace_id,
                ProjectActivity.project_id == project_id,
            )
            .order_by(ProjectActivity.created_at.desc(), ProjectActivity.id)
            .limit(limit)
        ).all()
    )


def _get_project(db: Session, workspace_id: UUID, project_id: UUID) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "project_not_found", "message": "The project was not found."},
        )
    return project


def _get_task(
    db: Session, workspace_id: UUID, project_id: UUID, task_id: UUID
) -> ProjectTask:
    task = db.scalar(
        select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.workspace_id == workspace_id,
            ProjectTask.project_id == project_id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "task_not_found", "message": "The task was not found."},
        )
    return task


def _validate_assignee(
    db: Session, workspace_id: UUID, assigned_to: UUID | None
) -> None:
    if assigned_to is None:
        return
    member_id = db.scalar(
        select(WorkspaceMembership.user_id).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == assigned_to,
            User.is_active.is_(True),
        )
        .join(User, User.id == WorkspaceMembership.user_id)
    )
    if member_id is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "assignee_not_in_workspace",
                "message": "The assignee must be an active member of this workspace.",
            },
        )


def _search_pattern(value: str) -> str:
    escaped = (
        value.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"
