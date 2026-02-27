"""Import router — CSV upload, preview, execute, status."""

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
    save_upload, preview_csv, build_header_mapping,
    create_import_record, execute_import,
)

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/upload", response_model=ImportUploadResponse)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Upload a CSV file for import preview."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    file_path = save_upload(content, file.filename)
    headers, preview_rows, row_count = preview_csv(file_path)
    header_mapping = build_header_mapping(headers)

    job = create_import_record(db, file.filename, file_path, headers, row_count, header_mapping)

    return ImportUploadResponse(
        import_id=job.id,
        filename=file.filename,
        row_count=row_count,
        column_preview=preview_rows,
        header_mapping=header_mapping,
    )


@router.get("/{import_id}", response_model=ImportStatusResponse)
def get_import_status(import_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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
def execute_import_job(import_id: UUID, body: ImportExecuteRequest = None, _: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
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
def list_imports(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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
