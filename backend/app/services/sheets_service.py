"""
Google Sheets two-way sync service.
Uses service account credentials for server-to-server auth.
No OAuth flow needed — admin configures service account once.

Security:
- Credentials stored encrypted in DB via api_credentials table
- Never log credentials or include in error messages
- All operations are admin-only
"""
import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from uuid import UUID

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Fields we sync between CRM and Sheets
SYNC_FIELDS = [
    "id", "first_name", "last_name", "email", "phone",
    "company", "title", "status", "tags", "lead_source",
    "last_contacted_at", "notes", "created_at", "sarson_rep",
    "city", "state", "country", "linkedin_url", "website"
]

# Fields that are editable in the sheet (excludes system fields like id, created_at)
EDITABLE_FIELDS = [
    "first_name", "last_name", "email", "phone", "company", "title",
    "status", "tags", "lead_source", "notes", "sarson_rep",
    "city", "state", "country", "linkedin_url", "website"
]


# ── Exceptions ─────────────────────────────────────────────────────────────

class SheetsServiceError(Exception):
    """Base exception for sheets service errors."""
    pass


class SheetsAuthError(SheetsServiceError):
    """Authentication/authorization error."""
    pass


class SheetsNotFoundError(SheetsServiceError):
    """Spreadsheet or sheet tab not found."""
    pass


class SheetsConfigError(SheetsServiceError):
    """Missing or invalid configuration (maps to 400)."""
    pass


class SheetsConflictError(SheetsServiceError):
    """Optimistic lock conflict (maps to 409)."""
    pass


# ── Input Validation & Sanitization ───────────────────────────────────────

_FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r"}

FIELD_MAX_LENGTHS = {
    "first_name": 100,
    "last_name": 100,
    "email": 255,
    "phone": 50,
    "company": 255,
    "title": 255,
    "status": 50,
    "tags": 1000,
    "lead_source": 100,
    "notes": 10000,
    "sarson_rep": 100,
    "city": 100,
    "state": 100,
    "country": 100,
    "linkedin_url": 500,
    "website": 500,
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
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
    """Strip CSV injection prefixes and excessive whitespace."""
    if not value:
        return value
    v = value.strip()
    if v and v[0] in _FORMULA_CHARS:
        v = "'" + v
    v = v.replace("\x00", "")
    return v


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return True
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_url(url: str) -> bool:
    """Validate URL format for linkedin/website fields."""
    if not url:
        return True
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
    sanitized = sanitize_value(value.strip())
    if field == "email":
        if not validate_email(sanitized):
            return "", f"Invalid email format: {sanitized[:50]}"
    elif field in ("linkedin_url", "website"):
        if sanitized and not validate_url(sanitized):
            return "", f"Invalid URL format for {field}: {sanitized[:50]}"
    sanitized = truncate_field(sanitized, field)
    return sanitized, None


# ── Google Sheets API Helpers ──────────────────────────────────────────────

def get_sheets_client(credentials_json: str):
    """
    Build Sheets API client from service account JSON string.

    Args:
        credentials_json: Service account JSON as a string (decrypted)

    Returns:
        Google Sheets API service object

    Raises:
        SheetsAuthError: If credentials are invalid
    """
    try:
        creds_data = json.loads(credentials_json)
        creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)
    except json.JSONDecodeError:
        raise SheetsAuthError("Invalid service account JSON format")
    except Exception as e:
        logger.error(f"Failed to initialize Sheets client: {type(e).__name__}")
        raise SheetsAuthError("Failed to authenticate with Google Sheets")


def _ensure_sheet_tab_exists(sheets_service, spreadsheet_id: str, sheet_name: str) -> bool:
    """
    Ensure the named sheet tab exists in the spreadsheet.
    Creates it if it doesn't exist.

    Returns:
        True if sheet was created, False if it already existed
    """
    try:
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        existing_names = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        if sheet_name in existing_names:
            return False

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {"title": sheet_name}
                    }
                }]
            }
        ).execute()
        return True

    except HttpError as e:
        if e.resp.status == 404:
            raise SheetsNotFoundError(f"Spreadsheet not found or not accessible")
        elif e.resp.status == 403:
            raise SheetsAuthError("Service account doesn't have access to this spreadsheet")
        raise SheetsServiceError(f"Failed to access spreadsheet: {e.resp.status}")


def export_contacts_to_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    contacts: List[Dict[str, Any]],
    credentials_json: str,
    checkpoint_row: int = 0,
    batch_size: int = 500,
) -> Dict[str, Any]:
    """
    Export contacts to a Google Sheet.
    Creates sheet if it doesn't exist. Supports resumable export via checkpoint.

    Args:
        spreadsheet_id: The Google Sheets spreadsheet ID
        sheet_name: Name of the tab within the spreadsheet
        contacts: List of contact dicts to export
        credentials_json: Decrypted service account JSON
        checkpoint_row: Row to resume from (0 = start fresh)
        batch_size: Number of rows to write per API call

    Returns:
        {
            "rows_written": int,
            "spreadsheet_url": str,
            "checkpoint_row": int,
            "complete": bool
        }
    """
    service = get_sheets_client(credentials_json)
    sheets = service.spreadsheets()

    _ensure_sheet_tab_exists(service, spreadsheet_id, sheet_name)

    headers = SYNC_FIELDS

    rows = []
    if checkpoint_row == 0:
        rows.append(headers)

    for contact in contacts[checkpoint_row:]:
        row = []
        for field in headers:
            val = contact.get(field)
            if val is None:
                row.append("")
            elif field == "tags" and isinstance(val, list):
                row.append(", ".join(str(t) for t in val))
            elif isinstance(val, datetime):
                row.append(val.isoformat())
            else:
                row.append(str(val))
        rows.append(row)

    if not rows:
        return {
            "rows_written": 0,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
            "checkpoint_row": len(contacts),
            "complete": True
        }

    if checkpoint_row == 0:
        try:
            sheets.values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:Z"
            ).execute()
        except HttpError:
            pass

    start_row = 1 if checkpoint_row == 0 else checkpoint_row + 2
    total_written = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        range_name = f"'{sheet_name}'!A{start_row + total_written}"

        try:
            sheets.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                body={"values": batch}
            ).execute()
            total_written += len(batch)
        except HttpError as e:
            logger.error(f"Batch write failed at row {start_row + total_written}: {e.resp.status}")
            return {
                "rows_written": total_written,
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                "checkpoint_row": checkpoint_row + total_written,
                "complete": False,
                "error": f"Write failed at row {checkpoint_row + total_written}"
            }

    data_rows = total_written - (1 if checkpoint_row == 0 else 0)

    return {
        "rows_written": data_rows,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        "checkpoint_row": checkpoint_row + data_rows,
        "complete": True
    }


def read_sheet_data(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_json: str,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Read all rows from a sheet.

    Returns:
        Tuple of (headers, rows) where rows is list of dicts using header as keys

    Raises:
        SheetsNotFoundError: If spreadsheet or tab doesn't exist
        SheetsAuthError: If service account can't access spreadsheet
    """
    service = get_sheets_client(credentials_json)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A:Z"
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise SheetsNotFoundError(f"Spreadsheet or sheet '{sheet_name}' not found")
        elif e.resp.status == 403:
            raise SheetsAuthError("Service account doesn't have access to this spreadsheet")
        raise SheetsServiceError(f"Failed to read spreadsheet: {e.resp.status}")

    values = result.get("values", [])

    if not values or len(values) < 1:
        return [], []

    headers = values[0]
    rows = []

    for row in values[1:]:
        padded = row + [""] * (len(headers) - len(row))
        row_dict = {}
        for i, header in enumerate(headers):
            row_dict[header] = padded[i] if i < len(padded) else ""
        rows.append(row_dict)

    return headers, rows


def compare_contact_with_sheet_row(
    crm_contact: Dict[str, Any],
    sheet_row: Dict[str, str],
    crm_updated_at: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Compare a CRM contact with a sheet row and identify conflicts.

    Args:
        crm_contact: Contact data from CRM
        sheet_row: Row data from sheet
        crm_updated_at: CRM contact's updated_at timestamp

    Returns:
        Dict of field -> {crm_value, sheet_value} for fields that differ
    """
    conflicts = {}

    for field in EDITABLE_FIELDS:
        crm_val = crm_contact.get(field)
        sheet_val = sheet_row.get(field, "").strip()

        if crm_val is None:
            crm_str = ""
        elif field == "tags" and isinstance(crm_val, list):
            crm_str = ", ".join(str(t) for t in crm_val)
        elif isinstance(crm_val, datetime):
            crm_str = crm_val.isoformat()
        else:
            crm_str = str(crm_val).strip()

        if not sheet_val:
            continue

        if crm_str != sheet_val:
            conflicts[field] = {
                "crm_value": crm_str,
                "sheet_value": sheet_val
            }

    return conflicts


def test_connection(
    spreadsheet_id: str,
    credentials_json: str,
) -> Dict[str, Any]:
    """
    Test connectivity to Google Sheets with the given credentials.

    Returns:
        {success: bool, message: str, spreadsheet_title?: str}
    """
    try:
        service = get_sheets_client(credentials_json)
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        title = spreadsheet.get("properties", {}).get("title", "Unknown")
        sheets_list = [s["properties"]["title"] for s in spreadsheet.get("sheets", [])]

        return {
            "success": True,
            "message": f"Connected to '{title}'",
            "spreadsheet_title": title,
            "sheets": sheets_list
        }
    except SheetsAuthError as e:
        return {"success": False, "message": str(e)}
    except SheetsNotFoundError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"Connection test failed: {type(e).__name__}")
        return {"success": False, "message": "Connection test failed"}


# ── Settings Helpers ───────────────────────────────────────────────────────

def get_setting(db, key: str) -> Optional[str]:
    """Get a setting value from crm_settings table."""
    from sqlalchemy import text
    from app.utils.encryption import decrypt_value

    result = db.execute(
        text("SELECT value, encrypted FROM crm_settings WHERE key = :key"),
        {"key": key}
    ).fetchone()
    if not result:
        return None
    value, encrypted = result
    if encrypted and value:
        decrypted = decrypt_value(value)
        if decrypted == value and len(value) > 50:
            logger.error(f"Decryption may have failed for setting '{key}' — returning None for safety")
            return None
        return decrypted
    return value


def set_setting(db, key: str, value: Optional[str], encrypted: bool = False, user_id: Optional[str] = None):
    """Set a setting value in crm_settings table."""
    from sqlalchemy import text
    from app.utils.encryption import encrypt_value

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


def get_credentials_json(db) -> Optional[str]:
    """Get decrypted service account JSON."""
    creds = get_setting(db, "sheets_credentials_json")
    if not creds:
        return None
    if not creds.strip().startswith("{"):
        logger.error("Credentials don't appear to be valid JSON — decryption may have failed")
        return None
    return creds


# ── Contact Helpers ────────────────────────────────────────────────────────

def build_contact_dict(contact) -> Dict[str, Any]:
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


def get_contacts_for_export(db, list_id=None) -> List[Dict[str, Any]]:
    """
    Get contacts for export. If list_id provided, export only that list's contacts.
    Uses yield_per for memory efficiency with large datasets.
    """
    from app.models.contact import Contact
    from app.models.static_list import StaticListMember
    from sqlalchemy.orm import joinedload

    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.deleted_at.is_(None))
    )
    if list_id:
        contact_ids = db.query(StaticListMember.c.contact_id).filter(
            StaticListMember.c.list_id == list_id
        ).subquery()
        query = query.filter(Contact.id.in_(contact_ids))

    contacts = query.order_by(Contact.last_name, Contact.first_name).yield_per(500).all()
    return [build_contact_dict(c) for c in contacts]


def get_or_create_tag(db, tag_name: str):
    """Get existing tag or create a new one."""
    from app.models.tag import Tag
    from sqlalchemy import func

    tag_name = tag_name.strip()[:100]
    tag = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
    if not tag:
        tag = Tag(name=tag_name)
        db.add(tag)
        db.flush()
    return tag


def add_import_tags_to_contact(db, contact, import_tags: List[str]) -> int:
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
        tag = get_or_create_tag(db, tag_name.strip())
        contact.tags.append(tag)
        added += 1

    return added


# ── Config Service Functions ───────────────────────────────────────────────

def get_sheets_config(db) -> dict:
    """Return sheets configuration as a dict (maps to ConfigResponse)."""
    spreadsheet_id = get_setting(db, "sheets_spreadsheet_id")
    sheet_name = get_setting(db, "sheets_default_sheet_name")
    credentials_set = get_credentials_json(db) is not None
    last_tested_at_str = get_setting(db, "sheets_last_tested_at")
    last_test_status = get_setting(db, "sheets_last_test_status")

    last_tested_at = None
    if last_tested_at_str:
        try:
            last_tested_at = datetime.fromisoformat(last_tested_at_str)
        except ValueError:
            pass

    return {
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name or "CRM Export",
        "credentials_set": credentials_set,
        "last_tested_at": last_tested_at,
        "last_test_status": last_test_status,
    }


def save_sheets_config(
    db,
    spreadsheet_id: Optional[str],
    sheet_name: Optional[str],
    credentials_json_str: Optional[str],
    user_id: str,
) -> bool:
    """
    Save config settings. Validates credentials JSON if provided.
    Returns True if credentials were updated (so caller can emit audit log).
    Raises ValueError for invalid credentials JSON.
    """
    if spreadsheet_id is not None:
        set_setting(db, "sheets_spreadsheet_id", spreadsheet_id, encrypted=False, user_id=user_id)

    if sheet_name is not None:
        set_setting(db, "sheets_default_sheet_name", sheet_name, encrypted=False, user_id=user_id)

    if credentials_json_str is not None:
        try:
            parsed = json.loads(credentials_json_str)
            if "type" not in parsed or parsed.get("type") != "service_account":
                raise ValueError("JSON must be a Google service account key (type: service_account)")
            if "client_email" not in parsed:
                raise ValueError("Service account JSON missing client_email field")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON format for credentials")

        set_setting(db, "sheets_credentials_json", credentials_json_str, encrypted=True, user_id=user_id)
        set_setting(db, "sheets_last_tested_at", None)
        set_setting(db, "sheets_last_test_status", None)
        return True  # credentials were updated

    return False


def run_connection_test(db) -> dict:
    """Test connection and persist result. Returns TestResponse-compatible dict."""
    credentials_json = get_credentials_json(db)
    if not credentials_json:
        return {"success": False, "message": "No service account credentials configured (or decryption failed)"}

    spreadsheet_id = get_setting(db, "sheets_spreadsheet_id")
    if not spreadsheet_id:
        return {"success": False, "message": "No spreadsheet ID configured"}

    result = test_connection(spreadsheet_id, credentials_json)

    set_setting(db, "sheets_last_tested_at", datetime.now(timezone.utc).isoformat())
    set_setting(db, "sheets_last_test_status", "success" if result["success"] else "failed")

    return result


# ── Export Service Function ────────────────────────────────────────────────

def run_export(db, spreadsheet_id: str, sheet_name: str, list_id, admin_id) -> dict:
    """
    Full export flow: validate → fetch contacts → write sheet → record audit.
    Returns ExportResponse-compatible dict.
    Raises SheetsConfigError, SheetsNotFoundError, SheetsAuthError, SheetsServiceError.
    """
    from app.models.sheets import SheetsExport
    from app.models.static_list import StaticList
    from app.services import audit_service

    credentials_json = get_credentials_json(db)
    if not credentials_json:
        raise SheetsConfigError("No service account credentials configured")

    list_name = None
    if list_id:
        static_list = db.query(StaticList).filter(StaticList.id == list_id).first()
        if not static_list:
            raise SheetsNotFoundError("List not found")
        list_name = static_list.name

    contacts = get_contacts_for_export(db, list_id)
    if not contacts:
        raise SheetsConfigError("No contacts to export")

    export_record = SheetsExport(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        filter_criteria={"list_id": str(list_id) if list_id else None},
        contact_count=len(contacts),
        exported_by=admin_id,
        list_id=list_id,
        sync_status="processing",
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    try:
        result = export_contacts_to_sheet(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            contacts=contacts,
            credentials_json=credentials_json,
        )

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
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "contact_count": result["rows_written"],
                "list_id": str(list_id) if list_id else None,
                "list_name": list_name,
            },
            user_id=str(admin_id),
        )
        db.commit()

        return {
            "export_id": export_record.id,
            "rows_written": result["rows_written"],
            "spreadsheet_url": result["spreadsheet_url"],
            "complete": result["complete"],
            "error": result.get("error"),
        }

    except (SheetsAuthError, SheetsNotFoundError, SheetsServiceError) as e:
        export_record.sync_status = "error"
        export_record.error_message = str(e)
        db.commit()
        raise


# ── List Service Functions ─────────────────────────────────────────────────

def get_exports_list(db, page: int, per_page: int) -> List[dict]:
    """Return paginated exports list as plain dicts."""
    from app.models.sheets import SheetsExport
    from app.models.static_list import StaticList
    from sqlalchemy.orm import joinedload

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
        result.append({
            "id": exp.id,
            "spreadsheet_id": exp.spreadsheet_id,
            "spreadsheet_url": exp.spreadsheet_url,
            "sheet_name": exp.sheet_name,
            "contact_count": exp.contact_count,
            "exported_at": exp.exported_at,
            "exported_by_name": exp.exporter.full_name if exp.exporter else None,
            "sync_status": exp.sync_status,
            "list_name": list_name,
        })
    return result


def get_imports_list(db, page: int, per_page: int) -> List[dict]:
    """Return paginated imports list as plain dicts."""
    from app.models.sheets import SheetsImportReview
    from sqlalchemy.orm import joinedload

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
        import_tags = []
        if review.import_data and isinstance(review.import_data, dict):
            import_tags = review.import_data.get("import_tags", [])
        result.append({
            "id": review.id,
            "status": review.status,
            "created_at": review.created_at,
            "reviewed_at": review.reviewed_at,
            "reviewed_by_name": review.reviewer.full_name if review.reviewer else None,
            "new_count": review.new_count or 0,
            "conflict_count": review.conflict_count or 0,
            "unchanged_count": review.unchanged_count or 0,
            "applied_count": review.applied_count or 0,
            "import_tags": import_tags,
        })
    return result


# ── Import Preview Service Function ───────────────────────────────────────

def run_import_preview(db, spreadsheet_id: str, sheet_name: str, import_tags: List[str]) -> dict:
    """
    Pull sheet data, compare with CRM, create review record.
    Returns ImportPreviewResponse-compatible dict.
    Raises SheetsConfigError, SheetsAuthError, SheetsNotFoundError, SheetsServiceError.
    """
    from app.models.contact import Contact
    from app.models.sheets import SheetsImportReview
    from sqlalchemy.orm import joinedload

    credentials_json = get_credentials_json(db)
    if not credentials_json:
        raise SheetsConfigError("No service account credentials configured")

    headers, sheet_rows = read_sheet_data(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        credentials_json=credentials_json,
    )

    if not sheet_rows:
        raise SheetsConfigError("Sheet is empty or has no data rows")

    if "id" not in headers:
        raise SheetsConfigError(
            "Sheet must have an 'id' column to map back to CRM contacts"
        )

    sanitized_import_tags = [
        sanitize_value(tag.strip())[:100]
        for tag in import_tags
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

    conflicts = []
    new_contacts = []
    orphans = []
    unchanged_count = 0

    for row_idx, sheet_row in enumerate(sanitized_rows):
        sheet_id = sheet_row.get("id", "").strip()

        if not sheet_id:
            email = sheet_row.get("email", "").strip()
            validation_errors = []
            if email and not validate_email(email):
                validation_errors.append(f"Invalid email format: {email[:50]}")
            linkedin = sheet_row.get("linkedin_url", "").strip()
            if linkedin and not validate_url(linkedin):
                validation_errors.append(f"Invalid LinkedIn URL: {linkedin[:50]}")
            website = sheet_row.get("website", "").strip()
            if website and not validate_url(website):
                validation_errors.append(f"Invalid website URL: {website[:50]}")
            if email:
                new_contacts.append({
                    "row_index": row_idx,
                    "email": email,
                    "first_name": sheet_row.get("first_name", "").strip() or None,
                    "last_name": sheet_row.get("last_name", "").strip() or None,
                    "company": sheet_row.get("company", "").strip() or None,
                    "raw_data": sheet_row,
                    "validation_errors": validation_errors,
                })
            continue

        crm_contact = crm_contacts_by_id.get(sheet_id)

        if not crm_contact:
            orphans.append({
                "sheet_row_index": row_idx,
                "contact_id": sheet_id,
                "email": sheet_row.get("email", "").strip() or None,
                "name": f"{sheet_row.get('first_name', '')} {sheet_row.get('last_name', '')}".strip() or None,
            })
            continue

        crm_dict = build_contact_dict(crm_contact)
        row_conflicts = compare_contact_with_sheet_row(crm_dict, sheet_row)

        if row_conflicts:
            contact_name = crm_contact.full_name
            for field, values in row_conflicts.items():
                conflicts.append({
                    "contact_id": sheet_id,
                    "contact_name": contact_name,
                    "field": field,
                    "crm_value": values["crm_value"],
                    "sheet_value": values["sheet_value"],
                })
        else:
            unchanged_count += 1

    review = SheetsImportReview(
        import_data={
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "headers": headers,
            "rows": sanitized_rows,
            "version": 1,
            "import_tags": sanitized_import_tags,
        },
        conflict_data={
            "conflicts": conflicts,
            "new_contacts": new_contacts,
            "orphans": orphans,
        },
        new_count=len(new_contacts),
        conflict_count=len(conflicts),
        unchanged_count=unchanged_count,
        status="pending",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return {
        "review_id": review.id,
        "new_contacts": new_contacts,
        "conflicts": conflicts,
        "orphans": orphans,
        "unchanged_count": unchanged_count,
        "total_sheet_rows": len(sanitized_rows),
        "import_tags": sanitized_import_tags,
    }


# ── Import Apply Service Function ──────────────────────────────────────────

def run_import_apply(
    db,
    review_id,
    admin_id,
    approved_changes: List[dict],
    import_new_contacts: List[int],
    expected_version: Optional[int] = None,
) -> dict:
    """
    Apply approved changes from an import preview.
    Returns ImportApplyResponse-compatible dict.
    Raises SheetsNotFoundError, SheetsConfigError, SheetsConflictError.
    """
    from app.models.contact import Contact
    from app.models.tag import Tag
    from app.models.sheets import SheetsImportReview
    from app.services import audit_service
    from sqlalchemy import func
    from sqlalchemy.orm import joinedload

    review = db.query(SheetsImportReview).filter(
        SheetsImportReview.id == review_id
    ).with_for_update().first()

    if not review:
        raise SheetsNotFoundError("Import review not found")

    if review.status not in ("pending", "partial"):
        raise SheetsConfigError(f"Review is already {review.status}")

    current_version = review.import_data.get("version", 1) if review.import_data else 1
    if expected_version is not None and expected_version != current_version:
        raise SheetsConflictError("Import review was modified. Please refresh and try again.")

    import_tags = review.import_data.get("import_tags", []) if review.import_data else []

    errors = []
    changes_applied = 0
    contacts_created = 0
    total_tags_added = 0

    # Group approved changes by contact
    changes_by_contact: Dict[str, Dict[str, str]] = {}
    for change in approved_changes:
        field = change["field"]
        contact_id = change["contact_id"]
        new_value = change["new_value"]

        if field not in EDITABLE_FIELDS:
            errors.append(f"Field '{field}' is not editable")
            continue

        sanitized_value, validation_error = sanitize_and_validate_field(field, new_value)
        if validation_error:
            errors.append(validation_error)
            continue

        if contact_id not in changes_by_contact:
            changes_by_contact[contact_id] = {}
        changes_by_contact[contact_id][field] = sanitized_value

    # Apply changes to existing contacts
    for contact_id, field_changes in changes_by_contact.items():
        contact = db.query(Contact).options(joinedload(Contact.tags)).filter(
            Contact.id == contact_id,
            Contact.deleted_at.is_(None)
        ).first()

        if not contact:
            errors.append(f"Contact {contact_id} not found")
            continue

        old_values = {}
        new_values = {}

        for field, new_value in field_changes.items():
            old_val = getattr(contact, field, None)
            old_values[field] = str(old_val) if old_val else None

            if field == "tags":
                tag_names = [sanitize_value(t.strip()) for t in new_value.split(",") if t.strip()]
                contact.tags = []
                for tag_name in tag_names:
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

        if import_tags:
            tags_added = add_import_tags_to_contact(db, contact, import_tags)
            total_tags_added += tags_added
            if tags_added > 0:
                new_values["import_tags_added"] = import_tags

        contact.updated_at = datetime.now(timezone.utc)

        audit_service.log_action_sync(
            db=db,
            action="sheets.import_apply",
            entity_type="contact",
            entity_id=contact_id,
            old_values=old_values,
            new_values=new_values,
            user_id=str(admin_id),
        )

    # Create new contacts if any approved
    if import_new_contacts and review.conflict_data:
        new_contact_data = review.conflict_data.get("new_contacts", [])

        for idx in import_new_contacts:
            new_data = next((n for n in new_contact_data if n.get("row_index") == idx), None)
            if not new_data:
                errors.append(f"New contact at row {idx} not found in review data")
                continue

            if new_data.get("validation_errors"):
                errors.append(f"Row {idx} has validation errors: {', '.join(new_data['validation_errors'])}")
                continue

            raw = new_data.get("raw_data", {})

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

            if email:
                existing = db.query(Contact).filter(
                    Contact.email == email,                    Contact.deleted_at.is_(None)
                ).first()
                if existing:
                    errors.append(f"Contact with email {email} already exists")
                    continue

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

            if import_tags:
                tags_added = add_import_tags_to_contact(db, new_contact, import_tags)
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
                user_id=str(admin_id),
            )
            contacts_created += 1

    review.status = "approved" if not errors else "partial"
    review.applied_count = changes_applied + contacts_created
    review.reviewed_by = admin_id
    review.reviewed_at = datetime.now(timezone.utc)

    new_version = current_version + 1
    if review.import_data:
        review.import_data = {**review.import_data, "version": new_version}
    else:
        review.import_data = {"version": new_version}

    db.commit()

    return {
        "changes_applied": changes_applied,
        "contacts_created": contacts_created,
        "tags_added": total_tags_added,
        "errors": errors,
        "version": new_version,
    }
