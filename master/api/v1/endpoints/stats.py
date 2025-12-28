from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
from datetime import datetime

router = APIRouter()

def get_node_by_api_key(
    x_api_key: str = Header(...),
    db: Session = Depends(deps.get_db)
) -> models.Node:
    node = db.query(models.Node).filter(models.Node.api_key == x_api_key).first()
    if not node:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return node

@router.post("/", response_model=dict)
def report_stats(
    *,
    db: Session = Depends(deps.get_db),
    stats_in: schemas.NodeStatsBase,
    node: models.Node = Depends(get_node_by_api_key)
) -> Any:
    """
    Receive stats from a node (Auth via X-API-KEY header).
    """
    # Record stats
    stats = models.NodeStats(
        node_id=node.id,
        cpu_usage=stats_in.cpu_usage,
        disk_usage=stats_in.disk_usage,
        active_backups=stats_in.active_backups,
        timestamp=datetime.utcnow()
    )
    db.add(stats)
    
    # Cleanup old stats (Keep last 5 minutes roughly, or last 10 records)
    # This prevents the table from growing indefinitely since we only need real-time data.
    # subquery to find IDs to keep?
    # Simple approach: Delete < (now - 10 minutes)
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    db.query(models.NodeStats).filter(
        models.NodeStats.node_id == node.id,
        models.NodeStats.timestamp < cutoff
    ).delete()
    
    db.commit()
    
    return {"status": "recorded", "node": node.hostname}
