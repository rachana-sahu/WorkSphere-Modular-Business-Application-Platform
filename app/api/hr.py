from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_workspace_roles
from app.models import Department, Employee, LeaveRequest, User
from app.schemas.hr import (
    DepartmentCreate,
    DepartmentResponse,
    EmployeeCreate,
    EmployeeResponse,
    LeaveCreate,
    LeaveResponse,
    LeaveReview,
)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/hr",
    tags=["HR"],
    dependencies=[Depends(require_workspace_roles("owner", "admin"))],
)


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(workspace_id: UUID, db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Department)
            .where(Department.workspace_id == workspace_id)
            .order_by(Department.name, Department.id)
        ).all()
    )


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    workspace_id: UUID,
    request: DepartmentCreate,
    db: Session = Depends(get_db),
) -> Department:
    department = Department(workspace_id=workspace_id, name=request.name)
    db.add(department)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "department_exists",
                "message": "A department with this name already exists.",
            },
        ) from exc
    return department


@router.get("/employees", response_model=list[EmployeeResponse])
def list_employees(workspace_id: UUID, db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.workspace_id == workspace_id)
            .order_by(Employee.last_name, Employee.first_name, Employee.id)
        ).all()
    )


@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    workspace_id: UUID,
    request: EmployeeCreate,
    db: Session = Depends(get_db),
) -> Employee:
    if request.department_id is not None:
        _get_department(db, workspace_id, request.department_id)
    employee = Employee(workspace_id=workspace_id, **request.model_dump())
    db.add(employee)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "employee_exists",
                "message": "An employee with this email already exists.",
            },
        ) from exc
    return employee


@router.get("/leave-requests", response_model=list[LeaveResponse])
def list_leave_requests(
    workspace_id: UUID,
    status_filter: Literal["pending", "approved", "rejected"] | None = None,
    db: Session = Depends(get_db),
):
    query = select(LeaveRequest).where(LeaveRequest.workspace_id == workspace_id)
    if status_filter is not None:
        query = query.where(LeaveRequest.status == status_filter)
    return list(
        db.scalars(
            query.order_by(LeaveRequest.created_at.desc(), LeaveRequest.id)
        ).all()
    )


@router.post(
    "/leave-requests",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_leave_request(
    workspace_id: UUID,
    request: LeaveCreate,
    db: Session = Depends(get_db),
) -> LeaveRequest:
    employee = db.scalar(
        select(Employee).where(
            Employee.id == request.employee_id,
            Employee.workspace_id == workspace_id,
        )
    )
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "employee_not_found",
                "message": "The employee was not found in this workspace.",
            },
        )
    leave_request = LeaveRequest(
        workspace_id=workspace_id,
        **request.model_dump(),
    )
    db.add(leave_request)
    db.commit()
    return leave_request


@router.patch("/leave-requests/{request_id}", response_model=LeaveResponse)
def review_leave_request(
    workspace_id: UUID,
    request_id: UUID,
    request: LeaveReview,
    reviewer: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaveRequest:
    leave_request = db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.id == request_id,
            LeaveRequest.workspace_id == workspace_id,
        )
    )
    if leave_request is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "leave_request_not_found",
                "message": "The leave request was not found.",
            },
        )
    if leave_request.status != "pending":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "leave_request_already_reviewed",
                "message": "Only pending leave requests can be reviewed.",
            },
        )
    leave_request.status = request.status
    leave_request.reviewed_by = reviewer.id
    db.commit()
    return leave_request


def _get_department(db: Session, workspace_id: UUID, department_id: UUID) -> Department:
    department = db.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.workspace_id == workspace_id,
        )
    )
    if department is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "department_not_found",
                "message": "The department was not found in this workspace.",
            },
        )
    return department
