"""
Quota Manager

Handles storage quota checking, warning notifications, and cleanup scheduling.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from master.db import models

logger = logging.getLogger(__name__)


def check_quota_status(site: models.Site) -> Dict[str, Any]:
    """
    Check if a site is over quota.
    Returns quota status with details.
    """
    used_bytes = site.storage_used_bytes or 0
    quota_bytes = (site.storage_quota_gb or 10) * (1024 ** 3)
    
    used_gb = round(used_bytes / (1024 ** 3), 2)
    quota_gb = site.storage_quota_gb or 10
    
    is_over_quota = used_bytes > quota_bytes
    usage_percentage = round((used_bytes / quota_bytes) * 100, 1) if quota_bytes > 0 else 0
    
    return {
        "site_id": site.id,
        "site_name": site.name,
        "used_bytes": used_bytes,
        "used_gb": used_gb,
        "quota_gb": quota_gb,
        "is_over_quota": is_over_quota,
        "usage_percentage": usage_percentage,
        "exceeded_at": site.quota_exceeded_at,
    }


def check_node_quota_status(node: models.Node, db: Session) -> Dict[str, Any]:
    """
    Check if a node is over its total quota.
    Calculates total used by all sites on the node.
    """
    # Sum all site storage usage for this node
    total_used = sum(s.storage_used_bytes or 0 for s in node.sites)
    node_quota_bytes = (node.storage_quota_gb or 100) * (1024 ** 3)
    
    is_over_quota = total_used > node_quota_bytes
    
    return {
        "node_id": node.id,
        "node_hostname": node.hostname,
        "used_bytes": total_used,
        "used_gb": round(total_used / (1024 ** 3), 2),
        "quota_gb": node.storage_quota_gb or 100,
        "is_over_quota": is_over_quota,
        "usage_percentage": round((total_used / node_quota_bytes) * 100, 1) if node_quota_bytes > 0 else 0,
    }


def mark_quota_exceeded(site: models.Site, db: Session) -> bool:
    """
    Mark a site as having exceeded quota if not already marked.
    Returns True if this is the first time exceeding.
    """
    if site.quota_exceeded_at is None:
        site.quota_exceeded_at = datetime.utcnow()
        db.commit()
        logger.warning(f"Site {site.name} first exceeded quota at {site.quota_exceeded_at}")
        return True
    return False


def clear_quota_exceeded(site: models.Site, db: Session) -> None:
    """Clear the quota exceeded marker when usage drops below quota."""
    if site.quota_exceeded_at is not None:
        site.quota_exceeded_at = None
        db.commit()
        logger.info(f"Site {site.name} quota cleared")


def schedule_oldest_backup_deletion(
    site: models.Site, 
    db: Session, 
    days: int = 3
) -> Optional[models.Backup]:
    """
    Schedule the oldest backup for deletion after specified days.
    Returns the scheduled backup or None if no backups.
    """
    # Find oldest backup without scheduled deletion
    oldest = db.query(models.Backup).filter(
        models.Backup.site_id == site.id,
        models.Backup.scheduled_deletion == None,
        models.Backup.status == "SUCCESS"
    ).order_by(models.Backup.created_at.asc()).first()
    
    if oldest:
        oldest.scheduled_deletion = datetime.utcnow() + timedelta(days=days)
        db.commit()
        logger.warning(
            f"Scheduled backup {oldest.filename} for deletion on {oldest.scheduled_deletion}"
        )
        return oldest
    
    return None


def get_overdue_scheduled_backups(db: Session) -> list:
    """Get all backups past their scheduled deletion date."""
    return db.query(models.Backup).filter(
        models.Backup.scheduled_deletion != None,
        models.Backup.scheduled_deletion <= datetime.utcnow()
    ).all()


async def send_quota_warning(
    site: models.Site,
    admin_email: str,
    quota_status: Dict[str, Any],
    scheduled_backup: Optional[models.Backup] = None
) -> bool:
    """
    Send quota warning email via communication channel.
    Returns True if sent successfully.
    """
    from master.core.messaging import send_notification
    
    subject = f"⚠️ Storage Quota Exceeded - {site.name}"
    
    deletion_warning = ""
    if scheduled_backup:
        deletion_date = scheduled_backup.scheduled_deletion.strftime("%Y-%m-%d %H:%M UTC")
        deletion_warning = f"""

**Automatic Cleanup Scheduled:**
The oldest backup ({scheduled_backup.filename}) will be automatically deleted on {deletion_date} 
if the quota issue is not resolved by then."""

    message = f"""
Storage quota has been exceeded for site **{site.name}**.

**Current Usage:**
- Used: {quota_status['used_gb']} GB
- Quota: {quota_status['quota_gb']} GB  
- Usage: {quota_status['usage_percentage']}%
{deletion_warning}

**Actions Required:**
1. Delete old backups to free space
2. Increase the site quota (if within node limits)
3. Review backup retention settings

Please address this within 3 days to prevent automatic cleanup.
"""
    
    try:
        await send_notification(
            to=admin_email,
            subject=subject,
            message=message,
            channel_type="email"
        )
        logger.info(f"Quota warning sent to {admin_email} for site {site.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to send quota warning: {e}")
        return False


def validate_site_quota_update(
    new_quota_gb: int,
    site: models.Site,
    node: models.Node,
    db: Session
) -> Dict[str, Any]:
    """
    Validate that a new site quota doesn't exceed node limits.
    Returns validation result with details.
    """
    node_quota_gb = node.storage_quota_gb or 100
    
    # Calculate total quota of all OTHER sites on this node
    other_sites_quota = sum(
        s.storage_quota_gb or 10 
        for s in node.sites 
        if s.id != site.id
    )
    
    # Total would be other sites + new quota
    total_after_update = other_sites_quota + new_quota_gb
    
    if new_quota_gb > node_quota_gb:
        return {
            "valid": False,
            "error": f"Site quota ({new_quota_gb} GB) cannot exceed node quota ({node_quota_gb} GB)",
            "max_allowed": node_quota_gb,
        }
    
    if total_after_update > node_quota_gb:
        available = node_quota_gb - other_sites_quota
        return {
            "valid": False,
            "error": f"Total site quotas would exceed node limit. Max available: {available} GB",
            "max_allowed": available,
        }
    
    return {
        "valid": True,
        "new_quota_gb": new_quota_gb,
        "node_quota_gb": node_quota_gb,
        "remaining_node_quota": node_quota_gb - total_after_update,
    }
