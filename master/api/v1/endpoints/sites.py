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
    }
