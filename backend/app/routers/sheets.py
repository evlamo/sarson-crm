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
- GET  /api/v1/sheets/imports        — List past import reviews
- GET  /api/v1/sheets/config         — Get sheets config
- POST /api/v1/sheets/config         — Save sheets config
- POST /api/v1/sheets/test           — Test connection
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_admin_user
from app.models.user import User
from app.services import sheets_service
from app.services.sheets_service import (
    SheetsServiceError,
    SheetsAuthError,
    SheetsNotFoundError,
    SheetsConfigError,
    SheetsConflictError,
)
from app.services import audit_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sheets", tags=["sheets"])


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
    import_tags: List[str] = Field(default_factory=list, max_length=20, description="Tags to auto-apply to all imported contacts (max 20)")


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


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Get current Google Sheets configuration."""
    return ConfigResponse(**sheets_service.get_sheets_config(db))


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
    try:
        credentials_updated = sheets_service.save_sheets_config(
            db, payload.spreadsheet_id, payload.sheet_name,
            payload.credentials_json, str(admin.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if credentials_updated:
        audit_service.log_action_sync(
            db=db,
            action="sheets.config_update",
            entity_type="settings",
            entity_id=None,
            new_values={"credentials_updated": True, "spreadsheet_id": payload.spreadsheet_id},
            user_id=str(admin.id),
        )

    db.commit()
    return ConfigResponse(**sheets_service.get_sheets_config(db))


@router.post("/test", response_model=TestResponse)
def test_sheets_connection(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """Test connection to Google Sheets with current configuration."""
    result = sheets_service.run_connection_test(db)
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
    try:
        result = sheets_service.run_export(
            db, payload.spreadsheet_id, payload.sheet_name,
            payload.list_id, admin.id
        )
        return ExportResponse(**result)
    except SheetsConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SheetsAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except SheetsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SheetsServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports", response_model=List[ExportListItem])
def list_exports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """List past exports with pagination."""
    return [ExportListItem(**item) for item in sheets_service.get_exports_list(db, page, per_page)]


@router.get("/imports", response_model=List[ImportHistoryItem])
def list_imports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """List past import reviews with pagination."""
    return [ImportHistoryItem(**item) for item in sheets_service.get_imports_list(db, page, per_page)]


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
    try:
        result = sheets_service.run_import_preview(
            db, payload.spreadsheet_id, payload.sheet_name, payload.import_tags
        )
        return ImportPreviewResponse(
            review_id=result["review_id"],
            new_contacts=[NewContactItem(**nc) for nc in result["new_contacts"]],
            conflicts=[ConflictItem(**c) for c in result["conflicts"]],
            orphans=[OrphanItem(**o) for o in result["orphans"]],
            unchanged_count=result["unchanged_count"],
            total_sheet_rows=result["total_sheet_rows"],
            import_tags=result["import_tags"],
        )
    except SheetsConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SheetsAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except SheetsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SheetsServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    approved_changes = [
        {"contact_id": c.contact_id, "field": c.field, "new_value": c.new_value}
        for c in payload.approved_changes
    ]
    try:
        result = sheets_service.run_import_apply(
            db, payload.review_id, admin.id,
            approved_changes, payload.import_new_contacts, payload.expected_version
        )
        return ImportApplyResponse(**result)
    except SheetsNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SheetsConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except SheetsConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))
