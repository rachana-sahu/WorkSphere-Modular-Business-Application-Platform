from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Contact(Base):
    __tablename__ = "crm_contacts"
    __table_args__ = (
        Index(
            "uq_crm_contacts_workspace_email",
            "workspace_id",
            text("lower(email)"),
            unique=True,
        ),
        Index("ix_crm_contacts_workspace_last_name", "workspace_id", "last_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_companies.id", ondelete="SET NULL")
    )
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    job_title: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
