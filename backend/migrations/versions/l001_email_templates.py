"""Email templates table for visual editor."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


def upgrade():
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


def downgrade():
    op.drop_index('ix_email_templates_created_by')
    op.drop_index('ix_email_templates_name')
    op.drop_table('email_templates')
