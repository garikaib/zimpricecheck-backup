from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from master import schemas
from master.api import deps
from master.db import models
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
