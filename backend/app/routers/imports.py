"""Import router — multi-format upload (CSV/TSV/XLSX/ODS/vCard), preview, execute, status."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.import_job import ImportJob
from app.auth.dependencies import get_current_user
from app.schemas.import_schema import (
    ImportUploadResponse, ImportStatusResponse,
    ImportExecuteRequest, ImportListResponse,
)
from app.services.import_service import (
    save_upload, create_import_record, execute_import,
)
from app.services.file_parser import (
    parse_file, validate_file, get_filetype_from_extension, MAX_FILE_SIZE,
)
from app.services.import_normalizer import map_headers

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".ods", ".vcf"}


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Upload a file (CSV/TSV/XLSX/ODS/vCard) for import preview."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    file_path = save_upload(content, file.filename)

    # Validate magic bytes
    try:
        validate_file(file_path, ext)
    except ValueError as e:
        import os as _os
        _os.unlink(file_path)
        raise HTTPException(400, str(e))

    # Parse file
    filetype = get_filetype_from_extension(file.filename)
    try:
        rows = parse_file(file_path, filetype)
    except ValueError as e:
        import os as _os
        _os.unlink(file_path)
        raise HTTPException(400, str(e))
    except Exception as e:
        import os as _os
        _os.unlink(file_path)
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
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute a pending import."""
    job = db.query(ImportJob).filter(ImportJob.id == import_id).first()
    if not job:
        raise HTTPException(404, "Import not found")
    if job.status not in ("pending", "failed"):
        raise HTTPException(400, f"Import is already {job.status}")

    overrides = body.column_mapping if body else None
    execute_import(db, job, overrides)
    db.refresh(job)

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
