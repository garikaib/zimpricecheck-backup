from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
from master.core.activity_logger import log_action
import secrets
import uuid

router = APIRouter()

@router.post("/join-request", response_model=schemas.NodeJoinResponse)
def request_join(
    *,
    db: Session = Depends(deps.get_db),
    node_in: schemas.NodeJoinRequest,
) -> Any:
    """
    Public Endpoint: Submit a request to join the cluster.
    Returns a Request ID to poll for status.
    """
    # Check if hostname already exists
    existing = db.query(models.Node).filter(models.Node.hostname == node_in.hostname).first()
    if existing:
        if existing.status == models.NodeStatus.ACTIVE:
             return {"request_id": "ALREADY_ACTIVE", "message": "Node already registered and active."}
        elif existing.status == models.NodeStatus.BLOCKED:
             raise HTTPException(status_code=403, detail="Node is blocked from joining.")
        else:
            # Pending or inactive, return existing ID (or re-generate?)
            # For simplicity, we assume we return the existing node's API key is NOT returned here.
            # We return a placeholder request ID (hashed ID?) or just the ID.
            # Let's use ID as request ID for now.
            return {"request_id": str(existing.id), "message": "Request already pending."}

    # Create new Pending Node
    # api_key is generated but NOT returned yet.
    api_key = secrets.token_urlsafe(32)
    
    node = models.Node(
        hostname=node_in.hostname,
        ip_address=node_in.ip_address,
        api_key=api_key,
        status=models.NodeStatus.PENDING,
        storage_quota_gb=100
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    
    return {"request_id": str(node.id), "message": "Join request submitted. Waiting for approval."}

@router.get("/status/{request_id}", response_model=schemas.NodeStatusResponse)
def check_status(
    request_id: str,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Public Endpoint: Check status of a join request.
    If APPROVED, returns the API Key (one-time show? or always? Secure enough for this context?)
    Ideally one-time, but for now we return it if status is ACTIVE.
    """
    try:
        node_id = int(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Request ID")

    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Request not found")
    
    response = {"status": node.status}
    
    if node.status == models.NodeStatus.ACTIVE:
        response["api_key"] = node.api_key
        
    return response

@router.post("/approve/{node_id}", response_model=schemas.NodeResponse)
def approve_node(
    node_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Approve a pending node.
    """
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.status = models.NodeStatus.ACTIVE
    node.admin_id = current_superuser.id # Assign to approver for now
    db.commit()
    db.refresh(node)
    
    # Log node approval
    log_action(
        action=models.ActionType.NODE_APPROVE,
        user=current_superuser,
        target_type="node",
        target_id=node.id,
        target_name=node.hostname,
    )
    
    return node

@router.get("/", response_model=List[schemas.NodeResponse])
def read_nodes(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve nodes.
    """
    if current_user.role == models.UserRole.SUPER_ADMIN:
        nodes = db.query(models.Node).offset(skip).limit(limit).all()
    else:
        # Node admins see their own nodes
        nodes = db.query(models.Node).filter(models.Node.admin_id == current_user.id).offset(skip).limit(limit).all()
    return nodes


@router.get("/simple", response_model=List[schemas.NodeSimple])
def read_nodes_simple(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Simple list of nodes for dropdowns.
    """
    if current_user.role == models.UserRole.SUPER_ADMIN:
        nodes = db.query(models.Node).all()
    else:
        nodes = db.query(models.Node).filter(models.Node.admin_id == current_user.id).all()
    return nodes


@router.get("/{node_id}", response_model=schemas.NodeDetailResponse)
def read_node(
    node_id: int,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get node details with stats.
    """
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Check access for non-super admins
    if current_user.role != models.UserRole.SUPER_ADMIN:
        if node.admin_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Calculate stats
    sites_count = len(node.sites)
    backups_count = sum(len(site.backups) for site in node.sites)
    storage_used_bytes = sum(site.storage_used_bytes or 0 for site in node.sites)
    storage_used_gb = round(storage_used_bytes / (1024**3), 2)
    
    return {
        "id": node.id,
        "hostname": node.hostname,
        "ip_address": node.ip_address,
        "status": node.status.value if hasattr(node.status, 'value') else node.status,
        "storage_quota_gb": node.storage_quota_gb,
        "total_available_gb": node.total_available_gb,
        "storage_used_gb": storage_used_gb,
        "sites_count": sites_count,
        "backups_count": backups_count,
    }


@router.put("/{node_id}/quota", response_model=schemas.NodeResponse)
def update_node_quota(
    node_id: int,
    quota_in: schemas.NodeQuotaUpdate,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Update node storage quota.
    """
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    if quota_in.storage_quota_gb > node.total_available_gb:
        raise HTTPException(
            status_code=400, 
            detail=f"Quota cannot exceed total available ({node.total_available_gb} GB)"
        )
    
    old_quota = node.storage_quota_gb
    node.storage_quota_gb = quota_in.storage_quota_gb
    db.commit()
    db.refresh(node)
    
    # Log quota update
    log_action(
        action=models.ActionType.NODE_QUOTA_UPDATE,
        user=current_superuser,
        target_type="node",
        target_id=node.id,
        target_name=node.hostname,
        details={"old_quota": old_quota, "new_quota": quota_in.storage_quota_gb},
    )
    
    return node


@router.get("/{node_id}/sites", response_model=schemas.SiteListResponse)
def read_node_sites(
    node_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List sites under a node.
    """
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Check access for non-super admins
    if current_user.role != models.UserRole.SUPER_ADMIN:
        if node.admin_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    sites = db.query(models.Site).filter(models.Site.node_id == node_id).offset(skip).limit(limit).all()
    total = db.query(models.Site).filter(models.Site.node_id == node_id).count()
    
    # Build response with computed fields
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


@router.get("/{node_id}/backups", response_model=schemas.BackupListResponse)
def read_node_backups(
    node_id: int,
    site_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List backups for a node.
    """
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Check access
    if current_user.role != models.UserRole.SUPER_ADMIN:
        if node.admin_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Get site IDs for this node
    site_ids = [s.id for s in node.sites]
    if site_id:
        if site_id not in site_ids:
            raise HTTPException(status_code=400, detail="Site not on this node")
        site_ids = [site_id]
    
    backups = (
        db.query(models.Backup)
        .join(models.Site)
        .filter(models.Site.id.in_(site_ids))
        .order_by(models.Backup.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = (
        db.query(models.Backup)
        .join(models.Site)
        .filter(models.Site.id.in_(site_ids))
        .count()
    )
    
    # Build response
    backup_responses = []
    for backup in backups:
        backup_responses.append({
            "id": backup.id,
            "site_id": backup.site_id,
            "site_name": backup.site.name if backup.site else "Unknown",
            "filename": backup.filename,
            "size_gb": round((backup.size_bytes or 0) / (1024**3), 2),
            "created_at": backup.created_at,
            "backup_type": backup.backup_type or "full",
            "status": backup.status or "unknown",
        })
    
    return {"backups": backup_responses, "total": total}


@router.delete("/{node_id}/backups/{backup_id}")
def delete_backup(
    node_id: int,
    backup_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Delete a backup.
    """
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    # Verify backup belongs to this node
    if backup.site.node_id != node_id:
        raise HTTPException(status_code=400, detail="Backup not on this node")
    
    backup_filename = backup.filename
    site_name = backup.site.name if backup.site else "unknown"
    
    db.delete(backup)
    db.commit()
    
    # Log backup deletion
    log_action(
        action=models.ActionType.BACKUP_DELETE,
        user=current_superuser,
        target_type="backup",
        target_id=backup_id,
        target_name=backup_filename,
        details={"site": site_name, "node_id": node_id},
    )
    
    return {"status": "deleted", "backup_id": backup_id}


@router.get("/storage-config")
def get_node_storage_config(
    db: Session = Depends(deps.get_db),
    current_node: models.Node = Depends(deps.get_current_node),
) -> Any:
    """
    Node: Fetch storage provider credentials for backup operations.
    Returns decrypted credentials for the default storage provider.
    """
    from master.core.encryption import decrypt_credential
    
    # Get default storage provider
    provider = db.query(models.StorageProvider).filter(
        models.StorageProvider.is_default == True,
        models.StorageProvider.is_active == True,
    ).first()
    
    if not provider:
        raise HTTPException(status_code=404, detail="No default storage provider configured")
    
    # Decrypt credentials
    access_key = decrypt_credential(provider.access_key_encrypted)
    secret_key = decrypt_credential(provider.secret_key_encrypted)
    
    return {
        "provider": {
            "type": provider.type.value if hasattr(provider.type, 'value') else str(provider.type),
            "bucket": provider.bucket,
            "region": provider.region,
            "endpoint": provider.endpoint,
            "access_key": access_key,
            "secret_key": secret_key,
            "storage_limit_gb": provider.storage_limit_gb,
        }
    }
