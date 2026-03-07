"""
Dynamic segment filter evaluation engine.

Converts JSON filter rules → SQLAlchemy query predicates.
All filtering uses parameterized queries — NO string interpolation of user input.
Field names are validated against a whitelist before use.
"""

from typing import List
from uuid import UUID

from sqlalchemy import and_, or_, exists, select, func, cast, String, Date
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.tag import Tag, ContactTag
from app.models.static_list import StaticListMember
from app.schemas.segment import ALLOWED_FIELDS, FilterCondition, FilterGroup


# ── Column Resolution ──────────────────────────────────────────────────────

# Map field names to Contact model columns (whitelist-enforced)
def _get_column(field: str):
    """Return the SQLAlchemy column for a whitelisted field. Raises ValueError for unknown fields."""
    if field == "tags":
        return None  # handled separately
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Field '{field}' not in whitelist")
    col = getattr(Contact, field, None)
    if col is None:
        raise ValueError(f"Field '{field}' does not exist on Contact model")
    return col


def _escape_like(val: str) -> str:
    """Escape special LIKE/ILIKE characters to prevent wildcard injection."""
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── Condition → Predicate ──────────────────────────────────────────────────

def _build_tag_predicate(op: str, value):
    """Build an EXISTS subquery for tag-based filtering."""
    tag_subq = (
        select(ContactTag.c.contact_id)
        .join(Tag, Tag.id == ContactTag.c.tag_id)
    )

    if op == "eq":
        tag_subq = tag_subq.where(Tag.name == value)
    elif op == "neq":
        # Contact does NOT have this tag
        return ~exists(
            tag_subq.where(
                Tag.name == value,
                ContactTag.c.contact_id == Contact.id,
            )
        )
    elif op == "contains":
        tag_subq = tag_subq.where(Tag.name.ilike(f"%{_escape_like(value)}%", escape="\\"))
    elif op == "not_contains":
        return ~exists(
            tag_subq.where(
                Tag.name.ilike(f"%{_escape_like(value)}%", escape="\\"),
                ContactTag.c.contact_id == Contact.id,
            )
        )
    elif op == "in":
        tag_subq = tag_subq.where(Tag.name.in_(value))
    elif op == "not_in":
        return ~exists(
            tag_subq.where(
                Tag.name.in_(value),
                ContactTag.c.contact_id == Contact.id,
            )
        )
    elif op == "is_null":
        return ~exists(
            tag_subq.where(ContactTag.c.contact_id == Contact.id)
        )
    elif op == "is_not_null":
        return exists(
            tag_subq.where(ContactTag.c.contact_id == Contact.id)
        )
    else:
        raise ValueError(f"Operator '{op}' not supported for tags")

    return exists(
        tag_subq.where(ContactTag.c.contact_id == Contact.id)
    )


def _build_condition_predicate(condition: FilterCondition):
    """Convert a single FilterCondition to a SQLAlchemy predicate."""
    if condition.field == "tags":
        return _build_tag_predicate(condition.op, condition.value)

    col = _get_column(condition.field)
    op = condition.op
    val = condition.value

    if op == "eq":
        return col == val
    elif op == "neq":
        return col != val
    elif op == "contains":
        return col.ilike(f"%{_escape_like(val)}%", escape="\\")
    elif op == "not_contains":
        return ~col.ilike(f"%{_escape_like(val)}%", escape="\\")
    elif op == "starts_with":
        return col.ilike(f"{_escape_like(val)}%", escape="\\")
    elif op == "gt":
        return col > val
    elif op == "gte":
        return col >= val
    elif op == "lt":
        return col < val
    elif op == "lte":
        return col <= val
    elif op == "is_null":
        return col.is_(None)
    elif op == "is_not_null":
        return col.isnot(None)
    elif op == "in":
        return col.in_(val)
    elif op == "not_in":
        return ~col.in_(val)
    else:
        raise ValueError(f"Unknown operator: {op}")


# ── Group → Predicate ─────────────────────────────────────────────────────

def _build_group_predicate(group: FilterGroup):
    """Recursively build predicates for a filter group (AND/OR with nesting)."""
    predicates = []
    for condition in group.conditions:
        if isinstance(condition, FilterGroup):
            predicates.append(_build_group_predicate(condition))
        else:
            predicates.append(_build_condition_predicate(condition))

    if not predicates:
        return True  # No conditions = match all

    if group.operator == "AND":
        return and_(*predicates)
    else:
        return or_(*predicates)


# ── Public API ─────────────────────────────────────────────────────────────

def build_segment_query(db: Session, filter_rules: dict):
    """
    Build a SQLAlchemy query for contacts matching the given filter rules.
    Returns a query on Contact (not yet executed).
    """
    group = FilterGroup.model_validate(filter_rules)
    predicate = _build_group_predicate(group)

    query = db.query(Contact).filter(Contact.deleted_at.is_(None))
    if predicate is not True:
        query = query.filter(predicate)
    return query


def count_segment_contacts(db: Session, filter_rules: dict) -> int:
    """Count contacts matching filter rules (efficient COUNT query)."""
    group = FilterGroup.model_validate(filter_rules)
    predicate = _build_group_predicate(group)

    query = db.query(func.count(Contact.id)).filter(Contact.deleted_at.is_(None))
    if predicate is not True:
        query = query.filter(predicate)
    return query.scalar()


def resolve_campaign_targets(target_type: str, target_id: UUID, db: Session) -> List[UUID]:
    """
    Returns contact_ids for either a dynamic segment or static list.
    Used by EMAIL-1 when sending campaigns.
    """
    if target_type == "segment":
        from app.models.segment import Segment
        segment = db.query(Segment).filter(Segment.id == target_id).first()
        if not segment:
            raise ValueError(f"Segment {target_id} not found")
        query = build_segment_query(db, segment.filters)
        return [row[0] for row in query.with_entities(Contact.id).all()]

    elif target_type == "static_list":
        from app.models.static_list import StaticList
        sl = db.query(StaticList).filter(StaticList.id == target_id).first()
        if not sl:
            raise ValueError(f"Static list {target_id} not found")
        rows = (
            db.query(StaticListMember.c.contact_id)
            .filter(StaticListMember.c.list_id == target_id)
            .all()
        )
        return [row[0] for row in rows]

    else:
        raise ValueError(f"Unknown target_type: {target_type}")
