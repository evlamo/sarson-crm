"""Email template management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.email_template import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    MailchimpTemplateImport,
)
from app.services import email_template_service
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/email-templates", tags=["email-templates"])


@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all email templates."""
    templates = email_template_service.list_templates(db)
    return {"data": [EmailTemplateResponse.from_orm(t) for t in templates]}


@router.get("/{template_id}")
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single template by ID."""
    template = email_template_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"data": EmailTemplateResponse.from_orm(template)}


@router.post("")
def create_template(
    data: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new custom email template."""
    template = email_template_service.create_template(
        db=db,
        name=data.name,
        design_json=data.design_json,
        html=data.html,
        user_id=current_user.id,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
    )
    return {"data": EmailTemplateResponse.from_orm(template)}


@router.patch("/{template_id}")
def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing template."""
    updates = data.dict(exclude_unset=True)
    template = email_template_service.update_template(db, template_id, updates)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"data": EmailTemplateResponse.from_orm(template)}


@router.delete("/{template_id}")
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a template."""
    success = email_template_service.delete_template(db, template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"data": {"message": "Template deleted"}}


@router.post("/import/mailchimp")
async def import_mailchimp_template(
    data: MailchimpTemplateImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a MailChimp template and convert merge fields."""
    template = await email_template_service.import_mailchimp_template(
        db=db,
        mailchimp_template_id=data.mailchimp_template_id,
        name=data.name,
        user_id=current_user.id,
    )
    return {"data": EmailTemplateResponse.from_orm(template)}
