# Sarson CRM

A production-grade Customer Relationship Management system built for Sarson Funds, designed to replace Zoho + Mailchimp for managing ~30,000 contacts and running email campaigns.

## Features

### Contact Management
- ✅ Create, edit, delete contacts
- ✅ CSV import with chunked processing (1000 rows/batch)
- ✅ Advanced search with debounced input
- ✅ Tag-based organization
- ✅ Static lists for segmentation
- ✅ Company associations
- ✅ Bulk operations (update, delete, add to list)
- ✅ Do Not Contact (DNC) list enforcement

### Campaign Management
- ✅ Email campaign creation wizard (5 steps)
- ✅ Sales vs Marketing campaign types
- ✅ Rich text email editor
- ✅ Variable interpolation (`{{first_name}}`, `{{company}}`)
- ✅ Contact selection with search/filter
- ✅ Automatic DNC and duplicate exclusion
- ✅ UTM tracking parameters
- ✅ Campaign scheduling

### User Management
- ✅ Role-based access control (Admin/User)
- ✅ JWT authentication with token blacklisting
- ✅ Multi-factor authentication (TOTP)
- ✅ Password reset flow
- ✅ User invitations
- ✅ Encrypted service account storage

### Security
- ✅ Token blacklist on logout
- ✅ Rate limiting (5/min auth, 100/hr contacts)
- ✅ CSRF protection
- ✅ Fernet encryption for sensitive data
- ✅ Audit trail for all operations
- ✅ Security headers (X-Content-Type-Options, X-Frame-Options, etc.)

### Integrations
- ✅ SendGrid email delivery
- ✅ Google Sheets sync
- ✅ Google OAuth

## Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Database:** PostgreSQL 16
- **Cache:** Redis
- **Queue:** Celery
- **Email:** SendGrid
- **Auth:** JWT + MFA (TOTP)

### Frontend
- **Framework:** React 18 + TypeScript
- **UI:** shadcn/ui + Tailwind CSS
- **Router:** TanStack Router
- **State:** TanStack Query (React Query)
- **HTTP:** Axios

### Infrastructure
- **Reverse Proxy:** Caddy (auto-HTTPS)
- **Deployment:** systemd services
- **Backups:** Automated PostgreSQL dumps

## Quick Start

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete production deployment instructions.

### Development Setup

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure database and keys
python -m alembic upgrade head  # Run migrations
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Documentation

- **[USER_GUIDE.md](USER_GUIDE.md)** - End-user documentation for CMO
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Fresh database setup for production
- **[PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)** - Complete deployment checklist

## Scripts

- **`backup-sarson-crm.sh`** - Automated daily database backup (30-day retention)
- **`restore-sarson-crm.sh`** - Safe database restore with confirmation

## Database Migrations

```bash
cd backend
source venv/bin/activate

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Architecture

```
Frontend (React SPA)
    ↓ HTTPS
Caddy (Reverse Proxy)
    ↓
FastAPI Backend (Port 8000)
    ↓
PostgreSQL (Database)
    ↓
Redis (Cache & Sessions)
    ↓
Celery (Background Tasks)
    ↓
SendGrid (Email Delivery)
```

## Key Decisions

- **All API responses:** `{data: {...}}` format (no exceptions)
- **Chunked CSV import:** 1000 rows per batch for stability
- **Password requirements:** 6+ characters (internal CRM, usability priority)
- **Email verification:** Disabled (internal users, immediate access)
- **Collaborative lists:** All users share lists (no per-user authorization)
- **DNC enforcement:** Automatic exclusion at campaign level

## Security Notes

- Never commit `.env` files (excluded in `.gitignore`)
- Database files excluded from Git (deploy with blank database)
- Generate new `SECRET_KEY` and `ENCRYPTION_KEY` for production
- Use HTTPS in production (Caddy handles this automatically)
- Enable firewall (allow 443/80, block 8000 externally)

## Data Privacy

**Important:** This repository does NOT contain any contact data, user data, or database files. Every deployment starts with a clean database. Contact lists must be imported via CSV after deployment.

## Production Deployment

Checklist:
- [ ] Generate new SECRET_KEY and ENCRYPTION_KEY
- [ ] Configure `.env` with production values
- [ ] Run database migrations
- [ ] Build frontend (`npm run build`)
- [ ] Configure Caddy reverse proxy
- [ ] Set up systemd services (backend + Celery)
- [ ] Schedule daily backups (cron)
- [ ] Test backup/restore procedure
- [ ] Enable firewall
- [ ] Create first admin user

See **[PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)** for complete step-by-step instructions.

## Support

For issues or questions:
- Check **[USER_GUIDE.md](USER_GUIDE.md)** for common problems
- Review logs: `sudo journalctl -u sarson-backend -n 100`
- Email: support@sarsonfunds.com

## License

Proprietary - Sarson Funds Internal Use Only

---

**Version:** 1.0  
**Last Updated:** March 2026  
**Repository:** github.com/evlamo/sarson-crm
