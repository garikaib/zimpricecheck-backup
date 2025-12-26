"""
Jobs API Endpoint

Provides REST API for job management.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from master.api import deps
from master.db import models
from daemon.job_queue import get_job_queue, JobStatus, BackupJob
from daemon.modules.base import get_module, list_modules

router = APIRouter()


# --- Schemas ---

class JobCreateRequest(BaseModel):
    module: str  # "wordpress", "mongodb", etc.
    target_id: int  # site_id, database_id, etc.
    target_name: str
    priority: int = 0


class StageResultResponse(BaseModel):
    status: str
    message: str


class JobResponse(BaseModel):
    id: str
    module: str
    target_id: int
    target_name: str
    status: str
    priority: int
    stages: List[str]
    current_stage: Optional[str]
    stage_results: dict
    progress_percent: int
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


class ModuleListResponse(BaseModel):
    modules: List[str]


# --- Endpoints ---

@router.get("/modules", response_model=ModuleListResponse)
def list_available_modules(
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List available backup modules.
    """
    return {"modules": list_modules()}


@router.get("/", response_model=JobListResponse)
def list_jobs(
    status: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 50,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    List all backup jobs with optional filters.
    """
    queue = get_job_queue()
    
    job_status = JobStatus(status) if status else None
    jobs = queue.list_jobs(status=job_status, module=module, limit=limit)
    
    return {
        "jobs": [j.to_dict() for j in jobs],
        "total": len(jobs),
    }


@router.post("/", response_model=JobResponse)
async def create_job(
    job_in: JobCreateRequest,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Create a new backup job.
    """
    # Validate module exists
    module = get_module(job_in.module)
    if not module:
        raise HTTPException(status_code=400, detail=f"Unknown module: {job_in.module}")
    
    queue = get_job_queue()
    job = queue.create_job(
        module=job_in.module,
        target_id=job_in.target_id,
        target_name=job_in.target_name,
        stages=module.get_stages(),
        priority=job_in.priority,
    )
    
    return job.to_dict()


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Get job details and progress.
    """
    queue = get_job_queue()
    job = queue.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.to_dict()


@router.delete("/{job_id}")
def cancel_job(
    job_id: str,
    current_user: models.User = Depends(deps.get_current_node_admin_or_higher),
) -> Any:
    """
    Cancel a pending or running job.
    """
    queue = get_job_queue()
    
    if not queue.get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    if queue.cancel_job(job_id):
        return {"status": "cancelled", "job_id": job_id}
    
    raise HTTPException(status_code=400, detail="Job cannot be cancelled")
