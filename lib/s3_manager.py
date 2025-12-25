#!/usr/bin/env python3
"""
S3 Storage Manager (Unlimited Servers Edition)

Manages uploads to S3-compatible storage services (AWS S3, iDrive E2, Backblaze B2, etc.)
Supports unlimited S3 server configurations via numbered environment variables.
"""

import os
import datetime
import sqlite3
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
DB_FILE = os.path.join(BASE_DIR, "backups.db")

load_dotenv(ENV_PATH)

# Server ID for shared storage
SERVER_ID = os.getenv("SERVER_ID", "default")


class S3StorageServer:
    """Represents a single S3-compatible storage server."""
    
    def __init__(self, server_id: int, endpoint: str, region: str, 
                 access_key: str, secret_key: str, bucket: str, 
                 storage_limit_gb: float = 100.0):
        self.server_id = server_id
        self.endpoint = endpoint
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self.storage_limit_bytes = int(storage_limit_gb * 1024 * 1024 * 1024)
        self._client = None
    
    @property
    def client(self):
        """Lazy-load S3 client."""
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=f"https://{self.endpoint}",
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
        return self._client
    
    def get_usage(self) -> int:
        """Get total bytes used in the bucket. Returns 0 on error."""
        try:
            total = 0
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket):
                for obj in page.get('Contents', []):
                    total += obj.get('Size', 0)
            return total
        except Exception:
            return 0
    
    def has_space(self, file_size: int) -> bool:
        """Check if server has enough space for file."""
        used = self.get_usage()
        return (self.storage_limit_bytes - used) >= file_size
    
    def ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ('404', 'NoSuchBucket'):
                try:
                    self.client.create_bucket(
                        Bucket=self.bucket,
                        CreateBucketConfiguration={'LocationConstraint': self.region}
                    )
                except ClientError:
                    # Some S3-compatible services handle this differently
                    self.client.create_bucket(Bucket=self.bucket)
    
    def upload(self, local_path: str, remote_key: str) -> tuple[bool, str]:
        """
        Upload file to S3.
        Returns (success, error_message).
        """
        try:
            self.ensure_bucket_exists()
            self.client.upload_file(local_path, self.bucket, remote_key)
            return True, ""
        except FileNotFoundError:
            return False, f"Local file not found: {local_path}"
        except NoCredentialsError:
            return False, "Invalid S3 credentials"
        except ClientError as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)
    
    def __repr__(self):
        return f"S3Server({self.server_id}: {self.endpoint}/{self.bucket})"


class S3Manager:
    """Manages multiple S3 storage servers."""
    
    def __init__(self):
        self.servers = self._load_servers()
    
    def _load_servers(self) -> list[S3StorageServer]:
        """Load all configured S3 servers from environment variables."""
        servers = []
        server_num = 1
        
        while True:
            prefix = f"S3_SERVER_{server_num}_"
            endpoint = os.getenv(f"{prefix}ENDPOINT", "")
            
            if not endpoint:
                break  # No more servers configured
            
            region = os.getenv(f"{prefix}REGION", "us-east-1")
            access_key = os.getenv(f"{prefix}ACCESS_KEY", "")
            secret_key = os.getenv(f"{prefix}SECRET_KEY", "")
            bucket = os.getenv(f"{prefix}BUCKET", "wordpress-backups")
            storage_limit = float(os.getenv(f"{prefix}STORAGE_LIMIT_GB", "100"))
            
            if access_key and secret_key:
                servers.append(S3StorageServer(
                    server_id=server_num,
                    endpoint=endpoint,
                    region=region,
                    access_key=access_key,
                    secret_key=secret_key,
                    bucket=bucket,
                    storage_limit_gb=storage_limit
                ))
            
            server_num += 1
        
        return servers
    
    @property
    def enabled(self) -> bool:
        """Check if any S3 servers are configured."""
        return len(self.servers) > 0
    
    def upload(self, local_path: str, filename: str, file_size: int, 
               site_name: str, log_func=None) -> tuple[bool, str]:
        """
        Upload file to any available S3 server.
        
        Uses folder structure: SERVER_ID/Year/Month/Day/filename
        Returns (success, server_endpoint or error_message).
        """
        if not self.servers:
            msg = "No S3 servers configured"
            if log_func:
                log_func("WARNING", msg, site_name)
            return False, msg
        
        # Determine remote path: SERVER_ID/Year/Month/Day
        now = datetime.datetime.now()
        remote_dir = f"{SERVER_ID}/{now.year}/{now.month:02d}/{now.day:02d}"
        remote_key = f"{remote_dir}/{filename}"
        
        # Try each server in order
        for server in self.servers:
            try:
                if log_func:
                    log_func("INFO", f"Trying S3 server: {server.endpoint}", site_name)
                
                # Check space
                if not server.has_space(file_size):
                    if log_func:
                        log_func("WARNING", f"Not enough space on {server.endpoint}", site_name)
                    continue
                
                # Upload
                success, error = server.upload(local_path, remote_key)
                
                if success:
                    # Record in database
                    self._record_upload(remote_key, server, file_size, site_name)
                    
                    if log_func:
                        log_func("SUCCESS", f"Uploaded to S3: {server.endpoint}/{server.bucket}", site_name)
                    
                    return True, server.endpoint
                else:
                    if log_func:
                        log_func("WARNING", f"Upload failed: {error}", site_name)
            
            except Exception as e:
                if log_func:
                    log_func("ERROR", f"S3 error: {e}", site_name)
                continue
        
        msg = "All S3 uploads failed"
        if log_func:
            log_func("ERROR", msg, site_name)
        return False, msg
    
    def _record_upload(self, remote_key: str, server: S3StorageServer, 
                       file_size: int, site_name: str):
        """Record successful upload in database."""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Ensure table exists
            c.execute('''CREATE TABLE IF NOT EXISTS s3_archives
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         filename TEXT NOT NULL,
                         s3_endpoint TEXT NOT NULL,
                         s3_bucket TEXT NOT NULL,
                         file_size INTEGER,
                         upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                         site_name TEXT,
                         server_id TEXT)''')
            
            c.execute("""INSERT INTO s3_archives 
                        (filename, s3_endpoint, s3_bucket, file_size, site_name, server_id) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                      (remote_key, server.endpoint, server.bucket, 
                       file_size, site_name, SERVER_ID))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to record upload: {e}")
    
    def list_uploads(self, site_name: str = None) -> list:
        """List recorded uploads, optionally filtered by site."""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            if site_name:
                c.execute("SELECT * FROM s3_archives WHERE site_name = ? AND server_id = ?", 
                          (site_name, SERVER_ID))
            else:
                c.execute("SELECT * FROM s3_archives WHERE server_id = ?", (SERVER_ID,))
            
            rows = c.fetchall()
            conn.close()
            return rows
        except Exception:
            return []


# Convenience function for direct usage
def upload_to_s3(filepath: str, filename: str, file_size: int, 
                 site_name: str, log_func=None) -> str | None:
    """
    Upload file to S3 storage.
    Returns endpoint on success, None on failure.
    """
    manager = S3Manager()
    success, result = manager.upload(filepath, filename, file_size, site_name, log_func)
    return result if success else None


if __name__ == "__main__":
    # Test S3 connectivity
    manager = S3Manager()
    
    if not manager.enabled:
        print("No S3 servers configured.")
        print("Set S3_SERVER_1_ENDPOINT, S3_SERVER_1_ACCESS_KEY, etc. in .env")
    else:
        print(f"Configured S3 servers: {len(manager.servers)}")
        for server in manager.servers:
            print(f"  - {server}")
            try:
                usage = server.get_usage()
                print(f"    Usage: {usage / 1024 / 1024:.2f} MB")
            except Exception as e:
                print(f"    Error: {e}")
