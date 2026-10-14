from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.assistant import get_project_summary_provider
from app.database import get_db
from app.dependencies import SESSION_COOKIE_NAME
from app.main import app
from app.models import Base
from app.services.project_summary import (
    ProjectSummaryContext,
    SummaryProviderError,
)


@pytest.fixture
def project_client() -> Iterator[TestClient]:
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
        yield client
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
            "display_name": "Project Owner",
            "password": "project-owner-secure-password",
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
    assert workspace.status_code == 200
    return token, UUID(workspace.json()["id"])


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_project(
    client: TestClient, workspace_id: UUID, token: str, name: str = "Website refresh"
) -> dict:
    response = client.post(
        f"/api/workspaces/{workspace_id}/projects",
        json={"name": name, "description": "  Rework the customer site.  "},
        headers=headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_task(
    client: TestClient,
    workspace_id: UUID,
    project_id: str,
    token: str,
    *,
    title: str = "Prepare content",
    status: str = "todo",
    priority: str = "medium",
    due_date: str | None = None,
    assigned_to: str | None = None,
):
    return client.post(
        f"/api/workspaces/{workspace_id}/projects/{project_id}/tasks",
        json={
            "title": title,
            "status": status,
            "priority": priority,
            "due_date": due_date,
            "assigned_to": assigned_to,
        },
        headers=headers(token),
    )


def test_projects_tasks_search_and_filters_are_workspace_scoped(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-owner@example.com", "Project Alpha"
    )
    project = create_project(project_client, workspace_id, token)
    first = create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        title="Draft launch copy",
        priority="high",
        due_date="2026-11-01",
    )
    second = create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        title="Review analytics",
        status="in_progress",
    )
    project_client.post(
        f"/api/workspaces/{workspace_id}/projects",
        json={"name": "Operations planning"},
        headers=headers(token),
    )

    project_page = project_client.get(
        f"/api/workspaces/{workspace_id}/projects",
        params={"q": "website", "page": 1, "page_size": 1},
        headers=headers(token),
    )
    task_page = project_client.get(
        f"/api/workspaces/{workspace_id}/projects/{project['id']}/tasks",
        params={"task_status": "todo", "priority": "high"},
        headers=headers(token),
    )
    searched_tasks = project_client.get(
        f"/api/workspaces/{workspace_id}/projects/{project['id']}/tasks",
        params={"q": "analytics"},
        headers=headers(token),
    )

    assert project_page.status_code == 200
    assert project_page.json()["total"] == 1
    assert project_page.json()["items"][0]["id"] == project["id"]
    assert first.status_code == 201
    assert second.status_code == 201
    assert task_page.json()["total"] == 1
    assert task_page.json()["items"][0]["id"] == first.json()["id"]
    assert searched_tasks.json()["items"][0]["id"] == second.json()["id"]


def test_status_changes_comments_and_activity_history(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-history@example.com", "Project History"
    )
    project = create_project(project_client, workspace_id, token)
    task = create_task(project_client, workspace_id, project["id"], token)
    project_path = f"/api/workspaces/{workspace_id}/projects/{project['id']}"
    task_path = f"{project_path}/tasks/{task.json()['id']}"

    project_update = project_client.patch(
        project_path,
        json={"status": "on_hold"},
        headers=headers(token),
    )
    task_update = project_client.patch(
        task_path,
        json={"status": "done", "priority": "high"},
        headers=headers(token),
    )
    comment = project_client.post(
        f"{task_path}/comments",
        json={"body": "  Approved by the content team.  "},
        headers=headers(token),
    )
    comments = project_client.get(f"{task_path}/comments", headers=headers(token))
    activities = project_client.get(
        f"{project_path}/activities", headers=headers(token)
    )

    assert project_update.json()["status"] == "on_hold"
    assert task_update.json()["status"] == "done"
    assert task_update.json()["priority"] == "high"
    assert comment.status_code == 201
    assert comment.json()["body"] == "Approved by the content team."
    assert comments.json()[0]["id"] == comment.json()["id"]
    assert {item["event_type"] for item in activities.json()} == {
        "project_created",
        "task_created",
        "project_status_changed",
        "task_status_changed",
        "task_updated",
        "task_comment_added",
    }


def test_invalid_status_assignee_and_cross_workspace_access_are_rejected(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-alpha@example.com", "Project Alpha"
    )
    foreign_token, foreign_workspace_id = create_workspace(
        project_client, "project-beta@example.com", "Project Beta"
    )
    project = create_project(project_client, workspace_id, token)
    foreign_project = create_project(
        project_client, foreign_workspace_id, foreign_token
    )
    task = create_task(project_client, workspace_id, project["id"], token)
    owner = project_client.get("/api/auth/me", headers=headers(token)).json()
    roster = project_client.get(
        f"/api/workspaces/{workspace_id}/projects/members",
        headers=headers(token),
    )
    assigned_task = create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        title="Assigned correctly",
        assigned_to=owner["id"],
    )

    invalid_status = project_client.patch(
        f"/api/workspaces/{workspace_id}/projects/{project['id']}/tasks/{task.json()['id']}",
        json={"status": "blocked"},
        headers=headers(token),
    )
    invalid_assignee = create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        assigned_to=str(UUID(int=1)),
    )
    foreign_project_read = project_client.get(
        f"/api/workspaces/{workspace_id}/projects/{foreign_project['id']}/tasks",
        headers=headers(token),
    )
    project_client.cookies.clear()
    unauthenticated = project_client.get(
        f"/api/workspaces/{workspace_id}/projects"
    )
    invalid_null_status = project_client.patch(
        f"/api/workspaces/{workspace_id}/projects/{project['id']}",
        json={"status": None},
        headers=headers(token),
    )

    assert invalid_status.status_code == 422
    assert invalid_assignee.status_code == 422
    assert invalid_assignee.json()["detail"]["code"] == "assignee_not_in_workspace"
    assert assigned_task.status_code == 201
    assert assigned_task.json()["assigned_to"] == owner["id"]
    assert roster.json() == [{"id": owner["id"], "display_name": "Project Owner"}]
    assert invalid_null_status.status_code == 422
    assert foreign_project_read.status_code == 404
    assert unauthenticated.status_code == 401


def test_project_status_draft_uses_project_scoped_context_and_mock_provider(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-draft@example.com", "Project Draft"
    )
    project = create_project(project_client, workspace_id, token)
    create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        title="Ship the release",
        status="done",
    )
    create_task(
        project_client,
        workspace_id,
        project["id"],
        token,
        title="Review analytics",
        status="in_progress",
    )

    response = project_client.post(
        f"/api/workspaces/{workspace_id}/assistant/projects/{project['id']}/status-draft",
        headers=headers(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "mock"
    assert "Website refresh is active" in response.json()["draft"]
    assert "1 of 2 tasks are complete" in response.json()["draft"]
    assert "was created." in response.json()["draft"].lower()
    assert "Review and edit" in response.json()["disclaimer"]


def test_project_status_draft_rejects_unauthorized_or_foreign_projects(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-draft-owner@example.com", "Draft Owner"
    )
    foreign_token, foreign_workspace_id = create_workspace(
        project_client, "project-draft-foreign@example.com", "Draft Foreign"
    )
    project = create_project(
        project_client, foreign_workspace_id, foreign_token
    )
    contexts: list[ProjectSummaryContext] = []

    class SpyProvider:
        name = "mock"

        def create_draft(self, context: ProjectSummaryContext) -> str:
            contexts.append(context)
            return "Draft"

    app.dependency_overrides[get_project_summary_provider] = lambda: SpyProvider()
    path = (
        f"/api/workspaces/{workspace_id}/assistant/projects/"
        f"{project['id']}/status-draft"
    )
    foreign_response = project_client.post(path, headers=headers(token))
    project_client.cookies.clear()
    unauthenticated = project_client.post(path)

    assert foreign_response.status_code == 404
    assert unauthenticated.status_code == 401
    assert contexts == []


def test_project_status_draft_reports_provider_and_output_failures(
    project_client: TestClient,
) -> None:
    token, workspace_id = create_workspace(
        project_client, "project-draft-errors@example.com", "Draft Errors"
    )
    project = create_project(project_client, workspace_id, token)
    path = (
        f"/api/workspaces/{workspace_id}/assistant/projects/"
        f"{project['id']}/status-draft"
    )

    class InvalidProvider:
        name = "mock"

        def create_draft(self, _context: ProjectSummaryContext) -> str:
            return "  "

    app.dependency_overrides[get_project_summary_provider] = lambda: InvalidProvider()
    invalid_output = project_client.post(path, headers=headers(token))

    class UnavailableProvider:
        name = "mock"

        def create_draft(self, _context: ProjectSummaryContext) -> str:
            raise SummaryProviderError("Provider is unavailable.")

    app.dependency_overrides[get_project_summary_provider] = (
        lambda: UnavailableProvider()
    )
    unavailable = project_client.post(path, headers=headers(token))

    assert invalid_output.status_code == 502
    assert invalid_output.json()["detail"]["code"] == "assistant_invalid_output"
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["code"] == "assistant_unavailable"
