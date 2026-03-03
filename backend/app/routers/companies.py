from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.utils.time import utcnow
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted, get_admin_user
from app.models.company import Company
from app.models.contact import Contact
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyPatch, CompanyResponse, PaginatedCompanies
from app.schemas.contact import ContactResponse
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


def _capture_company_snapshot(company: Company) -> dict:
    """Capture current values of a company for audit."""
    return {
        "name": company.name,
        "domain": company.domain,
        "website": company.website,
        "industry": company.industry,
        "phone": company.phone,
        "address": company.address,
        "city": company.city,
        "state": company.state,
        "country": company.country,
        "employee_count": company.employee_count,
        "aum": str(company.aum) if company.aum else None,
        "notes": company.notes,
    }


def _compute_changes(old: dict, new: dict) -> dict:
    changes = {}
    for key in set(old.keys()) | set(new.keys()):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


def _company_response(company: Company, db: Session, contact_count: int | None = None) -> CompanyResponse:
    if contact_count is None:
        contact_count = db.query(func.count(Contact.id)).filter(
            Contact.company_id == company.id,
            Contact.deleted_at.is_(None),
        ).scalar() or 0
    data = CompanyResponse.model_validate(company)
    data.contact_count = contact_count
    return data


@router.get("", response_model=PaginatedCompanies)
def list_companies(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    contact_counts = dict(
        db.query(Contact.company_id, func.count(Contact.id))
        .filter(Contact.company_id.in_([c.id for c in companies]), Contact.deleted_at.is_(None))
        .group_by(Contact.company_id)
        .all()
    ) if companies else {}

    return PaginatedCompanies(
        data=[_company_response(c, db, contact_count=contact_counts.get(c.id, 0)) for c in companies],
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
    if payload.domain:
        existing = db.query(Company).filter(Company.domain == payload.domain).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Company with domain '{payload.domain}' already exists")

    company = Company(**payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    
    audit_service.log_action_sync(
        db=db,
        action="company.create",
        entity_type="company",
        entity_id=str(company.id),
        new_values=_capture_company_snapshot(company),
        user_id=str(current_user.id),
    )
    db.commit()
    
    return _company_response(company, db)


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_snapshot = _capture_company_snapshot(company)

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
    
    new_snapshot = _capture_company_snapshot(company)
    changes = _compute_changes(old_snapshot, new_snapshot)
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="company.update",
            entity_type="company",
            entity_id=str(company.id),
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(company)
    return _company_response(company, db)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_snapshot = _capture_company_snapshot(company)

    db.query(Contact).filter(
        Contact.company_id == company.id,
        Contact.status == 'poc',
    ).update({'status': 'prospect'})
    db.query(Contact).filter(Contact.company_id == company.id).update({'company_id': None})
    company.deleted_at = utcnow()
    
    audit_service.log_action_sync(
        db=db,
        action="company.delete",
        entity_type="company",
        entity_id=str(company.id),
        old_values=old_snapshot,
        user_id=str(current_user.id),
    )
    
    db.commit()


@router.patch("/{company_id}", response_model=CompanyResponse)
def patch_company(
    company_id: str,
    payload: CompanyPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_snapshot = _capture_company_snapshot(company)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)

    company.updated_at = utcnow()
    
    new_snapshot = _capture_company_snapshot(company)
    changes = _compute_changes(old_snapshot, new_snapshot)
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="company.update",
            entity_type="company",
            entity_id=str(company.id),
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            user_id=str(current_user.id),
        )
    
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


@router.post("/{company_id}/poc/{contact_id}", status_code=200)
def assign_company_poc(
    company_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    new_poc = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None),
    ).first()
    if not new_poc:
        raise HTTPException(status_code=404, detail="Contact not found")

    if str(new_poc.company_id) != company_id:
        raise HTTPException(
            status_code=400,
            detail="Contact does not belong to this company",
        )

    old_poc_id = company.poc_contact_id

    if company.poc_contact_id and str(company.poc_contact_id) != contact_id:
        existing_poc = db.query(Contact).filter(
            Contact.id == company.poc_contact_id,
            Contact.deleted_at.is_(None),
        ).first()
        if existing_poc:
            existing_poc.status = "active"

    new_poc.status = "poc"
    company.poc_contact_id = new_poc.id
    
    audit_service.log_action_sync(
        db=db,
        action="company.assign_poc",
        entity_type="company",
        entity_id=str(company.id),
        old_values={"poc_contact_id": str(old_poc_id) if old_poc_id else None},
        new_values={"poc_contact_id": str(new_poc.id)},
        user_id=str(current_user.id),
    )

    db.commit()
    db.refresh(new_poc)

    return {
        "id": str(new_poc.id),
        "first_name": new_poc.first_name,
        "last_name": new_poc.last_name,
        "full_name": new_poc.full_name,
        "email": new_poc.email,
        "status": new_poc.status,
    }


@router.delete("/{company_id}/poc", status_code=200)
def remove_company_poc(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    company = db.query(Company).filter(
        Company.id == company_id,
        Company.deleted_at.is_(None),
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    old_poc_id = company.poc_contact_id

    if company.poc_contact_id:
        existing_poc = db.query(Contact).filter(
            Contact.id == company.poc_contact_id,
            Contact.deleted_at.is_(None),
        ).first()
        if existing_poc:
            existing_poc.status = "active"
        company.poc_contact_id = None
        
        audit_service.log_action_sync(
            db=db,
            action="company.remove_poc",
            entity_type="company",
            entity_id=str(company.id),
            old_values={"poc_contact_id": str(old_poc_id)},
            user_id=str(current_user.id),
        )

    db.commit()
    return {"detail": "POC removed"}
