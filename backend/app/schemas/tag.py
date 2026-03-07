import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid


def _validate_hex_color(v: str | None) -> str | None:
    if v is not None and not re.match(r'^#[0-9a-fA-F]{6}$', v):
        raise ValueError('Color must be a valid hex color (e.g. #ff0000)')
    return v


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field("#e8630a", max_length=20)
    category: Optional[str] = Field(None, max_length=50)

    @field_validator('color')
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, max_length=20)
    category: Optional[str] = Field(None, max_length=50)

    @field_validator('color')
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        return _validate_hex_color(v)


class TagResponse(TagBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True
