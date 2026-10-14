import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Base, User
from app.security import verify_password
from scripts.seed_demo import ensure_local_database, seed_demo


def test_demo_seed_is_idempotent_and_uses_supplied_password() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    password = "a-long-local-demo-password"
    with Session(engine) as session:
        seed_demo(session, password)
        first_counts = {
            table.name: session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }

        seed_demo(session, password)
        second_counts = {
            table.name: session.scalar(select(func.count()).select_from(table))
            for table in Base.metadata.sorted_tables
        }
        with pytest.raises(ValueError, match="does not match"):
            seed_demo(session, "a-different-password-that-is-rejected")

        demo_user = session.scalar(select(User).where(User.email == "demo@example.com"))
        assert demo_user is not None
        assert verify_password(password, demo_user.password_hash)
        assert first_counts == second_counts
    engine.dispose()


def test_demo_seed_refuses_non_local_database_hosts() -> None:
    ensure_local_database("sqlite:///local.db")

    with pytest.raises(ValueError, match="local database host"):
        ensure_local_database("postgresql+psycopg://user:pass@db.example.net/workspace")
