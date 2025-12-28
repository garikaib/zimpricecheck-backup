"""
WordPress Backup Module

Implements stage-based WordPress site backup.
"""
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from typing import List
import logging
import asyncio
import boto3
from botocore.exceptions import ClientError

from daemon.modules.base import BackupModule, BackupContext, register_module
from daemon.job_queue import StageResult, StageStatus

logger = logging.getLogger(__name__)


class WordPressModule(BackupModule):
    """
    WordPress backup module.
    
    Stages:
    1. backup_db - Dump MySQL database
    2. backup_files - Copy wp-content
    3. create_bundle - Create compressed archive
    4. upload_remote - Upload to storage provider
    5. cleanup - Remove temp files
    """
    
    @property
    def name(self) -> str:
        return "wordpress"
    
    def get_stages(self) -> List[str]:
        return [
            "backup_db",
            "backup_files",
            "create_bundle",
            "upload_remote",
            "cleanup",
        ]
    
    def get_config_schema(self) -> dict:
        return {
            "wp_path": {"type": "string", "required": True, "description": "WordPress installation path"},
            "db_name": {"type": "string", "required": True},
            "db_user": {"type": "string", "required": True},
            "db_password": {"type": "string", "required": True},
            "db_host": {"type": "string", "required": False, "default": "localhost"},
        }
    
    async def execute_stage(
        self,
        stage: str,
        context: BackupContext,
    ) -> StageResult:
        """Execute a WordPress backup stage."""
        start_time = time.monotonic()
        
        try:
            if stage == "backup_db":
                result = await self._backup_database(context)
            elif stage == "backup_files":
                result = await self._backup_files(context)
            elif stage == "create_bundle":
                result = await self._create_bundle(context)
            elif stage == "upload_remote":
                result = await self._upload_remote(context)
            elif stage == "cleanup":
                result = await self._cleanup(context)
            else:
                result = StageResult(
                    status=StageStatus.FAILED,
                    message=f"Unknown stage: {stage}",
                )
            
            result.duration_seconds = time.monotonic() - start_time
            return result
            
        except Exception as e:
            logger.exception(f"Stage {stage} failed for {context.target_name}")
            return StageResult(
                status=StageStatus.FAILED,
                message=str(e),
                duration_seconds=time.monotonic() - start_time,
            )
    
    async def _run_command(self, cmd: List[str], timeout: int = 3600, capture_output: bool = False, stdout=None) -> subprocess.CompletedProcess:
        """Run command in thread pool to prevent blocking asyncio loop."""
        loop = asyncio.get_event_loop()
        
        def _exec():
            return subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=capture_output,
                stdout=stdout,
                stderr=subprocess.PIPE if not capture_output else None  # Capture stderr if not capturing all output
            )
            
        return await loop.run_in_executor(None, _exec)

    async def _backup_database(self, context: BackupContext) -> StageResult:
        """Dump MySQL database using mysqldump."""
        config = context.config
        
        # Create temp directory for this backup
        context.temp_dir = tempfile.mkdtemp(prefix=f"backup_{context.target_id}_")
        sql_file = os.path.join(context.temp_dir, "database.sql")
        
        # Build mysqldump command
        cmd = [
            "mysqldump",
            "-h", config.get("db_host", "localhost"),
            "-u", config["db_user"],
            f"-p{config['db_password']}",
            "--single-transaction",
            "--quick",
            config["db_name"],
        ]
        
        logger.info(f"Dumping database {config['db_name']} for {context.target_name}")
        
        try:
            # Run in executor to avoid blocking
            # We need to handle file I/O safely with the executor
            loop = asyncio.get_event_loop()
            
            def _dump():
                with open(sql_file, "w") as f:
                    return subprocess.run(
                        cmd,
                        stdout=f,
                        stderr=subprocess.PIPE,
                        timeout=3600,
                    )
            
            result = await loop.run_in_executor(None, _dump)
            
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown error"
                return StageResult(
                    status=StageStatus.FAILED,
                    message=f"mysqldump failed: {error}",
                )
            
            size = os.path.getsize(sql_file)
            context.stage_data["db_size"] = size
            context.stage_data["sql_file"] = sql_file
            
            return StageResult(
                status=StageStatus.COMPLETED,
                message=f"Database dumped ({size / 1024 / 1024:.1f} MB)",
                details={"size_bytes": size},
            )
            
        except subprocess.TimeoutExpired:
            return StageResult(
                status=StageStatus.FAILED,
                message="Database dump timed out after 1 hour",
            )
    
    async def _backup_files(self, context: BackupContext) -> StageResult:
        """Copy wp-content directory."""
        config = context.config
        wp_path = config["wp_path"]
        wp_content = os.path.join(wp_path, "wp-content")
        
        if not os.path.exists(wp_content):
            return StageResult(
                status=StageStatus.FAILED,
                message=f"wp-content not found at {wp_content}",
            )
        
        # Copy to temp dir
        files_backup = os.path.join(context.temp_dir, "wp-content")
        
        logger.info(f"Copying wp-content for {context.target_name}")
        
        # Track skipped files due to permissions
        skipped_files = []
        
        def copy_with_permissions_handling(src, dst):
            """Copy function that handles permission errors gracefully."""
            try:
                shutil.copy2(src, dst)
            except PermissionError as e:
                skipped_files.append(src)
                logger.warning(f"Skipping unreadable file: {src}")
        
        def _copy_tree():
            # Use dirs_exist_ok=True for Python 3.8+ resilience
            shutil.copytree(
                wp_content,
                files_backup,
                symlinks=True,
                ignore=shutil.ignore_patterns("cache", "*.log", "wflogs"),
                copy_function=copy_with_permissions_handling,
                dirs_exist_ok=True,
            )
            
            # Calculate size
            total_size = 0
            for dirpath, _, filenames in os.walk(files_backup):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
            return total_size

        try:
            loop = asyncio.get_event_loop()
            total_size = await loop.run_in_executor(None, _copy_tree)
            
            context.stage_data["files_size"] = total_size
            context.stage_data["files_path"] = files_backup
            
            message = f"Files backed up ({total_size / 1024 / 1024:.1f} MB)"
            if skipped_files:
                message += f" - {len(skipped_files)} files skipped due to permissions"
            
            return StageResult(
                status=StageStatus.COMPLETED,
                message=message,
                details={"size_bytes": total_size, "skipped_count": len(skipped_files)},
            )
            
        except Exception as e:
            return StageResult(
                status=StageStatus.FAILED,
                message=f"File backup failed: {e}",
            )
    
    async def _create_bundle(self, context: BackupContext) -> StageResult:
        """Create compressed archive."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{context.target_name}_{timestamp}.tar.zst"
        archive_path = os.path.join(context.temp_dir, archive_name)
        
        logger.info(f"Creating archive {archive_name}")
        
        try:
            # Use zstandard compression
            cmd = [
                "tar",
                "-I", "zstd -T0",  # Multi-threaded zstd
                "-cf", archive_path,
                "-C", context.temp_dir,
                "database.sql",
                "wp-content",
            ]
            
            loop = asyncio.get_event_loop()
            
            # Helper to run subprocess in thread
            def _tar():
                return subprocess.run(cmd, capture_output=True, timeout=1800)
                
            result = await loop.run_in_executor(None, _tar)
            
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown error"
                return StageResult(
                    status=StageStatus.FAILED,
                    message=f"Archive creation failed: {error}",
                )
            
            size = os.path.getsize(archive_path)
            context.archive_path = archive_path
            context.stage_data["archive_name"] = archive_name
            context.stage_data["archive_size"] = size
            
            return StageResult(
                status=StageStatus.COMPLETED,
                message=f"Archive created ({size / 1024 / 1024:.1f} MB)",
                details={"archive_name": archive_name, "size_bytes": size},
            )
            
        except subprocess.TimeoutExpired:
            return StageResult(
                status=StageStatus.FAILED,
                message="Archive creation timed out after 30 minutes",
            )
    
    async def _upload_remote(self, context: BackupContext) -> StageResult:
        """Upload to S3 compatible storage."""
        if not context.archive_path or not os.path.exists(context.archive_path):
            return StageResult(
                status=StageStatus.FAILED,
                message="Archive not found",
            )
        
        # Get storage config from context
        storage_config = context.config.get("storage")
        if not storage_config or not storage_config.get("bucket"):
            logger.warning("No storage configuration found in context, skipping upload")
            return StageResult(
                status=StageStatus.SKIPPED,
                message="No storage provider configured",
            )
            
        archive_name = context.stage_data.get('archive_name')
        if not archive_name:
             archive_name = os.path.basename(context.archive_path)
             
        bucket = storage_config['bucket']
        
        # Build UUID-based path: {node_uuid}/{site_uuid}/{filename}
        node_uuid = context.config.get('node_uuid')
        site_uuid = context.config.get('site_uuid')
        
        if node_uuid and site_uuid:
            key = f"{node_uuid}/{site_uuid}/{archive_name}"
        else:
            # Fallback to name-based path for backwards compatibility
            key = f"{context.target_name}/{archive_name}"
            logger.warning(f"Using name-based path (missing UUIDs): {key}")
        
        logger.info(f"Uploading {archive_name} to {bucket}/{key}...")
        
        try:
            # Build S3 client args
            client_args = {
                'service_name': 's3',
                'region_name': storage_config.get('region') or 'us-east-1',
                'aws_access_key_id': storage_config.get('access_key'),
                'aws_secret_access_key': storage_config.get('secret_key'),
            }
            
            if storage_config.get('endpoint'):
                endpoint = storage_config['endpoint']
                if not endpoint.startswith("http"):
                    endpoint = f"https://{endpoint}"
                client_args['endpoint_url'] = endpoint
            
            # Helper function for blocking upload
            def upload_file_sync():
                s3 = boto3.client(**client_args)
                s3.upload_file(context.archive_path, bucket, key)
            
            # Run upload in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            start_upload = time.monotonic()
            await loop.run_in_executor(None, upload_file_sync)
            upload_duration = time.monotonic() - start_upload
            
            context.remote_path = f"s3://{bucket}/{key}"
            file_size_mb = os.path.getsize(context.archive_path) / (1024 * 1024)
            speed_mbps = file_size_mb / upload_duration if upload_duration > 0 else 0
            
            logger.info(f"Uploaded to {context.remote_path} in {upload_duration:.2f}s ({speed_mbps:.2f} MB/s)")
            
            return StageResult(
                status=StageStatus.COMPLETED,
                message=f"Uploaded to {context.remote_path}",
                details={
                    "remote_path": context.remote_path,
                    "bucket": bucket,
                    "key": key,
                    "duration": upload_duration,
                    "speed_mbps": speed_mbps
                },
            )
            
        except Exception as e:
            logger.exception(f"S3 Upload failed: {e}")
            return StageResult(
                status=StageStatus.FAILED,
                message=f"Upload failed: {str(e)}",
            )
    
    async def _cleanup(self, context: BackupContext) -> StageResult:
        """Remove temporary files."""
        if context.temp_dir and os.path.exists(context.temp_dir):
            try:
                shutil.rmtree(context.temp_dir)
                logger.info(f"Cleaned up temp dir {context.temp_dir}")
                return StageResult(
                    status=StageStatus.COMPLETED,
                    message="Cleanup completed",
                )
            except Exception as e:
                return StageResult(
                    status=StageStatus.FAILED,
                    message=f"Cleanup failed: {e}",
                )
        
        return StageResult(
            status=StageStatus.SKIPPED,
            message="Nothing to clean up",
        )


# Register the module
register_module(WordPressModule())
