"""expand_search_vector_trigger

Revision ID: c7a1e2f39b04
Revises: f684b64a21ae
Create Date: 2026-02-27 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7a1e2f39b04'
down_revision: Union[str, Sequence[str], None] = 'f684b64a21ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update trigger function to include more fields in search vector
    op.execute("""
        CREATE OR REPLACE FUNCTION contacts_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                to_tsvector('english',
                    coalesce(NEW.first_name, '') || ' ' ||
                    coalesce(NEW.last_name, '') || ' ' ||
                    coalesce(NEW.email, '') || ' ' ||
                    coalesce(NEW.company, '') || ' ' ||
                    coalesce(NEW.city, '') || ' ' ||
                    coalesce(NEW.state, '') || ' ' ||
                    coalesce(NEW.sarson_rep, '') || ' ' ||
                    coalesce(NEW.next_step, '') || ' ' ||
                    coalesce(NEW.notes, '')
                );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Backfill existing rows
    op.execute("""
        UPDATE contacts SET search_vector =
            to_tsvector('english',
                coalesce(first_name, '') || ' ' ||
                coalesce(last_name, '') || ' ' ||
                coalesce(email, '') || ' ' ||
                coalesce(company, '') || ' ' ||
                coalesce(city, '') || ' ' ||
                coalesce(state, '') || ' ' ||
                coalesce(sarson_rep, '') || ' ' ||
                coalesce(next_step, '') || ' ' ||
                coalesce(notes, '')
            )
    """)


def downgrade() -> None:
    # Revert to original trigger function
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
        UPDATE contacts SET search_vector =
            to_tsvector('english',
                coalesce(first_name, '') || ' ' ||
                coalesce(last_name, '') || ' ' ||
                coalesce(email, '') || ' ' ||
                coalesce(company, '') || ' ' ||
                coalesce(notes, '')
            )
    """)
