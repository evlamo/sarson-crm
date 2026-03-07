#!/bin/bash
cd /Users/agentstevesmith/.openclaw/workspace/crm/backend
source venv/bin/activate
export DATABASE_URL="postgresql://agentstevesmith@localhost:5432/crm_dev"
export REDIS_URL="redis://localhost:6379/0"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
