from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Base, User, Workspace, WorkspaceMembership


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_user(email: str = "member@example.test") -> User:
    return User(
        email=email,
        display_name="Demo Member",
        password_hash="test-only-hash",
    )


def create_workspace(slug: str = "demo") -> Workspace:
    return Workspace(name="Demo Workspace", slug=slug)


def test_membership_references_existing_workspace_and_user(session: Session) -> None:
    user = create_user()
    workspace = create_workspace()
    session.add_all([user, workspace])
    session.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="member",
    )
    session.add(membership)
    session.commit()

    assert session.get(
        WorkspaceMembership, (workspace.id, user.id)
    ) is not None


def test_user_email_must_be_unique(session: Session) -> None:
    session.add_all([create_user(), create_user()])

    with pytest.raises(IntegrityError):
        session.commit()


def test_workspace_slug_must_be_unique(session: Session) -> None:
    session.add_all([create_workspace(), create_workspace()])

    with pytest.raises(IntegrityError):
        session.commit()


def test_membership_role_is_constrained_by_database(session: Session) -> None:
    user = create_user()
    workspace = create_workspace()
    session.add_all([user, workspace])
    session.flush()
    session.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role="superuser",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_membership_requires_existing_foreign_keys(session: Session) -> None:
    session.add(
        WorkspaceMembership(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role="member",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_membership_pair_must_be_unique(session: Session) -> None:
    user = create_user()
    workspace = create_workspace()
    session.add_all([user, workspace])
    session.flush()
    session.add_all(
        [
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="member",
            ),
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user.id,
                role="admin",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_user_cascades_to_membership(session: Session) -> None:
    user = create_user()
    workspace = create_workspace()
    session.add_all([user, workspace])
    session.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="member",
    )
    session.add(membership)
    session.commit()

    session.delete(user)
    session.commit()

    assert session.get(
        WorkspaceMembership, (workspace.id, user.id)
    ) is None


def test_initial_migration_upgrades_and_downgrades(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from app.config import settings

    database_path = tmp_path / "migration-test.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path}")
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.upgrade(config, "0001_initial")

    engine = create_engine(f"sqlite:///{database_path}")
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "users",
        "workspace_memberships",
        "workspaces",
    }
    assert inspect(engine).get_indexes("workspace_memberships") == [
        {
            "name": "ix_workspace_memberships_user_id",
            "column_names": ["user_id"],
            "unique": 0,
            "dialect_options": {},
        }
    ]
    engine.dispose()

    command.downgrade(config, "base")

    engine = create_engine(f"sqlite:///{database_path}")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_feature_migrations_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from app.config import settings

    database_path = tmp_path / "crm-migration-test.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path}")
    config = Config(Path(__file__).parents[1] / "alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert {
        "crm_companies",
        "crm_contacts",
        "crm_leads",
        "crm_notes",
        "crm_activities",
        "projects",
        "project_tasks",
        "task_comments",
        "project_activities",
        "channels",
        "channel_messages",
        "departments",
        "employees",
        "leave_requests",
        "job_openings",
        "candidates",
        "job_applications",
        "application_history",
    }.issubset(inspector.get_table_names())
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND name = ?",
                ("uq_crm_companies_workspace_name",),
            ).scalar_one()
            == "uq_crm_companies_workspace_name"
        )
    assert "ck_crm_leads_valid_stage" in {
        constraint["name"]
        for constraint in inspector.get_check_constraints("crm_leads")
    }
    assert "ck_projects_valid_status" in {
        constraint["name"]
        for constraint in inspector.get_check_constraints("projects")
    }
    assert {
        "ck_project_tasks_valid_status",
        "ck_project_tasks_valid_priority",
    }.issubset(
        {
            constraint["name"]
            for constraint in inspector.get_check_constraints("project_tasks")
        }
    )
    assert {
        "ck_leave_requests_valid_status",
        "ck_leave_requests_valid_date_range",
    }.issubset(
        {
            constraint["name"]
            for constraint in inspector.get_check_constraints("leave_requests")
        }
    )
    assert "ck_job_applications_valid_status" in {
        constraint["name"]
        for constraint in inspector.get_check_constraints("job_applications")
    }
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name = ?",
            ("uq_channels_workspace_name",),
        ).scalar_one() == "uq_channels_workspace_name"
    engine.dispose()

    command.downgrade(config, "0001_initial")
    engine = create_engine(f"sqlite:///{database_path}")
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version",
        "users",
        "workspace_memberships",
        "workspaces",
    }
    engine.dispose()
