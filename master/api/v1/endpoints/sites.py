from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models

router = APIRouter()


@router.get("/", response_model=schemas.SiteListResponse)
def read_sites(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    List sites based on role.
    """
    if current_user.role == models.UserRole.SUPER_ADMIN:
        sites = db.query(models.Site).offset(skip).limit(limit).all()
        total = db.query(models.Site).count()
    elif current_user.role == models.UserRole.NODE_ADMIN:
        # Node admins see sites on their nodes
        node_ids = [n.id for n in current_user.nodes]
        sites = db.query(models.Site).filter(models.Site.node_id.in_(node_ids)).offset(skip).limit(limit).all()
        total = db.query(models.Site).filter(models.Site.node_id.in_(node_ids)).count()
    else:
        # Site admins see only their sites
        sites = db.query(models.Site).filter(models.Site.admin_id == current_user.id).offset(skip).limit(limit).all()
        total = db.query(models.Site).filter(models.Site.admin_id == current_user.id).count()
    
    # Build response
    site_responses = []
    for site in sites:
        last_backup = None
        if site.backups:
            last_backup = max(b.created_at for b in site.backups)
        
        site_responses.append({
            "id": site.id,
            "name": site.name,
            "wp_path": site.wp_path,
            "db_name": site.db_name,
            "node_id": site.node_id,
            "status": site.status or "active",
            "storage_used_gb": round((site.storage_used_bytes or 0) / (1024**3), 2),
            "last_backup": last_backup,
        })
    
    return {"sites": site_responses, "total": total}


@router.get("/simple", response_model=List[schemas.SiteSimple])
def read_sites_simple(
    node_id: int = None,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Simple list of sites for dropdowns. Optionally filter by node_id.
    """
    query = db.query(models.Site)
    
    if current_user.role == models.UserRole.SUPER_ADMIN:
        if node_id:
            query = query.filter(models.Site.node_id == node_id)
    elif current_user.role == models.UserRole.NODE_ADMIN:
        node_ids = [n.id for n in current_user.nodes]
        if node_id:
            if node_id not in node_ids:
                raise HTTPException(status_code=403, detail="Access denied to this node")
            query = query.filter(models.Site.node_id == node_id)
        else:
            query = query.filter(models.Site.node_id.in_(node_ids))
    else:
        # Site admins see only their sites
        query = query.filter(models.Site.admin_id == current_user.id)
    
    sites = query.all()
    return [{"id": s.id, "name": s.name, "node_id": s.node_id} for s in sites]


@router.get("/{site_id}")
def read_site(
    site_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get site details.
    """
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Check access
    if current_user.role == models.UserRole.SITE_ADMIN:
        if site.admin_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    last_backup = None
    if site.backups:
        last_backup = max(b.created_at for b in site.backups)
    
    return {
        "id": site.id,
        "name": site.name,
        "wp_path": site.wp_path,
        "db_name": site.db_name,
        "node_id": site.node_id,
        "status": site.status or "active",
        "storage_used_gb": round((site.storage_used_bytes or 0) / (1024**3), 2),
        "last_backup": last_backup,
        "backup_status": site.backup_status,
        "backup_progress": site.backup_progress,
        "backup_message": site.backup_message,
    }


# ============== Backup Control Endpoints ==============

@router.post("/{site_id}/backup/start")
async def start_site_backup(
    site_id: int,
    simulate: bool = True,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Start a backup for a site.
    For now, runs locally via daemon API.
    """
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Check access
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if already running
    if site.backup_status == "running":
        raise HTTPException(status_code=409, detail="Backup already running")
    
    # Import and call daemon API directly (same server)
    try:
        from daemon.api import start_backup, BackupStartRequest
        from fastapi import BackgroundTasks
        
        # Create a BackgroundTasks instance
        bg = BackgroundTasks()
        
        request = BackupStartRequest(
            site_path=site.wp_path,
            site_name=site.name,
            simulate=simulate,
        )
        
        result = await start_backup(request, bg)
        
        # Update site status
        from datetime import datetime
        site.backup_status = "running"
        site.backup_progress = 0
        site.backup_started_at = datetime.utcnow()
        site.backup_message = "Backup starting..."
        site.backup_error = None
        db.commit()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{site_id}/backup/stop")
async def stop_site_backup(
    site_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """Stop a running backup for a site."""
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    try:
        from daemon.api import stop_backup
        result = await stop_backup()
        
        site.backup_status = "stopped"
        site.backup_message = "Backup stopped by user"
        db.commit()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{site_id}/backup/status")
async def get_site_backup_status(
    site_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
):
    """Get backup status for a site."""
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Also get live status from daemon
    try:
        from daemon.api import get_backup_status
        daemon_status = await get_backup_status()
        
        # Sync status to site if it's for this site
        if daemon_status.get("current_site") == site.name:
            site.backup_status = daemon_status.get("status", "idle")
            site.backup_progress = daemon_status.get("progress", 0)
            site.backup_message = daemon_status.get("message")
            site.backup_error = daemon_status.get("error")
            db.commit()
        
        return {
            "site_id": site.id,
            "site_name": site.name,
            "status": site.backup_status,
            "progress": site.backup_progress,
            "message": site.backup_message,
            "error": site.backup_error,
            "started_at": site.backup_started_at.isoformat() if site.backup_started_at else None,
        }
        
    except ImportError:
        # Daemon not available, return DB status
        return {
            "site_id": site.id,
            "site_name": site.name,
            "status": site.backup_status,
            "progress": site.backup_progress,
            "message": site.backup_message,
            "error": site.backup_error,
            "started_at": site.backup_started_at.isoformat() if site.backup_started_at else None,
        }


# ============== Site Import from Scan ==============

@router.post("/import")
async def import_discovered_site(
    name: str,
    wp_path: str,
    db_name: str = None,
    node_id: int = None,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Import a discovered WordPress site into the system.
    """
    # Check if site already exists
    existing = db.query(models.Site).filter(models.Site.wp_path == wp_path).first()
    if existing:
        raise HTTPException(status_code=400, detail="Site with this path already exists")
    
    # Default to master node if not specified
    if not node_id:
        node = db.query(models.Node).first()
        if node:
            node_id = node.id
    
    site = models.Site(
        name=name,
        wp_path=wp_path,
        db_name=db_name,
        node_id=node_id,
        status="active",
        backup_status="idle",
    )
    
    db.add(site)
    db.commit()
    db.refresh(site)
    
    return {
        "success": True,
        "message": f"Site '{name}' imported successfully",
        "site": {
            "id": site.id,
            "name": site.name,
            "wp_path": site.wp_path,
            "node_id": site.node_id,
        }
    }

