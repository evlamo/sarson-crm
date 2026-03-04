"""
Contact Service Layer
Shared helpers for contact operations used across multiple routers.
"""
from uuid import UUID
from typing import Union

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.contact import Contact
from app.schemas.contact import ContactResponse


def get_contact_or_404(
    db: Session,
    contact_id: Union[str, UUID],
    *,
    load_relations: bool = True,
) -> Contact:
    """
    Fetch a non-deleted contact by ID, raising 404 if not found.
    
    Args:
        db: Database session
        contact_id: Contact UUID (str or UUID)
        load_relations: If True, eager-loads tags and company_obj (default True)
    """
    query = db.query(Contact)
    if load_relations:
        query = query.options(joinedload(Contact.tags), joinedload(Contact.company_obj))
    contact = query.filter(
        Contact.id == str(contact_id),
        Contact.deleted_at.is_(None),
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def build_contact_response(contact: Contact) -> ContactResponse:
    """Enrich ContactResponse with computed fields (full_name, company_name)."""
    data = ContactResponse.model_validate(contact)
    data.full_name = contact.full_name
    if contact.company_obj:
        data.company_name = contact.company_obj.name
    elif contact.company:
        data.company_name = contact.company
    return data
