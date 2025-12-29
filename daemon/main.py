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
    
    async def _report_stats_loop(self):
        """Periodically report system stats to master."""
        import httpx
        try:
            from daemon.node_metrics import get_system_metrics
        except ImportError:
            logger.error("Failed to import node_metrics. Stats reporting disabled.")
            return

        logger.info("Starting stats reporting loop")
        while self.running and not self._shutdown_event.is_set():
            try:
                metrics = get_system_metrics()
                
                # Calculate active backups (local queue)
                queue = get_job_queue()
                active_count = len(queue.list_jobs(status=JobStatus.RUNNING))
                
                # Disk usage: use highest usage partition
                disk_percent = 0
                if metrics.get("disks"):
                    disk_percent = max([d.get("percent_used", 0) for d in metrics["disks"]])
                
                stats_payload = {
                    "cpu_usage": int(metrics["cpu"]["usage_percent"]),
                    "disk_usage": int(disk_percent),
                    "active_backups": active_count
                }
                
                headers = {"X-API-KEY": self.config.node_api_key}
                # Ensure URL has correct path
                base_url = self.config.master_url.rstrip("/")
                url = f"{base_url}/stats/"
                
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=stats_payload, headers=headers, timeout=10.0)
                    if resp.status_code != 200:
                        logger.warning(f"Stats report failed: {resp.status_code} - {resp.text}")
                
            except Exception as e:
                logger.error(f"Failed to report stats: {e}")
            
            await asyncio.sleep(60) # Report every minute

    async def _run_node(self):
        """
        Run in node mode.
        
        If no API key: Request to join, display code, poll until approved.
        If API key: Start normal operation (poll for jobs, report stats).
        """
        logger.info(f"Node mode: Master URL = {self.config.master_url}")
        
        # If no API key, we need to register first
        if not self.config.node_api_key:
            logger.info("No API key found. Starting registration process...")
            api_key = await self._register_with_master()
            if not api_key:
                logger.error("Registration failed. Exiting.")
                return
            self.config.node_api_key = api_key
            # Save API key to config file for future runs
            self._save_api_key(api_key)
        
        # API key available, start normal operation
        logger.info("Node registered and active. Starting stats reporting and job polling.")
        
        # Start stats reporting in background
        asyncio.create_task(self._report_stats_loop())
        
        while self.running and not self._shutdown_event.is_set():
            try:
                # Pull jobs from master
                # TODO: Implement job fetching from master API
                
                await asyncio.sleep(30)  # Poll every 30 seconds
                
            except Exception as e:
                logger.error(f"Node loop error: {e}")
                await asyncio.sleep(60)
    
    async def _register_with_master(self) -> str:
        """
        Register this node with the master server.
        Returns the API key on success, None on failure.
        """
        import httpx
        import socket
        
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        
        logger.info(f"Requesting to join master as '{hostname}'...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Request to join
                resp = await client.post(
                    f"{self.config.master_url}/api/v1/nodes/join-request",
                    json={"hostname": hostname, "ip_address": ip_address},
                    timeout=30
                )
                
                if resp.status_code != 200:
                    logger.error(f"Join request failed: {resp.status_code} - {resp.text}")
                    return None
                
                data = resp.json()
                code = data.get("registration_code")
                
                if code == "ACTIVE":
                    logger.info("Node already registered and active.")
                    # Fetch API key if already active (edge case)
                    return None  # Will need manual key entry
                
                # Step 2: Display the code for admin
                print("\n" + "=" * 50)
                print(f"  REGISTRATION CODE: {code}")
                print("=" * 50)
                print(f"  Enter this code in the master dashboard")
                print(f"  to approve this node ({hostname})")
                print("=" * 50 + "\n")
                logger.info(f"Registration code: {code} - Waiting for admin approval...")
                
                # Step 3: Poll for approval (max 2 hours)
                start_time = __import__('time').time()
                while self.running and not self._shutdown_event.is_set():
                    # Check timeout (2 hours = 7200 seconds)
                    if __import__('time').time() - start_time > 7200:
                        logger.error("Registration timed out after 2 hours. Exiting.")
                        return None
                        
                    await asyncio.sleep(10)  # Poll every 10 seconds
                    
                    try:
                        status_resp = await client.get(
                            f"{self.config.master_url}/api/v1/nodes/status/code/{code}",
                            timeout=15
                        )
                        
                        if status_resp.status_code == 404:
                            logger.warning("Code no longer valid. May have been rejected.")
                            return None
                        
                        if status_resp.status_code == 200:
                            status_data = status_resp.json()
                            if status_data.get("status") == "active":
                                logger.info("Node approved by admin!")
                                return status_data.get("api_key")
                            else:
                                pass # Still pending
                    
                    except Exception as poll_err:
                        logger.warning(f"Poll error: {poll_err}")
                    
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return None
        
        return None
    
    def _save_api_key(self, api_key: str):
        """Save the API key to config file for persistence."""
        import os
        config_dir = "/etc/backupd"
        config_file = f"{config_dir}/config"
        
        try:
            os.makedirs(config_dir, exist_ok=True)
            
            # Read existing config or create new
            lines = []
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    lines = f.readlines()
            
            # Update or add API key
            key_line = f"api_key={api_key}\n"
            found = False
            for i, line in enumerate(lines):
                if line.startswith("api_key="):
                    lines[i] = key_line
                    found = True
                    break
            if not found:
                lines.append(key_line)
            
            with open(config_file, 'w') as f:
                f.writelines(lines)
            
            logger.info(f"API key saved to {config_file}")
            
        except Exception as e:
            logger.warning(f"Could not save API key to config: {e}")
            logger.info(f"Set BACKUPD_API_KEY={api_key} in environment instead.")
    
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
