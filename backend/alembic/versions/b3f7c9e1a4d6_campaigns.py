"""campaigns + campaign_recipients tables (bulk email/SMS outreach)

Revision ID: b3f7c9e1a4d6
Revises: 9a1c3e5b7d20
Create Date: 2026-10-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3f7c9e1a4d6"
down_revision = "9a1c3e5b7d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("filters", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=False),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_campaign_recipients_organization_id", "campaign_recipients", ["organization_id"])
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_lead_id", "campaign_recipients", ["lead_id"])
    op.create_index("ix_campaign_recipients_status", "campaign_recipients", ["status"])


def downgrade() -> None:
    op.drop_index("ix_campaign_recipients_status", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_lead_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_campaign_id", table_name="campaign_recipients")
    op.drop_index("ix_campaign_recipients_organization_id", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")
    op.drop_index("ix_campaigns_organization_id", table_name="campaigns")
    op.drop_table("campaigns")
