# Phase 1 Foundation Schema - Migration Report

**Date:** 2026-03-02  
**Migration:** `g001_phase1_foundation_schema.py`  
**Parent Revision:** `a82ce4d0d747`  
**Status:** ✅ COMPLETED SUCCESSFULLY

---

## Summary

Phase 1 Foundation schema migration completed. All database structures for campaigns, audit logging, DNC tracking, and RBAC are now in place.

---

## Tables Created

| Table | Row Count | Description |
|-------|-----------|-------------|
| `sales_campaigns` | 0 | High-level sales initiatives containing email campaigns |
| `campaign_contacts` | 0 | Junction table linking contacts to campaigns with per-campaign status |
| `audit_log` | 0 | Global audit trail for all user actions |
| `contact_field_history` | 0 | Field-level change tracking for contacts |
| `db_snapshots` | 0 | Registry of database snapshots for rollback |
| `sheets_exports` | 0 | Google Sheets export tracking |
| `sheets_import_reviews` | 0 | Pending sheet imports awaiting review |

---

## Columns Added

### contacts table
| Column | Type | Description |
|--------|------|-------------|
| `master_dnc` | BOOLEAN DEFAULT FALSE | Global do-not-contact flag |
| `master_dnc_reason` | TEXT | Reason for DNC status |
| `master_dnc_set_at` | TIMESTAMPTZ | When DNC was set |
| `master_dnc_set_by` | UUID FK → users | Who set the DNC status |

### users table
| Column | Type | Description |
|--------|------|-------------|
| `can_manage_users` | BOOLEAN DEFAULT FALSE | Create/edit/deactivate users |
| `can_manage_campaigns` | BOOLEAN DEFAULT FALSE | Create/edit/delete campaigns |
| `can_approve_imports` | BOOLEAN DEFAULT FALSE | Review and approve sheet imports |
| `can_revert_db` | BOOLEAN DEFAULT FALSE | Restore from snapshots |
| `can_manage_integrations` | BOOLEAN DEFAULT FALSE | Configure Mailchimp, Sheets, etc. |

### email_campaigns table
| Column | Type | Description |
|--------|------|-------------|
| `sales_campaign_id` | UUID FK → sales_campaigns | Parent sales campaign |

---

## Indexes Created

- `idx_sales_campaigns_status` - Filter campaigns by status
- `idx_sales_campaigns_owner` - Filter campaigns by owner
- `idx_email_campaigns_sales_campaign` - Join email campaigns to sales campaigns
- `idx_campaign_contacts_contact` - Lookup campaigns for a contact
- `idx_campaign_contacts_sales` - Lookup contacts in a sales campaign
- `idx_campaign_contacts_email` - Lookup contacts in an email campaign
- `idx_contacts_master_dnc` - Partial index for DNC contacts (WHERE master_dnc = TRUE)
- `idx_audit_log_entity` - Lookup audit entries by entity
- `idx_audit_log_user` - Lookup audit entries by user
- `idx_audit_log_created` - Time-ordered audit queries
- `idx_audit_log_action` - Filter by action type
- `idx_field_history_contact` - Lookup field history for a contact
- `idx_field_history_changed` - Time-ordered field history
- `idx_snapshots_created` - Time-ordered snapshot listing
- `idx_sheets_exports_spreadsheet` - Lookup exports by spreadsheet ID
- `idx_sheets_import_reviews_export` - Lookup reviews for an export
- `idx_sheets_import_reviews_status` - Filter pending reviews

---

## SQLAlchemy Models

### Created
- `backend/app/models/sales_campaign.py` - SalesCampaign, CampaignContact
- `backend/app/models/audit.py` - AuditLog, ContactFieldHistory, DbSnapshot
- `backend/app/models/sheets.py` - SheetsExport, SheetsImportReview

### Updated
- `backend/app/models/contact.py` - Added master_dnc fields + relationship
- `backend/app/models/user.py` - Added RBAC permission columns + helper methods
- `backend/app/models/campaign.py` - Added sales_campaign_id FK + relationship
- `backend/app/models/__init__.py` - Exported new models

---

## Services Created

- `backend/app/services/audit_service.py`
  - `log_action()` - Fire-and-forget audit logging
  - `log_field_change()` - Granular field-level change tracking

- `backend/app/services/dnc_service.py`
  - `is_contact_excluded()` - Check if contact is excluded from outbound
  - `set_master_dnc()` - Set master DNC status
  - `clear_master_dnc()` - Clear master DNC status

---

## RBAC Status

Verified admin user permissions were set correctly:

| User Role | can_manage_users | can_manage_campaigns | can_approve_imports | can_revert_db | can_manage_integrations |
|-----------|------------------|----------------------|---------------------|---------------|-------------------------|
| admin | ✅ TRUE | ✅ TRUE | ✅ TRUE | ✅ TRUE | ✅ TRUE |
| member | FALSE | FALSE | FALSE | FALSE | FALSE |

---

## Checklist

| Item | Status |
|------|--------|
| A. sales_campaigns table | ✅ Done |
| A. email_campaigns.sales_campaign_id | ✅ Done |
| A. campaign_contacts junction table | ✅ Done |
| B. contacts.master_dnc columns | ✅ Done |
| B. Partial index on master_dnc | ✅ Done |
| C. audit_log table | ✅ Done |
| C. audit_log indexes | ✅ Done |
| D. contact_field_history table | ✅ Done |
| E. db_snapshots table | ✅ Done |
| F. users RBAC columns | ✅ Done |
| F. Admin permissions UPDATE | ✅ Done |
| G. sheets_exports table | ✅ Done |
| G. sheets_import_reviews table | ✅ Done |
| SQLAlchemy models created | ✅ Done |
| audit_service.py | ✅ Done |
| dnc_service.py | ✅ Done |
| Migration runs clean | ✅ Done |

---

## File Locations

- **Migration:** `backend/migrations/versions/g001_phase1_foundation_schema.py`
- **Models:** `backend/app/models/{sales_campaign,audit,sheets}.py`
- **Services:** `backend/app/services/{audit_service,dnc_service}.py`

---

## Issues & Resolutions

1. **Multiple migration heads** - The migration initially pointed to `f684b64a21ae` but there was a merge point creating two heads. Fixed by updating `down_revision` to `a82ce4d0d747`.

---

## Next Steps (Phase 2+)

1. Build API endpoints for sales campaigns CRUD
2. Implement campaign contact management endpoints
3. Add audit logging to existing contact/campaign endpoints
4. Build sheets export/import review UI
5. Implement snapshot creation and restore functionality
