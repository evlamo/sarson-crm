#!/usr/bin/env python3
"""
Backfill: create Company records for all contacts that have a company name
but no company_id. Sets company_id on the contact after creation.
Run: python -m scripts.backfill_companies (from backend/)
"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.contact import Contact
from app.services.company_service import get_or_create_company


def backfill():
    db = SessionLocal()
    try:
        contacts = db.query(Contact).filter(
            Contact.deleted_at.is_(None),
            Contact.company.isnot(None),
            Contact.company != '',
        ).all()

        print(f"Found {len(contacts)} contacts with company names")
        updated = 0
        skipped = 0

        for contact in contacts:
            if contact.company_id:
                skipped += 1
                continue
            company = get_or_create_company(db, contact.company)
            if company:
                contact.company_id = company.id
                updated += 1

        db.commit()
        print(f"Updated: {updated}, Already linked: {skipped}")
    finally:
        db.close()


if __name__ == '__main__':
    backfill()
