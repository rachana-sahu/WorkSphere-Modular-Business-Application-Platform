from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CRMNote(Base):
    __tablename__ = "crm_notes"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN company_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="one_record_target",
        ),
        Index("ix_crm_notes_workspace_created", "workspace_id", "created_at"),
        Index("ix_crm_notes_lead_created", "lead_id", "created_at"),
        Index("ix_crm_notes_contact_created", "contact_id", "created_at"),
        Index("ix_crm_notes_company_created", "company_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_companies.id", ondelete="CASCADE")
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_contacts.id", ondelete="CASCADE")
    )
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_leads.id", ondelete="CASCADE")
    )
    author_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
