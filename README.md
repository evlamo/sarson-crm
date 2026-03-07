# Sarson Funds CRM

A production-grade CRM built to replace Zoho + Mailchimp for Sarson Funds. Designed for ~30,000 contacts and 5 internal users.

**Stack:** FastAPI · PostgreSQL 16 · React · shadcn/ui · Celery · Redis · Docker

---

## Features

- **Contacts** — Full contact management with search, sorting, filtering, inline editing
- **Companies** — Company records linked to contacts
- **Pipeline** — 8-stage Kanban deal pipeline
- **Campaigns** — Email campaign builder with SendGrid batch sending (1,000/call)
- **CSV Import** — Bulk import with deduplication, tag mapping, and async processing
- **Segments** — Dynamic segments (filter-rule based) and static lists
- **Tags** — Flexible tagging system across contacts
- **Auth** — JWT-based auth with refresh tokens, role-based access

---

## Quick Start (Docker)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git installed

### 1. Clone the repo

```bash
git clone https://github.com/evlamo/sarson-crm.git
cd sarson-crm
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and update:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Random 64-character string — change this before use |
| `SENDGRID_API_KEY` | Your SendGrid API key (optional — only needed for email campaigns) |
| `FROM_EMAIL` | Verified sender email address in SendGrid |
| `POSTGRES_PASSWORD` | Database password — change from default |

Everything else works out of the box for local development.

### 3. Start the stack

```bash
docker-compose up --build
```

This spins up 6 services: API, frontend, PostgreSQL, Redis, Celery worker, and Nginx. First run takes a few minutes to build images.

### 4. Open the app

- **CRM:** http://localhost:3000
- **API docs:** http://localhost:8000/docs

### Default login

| Field | Value |
|---|---|
| Email | `ev@speranza.local` |
| Password | `speranza2026` |

> ⚠️ Change the default password after first login.

---

## Running Without Docker (Development)

If you prefer to run services individually:

### Backend

```bash
cd backend

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create a .env in /backend)
export DATABASE_URL=postgresql://agentstevesmith@localhost:5432/crm_dev
export SECRET_KEY=your-secret-key
export REDIS_URL=redis://localhost:6379/0

# Run migrations
alembic upgrade head

# Seed the database
python scripts/seed.py

# Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open http://localhost:3000. The Vite dev server proxies `/api` → `localhost:8000` automatically.

### Celery Worker (for CSV imports + email campaigns)

```bash
cd backend
celery -A app.worker worker --loglevel=info
```

---

## Project Structure

```
sarson-crm/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── routers/        # API route handlers
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic (campaigns, imports, segments)
│   │   ├── auth/           # JWT auth, dependencies
│   │   └── tasks/          # Celery async tasks
│   ├── migrations/         # Alembic DB migrations
│   └── scripts/            # Seed script
├── frontend/
│   └── src/
│       ├── pages/          # Route-level components
│       ├── components/     # Shared UI components (shadcn/ui)
│       ├── hooks/          # Auth hook
│       └── lib/            # API client, types, utils
├── docker-compose.yml
├── nginx.conf
└── .env.example
```

---

## Database Schema

15 tables covering the full CRM data model:

| Table | Description |
|---|---|
| `users` | Internal CRM users (up to 5) |
| `contacts` | Primary contact records (~30k expected) |
| `companies` | Company records |
| `tags` | Tag definitions |
| `contact_tags` | Contact ↔ tag join |
| `deals` | Pipeline deals |
| `campaigns` | Email campaigns |
| `campaign_contacts` | Campaign send tracking |
| `templates` | Email templates with merge fields |
| `segments` | Dynamic filter-rule segments |
| `static_lists` | Manually curated contact lists |
| `static_list_contacts` | List ↔ contact join |
| `import_jobs` | CSV import job tracking |
| `activity_log` | Contact activity history |
| `custom_fields` | Extensible contact fields |

Full-text search is powered by a PostgreSQL `tsvector` + GIN index on contacts for sub-200ms search across 30k records.

---

## CSV Import

The import wizard supports bulk contact uploads:

- Upload via **Contacts → Import** in the UI, or `POST /api/v1/imports/upload`
- Processes in async batches of 500 rows (won't timeout on large files)
- Deduplicates by email address
- Maps `Sheet` and `Tab` columns from CSV → contact tags automatically
- Resolves company names to company records

---

## Email Campaigns

Campaigns use SendGrid's v3 personalizations API — batches of 1,000 recipients per API call.

To enable:
1. Add your `SENDGRID_API_KEY` to `.env`
2. Add a verified `FROM_EMAIL` (must be verified in your SendGrid account)
3. Configure a webhook endpoint in SendGrid → point to `POST /api/v1/webhooks/sendgrid` for open/click tracking

---

## API Reference

Interactive API docs available at http://localhost:8000/docs (Swagger UI) when the backend is running.

Key endpoints:

```
POST   /api/v1/auth/login
GET    /api/v1/contacts
POST   /api/v1/contacts
PATCH  /api/v1/contacts/{id}
DELETE /api/v1/contacts/{id}
POST   /api/v1/imports/upload
GET    /api/v1/campaigns
POST   /api/v1/campaigns/{id}/send
GET    /api/v1/segments
GET    /api/v1/tags
```

---

## Notes

- **Soft deletes** — contacts are never hard-deleted; `deleted_at` timestamp is set instead
- **Server-side sorting + pagination** — all data operations are server-side, critical for performance at 30k+ contacts
- **Sarson rep vs Sales rep** — `sarson_rep` stores the SF team member from CSV import; `sales_rep` is an external sales partner field
- SendGrid is optional — the app runs fully without it, email sending will just fail gracefully

---

## License

Private — Sarson Funds internal use only.
