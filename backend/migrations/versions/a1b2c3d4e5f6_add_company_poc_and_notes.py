"""add company poc and notes

Revision ID: a1b2c3d4e5f6
Revises: f684b64a21ae
Create Date: 2026-02-28 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = ('f684b64a21ae', 'e1fb25ad6c8b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('poc_contact_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_companies_poc_contact_id',
        'companies', 'contacts',
        ['poc_contact_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_companies_poc_contact_id', 'companies', type_='foreignkey')
    op.drop_column('companies', 'poc_contact_id')
    op.drop_column('companies', 'notes')
