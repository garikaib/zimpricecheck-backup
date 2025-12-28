import logging
from sqlalchemy.orm import Session
from master.db import models
from master.core.reconciliation import delete_s3_object

logger = logging.getLogger(__name__)

def enforce_retention_policy(site_id: int, db: Session):
    """
    Check and enforce backup retention policy for a site.
    Deletes oldest backups if count exceeds retention_copies.
    """
    try:
        site = db.query(models.Site).filter(models.Site.id == site_id).first()
        if not site:
            return

        # Determine retention limit
        # Priority: Site config > Node limit > Default 5
        limit = site.retention_copies or 5
        
        # Enforce Node max limit if applicable
        if site.node and site.node.max_retention_copies:
            limit = min(limit, site.node.max_retention_copies)
            
        # Fetch all successful backups, newest first
        backups = db.query(models.Backup).filter(
            models.Backup.site_id == site_id,
            models.Backup.status == "SUCCESS"
        ).order_by(models.Backup.created_at.desc()).all()
        
        if len(backups) <= limit:
            return
            
        # Identify backups to delete
        to_delete = backups[limit:]
        
        logger.info(f"Enforcing retention for site {site.name}: Deleting {len(to_delete)} old backups (Limit: {limit})")
        
        for backup in to_delete:
            delete_backup_record(backup, db)
            
    except Exception as e:
        logger.exception(f"Error enforcing retention for site {site_id}")

def delete_backup_record(backup: models.Backup, db: Session):
    """
    Delete a backup record and its remote file.
    Does NOT commit the session (caller should commit).
    Actually, to keep stats consistent, we might want to commit per deletion or in batch.
    """
    site = backup.site
    size_bytes = backup.size_bytes or 0
    filename = backup.filename
    
    # Delete from S3
    if backup.s3_path and backup.provider:
        try:
            delete_s3_object(backup.provider, backup.s3_path)
            logger.info(f"Deleted S3 object for retention: {backup.s3_path}")
        except Exception as e:
            logger.warning(f"Failed to delete S3 object {backup.s3_path}: {e}")

    # Update storage counters
    if site:
        site.storage_used_bytes = max(0, (site.storage_used_bytes or 0) - size_bytes)
        if site.node:
            site.node.storage_used_bytes = max(0, (site.node.storage_used_bytes or 0) - size_bytes)
        
        # Clear quota flag if resolved
        if site.quota_exceeded_at:
            used = site.storage_used_bytes
            quota = (site.storage_quota_gb or 10) * (1024 ** 3)
            if used <= quota:
                site.quota_exceeded_at = None
                
    if backup.provider:
        backup.provider.used_bytes = max(0, (backup.provider.used_bytes or 0) - size_bytes)
    
    db.delete(backup)
    db.commit() # Commit each deletion to ensure consistency
