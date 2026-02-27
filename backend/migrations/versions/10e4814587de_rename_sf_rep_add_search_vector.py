"""rename_sf_rep_add_search_vector

Revision ID: 10e4814587de
Revises: 1b3deaf32d57
Create Date: 2026-02-27 08:01:13.092029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = '10e4814587de'
down_revision: Union[str, Sequence[str], None] = '1b3deaf32d57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename sf_rep -> sarson_rep
    op.alter_column('contacts', 'sf_rep', new_column_name='sarson_rep')

    # Add search_vector tsvector column
    op.add_column('contacts', sa.Column('search_vector', TSVECTOR, nullable=True))

    # GIN index for fast full-text search
    op.create_index(
        'ix_contacts_search_vector',
        'contacts',
        ['search_vector'],
        postgresql_using='gin'
    )

    # Populate search_vector for existing rows
    op.execute("""
        UPDATE contacts SET search_vector =
            to_tsvector('english',
                coalesce(first_name, '') || ' ' ||
                coalesce(last_name, '') || ' ' ||
                coalesce(email, '') || ' ' ||
                coalesce(company, '') || ' ' ||
                coalesce(notes, '')
            )
    """)

    # Trigger function to auto-update search_vector on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION contacts_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                to_tsvector('english',
                    coalesce(NEW.first_name, '') || ' ' ||
                    coalesce(NEW.last_name, '') || ' ' ||
                    coalesce(NEW.email, '') || ' ' ||
                    coalesce(NEW.company, '') || ' ' ||
                    coalesce(NEW.notes, '')
                );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS contacts_search_vector_trigger ON contacts;
        CREATE TRIGGER contacts_search_vector_trigger
            BEFORE INSERT OR UPDATE ON contacts
            FOR EACH ROW EXECUTE FUNCTION contacts_search_vector_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS contacts_search_vector_trigger ON contacts;")
    op.execute("DROP FUNCTION IF EXISTS contacts_search_vector_update();")
    op.drop_index('ix_contacts_search_vector', table_name='contacts')
    op.drop_column('contacts', 'search_vector')
    op.alter_column('contacts', 'sarson_rep', new_column_name='sf_rep')
