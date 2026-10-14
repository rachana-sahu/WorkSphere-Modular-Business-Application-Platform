from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.dependencies import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)
from app.main import app
from app.models import Base, User, Workspace, WorkspaceMembership
from app.security import create_access_token, hash_password


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, Session]]:
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
    session_factory = Session

    def override_get_db() -> Iterator[Session]:
        with session_factory(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client, Session(engine) as db:
        yield client, db
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def register(
    client: TestClient,
    email: str = "owner@example.com",
    workspace_name: str = "Sample Workspace",
) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": "Workspace Owner",
            "password": "correct-horse-battery",
            "workspace_name": workspace_name,
        },
    )
    assert response.status_code == 201, response.text
    return {
        **response.json(),
        "access_token": client.cookies.get(SESSION_COOKIE_NAME),
    }


def workspace_id(client: TestClient, token: str) -> UUID:
    response = client.get(
        "/api/workspaces/current",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return UUID(response.json()["id"])


def add_member(
    db: Session,
    workspace_id: UUID,
    email: str,
    role: str = "member",
) -> User:
    user = User(
        email=email,
        display_name=email.split("@", maxsplit=1)[0].title(),
        password_hash=hash_password("member-password-secure"),
    )
    db.add(user)
    db.flush()
    db.add(
        WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
        )
    )
    db.commit()
    return user


def test_registration_normalizes_email_and_hashes_password(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    response = client.post(
        "/api/auth/register",
        json={
            "email": "  OWNER@Example.Com ",
            "display_name": "  A Workspace Owner ",
            "password": "correct-horse-battery",
            "workspace_name": "  Sample Workspace ",
        },
    )

    assert response.status_code == 201
    assert response.json()["expires_in"] > 0
    assert "access_token" not in response.json()
    assert client.cookies.get(SESSION_COOKIE_NAME)
    assert client.cookies.get(CSRF_COOKIE_NAME)
    session_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{SESSION_COOKIE_NAME}=")
    )
    csrf_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith(f"{CSRF_COOKIE_NAME}=")
    )
    assert "httponly" in session_cookie.lower()
    assert "secure" not in session_cookie.lower()
    assert "samesite=lax" in session_cookie.lower()
    assert "path=/api" in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    assert "path=/" in csrf_cookie.lower()
    user = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert user.display_name == "A Workspace Owner"
    assert user.password_hash != "correct-horse-battery"
    assert user.password_hash.startswith("$argon2id$")
    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user.id
        )
    )
    assert membership is not None
    assert membership.role == "owner"


def test_duplicate_email_returns_conflict_without_partial_workspace(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    register(client)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "OWNER@example.com",
            "display_name": "Another User",
            "password": "another-secure-password",
            "workspace_name": "A Different Workspace",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "registration_conflict"
    assert db.scalar(select(func.count()).select_from(Workspace)) == 1


def test_duplicate_workspace_slug_returns_conflict(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    register(client)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "another@example.com",
            "display_name": "Another User",
            "password": "another-secure-password",
            "workspace_name": "Sample---Workspace",
        },
    )

    assert response.status_code == 409
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_registration_rejects_short_password(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client

    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "display_name": "Workspace Owner",
            "password": "short",
            "workspace_name": "Sample Workspace",
        },
    )

    assert response.status_code == 422
    details = response.json()["detail"]
    assert details["code"] == "validation_error"
    assert all("input" not in error for error in details["errors"])
    assert all(error.get("input") != "short" for error in details["errors"])


def test_login_and_protected_profile_return_safe_user_data(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client
    register(client)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "OWNER@EXAMPLE.COM",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 200
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token is not None
    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile.status_code == 200
    assert profile.json()["email"] == "owner@example.com"
    assert "password_hash" not in profile.json()


def test_token_endpoint_issues_bearer_token_for_api_clients(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client
    register(client)
    response = client.post(
        "/api/auth/token",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.headers.get_list("set-cookie") == []
    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert profile.status_code == 200


def test_cookie_session_requires_csrf_for_logout_and_clears_session(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client
    register(client)
    assert client.get("/api/auth/me").status_code == 200
    workspace = client.get("/api/workspaces/current")
    assert workspace.status_code == 200
    company_url = (
        f"/api/workspaces/{workspace.json()['id']}/crm/companies"
    )

    missing_csrf = client.post(company_url, json={"name": "Rejected Write"})
    assert missing_csrf.status_code == 403
    invalid_csrf = client.post(
        "/api/auth/logout",
        headers={CSRF_HEADER_NAME: "not-the-csrf-token"},
    )
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token is not None
    allowed_write = client.post(
        company_url,
        json={"name": "Accepted Write"},
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    logout = client.post(
        "/api/auth/logout",
        headers={CSRF_HEADER_NAME: csrf_token},
    )

    assert missing_csrf.json()["detail"]["code"] == "csrf_validation_failed"
    assert invalid_csrf.status_code == 403
    assert allowed_write.status_code == 201
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("email", ["owner@example.com", "missing@example.com"])
def test_login_uses_same_error_for_unknown_email_and_bad_password(
    auth_client: tuple[TestClient, Session], email: str
) -> None:
    client, _db = auth_client
    register(client)

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "invalid_credentials",
        "message": "Email or password is incorrect.",
    }


def test_https_cookie_setting_marks_session_and_csrf_cookies_secure(
    auth_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _db = auth_client

    from app.config import settings

    monkeypatch.setattr(settings, "session_cookie_secure", True)
    response = client.post(
        "/api/auth/register",
        json={
            "email": "secure@example.com",
            "display_name": "Secure User",
            "password": "correct-horse-battery",
            "workspace_name": "Secure Workspace",
        },
    )

    assert response.status_code == 201
    assert all(
        "secure" in cookie.lower()
        for cookie in response.headers.get_list("set-cookie")
    )


def test_protected_endpoint_rejects_missing_or_malformed_tokens(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client

    missing = client.get("/api/auth/me")
    malformed = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert missing.status_code == 401
    assert malformed.status_code == 401


def test_deactivated_user_cannot_login_or_use_existing_token(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    token = register(client)["access_token"]
    user = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    user.is_active = False
    db.commit()

    profile = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert profile.status_code == 401
    assert login_response.status_code == 401
    assert login_response.json()["detail"]["code"] == "invalid_credentials"


def test_expired_token_is_rejected(
    auth_client: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _db = auth_client
    response = register(client)
    token = response["access_token"]

    from app.config import settings

    monkeypatch.setattr(settings, "access_token_expire_minutes", -1)
    user_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = UUID(user_response.json()["id"])
    expired_token = create_access_token(user_id)

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


def test_workspace_members_require_admin_or_owner_role(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    token = register(client)["access_token"]
    owner_id = workspace_id(client, token)
    member = add_member(db, owner_id, "member@example.com")
    client.post(
        "/api/auth/login",
        json={
            "email": member.email,
            "password": "member-password-secure",
        }
    )
    member_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert member_token is not None

    denied = client.get(
        f"/api/workspaces/{owner_id}/members",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    allowed = client.get(
        f"/api/workspaces/{owner_id}/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert len(allowed.json()) == 2


def test_only_workspace_owner_can_change_member_role(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    owner_token = register(client)["access_token"]
    owner_workspace_id = workspace_id(client, owner_token)
    member = add_member(db, owner_workspace_id, "member@example.com")
    client.post(
        "/api/auth/login",
        json={
            "email": member.email,
            "password": "member-password-secure",
        }
    )
    member_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert member_token is not None
    url = (
        f"/api/workspaces/{owner_workspace_id}/members/"
        f"{member.id}/role"
    )

    denied = client.patch(
        url,
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    changed = client.patch(
        url,
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert denied.status_code == 403
    assert changed.status_code == 200
    assert changed.json()["role"] == "admin"

    client.post(
        "/api/auth/login",
        json={
            "email": member.email,
            "password": "member-password-secure",
        }
    )
    admin_token = client.cookies.get(SESSION_COOKIE_NAME)
    assert admin_token is not None
    second_member = add_member(
        db, owner_workspace_id, "second-member@example.com"
    )
    admin_can_list = client.get(
        f"/api/workspaces/{owner_workspace_id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    admin_cannot_change_role = client.patch(
        f"/api/workspaces/{owner_workspace_id}/members/"
        f"{second_member.id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_can_list.status_code == 200
    assert admin_cannot_change_role.status_code == 403


def test_workspace_owner_cannot_be_demoted(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, _db = auth_client
    owner_token = register(client)["access_token"]
    owner_user = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()
    owner_workspace_id = workspace_id(client, owner_token)

    response = client.patch(
        f"/api/workspaces/{owner_workspace_id}/members/{owner_user['id']}/role",
        json={"role": "member"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "owner_role_protected"


def test_workspace_membership_does_not_leak_between_workspaces(
    auth_client: tuple[TestClient, Session],
) -> None:
    client, db = auth_client
    owner_token = register(client)["access_token"]
    owner_workspace_id = workspace_id(client, owner_token)
    outsider_response = register(
        client,
        email="outsider@example.com",
        workspace_name="Outsider Workspace",
    )
    outsider_token = outsider_response["access_token"]

    response = client.get(
        f"/api/workspaces/{owner_workspace_id}/members",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )

    assert response.status_code == 404
