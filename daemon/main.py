"""
Backupd - Modular Backup Daemon

Entry point for the backup daemon. Runs in master or node mode.

Usage:
    python -m daemon.main                    # Auto-detect mode
    python -m daemon.main --mode master      # Force master mode
    python -m daemon.main --mode node --master-url https://master.example.com
"""
import asyncio
import argparse
import logging
import signal
import sys
import os
from typing import Optional

from daemon.config import load_config, DaemonMode, DaemonConfig
from daemon.resource_manager import init_resource_manager, ResourceLimits, get_resource_manager
from daemon.job_queue import get_job_queue, JobStatus
from daemon.modules.base import get_module, list_modules, BackupContext

# Import modules to register them
import daemon.modules.wordpress  # noqa

# Import StageStatus for run_job
from daemon.job_queue import StageStatus

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging for the daemon."""
    import logging.handlers
    
    # Create log directory
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
        
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root_logger.addHandler(console)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "backupd.log"),
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


class BackupDaemon:
    """
    Main daemon class.
    
    In master mode: Runs FastAPI server + scheduler
    In node mode: Pulls jobs from master, executes backups
    """
    
    def __init__(self, config: DaemonConfig):
        self.config = config
        self.running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the daemon."""
        self.running = True
        
        # Initialize resource manager
        init_resource_manager(ResourceLimits(
            max_io_concurrent=self.config.max_io_concurrent,
            max_network_concurrent=self.config.max_network_concurrent,
        ))
        
        logger.info(f"Starting backupd in {self.config.mode.value} mode")
        logger.info(f"Registered modules: {list_modules()}")
        
        if self.config.mode == DaemonMode.MASTER:
            await self._run_master()
        elif self.config.mode == DaemonMode.NODE:
            await self._run_node()
        else:
            logger.warning("Daemon is unconfigured. Waiting for setup via API...")
            await self._run_master()  # Run API for configuration
    
    async def _run_master(self):
        """
        Run in master mode.
        
        Starts the FastAPI server with existing master/ API.
        Also runs the scheduler for defined backup schedules.
        """
        import uvicorn
        
        # Import the existing FastAPI app
        from master.main import app
        
        # Create uvicorn config
        uvi_config = uvicorn.Config(
            app,
            host=self.config.api_host,
            port=self.config.api_port,
            log_level="info",
        )
        server = uvicorn.Server(uvi_config)
        
        # Run server
        await server.serve()
    
    async def _run_node(self):
        """
        Run in node mode.
        
        - Polls master for pending jobs
        - Executes backup jobs
        - Reports status back to master
        """
        logger.info(f"Node mode: Master URL = {self.config.master_url}")
        
        if not self.config.node_api_key:
            logger.error("No API key configured. Generate one on the master server.")
            return
        
        while self.running and not self._shutdown_event.is_set():
            try:
                # Pull jobs from master
                # TODO: Implement job fetching from master API
                
                await asyncio.sleep(30)  # Poll every 30 seconds
                
            except Exception as e:
                logger.error(f"Node loop error: {e}")
                await asyncio.sleep(60)
    
    async def run_job(self, job_id: str):
        """Execute a backup job."""
        queue = get_job_queue()
        job = queue.get_job(job_id)
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        module = get_module(job.module)
        if not module:
            logger.error(f"Module {job.module} not found")
            queue.complete_job(job_id, success=False, error=f"Module {job.module} not found")
            return
        
        queue.start_job(job_id)
        logger.info(f"Starting job {job_id} ({job.module}:{job.target_name})")
        
        # Create context
        context = BackupContext(
            job_id=job.id,
            target_id=job.target_id,
            target_name=job.target_name,
            config={},  # TODO: Load from database
        )
        
        # Execute stages
        resource_manager = get_resource_manager()
        
        for stage in module.get_stages():
            job.current_stage = stage
            logger.info(f"Job {job_id}: Executing stage {stage}")
            
            try:
                # Acquire appropriate resources based on stage
                if stage in ["backup_db", "backup_files", "create_bundle"]:
                    async with resource_manager.acquire_io():
                        result = await module.execute_stage(stage, context)
                elif stage == "upload_remote":
                    async with resource_manager.acquire_network():
                        result = await module.execute_stage(stage, context)
                else:
                    result = await module.execute_stage(stage, context)
                
                queue.update_job_stage(job_id, stage, result)
                
                if result.status == StageStatus.FAILED:
                    logger.error(f"Job {job_id}: Stage {stage} failed: {result.message}")
                    queue.complete_job(job_id, success=False, error=result.message)
                    return
                
            except Exception as e:
                logger.exception(f"Job {job_id}: Stage {stage} exception")
                queue.complete_job(job_id, success=False, error=str(e))
                return
        
        queue.complete_job(job_id, success=True)
        logger.info(f"Job {job_id} completed successfully")
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down backupd...")
        self.running = False
        self._shutdown_event.set()
        
        # Shutdown resource manager
        get_resource_manager().shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backupd - Modular Backup Daemon")
    parser.add_argument(
        "--mode",
        choices=["master", "node"],
        help="Force daemon mode (default: auto-detect)",
    )
    parser.add_argument(
        "--master-url",
        help="Master server URL (node mode only)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port (master mode only)",
    )
    args = parser.parse_args()
    
    # Configure logging locally for node (master module not available on nodes)
    setup_logging()
    
    # Load config
    config = load_config()
    
    # Override with CLI args
    if args.mode:
        config.mode = DaemonMode(args.mode)
    if args.master_url:
        config.master_url = args.master_url
    if args.port:
        config.api_port = args.port
    
    # Create daemon
    daemon = BackupDaemon(config)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        asyncio.create_task(daemon.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
