"""Unified file parser — CSV, TSV, XLSX, XLS, ODS, vCard → List[Dict]."""

import csv
import io
import os
import magic
from typing import List, Dict, Optional

# Magic byte signatures for allowed file types
ALLOWED_MIMES = {
    "text/plain", "text/csv", "text/tab-separated-values",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",  # xls
    "application/vnd.oasis.opendocument.spreadsheet",  # ods
    "text/x-vcard", "text/vcard", "text/directory",  # vcf
    "application/zip",  # xlsx/ods are zips
    "application/octet-stream",  # fallback
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ROWS = 10_000


def validate_file(filepath: str, claimed_ext: str) -> str:
    """Validate file size and magic bytes. Returns detected mime type."""
    size = os.path.getsize(filepath)
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large ({size // 1024 // 1024}MB). Max 10MB.")
    if size == 0:
        raise ValueError("Empty file")

    detected = magic.from_file(filepath, mime=True)
    # For text-based formats (csv/tsv/vcf), magic often returns text/plain
    if detected not in ALLOWED_MIMES:
        raise ValueError(f"Unsupported file type: {detected}")
    return detected


def parse_file(filepath: str, filetype: str) -> List[Dict]:
    """Parse any supported file into a list of row dicts.
    
    filetype: one of 'csv', 'tsv', 'xlsx', 'xls', 'ods', 'vcf'
    """
    filetype = filetype.lower().lstrip(".")
    
    parsers = {
        "csv": _parse_csv,
        "tsv": _parse_tsv,
        "xlsx": _parse_xlsx,
        "xls": _parse_xlsx,  # openpyxl handles both
        "ods": _parse_ods,
        "vcf": _parse_vcf,
    }
    
    parser = parsers.get(filetype)
    if not parser:
        raise ValueError(f"Unsupported format: {filetype}")
    
    rows = parser(filepath)
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Too many rows ({len(rows)}). Max {MAX_ROWS}.")
    return rows


def _parse_csv(filepath: str) -> List[Dict]:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _parse_tsv(filepath: str) -> List[Dict]:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [dict(row) for row in reader]


def _parse_xlsx(filepath: str) -> List[Dict]:
    import openpyxl
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        d = {}
        for i, val in enumerate(row):
            if i < len(headers):
                d[headers[i]] = str(val).strip() if val is not None else ""
        result.append(d)
    return result


def _parse_ods(filepath: str) -> List[Dict]:
    from odf.opendocument import load
    from odf.table import Table, TableRow, TableCell
    from odf.text import P
    
    doc = load(filepath)
    sheets = doc.getElementsByType(Table)
    if not sheets:
        return []
    sheet = sheets[0]
    
    all_rows = []
    for row in sheet.getElementsByType(TableRow):
        cells = []
        for cell in row.getElementsByType(TableCell):
            repeat = int(cell.getAttribute("numbercolumnsrepeated") or 1)
            text_parts = []
            for p in cell.getElementsByType(P):
                t = ""
                for child in p.childNodes:
                    if hasattr(child, "data"):
                        t += child.data
                    elif hasattr(child, "__str__"):
                        t += str(child)
                text_parts.append(t)
            val = "\n".join(text_parts).strip()
            cells.extend([val] * min(repeat, 100))  # cap repeat to avoid memory issues
        all_rows.append(cells)
    
    if not all_rows:
        return []
    
    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(all_rows[0])]
    # Strip trailing empty headers
    while headers and not headers[-1].strip():
        headers.pop()
    
    result = []
    for row in all_rows[1:]:
        d = {}
        for i, val in enumerate(row):
            if i < len(headers) and headers[i]:
                d[headers[i]] = str(val).strip() if val else ""
        if any(v for v in d.values()):  # skip fully empty rows
            result.append(d)
    return result


def _parse_vcf(filepath: str) -> List[Dict]:
    import vobject
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    result = []
    for card in vobject.readComponents(content):
        row = {}
        
        # Name
        if hasattr(card, "n"):
            n = card.n.value
            row["first_name"] = str(n.given or "").strip()
            row["last_name"] = str(n.family or "").strip()
            if hasattr(n, "additional") and n.additional:
                row["middle_name"] = str(n.additional).strip()
        
        # Email
        if hasattr(card, "email"):
            row["email"] = str(card.email.value).strip()
        
        # Phone
        if hasattr(card, "tel"):
            row["phone"] = str(card.tel.value).strip()
        
        # Organization/Title
        if hasattr(card, "org"):
            orgs = card.org.value
            if orgs:
                row["company"] = str(orgs[0]).strip()
        if hasattr(card, "title"):
            row["title"] = str(card.title.value).strip()
        
        # URL
        if hasattr(card, "url"):
            url_val = str(card.url.value).strip()
            if "linkedin" in url_val.lower():
                row["linkedin_url"] = url_val
            else:
                row["website"] = url_val
        
        # Note
        if hasattr(card, "note"):
            row["notes"] = str(card.note.value).strip()
        
        # Address
        if hasattr(card, "adr"):
            adr = card.adr.value
            if hasattr(adr, "city") and adr.city:
                row["city"] = str(adr.city).strip()
            if hasattr(adr, "region") and adr.region:
                row["state"] = str(adr.region).strip()
            if hasattr(adr, "country") and adr.country:
                row["country"] = str(adr.country).strip()
        
        if row:
            result.append(row)
    
    return result


def get_filetype_from_extension(filename: str) -> str:
    """Extract filetype from filename extension."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    type_map = {
        "csv": "csv", "tsv": "tsv", "txt": "tsv",
        "xlsx": "xlsx", "xls": "xls",
        "ods": "ods", "vcf": "vcf",
    }
    ft = type_map.get(ext)
    if not ft:
        raise ValueError(f"Unsupported file extension: .{ext}")
    return ft
