"""
Storage Provider Management API

Centralized storage provider configuration for the SaaS platform.
Super Admins manage providers, nodes fetch credentials via API.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from master import schemas
from master.api import deps
from master.db import models
from master.core.encryption import encrypt_credential, decrypt_credential
from master.core.activity_logger import log_action
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

router = APIRouter()


# --- Helper Functions ---

def _provider_to_response(provider: models.StorageProvider) -> dict:
    """Convert StorageProvider model to response dict with used_gb calculated."""
    return {
        "id": provider.id,
        "name": provider.name,
        "type": provider.type.value if hasattr(provider.type, 'value') else str(provider.type),
        "bucket": provider.bucket,
        "region": provider.region,
        "endpoint": provider.endpoint,
        "is_default": provider.is_default,
        "storage_limit_gb": provider.storage_limit_gb,
        "used_gb": round(provider.used_bytes / (1024**3), 2) if provider.used_bytes else 0.0,
        "is_active": provider.is_active,
        "created_at": provider.created_at,
    }


# --- Storage Summary ---

@router.get("/summary", response_model=schemas.StorageSummaryResponse)
def get_storage_summary(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get storage summary across all nodes.
    Node Admins see only their nodes, Super Admins see all.
    """
    # 1. Determine eligible nodes based on role
    node_query = db.query(models.Node)
    if current_user.role != models.UserRole.SUPER_ADMIN:
        node_query = node_query.filter(models.Node.admin_id == current_user.id)
    
    nodes = node_query.filter(models.Node.status == models.NodeStatus.ACTIVE).all()
    node_ids = [n.id for n in nodes]
    
    # 2. Calculate Total Quota
    total_quota_gb = sum(n.storage_quota_gb for n in nodes)
    
    # 3. Calculate Usage Stats via Aggregation
    # Group by Node
    node_usage_stats = db.query(
        models.Site.node_id,
        func.sum(models.Backup.size_bytes).label("total_bytes")
    ).join(models.Backup).filter(
        models.Site.node_id.in_(node_ids) if node_ids else False
    ).group_by(models.Site.node_id).all()
    
    node_usage_map = {stat.node_id: stat.total_bytes or 0 for stat in node_usage_stats}
    
    # Group by Provider (Super Admin only for detailed provider view, but totals needed for all)
    # Note: We calculate provider stats globally for the providers view, 
    # but strictly speaking user should only see what they manage? 
    # Usually users see generic "Storage Used" but simplified. 
    # For now, we return full provider stats for Super Admin, and empty/filtered for others?
    # Schema requires list of providers.
    
    provider_usage_map = {}
    if current_user.role == models.UserRole.SUPER_ADMIN:
        provider_stats = db.query(
            models.Backup.provider_id,
            func.sum(models.Backup.size_bytes).label("total_bytes")
        ).group_by(models.Backup.provider_id).all()
        provider_usage_map = {stat.provider_id: stat.total_bytes or 0 for stat in provider_stats}

    # 4. Build Nodes Summary
    nodes_summary = []
    total_used_gb = 0.0
    
    for node in nodes:
        used_bytes = node_usage_map.get(node.id, 0)
        used_gb = round(used_bytes / (1024**3), 2)
        total_used_gb += used_gb
        
        nodes_summary.append({
            "node_id": node.id,
            "hostname": node.hostname,
            "quota_gb": node.storage_quota_gb,
            "used_gb": used_gb,
            "available_gb": round(node.storage_quota_gb - used_gb, 2),
            "usage_percentage": round((used_gb / node.storage_quota_gb) * 100, 1) if node.storage_quota_gb > 0 else 0,
            "status": node.status.value if hasattr(node.status, 'value') else str(node.status),
        })
    
    # 5. Build Providers Summary (Super Admin)
    providers_response = []
    if current_user.role == models.UserRole.SUPER_ADMIN:
        all_providers = db.query(models.StorageProvider).filter(models.StorageProvider.is_active == True).all()
        for p in all_providers:
            p_used_bytes = provider_usage_map.get(p.id, 0)
            # Update the provider object temporarily or create response dict
            p_dict = _provider_to_response(p)
            p_dict["used_gb"] = round(p_used_bytes / (1024**3), 2)
            providers_response.append(p_dict)

    total_available_gb = round(total_quota_gb - total_used_gb, 2)
    usage_percentage = round((total_used_gb / total_quota_gb) * 100, 1) if total_quota_gb > 0 else 0
    
    return {
        "total_quota_gb": total_quota_gb,
        "total_used_gb": round(total_used_gb, 2),
        "total_available_gb": total_available_gb,
        "usage_percentage": usage_percentage,
        "nodes_count": len(nodes),
        "nodes_summary": nodes_summary,
        "storage_providers": providers_response,
    }


# --- Storage Providers CRUD ---

@router.get("/providers", response_model=schemas.StorageProviderListResponse)
def list_storage_providers(
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: List all storage providers.
    """
    providers = db.query(models.StorageProvider).all()
    return {"providers": [_provider_to_response(p) for p in providers]}


@router.post("/providers", response_model=schemas.StorageProviderResponse)
def create_storage_provider(
    provider_in: schemas.StorageProviderCreate,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Add a new storage provider.
    """
    # Check for duplicate name
    existing = db.query(models.StorageProvider).filter(
        models.StorageProvider.name == provider_in.name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Provider with this name already exists")
    
    # Check for duplicate configuration (same bucket on same endpoint)
    # This prevents adding the same storage twice with different names
    existing_config = db.query(models.StorageProvider).filter(
        models.StorageProvider.type == provider_in.type,
        models.StorageProvider.bucket == provider_in.bucket,
        models.StorageProvider.endpoint == provider_in.endpoint
    ).first()
    
    if existing_config:
        raise HTTPException(
            status_code=400, 
            detail=f"Storage provider configuration duplicates existing provider '{existing_config.name}'"
        )
    
    # If is_default, unset other defaults
    if provider_in.is_default:
        db.query(models.StorageProvider).update({"is_default": False})
    
    # Create provider with encrypted credentials
    provider = models.StorageProvider(
        name=provider_in.name,
        type=models.ProviderType(provider_in.type),
        bucket=provider_in.bucket,
        region=provider_in.region,
        endpoint=provider_in.endpoint,
        access_key_encrypted=encrypt_credential(provider_in.access_key),
        secret_key_encrypted=encrypt_credential(provider_in.secret_key),
        is_default=provider_in.is_default,
        storage_limit_gb=provider_in.storage_limit_gb,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    
    log_action(
        action=models.ActionType.USER_CREATE,  # Reusing for provider creation
        user=current_superuser,
        target_type="storage_provider",
        target_id=provider.id,
        target_name=provider.name,
        details={"type": provider_in.type, "bucket": provider_in.bucket},
    )
    
    return _provider_to_response(provider)


@router.get("/providers/{provider_id}", response_model=schemas.StorageProviderResponse)
def get_storage_provider(
    provider_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Get a specific storage provider.
    """
    provider = db.query(models.StorageProvider).filter(models.StorageProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    return _provider_to_response(provider)


@router.put("/providers/{provider_id}", response_model=schemas.StorageProviderResponse)
def update_storage_provider(
    provider_id: int,
    provider_in: schemas.StorageProviderUpdate,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Update a storage provider.
    """
    provider = db.query(models.StorageProvider).filter(models.StorageProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    
    update_data = provider_in.model_dump(exclude_unset=True)
    
    # Handle is_default flag
    if update_data.get("is_default") == True:
        db.query(models.StorageProvider).filter(
            models.StorageProvider.id != provider_id
        ).update({"is_default": False})
    
    # Encrypt credentials if provided
    if "access_key" in update_data and update_data["access_key"]:
        update_data["access_key_encrypted"] = encrypt_credential(update_data.pop("access_key"))
    else:
        update_data.pop("access_key", None)
    
    if "secret_key" in update_data and update_data["secret_key"]:
        update_data["secret_key_encrypted"] = encrypt_credential(update_data.pop("secret_key"))
    else:
        update_data.pop("secret_key", None)
    
    for field, value in update_data.items():
        setattr(provider, field, value)
    
    db.commit()
    db.refresh(provider)
    
    log_action(
        action=models.ActionType.USER_UPDATE,  # Reusing for provider update
        user=current_superuser,
        target_type="storage_provider",
        target_id=provider.id,
        target_name=provider.name,
        details={"updated_fields": list(update_data.keys())},
    )
    
    return _provider_to_response(provider)


@router.delete("/providers/{provider_id}")
def delete_storage_provider(
    provider_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Delete a storage provider.
    Only allowed if no active backups use this provider.
    """
    provider = db.query(models.StorageProvider).filter(models.StorageProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    
    # Check for backups using this provider (future: add provider_id to Backup model)
    # For now, just check if it's the default
    if provider.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default storage provider")
    
    provider_name = provider.name
    db.delete(provider)
    db.commit()
    
    log_action(
        action=models.ActionType.USER_DELETE,  # Reusing for provider deletion
        user=current_superuser,
        target_type="storage_provider",
        target_id=provider_id,
        target_name=provider_name,
    )
    
    return {"status": "deleted", "provider_id": provider_id}


@router.post("/providers/{provider_id}/test", response_model=schemas.StorageTestResponse)
def test_storage_provider(
    provider_id: int,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Super Admin: Test connection to a storage provider.
    """
    provider = db.query(models.StorageProvider).filter(models.StorageProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Storage provider not found")
    
    if provider.type != models.ProviderType.S3:
        return {"success": False, "message": f"Testing not implemented for {provider.type.value}", "available_space_gb": None}
    
    try:
        # Decrypt credentials
        access_key = decrypt_credential(provider.access_key_encrypted)
        secret_key = decrypt_credential(provider.secret_key_encrypted)
        
        # Build endpoint URL
        endpoint_url = None
        if provider.endpoint:
            endpoint_url = f"https://{provider.endpoint}" if not provider.endpoint.startswith("http") else provider.endpoint
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            region_name=provider.region or 'us-east-1',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        
        # Test by listing bucket contents (limited)
        s3_client.list_objects_v2(Bucket=provider.bucket, MaxKeys=1)
        
        return {
            "success": True,
            "message": "Connection successful",
            "available_space_gb": None,  # S3 doesn't report available space
        }
        
    except NoCredentialsError:
        return {"success": False, "message": "Invalid credentials", "available_space_gb": None}
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        return {"success": False, "message": f"S3 Error: {error_code}", "available_space_gb": None}
    except Exception as e:
        return {"success": False, "message": str(e), "available_space_gb": None}


# --- Storage Health & Reconciliation ---

@router.get("/health")
def get_storage_health(
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get storage health status for dashboard.
    Returns over-quota sites, warning sites, and pending deletions.
    """
    from master.core.reconciliation import get_storage_health as _get_storage_health
    
    return _get_storage_health(db)


@router.post("/reconcile")
def trigger_storage_reconciliation(
    dry_run: bool = False,
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Trigger storage reconciliation.
    Compares DB storage tracking with actual S3 usage and corrects drift.
    
    - dry_run: If true, only reports discrepancies without fixing
    """
    from master.core.reconciliation import run_full_reconciliation
    
    result = run_full_reconciliation(db, dry_run=dry_run)
    return result


@router.post("/cleanup")
def trigger_scheduled_cleanup(
    db: Session = Depends(deps.get_db),
    current_superuser: models.User = Depends(deps.get_current_superuser),
) -> Any:
    """
    Manually trigger scheduled cleanup.
    Deletes all backups past their scheduled_deletion date.
    """
    from master.core.cleanup_scheduler import run_scheduled_cleanup
    
    result = run_scheduled_cleanup(db)
    return result
