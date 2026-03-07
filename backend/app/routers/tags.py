from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.tag import Tag
from app.models.contact import Contact
from app.models.tag import ContactTag
from app.schemas.tag import TagCreate, TagUpdate, TagResponse
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["tags"])


@router.get("/tags")
def list_tags(
    with_counts: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tags, optionally with contact counts."""
    if with_counts:
        results = (
            db.query(Tag, func.count(ContactTag.c.contact_id).label("contact_count"))
            .outerjoin(ContactTag, Tag.id == ContactTag.c.tag_id)
            .group_by(Tag.id)
            .order_by(Tag.name)
            .all()
        )
        return [
            {
                "id": str(tag.id),
                "name": tag.name,
                "color": tag.color,
                "category": getattr(tag, "category", None),
                "contact_count": count,
            }
            for tag, count in results
        ]
    return db.query(Tag).order_by(Tag.name).all()


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new tag. Name must be unique."""
    existing = db.query(Tag).filter(Tag.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Tag '{payload.name}' already exists")

    tag = Tag(**payload.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: str,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a tag (rename, change color)."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tag, key, value)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a tag (cascade removes from all contacts)."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()


# ── Contact-tag association endpoints ──────────────────────────────────────

@router.post("/contacts/{contact_id}/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def add_tag_to_contact(
    contact_id: str,
    payload: TagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a tag to a contact by name (creates tag if it doesn't exist)."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None),
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Get or create tag
    tag = db.query(Tag).filter(Tag.name == payload.name).first()
    if not tag:
        tag = Tag(**payload.model_dump())
        db.add(tag)
        db.flush()

    # Check not already attached
    if tag not in contact.tags:
        contact.tags.append(tag)
        db.commit()

    db.refresh(tag)
    return tag


@router.post("/contacts/{contact_id}/tags/by-id", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def add_tag_to_contact_by_id(
    contact_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an existing tag to a contact by tag ID."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None),
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag not in contact.tags:
        contact.tags.append(tag)
        db.commit()

    db.refresh(tag)
    return tag


@router.delete("/contacts/{contact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_contact(
    contact_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a tag from a contact."""
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None),
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag in contact.tags:
        contact.tags.remove(tag)
        db.commit()
