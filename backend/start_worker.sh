#!/bin/bash
cd /Users/agentstevesmith/.openclaw/workspace/crm/backend
source venv/bin/activate
export DATABASE_URL="postgresql://agentstevesmith@localhost:5432/crm_dev"
celery -A app.tasks.celery_app worker --loglevel=info -Q email,default
