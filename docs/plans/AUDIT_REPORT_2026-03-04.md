## FINDINGS REPORT — Sarson CRM Audit 2026-03-04

### Summary
**Overall health: YELLOW**
2 high, 1 medium, 3 low findings. No critical issues. The system is functional and well-structured, but two security/UX issues need attention before production hardening.

---

### ✅ Working Correctly

- **Backend health**: `GET /health` → `{"status":"ok","service":"Speranza CRM API"}` ✅
- **All routers loaded**: 100+ endpoints across all phases confirmed in OpenAPI spec ✅
- **Auth enforcement**: All sensitive endpoints correctly gated with `get_current_user` or `get_admin_user` ✅
- **DNC enforcement in sales campaigns**: `_is_contact_dnc()` checks `master_dnc` before adding contacts to campaigns; skipped contacts reported in response ✅
- **Campaign list OR logic** (`campaign_list_service.py`): Uses `sa_or_(*[Contact.tags.any(...)])` — correct OR logic ✅
- **Email eligible-contacts**: Properly filters `master_dnc`, `email_unsubscribed`, `completion_status` in ['complete','no'], and `excluded_reason='dnc'` — all within the same sales campaign (Fresh Slate Rule respected) ✅
- **Version history endpoints**: `/api/v1/audit/contacts/{id}`, `/field-history`, `/revert-field` all present and wired ✅
- **Revert endpoint** (`POST /api/v1/audit/contacts/{id}/revert-field`): Admin-only via `get_admin_user`, field allowlist validated, input sanitized ✅
- **DB snapshot task**: APScheduler configured at startup, `schedule_snapshot_job()` registered at 8h interval ✅
- **Google Sheets router**: 8 endpoints present (config GET+POST, test, export, exports list, imports list, import/preview, import/apply) ✅
- **TypeScript**: `npx tsc --noEmit` exits clean — zero type errors ✅
- **Layout.tsx HelpWidget**: Imported and rendered (`<HelpWidget isOpen={isHelpOpen} onOpenChange={setIsHelpOpen} />`) ✅
- **Admin nav hidden from non-admins**: `{isAdmin && (...adminItems)}` conditional in Layout.tsx ✅
- **ContactActivityPanel History tab**: Full Activity + Field History tabs with Revert button wired correctly ✅
- **CampaignStatsPage.tsx**: Exists ✅
- **SheetsPage.tsx with conflict resolution**: `conflictDecisions` state, per-field CRM vs Sheet decision UI ✅
- **Google OAuth login button**: Conditionally shown on LoginPage based on `/auth/google/status`, redirects to `/api/v1/auth/google/login` ✅
- **Google OAuth domain restriction**: Implemented and checks `allowed_domains` from DB config ✅
- **Google OAuth callback**: Validates domain, falls back to invite-based access for non-domain users ✅
- **User management endpoints**: `list_users`, `create_user`, `deactivate_user`, `reset_password`, `update_role` all gated with `get_admin_user` ✅
- **Invite endpoints**: Admin-only create/delete, public `validate_invite` endpoint ✅
- **Audit trail logging**: Present across contacts, campaigns, email campaigns, sheets operations ✅
- **Fresh Slate Rule**: `eligible-contacts` filters only within the parent sales campaign — contacts aren't blocked by membership in other campaigns ✅
- **Register endpoint**: Respects `enforce_domain_restriction` — blocks non-domain registrations without valid invite token ✅

---

### Findings

#### [HIGH] isAdmin hardcoded as `true` in ContactDetailPage.tsx

- **File**: `frontend/src/pages/ContactDetailPage.tsx:1264`
- **Issue**: `<ContactActivityPanel contactId={contactId!} isAdmin={true} />` — the `isAdmin` prop is hardcoded to `true` instead of reading from the auth store. This means ALL logged-in users see the "Revert" button on every field history entry, regardless of their actual role. Non-admins clicking Revert will get a 403 from the server (the API is correctly protected), creating a confusing broken UX.
- **Fix**: 
  ```tsx
  // At top of ContactDetailPage component:
  const isAdmin = useAuth((s) => s.isAdmin);
  // Then use:
  <ContactActivityPanel contactId={contactId!} isAdmin={isAdmin} />
  ```

---

#### [HIGH] `enforce_domain_restriction` defaults to `false` — open registration in "production"

- **File**: `backend/app/config.py:28` and `backend/.env.example`
- **Issue**: `enforce_domain_restriction: bool = False` is the default. No `.env` file is deployed to the backend (confirmed — `.env` not found, only `.env.example`). This means **anyone with any email address can self-register** via `/api/v1/auth/register`. Google OAuth domain restriction is also driven by a DB credential setting, not the config flag — but the register endpoint relies entirely on `settings.enforce_domain_restriction`. In a multi-user SaaS CRM with 47k contacts, this is a significant exposure if the service is ever publicly accessible.
- **Fix**: Create a production `.env` with `ENFORCE_DOMAIN_RESTRICTION=true`. Also consider defaulting to `True` in config.py for safety and requiring explicit opt-out in dev.

---

#### [MEDIUM] `apscheduler` missing from `requirements.txt`

- **File**: `backend/requirements.txt`
- **Issue**: APScheduler 3.11.2 is installed in the venv (`~/.openclaw/workspace/crm/backend/venv/`) but is **not listed in requirements.txt**. On a fresh deployment, `pip install -r requirements.txt` would not install APScheduler, causing the DB snapshot job to silently fail at startup with the log message "APScheduler not installed - snapshot job disabled". The snapshots would never run and no error would be raised.
- **Fix**: Add `apscheduler>=3.10.0` to `requirements.txt`.

---

#### [LOW] Bare `console.error` in ChangelogPage.tsx

- **File**: `frontend/src/pages/ChangelogPage.tsx:47`
- **Issue**: `console.error(err)` called directly — in production this leaks error detail to browser console with no user-friendly fallback display.
- **Fix**: Add a toast or error state display alongside the console.error, or use a structured logger.

---

#### [LOW] TODO comment in google_ads.py — Zoho parity gap untracked

- **File**: `backend/app/routers/google_ads.py:268`
- **Issue**: `# TODO: Zoho parity gap — optionally auto-create contact here for Google Ads leads` — untracked tech debt. Google Ads leads that don't match existing contacts are silently dropped rather than auto-created.
- **Fix**: Create a GitHub issue or project task to track this. Decide: auto-create contacts from Google Ads captures, or surface "unmatched lead" in the UI.

---

#### [LOW] `enforce_domain_restriction=false` in `.env.example`

- **File**: `backend/.env.example`
- **Issue**: The example config has `ENFORCE_DOMAIN_RESTRICTION=false` with no strong warning that production must set this to `true`. Dev environment is fine, but this increases risk of a deployment missing the setting.
- **Fix**: Add a prominent comment: `# ⚠️ MUST be true in production! Restricts registration to @sarsonfunds.com or admin invite only.`

---

### Verification Results for Known Issues

| Known Issue | Status |
|---|---|
| Lists OR logic (`sa_or_` in campaign_list_service.py) | ✅ FIXED — uses `sa_or_` correctly |
| Fresh Slate Rule in eligible-contacts | ✅ CORRECT — filters within parent campaign only |
| TypeScript errors in ContactDetailPage.tsx / ContactsPage.tsx | ✅ RESOLVED — `tsc --noEmit` exits clean |
| DNC on contact detail page | ✅ Present — DNC set/clear modals with mutation + audit log |
| Campaign membership view | ✅ Present — `/contacts/{id}/campaigns` endpoint + UI |

---

### Architecture Notes (No Action Required)

- The `eligible-contacts` route at `/email-campaigns/eligible-contacts` is declared after `/{campaign_id}/eligible-contacts` in the router. FastAPI correctly handles this via UUID type validation on `{campaign_id}` — "eligible-contacts" is not a valid UUID so it falls through to the static route. Both appear in OpenAPI spec. No bug, but minor ordering note.
- APScheduler `next_run_time` is set to `now() + 5 minutes` on startup, which means the first snapshot runs 5 minutes after backend start, then every 8 hours. This is intentional and correct.
- `isAdmin` in `ContactActivityPanel` has a default of `false` — the component itself is correctly built. The bug is only in the caller (ContactDetailPage).
