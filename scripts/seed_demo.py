"""Create an idempotent synthetic WorkSphere demo workspace for local use."""

import os
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    ApplicationHistory,
    Candidate,
    Channel,
    ChannelMessage,
    Company,
    Contact,
    CRMActivity,
    CRMNote,
    Department,
    Employee,
    JobApplication,
    JobOpening,
    Lead,
    LeaveRequest,
    Project,
    ProjectActivity,
    ProjectTask,
    TaskComment,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.security import hash_password, verify_password

DEMO_EMAIL = "demo@example.com"
WORKSPACE_SLUG = "worksphere-demo"


def ensure_local_database(database_url: str) -> None:
    parsed = make_url(database_url)
    if parsed.get_backend_name() == "sqlite":
        return
    if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Demo seeding is restricted to a local database host.")


def seed_demo(session: Session, password: str) -> None:
    user = session.scalar(select(User).where(User.email == DEMO_EMAIL))
    workspace = session.scalar(
        select(Workspace).where(Workspace.slug == WORKSPACE_SLUG)
    )
    if (user is None) != (workspace is None):
        raise ValueError(
            "Demo account and workspace must either both exist or both be absent."
        )

    if user is None:
        user = User(
            email=DEMO_EMAIL,
            display_name="Demo Owner",
            password_hash=hash_password(password),
        )
        workspace = Workspace(name="WorkSphere Demo", slug=WORKSPACE_SLUG)
        session.add_all([user, workspace])
        session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
        )
        session.flush()
    else:
        if not user.is_active:
            raise ValueError("The existing demo account is inactive.")
        if not verify_password(password, user.password_hash):
            raise ValueError(
                "The supplied password does not match the existing demo account."
            )
        membership = session.get(
            WorkspaceMembership, (workspace.id, user.id)
        )
        if membership is None or membership.role != "owner":
            raise ValueError(
                "The existing demo account must own the demo workspace."
            )

    assert user is not None and workspace is not None
    workspace_id = workspace.id

    company = session.scalar(
        select(Company).where(
            Company.workspace_id == workspace_id,
            Company.name == "Northstar Fieldworks",
        )
    )
    if company is None:
        company = Company(
            workspace_id=workspace_id,
            name="Northstar Fieldworks",
            domain="northstar.example",
            industry="Renewable energy",
        )
        session.add(company)
        session.flush()

    contact = session.scalar(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.email == "jordan.lee@northstar.example",
        )
    )
    if contact is None:
        contact = Contact(
            workspace_id=workspace_id,
            company_id=company.id,
            first_name="Jordan",
            last_name="Lee",
            email="jordan.lee@northstar.example",
            job_title="Operations Director",
        )
        session.add(contact)
        session.flush()

    lead = session.scalar(
        select(Lead).where(
            Lead.workspace_id == workspace_id,
            Lead.title == "Regional rollout planning",
        )
    )
    if lead is None:
        lead = Lead(
            workspace_id=workspace_id,
            company_id=company.id,
            contact_id=contact.id,
            assigned_to=user.id,
            title="Regional rollout planning",
            stage="qualified",
            source="Partner referral",
            estimated_value=Decimal("24500.00"),
        )
        session.add(lead)
        session.flush()
    if session.scalar(
        select(CRMNote.id).where(
            CRMNote.workspace_id == workspace_id,
            CRMNote.lead_id == lead.id,
            CRMNote.body == "Prepare a phased rollout proposal for the next review.",
        )
    ) is None:
        session.add(
            CRMNote(
                workspace_id=workspace_id,
                lead_id=lead.id,
                author_id=user.id,
                body="Prepare a phased rollout proposal for the next review.",
            )
        )
    if session.scalar(
        select(CRMActivity.id).where(
            CRMActivity.workspace_id == workspace_id,
            CRMActivity.lead_id == lead.id,
            CRMActivity.event_type == "demo_seeded",
        )
    ) is None:
        session.add(
            CRMActivity(
                workspace_id=workspace_id,
                lead_id=lead.id,
                actor_id=user.id,
                event_type="demo_seeded",
                summary="Synthetic lead record is ready for review.",
            )
        )

    project = session.scalar(
        select(Project).where(
            Project.workspace_id == workspace_id,
            Project.name == "Field operations launch",
        )
    )
    if project is None:
        project = Project(
            workspace_id=workspace_id,
            created_by=user.id,
            name="Field operations launch",
            description="Coordinate a synthetic regional service rollout.",
        )
        session.add(project)
        session.flush()
        session.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                actor_id=user.id,
                event_type="project_created",
                summary="Project 'Field operations launch' was created.",
            )
        )

    task = session.scalar(
        select(ProjectTask).where(
            ProjectTask.workspace_id == workspace_id,
            ProjectTask.project_id == project.id,
            ProjectTask.title == "Confirm site readiness",
        )
    )
    if task is None:
        task = ProjectTask(
            workspace_id=workspace_id,
            project_id=project.id,
            created_by=user.id,
            assigned_to=user.id,
            title="Confirm site readiness",
            description="Collect readiness checks from the pilot locations.",
            status="in_progress",
            priority="high",
            due_date=date(2027, 1, 15),
        )
        session.add(task)
        session.flush()
        session.add(
            ProjectActivity(
                workspace_id=workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor_id=user.id,
                event_type="task_created",
                summary="Task 'Confirm site readiness' was created.",
            )
        )
    if session.scalar(
        select(TaskComment.id).where(
            TaskComment.workspace_id == workspace_id,
            TaskComment.task_id == task.id,
            TaskComment.body == "Pilot checklist is in progress.",
        )
    ) is None:
        session.add(
            TaskComment(
                workspace_id=workspace_id,
                task_id=task.id,
                author_id=user.id,
                body="Pilot checklist is in progress.",
            )
        )

    channel = session.scalar(
        select(Channel).where(
            Channel.workspace_id == workspace_id,
            Channel.name == "general",
        )
    )
    if channel is None:
        channel = Channel(
            workspace_id=workspace_id,
            created_by=user.id,
            name="general",
            description="Synthetic demo team updates.",
        )
        session.add(channel)
        session.flush()
    if session.scalar(
        select(ChannelMessage.id).where(
            ChannelMessage.workspace_id == workspace_id,
            ChannelMessage.channel_id == channel.id,
            ChannelMessage.body == "Welcome to the WorkSphere demo workspace.",
        )
    ) is None:
        session.add(
            ChannelMessage(
                workspace_id=workspace_id,
                channel_id=channel.id,
                author_id=user.id,
                body="Welcome to the WorkSphere demo workspace.",
            )
        )

    department = session.scalar(
        select(Department).where(
            Department.workspace_id == workspace_id,
            Department.name == "Field Operations",
        )
    )
    if department is None:
        department = Department(
            workspace_id=workspace_id,
            name="Field Operations",
        )
        session.add(department)
        session.flush()
    employee = session.scalar(
        select(Employee).where(
            Employee.workspace_id == workspace_id,
            Employee.email == "casey.park@example.com",
        )
    )
    if employee is None:
        employee = Employee(
            workspace_id=workspace_id,
            department_id=department.id,
            first_name="Casey",
            last_name="Park",
            email="casey.park@example.com",
            job_title="Field Coordinator",
            start_date=date(2025, 3, 10),
        )
        session.add(employee)
        session.flush()
    if session.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.workspace_id == workspace_id,
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.start_date == date(2027, 2, 8),
            LeaveRequest.end_date == date(2027, 2, 9),
        )
    ) is None:
        session.add(
            LeaveRequest(
                workspace_id=workspace_id,
                employee_id=employee.id,
                start_date=date(2027, 2, 8),
                end_date=date(2027, 2, 9),
                reason="Synthetic sample request",
            )
        )

    job = session.scalar(
        select(JobOpening).where(
            JobOpening.workspace_id == workspace_id,
            JobOpening.title == "Implementation Specialist",
        )
    )
    if job is None:
        job = JobOpening(
            workspace_id=workspace_id,
            created_by=user.id,
            title="Implementation Specialist",
            department="Field Operations",
            description="Support synthetic customer onboarding scenarios.",
        )
        session.add(job)
        session.flush()
    candidate = session.scalar(
        select(Candidate).where(
            Candidate.workspace_id == workspace_id,
            Candidate.email == "sam.taylor@example.com",
        )
    )
    if candidate is None:
        candidate = Candidate(
            workspace_id=workspace_id,
            first_name="Sam",
            last_name="Taylor",
            email="sam.taylor@example.com",
        )
        session.add(candidate)
        session.flush()
    application = session.scalar(
        select(JobApplication).where(
            JobApplication.workspace_id == workspace_id,
            JobApplication.candidate_id == candidate.id,
            JobApplication.job_id == job.id,
        )
    )
    if application is None:
        application = JobApplication(
            workspace_id=workspace_id,
            candidate_id=candidate.id,
            job_id=job.id,
        )
        session.add(application)
        session.flush()
    if session.scalar(
        select(ApplicationHistory.id).where(
            ApplicationHistory.workspace_id == workspace_id,
            ApplicationHistory.application_id == application.id,
            ApplicationHistory.from_status.is_(None),
            ApplicationHistory.to_status == application.status,
        )
    ) is None:
        session.add(
            ApplicationHistory(
                workspace_id=workspace_id,
                application_id=application.id,
                to_status=application.status,
            )
        )

    session.commit()


def main() -> int:
    if os.getenv("WORKSPHERE_ENABLE_DEMO_SEED") != "true":
        print(
            "Refusing to seed: set WORKSPHERE_ENABLE_DEMO_SEED=true explicitly.",
            file=sys.stderr,
        )
        return 2
    password = os.getenv("WORKSPHERE_DEMO_PASSWORD", "")
    if len(password) < 12:
        print(
            "Set WORKSPHERE_DEMO_PASSWORD to a local-only password of at least 12 characters.",
            file=sys.stderr,
        )
        return 2
    try:
        ensure_local_database(settings.database_url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with Session(engine, expire_on_commit=False) as session:
            seed_demo(session, password)
    finally:
        engine.dispose()
    print(
        "Synthetic demo workspace is ready. Sign in with demo@example.com and "
        "the local-only WORKSPHERE_DEMO_PASSWORD you supplied."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
