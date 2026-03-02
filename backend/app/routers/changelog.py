"""Changelog endpoint - returns git commit history."""
import subprocess
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CommitEntry(BaseModel):
    hash: str
    message: str
    date: str
    relative_date: str


class ChangelogResponse(BaseModel):
    commits: List[CommitEntry]


def relative_time(date_str: str) -> str:
    """Convert ISO date to relative time string."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        minutes = seconds / 60
        if minutes < 60:
            m = int(minutes)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        hours = minutes / 60
        if hours < 24:
            h = int(hours)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        days = hours / 24
        if days < 7:
            d = int(days)
            return f"{d} day{'s' if d != 1 else ''} ago"
        weeks = days / 7
        if weeks < 4:
            w = int(weeks)
            return f"{w} week{'s' if w != 1 else ''} ago"
        months = days / 30
        if months < 12:
            m = int(months)
            return f"{m} month{'s' if m != 1 else ''} ago"
        years = days / 365
        y = int(years)
        return f"{y} year{'s' if y != 1 else ''} ago"
    except Exception:
        return date_str


@router.get("/changelog", response_model=ChangelogResponse)
async def get_changelog(
    current_user: User = Depends(get_current_user),
    _admin: User = Depends(require_admin),
    limit: int = 50,
):
    """
    Get git commit history for the CRM repository.
    Admin only.
    """
    try:
        # Get git log with format: hash|||message|||ISO date
        result = subprocess.run(
            [
                "git", "log",
                "--oneline",
                "--no-merges",
                f"-{limit}",
                "--format=%h|||%s|||%aI"
            ],
            cwd="/Users/agentstevesmith/.openclaw/workspace/crm",
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Git command failed: {result.stderr}"
            )
        
        commits: List[CommitEntry] = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|||')
            if len(parts) >= 3:
                commits.append(CommitEntry(
                    hash=parts[0],
                    message=parts[1],
                    date=parts[2],
                    relative_date=relative_time(parts[2]),
                ))
        
        return ChangelogResponse(commits=commits)
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Git command timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Git not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
