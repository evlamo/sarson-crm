"""Import router — multi-format upload (CSV/TSV/XLSX/ODS/vCard), preview, execute, status."""

import os
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.import_job import ImportJob
from app.auth.dependencies import get_current_user, require_not_restricted
from app.schemas.import_schema import (
    ImportUploadResponse, ImportStatusResponse,
    ImportExecuteRequest, ImportListResponse,
)
from app.services.import_service import (
    save_upload, create_import_record, execute_import,
    validate_mapping_overrides, UPLOADS_DIR,
)
from app.services.file_parser import (
    parse_file, validate_file, get_filetype_from_extension, MAX_FILE_SIZE,
)
from app.services.import_normalizer import map_headers
from app.services import audit_service

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".ods", ".vcf"}

# Issue #3: chunk size for streaming file size check
_CHUNK_SIZE = 64 * 1024  # 64KB


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file (CSV/TSV/XLSX/ODS/vCard) for import preview."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Issue #2/#6: Restrict filename to ASCII-only chars
    if not re.match(r'^[a-zA-Z0-9.\-_ ]+$', file.filename):
        raise HTTPException(400, "Filename must contain only ASCII letters, numbers, dots, hyphens, underscores, and spaces")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Issue #3: Read in chunks, enforce file size BEFORE reading entire file into memory
    chunks = []
    total_read = 0
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > MAX_FILE_SIZE:
            raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
        chunks.append(chunk)

    content = b"".join(chunks)
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    file_path = save_upload(content, file.filename)

    # Validate magic bytes
    try:
        validate_file(file_path, ext)
    except ValueError as e:
        os.unlink(file_path)
        raise HTTPException(400, str(e))

    # Parse file
    filetype = get_filetype_from_extension(file.filename)
    try:
        rows = parse_file(file_path, filetype)
    except ValueError as e:
        os.unlink(file_path)
        raise HTTPException(400, str(e))
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(400, f"Failed to parse file: {str(e)[:200]}")

    if not rows:
        raise HTTPException(400, "No data rows found in file")

    # Extract headers and build mapping
    headers = list(rows[0].keys()) if rows else []
    header_mapping = map_headers(headers)

    # Build preview (first 5 rows as list of lists)
    preview_rows = []
    for row in rows[:5]:
        preview_rows.append([row.get(h, "") for h in headers])

    row_count = len(rows)

    job = create_import_record(db, file.filename, file_path, headers, row_count, header_mapping, filetype)
    
    # Audit: import uploaded
    audit_service.log_action_sync(
        db=db,
        action="import.upload",
        entity_type="import",
        entity_id=str(job.id),
        new_values={
            "filename": file.filename,
            "row_count": row_count,
            "file_type": filetype,
        },
        user_id=str(current_user.id),
    )
    db.commit()

    return ImportUploadResponse(
        import_id=job.id,
        filename=file.filename,
        row_count=row_count,
        column_preview=preview_rows,
        header_mapping=header_mapping,
    )


@router.get("/{import_id}", response_model=ImportStatusResponse)
def get_import_status(
    import_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get import job status and progress."""
    job = db.query(ImportJob).filter(ImportJob.id == import_id).first()
    if not job:
        raise HTTPException(404, "Import not found")
    return ImportStatusResponse(
        id=job.id,
        filename=job.filename,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=(job.imported_count or 0) + (job.updated_count or 0) + (job.skipped_count or 0),
        created=job.imported_count or 0,
        updated=job.updated_count or 0,
        skipped=job.skipped_count or 0,
        errors=job.errors or [],
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.post("/{import_id}/execute", response_model=ImportStatusResponse)
def execute_import_job(
    import_id: UUID,
    body: ImportExecuteRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a pending import."""
    # Issue #20: Use with_for_update() to prevent TOCTOU race condition
    job = db.query(ImportJob).filter(
        ImportJob.id == import_id
    ).with_for_update().first()
    if not job:
        raise HTTPException(404, "Import not found")
    if job.status not in ("pending", "failed"):
        raise HTTPException(400, f"Import is already {job.status}")

    overrides = body.column_mapping if body else None

    # Issue #19: Validate mapping overrides against whitelist
    if overrides:
        try:
            validate_mapping_overrides(overrides)
        except ValueError as e:
            raise HTTPException(422, str(e))

    # Audit: import execution started
    audit_service.log_action_sync(
        db=db,
        action="import.execute_start",
        entity_type="import",
        entity_id=str(job.id),
        new_values={
            "filename": job.filename,
            "total_rows": job.total_rows,
            "has_overrides": overrides is not None,
        },
        user_id=str(current_user.id),
    )
    db.commit()

    execute_import(db, job, overrides)
    db.refresh(job)
    
    # Audit: import execution completed
    audit_service.log_action_sync(
        db=db,
        action="import.execute_complete",
        entity_type="import",
        entity_id=str(job.id),
        new_values={
            "status": job.status,
            "created": job.imported_count or 0,
            "updated": job.updated_count or 0,
            "skipped": job.skipped_count or 0,
            "error_count": job.error_count or 0,
        },
        user_id=str(current_user.id),
    )
    db.commit()

    return ImportStatusResponse(
        id=job.id,
        filename=job.filename,
        status=job.status,
        total_rows=job.total_rows,
        processed_rows=(job.imported_count or 0) + (job.updated_count or 0) + (job.skipped_count or 0),
        created=job.imported_count or 0,
        updated=job.updated_count or 0,
        skipped=job.skipped_count or 0,
        errors=job.errors or [],
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.delete("/{import_id}")
def delete_import_job(
    import_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    """Issue #18: Delete a staged import job and its uploaded file."""
    job = db.query(ImportJob).filter(ImportJob.id == import_id).first()
    if not job:
        raise HTTPException(404, "Import not found")
    if job.status == "processing":
        raise HTTPException(400, "Cannot delete an import that is currently processing")

    # Audit: import deleted
    audit_service.log_action_sync(
        db=db,
        action="import.delete",
        entity_type="import",
        entity_id=str(job.id),
        old_values={
            "filename": job.filename,
            "status": job.status,
            "total_rows": job.total_rows,
        },
        user_id=str(current_user.id),
    )

    # Delete the uploaded file
    file_path = job.column_map.get("file_path", "") if job.column_map else ""
    if file_path and os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except Exception:
            pass

    db.delete(job)
    db.commit()
    return {"detail": "Import deleted"}


@router.get("", response_model=list[ImportListResponse])
def list_imports(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all import jobs."""
    jobs = db.query(ImportJob).order_by(ImportJob.created_at.desc()).all()
    return [
        ImportListResponse(
            id=j.id,
            filename=j.filename,
            status=j.status,
            total_rows=j.total_rows,
            created=j.imported_count or 0,
            updated=j.updated_count or 0,
            skipped=j.skipped_count or 0,
            error_count=j.error_count or 0,
            created_at=j.created_at,
        )
        for j in jobs
    ]
