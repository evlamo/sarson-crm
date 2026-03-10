"""Phase 8: Campaign Contact Removal - DNC campaigns tracking

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
    # Add dnc_campaigns field to contacts table
    op.add_column("contacts", sa.Column("dnc_campaigns", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("contacts", sa.Column("dnc_campaigns_set_at", sa.DateTime(timezone=True), nullable=True))
    
    # Create campaign_contact_removal table for explicit removal tracking
    op.create_table(
        "campaign_contact_removal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sales_campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("removed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for performance
    op.create_index("idx_campaign_contact_removal_contact", "campaign_contact_removal", ["contact_id"])
    op.create_index("idx_campaign_contact_removal_campaign", "campaign_contact_removal", ["sales_campaign_id"])
    op.create_index("idx_campaign_contact_removal_reason", "campaign_contact_removal", ["reason"])
    
    # Create unique constraint on contact+campaign
    op.create_unique_constraint("uq_campaign_contact_removal", "campaign_contact_removal", ["contact_id", "sales_campaign_id"])


def downgrade() -> None:
    op.drop_constraint("uq_campaign_contact_removal", "campaign_contact_removal")
    op.drop_index("idx_campaign_contact_removal_reason", table_name="campaign_contact_removal")
    op.drop_index("idx_campaign_contact_removal_campaign", table_name="campaign_contact_removal")
    op.drop_index("idx_campaign_contact_removal_contact", table_name="campaign_contact_removal")
    op.drop_table("campaign_contact_removal")
    op.drop_column("contacts", "dnc_campaigns_set_at")
    op.drop_column("contacts", "dnc_campaigns")
