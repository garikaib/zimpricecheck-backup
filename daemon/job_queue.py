"""
Job Queue

Manages backup jobs with stage-based progress tracking.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    status: StageStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0


@dataclass
class BackupJob:
    id: str
    module: str  # "wordpress", "mongodb", etc.
    target_id: int  # site_id, database_id, etc.
    target_name: str  # human readable
    status: JobStatus = JobStatus.PENDING
    priority: int = 0  # higher = more important
    
    # Stage tracking
    stages: List[str] = field(default_factory=list)
    current_stage: Optional[str] = None
    stage_results: Dict[str, StageResult] = field(default_factory=dict)
    
    # Progress
    progress_percent: int = 0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Errors
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "module": self.module,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "status": self.status.value,
            "priority": self.priority,
            "stages": self.stages,
            "current_stage": self.current_stage,
            "stage_results": {
                k: {"status": v.status.value, "message": v.message}
                for k, v in self.stage_results.items()
            },
            "progress_percent": self.progress_percent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class JobQueue:
    """
    Priority-based job queue with stage progress tracking.
    """
    
    def __init__(self):
        self._jobs: Dict[str, BackupJob] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._callbacks: List[Callable[[BackupJob], None]] = []
    
    def create_job(
        self,
        module: str,
        target_id: int,
        target_name: str,
        stages: List[str],
        priority: int = 0,
    ) -> BackupJob:
        """Create a new backup job and add to queue."""
        job = BackupJob(
            id=str(uuid.uuid4()),
            module=module,
            target_id=target_id,
            target_name=target_name,
            stages=stages,
            priority=priority,
        )
        
        self._jobs[job.id] = job
        # Priority queue uses (priority, timestamp, job_id) for ordering
        # Negate priority so higher values come first
        self._queue.put_nowait((-priority, datetime.utcnow().timestamp(), job.id))
        
        logger.info(f"Created job {job.id} for {module}:{target_name}")
        self._notify_callbacks(job)
        
        return job
    
    def get_job(self, job_id: str) -> Optional[BackupJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        module: Optional[str] = None,
        limit: int = 50,
    ) -> List[BackupJob]:
        """List jobs with optional filters."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        if module:
            jobs = [j for j in jobs if j.module == module]
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
    
    async def get_next_job(self) -> Optional[BackupJob]:
        """Get next job from queue (blocks until one is available)."""
        try:
            _, _, job_id = await asyncio.wait_for(self._queue.get(), timeout=5.0)
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PENDING:
                return job
            return None
        except asyncio.TimeoutError:
            return None
    
    def update_job_stage(
        self,
        job_id: str,
        stage: str,
        result: StageResult,
    ):
        """Update job with stage result."""
        job = self._jobs.get(job_id)
        if not job:
            return
        
        job.stage_results[stage] = result
        
        if result.status == StageStatus.COMPLETED:
            completed = len([r for r in job.stage_results.values() if r.status == StageStatus.COMPLETED])
            job.progress_percent = int((completed / len(job.stages)) * 100)
        
        if result.status == StageStatus.FAILED:
            job.status = JobStatus.FAILED
            job.error_message = result.message
            job.completed_at = datetime.utcnow()
        
        self._notify_callbacks(job)
    
    def start_job(self, job_id: str):
        """Mark job as running."""
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            self._notify_callbacks(job)
    
    def complete_job(self, job_id: str, success: bool = True, error: str = None):
        """Mark job as completed or failed."""
        job = self._jobs.get(job_id)
        if job:
            job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.progress_percent = 100 if success else job.progress_percent
            if error:
                job.error_message = error
            self._notify_callbacks(job)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            self._notify_callbacks(job)
            return True
        
        if job.status == JobStatus.RUNNING:
            task = self._running_jobs.get(job_id)
            if task:
                task.cancel()
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            self._notify_callbacks(job)
            return True
        
        return False
    
    def add_callback(self, callback: Callable[[BackupJob], None]):
        """Add callback for job updates (for SSE, WebSocket, etc.)."""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, job: BackupJob):
        """Notify all callbacks of job update."""
        for callback in self._callbacks:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Callback error: {e}")


# Global instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
