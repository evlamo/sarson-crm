"""Email templates table for visual editor.

Revision ID: l001_email_templates
Revises: k001_nested_campaigns
Create Date: 2026-03-11 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

# revision identifiers, used by Alembic.
revision = 'l001_email_templates'
down_revision = 'k001_nested_campaigns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'email_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('design_json', JSONB, nullable=False),
        sa.Column('html', sa.Text, nullable=False),
        sa.Column('thumbnail_url', sa.String(500)),
        sa.Column('is_mailchimp_template', sa.Boolean, default=False),
        sa.Column('mailchimp_template_id', sa.Integer),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_email_templates_name', 'email_templates', ['name'])
    op.create_index('ix_email_templates_created_by', 'email_templates', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_email_templates_created_by')
    op.drop_index('ix_email_templates_name')
    op.drop_table('email_templates')
