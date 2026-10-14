from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import (
    ApplicationHistory,
    Candidate,
    JobApplication,
    JobOpening,
    User,
)
from app.schemas.ats import (
    ApplicationHistoryResponse,
    ApplicationResponse,
    ApplicationUpdate,
    CandidateCreate,
    CandidateResponse,
    JobCreate,
    JobResponse,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/ats",
    tags=["Applicant tracking"],
    dependencies=[Depends(require_workspace_roles("owner", "admin", "member"))],
)


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    workspace_id: UUID,
    job_status: Literal["open", "paused", "closed"] | None = None,
    db: Session = Depends(get_db),
):
    query = select(JobOpening).where(JobOpening.workspace_id == workspace_id)
    if job_status is not None:
        query = query.where(JobOpening.status == job_status)
    return list(
        db.scalars(query.order_by(JobOpening.created_at.desc(), JobOpening.id)).all()
    )


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    workspace_id: UUID,
    request: JobCreate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOpening:
    job = JobOpening(
        workspace_id=workspace_id,
        created_by=actor.id,
        **request.model_dump(),
    )
    db.add(job)
    db.commit()
    return job


@router.post(
    "/candidates",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    workspace_id: UUID,
    request: CandidateCreate,
    db: Session = Depends(get_db),
) -> Candidate:
    _get_job(db, workspace_id, request.job_id)
    existing = db.scalar(
        select(Candidate).where(
            Candidate.workspace_id == workspace_id,
            Candidate.email.ilike(str(request.email)),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "candidate_exists",
                "message": "A candidate with this email already exists.",
            },
        )
    candidate = Candidate(
        workspace_id=workspace_id,
        first_name=request.first_name,
        last_name=request.last_name,
        email=str(request.email),
        phone=request.phone,
    )
    db.add(candidate)
    try:
        db.flush()
        application = JobApplication(
            workspace_id=workspace_id,
            candidate_id=candidate.id,
            job_id=request.job_id,
        )
        db.add(application)
        db.flush()
        db.add(
            ApplicationHistory(
                workspace_id=workspace_id,
                application_id=application.id,
                to_status=application.status,
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "application_exists",
                "message": "This candidate already applied for this job.",
            },
        ) from exc
    return candidate


@router.get("/candidates", response_model=list[CandidateResponse])
def list_candidates(
    workspace_id: UUID,
    db: Session = Depends(get_db),
) -> list[Candidate]:
    return list(
        db.scalars(
            select(Candidate)
            .where(Candidate.workspace_id == workspace_id)
            .order_by(Candidate.last_name, Candidate.first_name, Candidate.id)
        ).all()
    )


@router.get("/applications", response_model=list[ApplicationResponse])
def list_applications(
    workspace_id: UUID,
    application_status: Literal[
        "applied", "screening", "interview", "offer", "hired", "rejected"
    ]
    | None = None,
    job_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    query = select(JobApplication).where(JobApplication.workspace_id == workspace_id)
    if application_status is not None:
        query = query.where(JobApplication.status == application_status)
    if job_id is not None:
        query = query.where(JobApplication.job_id == job_id)
    return list(
        db.scalars(
            query.order_by(JobApplication.updated_at.desc(), JobApplication.id)
        ).all()
    )


@router.patch(
    "/applications/{application_id}", response_model=ApplicationResponse
)
def update_application(
    workspace_id: UUID,
    application_id: UUID,
    request: ApplicationUpdate,
    actor: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobApplication:
    application = db.scalar(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.workspace_id == workspace_id,
        )
    )
    if application is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "application_not_found",
                "message": "The application was not found.",
            },
        )
    previous_status = application.status
    if previous_status != request.status:
        application.status = request.status
        db.add(
            ApplicationHistory(
                workspace_id=workspace_id,
                application_id=application.id,
                actor_id=actor.id,
                from_status=previous_status,
                to_status=request.status,
            )
        )
        db.commit()
    return application


@router.get(
    "/applications/{application_id}/history",
    response_model=list[ApplicationHistoryResponse],
)
def list_application_history(
    workspace_id: UUID,
    application_id: UUID,
    db: Session = Depends(get_db),
) -> list[ApplicationHistory]:
    if db.scalar(
        select(JobApplication.id).where(
            JobApplication.id == application_id,
            JobApplication.workspace_id == workspace_id,
        )
    ) is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "application_not_found",
                "message": "The application was not found.",
            },
        )
    return list(
        db.scalars(
            select(ApplicationHistory)
            .where(
                ApplicationHistory.workspace_id == workspace_id,
                ApplicationHistory.application_id == application_id,
            )
            .order_by(ApplicationHistory.created_at.desc(), ApplicationHistory.id)
        ).all()
    )


def _get_job(db: Session, workspace_id: UUID, job_id: UUID) -> JobOpening:
    job = db.scalar(
        select(JobOpening).where(
            JobOpening.id == job_id,
            JobOpening.workspace_id == workspace_id,
        )
    )
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "job_not_found", "message": "The job opening was not found."},
        )
    if job.status != "open":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "job_not_open",
                "message": "Applications can only be created for open job postings.",
            },
        )
    return job
