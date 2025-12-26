from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models

router = APIRouter()


@router.get("/me", response_model=schemas.ActivityLogListResponse)
def read_my_activity_logs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 50,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user's activity logs.
    """
    logs = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.user_id == current_user.id)
        .order_by(models.ActivityLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(models.ActivityLog).filter(
        models.ActivityLog.user_id == current_user.id
    ).count()
    
    return {"logs": logs, "total": total}


@router.get("/", response_model=schemas.ActivityLogListResponse)
def read_activity_logs(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 50,
    user_id: int = None,
    action: str = None,
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: List all activity logs.
    Optional filters: user_id, action
    """
    query = db.query(models.ActivityLog)
    
    if user_id:
        query = query.filter(models.ActivityLog.user_id == user_id)
    if action:
        query = query.filter(models.ActivityLog.action == action)
    
    logs = query.order_by(models.ActivityLog.created_at.desc()).offset(skip).limit(limit).all()
    total = query.count()
    
    return {"logs": logs, "total": total}


@router.get("/user/{user_id}", response_model=schemas.ActivityLogListResponse)
def read_user_activity_logs(
    user_id: int,
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 50,
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Get specific user's activity logs.
    """
    logs = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.user_id == user_id)
        .order_by(models.ActivityLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(models.ActivityLog).filter(
        models.ActivityLog.user_id == user_id
    ).count()
    
    return {"logs": logs, "total": total}
