#!/usr/bin/env python3
"""Seed the database with initial data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.models.tag import Tag
from app.models.segment import Segment
from app.models.deal import Pipeline
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed():
    db = SessionLocal()
    try:
        # Admin user
        existing = db.query(User).filter(User.email == "ev@speranza.local").first()
        if not existing:
            admin = User(
                id=uuid.uuid4(),
                email="ev@speranza.local",
                name="Ev",
                hashed_password=pwd_context.hash("speranza2026"),
                role="admin"
            )
            db.add(admin)
            print("✓ Admin user created: ev@speranza.local / speranza2026")
        else:
            print("✓ Admin user already exists")

        # Default tags
        default_tags = [
            ("LP Investor", "#56c254", "fund"),
            ("Fund III Interest", "#f5c518", "fund"),
            ("Fund I LP", "#3a86ff", "fund"),
            ("Warm Lead", "#e8630a", "status"),
            ("Do Not Contact", "#e63030", "status"),
            ("Newsletter", "#8b6ab5", "segment"),
            ("Annual LP Update", "#cc1f7a", "segment"),
            ("Accredited Investor", "#56c254", "status"),
            ("KYC Complete", "#3a86ff", "status"),
        ]
        for name, color, cat in default_tags:
            existing_tag = db.query(Tag).filter(Tag.name == name).first()
            if not existing_tag:
                db.add(Tag(name=name, color=color, category=cat))
        print("✓ Default tags created")

        # Default segments
        default_segments = [
            ("All Active Contacts", "All contacts with active status", {"status": ["active"]}),
            ("LP Investors", "All LP investor contacts", {"contact_type": ["lp_investor"]}),
            ("Unsubscribed", "Contacts who unsubscribed", {"email_unsubscribed": True}),
            ("Do Not Contact", "Contacts marked DNC", {"status": ["do_not_contact"]}),
            ("Newsletter List", "Tagged for newsletter", {"tags": ["Newsletter"]}),
        ]
        for name, desc, filters in default_segments:
            existing_seg = db.query(Segment).filter(Segment.name == name).first()
            if not existing_seg:
                db.add(Segment(name=name, description=desc, filters=filters, is_system=True))
        print("✓ Default segments created")

        # Default pipeline
        existing_pipeline = db.query(Pipeline).filter(Pipeline.is_default == True).first()
        if not existing_pipeline:
            db.add(Pipeline(
                name="Deal Pipeline",
                is_default=True,
                stages=[
                    {"name": "Sourced", "order": 1, "probability": 10, "color": "#5a5648"},
                    {"name": "Screening", "order": 2, "probability": 25, "color": "#3a86ff"},
                    {"name": "Diligence", "order": 3, "probability": 50, "color": "#f5c518"},
                    {"name": "Term Sheet", "order": 4, "probability": 75, "color": "#e8630a"},
                    {"name": "Closing", "order": 5, "probability": 90, "color": "#56c254"},
                    {"name": "Closed Won", "order": 6, "probability": 100, "color": "#56c254"},
                    {"name": "Closed Lost", "order": 7, "probability": 0, "color": "#e63030"},
                    {"name": "Passed", "order": 8, "probability": 0, "color": "#8b6ab5"},
                ]
            ))
        print("✓ Default pipeline created")

        db.commit()
        print("\n✓ Seed complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
