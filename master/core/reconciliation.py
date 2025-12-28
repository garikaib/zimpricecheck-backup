"""
Storage Reconciliation

Synchronizes database storage tracking with actual S3 usage.
Detects drift and updates records accordingly.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from master.db import models

logger = logging.getLogger(__name__)


def get_s3_client(provider: models.StorageProvider):
    """Create S3 client for a storage provider."""
    import boto3
    from master.core.encryption import decrypt_credential
    
    client_args = {
        'service_name': 's3',
        'region_name': provider.region or 'us-east-1',
        'aws_access_key_id': decrypt_credential(provider.access_key_encrypted),
        'aws_secret_access_key': decrypt_credential(provider.secret_key_encrypted),
    }
    
    if provider.endpoint:
        endpoint = provider.endpoint
        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"
        client_args['endpoint_url'] = endpoint
    
    return boto3.client(**client_args)


def get_s3_prefix_size(
    s3_client, 
    bucket: str, 
    prefix: str
) -> int:
    """Get total size of all objects under a prefix."""
    total_size = 0
    paginator = s3_client.get_paginator('list_objects_v2')
    
    try:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                total_size += obj.get('Size', 0)
    except Exception as e:
        logger.error(f"Error listing S3 prefix {prefix}: {e}")
        raise
    
    return total_size


def reconcile_site_storage(
    site: models.Site,
    provider: models.StorageProvider,
    db: Session,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Reconcile a single site's storage with S3.
    Returns discrepancy info.
    """
    if not site.uuid or not site.node or not site.node.uuid:
        return {
            "site_id": site.id,
            "error": "Missing UUID for site or node",
            "skipped": True
        }
    
    prefix = f"{site.node.uuid}/{site.uuid}/"
    
    try:
        s3_client = get_s3_client(provider)
        actual_bytes = get_s3_prefix_size(s3_client, provider.bucket, prefix)
    except Exception as e:
        return {
            "site_id": site.id,
            "error": str(e),
            "skipped": True
        }
    
    db_bytes = site.storage_used_bytes or 0
    drift = actual_bytes - db_bytes
    drift_gb = round(drift / (1024 ** 3), 3)
    
    result = {
        "site_id": site.id,
        "site_name": site.name,
        "prefix": prefix,
        "db_bytes": db_bytes,
        "actual_bytes": actual_bytes,
        "drift_bytes": drift,
        "drift_gb": drift_gb,
        "has_drift": drift != 0,
    }
    
    if drift != 0 and not dry_run:
        old_value = site.storage_used_bytes
        site.storage_used_bytes = actual_bytes
        db.commit()
        result["corrected"] = True
        result["old_value"] = old_value
        logger.info(f"Corrected site {site.name} storage: {db_bytes} -> {actual_bytes}")
    
    return result


def reconcile_node_storage(
    node: models.Node,
    db: Session
) -> Dict[str, Any]:
    """
    Recalculate node storage from sum of site storage.
    """
    total_from_sites = sum(s.storage_used_bytes or 0 for s in node.sites)
    db_bytes = node.storage_used_bytes or 0
    drift = total_from_sites - db_bytes
    
    result = {
        "node_id": node.id,
        "hostname": node.hostname,
        "db_bytes": db_bytes,
        "calculated_bytes": total_from_sites,
        "drift_bytes": drift,
        "has_drift": drift != 0,
    }
    
    if drift != 0:
        node.storage_used_bytes = total_from_sites
        db.commit()
        result["corrected"] = True
        logger.info(f"Corrected node {node.hostname} storage: {db_bytes} -> {total_from_sites}")
    
    return result


def run_full_reconciliation(
    db: Session,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run full storage reconciliation across all sites and nodes.
    """
    start_time = datetime.utcnow()
    
    # Get default provider
    provider = db.query(models.StorageProvider).filter(
        models.StorageProvider.is_default == True,
        models.StorageProvider.is_active == True
    ).first()
    
    if not provider:
        return {
            "success": False,
            "error": "No active default storage provider found",
            "timestamp": start_time.isoformat()
        }
    
    sites_results = []
    nodes_results = []
    total_drift = 0
    errors = 0
    
    # Reconcile all sites
    sites = db.query(models.Site).all()
    for site in sites:
        result = reconcile_site_storage(site, provider, db, dry_run)
        sites_results.append(result)
        if result.get("has_drift"):
            total_drift += abs(result.get("drift_bytes", 0))
        if result.get("error"):
            errors += 1
    
    # Reconcile all nodes
    nodes = db.query(models.Node).all()
    for node in nodes:
        result = reconcile_node_storage(node, db)
        nodes_results.append(result)
    
    end_time = datetime.utcnow()
    
    return {
        "success": True,
        "dry_run": dry_run,
        "timestamp": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "sites_checked": len(sites_results),
        "nodes_checked": len(nodes_results),
        "sites_with_drift": sum(1 for r in sites_results if r.get("has_drift")),
        "total_drift_bytes": total_drift,
        "total_drift_gb": round(total_drift / (1024 ** 3), 2),
        "errors": errors,
        "sites": sites_results,
        "nodes": nodes_results,
    }


def get_storage_health(db: Session) -> Dict[str, Any]:
    """
    Get overall storage health status for dashboard.
    """
    # Get provider info
    provider = db.query(models.StorageProvider).filter(
        models.StorageProvider.is_default == True
    ).first()
    
    # Count sites over quota
    sites = db.query(models.Site).all()
    over_quota_sites = []
    warning_sites = []  # >80% usage
    
    for site in sites:
        used = site.storage_used_bytes or 0
        quota = (site.storage_quota_gb or 10) * (1024 ** 3)
        usage_pct = (used / quota * 100) if quota > 0 else 0
        
        if used > quota:
            over_quota_sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "used_gb": round(used / (1024 ** 3), 2),
                "quota_gb": site.storage_quota_gb,
                "usage_percent": round(usage_pct, 1),
                "exceeded_at": site.quota_exceeded_at.isoformat() if site.quota_exceeded_at else None
            })
        elif usage_pct >= 80:
            warning_sites.append({
                "site_id": site.id,
                "site_name": site.name,
                "usage_percent": round(usage_pct, 1)
            })
    
    # Count scheduled deletions
    scheduled = db.query(models.Backup).filter(
        models.Backup.scheduled_deletion != None
    ).count()
    
    # Total storage used
    total_used = sum(s.storage_used_bytes or 0 for s in sites)
    
    return {
        "healthy": len(over_quota_sites) == 0,
        "total_sites": len(sites),
        "total_used_gb": round(total_used / (1024 ** 3), 2),
        "over_quota_count": len(over_quota_sites),
        "over_quota_sites": over_quota_sites,
        "warning_count": len(warning_sites),
        "warning_sites": warning_sites,
        "scheduled_deletions": scheduled,
        "provider": {
            "name": provider.name if provider else None,
            "bucket": provider.bucket if provider else None,
            "is_active": provider.is_active if provider else False
        } if provider else None,
        "timestamp": datetime.utcnow().isoformat()
    }


def delete_s3_object(
    provider: models.StorageProvider,
    s3_path: str
) -> bool:
    """
    Delete a single object from S3.
    Returns True if successful.
    """
    try:
        s3_client = get_s3_client(provider)
        
        # Parse Key from s3_path (stored as s3://bucket/key)
        key = s3_path
        if key.startswith(f"s3://{provider.bucket}/"):
            key = key[len(f"s3://{provider.bucket}/"):]
        elif key.startswith("s3://"):
            parts = key[5:].split("/", 1)
            if len(parts) == 2:
                key = parts[1]
                
        s3_client.delete_object(Bucket=provider.bucket, Key=key)
        logger.info(f"Deleted S3 object: {provider.bucket}/{key}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete S3 object {s3_path}: {e}")
        return False
