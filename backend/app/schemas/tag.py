from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field("#e8630a", max_length=20)
    category: Optional[str] = Field(None, max_length=50)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=50)


class TagResponse(TagBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
