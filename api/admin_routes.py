from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta, timezone
from typing import List
from fastapi_cache.decorator import cache

from api.database import get_db
from api.models import User, Job, JobStatus
from api.auth_routes import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])

def get_admin_user(current_user: User = Depends(get_current_user)):
    """Dependency to check if the current user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this resource")
    return current_user

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Fetch North Star metrics for the Admin Dashboard."""
    total_users = db.query(User).count()
    total_jobs = db.query(Job).count()
    completed_jobs = db.query(Job).filter(Job.status == JobStatus.COMPLETED).count()
    
    # Calculate success rate
    success_rate = 0
    if total_jobs > 0:
        success_rate = int((completed_jobs / total_jobs) * 100)
        
    today = datetime.now(timezone.utc).date()
    activity = []
    jobs_by_day = {}
    users_by_day = {}
    start = today - timedelta(days=6)
    start_datetime = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    for job in db.query(Job.created_at).filter(Job.created_at >= start_datetime).all():
        if job.created_at:
            key = job.created_at.date().isoformat()
            jobs_by_day[key] = jobs_by_day.get(key, 0) + 1
    for user in db.query(User.created_at).filter(User.created_at >= start_datetime).all():
        if user.created_at:
            key = user.created_at.date().isoformat()
            users_by_day[key] = users_by_day.get(key, 0) + 1
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        activity.append({
            "date": key,
            "label": day.strftime("%a"),
            "jobs": jobs_by_day.get(key, 0),
            "signups": users_by_day.get(key, 0),
        })

    return {
        "total_users": total_users,
        "total_jobs": total_jobs,
        "success_rate": f"{success_rate}%",
        "activity": activity,
    }

@router.get("/users", response_model=List[dict])
def get_all_users(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Get all users and their credit/tier info."""
    users = db.query(User).order_by(User.id.desc()).limit(50).all()
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_admin": u.is_admin, "is_active": u.is_active, "tier": u.tier.value if u.tier else "FREE", "credits": u.credits, "created_at": u.created_at} for u in users]

@router.get("/jobs", response_model=List[dict])
def get_all_jobs_admin(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    """Get all jobs across the platform."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
    return [{
        "id": j.id, 
        "ticker": j.ticker, 
        "user_id": j.user_id, 
        "status": j.status.value if j.status else "PENDING", 
        "created_at": j.created_at, 
        "completed_at": j.completed_at,
        "error_message": j.error_message
    } for j in jobs]
