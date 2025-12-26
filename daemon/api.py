"""
Daemon API

FastAPI router for daemon-specific endpoints (scan, backup control).
This runs on nodes to receive commands from the master.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from daemon.scanner import scan_for_wordpress_sites, site_to_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daemon", tags=["daemon"])


# In-memory backup state (for single-node simplicity)
_backup_state: Dict[str, Any] = {
    "status": "idle",  # idle, scanning, running, completed, failed
    "progress": 0,
    "current_site": None,
    "started_at": None,
    "completed_at": None,
    "error": None,
    "message": None,
}


class ScanRequest(BaseModel):
    base_path: str = "/var/www"


class BackupStartRequest(BaseModel):
    site_path: str
    site_name: str
    simulate: bool = False  # For testing without real backup


class BackupStopRequest(BaseModel):
    force: bool = False


# ============== Scan Endpoints ==============

@router.get("/scan")
async def scan_sites(base_path: str = "/var/www"):
    """
    Scan for WordPress sites in the given base path.
    Returns list of discovered sites.
    """
    logger.info(f"Scanning for WordPress sites in {base_path}")
    
    global _backup_state
    _backup_state["status"] = "scanning"
    _backup_state["message"] = f"Scanning {base_path}..."
    
    try:
        sites = scan_for_wordpress_sites(base_path)
        result = [site_to_dict(site) for site in sites]
        
        _backup_state["status"] = "idle"
        _backup_state["message"] = f"Found {len(sites)} WordPress sites"
        
        return {
            "success": True,
            "sites": result,
            "total": len(result),
            "scanned_path": base_path,
        }
    except Exception as e:
        _backup_state["status"] = "idle"
        _backup_state["error"] = str(e)
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Backup Control Endpoints ==============

async def _run_simulated_backup(site_path: str, site_name: str):
    """Simulate a backup for testing purposes."""
    global _backup_state
    
    try:
        _backup_state["status"] = "running"
        _backup_state["current_site"] = site_name
        _backup_state["started_at"] = datetime.utcnow().isoformat()
        _backup_state["error"] = None
        
        stages = [
            ("Preparing backup", 10),
            ("Backing up database", 30),
            ("Backing up files", 60),
            ("Creating archive", 80),
            ("Uploading to remote", 95),
            ("Cleaning up", 100),
        ]
        
        for stage_name, progress in stages:
            if _backup_state["status"] != "running":
                logger.info(f"Backup stopped at stage: {stage_name}")
                return
            
            _backup_state["message"] = stage_name
            _backup_state["progress"] = progress
            logger.info(f"[SIMULATE] {site_name}: {stage_name} ({progress}%)")
            await asyncio.sleep(2)  # Simulate work
        
        _backup_state["status"] = "completed"
        _backup_state["completed_at"] = datetime.utcnow().isoformat()
        _backup_state["message"] = "Backup completed successfully"
        logger.info(f"[SIMULATE] Backup completed for {site_name}")
        
    except Exception as e:
        _backup_state["status"] = "failed"
        _backup_state["error"] = str(e)
        logger.error(f"Backup failed: {e}")


@router.post("/backup/start")
async def start_backup(
    request: BackupStartRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a backup for the specified site.
    Returns immediately, backup runs in background.
    """
    global _backup_state
    
    if _backup_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Backup already running for {_backup_state['current_site']}"
        )
    
    logger.info(f"Starting backup for {request.site_name} at {request.site_path}")
    
    if request.simulate:
        # Run simulated backup
        background_tasks.add_task(
            _run_simulated_backup,
            request.site_path,
            request.site_name,
        )
    else:
        # TODO: Implement real backup using existing wordpress module
        background_tasks.add_task(
            _run_simulated_backup,  # For now, use simulated
            request.site_path,
            request.site_name,
        )
    
    _backup_state["status"] = "running"
    _backup_state["current_site"] = request.site_name
    _backup_state["progress"] = 0
    _backup_state["message"] = "Backup starting..."
    
    return {
        "success": True,
        "message": f"Backup started for {request.site_name}",
        "status": "running",
    }


@router.post("/backup/stop")
async def stop_backup(request: BackupStopRequest = None):
    """Stop the currently running backup."""
    global _backup_state
    
    if _backup_state["status"] != "running":
        return {
            "success": True,
            "message": "No backup currently running",
            "status": _backup_state["status"],
        }
    
    logger.info(f"Stopping backup for {_backup_state['current_site']}")
    
    _backup_state["status"] = "stopped"
    _backup_state["message"] = "Backup stopped by user"
    
    return {
        "success": True,
        "message": "Backup stop requested",
        "status": "stopped",
    }


@router.get("/backup/status")
async def get_backup_status():
    """Get current backup status."""
    return _backup_state


@router.get("/health")
async def daemon_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "backup_status": _backup_state["status"],
        "timestamp": datetime.utcnow().isoformat(),
    }
