from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class StaticListCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class StaticListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)


class StaticListResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    member_count: int = 0
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaticListListResponse(BaseModel):
    data: List[StaticListResponse]
    total: int


class ContactIdsRequest(BaseModel):
    contact_ids: List[uuid.UUID] = Field(..., min_length=1, max_length=5000)


class StaticListContactsResponse(BaseModel):
    data: list
    total: int
    page: int
    per_page: int
