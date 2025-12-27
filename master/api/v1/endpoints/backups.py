"""
Backup Management Endpoints

CRUD operations for backup records and download URL generation.
"""
from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models

router = APIRouter()


# ============== Site Backups ==============

@router.get("/sites/{site_id}/backups", response_model=schemas.BackupListResponse)
def list_site_backups(
    site_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List all backups for a specific site.
    """
    # Check site exists and user has access
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Access check for Node Admins
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Query backups
    query = db.query(models.Backup).filter(models.Backup.site_id == site_id)
    total = query.count()
    backups = query.order_by(models.Backup.created_at.desc()).offset(skip).limit(limit).all()
    
    backup_list = []
    for b in backups:
        provider_name = None
        if b.provider:
            provider_name = b.provider.name
        
        backup_list.append({
            "id": b.id,
            "site_id": b.site_id,
            "site_name": site.name,
            "filename": b.filename,
            "size_bytes": b.size_bytes or 0,
            "size_gb": round((b.size_bytes or 0) / (1024**3), 3),
            "s3_path": b.s3_path,
            "created_at": b.created_at,
            "backup_type": b.backup_type or "full",
            "status": b.status,
            "storage_provider": provider_name,
        })
    
    return {"backups": backup_list, "total": total}


# ============== Scheduled Deletions (MUST be before /{backup_id} routes) ==============

@router.get("/backups/scheduled-deletions")
def list_scheduled_deletions(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List all backups scheduled for automatic deletion.
    Used by frontend to show pending cleanup warnings.
    """
    query = db.query(models.Backup).filter(
        models.Backup.scheduled_deletion != None
    )
    
    # Filter by access for non-super admins
    if current_user.role == models.UserRole.NODE_ADMIN:
        node_ids = [n.id for n in current_user.nodes]
        query = query.join(models.Site).filter(models.Site.node_id.in_(node_ids))
    
    scheduled = query.order_by(models.Backup.scheduled_deletion.asc()).all()
    
    return {
        "count": len(scheduled),
        "backups": [
            {
                "backup_id": b.id,
                "filename": b.filename,
                "size_gb": round((b.size_bytes or 0) / (1024 ** 3), 2),
                "site_id": b.site_id,
                "site_name": b.site.name if b.site else None,
                "scheduled_deletion": b.scheduled_deletion.isoformat(),
                "days_remaining": max(0, (b.scheduled_deletion - datetime.utcnow()).days),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in scheduled
        ]
    }


# ============== Single Backup Operations ==============

@router.get("/backups/{backup_id}")
def get_backup_detail(
    backup_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get detailed information about a specific backup.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    site = backup.site
    if not site:
        raise HTTPException(status_code=404, detail="Associated site not found")
    
    # Access check for Node Admins
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    provider_detail = None
    if backup.provider:
        provider_detail = {
            "id": backup.provider.id,
            "name": backup.provider.name,
            "type": backup.provider.type.value if hasattr(backup.provider.type, 'value') else str(backup.provider.type),
        }
    
    return {
        "id": backup.id,
        "site_id": backup.site_id,
        "site_name": site.name,
        "filename": backup.filename,
        "size_bytes": backup.size_bytes or 0,
        "size_gb": round((backup.size_bytes or 0) / (1024**3), 3),
        "s3_path": backup.s3_path,
        "created_at": backup.created_at,
        "backup_type": backup.backup_type or "full",
        "status": backup.status,
        "storage_provider": backup.provider.name if backup.provider else None,
        "storage_provider_detail": provider_detail,
    }


@router.delete("/backups/{backup_id}")
def delete_backup(
    backup_id: int,
    delete_remote: bool = Query(True, description="Also delete file from remote storage"),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Delete a backup record and optionally the remote S3 file.
    Updates storage counters for site, node, and provider.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    site = backup.site
    site_name = site.name if site else "Unknown"
    filename = backup.filename
    size_bytes = backup.size_bytes or 0
    s3_deleted = False
    
    # Delete from S3 if requested
    if delete_remote and backup.s3_path and backup.provider:
        try:
            from master.core.reconciliation import delete_s3_object
            s3_deleted = delete_s3_object(backup.provider, backup.s3_path)
        except Exception as e:
            # Log but don't fail - still delete DB record
            pass
    
    # Update storage counters
    if site:
        site.storage_used_bytes = max(0, (site.storage_used_bytes or 0) - size_bytes)
        
        if site.node:
            site.node.storage_used_bytes = max(0, (site.node.storage_used_bytes or 0) - size_bytes)
        
        # Clear quota exceeded if now under limit
        if site.quota_exceeded_at:
            used = site.storage_used_bytes
            quota = (site.storage_quota_gb or 10) * (1024 ** 3)
            if used <= quota:
                site.quota_exceeded_at = None
    
    if backup.provider:
        backup.provider.used_bytes = max(0, (backup.provider.used_bytes or 0) - size_bytes)
    
    db.delete(backup)
    db.commit()
    
    return {
        "success": True,
        "message": f"Backup '{filename}' for site '{site_name}' deleted",
        "s3_deleted": s3_deleted,
        "freed_bytes": size_bytes,
        "freed_gb": round(size_bytes / (1024 ** 3), 2),
    }



@router.delete("/backups/{backup_id}/cancel-deletion")
def cancel_scheduled_deletion(
    backup_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Cancel a scheduled deletion for a backup.
    Clears the scheduled_deletion field.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    # Access check
    if backup.site and current_user.role == models.UserRole.NODE_ADMIN:
        if backup.site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if not backup.scheduled_deletion:
        return {
            "success": True,
            "message": "Backup was not scheduled for deletion",
            "backup_id": backup.id,
        }
    
    old_date = backup.scheduled_deletion
    backup.scheduled_deletion = None
    db.commit()
    
    return {
        "success": True,
        "message": f"Cancelled scheduled deletion for {backup.filename}",
        "backup_id": backup.id,
        "was_scheduled_for": old_date.isoformat(),
    }


@router.get("/backups/{backup_id}/download")
def get_backup_download_url(
    backup_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Generate a presigned download URL for a backup.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    site = backup.site
    if not site:
        raise HTTPException(status_code=404, detail="Associated site not found")
    
    # Access check for Node Admins
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if not backup.provider:
        raise HTTPException(status_code=400, detail="No storage provider associated with this backup")
    
    if not backup.s3_path:
        raise HTTPException(status_code=400, detail="No remote path available for this backup")
    
    # Generate presigned URL
    try:
        from master.core.reconciliation import get_s3_client
        s3_client = get_s3_client(backup.provider)
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': backup.provider.bucket, 'Key': backup.s3_path},
            ExpiresIn=3600  # 1 hour
        )
        
        return {
            "backup_id": backup.id,
            "filename": backup.filename,
            "download_url": url,
            "expires_in_seconds": 3600,
        }
    except Exception as e:
        return {
            "backup_id": backup.id,
            "filename": backup.filename,
            "s3_path": backup.s3_path,
            "provider": backup.provider.name,
            "download_url": None,
            "error": str(e),
        }
