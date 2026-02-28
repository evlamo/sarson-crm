from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.utils.time import utcnow
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.company import Company
from app.models.contact import Contact
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyPatch, CompanyResponse, PaginatedCompanies
from app.schemas.contact import ContactResponse
from app.models.user import User

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


def _company_response(company: Company, db: Session) -> CompanyResponse:
    """Build CompanyResponse with contact_count."""
    count = db.query(func.count(Contact.id)).filter(
        Contact.company_id == company.id,
        Contact.deleted_at.is_(None),
    ).scalar() or 0
    data = CompanyResponse.model_validate(company)
    data.contact_count = count
    return data


@router.get("", response_model=PaginatedCompanies)
def list_companies(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated list of companies. Filter by name search."""
    query = db.query(Company).filter(Company.deleted_at.is_(None))

    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))

    total = query.count()
    companies = (
        query.order_by(Company.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return PaginatedCompanies(
        data=[_company_response(c, db) for c in companies],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single company with contact count."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return _company_response(company, db)


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new company."""
    if payload.domain:
        existing = db.query(Company).filter(Company.domain == payload.domain).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Company with domain '{payload.domain}' already exists")

    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return _company_response(company, db)


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full update of a company."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Domain uniqueness check (exclude self)
    if payload.domain:
        conflict = db.query(Company).filter(
            Company.domain == payload.domain,
            Company.id != company_id,
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Domain '{payload.domain}' already in use")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    company.updated_at = utcnow()
    db.commit()
    db.refresh(company)
    return _company_response(company, db)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a company."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Null out company_id on contacts but keep company text
    contacts = db.query(Contact).filter(Contact.company_id == company.id).all()
    for c in contacts:
        c.company_id = None
    company.deleted_at = utcnow()
    db.commit()


@router.patch("/{company_id}", response_model=CompanyResponse)
def patch_company(
    company_id: str,
    payload: CompanyPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partial update of a company."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    company.updated_at = utcnow()
    db.commit()
    db.refresh(company)
    return _company_response(company, db)


@router.get("/{company_id}/contacts")
def get_company_contacts(
    company_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contacts belonging to a company."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = db.query(Contact).filter(
        Contact.company_id == company_id,
        Contact.deleted_at.is_(None),
    )
    total = query.count()
    contacts = (
        query.order_by(Contact.last_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "data": [
            {
                "id": str(c.id),
                "first_name": c.first_name,
                "last_name": c.last_name,
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "title": c.title,
                "status": c.status,
            }
            for c in contacts
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/{company_id}/poc")
def get_company_poc(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current POC contact for a company."""
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not company.poc_contact_id:
        return None

    poc = db.query(Contact).filter(Contact.id == company.poc_contact_id).first()
    if not poc:
        return None

    return {
        "id": str(poc.id),
        "first_name": poc.first_name,
        "last_name": poc.last_name,
        "full_name": poc.full_name,
        "email": poc.email,
        "status": poc.status,
    }
