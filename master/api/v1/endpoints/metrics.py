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
