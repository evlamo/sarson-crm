# EMAIL-1: Campaigns API + SendGrid Batch Send

## Context
- CRM path: `/Users/agentstevesmith/.openclaw/workspace/crm/`
- Backend: `/Users/agentstevesmith/.openclaw/workspace/crm/backend/`
- DB: `crm_dev` on localhost:5432, user: `agentstevesmith`, no password
- Virtualenv: `backend/venv/` — activate with `source backend/venv/bin/activate`
- Config: `app/config.py` has `sendgrid_api_key`, `from_email`, `from_name`, `redis_url`
- Models exist: `EmailCampaign`, `EmailSend`, `EmailTemplate` in `app/models/campaign.py`
- Segment service: `app/services/segment_service.py` — use `evaluate_segment_filters()`
- Auth: `from app.auth.router import get_current_user`
- DB: `from app.database import get_db`

## Build

### 1. Campaigns Router (`app/routers/campaigns.py`)
All under `/api/v1/campaigns`, require auth:
- `GET /` — list with pagination, filter by status
- `POST /` — create draft
- `GET /{id}` — detail with stats
- `PATCH /{id}` — update (draft only)
- `DELETE /{id}` — delete (draft only)
- `POST /{id}/send` — trigger send (resolve segment, queue Celery task)
- `POST /{id}/schedule` — schedule future send
- `POST /{id}/cancel` — cancel scheduled
- `GET /{id}/stats` — analytics (rates calculated)
- `GET /{id}/recipients` — paginated email_sends
- `POST /{id}/duplicate` — clone as draft

### 2. Schemas (`app/schemas/campaign.py`)
CampaignCreate, CampaignUpdate, CampaignOut, CampaignStats, CampaignRecipient, EmailSendOut

### 3. Service (`app/services/campaign_service.py`)
- `resolve_recipients(campaign, db)` — get contacts from segment, filter out unsubscribed/bounced/invalid/do_not_contact/no-email
- `prepare_send(campaign_id, db)` — create EmailSend records, update recipient_count, set status='sending'
- `render_merge_fields(html, contact_data)` — replace {{first_name}}, {{last_name}}, {{full_name}}, {{company}}, {{email}}, {{unsubscribe_url}}

### 4. Celery Task (`app/tasks/send_campaign.py`)
- Create `app/tasks/__init__.py` with Celery config (broker=redis from settings)
- `send_campaign_task(campaign_id)`:
  1. Load campaign, call prepare_send()
  2. Batch recipients into groups of 1000
  3. Build SendGrid v3 personalizations payload per batch
  4. Include custom_args: campaign_id, contact_id
  5. Set List-Unsubscribe header
  6. Send via sendgrid package or httpx
  7. Update EmailSend.message_id from response
  8. Rate limit: max 3 calls/sec
  9. On complete: status='sent', sent_at=now
  10. On failure: status='failed', log error

### 5. Dependencies
```bash
cd /Users/agentstevesmith/.openclaw/workspace/crm/backend && source venv/bin/activate && pip install sendgrid celery[redis] httpx
```

### 6. Register in main.py
Add campaigns router import + include_router

### 7. Verify
- API starts clean: `uvicorn app.main:app --reload --port 8000`
- Test create + list campaigns via curl
- Celery worker starts: `celery -A app.tasks worker --loglevel=info`

### 8. Git Commit
```bash
cd /Users/agentstevesmith/.openclaw/workspace/crm && git add -A && git commit -m "EMAIL-1: Campaigns API + SendGrid batch send pipeline"
```

## Coding Standards — MANDATORY
Apply the Lead Systems Architect protocol:

**3-Iteration Loop:**
1. Iteration 1 — Draft & Structure: Write initial implementation
2. Iteration 2 — Standardization & Refinement: Review against platform docs + best practices
3. Iteration 3 — Optimization & Hardening: Performance, edge cases, security

**Integrity Check (after Iteration 3):**
1. Cross-reference: web_search for current industry standards
2. Gap analysis: Compare against popular open-source implementations
3. Security audit: OWASP checks, platform-specific flaws
4. If passes → FINAL_CERTIFIED_CODE. If fails → Emergency Correction.
