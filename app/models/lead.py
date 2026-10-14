from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LEAD_STAGES = ("new", "qualified", "proposal", "won", "lost")


class Lead(Base):
    __tablename__ = "crm_leads"
    __table_args__ = (
        CheckConstraint(
            "stage IN ('new', 'qualified', 'proposal', 'won', 'lost')",
            name="valid_stage",
        ),
        CheckConstraint("estimated_value IS NULL OR estimated_value >= 0", name="nonnegative_value"),
        Index("ix_crm_leads_workspace_stage_created", "workspace_id", "stage", "created_at"),
        Index("ix_crm_leads_workspace_created", "workspace_id", "created_at"),
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
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("crm_contacts.id", ondelete="SET NULL")
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    stage: Mapped[str] = mapped_column(
        String(24), nullable=False, default="new", server_default="new"
    )
    source: Mapped[str | None] = mapped_column(String(80))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
