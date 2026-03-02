"""
Audit logging service.
Phase 1 Foundation — Fire-and-forget audit trail for all actions.
Phase 4 — Enhanced with sync support + field history tracking.
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
    Log an action to the audit log (async version).
    Fire-and-forget safe — never raises exceptions.
    """
    try:
        safe_user_id = _safe_uuid_str(user_id)
        safe_entity_id = _safe_uuid_str(entity_id)
        
        if hasattr(db, 'execute') and not hasattr(db, 'add'):
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
            # Don't commit here — let the caller handle transaction
    except Exception as e:
        logger.error(f"Audit log error: {e}")


def log_action_sync(
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
    Log an action to the audit log (sync version for FastAPI/SQLAlchemy).
    Fire-and-forget safe — never raises exceptions.
    """
    try:
        from app.models.audit import AuditLog
        
        safe_user_id = _safe_uuid_str(user_id)
        safe_entity_id = _safe_uuid_str(entity_id)
        
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
        # Don't commit — transaction is managed by caller
    except Exception as e:
        logger.error(f"Audit log sync error: {e}")


async def log_field_change(
    db,
    contact_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    changed_by: Optional[str] = None,
    source: str = "manual",
):
    """Log a field-level change for a contact (async version)."""
    try:
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
    except Exception as e:
        logger.error(f"Field history log error: {e}")


def log_field_change_sync(
    db,
    contact_id: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    changed_by: Optional[str] = None,
    source: str = "manual",
):
    """Log a field-level change for a contact (sync version)."""
    try:
        from app.models.audit import ContactFieldHistory
        
        safe_contact_id = _safe_uuid_str(contact_id)
        safe_changed_by = _safe_uuid_str(changed_by)
        
        history_entry = ContactFieldHistory(
            contact_id=safe_contact_id,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            changed_by=safe_changed_by,
            source=source,
        )
        db.add(history_entry)
    except Exception as e:
        logger.error(f"Field history sync log error: {e}")


def log_entity_changes_sync(
    db,
    entity,
    changes: dict,
    action: str,
    entity_type: str,
    user_id: str,
):
    """
    Log both audit_log entry and field history (for contacts).
    Convenience function for update operations.
    
    Args:
        db: SQLAlchemy session
        entity: The entity being updated
        changes: Dict of {field: {"old": value, "new": value}}
        action: Action type (e.g., "contact.update")
        entity_type: Entity type (e.g., "contact")
        user_id: User performing the action
    """
    if not changes:
        return
    
    old_values = {k: v.get("old") for k, v in changes.items()}
    new_values = {k: v.get("new") for k, v in changes.items()}
    
    # Log to audit_log
    log_action_sync(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity.id),
        old_values=old_values,
        new_values=new_values,
        user_id=user_id,
    )
    
    # For contacts, also log field-level history
    if entity_type == "contact":
        for field_name, values in changes.items():
            log_field_change_sync(
                db=db,
                contact_id=str(entity.id),
                field_name=field_name,
                old_value=values.get("old"),
                new_value=values.get("new"),
                changed_by=user_id,
                source="manual",
            )
