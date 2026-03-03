"""
Google Sheets two-way sync router.
Admin-only endpoints for exporting contacts to Sheets and importing changes back.

Security hardened — Phase 5 Audit v2:
- Input sanitization for CSV injection prevention
- Email/URL validation on imports
- Value length limits
- Optimistic locking on import apply
- Enhanced error handling

Endpoints:
- POST /api/v1/sheets/export         — Export contacts/list to a sheet
- POST /api/v1/sheets/import/preview — Pull sheet data, compare with CRM, return conflicts
- POST /api/v1/sheets/import/apply   — Apply approved import changes
- GET  /api/v1/sheets/exports        — List past exports
- GET  /api/v1/sheets/exports/{id}   — Get specific export details
- GET  /api/v1/sheets/config         — Get sheets config
- POST /api/v1/sheets/config         — Save sheets config
- POST /api/v1/sheets/test           — Test connection
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_admin_user
from app.models.user import User
from app.models.contact import Contact
from app.models.tag import Tag
from app.models.sheets import SheetsExport, SheetsImportReview
from app.models.static_list import StaticList, StaticListMember
from app.services import audit_service
from app.services.sheets_service import (
    export_contacts_to_sheet,
    read_sheet_data,
    compare_contact_with_sheet_row,
    test_connection,
    SheetsServiceError,
    SheetsAuthError,
    SheetsNotFoundError,
    EDITABLE_FIELDS,
)
from app.utils.encryption import encrypt_value, decrypt_value, mask_value

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sheets", tags=["sheets"])


# ── Input Validation & Sanitization ────────────────────────────────────────

# CSV injection prevention characters
_FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r"}

# Field length limits (varchar sizes from schema)
FIELD_MAX_LENGTHS = {
    "first_name": 100,
    "last_name": 100,
    "email": 255,
    "phone": 50,
    "company": 255,
    "title": 255,
    "status": 50,
    "tags": 1000,  # Combined tag string
    "lead_source": 100,
    "notes": 10000,
    "sarson_rep": 100,
    "city": 100,
    "state": 100,
    "country": 100,
    "linkedin_url": 500,
    "website": 500,
}

# Basic email regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# URL regex for linkedin/website validation
URL_REGEX = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def sanitize_value(value: str) -> str:
    """
    Strip CSV injection prefixes and excessive whitespace.
    Prevents formula injection when values are exported back to sheets.
    """
    if not value:
        return value
    v = value.strip()
    # Escape CSV injection characters by prefixing with single quote
    if v and v[0] in _FORMULA_CHARS:
        v = "'" + v
    # Remove any null bytes
    v = v.replace("\x00", "")
    return v


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return True  # Empty is allowed
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_url(url: str) -> bool:
    """Validate URL format for linkedin/website fields."""
    if not url:
        return True  # Empty is allowed
    return bool(URL_REGEX.match(url.strip()))


def truncate_field(value: str, field: str) -> str:
    """Truncate value to max length for field."""
    max_len = FIELD_MAX_LENGTHS.get(field, 255)
    if value and len(value) > max_len:
        return value[:max_len]
    return value


def sanitize_and_validate_field(field: str, value: str) -> tuple[str, Optional[str]]:
    """
    Sanitize and validate a field value.
    Returns (sanitized_value, error_message or None).
    """
    if not value:
        return "", None
    
    # Sanitize first
    sanitized = sanitize_value(value.strip())
    
    # Validate based on field type
    if field == "email":
        if not validate_email(sanitized):
            return "", f"Invalid email format: {sanitized[:50]}"
    elif field in ("linkedin_url", "website"):
        if sanitized and not validate_url(sanitized):
            return "", f"Invalid URL format for {field}: {sanitized[:50]}"
    
    # Truncate to max length
    sanitized = truncate_field(sanitized, field)
    
    return sanitized, None


# ── Pydantic Schemas ───────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    spreadsheet_id: str = Field(..., min_length=10, max_length=100)
    sheet_name: str = Field(default="CRM Export", min_length=1, max_length=100)
    list_id: Optional[UUID] = None


class ExportResponse(BaseModel):
    export_id: UUID
    rows_written: int
    spreadsheet_url: str
    complete: bool
    error: Optional[str] = None


class ImportPreviewRequest(BaseModel):
    spreadsheet_id: str = Field(..., min_length=10, max_length=100)
    sheet_name: str = Field(default="CRM Export", min_length=1, max_length=100)
    import_tags: List[str] = Field(default_factory=list, description="Tags to auto-apply to all imported contacts")


class ConflictItem(BaseModel):
    contact_id: str
    contact_name: str
    field: str
    crm_value: str
    sheet_value: str


class NewContactItem(BaseModel):
    row_index: int
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    company: Optional[str]
    raw_data: Dict[str, str]
    validation_errors: List[str] = Field(default_factory=list)


class OrphanItem(BaseModel):
    """Contact exists in sheet but was deleted in CRM"""
    sheet_row_index: int
    contact_id: str
    email: Optional[str]
    name: Optional[str]


class ImportPreviewResponse(BaseModel):
    review_id: UUID
    new_contacts: List[NewContactItem]
    conflicts: List[ConflictItem]
    orphans: List[OrphanItem]
    unchanged_count: int
    total_sheet_rows: int
    import_tags: List[str] = Field(default_factory=list)


class ApprovedChange(BaseModel):
    contact_id: str
    field: str
    new_value: str


class ImportApplyRequest(BaseModel):
    review_id: UUID
    approved_changes: List[ApprovedChange] = Field(default_factory=list)
    import_new_contacts: List[int] = Field(default_factory=list, description="Row indices of new contacts to import")
    expected_version: Optional[int] = Field(None, description="Optimistic lock version")


class ImportApplyResponse(BaseModel):
    changes_applied: int
    contacts_created: int
    tags_added: int = 0
    errors: List[str]
    version: int = Field(default=1, description="New version after apply")


class ConfigResponse(BaseModel):
    spreadsheet_id: Optional[str]
    sheet_name: Optional[str]
    credentials_set: bool
    last_tested_at: Optional[datetime]
    last_test_status: Optional[str]


class ConfigUpdateRequest(BaseModel):
    spreadsheet_id: Optional[str] = Field(None, max_length=100)
    sheet_name: Optional[str] = Field(None, max_length=100)
    credentials_json: Optional[str] = Field(None, description="Service account JSON (write-only)")


class TestResponse(BaseModel):
    success: bool
    message: str
    spreadsheet_title: Optional[str] = None
    sheets: Optional[List[str]] = None


class ExportListItem(BaseModel):
    id: UUID
    spreadsheet_id: str
    spreadsheet_url: Optional[str]
    sheet_name: Optional[str]
    contact_count: Optional[int]
    exported_at: datetime
    exported_by_name: Optional[str]
    sync_status: Optional[str]
    list_name: Optional[str]


class ImportHistoryItem(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by_name: Optional[str]
    new_count: int
    conflict_count: int
    unchanged_count: int
    applied_count: int
    import_tags: List[str] = Field(default_factory=list)


# ── Settings Helpers ───────────────────────────────────────────────────────

def _get_setting(db: Session, key: str) -> Optional[str]:
    """Get a setting value from crm_settings table."""
    result = db.execute(
        text("SELECT value, encrypted FROM crm_settings WHERE key = :key"),
        {"key": key}
    ).fetchone()
    if not result:
        return None
    value, encrypted = result
    if encrypted and value:
        decrypted = decrypt_value(value)
        # Safety check: if decryption returned the same value, it likely failed
        if decrypted == value and len(value) > 50:
            logger.error(f"Decryption may have failed for setting '{key}' — returning None for safety")
            return None
        return decrypted
    return value


def _set_setting(db: Session, key: str, value: Optional[str], encrypted: bool = False, user_id: Optional[str] = None):
    """Set a setting value in crm_settings table."""
    if value is None:
        db.execute(text("DELETE FROM crm_settings WHERE key = :key"), {"key": key})
    else:
        stored_value = encrypt_value(value) if encrypted else value
        db.execute(
            text("""
                INSERT INTO crm_settings (key, value, encrypted, updated_at, updated_by)
                VALUES (:key, :value, :encrypted, NOW(), :user_id::uuid)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    encrypted = EXCLUDED.encrypted,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """),
            {"key": key, "value": stored_value, "encrypted": encrypted, "user_id": user_id}
        )


def _get_credentials_json(db: Session) -> Optional[str]:
    """Get decrypted service account JSON."""
    creds = _get_setting(db, "sheets_credentials_json")
    if not creds:
        return None
    # Validate it looks like JSON before returning
    if not creds.strip().startswith("{"):
        logger.error("Credentials don't appear to be valid JSON — decryption may have failed")
        return None
    return creds


# ── Contact Query Helpers ──────────────────────────────────────────────────

def _build_contact_dict(contact: Contact) -> Dict[str, Any]:
    """Build export-friendly dict from Contact model."""
    return {
        "id": str(contact.id),
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "email": contact.email or "",
        "phone": contact.phone or "",
        "company": contact.company_obj.name if contact.company_obj else (contact.company or ""),
        "title": contact.title or "",
        "status": contact.status or "",
        "tags": [t.name for t in contact.tags] if contact.tags else [],
        "lead_source": contact.lead_source or "",
        "last_contacted_at": contact.last_contacted_at,
        "notes": contact.notes or "",
        "created_at": contact.created_at,
        "sarson_rep": contact.sarson_rep or "",
        "city": contact.city or "",
        "state": contact.state or "",
        "country": contact.country or "",
        "linkedin_url": contact.linkedin_url or "",
        "website": contact.website or "",
        "updated_at": contact.updated_at,
    }


def _get_contacts_for_export(db: Session, list_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
    """
    Get contacts for export. If list_id provided, export only that list's contacts.
    Uses yield_per for memory efficiency with large datasets.
    """
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.deleted_at.is_(None))
    )
    
    if list_id:
        # Get contacts from the static list
        contact_ids = db.query(StaticListMember.c.contact_id).filter(
            StaticListMember.c.list_id == list_id
        ).subquery()
        query = query.filter(Contact.id.in_(contact_ids))
    
    # Use yield_per for memory efficiency with large datasets
    contacts = query.order_by(Contact.last_name, Contact.first_name).yield_per(500).all()
    return [_build_contact_dict(c) for c in contacts]


def _get_or_create_tag(db: Session, tag_name: str) -> Tag:
    """Get existing tag or create a new one."""
    tag_name = tag_name.strip()[:100]  # Truncate to reasonable length
    tag = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
    if not tag:
        tag = Tag(name=tag_name)
        db.add(tag)
        db.flush()
    return tag


def _add_import_tags_to_contact(db: Session, contact: Contact, import_tags: List[str]) -> int:
    """Add import tags to a contact, returning count of tags actually added."""
    if not import_tags:
        return 0
    
    added = 0
    existing_tag_names = {t.name.lower() for t in contact.tags} if contact.tags else set()
    
    for tag_name in import_tags:
        if not tag_name.strip():
            continue
        if tag_name.strip().lower() in existing_tag_names:
            continue
        
        tag = _get_or_create_tag(db, tag_name.strip())
        contact.tags.append(tag)
        added += 1
    
    return added


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get current Google Sheets configuration."""
    spreadsheet_id = _get_setting(db, "sheets_spreadsheet_id")
    sheet_name = _get_setting(db, "sheets_default_sheet_name")
    credentials_set = _get_credentials_json(db) is not None
    last_tested_at_str = _get_setting(db, "sheets_last_tested_at")
    last_test_status = _get_setting(db, "sheets_last_test_status")
    
    last_tested_at = None
    if last_tested_at_str:
        try:
            last_tested_at = datetime.fromisoformat(last_tested_at_str)
        except ValueError:
            pass
    
    return ConfigResponse(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name or "CRM Export",
        credentials_set=credentials_set,
        last_tested_at=last_tested_at,
        last_test_status=last_test_status,
    )


@router.post("/config", response_model=ConfigResponse)
def update_config(
    payload: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Update Google Sheets configuration.
    credentials_json is write-only — never returned after save.
    """
    user_id = str(admin.id)
    
    if payload.spreadsheet_id is not None:
        _set_setting(db, "sheets_spreadsheet_id", payload.spreadsheet_id, encrypted=False, user_id=user_id)
    
    if payload.sheet_name is not None:
        _set_setting(db, "sheets_default_sheet_name", payload.sheet_name, encrypted=False, user_id=user_id)
    
    if payload.credentials_json is not None:
        # Validate it's valid JSON before saving
        try:
            import json
            parsed = json.loads(payload.credentials_json)
            # Validate it has required service account fields
            if "type" not in parsed or parsed.get("type") != "service_account":
                raise HTTPException(status_code=422, detail="JSON must be a Google service account key (type: service_account)")
            if "client_email" not in parsed:
                raise HTTPException(status_code=422, detail="Service account JSON missing client_email field")
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid JSON format for credentials")
        
        _set_setting(db, "sheets_credentials_json", payload.credentials_json, encrypted=True, user_id=user_id)
        # Clear test status when credentials change
        _set_setting(db, "sheets_last_tested_at", None)
        _set_setting(db, "sheets_last_test_status", None)
        
        audit_service.log_action_sync(
            db=db,
            action="sheets.config_update",
            entity_type="settings",
            entity_id=None,
            new_values={"credentials_updated": True, "spreadsheet_id": payload.spreadsheet_id},
            user_id=user_id,
        )
    
    db.commit()
    return get_config(db, admin)


@router.post("/test", response_model=TestResponse)
def test_sheets_connection(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Test connection to Google Sheets with current configuration."""
    credentials_json = _get_credentials_json(db)
    spreadsheet_id = _get_setting(db, "sheets_spreadsheet_id")
    
    if not credentials_json:
        return TestResponse(success=False, message="No service account credentials configured (or decryption failed)")
    
    if not spreadsheet_id:
        return TestResponse(success=False, message="No spreadsheet ID configured")
    
    result = test_connection(spreadsheet_id, credentials_json)
    
    # Store test result
    _set_setting(db, "sheets_last_tested_at", datetime.now(timezone.utc).isoformat())
    _set_setting(db, "sheets_last_test_status", "success" if result["success"] else "failed")
    db.commit()
    
    return TestResponse(**result)


@router.post("/export", response_model=ExportResponse)
def export_to_sheets(
    payload: ExportRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Export contacts to a Google Sheet.
    If list_id is provided, exports only that list's contacts.
    Otherwise exports all active contacts.
    """
    credentials_json = _get_credentials_json(db)
    if not credentials_json:
        raise HTTPException(status_code=400, detail="No service account credentials configured")
    
    # Validate list exists if provided
    list_name = None
    if payload.list_id:
        static_list = db.query(StaticList).filter(StaticList.id == payload.list_id).first()
        if not static_list:
            raise HTTPException(status_code=404, detail="List not found")
        list_name = static_list.name
    
    # Get contacts
    contacts = _get_contacts_for_export(db, payload.list_id)
    
    if not contacts:
        raise HTTPException(status_code=400, detail="No contacts to export")
    
    # Create export record
    export_record = SheetsExport(
        spreadsheet_id=payload.spreadsheet_id,
        sheet_name=payload.sheet_name,
        filter_criteria={"list_id": str(payload.list_id) if payload.list_id else None},
        contact_count=len(contacts),
        exported_by=admin.id,
        list_id=payload.list_id,
        sync_status="processing",
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)
    
    try:
        result = export_contacts_to_sheet(
            spreadsheet_id=payload.spreadsheet_id,
            sheet_name=payload.sheet_name,
            contacts=contacts,
            credentials_json=credentials_json,
        )
        
        # Update export record
        export_record.spreadsheet_url = result["spreadsheet_url"]
        export_record.contact_count = result["rows_written"]
        export_record.sync_status = "active" if result["complete"] else "partial"
        export_record.last_synced_at = datetime.now(timezone.utc)
        export_record.checkpoint_row = result.get("checkpoint_row", 0)
        
        if not result["complete"]:
            export_record.error_message = result.get("error")
        
        audit_service.log_action_sync(
            db=db,
            action="sheets.export",
            entity_type="sheets_export",
            entity_id=str(export_record.id),
            new_values={
                "spreadsheet_id": payload.spreadsheet_id,
                "sheet_name": payload.sheet_name,
                "contact_count": result["rows_written"],
                "list_id": str(payload.list_id) if payload.list_id else None,
                "list_name": list_name,
            },
            user_id=str(admin.id),
        )
        
        db.commit()
        
        return ExportResponse(
            export_id=export_record.id,
            rows_written=result["rows_written"],
            spreadsheet_url=result["spreadsheet_url"],
            complete=result["complete"],
            error=result.get("error"),
        )
        
    except SheetsAuthError as e:
        export_record.sync_status = "error"
        export_record.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=401, detail=str(e))
    except SheetsNotFoundError as e:
        export_record.sync_status = "error"
        export_record.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=404, detail=str(e))
    except SheetsServiceError as e:
        export_record.sync_status = "error"
        export_record.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports", response_model=List[ExportListItem])
def list_exports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """List past exports with pagination."""
    exports = (
        db.query(SheetsExport)
        .options(joinedload(SheetsExport.exporter))
        .order_by(SheetsExport.exported_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    result = []
    for exp in exports:
        list_name = None
        if exp.list_id:
            static_list = db.query(StaticList).filter(StaticList.id == exp.list_id).first()
            list_name = static_list.name if static_list else None
        
        result.append(ExportListItem(
            id=exp.id,
            spreadsheet_id=exp.spreadsheet_id,
            spreadsheet_url=exp.spreadsheet_url,
            sheet_name=exp.sheet_name,
            contact_count=exp.contact_count,
            exported_at=exp.exported_at,
            exported_by_name=exp.exporter.full_name if exp.exporter else None,
            sync_status=exp.sync_status,
            list_name=list_name,
        ))
    
    return result


@router.get("/imports", response_model=List[ImportHistoryItem])
def list_imports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """List past import reviews with pagination."""
    reviews = (
        db.query(SheetsImportReview)
        .options(joinedload(SheetsImportReview.reviewer))
        .order_by(SheetsImportReview.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    result = []
    for review in reviews:
        # Extract import_tags from import_data
        import_tags = []
        if review.import_data and isinstance(review.import_data, dict):
            import_tags = review.import_data.get("import_tags", [])
        
        result.append(ImportHistoryItem(
            id=review.id,
            status=review.status,
            created_at=review.created_at,
            reviewed_at=review.reviewed_at,
            reviewed_by_name=review.reviewer.full_name if review.reviewer else None,
            new_count=review.new_count or 0,
            conflict_count=review.conflict_count or 0,
            unchanged_count=review.unchanged_count or 0,
            applied_count=review.applied_count or 0,
            import_tags=import_tags,
        ))
    
    return result


@router.post("/import/preview", response_model=ImportPreviewResponse)
def preview_import(
    payload: ImportPreviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Pull sheet data, compare with CRM, and return a preview of changes.
    Identifies conflicts, new contacts, and orphans (deleted in CRM).
    All values are sanitized during preview.
    """
    credentials_json = _get_credentials_json(db)
    if not credentials_json:
        raise HTTPException(status_code=400, detail="No service account credentials configured")
    
    try:
        headers, sheet_rows = read_sheet_data(
            spreadsheet_id=payload.spreadsheet_id,
            sheet_name=payload.sheet_name,
            credentials_json=credentials_json,
        )
    except SheetsAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except SheetsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SheetsServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    if not sheet_rows:
        raise HTTPException(status_code=400, detail="Sheet is empty or has no data rows")
    
    # Check if 'id' column exists
    if "id" not in headers:
        raise HTTPException(
            status_code=400, 
            detail="Sheet must have an 'id' column to map back to CRM contacts"
        )
    
    # Sanitize import_tags
    sanitized_import_tags = [
        sanitize_value(tag.strip())[:100] 
        for tag in payload.import_tags 
        if tag.strip()
    ]
    
    # Sanitize all sheet values upfront
    sanitized_rows = []
    for row in sheet_rows:
        sanitized_row = {}
        for key, value in row.items():
            if isinstance(value, str):
                sanitized_row[key] = sanitize_value(value.strip())
            else:
                sanitized_row[key] = value
        sanitized_rows.append(sanitized_row)
    
    # Build lookup of CRM contacts by ID
    contact_ids = [row.get("id", "").strip() for row in sanitized_rows if row.get("id", "").strip()]
    
    crm_contacts_by_id = {}
    if contact_ids:
        contacts = (
            db.query(Contact)
            .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
            .filter(Contact.id.in_(contact_ids))
            .all()
        )
        for c in contacts:
            crm_contacts_by_id[str(c.id)] = c
    
    # Analyze each row
    conflicts = []
    new_contacts = []
    orphans = []
    unchanged_count = 0
    
    for row_idx, sheet_row in enumerate(sanitized_rows):
        sheet_id = sheet_row.get("id", "").strip()
        
        if not sheet_id:
            # No ID = potentially new contact
            email = sheet_row.get("email", "").strip()
            
            # Validate new contact data
            validation_errors = []
            if email and not validate_email(email):
                validation_errors.append(f"Invalid email format: {email[:50]}")
            
            linkedin = sheet_row.get("linkedin_url", "").strip()
            if linkedin and not validate_url(linkedin):
                validation_errors.append(f"Invalid LinkedIn URL: {linkedin[:50]}")
            
            website = sheet_row.get("website", "").strip()
            if website and not validate_url(website):
                validation_errors.append(f"Invalid website URL: {website[:50]}")
            
            # Only consider as new if it has an email
            if email:
                new_contacts.append(NewContactItem(
                    row_index=row_idx,
                    email=email,
                    first_name=sheet_row.get("first_name", "").strip() or None,
                    last_name=sheet_row.get("last_name", "").strip() or None,
                    company=sheet_row.get("company", "").strip() or None,
                    raw_data=sheet_row,
                    validation_errors=validation_errors,
                ))
            continue
        
        crm_contact = crm_contacts_by_id.get(sheet_id)
        
        if not crm_contact:
            # ID exists in sheet but not in CRM (or was deleted)
            orphans.append(OrphanItem(
                sheet_row_index=row_idx,
                contact_id=sheet_id,
                email=sheet_row.get("email", "").strip() or None,
                name=f"{sheet_row.get('first_name', '')} {sheet_row.get('last_name', '')}".strip() or None,
            ))
            continue
        
        # Compare fields
        crm_dict = _build_contact_dict(crm_contact)
        row_conflicts = compare_contact_with_sheet_row(crm_dict, sheet_row)
        
        if row_conflicts:
            contact_name = crm_contact.full_name
            for field, values in row_conflicts.items():
                conflicts.append(ConflictItem(
                    contact_id=sheet_id,
                    contact_name=contact_name,
                    field=field,
                    crm_value=values["crm_value"],
                    sheet_value=values["sheet_value"],
                ))
        else:
            unchanged_count += 1
    
    # Create import review record with version tracking
    review = SheetsImportReview(
        import_data={
            "spreadsheet_id": payload.spreadsheet_id,
            "sheet_name": payload.sheet_name,
            "headers": headers,
            "rows": sanitized_rows,  # Store sanitized rows
            "version": 1,  # Initial version for optimistic locking
            "import_tags": sanitized_import_tags,  # Store import tags
        },
        conflict_data={
            "conflicts": [c.model_dump() for c in conflicts],
            "new_contacts": [n.model_dump() for n in new_contacts],
            "orphans": [o.model_dump() for o in orphans],
        },
        new_count=len(new_contacts),
        conflict_count=len(conflicts),
        unchanged_count=unchanged_count,
        status="pending",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    
    return ImportPreviewResponse(
        review_id=review.id,
        new_contacts=new_contacts,
        conflicts=conflicts,
        orphans=orphans,
        unchanged_count=unchanged_count,
        total_sheet_rows=len(sanitized_rows),
        import_tags=sanitized_import_tags,
    )


@router.post("/import/apply", response_model=ImportApplyResponse)
def apply_import(
    payload: ImportApplyRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Apply approved changes from an import preview.
    Only explicitly approved changes are applied.
    Uses optimistic locking to prevent concurrent modifications.
    Applies import_tags to all created/updated contacts.
    """
    review = db.query(SheetsImportReview).filter(
        SheetsImportReview.id == payload.review_id
    ).with_for_update().first()  # Lock the row
    
    if not review:
        raise HTTPException(status_code=404, detail="Import review not found")
    
    if review.status not in ("pending", "partial"):
        raise HTTPException(status_code=400, detail=f"Review is already {review.status}")
    
    # Check optimistic lock version
    current_version = review.import_data.get("version", 1) if review.import_data else 1
    if payload.expected_version is not None and payload.expected_version != current_version:
        raise HTTPException(
            status_code=409, 
            detail="Import review was modified. Please refresh and try again."
        )
    
    # Get import tags from the review
    import_tags = review.import_data.get("import_tags", []) if review.import_data else []
    
    errors = []
    changes_applied = 0
    contacts_created = 0
    total_tags_added = 0
    
    # Group approved changes by contact
    changes_by_contact: Dict[str, Dict[str, str]] = {}
    for change in payload.approved_changes:
        # Strict field validation
        if change.field not in EDITABLE_FIELDS:
            errors.append(f"Field '{change.field}' is not editable")
            continue
        
        # Validate and sanitize the value
        sanitized_value, validation_error = sanitize_and_validate_field(change.field, change.new_value)
        if validation_error:
            errors.append(validation_error)
            continue
        
        if change.contact_id not in changes_by_contact:
            changes_by_contact[change.contact_id] = {}
        changes_by_contact[change.contact_id][change.field] = sanitized_value
    
    # Apply changes to existing contacts
    for contact_id, field_changes in changes_by_contact.items():
        contact = db.query(Contact).options(joinedload(Contact.tags)).filter(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        ).first()
        
        if not contact:
            errors.append(f"Contact {contact_id} not found")
            continue
        
        # Track old values for audit
        old_values = {}
        new_values = {}
        
        for field, new_value in field_changes.items():
            old_val = getattr(contact, field, None)
            old_values[field] = str(old_val) if old_val else None
            
            # Handle special fields
            if field == "tags":
                # Tags come as comma-separated string
                tag_names = [sanitize_value(t.strip()) for t in new_value.split(",") if t.strip()]
                # Clear existing tags and add new ones
                contact.tags = []
                for tag_name in tag_names:
                    # Truncate tag name to reasonable length
                    tag_name = tag_name[:100]
                    tag = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        db.flush()
                    contact.tags.append(tag)
                new_values[field] = new_value
            else:
                setattr(contact, field, new_value if new_value else None)
                new_values[field] = new_value
            
            changes_applied += 1
        
        # Apply import tags to updated contacts
        if import_tags:
            tags_added = _add_import_tags_to_contact(db, contact, import_tags)
            total_tags_added += tags_added
            if tags_added > 0:
                new_values["import_tags_added"] = import_tags
        
        contact.updated_at = datetime.now(timezone.utc)
        
        # Audit log
        audit_service.log_action_sync(
            db=db,
            action="sheets.import_apply",
            entity_type="contact",
            entity_id=contact_id,
            old_values=old_values,
            new_values=new_values,
            user_id=str(admin.id),
        )
    
    # Create new contacts if any approved
    if payload.import_new_contacts and review.conflict_data:
        new_contact_data = review.conflict_data.get("new_contacts", [])
        
        for idx in payload.import_new_contacts:
            # Find the new contact data by row index
            new_data = next((n for n in new_contact_data if n.get("row_index") == idx), None)
            if not new_data:
                errors.append(f"New contact at row {idx} not found in review data")
                continue
            
            # Check for pre-existing validation errors
            if new_data.get("validation_errors"):
                errors.append(f"Row {idx} has validation errors: {', '.join(new_data['validation_errors'])}")
                continue
            
            raw = new_data.get("raw_data", {})
            
            # Validate and sanitize all fields for new contact
            email, email_err = sanitize_and_validate_field("email", raw.get("email", ""))
            if email_err:
                errors.append(f"Row {idx}: {email_err}")
                continue
            
            linkedin, linkedin_err = sanitize_and_validate_field("linkedin_url", raw.get("linkedin_url", ""))
            if linkedin_err:
                errors.append(f"Row {idx}: {linkedin_err}")
                continue
            
            website, website_err = sanitize_and_validate_field("website", raw.get("website", ""))
            if website_err:
                errors.append(f"Row {idx}: {website_err}")
                continue
            
            # Check for duplicate email
            if email:
                existing = db.query(Contact).filter(
                    Contact.email == email,
                    Contact.deleted_at.is_(None)
                ).first()
                if existing:
                    errors.append(f"Contact with email {email} already exists")
                    continue
            
            # Sanitize and truncate all fields
            first_name = truncate_field(sanitize_value(raw.get("first_name", "").strip()), "first_name")
            last_name = truncate_field(sanitize_value(raw.get("last_name", "").strip()), "last_name")
            phone = truncate_field(sanitize_value(raw.get("phone", "").strip()), "phone")
            company = truncate_field(sanitize_value(raw.get("company", "").strip()), "company")
            title = truncate_field(sanitize_value(raw.get("title", "").strip()), "title")
            status = truncate_field(sanitize_value(raw.get("status", "").strip()), "status") or "active"
            lead_source = truncate_field(sanitize_value(raw.get("lead_source", "").strip()), "lead_source") or "sheets_import"
            notes = truncate_field(sanitize_value(raw.get("notes", "").strip()), "notes")
            sarson_rep = truncate_field(sanitize_value(raw.get("sarson_rep", "").strip()), "sarson_rep")
            city = truncate_field(sanitize_value(raw.get("city", "").strip()), "city")
            state = truncate_field(sanitize_value(raw.get("state", "").strip()), "state")
            country = truncate_field(sanitize_value(raw.get("country", "").strip()), "country")
            
            # Create contact
            new_contact = Contact(
                first_name=first_name or None,
                last_name=last_name or None,
                email=email or None,
                phone=phone or None,
                company=company or None,
                title=title or None,
                status=status,
                lead_source=lead_source,
                notes=notes or None,
                sarson_rep=sarson_rep or None,
                city=city or None,
                state=state or None,
                country=country or None,
                linkedin_url=linkedin or None,
                website=website or None,
            )
            db.add(new_contact)
            db.flush()
            
            # Handle tags from sheet
            tags_str = raw.get("tags", "").strip()
            if tags_str:
                tag_names = [sanitize_value(t.strip())[:100] for t in tags_str.split(",") if t.strip()]
                for tag_name in tag_names:
                    tag = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        db.flush()
                    new_contact.tags.append(tag)
            
            # Apply import tags to new contacts
            if import_tags:
                tags_added = _add_import_tags_to_contact(db, new_contact, import_tags)
                total_tags_added += tags_added
            
            audit_service.log_action_sync(
                db=db,
                action="sheets.import_create",
                entity_type="contact",
                entity_id=str(new_contact.id),
                new_values={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "source": "sheets_import",
                    "import_tags": import_tags if import_tags else None,
                },
                user_id=str(admin.id),
            )
            
            contacts_created += 1
    
    # Update review status and increment version
    review.status = "approved" if not errors else "partial"
    review.applied_count = changes_applied + contacts_created
    review.reviewed_by = admin.id
    review.reviewed_at = datetime.now(timezone.utc)
    
    # Update version for optimistic locking
    new_version = current_version + 1
    if review.import_data:
        review.import_data = {**review.import_data, "version": new_version}
    else:
        review.import_data = {"version": new_version}
    
    db.commit()
    
    return ImportApplyResponse(
        changes_applied=changes_applied,
        contacts_created=contacts_created,
        tags_added=total_tags_added,
        errors=errors,
        version=new_version,
    )
