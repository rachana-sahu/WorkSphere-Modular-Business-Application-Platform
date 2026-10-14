"""Add workspace-scoped CRM records.

Revision ID: 0002_crm
Revises: 0001_initial
Create Date: 2026-10-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_crm"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_companies",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_crm_companies_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crm_companies"),
    )
    op.create_index(
        "uq_crm_companies_workspace_name",
        "crm_companies",
        ["workspace_id", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("job_title", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["crm_companies.id"],
            name="fk_crm_contacts_company_id_crm_companies",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_crm_contacts_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crm_contacts"),
    )
    op.create_index(
        "uq_crm_contacts_workspace_email",
        "crm_contacts",
        ["workspace_id", sa.text("lower(email)")],
        unique=True,
    )
    op.create_index(
        "ix_crm_contacts_workspace_last_name",
        "crm_contacts",
        ["workspace_id", "last_name"],
        unique=False,
    )

    op.create_table(
        "crm_leads",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("contact_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("assigned_to", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column(
            "stage",
            sa.String(length=24),
            server_default="new",
            nullable=False,
        ),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "stage IN ('new', 'qualified', 'proposal', 'won', 'lost')",
            name="valid_stage",
        ),
        sa.CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0",
            name="nonnegative_value",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name="fk_crm_leads_assigned_to_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["crm_companies.id"],
            name="fk_crm_leads_company_id_crm_companies",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["crm_contacts.id"],
            name="fk_crm_leads_contact_id_crm_contacts",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_crm_leads_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crm_leads"),
    )
    op.create_index(
        "ix_crm_leads_workspace_stage_created",
        "crm_leads",
        ["workspace_id", "stage", "created_at"],
    )
    op.create_index(
        "ix_crm_leads_workspace_created",
        "crm_leads",
        ["workspace_id", "created_at"],
    )

    op.create_table(
        "crm_notes",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("contact_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("lead_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("author_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(CASE WHEN company_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="one_record_target",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_crm_notes_author_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["crm_companies.id"],
            name="fk_crm_notes_company_id_crm_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["crm_contacts.id"],
            name="fk_crm_notes_contact_id_crm_contacts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["crm_leads.id"],
            name="fk_crm_notes_lead_id_crm_leads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_crm_notes_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crm_notes"),
    )
    op.create_index(
        "ix_crm_notes_workspace_created", "crm_notes", ["workspace_id", "created_at"]
    )
    op.create_index("ix_crm_notes_lead_created", "crm_notes", ["lead_id", "created_at"])
    op.create_index(
        "ix_crm_notes_contact_created", "crm_notes", ["contact_id", "created_at"]
    )
    op.create_index(
        "ix_crm_notes_company_created", "crm_notes", ["company_id", "created_at"]
    )

    op.create_table(
        "crm_activities",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workspace_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("contact_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("lead_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("from_stage", sa.String(length=24), nullable=True),
        sa.Column("to_stage", sa.String(length=24), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(CASE WHEN company_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN contact_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN lead_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="one_record_target",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name="fk_crm_activities_actor_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["crm_companies.id"],
            name="fk_crm_activities_company_id_crm_companies",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["crm_contacts.id"],
            name="fk_crm_activities_contact_id_crm_contacts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["crm_leads.id"],
            name="fk_crm_activities_lead_id_crm_leads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_crm_activities_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_crm_activities"),
    )
    op.create_index(
        "ix_crm_activities_workspace_created",
        "crm_activities",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_crm_activities_lead_created", "crm_activities", ["lead_id", "created_at"]
    )
    op.create_index(
        "ix_crm_activities_contact_created",
        "crm_activities",
        ["contact_id", "created_at"],
    )
    op.create_index(
        "ix_crm_activities_company_created",
        "crm_activities",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("crm_activities")
    op.drop_table("crm_notes")
    op.drop_table("crm_leads")
    op.drop_table("crm_contacts")
    op.drop_table("crm_companies")
