"""Email template service with MailChimp import and merge field conversion."""
import re
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.email_template import EmailTemplate


def convert_mailchimp_to_sendgrid_merge(html: str) -> str:
    """Convert MailChimp *|FNAME|* syntax to SendGrid {{first_name}} syntax."""
    conversions = {
        r'\*\|FNAME\|\*': '{{first_name}}',
        r'\*\|LNAME\|\*': '{{last_name}}',
        r'\*\|EMAIL\|\*': '{{email}}',
        r'\*\|COMPANY\|\*': '{{company}}',
        r'\*\|PHONE\|\*': '{{phone}}',
    }
    result = html
    for mc_pattern, sg_tag in conversions.items():
        result = re.sub(mc_pattern, sg_tag, result, flags=re.IGNORECASE)
    return result


def convert_sendgrid_to_mailchimp_merge(html: str) -> str:
    """Convert SendGrid {{first_name}} to MailChimp *|FNAME|* for MailChimp API."""
    conversions = {
        r'\{\{first_name\}\}': '*|FNAME|*',
        r'\{\{last_name\}\}': '*|LNAME|*',
        r'\{\{email\}\}': '*|EMAIL|*',
        r'\{\{company\}\}': '*|COMPANY|*',
        r'\{\{phone\}\}': '*|PHONE|*',
    }
    result = html
    for sg_pattern, mc_tag in conversions.items():
        result = re.sub(sg_pattern, mc_tag, result, flags=re.IGNORECASE)
    return result


async def import_mailchimp_template(
    db: Session,
    mailchimp_template_id: int,
    name: str,
    user_id: UUID,
) -> EmailTemplate:
    """Import a MailChimp template and convert merge fields."""
    # Create minimal Unlayer design JSON (HTML-only mode)
    # In future, can fetch from MailChimp and parse HTML
    design_json = {
        "counters": {"u_column": 1, "u_row": 1},
        "body": {
            "rows": [{
                "cells": [1],
                "columns": [{
                    "contents": [{
                        "type": "html",
                        "values": {"html": ""}
                    }]
                }]
            }]
        }
    }

    template = EmailTemplate(
        name=name,
        design_json=design_json,
        html="",
        is_mailchimp_template=True,
        mailchimp_template_id=mailchimp_template_id,
        created_by=user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def list_templates(db: Session, include_deleted: bool = False) -> List[EmailTemplate]:
    """List all email templates."""
    query = db.query(EmailTemplate)
    if not include_deleted:
        query = query.filter(EmailTemplate.deleted_at.is_(None))
    return query.order_by(EmailTemplate.created_at.desc()).all()


def get_template(db: Session, template_id: UUID) -> Optional[EmailTemplate]:
    """Get a single template by ID."""
    return db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.deleted_at.is_(None),
    ).first()


def create_template(
    db: Session,
    name: str,
    design_json: dict,
    html: str,
    user_id: UUID,
    description: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
) -> EmailTemplate:
    """Create a new custom template."""
    template = EmailTemplate(
        name=name,
        description=description,
        design_json=design_json,
        html=html,
        thumbnail_url=thumbnail_url,
        created_by=user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template_id: UUID,
    updates: dict,
) -> Optional[EmailTemplate]:
    """Update an existing template."""
    template = get_template(db, template_id)
    if not template:
        return None

    for key, value in updates.items():
        if value is not None and hasattr(template, key):
            setattr(template, key, value)

    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: UUID) -> bool:
    """Soft-delete a template."""
    template = get_template(db, template_id)
    if not template:
        return False

    template.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
