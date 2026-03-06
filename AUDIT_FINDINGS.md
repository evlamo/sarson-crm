# Campaign Contact Removal Feature - Security Audit Report

**Date:** 2026-03-06  
**Auditor:** code-auditor  
**Status:** ✅ REVIEWED WITH ISSUES IDENTIFIED

## Overview
Full audit of Sales Campaign Contact Removal feature (frontend + backend). Feature enables users to remove contacts from campaigns with reason tracking and campaign history viewing.

---

## Backend Audit (campaign_contact_removal.py)

### ✅ STRENGTHS
- **Auth protection:** All endpoints require `@get_current_user` decorator
- **Input validation:** Reason field validated (5-500 chars via Pydantic)
- **Campaign ownership check:** POST /remove-contact verifies `campaign.owner_id == current_user.id`
- **Sanitization:** Reason field stripped and length-checked before storage
- **Parameterized queries:** SQLAlchemy ORM prevents SQL injection
- **Audit logging:** All mutations logged via `audit_service.log_action()`
- **Error handling:** Generic error messages don't leak internals

### ⚠️ CRITICAL ISSUES FOUND

#### Issue #1: Missing Authorization on GET /campaign-history
**Severity:** HIGH  
**Location:** `campaign_contact_removal.py:176-230` (GET /contacts/{contact_id}/campaign-history)  

**Problem:**
```python
contact = db.query(Contact).filter_by(id=contact_id).first()
if not contact:
    raise HTTPException(status_code=404, detail="Contact not found")
# NO AUTHORIZATION CHECK - endpoint allows ANY authenticated user to view removal history
```

Any authenticated user can view removal history for ANY contact in the system. This exposes sensitive business information (removal reasons, campaign strategies, etc.).

**Impact:**
- Data privacy breach: Employees can spy on competitor contacts
- Business intelligence exposure: Removal patterns reveal sales strategies
- Compliance risk: May violate data access policies (GDPR, CCPA)

**Fix (REQUIRED):**
```python
# Add authorization check after contact validation
contact = db.query(Contact).filter_by(id=contact_id).first()
if not contact:
    raise HTTPException(status_code=404, detail="Contact not found")

# ✅ NEW: Verify user owns contact or is admin
is_admin = current_user.role == "admin"
is_owner = contact.company_id == current_user.company_id  # Adjust based on actual business logic
if not is_admin and not is_owner:
    raise HTTPException(status_code=403, detail="Not authorized to view this contact's history")
```

---

#### Issue #2: No Rate Limiting
**Severity:** MEDIUM  
**Location:** Both endpoints (POST /remove-contact, GET /campaign-history)

**Problem:**
No rate limiting middleware (slowapi) configured on these endpoints. Attackers can:
- Brute-force removal of all contacts from all campaigns
- DoS attack by querying campaign history repeatedly
- Spam the audit log

**Impact:**
- API abuse: Malicious user can remove 10,000+ contacts in minutes
- Database load: Uncontrolled query volume on GET /campaign-history
- Audit trail pollution: Legitimate audit logs obscured by spam

**Fix (RECOMMENDED):**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/{campaign_id}/remove-contact")
@limiter.limit("10/minute")  # 10 removals per minute per user
def remove_contact_from_campaign(...):
    # endpoint code

@router.get("/contacts/{contact_id}/campaign-history")
@limiter.limit("30/minute")  # 30 queries per minute per user
def get_contact_campaign_removal_history(...):
    # endpoint code
```

Add to main.py:
```python
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

### ✅ INPUT VALIDATION: GOOD
- ✅ Reason field: 5-500 character limit enforced by Pydantic
- ✅ UUID validation: campaign_id, contact_id validated by FastAPI
- ✅ Pagination: limit/offset validated (ge=1, le=1000)
- ✅ No injection risks: Parameterized queries via SQLAlchemy

---

## Frontend Audit

### RemoveContactModal.tsx

**✅ STRENGTHS:**
- **XSS prevention:** React escapes JSX by default, no dangerously set innerHTML
- **Input validation:** Min 5 / max 500 character enforcement with visual feedback
- **Error handling:** Catches API errors, displays user-friendly messages via toast
- **Accessibility:** Proper labels, dialog semantics, ARIA attributes via shadcn
- **DNC warning:** Visual alert when contact is marked DNC

**⚠️ OBSERVATIONS:**
- **No CSRF tokens:** API calls should include CSRF token in headers (if using cookies)
  - **Current state:** Using Bearer token (JWT), so CSRF is not applicable ✅
  - **Risk:** If auth method changes to session cookies, add CSRF protection

---

### CampaignRemovalHistory.tsx

**✅ STRENGTHS:**
- **Query-based fetching:** Uses react-query for caching + pagination
- **Error states:** Displays error message if API fails
- **Loading states:** Shows spinner while fetching
- **Accessibility:** Proper table semantics, readable text

**⚠️ ISSUE: No Data Verification**
- Component doesn't verify user has permission to view removal history
- Relies entirely on backend authorization (which is currently BROKEN - see Issue #1)

---

## Database Audit (Migration j001)

### ✅ SCHEMA DESIGN
```sql
CREATE TABLE campaign_contact_removal (
  id UUID PRIMARY KEY,
  campaign_id UUID NOT NULL FK → sales_campaigns,
  contact_id UUID NOT NULL FK → contacts,
  reason VARCHAR(500) NOT NULL,
  removed_by_id UUID FK → users,
  removed_at TIMESTAMP,
  UNIQUE(campaign_id, contact_id)
)
```

**Strengths:**
- ✅ Composite unique constraint prevents duplicate removals
- ✅ Proper indexes on campaign_id, contact_id, removed_at
- ✅ Cascade deletes maintain referential integrity
- ✅ Timestamps track removal timeline

---

## Summary

### Blocking Issues (Must Fix Before Production)
1. **Missing authorization check** on GET /campaign-history (Issue #1) — HIGH severity
   - Any authenticated user can view any contact's removal history
   - Fix: Add company/ownership verification before returning data

### Important Issues (Should Fix)
2. **No rate limiting** on both endpoints (Issue #2) — MEDIUM severity
   - DoS risk, API abuse vulnerability
   - Fix: Add slowapi limiter with 10-30 requests/minute per user

### Recommendation
- **Do not merge to main** until Issue #1 is fixed
- Deploy rate limiting (Issue #2) in next sprint if not blocking

---

## Files Changed
- `/backend/migrations/versions/j001_campaign_contact_removal.py` — NEW
- `/backend/app/models/campaign_removal.py` — NEW
- `/backend/app/routers/campaign_contact_removal.py` — NEW (with security notes)
- `/frontend/src/components/RemoveContactModal.tsx` — NEW
- `/frontend/src/components/CampaignRemovalHistory.tsx` — NEW
- Integration required: SalesCampaignsPage.tsx (add RemoveContactModal state/handlers)

---

## Recommendations for Future Phases

1. **Implement rate limiting** via slowapi middleware (global config)
2. **Add audit logging** for failed authorization attempts
3. **Add frontend error boundary** around campaign history component
4. **Implement soft-delete recovery** (restore endpoint exists but not UI for it yet)
5. **Add bulk removal** with reason batch operation
6. **Track removal trends** (analytics: most common removal reasons per campaign)

---

**Audit Status:** 🔴 **BLOCKED** - Issue #1 must be fixed before merge  
**Next Step:** Fix authorization check, re-audit, then create feature branch for commit
