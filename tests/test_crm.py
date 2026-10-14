from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.dependencies import SESSION_COOKIE_NAME
from app.main import app
from app.models import (
    Base,
    CRMActivity,
    CRMNote,
    Lead,
    User,
)
from app.security import hash_password


@pytest.fixture
def crm_client() -> Iterator[tuple[TestClient, Session]]:
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
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client, Session(engine, expire_on_commit=False) as db:
        yield client, db
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_workspace_session(
    client: TestClient, email: str, workspace_name: str
) -> tuple[str, UUID]:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": "CRM Owner",
            "password": "crm-owner-secure-password",
            "workspace_name": workspace_name,
        },
    )
    assert response.status_code == 201, response.text
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None
    workspace = client.get(
        "/api/workspaces/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert workspace.status_code == 200
    return token, UUID(workspace.json()["id"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_company(client: TestClient, workspace_id: UUID, token: str, name: str):
    response = client.post(
        f"/api/workspaces/{workspace_id}/crm/companies",
        json={"name": name, "industry": "Software"},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_contact(
    client: TestClient,
    workspace_id: UUID,
    token: str,
    *,
    email: str = "alex@example.com",
    company_id: str | None = None,
):
    return client.post(
        f"/api/workspaces/{workspace_id}/crm/contacts",
        json={
            "first_name": "Alex",
            "last_name": "Rivera",
            "email": email,
            "job_title": "Director",
            "company_id": company_id,
        },
        headers=auth(token),
    )


def create_lead(
    client: TestClient,
    workspace_id: UUID,
    token: str,
    *,
    title: str = "Pilot program",
    stage: str = "new",
    company_id: str | None = None,
    contact_id: str | None = None,
    estimated_value: int = 12000,
):
    return client.post(
        f"/api/workspaces/{workspace_id}/crm/leads",
        json={
            "title": title,
            "stage": stage,
            "estimated_value": estimated_value,
            "company_id": company_id,
            "contact_id": contact_id,
        },
        headers=auth(token),
    )


def test_crm_creation_search_and_pagination_are_workspace_scoped(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, _db = crm_client
    token, workspace_id = create_workspace_session(
        client, "crm-owner@example.com", "CRM Alpha"
    )
    company = create_company(client, workspace_id, token, "Northwind Labs")
    contact = create_contact(
        client, workspace_id, token, company_id=company["id"]
    )
    assert contact.status_code == 201, contact.text
    lead = create_lead(
        client,
        workspace_id,
        token,
        title="Northwind discovery",
        company_id=company["id"],
        contact_id=contact.json()["id"],
    )
    assert lead.status_code == 201, lead.text
    create_lead(client, workspace_id, token, title="Retail expansion")

    search = client.get(
        f"/api/workspaces/{workspace_id}/crm/leads",
        params={"q": "northwind", "page": 1, "page_size": 1},
        headers=auth(token),
    )
    page = client.get(
        f"/api/workspaces/{workspace_id}/crm/leads",
        params={"page": 2, "page_size": 1, "sort_by": "title"},
        headers=auth(token),
    )
    companies = client.get(
        f"/api/workspaces/{workspace_id}/crm/companies",
        params={"q": "labs"},
        headers=auth(token),
    )
    contacts = client.get(
        f"/api/workspaces/{workspace_id}/crm/contacts",
        params={"company_id": company["id"], "q": "alex"},
        headers=auth(token),
    )

    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["id"] == lead.json()["id"]
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert companies.json()["total"] == 1
    assert contacts.json()["total"] == 1


def test_duplicate_company_name_and_contact_email_return_conflict(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, _db = crm_client
    token, workspace_id = create_workspace_session(
        client, "crm-owner@example.com", "CRM Alpha"
    )
    create_company(client, workspace_id, token, "Northwind Labs")

    duplicate_company = client.post(
        f"/api/workspaces/{workspace_id}/crm/companies",
        json={"name": "  NORTHWIND labs  "},
        headers=auth(token),
    )
    create_contact(client, workspace_id, token)
    duplicate_contact = create_contact(
        client, workspace_id, token, email="ALEX@EXAMPLE.COM"
    )

    assert duplicate_company.status_code == 409
    assert duplicate_company.json()["detail"]["code"] == "company_exists"
    assert duplicate_contact.status_code == 409
    assert duplicate_contact.json()["detail"]["code"] == "contact_exists"


def test_lead_stages_are_validated_and_filtered(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, _db = crm_client
    token, workspace_id = create_workspace_session(
        client, "crm-owner@example.com", "CRM Alpha"
    )
    create_lead(client, workspace_id, token, title="Qualified deal", stage="qualified")

    filtered = client.get(
        f"/api/workspaces/{workspace_id}/crm/leads",
        params={"stage": "qualified"},
        headers=auth(token),
    )
    invalid_filter = client.get(
        f"/api/workspaces/{workspace_id}/crm/leads",
        params={"stage": "pending"},
        headers=auth(token),
    )
    invalid_stage = create_lead(
        client, workspace_id, token, title="Invalid", stage="pending"
    )

    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert invalid_filter.status_code == 422
    assert invalid_stage.status_code == 422


def test_stage_changes_notes_and_history_are_recorded_atomically(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, db = crm_client
    token, workspace_id = create_workspace_session(
        client, "crm-owner@example.com", "CRM Alpha"
    )
    lead = create_lead(client, workspace_id, token)
    lead_id = lead.json()["id"]
    base_path = f"/api/workspaces/{workspace_id}/crm/leads/{lead_id}"

    update = client.patch(
        base_path,
        json={"stage": "qualified"},
        headers=auth(token),
    )
    note = client.post(
        f"{base_path}/notes",
        json={"body": "  Spoke with the buyer; schedule a follow-up.  "},
        headers=auth(token),
    )
    notes = client.get(f"{base_path}/notes", headers=auth(token))
    activities = client.get(f"{base_path}/activities", headers=auth(token))

    assert update.status_code == 200
    assert update.json()["stage"] == "qualified"
    assert note.status_code == 201
    assert note.json()["body"] == "Spoke with the buyer; schedule a follow-up."
    assert notes.json()[0]["id"] == note.json()["id"]
    assert [item["event_type"] for item in activities.json()] == [
        "lead_note_added",
        "lead_stage_changed",
        "lead_created",
    ]
    assert activities.json()[1]["from_stage"] == "new"
    assert activities.json()[1]["to_stage"] == "qualified"
    assert db.scalar(
        select(func.count()).select_from(CRMNote).where(
            CRMNote.lead_id == UUID(lead_id)
        )
    ) == 1
    assert db.scalar(
        select(func.count())
        .select_from(CRMActivity)
        .where(CRMActivity.lead_id == UUID(lead_id))
    ) == 3


def test_relations_cannot_cross_workspace_boundaries(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, _db = crm_client
    first_token, first_workspace = create_workspace_session(
        client, "first@example.com", "First Workspace"
    )
    second_token, second_workspace = create_workspace_session(
        client, "second@example.com", "Second Workspace"
    )
    foreign_company = create_company(
        client, second_workspace, second_token, "Foreign Company"
    )

    response = create_lead(
        client,
        first_workspace,
        first_token,
        company_id=foreign_company["id"],
    )
    foreign_record_read = client.get(
        f"/api/workspaces/{first_workspace}/crm/leads/{foreign_company['id']}",
        headers=auth(first_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "company_not_found"
    assert foreign_record_read.status_code == 404


def test_unrelated_user_cannot_read_crm_data(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, _db = crm_client
    owner_token, owner_workspace = create_workspace_session(
        client, "owner@example.com", "Owner Workspace"
    )
    outsider_token, _outsider_workspace = create_workspace_session(
        client, "outsider@example.com", "Outsider Workspace"
    )
    create_lead(client, owner_workspace, owner_token)

    response = client.get(
        f"/api/workspaces/{owner_workspace}/crm/leads",
        headers=auth(outsider_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "workspace_not_found"


def test_invalid_assignment_and_contact_company_pair_are_rejected(
    crm_client: tuple[TestClient, Session],
) -> None:
    client, db = crm_client
    token, workspace_id = create_workspace_session(
        client, "crm-owner@example.com", "CRM Alpha"
    )
    company_a = create_company(client, workspace_id, token, "Company A")
    company_b = create_company(client, workspace_id, token, "Company B")
    contact = create_contact(
        client,
        workspace_id,
        token,
        email="linked@example.com",
        company_id=company_a["id"],
    ).json()
    unrelated_user = User(
        email="unrelated@example.com",
        display_name="Unrelated",
        password_hash=hash_password("unrelated-secure-password"),
    )
    db.add(unrelated_user)
    db.commit()

    wrong_company = create_lead(
        client,
        workspace_id,
        token,
        company_id=company_b["id"],
        contact_id=contact["id"],
    )
    wrong_assignee = client.post(
        f"/api/workspaces/{workspace_id}/crm/leads",
        json={
            "title": "Unassigned authorization check",
            "assigned_to": str(unrelated_user.id),
        },
        headers=auth(token),
    )

    assert wrong_company.status_code == 422
    assert wrong_assignee.status_code == 422
    assert db.scalar(select(func.count()).select_from(Lead)) == 0
