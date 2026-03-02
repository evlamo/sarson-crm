"""
Audit logging service.
Phase 1 Foundation — Fire-and-forget audit trail for all actions.
"""
from typing import Optional, Any
import json
import logging

logger = logging.getLogger(__name__)


def _safe_uuid_str(value: Any) -> Optional[str]:
    """Safely convert a value to string for UUID casting, handling None."""
    if value is None:
        return None
    return str(value)


async def log_action(
    db,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Log an action to the audit log.
    
    This is fire-and-forget safe — never raises exceptions.
    Always call this, even if you don't care about the result.
    
    Args:
        db: Database connection (asyncpg or SQLAlchemy session)
        action: Action identifier (e.g., 'contact.update', 'campaign.delete')
        entity_type: Entity type (e.g., 'contact', 'campaign', 'user')
        entity_id: UUID of the affected entity (can be None for actions without a specific entity)
        old_values: Previous state (for updates/deletes)
        new_values: New state (for creates/updates)
        user_id: UUID of the user performing the action
        ip_address: Client IP address
        user_agent: Client user agent string
    """
    try:
        # Safely convert UUIDs to strings (handles None, UUID objects, ints, etc.)
        safe_user_id = _safe_uuid_str(user_id)
        safe_entity_id = _safe_uuid_str(entity_id)
        
        # Handle both asyncpg and SQLAlchemy patterns
        if hasattr(db, 'execute') and not hasattr(db, 'add'):
            # asyncpg style - pass None directly when entity_id is None
            await db.execute("""
                INSERT INTO audit_log (user_id, action, entity_type, entity_id, old_values, new_values, ip_address, user_agent)
                VALUES ($1::uuid, $2, $3, $4::uuid, $5::jsonb, $6::jsonb, $7, $8)
            """,
                safe_user_id,
                action,
                entity_type,
                safe_entity_id,
                json.dumps(old_values) if old_values else None,
                json.dumps(new_values) if new_values else None,
                ip_address,
                user_agent,
            )
        else:
            # SQLAlchemy ORM style
            from app.models.audit import AuditLog
            audit_entry = AuditLog(
                user_id=safe_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=safe_entity_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(audit_entry)
            await db.commit()
    except Exception as e:
        logger.error(f"Audit log error: {e}")
        # Never raise — audit failures should not break business logic


async def log_field_change(
    db,
    contact_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    changed_by: Optional[str] = None,
    source: str = "manual",
):
    """
    Log a field-level change for a contact.
    
    Args:
        db: Database connection
        contact_id: UUID of the contact
        field_name: Name of the changed field
        old_value: Previous value (will be stringified)
        new_value: New value (will be stringified)
        changed_by: UUID of the user making the change
        source: Source of change ('manual', 'import', 'sheets_sync', 'api')
    """
    try:
        # Safely convert UUIDs
        safe_contact_id = _safe_uuid_str(contact_id)
        safe_changed_by = _safe_uuid_str(changed_by)
        
        if hasattr(db, 'execute') and not hasattr(db, 'add'):
            await db.execute("""
                INSERT INTO contact_field_history (contact_id, field_name, old_value, new_value, changed_by, source)
                VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6)
            """,
                safe_contact_id,
                field_name,
                str(old_value) if old_value is not None else None,
                str(new_value) if new_value is not None else None,
                safe_changed_by,
                source,
            )
        else:
            from app.models.audit import ContactFieldHistory
            history_entry = ContactFieldHistory(
                contact_id=safe_contact_id,
                field_name=field_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                changed_by=safe_changed_by,
                source=source,
            )
            db.add(history_entry)
            await db.commit()
    except Exception as e:
        logger.error(f"Field history log error: {e}")
