from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.dependencies import SESSION_COOKIE_NAME
from app.main import app
from app.models import Base, WorkspaceMembership


@pytest.fixture
def people_client() -> Iterator[tuple[TestClient, Engine]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    def override_get_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as database_session:
            yield database_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_workspace(
    client: TestClient, email: str, name: str
) -> tuple[str, UUID]:
    registration = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": "People Module Owner",
            "password": "people-module-secure-password",
            "workspace_name": name,
        },
    )
    assert registration.status_code == 201, registration.text
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None
    workspace = client.get(
        "/api/workspaces/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, UUID(workspace.json()["id"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_communication_channel_message_validation_and_workspace_isolation(
    people_client: tuple[TestClient, object],
) -> None:
    client, _engine = people_client
    token, workspace_id = create_workspace(
        client, "channels-owner@example.com", "Channels"
    )
    foreign_token, foreign_workspace_id = create_workspace(
        client, "channels-foreign@example.com", "Other Channels"
    )
    channel_path = f"/api/workspaces/{workspace_id}/communication/channels"
    channel = client.post(
        channel_path,
        json={"name": "  general  "},
        headers=auth(token),
    )
    duplicate = client.post(
        channel_path,
        json={"name": "GENERAL"},
        headers=auth(token),
    )
    message_path = f"{channel_path}/{channel.json()['id']}/messages"
    message = client.post(
        message_path,
        json={"body": "  Welcome  "},
        headers=auth(token),
    )
    messages = client.get(message_path, headers=auth(token))
    foreign_read = client.get(
        f"/api/workspaces/{foreign_workspace_id}/communication/channels/"
        f"{channel.json()['id']}/messages",
        headers=auth(foreign_token),
    )
    blank_message = client.post(
        message_path,
        json={"body": "  "},
        headers=auth(token),
    )

    assert channel.status_code == 201
    assert channel.json()["name"] == "general"
    assert duplicate.status_code == 409
    assert message.status_code == 201
    assert message.json()["body"] == "Welcome"
    assert [item["id"] for item in messages.json()] == [message.json()["id"]]
    assert foreign_read.status_code == 404
    assert blank_message.status_code == 422


def test_hr_workflows_enforce_admin_role_and_leave_state(
    people_client: tuple[TestClient, object],
) -> None:
    client, engine = people_client
    owner_token, workspace_id = create_workspace(
        client, "hr-owner@example.com", "People Operations"
    )
    member_token, _member_workspace_id = create_workspace(
        client, "hr-member@example.com", "Member Workspace"
    )
    member_id = UUID(
        client.get("/api/auth/me", headers=auth(member_token)).json()["id"]
    )
    with Session(engine) as database_session:
        database_session.add(
            WorkspaceMembership(
                workspace_id=workspace_id,
                user_id=member_id,
                role="member",
            )
        )
        database_session.commit()

    base = f"/api/workspaces/{workspace_id}/hr"
    denied = client.get(f"{base}/departments", headers=auth(member_token))
    department = client.post(
        f"{base}/departments",
        json={"name": "  Research  "},
        headers=auth(owner_token),
    )
    employee = client.post(
        f"{base}/employees",
        json={
            "first_name": "Avery",
            "last_name": "Morgan",
            "email": "avery@example.com",
            "department_id": department.json()["id"],
        },
        headers=auth(owner_token),
    )
    invalid_dates = client.post(
        f"{base}/leave-requests",
        json={
            "employee_id": employee.json()["id"],
            "start_date": "2026-11-20",
            "end_date": "2026-11-19",
        },
        headers=auth(owner_token),
    )
    leave_request = client.post(
        f"{base}/leave-requests",
        json={
            "employee_id": employee.json()["id"],
            "start_date": "2026-11-20",
            "end_date": "2026-11-21",
            "reason": "Personal leave",
        },
        headers=auth(owner_token),
    )
    review_path = f"{base}/leave-requests/{leave_request.json()['id']}"
    approved = client.patch(
        review_path,
        json={"status": "approved"},
        headers=auth(owner_token),
    )
    reviewed_again = client.patch(
        review_path,
        json={"status": "rejected"},
        headers=auth(owner_token),
    )

    assert denied.status_code == 403
    assert department.status_code == 201
    assert employee.status_code == 201
    assert invalid_dates.status_code == 422
    assert leave_request.status_code == 201
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by"] is not None
    assert reviewed_again.status_code == 409


def test_ats_initial_application_and_status_history(
    people_client: tuple[TestClient, object],
) -> None:
    client, _engine = people_client
    token, workspace_id = create_workspace(client, "ats-owner@example.com", "Hiring")
    base = f"/api/workspaces/{workspace_id}/ats"
    job = client.post(
        f"{base}/jobs",
        json={"title": "  Product designer  "},
        headers=auth(token),
    )
    candidate = client.post(
        f"{base}/candidates",
        json={
            "first_name": "Riley",
            "last_name": "Quinn",
            "email": "RILEY@example.com",
            "job_id": job.json()["id"],
        },
        headers=auth(token),
    )
    applications = client.get(f"{base}/applications", headers=auth(token))
    application_id = applications.json()[0]["id"]
    updated = client.patch(
        f"{base}/applications/{application_id}",
        json={"status": "screening"},
        headers=auth(token),
    )
    history = client.get(
        f"{base}/applications/{application_id}/history",
        headers=auth(token),
    )
    duplicate_candidate = client.post(
        f"{base}/candidates",
        json={
            "first_name": "Riley",
            "last_name": "Quinn",
            "email": "riley@example.com",
            "job_id": job.json()["id"],
        },
        headers=auth(token),
    )
    invalid_stage = client.patch(
        f"{base}/applications/{application_id}",
        json={"status": "background_check"},
        headers=auth(token),
    )

    assert job.status_code == 201
    assert candidate.status_code == 201
    assert candidate.json()["email"] == "riley@example.com"
    assert applications.status_code == 200
    assert applications.json()[0]["status"] == "applied"
    assert updated.json()["status"] == "screening"
    assert [(item["from_status"], item["to_status"]) for item in history.json()] == [
        ("applied", "screening"),
        (None, "applied"),
    ]
    assert duplicate_candidate.status_code == 409
    assert invalid_stage.status_code == 422
