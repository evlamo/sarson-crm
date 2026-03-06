"""Phase 8: Campaign Contact Removal Tracking

Revision ID: j001_campaign_contact_removal
Revises: i001_phase7_google_oauth
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "j001_campaign_contact_removal"
down_revision = "i001_phase7_google_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create campaign_contact_removal table
    op.create_table(
        "campaign_contact_removal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.func.gen_random_uuid()),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),  # e.g., "Not interested", "Invalid email", "Requested removal"
        sa.Column("removed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_contact_removal"),
        sa.Index("idx_campaign_removal_campaign", "campaign_id"),
        sa.Index("idx_campaign_removal_contact", "contact_id"),
        sa.Index("idx_campaign_removal_removed_at", "removed_at"),
    )
    
    # Add dnc_campaigns flag to contacts table (tracks if contact is DNC in any campaign)
    op.add_column("contacts", sa.Column("dnc_campaigns", sa.JSON(), server_default="[]", nullable=False))


def downgrade() -> None:
    op.drop_column("contacts", "dnc_campaigns")
    op.drop_table("campaign_contact_removal")
