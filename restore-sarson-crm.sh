#!/bin/bash
#
# Sarson CRM Database Restore Script
# Restore from backup with safety checks
#

set -e  # Exit on any error

# Configuration
BACKUP_DIR="/var/backups/sarson-crm"
DB_NAME="crm_production"
DB_USER="crm_user"
DB_HOST="localhost"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backup file provided
if [ $# -eq 0 ]; then
    echo -e "${RED}ERROR: No backup file specified${NC}"
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    # Try looking in backup directory
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    else
        echo -e "${RED}ERROR: Backup file not found: $BACKUP_FILE${NC}"
        exit 1
    fi
fi

# Confirm restore
echo -e "${YELLOW}WARNING: This will OVERWRITE all data in database '$DB_NAME'${NC}"
echo "Backup file: $BACKUP_FILE"
echo "Database: $DB_NAME"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a safety backup before restore
SAFETY_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
echo -e "${GREEN}Creating safety backup before restore...${NC}"

if [ -n "$DB_PASSWORD" ]; then
    PGPASSWORD="$DB_PASSWORD" pg_dump -U "$DB_USER" -h "$DB_HOST" "$DB_NAME" | gzip > "$SAFETY_BACKUP"
else
    pg_dump -U "$DB_USER" -h "$DB_HOST" "$DB_NAME" | gzip > "$SAFETY_BACKUP"
fi

echo "Safety backup created: $SAFETY_BACKUP"

# Stop backend services to prevent writes during restore
echo -e "${GREEN}Stopping backend services...${NC}"
sudo systemctl stop sarson-backend sarson-celery 2>/dev/null || true

# Perform restore
echo -e "${GREEN}Restoring database from $BACKUP_FILE...${NC}"

if [ -n "$DB_PASSWORD" ]; then
    gunzip -c "$BACKUP_FILE" | PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h "$DB_HOST" "$DB_NAME"
else
    gunzip -c "$BACKUP_FILE" | psql -U "$DB_USER" -h "$DB_HOST" "$DB_NAME"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Restore completed successfully!${NC}"
else
    echo -e "${RED}ERROR: Restore failed!${NC}"
    echo "Safety backup available at: $SAFETY_BACKUP"
    exit 1
fi

# Restart backend services
echo -e "${GREEN}Starting backend services...${NC}"
sudo systemctl start sarson-backend sarson-celery

# Verify services started
sleep 2
if sudo systemctl is-active --quiet sarson-backend; then
    echo -e "${GREEN}Backend service started successfully${NC}"
else
    echo -e "${RED}WARNING: Backend service failed to start${NC}"
fi

if sudo systemctl is-active --quiet sarson-celery; then
    echo -e "${GREEN}Celery service started successfully${NC}"
else
    echo -e "${RED}WARNING: Celery service failed to start${NC}"
fi

echo ""
echo -e "${GREEN}Database restore complete!${NC}"
echo "Safety backup saved at: $SAFETY_BACKUP"
