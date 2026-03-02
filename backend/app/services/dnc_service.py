"""
DNC (Do Not Contact) enforcement service.
Phase 1 Foundation — Central point for all exclusion logic.
"""
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


async def is_contact_excluded(
    db,
    contact_id: str,
    sales_campaign_id: Optional[str] = None,
    email_campaign_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Check if a contact should be excluded from outbound communication.
    
    Returns:
        (is_excluded: bool, reason: str)
    
    Exclusion Rules (in order of precedence):
    1. Master DNC → always excluded from ALL outbound
    2. Email unsubscribed → excluded from all emails
    3. Campaign completion (status='complete' or 'no') → excluded from THIS sales campaign only
    
    Note: A 'no' on Campaign A does NOT block Campaign B.
    Only master_dnc=TRUE blocks everything globally.
    """
    try:
        # ========== RESOLVE SALES CAMPAIGN FROM EMAIL CAMPAIGN IF NEEDED ==========
        # If we have an email_campaign_id but no sales_campaign_id, look up the parent
        resolved_sales_campaign_id = sales_campaign_id
        if email_campaign_id and not sales_campaign_id:
            if hasattr(db, 'fetchrow'):
                # asyncpg style
                ec_row = await db.fetchrow(
                    "SELECT sales_campaign_id FROM email_campaigns WHERE id = $1::uuid",
                    email_campaign_id
                )
                if ec_row and ec_row['sales_campaign_id']:
                    resolved_sales_campaign_id = str(ec_row['sales_campaign_id'])
            else:
                # SQLAlchemy style
                from sqlalchemy import select
                from app.models.campaign import EmailCampaign
                result = await db.execute(
                    select(EmailCampaign.sales_campaign_id)
                    .where(EmailCampaign.id == email_campaign_id)
                )
                ec_row = result.first()
                if ec_row and ec_row.sales_campaign_id:
                    resolved_sales_campaign_id = str(ec_row.sales_campaign_id)
        
        # ========== CHECK CONTACT STATUS ==========
        if hasattr(db, 'fetchrow'):
            # asyncpg style
            contact = await db.fetchrow(
                "SELECT master_dnc, master_dnc_reason, email_unsubscribed FROM contacts WHERE id = $1::uuid",
                contact_id
            )
        else:
            # SQLAlchemy style
            from sqlalchemy import select
            from app.models.contact import Contact
            result = await db.execute(
                select(Contact.master_dnc, Contact.master_dnc_reason, Contact.email_unsubscribed)
                .where(Contact.id == contact_id)
            )
            contact = result.first()
        
        if not contact:
            return False, ""
        
        # Rule 1: Master DNC (highest priority - blocks EVERYTHING)
        master_dnc = contact['master_dnc'] if hasattr(contact, '__getitem__') else contact.master_dnc
        if master_dnc:
            reason = contact['master_dnc_reason'] if hasattr(contact, '__getitem__') else contact.master_dnc_reason
            return True, f"Master DNC: {reason or 'Do not contact'}"
        
        # Rule 2: Email unsubscribed (for email campaigns only)
        if email_campaign_id:
            unsubscribed = contact['email_unsubscribed'] if hasattr(contact, '__getitem__') else contact.email_unsubscribed
            if unsubscribed:
                return True, "Email unsubscribed"
        
        # Rule 3: Check campaign-specific completion using RESOLVED sales_campaign_id
        # This ensures "No" on Campaign A only blocks emails under Campaign A
        if resolved_sales_campaign_id:
            if hasattr(db, 'fetchrow'):
                campaign_status = await db.fetchrow("""
                    SELECT completion_status FROM campaign_contacts
                    WHERE contact_id = $1::uuid AND sales_campaign_id = $2::uuid
                """, contact_id, resolved_sales_campaign_id)
            else:
                from sqlalchemy import select
                from app.models.sales_campaign import CampaignContact
                result = await db.execute(
                    select(CampaignContact.completion_status)
                    .where(CampaignContact.contact_id == contact_id)
                    .where(CampaignContact.sales_campaign_id == resolved_sales_campaign_id)
                )
                campaign_status = result.first()
            
            if campaign_status:
                status = campaign_status['completion_status'] if hasattr(campaign_status, '__getitem__') else campaign_status.completion_status
                if status in ('complete', 'no'):
                    return True, f"Campaign completed with status: {status}"
        
        return False, ""
    
    except Exception as e:
        logger.error(f"DNC check error: {e}")
        # On error, default to NOT excluded (fail open for business continuity)
        return False, ""


async def set_master_dnc(
    db,
    contact_id: str,
    reason: str,
    set_by: Optional[str] = None,
) -> bool:
    """
    Set master DNC status on a contact.
    
    Args:
        db: Database connection
        contact_id: UUID of the contact
        reason: Why they're being added to DNC
        set_by: UUID of the user setting the DNC status
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from datetime import datetime, timezone
        
        if hasattr(db, 'execute'):
            await db.execute("""
                UPDATE contacts 
                SET master_dnc = TRUE, 
                    master_dnc_reason = $2, 
                    master_dnc_set_at = $3, 
                    master_dnc_set_by = $4::uuid,
                    updated_at = $3
                WHERE id = $1::uuid
            """, contact_id, reason, datetime.now(timezone.utc), set_by)
        else:
            from sqlalchemy import update
            from app.models.contact import Contact
            await db.execute(
                update(Contact)
                .where(Contact.id == contact_id)
                .values(
                    master_dnc=True,
                    master_dnc_reason=reason,
                    master_dnc_set_at=datetime.now(timezone.utc),
                    master_dnc_set_by=set_by,
                )
            )
            await db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Set master DNC error: {e}")
        return False


async def clear_master_dnc(
    db,
    contact_id: str,
) -> bool:
    """
    Clear master DNC status from a contact.
    
    Args:
        db: Database connection
        contact_id: UUID of the contact
    
    Returns:
        True if successful, False otherwise
    """
    try:
        if hasattr(db, 'execute'):
            await db.execute("""
                UPDATE contacts 
                SET master_dnc = FALSE, 
                    master_dnc_reason = NULL, 
                    master_dnc_set_at = NULL, 
                    master_dnc_set_by = NULL,
                    updated_at = NOW()
                WHERE id = $1::uuid
            """, contact_id)
        else:
            from sqlalchemy import update
            from app.models.contact import Contact
            await db.execute(
                update(Contact)
                .where(Contact.id == contact_id)
                .values(
                    master_dnc=False,
                    master_dnc_reason=None,
                    master_dnc_set_at=None,
                    master_dnc_set_by=None,
                )
            )
            await db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Clear master DNC error: {e}")
        return False
