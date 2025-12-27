"""
Daemon API

FastAPI router for daemon-specific endpoints (scan, backup control).
This runs on nodes to receive commands from the master.
"""
import asyncio
import logging
import os
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from daemon.scanner import scan_for_wordpress_sites, site_to_dict, verify_wordpress_site, parse_wp_config
from daemon.modules.base import BackupContext, get_module
from daemon.modules.wordpress import WordPressModule  # Ensure module is registered
from master.api import deps
from master.db import models
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daemon", tags=["daemon"])


# ============== Backup Cleanup Utilities ==============

import glob
import tempfile
import shutil

# Pattern for backup temp directories
BACKUP_TEMP_PATTERN = "backup_*"
BACKUP_TEMP_DIR = tempfile.gettempdir()


def cleanup_orphaned_backup_dirs(site_id: Optional[int] = None, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Clean up orphaned backup temp directories.
    
    Args:
        site_id: If provided, only clean up dirs for this site
        max_age_hours: Only clean dirs older than this (0 = all)
    
    Returns:
        Dict with cleanup stats
    """
    import time
    
    cleaned = []
    errors = []
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    # Build pattern
    if site_id:
        pattern = os.path.join(BACKUP_TEMP_DIR, f"backup_{site_id}_*")
    else:
        pattern = os.path.join(BACKUP_TEMP_DIR, BACKUP_TEMP_PATTERN)
    
    for dir_path in glob.glob(pattern):
        try:
            if os.path.isdir(dir_path):
                # Check age
                dir_mtime = os.path.getmtime(dir_path)
                age_seconds = current_time - dir_mtime
                
                if max_age_hours == 0 or age_seconds > max_age_seconds:
                    size = sum(
                        os.path.getsize(os.path.join(dp, f))
                        for dp, _, files in os.walk(dir_path)
                        for f in files
                    )
                    shutil.rmtree(dir_path)
                    cleaned.append({
                        "path": dir_path,
                        "size_bytes": size,
                        "age_hours": round(age_seconds / 3600, 1),
                    })
                    logger.info(f"Cleaned up orphaned backup dir: {dir_path} ({size} bytes)")
        except Exception as e:
            errors.append({"path": dir_path, "error": str(e)})
            logger.warning(f"Failed to clean up {dir_path}: {e}")
    
    total_freed = sum(d["size_bytes"] for d in cleaned)
    
    return {
        "cleaned_count": len(cleaned),
        "cleaned_dirs": cleaned,
        "total_freed_bytes": total_freed,
        "total_freed_mb": round(total_freed / 1024 / 1024, 2),
        "errors": errors,
    }


def cleanup_on_startup():
    """Clean up orphaned backup directories on server startup."""
    logger.info("Running startup cleanup for orphaned backup directories...")
    result = cleanup_orphaned_backup_dirs(max_age_hours=0)  # Clean all
    if result["cleaned_count"] > 0:
        logger.info(f"Startup cleanup: removed {result['cleaned_count']} dirs, freed {result['total_freed_mb']} MB")
    else:
        logger.info("Startup cleanup: no orphaned backup directories found")
    return result


# Run cleanup on module load (server startup)
try:
    cleanup_on_startup()
except Exception as e:
    logger.warning(f"Startup cleanup failed: {e}")


class ScanRequest(BaseModel):
    base_path: str = "/var/www"


class BackupStartRequest(BaseModel):
    site_id: int
    site_path: str
    site_name: str


class BackupStopRequest(BaseModel):
    site_id: int
    force: bool = False


class VerifySiteRequest(BaseModel):
    path: str
    wp_config_path: Optional[str] = None


# ============== Scan Endpoints ==============

@router.get("/scan")
async def scan_sites(
    base_path: str = "/var/www",
    db: Session = Depends(deps.get_db)
):
    """
    Scan for WordPress sites in the given base path.
    Returns list of discovered sites.
    """
    logger.info(f"Scanning for WordPress sites in {base_path}")
    
    try:
        sites = scan_for_wordpress_sites(base_path)
        result = [site_to_dict(site) for site in sites]
        
        # Determine Node ID
        node_id = None
        node = db.query(models.Node).first()
        if node:
            node_id = node.id
        
        return {
            "success": True,
            "node_id": node_id,
            "sites": result,
            "total": len(result),
            "scanned_path": base_path,
        }
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-site")
async def verify_site_endpoint(request: VerifySiteRequest):
    """
    Verify a potential WordPress site path.
    """
    logger.info(f"Verifying site at {request.path}")
    
    try:
        result = verify_wordpress_site(request.path, request.wp_config_path)
        return result
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Real Backup Execution ==============

async def _run_real_backup(site_id: int, site_path: str, site_name: str):
    """
    Run a real WordPress backup using the WordPressModule.
    Updates site status in DB at each stage.
    """
    from master.db.session import SessionLocal  # Fixed: was master.db.database
    
    logger.info(f"[BACKUP] _run_real_backup started for {site_name} (ID: {site_id})")
    
    db = SessionLocal()
    
    try:
        site = db.query(models.Site).filter(models.Site.id == site_id).first()
        if not site:
            logger.error(f"Site {site_id} not found for backup")
            return
        
        # Parse wp-config to get DB credentials
        wp_config_path = Path(site_path) / "wp-config.php"
        if not wp_config_path.exists():
            # Try parent directory
            wp_config_path = Path(site_path).parent / "wp-config.php"
        
        if not wp_config_path.exists():
            site.backup_status = "failed"
            site.backup_message = "wp-config.php not found"
            site.backup_error = "Cannot find wp-config.php for database credentials"
            db.commit()
            logger.error(f"wp-config.php not found for {site_name}")
            return
        
        config = parse_wp_config(wp_config_path)
        if not config.get("db_name") or not config.get("db_user"):
            site.backup_status = "failed"
            site.backup_message = "Could not parse database credentials"
            site.backup_error = "Missing db_name or db_user in wp-config.php"
            db.commit()
            logger.error(f"Could not parse wp-config for {site_name}")
            return
        
        # Create backup context
        context = BackupContext(
            job_id=f"backup_{site_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            target_id=site_id,
            target_name=site_name,
            config={
                "wp_path": site_path,
                "db_name": config.get("db_name"),
                "db_user": config.get("db_user"),
                "db_password": config.get("db_password", ""),
                "db_host": config.get("db_host", "localhost"),
            }
        )
        
        # Get WordPress module
        wp_module = get_module("wordpress")
        if not wp_module:
            # Manually instantiate if not registered
            wp_module = WordPressModule()
        
        stages = wp_module.get_stages()
        total_stages = len(stages)
        
        logger.info(f"Starting real backup for {site_name} with {total_stages} stages")
        
        for i, stage in enumerate(stages):
            # Check if backup was stopped
            db.refresh(site)
            if site.backup_status == "stopped":
                logger.info(f"Backup stopped by user at stage {stage}")
                return
            
            # Update progress
            progress = int(((i) / total_stages) * 100)
            site.backup_progress = progress
            site.backup_message = f"Running: {stage}"
            db.commit()
            
            logger.info(f"[{site_name}] Stage {i+1}/{total_stages}: {stage}")
            
            # Execute stage
            result = await wp_module.execute_stage(stage, context)
            
            if result.status.value == "failed":
                site.backup_status = "failed"
                site.backup_message = f"Failed at {stage}"
                site.backup_error = result.message
                db.commit()
                logger.error(f"Backup failed at stage {stage}: {result.message}")
                return
            
            logger.info(f"[{site_name}] Stage {stage} completed: {result.message}")
        
        # Backup completed successfully
        archive_size = context.stage_data.get("archive_size", 0)
        archive_name = context.stage_data.get("archive_name", "unknown.tar.zst")
        
        # Create Backup record
        backup_record = models.Backup(
            site_id=site_id,
            filename=archive_name,
            s3_path=context.remote_path,
            size_bytes=archive_size,
            status="SUCCESS",
            backup_type="full",
            created_at=datetime.utcnow(),
        )
        
        # Try to get default provider
        default_provider = db.query(models.StorageProvider).filter(
            models.StorageProvider.is_default == True
        ).first()
        if default_provider:
            backup_record.provider_id = default_provider.id
        
        db.add(backup_record)
        
        # Update site status
        site.backup_status = "completed"
        site.backup_progress = 100
        site.backup_message = f"Backup completed: {archive_name}"
        site.backup_error = None
        site.storage_used_bytes = (site.storage_used_bytes or 0) + archive_size
        
        db.commit()
        
        logger.info(f"Backup completed for {site_name}: {archive_name} ({archive_size} bytes)")
        
    except Exception as e:
        logger.exception(f"Backup failed for site {site_id}: {e}")
        
        # Clean up temp files on failure
        try:
            cleanup_result = cleanup_orphaned_backup_dirs(site_id=site_id, max_age_hours=0)
            if cleanup_result["cleaned_count"] > 0:
                logger.info(f"Cleaned up {cleanup_result['cleaned_count']} temp dirs after failed backup, freed {cleanup_result['total_freed_mb']} MB")
        except Exception as cleanup_error:
            logger.warning(f"Failed to clean up after backup failure: {cleanup_error}")
        
        try:
            site = db.query(models.Site).filter(models.Site.id == site_id).first()
            if site:
                site.backup_status = "failed"
                site.backup_error = str(e)
                site.backup_message = "Backup failed with error"
                db.commit()
        except:
            pass
    finally:
        db.close()


# ============== Backup Control Endpoints ==============

@router.post("/backup/start")
async def start_backup(
    request: BackupStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
):
    """
    Start a real backup for the specified site.
    Returns immediately, backup runs in background.
    """
    # Check site exists and is not already running
    site = db.query(models.Site).filter(models.Site.id == request.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Check DB status, not in-memory state
    if site.backup_status == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Backup already running for {site.name}"
        )
    
    logger.info(f"Starting backup for {request.site_name} (ID: {request.site_id})")
    
    # Update site status immediately
    site.backup_status = "running"
    site.backup_progress = 0
    site.backup_started_at = datetime.utcnow()
    site.backup_message = "Initializing backup..."
    site.backup_error = None
    db.commit()
    
    # Run backup in background
    background_tasks.add_task(
        _run_real_backup,
        request.site_id,
        request.site_path,
        request.site_name,
    )
    
    return {
        "success": True,
        "message": f"Backup started for {request.site_name}",
        "status": "running",
        "site_id": request.site_id,
    }


@router.post("/backup/stop")
async def stop_backup(
    request: BackupStopRequest,
    db: Session = Depends(deps.get_db),
):
    """Stop a running backup for a specific site."""
    site = db.query(models.Site).filter(models.Site.id == request.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    if site.backup_status != "running":
        return {
            "success": True,
            "message": "No backup currently running for this site",
            "status": site.backup_status,
        }
    
    logger.info(f"Stopping backup for {site.name}")
    
    site.backup_status = "stopped"
    site.backup_message = "Backup stopped by user"
    db.commit()
    
    return {
        "success": True,
        "message": "Backup stop requested",
        "status": "stopped",
    }


@router.get("/backup/status/{site_id}")
async def get_backup_status(
    site_id: int,
    db: Session = Depends(deps.get_db),
):
    """Get backup status for a specific site."""
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    return {
        "site_id": site.id,
        "site_name": site.name,
        "status": site.backup_status,
        "progress": site.backup_progress,
        "message": site.backup_message,
        "error": site.backup_error,
        "started_at": site.backup_started_at.isoformat() if site.backup_started_at else None,
    }


@router.post("/backup/reset/{site_id}")
async def reset_backup_status(
    site_id: int,
    db: Session = Depends(deps.get_db),
):
    """Reset a stuck backup status to idle and clean up temp files."""
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Clean up any orphaned temp directories for this site
    cleanup_result = cleanup_orphaned_backup_dirs(site_id=site_id, max_age_hours=0)
    
    site.backup_status = "idle"
    site.backup_progress = 0
    site.backup_message = None
    site.backup_error = None
    db.commit()
    
    logger.info(f"Backup reset for {site.name}: cleaned {cleanup_result['cleaned_count']} temp dirs, freed {cleanup_result['total_freed_mb']} MB")
    
    return {
        "success": True,
        "message": f"Backup status reset to idle for {site.name}",
        "cleanup": {
            "dirs_removed": cleanup_result["cleaned_count"],
            "space_freed_mb": cleanup_result["total_freed_mb"],
        }
    }


@router.get("/health")
async def daemon_health(db: Session = Depends(deps.get_db)):
    """Health check endpoint."""
    # Count running backups from DB
    running_count = db.query(models.Site).filter(
        models.Site.backup_status == "running"
    ).count()
    
    return {
        "status": "healthy",
        "running_backups": running_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/backup/cleanup")
async def cleanup_backup_temps(
    max_age_hours: int = Query(default=24, ge=0, description="Only clean dirs older than this (0 = all)"),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Manually clean up orphaned backup temp directories.
    
    Use max_age_hours=0 to clean ALL backup temp dirs.
    """
    result = cleanup_orphaned_backup_dirs(max_age_hours=max_age_hours)
    
    logger.info(f"Manual cleanup by {current_user.email}: removed {result['cleaned_count']} dirs, freed {result['total_freed_mb']} MB")
    
    return {
        "success": True,
        "message": f"Cleaned up {result['cleaned_count']} orphaned backup directories",
        "cleaned_count": result["cleaned_count"],
        "space_freed_mb": result["total_freed_mb"],
        "space_freed_bytes": result["total_freed_bytes"],
        "errors": result["errors"] if result["errors"] else None,
    }

@router.get("/backup/stream/{site_id}")
async def stream_backup_progress(
    site_id: int,
    token: Optional[str] = Query(default=None, description="JWT token for SSE auth"),
    interval: int = Query(default=2, ge=1, le=30, description="Poll interval in seconds"),
    db: Session = Depends(deps.get_db),
):
    """
    Stream backup progress in real-time using Server-Sent Events (SSE).
    
    Polls the database for status updates at the specified interval.
    Automatically closes when backup completes or fails.
    
    Usage:
    ```javascript
    const token = 'your-jwt-token';
    const source = new EventSource(`/api/v1/daemon/backup/stream/1?token=${token}`);
    source.onmessage = (event) => {
      const progress = JSON.parse(event.data);
      console.log(`[${progress.status}] ${progress.progress}% - ${progress.message}`);
    };
    source.onerror = () => source.close();
    ```
    """
    # Require token query param for SSE
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide JWT token as ?token= query parameter."
        )
    
    # Verify token
    current_user = deps.verify_token_string(token, db)
    
    # Check site exists
    site = db.query(models.Site).filter(models.Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    async def event_generator():
        """Generator that yields backup status as SSE events."""
        from master.db.session import SessionLocal
        
        # Use a fresh session for polling
        poll_db = SessionLocal()
        start_time = time.time()
        
        try:
            yield f"data: {{\"event\": \"connected\", \"site_id\": {site_id}, \"message\": \"Streaming backup progress...\"}}\n\n"
            
            while True:
                try:
                    # Refresh site from DB
                    poll_db.expire_all()
                    site = poll_db.query(models.Site).filter(models.Site.id == site_id).first()
                    
                    if not site:
                        yield f"data: {{\"event\": \"error\", \"message\": \"Site not found\"}}\n\n"
                        break
                    
                    elapsed = int(time.time() - start_time)
                    
                    # Build progress event
                    progress_data = {
                        "event": "progress",
                        "site_id": site.id,
                        "site_name": site.name,
                        "status": site.backup_status or "idle",
                        "progress": site.backup_progress or 0,
                        "message": site.backup_message or "",
                        "error": site.backup_error,
                        "elapsed_seconds": elapsed,
                        "started_at": site.backup_started_at.isoformat() if site.backup_started_at else None,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                    
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    # Check terminal conditions
                    if site.backup_status in ["completed", "failed", "stopped", "idle"]:
                        # Give client time to receive final status
                        await asyncio.sleep(1)
                        yield f"data: {{\"event\": \"finished\", \"status\": \"{site.backup_status}\"}}\n\n"
                        break
                    
                    # Wait before next poll
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    yield f"data: {{\"event\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
                    await asyncio.sleep(interval)
        finally:
            poll_db.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
