from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import (
    CRMActivity,
    CRMNote,
    Company,
    Contact,
    Lead,
    User,
    WorkspaceMembership,
)
from app.schemas.crm import (
    ActivityResponse,
    CompanyCreate,
    CompanyPage,
    CompanyResponse,
    ContactCreate,
    ContactPage,
    ContactResponse,
    LeadCreate,
    LeadPage,
    LeadResponse,
    LeadUpdate,
    NoteCreate,
    NoteResponse,
    SortDirection,
    SortField,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/crm",
    tags=["CRM"],
    dependencies=[
        Depends(require_workspace_roles("owner", "admin", "member"))
    ],
)


def _authenticated_user_id(
    current_user: User = Depends(get_current_user),
) -> UUID:
    return current_user.id


@router.get("/companies", response_model=CompanyPage)
def list_companies(
    workspace_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> CompanyPage:
    query = select(Company).where(Company.workspace_id == workspace_id)
    if q and q.strip():
        pattern = _search_pattern(q)
        query = query.where(
            or_(
                Company.name.ilike(pattern, escape="\\"),
                Company.domain.ilike(pattern, escape="\\"),
                Company.industry.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Company.name, Company.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return CompanyPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    workspace_id: UUID,
    request: CompanyCreate,
    actor_id: UUID = Depends(_authenticated_user_id),
    db: Session = Depends(get_db),
) -> Company:
    company = Company(workspace_id=workspace_id, **request.model_dump())
    db.add(company)
    try:
        db.flush()
        db.add(
            CRMActivity(
                workspace_id=workspace_id,
                company_id=company.id,
                actor_id=actor_id,
                event_type="company_created",
                summary=f"Company '{company.name}' was created.",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_crm_companies_workspace_name" in str(exc.orig):
            raise _conflict(
                "company_exists", "A company with this name already exists."
            ) from None
        raise
    return company


@router.get("/contacts", response_model=ContactPage)
def list_contacts(
    workspace_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    company_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ContactPage:
    query = select(Contact).where(Contact.workspace_id == workspace_id)
    if company_id is not None:
        query = query.where(Contact.company_id == company_id)
    if q and q.strip():
        pattern = _search_pattern(q)
        query = query.outerjoin(Company, Contact.company_id == Company.id).where(
            or_(
                Contact.first_name.ilike(pattern, escape="\\"),
                Contact.last_name.ilike(pattern, escape="\\"),
                Contact.email.ilike(pattern, escape="\\"),
                Contact.job_title.ilike(pattern, escape="\\"),
                Company.name.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Contact.last_name, Contact.first_name, Contact.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ContactPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contact(
    workspace_id: UUID,
    request: ContactCreate,
    actor_id: UUID = Depends(_authenticated_user_id),
    db: Session = Depends(get_db),
) -> Contact:
    if request.company_id is not None:
        _require_company(db, workspace_id, request.company_id)
    contact = Contact(
        workspace_id=workspace_id,
        **request.model_dump(),
    )
    db.add(contact)
    try:
        db.flush()
        db.add(
            CRMActivity(
                workspace_id=workspace_id,
                contact_id=contact.id,
                actor_id=actor_id,
                event_type="contact_created",
                summary=(
                    f"Contact '{contact.first_name} {contact.last_name}' "
                    "was created."
                ),
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_crm_contacts_workspace_email" in str(exc.orig):
            raise _conflict(
                "contact_exists",
                "A contact with this email already exists in the workspace.",
            ) from None
        raise
    return contact


@router.get("/leads", response_model=LeadPage)
def list_leads(
    workspace_id: UUID,
    q: str | None = Query(default=None, max_length=100),
    stage: Literal["new", "qualified", "proposal", "won", "lost"] | None = None,
    sort_by: SortField = "created_at",
    sort_direction: SortDirection = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> LeadPage:
    query = (
        select(Lead)
        .outerjoin(Company, Lead.company_id == Company.id)
        .outerjoin(Contact, Lead.contact_id == Contact.id)
        .where(Lead.workspace_id == workspace_id)
    )
    if stage is not None:
        query = query.where(Lead.stage == stage)
    if q and q.strip():
        pattern = _search_pattern(q)
        query = query.where(
            or_(
                Lead.title.ilike(pattern, escape="\\"),
                Lead.source.ilike(pattern, escape="\\"),
                Company.name.ilike(pattern, escape="\\"),
                Contact.first_name.ilike(pattern, escape="\\"),
                Contact.last_name.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sort_column = getattr(Lead, sort_by)
    order_expression = (
        sort_column.asc() if sort_direction == "asc" else sort_column.desc()
    )
    items = db.scalars(
        query.order_by(order_expression, Lead.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return LeadPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/leads",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lead(
    workspace_id: UUID,
    request: LeadCreate,
    actor_id: UUID = Depends(_authenticated_user_id),
    db: Session = Depends(get_db),
) -> Lead:
    _validate_lead_relations(
        db, workspace_id, request.company_id, request.contact_id, request.assigned_to
    )
    lead = Lead(workspace_id=workspace_id, **request.model_dump())
    db.add(lead)
    db.flush()
    db.add(
        CRMActivity(
            workspace_id=workspace_id,
            lead_id=lead.id,
            actor_id=actor_id,
            event_type="lead_created",
            summary=f"Lead '{lead.title}' was created in the {lead.stage} stage.",
            to_stage=lead.stage,
        )
    )
    db.commit()
    return lead


@router.patch("/leads/{lead_id}", response_model=LeadResponse)
def update_lead(
    workspace_id: UUID,
    lead_id: UUID,
    request: LeadUpdate,
    actor_id: UUID = Depends(_authenticated_user_id),
    db: Session = Depends(get_db),
) -> Lead:
    lead = _get_lead(db, workspace_id, lead_id)
    changes = request.model_dump(exclude_unset=True)
    next_company_id = changes.get("company_id", lead.company_id)
    next_contact_id = changes.get("contact_id", lead.contact_id)
    next_assignee_id = changes.get("assigned_to", lead.assigned_to)
    _validate_lead_relations(
        db,
        workspace_id,
        next_company_id,
        next_contact_id,
        next_assignee_id,
    )
    previous_stage = lead.stage
    for field, value in changes.items():
        setattr(lead, field, value)

    if "stage" in changes and changes["stage"] != previous_stage:
        db.add(
            CRMActivity(
                workspace_id=workspace_id,
                lead_id=lead.id,
                actor_id=actor_id,
                event_type="lead_stage_changed",
                summary=(
                    f"Lead stage changed from {previous_stage} "
                    f"to {lead.stage}."
                ),
                from_stage=previous_stage,
                to_stage=lead.stage,
            )
        )
    db.commit()
    return lead


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def read_lead(
    workspace_id: UUID, lead_id: UUID, db: Session = Depends(get_db)
) -> Lead:
    return _get_lead(db, workspace_id, lead_id)


@router.get(
    "/leads/{lead_id}/notes",
    response_model=list[NoteResponse],
)
def list_lead_notes(
    workspace_id: UUID,
    lead_id: UUID,
    db: Session = Depends(get_db),
) -> list[CRMNote]:
    _get_lead(db, workspace_id, lead_id)
    return list(
        db.scalars(
            select(CRMNote)
            .where(
                CRMNote.workspace_id == workspace_id,
                CRMNote.lead_id == lead_id,
            )
            .order_by(CRMNote.created_at.desc(), CRMNote.id)
        ).all()
    )


@router.post(
    "/leads/{lead_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lead_note(
    workspace_id: UUID,
    lead_id: UUID,
    request: NoteCreate,
    actor_id: UUID = Depends(_authenticated_user_id),
    db: Session = Depends(get_db),
) -> CRMNote:
    lead = _get_lead(db, workspace_id, lead_id)
    note = CRMNote(
        workspace_id=workspace_id,
        lead_id=lead.id,
        author_id=actor_id,
        body=request.body,
    )
    db.add(note)
    db.flush()
    db.add(
        CRMActivity(
            workspace_id=workspace_id,
            lead_id=lead.id,
            actor_id=actor_id,
            event_type="lead_note_added",
            summary="A note was added to the lead.",
        )
    )
    db.commit()
    return note


@router.get(
    "/leads/{lead_id}/activities",
    response_model=list[ActivityResponse],
)
def list_lead_activities(
    workspace_id: UUID,
    lead_id: UUID,
    db: Session = Depends(get_db),
) -> list[CRMActivity]:
    _get_lead(db, workspace_id, lead_id)
    return list(
        db.scalars(
            select(CRMActivity)
            .where(
                CRMActivity.workspace_id == workspace_id,
                CRMActivity.lead_id == lead_id,
            )
            .order_by(CRMActivity.created_at.desc(), CRMActivity.id)
        ).all()
    )


def _get_lead(db: Session, workspace_id: UUID, lead_id: UUID) -> Lead:
    lead = db.scalar(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.workspace_id == workspace_id,
        )
    )
    if lead is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "lead_not_found", "message": "The lead was not found."},
        )
    return lead


def _require_company(
    db: Session, workspace_id: UUID, company_id: UUID
) -> Company:
    company = db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.workspace_id == workspace_id,
        )
    )
    if company is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "company_not_found",
                "message": "The company was not found in this workspace.",
            },
        )
    return company


def _validate_lead_relations(
    db: Session,
    workspace_id: UUID,
    company_id: UUID | None,
    contact_id: UUID | None,
    assigned_to: UUID | None,
) -> None:
    if company_id is not None:
        _require_company(db, workspace_id, company_id)
    contact: Contact | None = None
    if contact_id is not None:
        contact = db.scalar(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.workspace_id == workspace_id,
            )
        )
        if contact is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "contact_not_found",
                    "message": "The contact was not found in this workspace.",
                },
            )
    if (
        company_id is not None
        and contact is not None
        and contact.company_id not in (None, company_id)
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "crm_relationship_mismatch",
                "message": "The contact does not belong to the selected company.",
            },
        )
    if assigned_to is not None:
        is_member = db.scalar(
            select(WorkspaceMembership.user_id).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == assigned_to,
            )
        )
        if is_member is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "assignee_not_in_workspace",
                    "message": "The assignee must belong to this workspace.",
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


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": code, "message": message},
    )
