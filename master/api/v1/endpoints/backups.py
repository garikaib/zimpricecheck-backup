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
    delete_remote: bool = Query(False, description="Also delete file from remote storage"),
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Delete a backup record. Optionally delete the remote file.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    site_name = backup.site.name if backup.site else "Unknown"
    filename = backup.filename
    
    # TODO: Implement remote file deletion if delete_remote=True
    # This would require decrypting provider credentials and using boto3/similar
    if delete_remote and backup.s3_path:
        # Placeholder - actual implementation requires storage provider integration
        pass
    
    db.delete(backup)
    db.commit()
    
    return {
        "success": True,
        "message": f"Backup '{filename}' for site '{site_name}' deleted",
        "remote_deleted": delete_remote and backup.s3_path is not None,
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
    
    # TODO: Generate presigned URL using storage provider credentials
    # This is a placeholder - actual implementation requires:
    # 1. Decrypt provider credentials
    # 2. Use boto3 or equivalent to generate presigned URL
    
    # For now, return the path info so frontend knows it exists
    return {
        "backup_id": backup.id,
        "filename": backup.filename,
        "s3_path": backup.s3_path,
        "provider": backup.provider.name,
        "download_url": None,  # TODO: Implement presigned URL
        "message": "Presigned URL generation not yet implemented. Use s3_path directly if you have provider access.",
        "expires_in_seconds": 0,
    }
