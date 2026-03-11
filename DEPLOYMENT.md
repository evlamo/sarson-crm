# Sarson CRM - Deployment Guide

## Fresh Database Setup

The repository does NOT include any database files or contact data. When deploying to a new server:

### 1. Database Creation

```bash
# Create PostgreSQL database
createdb crm_production

# Set connection string in .env
DATABASE_URL=postgresql://user:password@localhost/crm_production
```

### 2. Run Migrations

```bash
cd backend
python -m alembic upgrade head
```

This creates all tables with NO data.

### 3. Create Admin User

```bash
# Use the registration endpoint or create via script
# First user becomes admin
```

### 4. Import Contact Lists

- Use CSV import feature in the UI
- Import your 30k+ contacts
- Create lists and tags as needed

---

## Environment Variables Required

Copy `.env.example` to `.env` and configure:

- `DATABASE_URL` - PostgreSQL connection
- `SECRET_KEY` - JWT signing key (generate new for production)
- `ENCRYPTION_KEY` - Fernet key for sensitive data
- `SENDGRID_API_KEY` - Email sending
- `REDIS_URL` - Caching layer
- `FRONTEND_URL` - CORS configuration

---

## Services to Start

```bash
# Backend API
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Celery worker (background tasks)
celery -A app.celery_app worker --loglevel=info

# Frontend (production build)
cd frontend
npm run build
# Serve dist/ via Caddy or nginx
```

---

## Security Checklist

- [ ] Change `SECRET_KEY` and `ENCRYPTION_KEY` in production
- [ ] Enable HTTPS (Caddy handles this automatically)
- [ ] Configure firewall (allow 443, block 8000 externally)
- [ ] Set `ENFORCE_DOMAIN_RESTRICTION=true` if using email domain restrictions
- [ ] Configure backup schedule for PostgreSQL
- [ ] Review rate limiting settings in `app/main.py`

---

## Data Privacy

**Important:** No contact data, user data, or database files are stored in Git. Every deployment starts with a clean database.
