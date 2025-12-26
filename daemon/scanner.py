"""
WordPress Site Scanner

Scans directories for WordPress installations by looking for wp-content/ and wp-config.php.
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSite:
    """Represents a discovered WordPress site."""
    name: str
    path: str
    has_wp_config: bool
    has_wp_content: bool
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_host: Optional[str] = None
    table_prefix: Optional[str] = None


def parse_wp_config(wp_config_path: Path) -> Dict[str, str]:
    """
    Parse wp-config.php to extract database configuration.
    
    Returns dict with keys: db_name, db_user, db_password, db_host, table_prefix
    """
    config = {}
    
    try:
        content = wp_config_path.read_text()
        
        # Pattern for define('KEY', 'value');
        define_pattern = r"define\s*\(\s*['\"](\w+)['\"]\s*,\s*['\"]([^'\"]*)"
        for match in re.finditer(define_pattern, content):
            key, value = match.groups()
            if key == "DB_NAME":
                config["db_name"] = value
            elif key == "DB_USER":
                config["db_user"] = value
            elif key == "DB_PASSWORD":
                config["db_password"] = value
            elif key == "DB_HOST":
                config["db_host"] = value
        
        # Pattern for $table_prefix = 'wp_';
        prefix_pattern = r"\$table_prefix\s*=\s*['\"]([^'\"]+)"
        match = re.search(prefix_pattern, content)
        if match:
            config["table_prefix"] = match.group(1)
        
    except Exception as e:
        logger.warning(f"Failed to parse wp-config.php at {wp_config_path}: {e}")
    
    return config


def scan_for_wordpress_sites(
    base_path: str = "/var/www",
    subdirs: List[str] = None,
) -> List[DiscoveredSite]:
    """
    Scan for WordPress installations.
    
    Args:
        base_path: Base directory to scan (default: /var/www)
        subdirs: Subdirectories to check within each site (default: ["htdocs", "public_html", "html", "www", "."])
    
    Returns:
        List of discovered WordPress sites
    """
    if subdirs is None:
        subdirs = ["htdocs", "public_html", "html", "www", "."]
    
    sites = []
    base = Path(base_path)
    
    if not base.exists():
        logger.warning(f"Base path does not exist: {base_path}")
        return sites
    
    try:
        for site_dir in base.iterdir():
            if not site_dir.is_dir():
                continue
            
            # Skip common non-site directories
            if site_dir.name.startswith(".") or site_dir.name in ["cgi-bin", "logs"]:
                continue
            
            # Check each possible subdirectory
            for subdir in subdirs:
                if subdir == ".":
                    check_path = site_dir
                else:
                    check_path = site_dir / subdir
                
                if not check_path.exists():
                    continue
                
                wp_config = check_path / "wp-config.php"
                wp_content = check_path / "wp-content"
                
                has_wp_config = wp_config.exists()
                has_wp_content = wp_content.exists() and wp_content.is_dir()
                
                if has_wp_config or has_wp_content:
                    site = DiscoveredSite(
                        name=site_dir.name,
                        path=str(check_path),
                        has_wp_config=has_wp_config,
                        has_wp_content=has_wp_content,
                    )
                    
                    # Parse wp-config if available
                    if has_wp_config:
                        config = parse_wp_config(wp_config)
                        site.db_name = config.get("db_name")
                        site.db_user = config.get("db_user")
                        site.db_host = config.get("db_host")
                        site.table_prefix = config.get("table_prefix")
                    
                    sites.append(site)
                    logger.info(f"Discovered WordPress site: {site.name} at {site.path}")
                    break  # Found in this subdirectory, move to next site
    
    except PermissionError as e:
        logger.warning(f"Permission denied scanning {base_path}: {e}")
    except Exception as e:
        logger.error(f"Error scanning for sites: {e}")
    
    return sites


def site_to_dict(site: DiscoveredSite) -> Dict[str, Any]:
    """Convert DiscoveredSite to dictionary for JSON serialization."""
    return {
        "name": site.name,
        "path": site.path,
        "has_wp_config": site.has_wp_config,
        "has_wp_content": site.has_wp_content,
        "db_name": site.db_name,
        "db_user": site.db_user,
        "db_host": site.db_host,
        "table_prefix": site.table_prefix,
        "is_complete": site.has_wp_config and site.has_wp_content,
    }
