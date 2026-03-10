"""Add nested campaigns: sales_campaign_id FK to email_campaigns.

Revision ID: k001_nested_campaigns
Revises: j001_campaign_contact_removal, a1b2c3d4e5f8
Create Date: 2026-03-10 18:32:00.000000

This is a merge point of the two branches.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'k001_nested_campaigns'
down_revision = ('j001_campaign_contact_removal', 'a1b2c3d4e5f8')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add sales_campaign_id column to email_campaigns
    op.add_column('email_campaigns',
        sa.Column('sales_campaign_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_email_campaigns_sales_campaign_id',
        'email_campaigns', 'sales_campaigns',
        ['sales_campaign_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add index for performance
    op.create_index(
        'idx_email_campaigns_sales_campaign_id',
        'email_campaigns',
        ['sales_campaign_id']
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_email_campaigns_sales_campaign_id', table_name='email_campaigns')
    
    # Drop foreign key
    op.drop_constraint('fk_email_campaigns_sales_campaign_id', 'email_campaigns', type_='foreignkey')
    
    # Drop column
    op.drop_column('email_campaigns', 'sales_campaign_id')
