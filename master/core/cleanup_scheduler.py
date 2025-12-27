"""
Cleanup Scheduler

Background task to delete scheduled backups and cleanup over-quota sites.
"""
import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session

from master.db import models

logger = logging.getLogger(__name__)


def run_scheduled_cleanup(db: Session) -> Dict[str, Any]:
    """
    Delete all backups past their scheduled_deletion date.
    Updates storage usage after deletions.
    Returns summary of cleanup actions.
    """
    from master.core.quota_manager import get_overdue_scheduled_backups
    
    overdue = get_overdue_scheduled_backups(db)
    
    deleted_count = 0
    freed_bytes = 0
    errors = []
    
    for backup in overdue:
        try:
            logger.info(f"Auto-deleting expired backup: {backup.filename}")
            
            # Update site storage
            if backup.site:
                backup.site.storage_used_bytes = max(0, 
                    (backup.site.storage_used_bytes or 0) - (backup.size_bytes or 0)
                )
                
                # Update node storage
                if backup.site.node:
                    backup.site.node.storage_used_bytes = max(0,
                        (backup.site.node.storage_used_bytes or 0) - (backup.size_bytes or 0)
                    )
                
                # Clear quota exceeded if now under limit
                used = backup.site.storage_used_bytes or 0
                quota = (backup.site.storage_quota_gb or 10) * (1024 ** 3)
                if used <= quota and backup.site.quota_exceeded_at:
                    backup.site.quota_exceeded_at = None
                    logger.info(f"Site {backup.site.name} back under quota after cleanup")
            
            # Update provider storage
            if backup.provider:
                backup.provider.used_bytes = max(0,
                    (backup.provider.used_bytes or 0) - (backup.size_bytes or 0)
                )
            
            freed_bytes += backup.size_bytes or 0
            
            # Delete the backup record (S3 cleanup would go here in production)
            db.delete(backup)
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup.id}: {e}")
            errors.append({"backup_id": backup.id, "error": str(e)})
    
    db.commit()
    
    result = {
        "deleted_count": deleted_count,
        "freed_bytes": freed_bytes,
        "freed_gb": round(freed_bytes / (1024 ** 3), 2),
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if deleted_count > 0:
        logger.info(f"Scheduled cleanup complete: deleted {deleted_count} backups, freed {result['freed_gb']} GB")
    
    return result


def check_and_notify_pending_deletions(db: Session) -> Dict[str, Any]:
    """
    Check for backups scheduled for deletion within 24 hours and send reminder.
    """
    from datetime import timedelta
    
    tomorrow = datetime.utcnow() + timedelta(days=1)
    
    pending = db.query(models.Backup).filter(
        models.Backup.scheduled_deletion != None,
        models.Backup.scheduled_deletion <= tomorrow,
        models.Backup.scheduled_deletion > datetime.utcnow()
    ).all()
    
    return {
        "pending_count": len(pending),
        "pending_backups": [
            {
                "backup_id": b.id,
                "filename": b.filename,
                "site_name": b.site.name if b.site else None,
                "scheduled_deletion": b.scheduled_deletion.isoformat(),
            }
            for b in pending
        ]
    }


def cleanup_on_startup(db: Session) -> Dict[str, Any]:
    """
    Run cleanup check on server startup.
    Called from main.py lifespan event.
    """
    try:
        result = run_scheduled_cleanup(db)
        return result
    except Exception as e:
        logger.error(f"Startup cleanup failed: {e}")
        return {"error": str(e)}
