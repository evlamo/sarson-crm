# Sarson CRM - Production Deployment Checklist

## Pre-Deployment

### Repository & Code
- [ ] Latest code pulled from `main` branch
- [ ] All tests passing
- [ ] No debug code or console.logs in production
- [ ] `.gitignore` properly excludes database files and logs

### Environment Setup
- [ ] Server provisioned (Ubuntu 20.04+ recommended)
- [ ] Domain name configured (DNS pointing to server)
- [ ] SSL certificate ready (Caddy handles this automatically)
- [ ] Firewall configured (allow 443, 80; block 8000)

---

## Database Setup

### PostgreSQL Installation
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Create Production Database
```bash
sudo -u postgres psql

CREATE DATABASE crm_production;
CREATE USER crm_user WITH PASSWORD 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE crm_production TO crm_user;
\q
```

- [ ] Database created
- [ ] User created with strong password
- [ ] Privileges granted

---

## Backend Setup

### Install Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] Python 3.10+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed

### Environment Variables

Create `backend/.env`:

```env
# Database
DATABASE_URL=postgresql://crm_user:PASSWORD@localhost/crm_production

# Security (GENERATE NEW KEYS FOR PRODUCTION)
SECRET_KEY=GENERATE_WITH_openssl_rand_hex_32
ENCRYPTION_KEY=GENERATE_WITH_python_fernet_key

# Email
SENDGRID_API_KEY=your_sendgrid_api_key_here

# Redis
REDIS_URL=redis://localhost:6379/0

# App Config
ENVIRONMENT=production
DEBUG=False
FRONTEND_URL=https://yourdomain.com
MAX_USERS=10
ENFORCE_DOMAIN_RESTRICTION=True

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Token Expiration
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

**Generate ENCRYPTION_KEY (Fernet):**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

- [ ] `.env` file created
- [ ] All keys generated (never reuse dev keys)
- [ ] Database URL correct
- [ ] Frontend URL matches your domain
- [ ] Debug mode OFF

### Run Database Migrations
```bash
cd backend
source venv/bin/activate
python -m alembic upgrade head
```

- [ ] All migrations applied successfully
- [ ] Tables created
- [ ] No errors

---

## Redis Setup

```bash
sudo apt install redis-server -y
sudo systemctl start redis
sudo systemctl enable redis
```

- [ ] Redis installed
- [ ] Redis running
- [ ] Redis auto-starts on boot

---

## Frontend Setup

### Install Dependencies
```bash
cd frontend
npm install
```

### Environment Variables

Create `frontend/.env.production`:

```env
VITE_API_BASE_URL=https://yourdomain.com/api/v1
```

### Build Frontend
```bash
npm run build
```

This creates `frontend/dist/` with optimized production files.

- [ ] Dependencies installed
- [ ] Build completed successfully
- [ ] `dist/` folder created
- [ ] No TypeScript errors

---

## Reverse Proxy (Caddy)

### Install Caddy
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Configure Caddy

Create `/etc/caddy/Caddyfile`:

```
yourdomain.com {
    # Frontend (React SPA)
    root * /path/to/sarson-crm/frontend/dist
    try_files {path} /index.html
    file_server

    # Backend API
    handle /api/* {
        reverse_proxy localhost:8000
    }

    # Security headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

```bash
sudo systemctl reload caddy
```

- [ ] Caddy installed
- [ ] Caddyfile configured
- [ ] SSL certificate auto-generated
- [ ] HTTPS working

---

## Systemd Services

### Backend API Service

Create `/etc/systemd/system/sarson-backend.service`:

```ini
[Unit]
Description=Sarson CRM Backend API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/sarson-crm/backend
Environment="PATH=/path/to/sarson-crm/backend/venv/bin"
ExecStart=/path/to/sarson-crm/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Celery Worker Service

Create `/etc/systemd/system/sarson-celery.service`:

```ini
[Unit]
Description=Sarson CRM Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/sarson-crm/backend
Environment="PATH=/path/to/sarson-crm/backend/venv/bin"
ExecStart=/path/to/sarson-crm/backend/venv/bin/celery -A app.celery_app worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable sarson-backend sarson-celery
sudo systemctl start sarson-backend sarson-celery
```

- [ ] Backend service created
- [ ] Celery service created
- [ ] Services enabled (auto-start on boot)
- [ ] Services running without errors

---

## Database Backups

### Create Backup Script

Create `/root/backup-sarson-crm.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/var/backups/sarson-crm"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="crm_production"
DB_USER="crm_user"

mkdir -p $BACKUP_DIR

# Backup database
PGPASSWORD='YOUR_DB_PASSWORD' pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_DIR/backup_$TIMESTAMP.sql.gz

# Keep only last 30 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$TIMESTAMP.sql.gz"
```

```bash
chmod +x /root/backup-sarson-crm.sh
```

### Schedule Daily Backups

```bash
sudo crontab -e
```

Add line:
```
0 2 * * * /root/backup-sarson-crm.sh >> /var/log/sarson-backup.log 2>&1
```

- [ ] Backup script created
- [ ] Script executable
- [ ] Cron job configured (runs daily at 2 AM)
- [ ] Test backup manually

### Test Restore

```bash
# Create test database
sudo -u postgres psql -c "CREATE DATABASE crm_test;"

# Restore backup
gunzip -c /var/backups/sarson-crm/backup_TIMESTAMP.sql.gz | sudo -u postgres psql crm_test

# Verify data
sudo -u postgres psql crm_test -c "SELECT COUNT(*) FROM contacts;"

# Drop test database
sudo -u postgres psql -c "DROP DATABASE crm_test;"
```

- [ ] Backup restore tested successfully

---

## First User Creation

### Option 1: Via Registration Page
- Go to https://yourdomain.com
- Click "Register"
- Enter email ending in @sarsonfunds.com or @speranza.local
- First user automatically becomes admin

### Option 2: Via Database (if needed)
```bash
cd backend
source venv/bin/activate
python3 -c "
from app.auth.security import hash_password
import uuid
print('Password hash:', hash_password('YOUR_PASSWORD_HERE'))
print('User ID:', uuid.uuid4())
"
```

Then insert into database:
```sql
INSERT INTO users (id, email, name, hashed_password, role, is_active)
VALUES (
  'UUID_FROM_ABOVE',
  'admin@sarsonfunds.com',
  'Admin User',
  'HASH_FROM_ABOVE',
  'admin',
  true
);
```

- [ ] Admin user created
- [ ] Can log in successfully

---

## Post-Deployment Testing

### Smoke Tests
- [ ] Homepage loads (HTTPS)
- [ ] Login works
- [ ] Logout works
- [ ] Create contact
- [ ] Edit contact
- [ ] Create campaign
- [ ] Create list
- [ ] CSV import (small test file)

### Service Health
```bash
# Check backend
curl https://yourdomain.com/api/v1/health

# Check services
sudo systemctl status sarson-backend
sudo systemctl status sarson-celery
sudo systemctl status redis
sudo systemctl status postgresql
```

- [ ] All services running
- [ ] API responding
- [ ] No errors in logs

---

## Monitoring & Logs

### Log Locations
- Backend: `/var/log/sarson-backend.log` (if configured)
- Celery: `/var/log/sarson-celery.log` (if configured)
- Caddy: `/var/log/caddy/`
- PostgreSQL: `/var/log/postgresql/`

### Check Logs
```bash
sudo journalctl -u sarson-backend -n 50 --no-pager
sudo journalctl -u sarson-celery -n 50 --no-pager
```

- [ ] Logs accessible
- [ ] No critical errors

---

## Security Hardening

### Firewall (ufw)
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP (redirects to HTTPS)
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

- [ ] Firewall enabled
- [ ] Only necessary ports open

### Fail2ban (Optional)
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
```

- [ ] Fail2ban installed (protects against brute force)

### SSH Hardening
- [ ] Disable root login
- [ ] Use SSH keys (disable password auth)
- [ ] Change default SSH port (optional)

---

## Final Checklist

### Security
- [ ] All default passwords changed
- [ ] SECRET_KEY and ENCRYPTION_KEY unique (not from dev)
- [ ] Debug mode OFF
- [ ] HTTPS working
- [ ] Firewall enabled

### Services
- [ ] Backend running
- [ ] Celery running
- [ ] Redis running
- [ ] PostgreSQL running
- [ ] All services auto-start on boot

### Backups
- [ ] Backup script working
- [ ] Cron job scheduled
- [ ] Restore tested

### Application
- [ ] Admin user created
- [ ] Login working
- [ ] All features tested
- [ ] No test data in production database

### Documentation
- [ ] CMO has user guide
- [ ] CMO has login credentials
- [ ] Support contact information shared

---

## Troubleshooting

### Backend Won't Start
```bash
# Check logs
sudo journalctl -u sarson-backend -n 100 --no-pager

# Common issues:
# - Wrong DATABASE_URL in .env
# - Migrations not run
# - Missing dependencies
```

### Can't Login
- Check if user exists in database
- Verify password hashed correctly
- Check backend logs for auth errors

### Emails Not Sending
- Verify SENDGRID_API_KEY in .env
- Check Celery worker is running
- Look at Celery logs for errors

---

## Rollback Plan

If deployment fails:

1. **Keep old version running** (don't stop services until new version confirmed working)
2. **Database rollback:**
   ```bash
   # Restore from backup
   gunzip -c /var/backups/sarson-crm/backup_TIMESTAMP.sql.gz | sudo -u postgres psql crm_production
   ```
3. **Code rollback:**
   ```bash
   git checkout PREVIOUS_COMMIT_HASH
   # Rebuild and restart services
   ```

---

**Ready for Production?** ✅

Once all checkboxes are marked, your Sarson CRM is production-ready!

**Support:** Keep this checklist for future reference and troubleshooting.
