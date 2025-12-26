"""
Activity Logger - Non-blocking logging utility for tracking user actions.
Handles Cloudflare-aware IP detection and auto-cleanup for retention.
"""
import json
import threading
from datetime import datetime
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session
from master.db import models
from master.db.session import SessionLocal

# Maximum logs to keep per user
MAX_LOGS_PER_USER = 100


def get_client_ip(request: Request) -> str:
    """
    Get real client IP, handling proxies and Cloudflare.
    
    Priority order:
    1. CF-Connecting-IP (Cloudflare)
    2. X-Real-IP (Nginx)
    3. X-Forwarded-For (first IP in chain)
    4. request.client.host (fallback)
    """
    if not request:
        return "unknown"
    
    # Cloudflare
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    
    # Nginx/reverse proxy
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Standard proxy header (take first IP)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Direct connection
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request."""
    if not request:
        return "unknown"
    return request.headers.get("User-Agent", "unknown")[:500]  # Limit length


def _cleanup_old_logs(db: Session, user_id: int):
    """Remove old logs keeping only the most recent MAX_LOGS_PER_USER."""
    if not user_id:
        return
    
    # Get IDs of logs to keep
    logs_to_keep = (
        db.query(models.ActivityLog.id)
        .filter(models.ActivityLog.user_id == user_id)
        .order_by(models.ActivityLog.created_at.desc())
        .limit(MAX_LOGS_PER_USER)
        .subquery()
    )
    
    # Delete logs not in the keep list
    db.query(models.ActivityLog).filter(
        models.ActivityLog.user_id == user_id,
        ~models.ActivityLog.id.in_(logs_to_keep)
    ).delete(synchronize_session=False)
    db.commit()


def _log_action_sync(
    user_id: Optional[int],
    user_email: Optional[str],
    action: models.ActionType,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Synchronous logging function that runs in a separate thread."""
    try:
        db = SessionLocal()
        
        log_entry = models.ActivityLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
        )
        
        db.add(log_entry)
        db.commit()
        
        # Cleanup old logs for this user
        if user_id:
            _cleanup_old_logs(db, user_id)
        
        db.close()
    except Exception as e:
        # Silent failure - don't affect main request
        print(f"[ActivityLog] Error logging action: {e}")


def log_action(
    action: models.ActionType,
    user: Optional[models.User] = None,
    request: Optional[Request] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_email: Optional[str] = None,
):
    """
    Non-blocking activity logging.
    
    Usage:
        log_action(
            action=ActionType.LOGIN,
            user=current_user,
            request=request,
            details={"success": True}
        )
    """
    # Extract info from request if provided
    if request:
        if not ip_address:
            ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
    else:
        user_agent = None
    
    # Get user info
    user_id = user.id if user else None
    if not user_email and user:
        user_email = user.email
    
    # Run in background thread (non-blocking)
    thread = threading.Thread(
        target=_log_action_sync,
        args=(
            user_id,
            user_email,
            action,
            target_type,
            target_id,
            target_name,
            details,
            ip_address,
            user_agent,
        ),
        daemon=True,
    )
    thread.start()
