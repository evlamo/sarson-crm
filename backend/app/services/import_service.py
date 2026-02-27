"""CSV Import Service for Sarson Funds CRM.

Handles 30k+ contact imports with batch processing, dedup by email,
company resolution, tag creation, and robust date parsing.
"""

import csv
import io
import os
import re
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.company import Company
from app.models.tag import Tag, ContactTag
from app.models.import_job import ImportJob

BATCH_SIZE = 500

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")

# CSV header → contact field mapping
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
    "sales rep": "sales_rep",
    "notes": "notes",
    "last contact": "last_contacted_at",
    "next step": "next_step",
    "flw up date": "follow_up_date",
    "contact type": "_ignore",
    "contacted": "contacted",
    "status": "status",
    "source": "lead_source",
}

# Fields that are CSV injection vectors — sanitize values starting with these
_FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r"}


def _sanitize(value: str) -> str:
    """Strip CSV injection prefixes and whitespace."""
    v = value.strip()
    if v and v[0] in _FORMULA_CHARS:
        v = "'" + v
    return v


def _normalize_header(h: str) -> str:
    """Normalize a CSV header for matching."""
    return re.sub(r"\s+", " ", h.strip().lower()).rstrip("|").strip()


def _parse_date(val: str) -> Optional[datetime]:
    """Try multiple date formats. Returns None on failure."""
    if not val or not val.strip():
        return None
    val = val.strip()
    formats = [
        "%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y",
        "%m-%d-%y", "%d/%m/%Y", "%Y/%m/%d", "%m.%d.%Y",
        "%B %d, %Y", "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _parse_date_only(val: str) -> Optional[date]:
    dt = _parse_date(val)
    return dt.date() if dt else None


def _parse_bool(val: str) -> bool:
    return val.strip().upper() == "YES" if val else False


def build_header_mapping(headers: list[str]) -> dict[str, str]:
    """Map CSV headers to field names. Returns {csv_header: field_name}."""
    mapping = {}
    for h in headers:
        norm = _normalize_header(h)
        if norm in HEADER_MAP:
            mapping[h] = HEADER_MAP[norm]
        else:
            # Fuzzy: try prefix match
            for key, field in HEADER_MAP.items():
                if norm.startswith(key) or key.startswith(norm):
                    mapping[h] = field
                    break
    return mapping


def save_upload(file_content: bytes, filename: str) -> str:
    """Save uploaded CSV, return file path."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    safe_name = re.sub(r"[^\w.\-]", "_", filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    path = os.path.join(UPLOADS_DIR, unique_name)
    with open(path, "wb") as f:
        f.write(file_content)
    return path


def preview_csv(file_path: str) -> tuple[list[str], list[list[str]], int]:
    """Read headers, first 5 rows, and total row count."""
    # Handle BOM
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
                         header_mapping: dict[str, str]) -> ImportJob:
    """Create an ImportJob record."""
    job = ImportJob(
        id=uuid.uuid4(),
        filename=filename,
        status="pending",
        column_map={"file_path": file_path, "mapping": header_mapping},
        total_rows=row_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def execute_import(db: Session, job: ImportJob,
                   mapping_overrides: Optional[dict[str, str]] = None):
    """Execute the CSV import with batch processing."""
    job.status = "processing"
    job.started_at = datetime.utcnow()
    db.commit()

    file_path = job.column_map.get("file_path", "")
    mapping = job.column_map.get("mapping", {})
    if mapping_overrides:
        mapping.update(mapping_overrides)

    # Caches to avoid repeated DB queries
    company_cache: dict[str, uuid.UUID] = {}  # lowercase name → id
    tag_cache: dict[str, uuid.UUID] = {}      # lowercase name → id
    email_contact_cache: dict[str, uuid.UUID] = {}  # email → contact id

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

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch_contacts_new = []
            batch_contacts_update = []
            batch_tag_links = []  # (contact_id, tag_id)

            for row_num, row in enumerate(reader, start=2):
                try:
                    record = {}
                    company_name = None
                    company_website = None
                    sheet_tag = None
                    tab_tag = None

                    for csv_col, field in mapping.items():
                        raw = row.get(csv_col, "")
                        val = _sanitize(raw) if raw else ""

                        if field == "_ignore" or not val:
                            continue
                        elif field == "_sheet_tag":
                            sheet_tag = val
                        elif field == "_tab_tag":
                            tab_tag = val
                        elif field == "_company":
                            company_name = val
                        elif field == "_company_website":
                            company_website = val
                        elif field == "last_contacted_at":
                            record[field] = _parse_date(val)
                        elif field == "follow_up_date":
                            record[field] = _parse_date_only(val)
                        elif field == "contacted":
                            record[field] = _parse_bool(val)
                        elif field == "email":
                            record[field] = val.strip().lower()
                        elif field == "email_domain":
                            record[field] = val.strip().lower()
                        else:
                            record[field] = val

                    # Skip rows without email
                    email = record.get("email")
                    if not email:
                        skipped += 1
                        processed += 1
                        continue

                    # Resolve company
                    if company_name:
                        cname_lower = company_name.lower()
                        if cname_lower not in company_cache:
                            existing_co = db.query(Company).filter(
                                func.lower(Company.name) == cname_lower,
                                Company.deleted_at.is_(None)
                            ).first()
                            if existing_co:
                                company_cache[cname_lower] = existing_co.id
                                if company_website and not existing_co.website:
                                    existing_co.website = company_website
                            else:
                                new_co = Company(
                                    id=uuid.uuid4(),
                                    name=company_name,
                                    website=company_website or None,
                                )
                                db.add(new_co)
                                db.flush()
                                company_cache[cname_lower] = new_co.id
                        record["company_id"] = company_cache[cname_lower]
                        record["company"] = company_name

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
                                    new_tag = Tag(
                                        id=uuid.uuid4(),
                                        name=tag_name,
                                        category="import",
                                    )
                                    db.add(new_tag)
                                    db.flush()
                                    tag_cache[tname_lower] = new_tag.id
                            tag_ids.append(tag_cache[tname_lower])

                    # Dedup by email
                    if email in email_contact_cache:
                        # Update existing — only non-empty values
                        contact_id = email_contact_cache[email]
                        update_data = {k: v for k, v in record.items()
                                       if v is not None and v != "" and k != "email"}
                        if update_data:
                            db.query(Contact).filter(Contact.id == contact_id).update(
                                update_data, synchronize_session=False
                            )
                        for tid in tag_ids:
                            batch_tag_links.append((contact_id, tid))
                        updated += 1
                    else:
                        # Create new contact
                        contact_id = uuid.uuid4()
                        record["id"] = contact_id
                        record["source_import_id"] = str(job.id)
                        batch_contacts_new.append(record)
                        email_contact_cache[email] = contact_id
                        for tid in tag_ids:
                            batch_tag_links.append((contact_id, tid))
                        created += 1

                    processed += 1

                    # Batch commit
                    if processed % BATCH_SIZE == 0:
                        if batch_contacts_new:
                            db.bulk_insert_mappings(Contact, batch_contacts_new)
                            batch_contacts_new = []
                        _insert_tag_links(db, batch_tag_links)
                        batch_tag_links = []
                        db.commit()
                        # Update progress
                        job.imported_count = created
                        job.updated_count = updated
                        job.skipped_count = skipped
                        db.commit()

                except Exception as e:
                    errors.append({"row": row_num, "error": str(e)[:200]})
                    skipped += 1
                    processed += 1

            # Final batch
            if batch_contacts_new:
                db.bulk_insert_mappings(Contact, batch_contacts_new)
            _insert_tag_links(db, batch_tag_links)
            db.commit()

        job.status = "complete"
    except Exception as e:
        job.status = "failed"
        errors.append({"row": 0, "error": f"Fatal: {str(e)[:500]}"})
        db.rollback()

    job.imported_count = created
    job.updated_count = updated
    job.skipped_count = skipped
    job.error_count = len(errors)
    job.errors = errors[:1000]  # Cap stored errors
    job.completed_at = datetime.utcnow()
    db.commit()


def _insert_tag_links(db: Session, links: list[tuple]):
    """Insert contact_tags, ignoring duplicates."""
    if not links:
        return
    for contact_id, tag_id in links:
        stmt = pg_insert(ContactTag).values(
            contact_id=contact_id, tag_id=tag_id
        ).on_conflict_do_nothing()
        db.execute(stmt)
