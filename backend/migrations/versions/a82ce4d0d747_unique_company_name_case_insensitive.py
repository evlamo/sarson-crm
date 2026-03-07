"""unique_company_name_case_insensitive

Revision ID: a82ce4d0d747
Revises: 4d37212c494a
Create Date: 2026-02-28 11:37:06.920869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a82ce4d0d747'
down_revision: Union[str, Sequence[str], None] = '4d37212c494a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_lower ON companies (lower(name)) WHERE deleted_at IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS uq_companies_name_lower")
