"""
Log Management API Endpoints

Provides REST API access to application logs for monitoring and debugging.
All endpoints require super_admin role.
"""
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from master.api import deps
from master.db import models
from master.core.logging_config import get_log_dir, read_log_entries, list_log_files, get_logger

logger = get_logger(__name__)

router = APIRouter()


# Valid log file name pattern (security: prevent path traversal)
VALID_LOG_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+\.log(\.\d+)?$')


@router.get("")
async def get_logs(
    limit: int = Query(default=50, le=500, ge=1, description="Max entries to return"),
    level: Optional[str] = Query(default=None, description="Filter by level: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
    search: Optional[str] = Query(default=None, description="Search in message content"),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Get recent log entries from the JSON log file.
    
    Returns parsed log entries with filtering options.
    """
    entries = read_log_entries(
        log_file="app.json.log",
        limit=limit,
        level=level,
        search=search,
    )
    
    return {
        "entries": entries,
        "total": len(entries),
        "filters": {
            "level": level,
            "search": search,
        }
    }


@router.get("/files")
async def get_log_files(
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    List all available log files with their sizes and modification times.
    """
    files = list_log_files()
    log_dir = str(get_log_dir())
    
    return {
        "log_directory": log_dir,
        "files": files,
        "total": len(files),
    }


@router.get("/download/{filename}")
async def download_log_file(
    filename: str,
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Download a specific log file.
    
    Security: Only allows downloading files from the log directory.
    """
    # Security: Validate filename pattern
    if not VALID_LOG_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename format")
    
    log_dir = get_log_dir()
    file_path = log_dir / filename
    
    # Security: Ensure the resolved path is still within log_dir
    try:
        file_path = file_path.resolve()
        if not str(file_path).startswith(str(log_dir.resolve())):
            raise HTTPException(status_code=400, detail="Invalid path")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    
    logger.info(f"Log file downloaded: {filename} by {current_user.email}")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/plain",
    )


@router.get("/search")
async def search_logs(
    query: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(default=100, le=500, ge=1),
    level: Optional[str] = Query(default=None),
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Search through log entries by keyword.
    """
    entries = read_log_entries(
        log_file="app.json.log",
        limit=limit,
        level=level,
        search=query,
    )
    
    return {
        "query": query,
        "entries": entries,
        "total": len(entries),
    }


@router.get("/stream")
async def stream_logs(
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Stream new log entries in real-time using Server-Sent Events (SSE).
    
    Connect using EventSource API in browser:
    ```javascript
    const source = new EventSource('/api/v1/logs/stream', {
        headers: {'Authorization': 'Bearer <token>'}
    });
    source.onmessage = (event) => console.log(JSON.parse(event.data));
    ```
    """
    log_file = get_log_dir() / "app.json.log"
    
    async def event_generator():
        """Generator that yields new log lines as SSE events."""
        last_position = 0
        
        # Get initial file position (end of file)
        if log_file.exists():
            last_position = log_file.stat().st_size
        
        yield f"data: {{'event': 'connected', 'message': 'Streaming logs...'}}\n\n"
        
        while True:
            try:
                if log_file.exists():
                    current_size = log_file.stat().st_size
                    
                    # File was rotated (size decreased)
                    if current_size < last_position:
                        last_position = 0
                    
                    # New content available
                    if current_size > last_position:
                        with open(log_file, 'r', encoding='utf-8') as f:
                            f.seek(last_position)
                            new_lines = f.readlines()
                            last_position = f.tell()
                        
                        for line in new_lines:
                            line = line.strip()
                            if line:
                                # Escape for SSE format
                                yield f"data: {line}\n\n"
                
                # Poll interval
                await asyncio.sleep(1)
                
            except Exception as e:
                yield f"data: {{'event': 'error', 'message': '{str(e)}'}}\n\n"
                await asyncio.sleep(5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/levels")
async def get_log_levels(
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Get available log levels and current configuration.
    """
    import logging
    current_level = logging.getLogger().level
    
    return {
        "current_level": logging.getLevelName(current_level),
        "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    }


@router.get("/stats")
async def get_log_stats(
    current_user: models.User = Depends(deps.get_current_superuser),
):
    """
    Get log statistics (file sizes, entry counts by level).
    """
    files = list_log_files()
    total_size = sum(f["size_bytes"] for f in files)
    
    # Count entries by level from recent logs
    entries = read_log_entries(limit=1000)
    level_counts = {}
    for entry in entries:
        level = entry.get("level", "UNKNOWN")
        level_counts[level] = level_counts.get(level, 0) + 1
    
    return {
        "file_count": len(files),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "recent_entries_by_level": level_counts,
        "log_directory": str(get_log_dir()),
    }
