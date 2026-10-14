from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index(
            "uq_employees_workspace_email",
            "workspace_id",
            text("lower(email)"),
            unique=True,
        ),
        Index("ix_employees_workspace_last_name", "workspace_id", "last_name"),
        Index("ix_employees_department", "department_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(120))
    start_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
