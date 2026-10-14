from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Company(Base):
    __tablename__ = "crm_companies"
    __table_args__ = (
        Index(
            "uq_crm_companies_workspace_name",
            "workspace_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(253))
    phone: Mapped[str | None] = mapped_column(String(40))
    website: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
