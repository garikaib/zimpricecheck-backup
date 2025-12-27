"""
Node System Metrics Collector

Collects system-level metrics for monitoring node health:
- CPU usage and load averages
- Memory usage
- Disk usage
- Network I/O
- Process information
"""
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


@dataclass
class CPUMetrics:
    """CPU usage metrics."""
    usage_percent: float
    core_count: int
    load_avg_1min: float
    load_avg_5min: float
    load_avg_15min: float


@dataclass
class MemoryMetrics:
    """Memory usage metrics."""
    total_bytes: int
    used_bytes: int
    available_bytes: int
    percent_used: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_percent: float


@dataclass
class DiskMetrics:
    """Disk usage for a specific path."""
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float


@dataclass 
class NetworkMetrics:
    """Network I/O metrics."""
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    connections_count: int


@dataclass
class SystemMetrics:
    """Complete system metrics snapshot."""
    timestamp: str
    hostname: str
    uptime_seconds: int
    cpu: CPUMetrics
    memory: MemoryMetrics
    disks: list  # List of DiskMetrics
    network: NetworkMetrics
    backup_process: Optional[Dict[str, Any]] = None


def get_cpu_metrics() -> CPUMetrics:
    """Get CPU usage and load averages."""
    if not PSUTIL_AVAILABLE:
        return CPUMetrics(
            usage_percent=0.0,
            core_count=1,
            load_avg_1min=0.0,
            load_avg_5min=0.0,
            load_avg_15min=0.0,
        )
    
    # Get load averages (Unix only)
    try:
        load_avg = os.getloadavg()
    except (OSError, AttributeError):
        load_avg = (0.0, 0.0, 0.0)
    
    return CPUMetrics(
        usage_percent=psutil.cpu_percent(interval=0.1),
        core_count=psutil.cpu_count() or 1,
        load_avg_1min=load_avg[0],
        load_avg_5min=load_avg[1],
        load_avg_15min=load_avg[2],
    )


def get_memory_metrics() -> MemoryMetrics:
    """Get memory usage statistics."""
    if not PSUTIL_AVAILABLE:
        return MemoryMetrics(
            total_bytes=0,
            used_bytes=0,
            available_bytes=0,
            percent_used=0.0,
            swap_total_bytes=0,
            swap_used_bytes=0,
            swap_percent=0.0,
        )
    
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return MemoryMetrics(
        total_bytes=mem.total,
        used_bytes=mem.used,
        available_bytes=mem.available,
        percent_used=mem.percent,
        swap_total_bytes=swap.total,
        swap_used_bytes=swap.used,
        swap_percent=swap.percent,
    )


def get_disk_metrics(paths: list = None) -> list:
    """Get disk usage for specified paths."""
    if paths is None:
        paths = ["/", "/var/www", "/tmp"]
    
    disks = []
    
    if not PSUTIL_AVAILABLE:
        return disks
    
    for path in paths:
        if os.path.exists(path):
            try:
                usage = psutil.disk_usage(path)
                disks.append(DiskMetrics(
                    path=path,
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                    percent_used=usage.percent,
                ))
            except (PermissionError, OSError):
                pass
    
    return disks


def get_network_metrics() -> NetworkMetrics:
    """Get network I/O statistics."""
    if not PSUTIL_AVAILABLE:
        return NetworkMetrics(
            bytes_sent=0,
            bytes_recv=0,
            packets_sent=0,
            packets_recv=0,
            connections_count=0,
        )
    
    net_io = psutil.net_io_counters()
    
    try:
        connections = len(psutil.net_connections(kind='inet'))
    except (psutil.AccessDenied, PermissionError):
        connections = 0
    
    return NetworkMetrics(
        bytes_sent=net_io.bytes_sent,
        bytes_recv=net_io.bytes_recv,
        packets_sent=net_io.packets_sent,
        packets_recv=net_io.packets_recv,
        connections_count=connections,
    )


def get_backup_process_info() -> Optional[Dict[str, Any]]:
    """Get info about running backup process if any."""
    if not PSUTIL_AVAILABLE:
        return None
    
    # Look for mysqldump, tar, or zstd processes
    backup_keywords = ["mysqldump", "tar", "zstd", "backup"]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent', 'create_time']):
        try:
            cmdline = " ".join(proc.info.get('cmdline') or [])
            name = proc.info.get('name', '')
            
            if any(kw in cmdline.lower() or kw in name.lower() for kw in backup_keywords):
                return {
                    "pid": proc.info['pid'],
                    "name": name,
                    "cpu_percent": proc.info.get('cpu_percent', 0),
                    "memory_percent": proc.info.get('memory_percent', 0),
                    "running_seconds": int(time.time() - proc.info.get('create_time', time.time())),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return None


def get_system_metrics() -> Dict[str, Any]:
    """
    Get complete system metrics snapshot.
    
    Returns a dictionary suitable for JSON serialization.
    """
    import socket
    
    # Get uptime
    if PSUTIL_AVAILABLE:
        boot_time = psutil.boot_time()
        uptime = int(time.time() - boot_time)
    else:
        uptime = 0
    
    metrics = SystemMetrics(
        timestamp=datetime.utcnow().isoformat() + "Z",
        hostname=socket.gethostname(),
        uptime_seconds=uptime,
        cpu=get_cpu_metrics(),
        memory=get_memory_metrics(),
        disks=[asdict(d) for d in get_disk_metrics()],
        network=get_network_metrics(),
        backup_process=get_backup_process_info(),
    )
    
    # Convert to dict, handling nested dataclasses
    result = {
        "timestamp": metrics.timestamp,
        "hostname": metrics.hostname,
        "uptime_seconds": metrics.uptime_seconds,
        "cpu": asdict(metrics.cpu),
        "memory": asdict(metrics.memory),
        "disks": metrics.disks,
        "network": asdict(metrics.network),
        "backup_process": metrics.backup_process,
        "psutil_available": PSUTIL_AVAILABLE,
    }
    
    return result


def get_disk_details() -> Dict[str, Any]:
    """Get detailed disk information for all partitions."""
    if not PSUTIL_AVAILABLE:
        return {"partitions": [], "error": "psutil not available"}
    
    partitions = []
    
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            partitions.append({
                "device": partition.device,
                "mountpoint": partition.mountpoint,
                "fstype": partition.fstype,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": usage.percent,
            })
        except (PermissionError, OSError):
            pass
    
    return {"partitions": partitions}


# For testing
if __name__ == "__main__":
    import json
    print(json.dumps(get_system_metrics(), indent=2))
