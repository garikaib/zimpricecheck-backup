"""
Base Backup Module

Abstract base class for all backup modules (WordPress, MongoDB, etc.)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from daemon.job_queue import StageResult, StageStatus

logger = logging.getLogger(__name__)


@dataclass
class BackupContext:
    """Context passed to each backup stage."""
    job_id: str
    target_id: int
    target_name: str
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Working data shared between stages
    temp_dir: Optional[str] = None
    archive_path: Optional[str] = None
    remote_path: Optional[str] = None
    
    # For passing data between stages
    stage_data: Dict[str, Any] = field(default_factory=dict)
    
    # Progress tracking
    current_stage: str = ""
    stage_number: int = 0
    total_stages: int = 0
    bytes_processed: int = 0
    bytes_total: int = 0
    start_time: Optional[float] = None  # time.time() when backup started
    stage_start_time: Optional[float] = None
    
    # Callback for progress updates (optional)
    # Signature: callback(context, message: str)
    progress_callback: Optional[Any] = None
    
    def report_progress(self, message: str, bytes_delta: int = 0):
        """Report progress update."""
        self.bytes_processed += bytes_delta
        if self.progress_callback:
            try:
                self.progress_callback(self, message)
            except Exception:
                pass  # Don't let callback errors break backup


class BackupModule(ABC):
    """
    Abstract base class for backup modules.
    
    Each module must implement:
    - name: Module identifier
    - get_stages(): List of stage names
    - execute_stage(): Execute a single stage
    - get_config_schema(): JSON schema for module config
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return module name (e.g., 'wordpress', 'mongodb')."""
        pass
    
    @abstractmethod
    def get_stages(self) -> List[str]:
        """
        Return ordered list of stage names.
        
        Example: ["backup_db", "backup_files", "create_bundle", "upload_remote", "cleanup"]
        """
        pass
    
    @abstractmethod
    async def execute_stage(
        self,
        stage: str,
        context: BackupContext,
    ) -> StageResult:
        """
        Execute a single backup stage.
        
        Args:
            stage: Stage name to execute
            context: Shared context with config and working data
        
        Returns:
            StageResult with status, message, and optional details
        """
        pass
    
    @abstractmethod
    def get_config_schema(self) -> dict:
        """
        Return JSON schema for module-specific configuration.
        
        Example for WordPress:
        {
            "db_user": {"type": "string", "required": True},
            "db_password": {"type": "string", "required": True},
            "wp_path": {"type": "string", "required": True},
        }
        """
        pass
    
    def validate_config(self, config: dict) -> tuple[bool, List[str]]:
        """
        Validate configuration against schema.
        
        Returns (is_valid, error_messages)
        """
        schema = self.get_config_schema()
        errors = []
        
        for key, spec in schema.items():
            if spec.get("required") and key not in config:
                errors.append(f"Missing required config: {key}")
        
        return len(errors) == 0, errors


# Registry of available modules
_modules: Dict[str, BackupModule] = {}


def register_module(module: BackupModule):
    """Register a backup module."""
    _modules[module.name] = module
    logger.info(f"Registered backup module: {module.name}")


def get_module(name: str) -> Optional[BackupModule]:
    """Get a registered module by name."""
    return _modules.get(name)


def list_modules() -> List[str]:
    """List all registered module names."""
    return list(_modules.keys())
