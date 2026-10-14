import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger("worksphere.database")
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning(
            "Database readiness check failed",
            extra={"error_type": type(exc).__name__},
        )
        return False
    return True
