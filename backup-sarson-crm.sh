#!/bin/bash
#
# Sarson CRM Database Backup Script
# Daily automated backup with 30-day retention
#

set -e  # Exit on any error

# Configuration
BACKUP_DIR="/var/backups/sarson-crm"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="crm_production"
DB_USER="crm_user"
DB_HOST="localhost"
RETENTION_DAYS=30

# Read password from environment or .pgpass file
# Option 1: Set DB_PASSWORD environment variable
# Option 2: Configure ~/.pgpass file (more secure)
# DB_PASSWORD="your_password_here"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Log start
echo "[$(date)] Starting backup of $DB_NAME..."

# Perform backup
BACKUP_FILE="$BACKUP_DIR/backup_${TIMESTAMP}.sql.gz"

if [ -n "$DB_PASSWORD" ]; then
    PGPASSWORD="$DB_PASSWORD" pg_dump -U "$DB_USER" -h "$DB_HOST" "$DB_NAME" | gzip > "$BACKUP_FILE"
else
    # Uses ~/.pgpass if password not in environment
    pg_dump -U "$DB_USER" -h "$DB_HOST" "$DB_NAME" | gzip > "$BACKUP_FILE"
fi

# Check if backup was successful
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date)] Backup completed successfully: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "[$(date)] ERROR: Backup failed!" >&2
    exit 1
fi

# Remove old backups (older than retention period)
echo "[$(date)] Removing backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# List recent backups
echo "[$(date)] Recent backups:"
ls -lh "$BACKUP_DIR" | tail -5

# Optional: Upload to S3/cloud storage
# aws s3 cp "$BACKUP_FILE" s3://your-bucket/sarson-crm-backups/

echo "[$(date)] Backup process completed."
