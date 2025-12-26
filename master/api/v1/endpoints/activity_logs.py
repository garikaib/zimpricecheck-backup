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
    Get current user's own activity logs.
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
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List activity logs based on role:
    - Super Admin: All logs
    - Node Admin: Logs of Site Admins on their nodes + own logs
    """
    query = db.query(models.ActivityLog)
    
    if current_user.role == models.UserRole.SUPER_ADMIN:
        # Super Admin sees all
        if user_id:
            query = query.filter(models.ActivityLog.user_id == user_id)
    else:
        # Node Admin: Get Site Admins under their nodes + own logs
        node_ids = [n.id for n in current_user.nodes]
        site_admin_ids = (
            db.query(models.User.id)
            .join(models.Site, models.User.id == models.Site.admin_id)
            .filter(models.Site.node_id.in_(node_ids))
            .filter(models.User.role == models.UserRole.SITE_ADMIN)
            .distinct()
            .all()
        )
        allowed_user_ids = [current_user.id] + [u.id for u in site_admin_ids]
        
        if user_id:
            if user_id not in allowed_user_ids:
                raise HTTPException(status_code=403, detail="Cannot view this user's logs")
            query = query.filter(models.ActivityLog.user_id == user_id)
        else:
            query = query.filter(models.ActivityLog.user_id.in_(allowed_user_ids))
    
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
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get specific user's logs:
    - Super Admin: Any user
    - Node Admin: Site Admins on their nodes only
    """
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Access check for Node Admins
    if current_user.role != models.UserRole.SUPER_ADMIN:
        # Node Admin can view own logs or Site Admins under their nodes
        if user_id == current_user.id:
            pass  # Can view own
        elif target_user.role == models.UserRole.SITE_ADMIN:
            # Check if Site Admin has sites on their nodes
            node_ids = [n.id for n in current_user.nodes]
            has_access = (
                db.query(models.Site)
                .filter(models.Site.admin_id == user_id)
                .filter(models.Site.node_id.in_(node_ids))
                .first()
            )
            if not has_access:
                raise HTTPException(status_code=403, detail="Cannot view this user's logs")
        else:
            raise HTTPException(status_code=403, detail="Cannot view this user's logs")
    
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
