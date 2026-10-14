from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        Index(
            "uq_departments_workspace_name",
            "workspace_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
