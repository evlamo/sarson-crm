"""Phase 7: Google OAuth support + restricted users

Revision ID: i001_phase7_google_oauth
Revises: h001_phase4_audit_idx
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "i001_phase7_google_oauth"
down_revision = "h001_phase4_audit_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add OAuth columns to users table
    op.add_column("users", sa.Column("google_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("auth_provider", sa.String(50), server_default="local", nullable=False))
    op.add_column("users", sa.Column("is_restricted", sa.Boolean(), server_default="false", nullable=False))
    # avatar_url already exists from prior migrations
    
    # Create unique index on google_id for faster lookups
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    
    # OAuth state table for CSRF protection
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(255), primary_key=True),
        sa.Column("redirect_uri", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), server_default=sa.text("NOW() + INTERVAL '10 minutes'")),
    )
    op.create_index("ix_oauth_states_expires", "oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_table("oauth_states")
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "is_restricted")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "google_id")
