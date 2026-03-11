"""Add unique POC per company constraint

Revision ID: 20260311000545
Revises: 
Create Date: 2026-03-11 00:05:45.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260311000545'
down_revision = 'f684b64a21ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create a partial unique index: only one active POC per company
    # This prevents two contacts with status='poc' for the same company (where deleted_at is NULL)
    op.create_index(
        'idx_one_poc_per_company',
        'contacts',
        ['company_id'],
        unique=True,
        postgresql_where=sa.text("status = 'poc' AND deleted_at IS NULL")
    )


def downgrade() -> None:
    op.drop_index('idx_one_poc_per_company', table_name='contacts')
