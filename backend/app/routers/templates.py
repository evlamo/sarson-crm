"""
Email Templates API — CRUD + merge field preview.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted
from app.models.user import User
from app.models.contact import Contact
from app.models.campaign import EmailTemplate
from app.schemas.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateOut,
    TemplateListOut,
    TemplatePreview,
    MergeFieldsRequest,
)
from app.services.campaign_service import render_merge_fields
from app.services import audit_service

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


# ── List Templates ─────────────────────────────────────────────────────────

@router.get("", response_model=TemplateListOut)
def list_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmailTemplate)
    if category:
        query = query.filter(EmailTemplate.category == category)
    if search:
        query = query.filter(EmailTemplate.name.ilike(f"%{search}%"))

    total = query.count()
    items = (
        query.order_by(desc(EmailTemplate.updated_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return TemplateListOut(data=items, total=total, page=page, per_page=limit)


# ── Create Template ────────────────────────────────────────────────────────

@router.post("/", response_model=TemplateOut, status_code=201)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = EmailTemplate(
        name=data.name,
        subject=data.subject,
        body_html=data.body_html,
        body_text=data.body_text,
        category=data.category,
        created_by=current_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    
    # Audit: template created
    audit_service.log_action_sync(
        db=db,
        action="template.create",
        entity_type="template",
        entity_id=str(template.id),
        new_values={
            "name": template.name,
            "subject": template.subject,
            "category": template.category,
        },
        user_id=str(current_user.id),
    )
    db.commit()
    
    return template


# ── Get Template ───────────────────────────────────────────────────────────

@router.get("/{template_id}", response_model=TemplateOut)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# ── Update Template ────────────────────────────────────────────────────────

@router.patch("/{template_id}", response_model=TemplateOut)
def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    old_values = {
        "name": template.name,
        "subject": template.subject,
        "category": template.category,
    }

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    template.updated_at = datetime.now(timezone.utc)
    
    new_values = {
        "name": template.name,
        "subject": template.subject,
        "category": template.category,
    }
    
    changes = {k: v for k, v in new_values.items() if old_values.get(k) != v}
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="template.update",
            entity_type="template",
            entity_id=str(template.id),
            old_values={k: old_values[k] for k in changes},
            new_values=changes,
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(template)
    return template


# ── Delete Template ────────────────────────────────────────────────────────

@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Audit: template deleted
    audit_service.log_action_sync(
        db=db,
        action="template.delete",
        entity_type="template",
        entity_id=str(template.id),
        old_values={
            "name": template.name,
            "subject": template.subject,
            "category": template.category,
        },
        user_id=str(current_user.id),
    )
    
    db.delete(template)
    db.commit()


# ── Preview Template with Merge Fields ─────────────────────────────────────

@router.post("/{template_id}/preview", response_model=TemplatePreview)
def preview_template(
    template_id: UUID,
    data: MergeFieldsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Build merge data — from contact or sample data
    merge_data = {
        "first_name": "John",
        "last_name": "Doe",
        "full_name": "John Doe",
        "company": "Acme Corp",
        "email": "john@acme.com",
        "unsubscribe_url": "https://sarsonfunds.com/unsubscribe?preview=true",
    }

    if data.contact_id:
        contact = db.query(Contact).filter(
            Contact.id == data.contact_id,
            Contact.deleted_at.is_(None),
        ).first()
        if contact:
            merge_data = {
                "first_name": contact.first_name or "",
                "last_name": contact.last_name or "",
                "full_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "company": contact.company or "",
                "email": contact.email or "",
                "unsubscribe_url": f"https://sarsonfunds.com/unsubscribe?c={contact.id}",
            }

    if data.sample_data:
        merge_data.update(data.sample_data)

    rendered_subject = render_merge_fields(template.subject or "", merge_data)
    rendered_html = render_merge_fields(template.body_html, merge_data)
    rendered_text = render_merge_fields(template.body_text or "", merge_data) if template.body_text else None

    return TemplatePreview(
        subject=rendered_subject,
        body_html=rendered_html,
        body_text=rendered_text,
    )
