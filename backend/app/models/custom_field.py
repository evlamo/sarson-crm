import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String, nullable=False)  # contact | company | deal
    key = Column(String, nullable=False)
    label = Column(String, nullable=False)
    field_type = Column(String, nullable=False)  # text | number | date | boolean | select | multi_select
    options = Column(JSONB)
    required = Column(Boolean, default=False)
    position = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("entity_type", "key", name="uq_custom_field_entity_key"),)
