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
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

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


class SheetsServiceError(Exception):
    """Base exception for sheets service errors."""
    pass


class SheetsAuthError(SheetsServiceError):
    """Authentication/authorization error."""
    pass


class SheetsNotFoundError(SheetsServiceError):
    """Spreadsheet or sheet tab not found."""
    pass


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
        # Never log the actual credentials
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
        
        # Create the sheet
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
    
    # Ensure tab exists
    _ensure_sheet_tab_exists(service, spreadsheet_id, sheet_name)
    
    # Build headers
    headers = SYNC_FIELDS
    
    # Build all rows
    rows = []
    if checkpoint_row == 0:
        # Starting fresh - add header row
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
    
    # Clear existing data if starting fresh
    if checkpoint_row == 0:
        try:
            sheets.values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:Z"
            ).execute()
        except HttpError:
            pass  # Sheet might be new/empty
    
    # Write in batches
    start_row = 1 if checkpoint_row == 0 else checkpoint_row + 2  # +2 for header and 1-indexed
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
    
    # Subtract header row from count if we wrote it
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
        # Pad row to header length
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
        
        # Normalize CRM value to string for comparison
        if crm_val is None:
            crm_str = ""
        elif field == "tags" and isinstance(crm_val, list):
            crm_str = ", ".join(str(t) for t in crm_val)
        elif isinstance(crm_val, datetime):
            crm_str = crm_val.isoformat()
        else:
            crm_str = str(crm_val).strip()
        
        # Skip if sheet value is empty (never overwrite with blank per spec)
        if not sheet_val:
            continue
        
        # Compare
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
