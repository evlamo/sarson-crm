# Sarson CRM — Quality Completion Plan
**Date:** 2026-03-04  
**Source:** Audit report + fix plan  
**Goal:** Ship everything to senior-level quality

---

## Phase A — Quick Fixes (no agent needed, ~20 min)
- [ ] `tags.py` — fix inconsistent response shapes (two different shapes from one endpoint)
- [ ] `BUILD_STATUS.md` — update to reflect phases 1-7 all complete + current state

## Phase B — Sheets Refactor (~full day)
Extract `sheets.py` (1,131 lines) into proper service/router split:
- `routers/sheets.py` — thin router, HTTP concerns only (auth, request parsing, response formatting)
- `services/sheets_service.py` — all business logic (`_get_setting`, `_set_setting`, `_get_credentials_json`, `_build_contact_dict`, conflict detection, export/import logic)
- Behavior must be identical after refactor — no feature changes
- All existing endpoints must pass same inputs/outputs

## Phase C — God Component Decomposition (~half day)
Break down 5 oversized frontend components:

| Component | Lines | Extract to |
|---|---|---|
| `CampaignsPage.tsx` | 1,350 | `CampaignList`, `CampaignDetail`, `CampaignContacts`, `CampaignEmails` |
| `ContactDetailPage.tsx` | 1,327 | `ContactInfo`, `ContactActivity`, `ContactHistory`, `ContactCampaigns` |
| `ContactsPage.tsx` | 1,244 | `ContactsTable`, `ContactsFilters`, `ContactsBulkActions` |
| `SheetsPage.tsx` | 1,177 | `SheetsConfig`, `SheetsExport`, `SheetsImport`, `ConflictResolver` |
| `ListsPage.tsx` | 1,002 | `ListsTable`, `ListDetail`, `ListContactsPanel` |

Rules:
- Each extracted component gets its own file in `frontend/src/components/`
- Props typed with proper interfaces
- No logic duplication — shared state stays in parent, passed down
- TypeScript must be clean after decomposition
