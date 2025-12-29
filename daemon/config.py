"""
Backupd Configuration

Detects master/node mode and loads settings.
"""
import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class DaemonMode(str, Enum):
    MASTER = "master"
    NODE = "node"
    UNCONFIGURED = "unconfigured"


@dataclass
class DaemonConfig:
    mode: DaemonMode
    master_url: Optional[str] = None
    node_api_key: Optional[str] = None
    registration_code: Optional[str] = None
    data_dir: str = "/var/lib/backupd"
    
    # Resource limits
    max_io_concurrent: int = 2
    max_network_concurrent: int = 1
    max_upload_bandwidth_mbps: int = 50
    
    # API settings (master mode)
    api_host: str = "0.0.0.0"
    api_port: int = 8000


def detect_mode() -> DaemonMode:
    """
    Detect daemon mode from environment or config file.
    """
    # Check environment variable first
    mode_env = os.getenv("BACKUPD_MODE", "").lower()
    if mode_env == "master":
        return DaemonMode.MASTER
    elif mode_env == "node":
        return DaemonMode.NODE
    
    # Check for config file
    config_file = os.getenv("BACKUPD_CONFIG", "/etc/backupd/config")
    if os.path.exists(config_file):
        with open(config_file) as f:
            for line in f:
                if line.startswith("mode="):
                    mode_val = line.split("=")[1].strip().lower()
                    if mode_val == "master":
                        return DaemonMode.MASTER
                    elif mode_val == "node":
                        return DaemonMode.NODE
    
    return DaemonMode.UNCONFIGURED


def load_config() -> DaemonConfig:
    """
    Load full daemon configuration.
    """
    mode = detect_mode()
    
    # Try to load API key from config file if not in env
    api_key = os.getenv("BACKUPD_API_KEY")
    if not api_key:
        config_file = os.getenv("BACKUPD_CONFIG", "/etc/backupd/config")
        if os.path.exists(config_file):
            with open(config_file) as f:
                for line in f:
                    if line.startswith("api_key="):
                        api_key = line.split("=", 1)[1].strip()
                        break
    
    config = DaemonConfig(
        mode=mode,
        master_url=os.getenv("BACKUPD_MASTER_URL"),
        node_api_key=api_key,
        data_dir=os.getenv("BACKUPD_DATA_DIR", "/var/lib/backupd"),
        max_io_concurrent=int(os.getenv("BACKUPD_MAX_IO", "2")),
        max_network_concurrent=int(os.getenv("BACKUPD_MAX_NETWORK", "1")),
        max_upload_bandwidth_mbps=int(os.getenv("BACKUPD_MAX_BANDWIDTH_MBPS", "50")),
        api_host=os.getenv("BACKUPD_HOST", "0.0.0.0"),
        api_port=int(os.getenv("BACKUPD_PORT", "8000")),
    )
    
    return config

