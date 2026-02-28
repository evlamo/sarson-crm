"""Company auto-creation and lookup service."""
import uuid
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company


def get_or_create_company(db: Session, company_name: str) -> Optional[Company]:
    """
    Case-insensitive lookup by name. Creates if not found.
    Returns the Company object, or None if name is empty.
    Handles race conditions via unique index + IntegrityError retry.
    """
    if not company_name or not company_name.strip():
        return None
    name = company_name.strip()
    company = db.query(Company).filter(
        func.lower(Company.name) == name.lower(),
        Company.deleted_at.is_(None),
    ).first()
    if company:
        return company
    try:
        company = Company(id=uuid.uuid4(), name=name)
        db.add(company)
        db.flush()
        return company
    except IntegrityError:
        db.rollback()
        return db.query(Company).filter(
            func.lower(Company.name) == name.lower(),
            Company.deleted_at.is_(None),
        ).first()
