"""
Node Metrics API Endpoints

Provides REST API access to node system metrics for monitoring.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from master.api import deps
from master.db import models
from master.core.logging_config import get_logger

# Import metrics collector
try:
    from daemon.node_metrics import get_system_metrics, get_disk_details, PSUTIL_AVAILABLE
except ImportError:
    PSUTIL_AVAILABLE = False
    def get_system_metrics():
        return {"error": "Metrics module not available", "psutil_available": False}
    def get_disk_details():
        return {"error": "Metrics module not available"}

logger = get_logger(__name__)

router = APIRouter()


@router.get("/node")
async def get_node_metrics(
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Get current node system metrics.
    
    Returns CPU, memory, disk, and network usage statistics.
    """
    metrics = get_system_metrics()
    return metrics


@router.get("/disk")
async def get_disk_usage(
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Get detailed disk usage information for all partitions.
    """
    return get_disk_details()


@router.get("/node/stream")
async def stream_node_metrics(
    token: Optional[str] = Query(default=None, description="JWT token for SSE auth"),
    interval: int = Query(default=5, ge=1, le=60, description="Update interval in seconds"),
    db: Session = Depends(deps.get_db),
):
    """
    Stream node metrics in real-time using Server-Sent Events (SSE).
    
    Updates at the specified interval (default 5 seconds).
    
    Usage:
    ```javascript
    const token = 'your-jwt-token';
    const source = new EventSource(`/api/v1/metrics/node/stream?token=${token}&interval=5`);
    source.onmessage = (event) => {
      const metrics = JSON.parse(event.data);
      console.log('CPU:', metrics.cpu.usage_percent + '%');
    };
    ```
    """
    import json
    
    # Require token query param for SSE
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide JWT token as ?token= query parameter."
        )
    
    # Verify token
    current_user = deps.verify_token_string(token, db)
    
    # Check at least node admin role
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.NODE_ADMIN]:
        raise HTTPException(status_code=403, detail="Node admin access required")
    
    async def event_generator():
        """Generator that yields metrics as SSE events."""
        yield f"data: {{\"event\": \"connected\", \"message\": \"Streaming metrics every {interval}s\", \"user\": \"{current_user.email}\"}}\n\n"
        
        while True:
            try:
                metrics = get_system_metrics()
                yield f"data: {json.dumps(metrics)}\n\n"
                await asyncio.sleep(interval)
            except Exception as e:
                yield f"data: {{\"event\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
                await asyncio.sleep(interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/summary")
async def get_metrics_summary(
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
):
    """
    Get a simplified metrics summary suitable for dashboard display.
    """
    metrics = get_system_metrics()
    
    # Extract key metrics for dashboard
    cpu = metrics.get("cpu", {})
    memory = metrics.get("memory", {})
    disks = metrics.get("disks", [])
    
    # Find root and /var/www disk
    root_disk = next((d for d in disks if d.get("path") == "/"), {})
    www_disk = next((d for d in disks if d.get("path") == "/var/www"), root_disk)
    
    return {
        "timestamp": metrics.get("timestamp"),
        "hostname": metrics.get("hostname"),
        "uptime_seconds": metrics.get("uptime_seconds"),
        "cpu_percent": cpu.get("usage_percent", 0),
        "load_average": cpu.get("load_avg_1min", 0),
        "memory_percent": memory.get("percent_used", 0),
        "memory_available_gb": round(memory.get("available_bytes", 0) / (1024**3), 2),
        "disk_percent": www_disk.get("percent_used", root_disk.get("percent_used", 0)),
        "disk_free_gb": round(www_disk.get("free_bytes", root_disk.get("free_bytes", 0)) / (1024**3), 2),
        "backup_running": metrics.get("backup_process") is not None,
        "psutil_available": metrics.get("psutil_available", False),
    }


# ============================================================================
# UNIFIED NODE STATS STREAMING
# ============================================================================

def _get_local_node_stats():
    """Get stats for the local (Master) node using psutil."""
    metrics = get_system_metrics()
    cpu = metrics.get("cpu", {})
    memory = metrics.get("memory", {})
    disks = metrics.get("disks", [])
    root_disk = next((d for d in disks if d.get("path") == "/"), {})
    
    return {
        "cpu_percent": cpu.get("usage_percent", 0),
        "memory_percent": memory.get("percent_used", 0),
        "disk_percent": root_disk.get("percent_used", 0),
        "uptime_seconds": metrics.get("uptime_seconds", 0),
        "network": metrics.get("network", {}),
        "psutil_available": metrics.get("psutil_available", False),
    }


def _get_remote_node_stats(db: Session, node_id: int):
    """Get stats for a remote node from the database."""
    from datetime import datetime, timedelta
    
    latest = db.query(models.NodeStats).filter(
        models.NodeStats.node_id == node_id
    ).order_by(models.NodeStats.timestamp.desc()).first()
    
    if not latest:
        return None
    
    # Check freshness (consider stale if > 5 minutes old)
    age = datetime.utcnow() - latest.timestamp
    is_stale = age > timedelta(minutes=5)
    
    return {
        "cpu_percent": latest.cpu_usage,
        "memory_percent": None,  # Not tracked in current schema
        "disk_percent": latest.disk_usage,
        "active_backups": latest.active_backups,
        "last_seen": latest.timestamp.isoformat() + "Z",
        "is_stale": is_stale,
    }


def _get_master_node_id(db: Session) -> int:
    """Identify the Master node by matching hostname."""
    import socket
    local_hostname = socket.gethostname()
    
    # Also check common variations
    from master.db.models import Node
    
    # Try exact match first
    node = db.query(Node).filter(Node.hostname == local_hostname).first()
    if node:
        return node.id
    
    # Try with domain suffix
    for suffix in ["", ".local", ".zimpricecheck.com"]:
        node = db.query(Node).filter(Node.hostname == local_hostname + suffix).first()
        if node:
            return node.id
    
    # Fallback: check if any node has 127.0.0.1 IP
    node = db.query(Node).filter(Node.ip_address == "127.0.0.1").first()
    if node:
        return node.id
    
    return -1  # Not found


@router.get("/nodes/stats/stream")
async def stream_all_nodes_stats(
    token: Optional[str] = Query(default=None, description="JWT token for SSE auth"),
    interval: int = Query(default=5, ge=1, le=60, description="Update interval in seconds"),
    db: Session = Depends(deps.get_db),
):
    """
    Stream real-time stats for ALL nodes in a unified format.
    
    Combines:
    - Master node: Live psutil metrics
    - Remote nodes: Stats from database (pushed by daemons)
    
    Usage:
    ```javascript
    const source = new EventSource(`/api/v1/metrics/nodes/stats/stream?token=${token}`);
    source.onmessage = (event) => {
      const data = JSON.parse(event.data);
      data.nodes.forEach(node => console.log(node.hostname, node.cpu_percent));
    };
    ```
    """
    import json
    from datetime import datetime
    
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    
    current_user = deps.verify_token_string(token, db)
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.NODE_ADMIN]:
        raise HTTPException(status_code=403, detail="Node admin access required")
    
    master_node_id = _get_master_node_id(db)
    
    async def event_generator():
        yield f'data: {{"event": "connected", "message": "Streaming all nodes stats every {interval}s"}}\n\n'
        
        while True:
            try:
                nodes = db.query(models.Node).filter(
                    models.Node.status == "active"
                ).all()
                
                result = []
                for node in nodes:
                    if node.id == master_node_id:
                        # Local/Master node - use psutil
                        local_stats = _get_local_node_stats()
                        result.append({
                            "id": node.id,
                            "hostname": node.hostname,
                            "status": "online",
                            "is_master": True,
                            "cpu_percent": local_stats["cpu_percent"],
                            "memory_percent": local_stats["memory_percent"],
                            "disk_percent": local_stats["disk_percent"],
                            "uptime_seconds": local_stats["uptime_seconds"],
                            "active_backups": 0,  # TODO: Track locally
                            "last_seen": None,
                        })
                    else:
                        # Remote node - use DB
                        remote_stats = _get_remote_node_stats(db, node.id)
                        if remote_stats:
                            result.append({
                                "id": node.id,
                                "hostname": node.hostname,
                                "status": "stale" if remote_stats.get("is_stale") else "online",
                                "is_master": False,
                                "cpu_percent": remote_stats["cpu_percent"],
                                "memory_percent": remote_stats.get("memory_percent"),
                                "disk_percent": remote_stats["disk_percent"],
                                "uptime_seconds": None,
                                "active_backups": remote_stats.get("active_backups", 0),
                                "last_seen": remote_stats["last_seen"],
                            })
                        else:
                            result.append({
                                "id": node.id,
                                "hostname": node.hostname,
                                "status": "offline",
                                "is_master": False,
                                "cpu_percent": None,
                                "memory_percent": None,
                                "disk_percent": None,
                                "uptime_seconds": None,
                                "active_backups": None,
                                "last_seen": None,
                            })
                
                payload = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "nodes": result,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Stats stream error: {e}")
                yield f'data: {{"event": "error", "message": "{str(e)}"}}\n\n'
                await asyncio.sleep(interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/nodes/{node_id}/stats/stream")
async def stream_single_node_stats(
    node_id: int,
    token: Optional[str] = Query(default=None, description="JWT token for SSE auth"),
    interval: int = Query(default=5, ge=1, le=60, description="Update interval in seconds"),
    db: Session = Depends(deps.get_db),
):
    """
    Stream real-time stats for a SINGLE node.
    
    Useful for node detail modals or focused monitoring.
    """
    import json
    from datetime import datetime
    
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    
    current_user = deps.verify_token_string(token, db)
    if current_user.role not in [models.UserRole.SUPER_ADMIN, models.UserRole.NODE_ADMIN]:
        raise HTTPException(status_code=403, detail="Node admin access required")
    
    node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    master_node_id = _get_master_node_id(db)
    is_master = (node.id == master_node_id)
    
    async def event_generator():
        yield f'data: {{"event": "connected", "node_id": {node_id}, "hostname": "{node.hostname}"}}\n\n'
        
        while True:
            try:
                if is_master:
                    stats = _get_local_node_stats()
                    payload = {
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "id": node.id,
                        "hostname": node.hostname,
                        "status": "online",
                        "is_master": True,
                        **stats,
                    }
                else:
                    remote_stats = _get_remote_node_stats(db, node.id)
                    if remote_stats:
                        payload = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "id": node.id,
                            "hostname": node.hostname,
                            "status": "stale" if remote_stats.get("is_stale") else "online",
                            "is_master": False,
                            **remote_stats,
                        }
                    else:
                        payload = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "id": node.id,
                            "hostname": node.hostname,
                            "status": "offline",
                            "is_master": False,
                        }
                
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(interval)
                
            except Exception as e:
                yield f'data: {{"event": "error", "message": "{str(e)}"}}\n\n'
                await asyncio.sleep(interval)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
