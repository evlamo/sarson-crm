from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ImportUploadResponse(BaseModel):
    import_id: UUID
    filename: str
    row_count: int
    column_preview: list[list[str]]
    header_mapping: dict[str, str]

    class Config:
        from_attributes = True


class ImportStatusResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    total_rows: Optional[int] = None
    processed_rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImportExecuteRequest(BaseModel):
    column_mapping: Optional[dict[str, str]] = None


class ImportListResponse(BaseModel):
    id: UUID
    filename: str
    status: str
    total_rows: Optional[int] = None
    created: int = 0
    updated: int = 0
    skipped: int = 0
    error_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
