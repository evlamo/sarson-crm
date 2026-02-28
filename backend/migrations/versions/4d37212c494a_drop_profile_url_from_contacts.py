"""drop_profile_url_from_contacts

Revision ID: 4d37212c494a
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 11:33:28.601091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d37212c494a'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('contacts', 'profile_url')


def downgrade() -> None:
    op.add_column('contacts', sa.Column('profile_url', sa.Text(), nullable=True))
