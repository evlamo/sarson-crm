"""Phase 4: Add performance indexes for audit tables

Revision ID: h001_phase4_audit_idx
Revises: g001_phase1_foundation
Create Date: 2026-03-02

Adds composite indexes for efficient querying at scale (47k contacts):
- audit_log: entity + time, action + time
- contact_field_history: contact + field, contact + time
- db_snapshots: type, created_at
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'h001_phase4_audit_idx'
down_revision = 'g001_phase1_foundation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Audit log indexes (idempotent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entity_time 
        ON audit_log (entity_type, created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at 
        ON audit_log (created_at)
    """)
    
    # Contact field history indexes (idempotent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_field_history_contact_field 
        ON contact_field_history (contact_id, field_name)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_field_history_contact_time 
        ON contact_field_history (contact_id, changed_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_field_history_changed_at 
        ON contact_field_history (changed_at)
    """)
    
    # DB snapshots indexes (idempotent)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_db_snapshots_created_at 
        ON db_snapshots (created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_db_snapshots_type 
        ON db_snapshots (snapshot_type)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_audit_log_entity_time")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_created_at")
    op.execute("DROP INDEX IF EXISTS idx_field_history_contact_field")
    op.execute("DROP INDEX IF EXISTS idx_field_history_contact_time")
    op.execute("DROP INDEX IF EXISTS idx_field_history_changed_at")
    op.execute("DROP INDEX IF EXISTS idx_db_snapshots_created_at")
    op.execute("DROP INDEX IF EXISTS idx_db_snapshots_type")
