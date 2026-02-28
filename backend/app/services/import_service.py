"""Import Service for Sarson Funds CRM.

Handles multi-format contact imports with batch processing, dedup by email,
company resolution, tag creation, and robust data normalization.
"""

import csv
import io
import os
import re
import uuid
from datetime import datetime, date
from app.utils.time import utcnow
from app.utils.time import utcnow
from typing import Optional

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.company import Company
from app.models.tag import Tag, ContactTag
from app.models.import_job import ImportJob
from app.services.file_parser import parse_file
from app.services.company_service import get_or_create_company as _get_or_create_company
from app.services.import_normalizer import (
    map_headers, normalize_row, sanitize_value,
    normalize_email, normalize_phone, normalize_name,
    normalize_status, normalize_date, normalize_bool, normalize_country,
)

BATCH_SIZE = 500

# Issue #7/#12: UPLOADS_DIR outside repo, configurable via env var
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "/tmp/crm_uploads")

# Whitelist of allowed CRM target field names (Issue #19)
ALLOWED_CRM_FIELDS = {
    "first_name", "middle_name", "last_name", "email", "phone", "title",
    "company", "city", "state", "country", "status", "lead_source",
    "sarson_rep", "next_step", "last_contacted_at", "contacted", "notes",
    "linkedin_url", "website", "profile_url", "email_domain",
    # Internal mapping fields
    "_company", "_company_website", "_sheet_tag", "_tab_tag", "_ignore",
    "__skip__",
}

# Legacy CSV header → contact field mapping (extended)
HEADER_MAP = {
    "sheet imported from": "_sheet_tag",
    "tab": "_tab_tag",
    "vc/company": "_company",
    "first": "first_name",
    "last": "last_name",
    "middle": "middle_name",
    "position": "title",
    "email": "email",
    "email domain": "email_domain",
    "phone": "phone",
    "website": "_company_website",
    "contact url": "profile_url",
    "sf rep": "sarson_rep",
    "notes": "notes",
    "last contact": "last_contacted_at",
    "next step": "next_step",
    "contact type": "_ignore",
    "contacted": "contacted",
    "status": "status",
    "source": "lead_source",
    # Extended aliases
    "first name": "first_name",
    "last name": "last_name",
    "middle name": "middle_name",
    "email address": "email",
    "phone number": "phone",
    "mobile": "phone",
    "cell": "phone",
    "job title": "title",
    "company": "_company",
    "organization": "_company",
    "company name": "_company",
    "city": "city",
    "state": "state",
    "country": "country",
    "lead source": "lead_source",
    "sarson rep": "sarson_rep",
    "linkedin": "linkedin_url",
    "linkedin url": "linkedin_url",
    "profile url": "profile_url",
}

_FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r"}


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", h.strip().lower()).rstrip("|").strip()


def build_header_mapping(headers: list[str]) -> dict[str, str]:
    """Map headers to field names using both legacy HEADER_MAP and new normalizer."""
    mapping = {}
    for h in headers:
        norm = _normalize_header(h)
        if norm in HEADER_MAP:
            mapping[h] = HEADER_MAP[norm]
        else:
            for key, field in HEADER_MAP.items():
                if norm.startswith(key) or key.startswith(norm):
                    mapping[h] = field
                    break
    
    # Also try the new normalizer for any unmapped headers
    new_mapping = map_headers(headers)
    for h, field in new_mapping.items():
        if h not in mapping:
            mapping[h] = field
    
    return mapping


def save_upload(file_content: bytes, filename: str) -> str:
    """Save uploaded file, return file path."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Issue #2/#11: ASCII-only filename sanitization
    safe_name = re.sub(r"[^a-zA-Z0-9.\-]", "_", filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    path = os.path.join(UPLOADS_DIR, unique_name)
    with open(path, "wb") as f:
        f.write(file_content)
    return path


def preview_csv(file_path: str) -> tuple[list[str], list[list[str]], int]:
    """Read headers, first 5 rows, and total row count."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = next(reader)
        preview_rows = []
        count = 0
        for row in reader:
            count += 1
            if count <= 5:
                preview_rows.append(row)
    return headers, preview_rows, count


def create_import_record(db: Session, filename: str, file_path: str,
                         headers: list[str], row_count: int,
                         header_mapping: dict[str, str],
                         filetype: str = "csv") -> ImportJob:
    """Create an ImportJob record."""
    job = ImportJob(
        id=uuid.uuid4(),
        filename=filename,
        status="pending",
        column_map={"file_path": file_path, "mapping": header_mapping, "filetype": filetype},
        total_rows=row_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def validate_mapping_overrides(overrides: dict[str, str]) -> None:
    """Issue #19: Validate mapping override values against whitelist."""
    invalid = [v for v in overrides.values() if v not in ALLOWED_CRM_FIELDS]
    if invalid:
        raise ValueError(f"Unknown target fields: {', '.join(invalid)}")


def execute_import(db: Session, job: ImportJob,
                   mapping_overrides: Optional[dict[str, str]] = None):
    """Execute the import with batch processing — supports all file formats."""
    job.status = "processing"
    job.started_at = utcnow()
    db.commit()  # Issue #20: commit processing status before doing work

    file_path = job.column_map.get("file_path", "")
    mapping = job.column_map.get("mapping", {})
    filetype = job.column_map.get("filetype", "csv")
    if mapping_overrides:
        mapping.update(mapping_overrides)

    company_cache: dict[str, uuid.UUID] = {}
    tag_cache: dict[str, uuid.UUID] = {}
    email_contact_cache: dict[str, uuid.UUID] = {}

    # Pre-load existing emails for dedup
    existing = db.query(Contact.email, Contact.id).filter(
        Contact.email.isnot(None), Contact.deleted_at.is_(None)
    ).all()
    for e, cid in existing:
        if e:
            email_contact_cache[e.lower()] = cid

    created = 0
    updated = 0
    skipped = 0
    errors = []
    processed = 0
    # Track in-file emails for duplicate detection (Issue #10/#16)
    seen_emails_in_file: set[str] = set()

    try:
        # Parse using the multi-format parser
        rows = parse_file(file_path, filetype)

        batch_contacts_new = []
        batch_tag_links = []

        for row_num, raw_row in enumerate(rows, start=2):
            try:
                # Map raw headers to CRM fields
                mapped_row = {}
                company_name = None
                company_website = None
                sheet_tag = None
                tab_tag = None

                for raw_col, raw_val in raw_row.items():
                    field = mapping.get(raw_col)
                    if not field or not raw_val:
                        continue
                    val = sanitize_value(str(raw_val))
                    if not val:
                        continue

                    if field == "_ignore" or field == "__skip__":
                        continue
                    elif field == "_sheet_tag":
                        sheet_tag = val
                    elif field == "_tab_tag":
                        tab_tag = val
                    elif field == "_company":
                        company_name = val
                    elif field == "_company_website":
                        company_website = val
                    else:
                        mapped_row[field] = val

                # For vCard files, fields come pre-mapped
                if filetype == "vcf":
                    for field in ("first_name", "last_name", "middle_name", "email",
                                  "phone", "company", "title", "linkedin_url",
                                  "website", "notes", "city", "state", "country"):
                        if field in raw_row and field not in mapped_row:
                            mapped_row[field] = raw_row[field]
                    if "company" in mapped_row and not company_name:
                        company_name = mapped_row.pop("company", None)

                # Normalize all fields
                normalized = normalize_row(mapped_row)

                # Skip rows without email (Issue #10: record reason)
                email = normalized.get("email")
                if not email:
                    skipped += 1
                    processed += 1
                    errors.append({"row": row_num, "error": "Skipped: missing or invalid email"})
                    continue

                # Issue #16: Check for in-file duplicate emails
                if email in seen_emails_in_file:
                    skipped += 1
                    processed += 1
                    errors.append({"row": row_num, "error": f"Skipped: duplicate email '{email}' within file"})
                    continue
                seen_emails_in_file.add(email)

                # Resolve company via shared service
                if company_name:
                    cname_lower = company_name.lower()
                    if cname_lower not in company_cache:
                        co = _get_or_create_company(db, company_name)
                        if co:
                            company_cache[cname_lower] = co.id
                            if company_website and not co.website:
                                co.website = company_website
                    if cname_lower in company_cache:
                        normalized["company_id"] = company_cache[cname_lower]
                        normalized["company"] = company_name

                # Resolve tags
                tag_ids = []
                for tag_name in [sheet_tag, tab_tag]:
                    if tag_name:
                        tname_lower = tag_name.lower()
                        if tname_lower not in tag_cache:
                            existing_tag = db.query(Tag).filter(
                                func.lower(Tag.name) == tname_lower
                            ).first()
                            if existing_tag:
                                tag_cache[tname_lower] = existing_tag.id
                            else:
                                new_tag = Tag(id=uuid.uuid4(), name=tag_name, category="import")
                                db.add(new_tag)
                                db.flush()
                                tag_cache[tname_lower] = new_tag.id
                        tag_ids.append(tag_cache[tname_lower])

                # POC enforcement — skip if company already has a POC
                if normalized.get("status") == "poc" and normalized.get("company_id"):
                    existing_poc = db.query(Contact).filter(
                        Contact.company_id == normalized["company_id"],
                        Contact.status == "poc",
                        Contact.deleted_at.is_(None),
                    ).first()
                    if existing_poc:
                        skipped += 1
                        processed += 1
                        errors.append({"row": row_num, "error": f"Skipped: company already has POC ({existing_poc.full_name})"})
                        continue

                # Sync poc_contact_id on company when importing a POC contact
                _import_poc_company_id = normalized.get("company_id")
                _import_poc_status = normalized.get("status")

                # Dedup by email against existing DB contacts
                if email in email_contact_cache:
                    skipped += 1
                    errors.append({"row": row_num, "error": f"Skipped: email '{email}' already exists in CRM"})
                else:
                    contact_id = uuid.uuid4()
                    normalized["id"] = contact_id
                    normalized["source_import_id"] = str(job.id)
                    batch_contacts_new.append(normalized)
                    email_contact_cache[email] = contact_id
                    # If this contact is POC, sync company.poc_contact_id
                    if _import_poc_status == "poc" and _import_poc_company_id:
                        company_obj = db.query(Company).filter(Company.id == _import_poc_company_id).first()
                        if company_obj:
                            company_obj.poc_contact_id = contact_id
                    for tid in tag_ids:
                        batch_tag_links.append((contact_id, tid))
                    created += 1

                processed += 1

                # Issue #14: Use flush instead of commit for batches
                if processed % BATCH_SIZE == 0:
                    if batch_contacts_new:
                        db.bulk_insert_mappings(Contact, batch_contacts_new)
                        batch_contacts_new = []
                    _insert_tag_links(db, batch_tag_links)
                    batch_tag_links = []
                    db.flush()
                    # Update progress for polling (Issue #23)
                    job.imported_count = created
                    job.updated_count = updated
                    job.skipped_count = skipped
                    db.flush()

            except Exception as e:
                errors.append({"row": row_num, "error": str(e)[:200]})
                skipped += 1
                processed += 1

        # Final batch
        if batch_contacts_new:
            db.bulk_insert_mappings(Contact, batch_contacts_new)
        _insert_tag_links(db, batch_tag_links)

        # Issue #14: Single commit at the very end
        job.status = "complete"
        job.imported_count = created
        job.updated_count = updated
        job.skipped_count = skipped
        job.error_count = len(errors)
        job.errors = errors[:1000]
        job.completed_at = utcnow()
        db.commit()

    except Exception as e:
        # Issue #14: Full rollback on any error
        db.rollback()
        job.status = "failed"
        errors.append({"row": 0, "error": f"Fatal: {str(e)[:500]}"})
        job.imported_count = created
        job.updated_count = updated
        job.skipped_count = skipped
        job.error_count = len(errors)
        job.errors = errors[:1000]
        job.completed_at = utcnow()
        db.commit()

    # Issue #5: Delete uploaded file after import
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass  # Don't break the response if file deletion fails


def _insert_tag_links(db: Session, links: list[tuple]):
    if not links:
        return
    for contact_id, tag_id in links:
        stmt = pg_insert(ContactTag).values(
            contact_id=contact_id, tag_id=tag_id
        ).on_conflict_do_nothing()
        db.execute(stmt)
