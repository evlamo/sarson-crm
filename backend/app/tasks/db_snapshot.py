"""
Database snapshot task.
Phase 4 — Lightweight stats-based snapshots every 8 hours.
"""
import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.audit import DbSnapshot, AuditLog
from app.models.contact import Contact
from app.models.company import Company
from app.models.static_list import StaticList
from app.models.sales_campaign import SalesCampaign

logger = logging.getLogger(__name__)


async def take_db_snapshot():
    """
    Take a lightweight stats-based snapshot of the database.
    Records counts + recent audit activity.
    """
    db = SessionLocal()
    try:
        # Get entity counts
        contact_count = db.query(func.count(Contact.id)).filter(
            Contact.deleted_at.is_(None)
        ).scalar() or 0
        
        company_count = db.query(func.count(Company.id)).filter(
            Company.deleted_at.is_(None)
        ).scalar() or 0
        
        list_count = db.query(func.count(StaticList.id)).scalar() or 0
        
        campaign_count = db.query(func.count(SalesCampaign.id)).filter(
            SalesCampaign.status != 'archived'
        ).scalar() or 0
        
        # Count recent audit activity (last 8 hours)
        eight_hours_ago = datetime.now(timezone.utc) - timedelta(hours=8)
        recent_changes = db.query(func.count(AuditLog.id)).filter(
            AuditLog.created_at > eight_hours_ago
        ).scalar() or 0
        
        # Get summary of recent action types
        recent_actions = db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at > eight_hours_ago
        ).group_by(AuditLog.action).limit(20).all()
        
        action_summary = {action: count for action, count in recent_actions}
        
        # Build snapshot data
        snapshot_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "contacts": contact_count,
                "companies": company_count,
                "lists": list_count,
                "campaigns": campaign_count,
            },
            "recent_activity": {
                "total_changes": recent_changes,
                "action_breakdown": action_summary,
            },
        }
        
        # Save snapshot
        snapshot = DbSnapshot(
            label=f"Auto snapshot {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
            snapshot_type="auto",
            data=snapshot_data,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(snapshot)
        db.commit()
        
        logger.info(f"DB snapshot taken: {contact_count} contacts, {recent_changes} recent changes")
        return snapshot_data
        
    except Exception as e:
        logger.error(f"Failed to take DB snapshot: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def take_db_snapshot_sync():
    """Synchronous wrapper for the snapshot task."""
    import asyncio
    return asyncio.run(take_db_snapshot())


# For APScheduler integration
def schedule_snapshot_job(scheduler):
    """Register the snapshot job with APScheduler."""
    scheduler.add_job(
        take_db_snapshot_sync,
        'interval',
        hours=8,
        id='db_snapshot',
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    logger.info("Scheduled DB snapshot job (every 8 hours)")
