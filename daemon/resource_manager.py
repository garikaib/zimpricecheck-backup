"""
Resource Manager

Controls concurrent access to I/O, network, and CPU resources.
All backup jobs share these pools to prevent overloading the system.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class ResourceLimits:
    max_io_concurrent: int = 2
    max_network_concurrent: int = 1
    max_cpu_workers: int = 4
    max_upload_bandwidth_mbps: int = 50


class ResourceManager:
    """
    Manages shared resources across all backup jobs.
    
    Usage:
        async with resource_manager.acquire_io():
            # disk operations
        
        async with resource_manager.acquire_network():
            # upload/download
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        
        # Semaphores for resource control
        self._io_semaphore = asyncio.Semaphore(self.limits.max_io_concurrent)
        self._network_semaphore = asyncio.Semaphore(self.limits.max_network_concurrent)
        
        # Thread pool for CPU-intensive work
        self._cpu_pool = ThreadPoolExecutor(
            max_workers=self.limits.max_cpu_workers,
            thread_name_prefix="backupd-worker"
        )
        
        # Bandwidth tracking
        self._bandwidth_limit_bps = self.limits.max_upload_bandwidth_mbps * 1_000_000 / 8
        self._bytes_sent_this_second = 0
        self._last_reset = time.monotonic()
    
    def acquire_io(self):
        """Context manager for I/O operations."""
        return self._io_semaphore
    
    def acquire_network(self):
        """Context manager for network operations."""
        return self._network_semaphore
    
    @property
    def cpu_pool(self) -> ThreadPoolExecutor:
        """Thread pool for CPU-intensive work."""
        return self._cpu_pool
    
    async def rate_limited_upload(self, data: bytes, upload_func):
        """
        Upload data with bandwidth limiting.
        
        Args:
            data: bytes to upload
            upload_func: async callable that performs the upload
        """
        async with self._network_semaphore:
            # Simple rate limiting - wait if we've exceeded bandwidth
            now = time.monotonic()
            if now - self._last_reset >= 1.0:
                self._bytes_sent_this_second = 0
                self._last_reset = now
            
            bytes_to_send = len(data)
            while self._bytes_sent_this_second + bytes_to_send > self._bandwidth_limit_bps:
                await asyncio.sleep(0.1)
                now = time.monotonic()
                if now - self._last_reset >= 1.0:
                    self._bytes_sent_this_second = 0
                    self._last_reset = now
            
            self._bytes_sent_this_second += bytes_to_send
            return await upload_func(data)
    
    def get_stats(self) -> dict:
        """Get current resource usage stats."""
        return {
            "io_available": self.limits.max_io_concurrent - (self.limits.max_io_concurrent - self._io_semaphore._value),
            "io_max": self.limits.max_io_concurrent,
            "network_available": self.limits.max_network_concurrent - (self.limits.max_network_concurrent - self._network_semaphore._value),
            "network_max": self.limits.max_network_concurrent,
            "bandwidth_limit_mbps": self.limits.max_upload_bandwidth_mbps,
        }
    
    def shutdown(self):
        """Cleanup resources."""
        self._cpu_pool.shutdown(wait=True)


# Global instance
_resource_manager: Optional[ResourceManager] = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def init_resource_manager(limits: ResourceLimits) -> ResourceManager:
    """Initialize the global resource manager with custom limits."""
    global _resource_manager
    _resource_manager = ResourceManager(limits)
    return _resource_manager
