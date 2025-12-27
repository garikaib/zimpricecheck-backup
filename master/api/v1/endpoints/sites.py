from typing import Any, List, Dict
from pathlib import Path
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
            "uuid": site.uuid,
            "name": site.name,
            "wp_path": site.wp_path,
            "db_name": site.db_name,
            "node_id": site.node_id,
            "node_uuid": site.node.uuid if site.node else None,
            "status": site.status or "active",
            "storage_used_bytes": site.storage_used_bytes or 0,
            "storage_quota_gb": site.storage_quota_gb or 10,
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
        "uuid": site.uuid,
        "name": site.name,
        "wp_path": site.wp_path,
        "db_name": site.db_name,
        "node_id": site.node_id,
        "node_uuid": site.node.uuid if site.node else None,
        "status": site.status or "active",
        "storage_used_bytes": site.storage_used_bytes or 0,
        "storage_quota_gb": site.storage_quota_gb or 10,
        "storage_used_gb": round((site.storage_used_bytes or 0) / (1024**3), 2),
        "last_backup": last_backup,
        "backup_status": site.backup_status,
        "backup_progress": site.backup_progress,
        "backup_message": site.backup_message,
    }


# ============== Quota Management ==============

@router.put("/{site_id}/quota")
def update_site_quota(
    site_id: int,
    quota_gb: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Update site storage quota.
    Validates that quota doesn't exceed node limits.
    """
    from master.core.quota_manager import validate_site_quota_update
    
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Check access
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get the node
    node = site.node
    if not node:
        raise HTTPException(status_code=400, detail="Site has no associated node")
    
    # Validate quota
    validation = validate_site_quota_update(quota_gb, site, node, db)
    
    if not validation["valid"]:
        raise HTTPException(
            status_code=400, 
            detail={
                "message": validation["error"],
                "max_allowed_gb": validation.get("max_allowed", node.storage_quota_gb)
            }
        )
    
    # Update quota
    old_quota = site.storage_quota_gb
    site.storage_quota_gb = quota_gb
    
    # Clear exceeded marker if now under quota
    if site.quota_exceeded_at:
        used_bytes = site.storage_used_bytes or 0
        if used_bytes <= quota_gb * (1024 ** 3):
            site.quota_exceeded_at = None
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Quota updated from {old_quota} GB to {quota_gb} GB",
        "site_id": site.id,
        "old_quota_gb": old_quota,
        "new_quota_gb": quota_gb,
        "remaining_node_quota_gb": validation.get("remaining_node_quota"),
    }


# ============== Backup Control Endpoints ==============

@router.post("/{site_id}/backup/start")
async def start_site_backup(
    site_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Start a real backup for a site.
    Runs DB dump, file compression, and upload.
    """
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Check access
    if current_user.role == models.UserRole.NODE_ADMIN:
        if site.node_id not in [n.id for n in current_user.nodes]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if already running (check DB, not in-memory)
    if site.backup_status == "running":
        raise HTTPException(status_code=409, detail="Backup already running")
    
    # Import and call daemon API directly (same server)
    try:
        from daemon.api import start_backup, BackupStartRequest
        from fastapi import BackgroundTasks
        
        # Create a BackgroundTasks instance
        bg = BackgroundTasks()
        
        request = BackupStartRequest(
            site_id=site.id,
            site_path=site.wp_path,
            site_name=site.name,
        )
        
        result = await start_backup(request, bg, db)
        
        return result
        
    except HTTPException:
        raise
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
        from daemon.api import stop_backup, BackupStopRequest
        
        request = BackupStopRequest(site_id=site.id)
        result = await stop_backup(request, db)
        
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


# ============== Site Manual Add ==============

@router.post("/manual", response_model=Dict[str, Any])
async def add_site_manually(
    site_in: schemas.SiteManualCreate,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Manually add a site by path. Verifies with daemon first.
    """
    # 1. Determine Node
    node_id = site_in.node_id
    if not node_id:
        # Default to master node if not specified
        # In a real multi-node setup, we'd need to know which node fs to check.
        # For now, assuming Master/Local node for simplified manual add
        # or defaulting to first node.
        node = db.query(models.Node).first()
        if node:
            node_id = node.id
        else:
             raise HTTPException(status_code=400, detail="No nodes available")

    # 2. Check existence
    existing = db.query(models.Site).filter(models.Site.wp_path == site_in.path).first()
    if existing:
         raise HTTPException(status_code=400, detail=f"Site already exists with path {site_in.path}")

    # 3. Call Daemon Verification
    # We need to know which daemon to call.
    # For this implementation, we assume local imports/daemon calls (Master acts as Node)
    # or we'd need HTTP call to node agent.
    # Given the project context (integrated daemon), we import directly.
    
    try:
        from daemon.api import verify_site_endpoint, VerifySiteRequest
        
        verify_req = VerifySiteRequest(
            path=site_in.path,
            wp_config_path=site_in.wp_config_path
        )
        
        # Directly calling the async function since we are in async context
        # and likely in the same process/server for this "Master+Node" setup
        # If separate, we'd use requests/httpx to call the node's API.
        verify_result = await verify_site_endpoint(verify_req)
        
        if not verify_result.get("valid"):
            error_msg = verify_result.get("error", "Verification failed")
            if verify_result.get("needs_config_path"):
                 raise HTTPException(status_code=422, detail={
                     "message": error_msg,
                     "code": "missing_config",
                     "hint": "Please provide the full path to wp-config.php"
                 })
            
            raise HTTPException(status_code=400, detail=f"Invalid site: {error_msg}")
            
        # 4. Create Site
        details = verify_result.get("details", {})
        
        site_name = site_in.name or details.get("site_name") or Path(site_in.path).name
        
        site = models.Site(
            name=site_name,
            wp_path=site_in.path,
            db_name=details.get("db_name"),
            node_id=node_id,
            status="active",
            site_url=details.get("site_url"), # Assuming we add this field to model later or use it logic
            backup_status="idle",
        )
        
        db.add(site)
        db.commit()
        db.refresh(site)
        
        return {
            "success": True,
            "message": f"Site '{site.name}' added successfully",
            "site": {
                "id": site.id,
                "name": site.name,
                "url": details.get("site_url"),
                "wp_path": site.wp_path,
                "node_id": site.node_id
            }
        }
        
    except ImportError:
        raise HTTPException(status_code=500, detail="Daemon module not available")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

