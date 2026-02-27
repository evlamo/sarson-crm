from pydantic import BaseModel, Field
from typing import Optional, List, Any, Literal, Union, ForwardRef
from datetime import datetime
import uuid


# ── Filter Rules ───────────────────────────────────────────────────────────

ALLOWED_OPERATORS = {
    "eq", "neq", "contains", "not_contains", "starts_with",
    "gt", "gte", "lt", "lte", "is_null", "is_not_null", "in", "not_in",
}

ALLOWED_FIELDS = {
    # Identity
    "first_name", "last_name", "middle_name", "email", "email_secondary",
    "phone", "phone_secondary",
    # Professional
    "title", "company", "department", "linkedin_url", "website",
    "email_domain", "profile_url", "sarson_rep", "sales_rep",
    # Location
    "city", "state", "country", "timezone",
    # CRM
    "contact_type", "status", "lead_source", "owner_id", "assigned_to",
    "next_step", "follow_up_date", "contacted",
    # Engagement
    "last_contacted_at", "last_emailed_at", "email_open_count", "email_click_count",
    # Email deliverability
    "email_valid", "email_bounced", "email_unsubscribed", "unsubscribed_at",
    # Investment
    "commitment_amount", "commitment_currency", "investor_tier",
    "fund_interest", "accredited_status", "kyc_completed", "kyc_completed_at",
    # Meta
    "notes", "source_import_id", "created_at", "updated_at",
    # Special
    "tags",
}


class FilterCondition(BaseModel):
    field: str
    op: str
    value: Any = None

    def model_post_init(self, __context: Any) -> None:
        if self.field not in ALLOWED_FIELDS:
            raise ValueError(f"Field '{self.field}' is not allowed for filtering")
        if self.op not in ALLOWED_OPERATORS:
            raise ValueError(f"Operator '{self.op}' is not supported")
        if self.op in ("in", "not_in") and not isinstance(self.value, list):
            raise ValueError(f"Operator '{self.op}' requires an array value")
        if self.op in ("is_null", "is_not_null") and self.value is not None:
            raise ValueError(f"Operator '{self.op}' should not have a value")


class FilterGroup(BaseModel):
    operator: Literal["AND", "OR"] = "AND"
    conditions: List[Union[FilterCondition, "FilterGroup"]] = Field(default_factory=list)


# Allow recursive model
FilterGroup.model_rebuild()


# ── Segment CRUD ───────────────────────────────────────────────────────────

class SegmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    filter_rules: FilterGroup


class SegmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    filter_rules: Optional[FilterGroup] = None


class SegmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    filter_rules: dict
    contact_count: int = 0
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    data: List[SegmentResponse]
    total: int


class SegmentContactsResponse(BaseModel):
    data: list
    total: int
    page: int
    per_page: int
