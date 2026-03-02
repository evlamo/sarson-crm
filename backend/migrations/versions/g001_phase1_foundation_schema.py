"""Phase 1 Foundation Schema

Revision ID: g001_phase1_foundation
Revises: f684b64a21ae
Create Date: 2026-03-02

New tables:
- sales_campaigns
- campaign_contacts
- audit_log
- contact_field_history
- db_snapshots
- sheets_exports
- sheets_import_reviews

Modified tables:
- contacts: add master_dnc fields
- users: add RBAC permission columns
- email_campaigns: add sales_campaign_id FK
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = 'g001_phase1_foundation'
down_revision: Union[str, Sequence[str], None] = 'a82ce4d0d747'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== A. SALES CAMPAIGNS ==========
    op.create_table(
        'sales_campaigns',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_sales_campaigns_status', 'sales_campaigns', ['status'])
    op.create_index('idx_sales_campaigns_owner', 'sales_campaigns', ['owner_id'])

    # ========== Add sales_campaign_id to email_campaigns ==========
    op.add_column('email_campaigns', sa.Column('sales_campaign_id', UUID(as_uuid=True)))
    op.create_foreign_key(
        'fk_email_campaigns_sales_campaign',
        'email_campaigns', 'sales_campaigns',
        ['sales_campaign_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_email_campaigns_sales_campaign', 'email_campaigns', ['sales_campaign_id'])

    # ========== CAMPAIGN CONTACTS JUNCTION ==========
    op.create_table(
        'campaign_contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contact_id', UUID(as_uuid=True), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sales_campaign_id', UUID(as_uuid=True), sa.ForeignKey('sales_campaigns.id', ondelete='CASCADE')),
        sa.Column('email_campaign_id', UUID(as_uuid=True), sa.ForeignKey('email_campaigns.id', ondelete='CASCADE')),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('completion_status', sa.String(50)),
        sa.Column('excluded_reason', sa.String(255)),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.UniqueConstraint('contact_id', 'sales_campaign_id', name='uq_campaign_contacts_contact_sales'),
    )
    op.create_index('idx_campaign_contacts_contact', 'campaign_contacts', ['contact_id'])
    op.create_index('idx_campaign_contacts_sales', 'campaign_contacts', ['sales_campaign_id'])
    op.create_index('idx_campaign_contacts_email', 'campaign_contacts', ['email_campaign_id'])

    # ========== B. MASTER DNC ON CONTACTS ==========
    op.add_column('contacts', sa.Column('master_dnc', sa.Boolean, server_default='FALSE'))
    op.add_column('contacts', sa.Column('master_dnc_reason', sa.Text))
    op.add_column('contacts', sa.Column('master_dnc_set_at', sa.DateTime(timezone=True)))
    op.add_column('contacts', sa.Column('master_dnc_set_by', UUID(as_uuid=True)))
    op.create_foreign_key(
        'fk_contacts_master_dnc_set_by',
        'contacts', 'users',
        ['master_dnc_set_by'], ['id'],
        ondelete='SET NULL'
    )
    op.execute("""
        CREATE INDEX idx_contacts_master_dnc ON contacts(master_dnc) WHERE master_dnc = TRUE;
    """)

    # ========== C. AUDIT LOG ==========
    op.create_table(
        'audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True)),
        sa.Column('old_values', JSONB),
        sa.Column('new_values', JSONB),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_log_user', 'audit_log', ['user_id'])
    op.create_index('idx_audit_log_created', 'audit_log', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_audit_log_action', 'audit_log', ['action'])

    # ========== D. CONTACT FIELD HISTORY ==========
    op.create_table(
        'contact_field_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contact_id', UUID(as_uuid=True), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('old_value', sa.Text),
        sa.Column('new_value', sa.Text),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('source', sa.String(50), server_default='manual'),
    )
    op.create_index('idx_field_history_contact', 'contact_field_history', ['contact_id'])
    op.create_index('idx_field_history_changed', 'contact_field_history', ['changed_at'], postgresql_ops={'changed_at': 'DESC'})

    # ========== E. DB SNAPSHOTS REGISTRY ==========
    op.create_table(
        'db_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('label', sa.String(255)),
        sa.Column('snapshot_type', sa.String(50), server_default='auto'),
        sa.Column('file_path', sa.Text, nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
    )
    op.create_index('idx_snapshots_created', 'db_snapshots', ['created_at'], postgresql_ops={'created_at': 'DESC'})

    # ========== F. RBAC EXPANSION ON USERS ==========
    op.add_column('users', sa.Column('can_manage_users', sa.Boolean, server_default='FALSE'))
    op.add_column('users', sa.Column('can_manage_campaigns', sa.Boolean, server_default='FALSE'))
    op.add_column('users', sa.Column('can_approve_imports', sa.Boolean, server_default='FALSE'))
    op.add_column('users', sa.Column('can_revert_db', sa.Boolean, server_default='FALSE'))
    op.add_column('users', sa.Column('can_manage_integrations', sa.Boolean, server_default='FALSE'))
    # Grant all permissions to existing admins
    op.execute("""
        UPDATE users SET 
            can_manage_users = TRUE,
            can_manage_campaigns = TRUE,
            can_approve_imports = TRUE,
            can_revert_db = TRUE,
            can_manage_integrations = TRUE
        WHERE role = 'admin';
    """)

    # ========== G. GOOGLE SHEETS SYNC REGISTRY ==========
    op.create_table(
        'sheets_exports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('spreadsheet_id', sa.String(255), nullable=False),
        sa.Column('spreadsheet_url', sa.Text),
        sa.Column('sheet_name', sa.String(255)),
        sa.Column('filter_criteria', JSONB),
        sa.Column('contact_count', sa.Integer),
        sa.Column('exported_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('exported_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('last_synced_at', sa.DateTime(timezone=True)),
        sa.Column('sync_status', sa.String(50), server_default='active'),
    )
    op.create_index('idx_sheets_exports_spreadsheet', 'sheets_exports', ['spreadsheet_id'])

    op.create_table(
        'sheets_import_reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('export_id', UUID(as_uuid=True), sa.ForeignKey('sheets_exports.id', ondelete='SET NULL')),
        sa.Column('import_data', JSONB, nullable=False),
        sa.Column('conflict_data', JSONB),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('idx_sheets_import_reviews_export', 'sheets_import_reviews', ['export_id'])
    op.create_index('idx_sheets_import_reviews_status', 'sheets_import_reviews', ['status'])


def downgrade() -> None:
    # ========== G. SHEETS TABLES (reverse order) ==========
    op.drop_index('idx_sheets_import_reviews_status', 'sheets_import_reviews')
    op.drop_index('idx_sheets_import_reviews_export', 'sheets_import_reviews')
    op.drop_table('sheets_import_reviews')
    op.drop_index('idx_sheets_exports_spreadsheet', 'sheets_exports')
    op.drop_table('sheets_exports')
    
    # ========== F. RBAC COLUMNS ==========
    op.drop_column('users', 'can_manage_integrations')
    op.drop_column('users', 'can_revert_db')
    op.drop_column('users', 'can_approve_imports')
    op.drop_column('users', 'can_manage_campaigns')
    op.drop_column('users', 'can_manage_users')
    
    # ========== E. DB SNAPSHOTS ==========
    op.drop_index('idx_snapshots_created', 'db_snapshots')
    op.drop_table('db_snapshots')
    
    # ========== D. CONTACT FIELD HISTORY ==========
    op.drop_index('idx_field_history_changed', 'contact_field_history')
    op.drop_index('idx_field_history_contact', 'contact_field_history')
    op.drop_table('contact_field_history')
    
    # ========== C. AUDIT LOG ==========
    op.drop_index('idx_audit_log_action', 'audit_log')
    op.drop_index('idx_audit_log_created', 'audit_log')
    op.drop_index('idx_audit_log_user', 'audit_log')
    op.drop_index('idx_audit_log_entity', 'audit_log')
    op.drop_table('audit_log')
    
    # ========== B. MASTER DNC ON CONTACTS ==========
    op.drop_constraint('fk_contacts_master_dnc_set_by', 'contacts', type_='foreignkey')
    op.execute('DROP INDEX IF EXISTS idx_contacts_master_dnc;')
    op.drop_column('contacts', 'master_dnc_set_by')
    op.drop_column('contacts', 'master_dnc_set_at')
    op.drop_column('contacts', 'master_dnc_reason')
    op.drop_column('contacts', 'master_dnc')
    
    # ========== A. CAMPAIGN CONTACTS ==========
    op.drop_index('idx_campaign_contacts_email', 'campaign_contacts')
    op.drop_index('idx_campaign_contacts_sales', 'campaign_contacts')
    op.drop_index('idx_campaign_contacts_contact', 'campaign_contacts')
    op.drop_table('campaign_contacts')
    
    # ========== EMAIL CAMPAIGNS SALES LINK ==========
    op.drop_index('idx_email_campaigns_sales_campaign', 'email_campaigns')
    op.drop_constraint('fk_email_campaigns_sales_campaign', 'email_campaigns', type_='foreignkey')
    op.drop_column('email_campaigns', 'sales_campaign_id')
    
    # ========== SALES CAMPAIGNS ==========
    op.drop_index('idx_sales_campaigns_owner', 'sales_campaigns')
    op.drop_index('idx_sales_campaigns_status', 'sales_campaigns')
    op.drop_table('sales_campaigns')
