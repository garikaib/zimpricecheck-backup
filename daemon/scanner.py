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

import subprocess
import shlex
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

def get_site_metadata(config: Dict[str, str]) -> Dict[str, str]:
    """
    Attempt to fetch site URL and name from the database.
    """
    metadata = {"url": None, "name": None}
    
    # We need at least db user and name
    if not config.get("db_user") or not config.get("db_name"):
        return metadata
    
    # Construct mysql command
    # mysql -u user -ppassword -h host -D dbname -N -e "select option_value from wp_options where option_name in ('siteurl', 'blogname');"
    
    cmd = ["mysql"]
    
    # Add connection verification options
    cmd.extend(["--connect-timeout=5", "--silent", "--skip-column-names"])
    
    if config.get("db_host"):
        # Handle port if present (host:port)
        host_parts = config["db_host"].split(":")
        cmd.extend(["-h", host_parts[0]])
        if len(host_parts) > 1:
            cmd.extend(["-P", host_parts[1]])
            
    cmd.extend(["-u", config["db_user"]])
    
    if config.get("db_password"):
        cmd.extend([f"-p{config['db_password']}"])
        
    cmd.extend(["-D", config["db_name"]])
    
    prefix = config.get("table_prefix", "wp_")
    table = f"{prefix}options"
    
    query = f"SELECT option_name, option_value FROM {table} WHERE option_name IN ('siteurl', 'blogname')"
    cmd.extend(["-e", query])
    
    try:
        # Run command with timeout
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    key, val = parts[0], parts[1]
                    if key == "siteurl":
                        metadata["url"] = val
                    elif key == "blogname":
                        metadata["name"] = val
        else:
            logger.warning(f"Metadata fetch failed: {result.stderr}")
            
    except Exception as e:
        logger.warning(f"Error fetching metadata: {e}")
        
    return metadata

def verify_wordpress_site(path: str, wp_config_path: str = None) -> Dict[str, Any]:
    """
    Verify if a path is a valid WordPress site and extract details.
    
    Args:
        path: The document root of the site.
        wp_config_path: Optional specific path to wp-config.php.
        
    Returns:
        Dict with status and details.
    """
    path_obj = Path(path)
    result = {
        "valid": False,
        "error": None,
        "path": path,
        "details": {}
    }
    
    if not path_obj.exists():
        result["error"] = "Directory does not exist"
        return result
        
    if not path_obj.is_dir():
        result["error"] = "Path is not a directory"
        return result
        
    # 1. Check for wp-content
    wp_content = path_obj / "wp-content"
    if not wp_content.exists() or not wp_content.is_dir():
        result["error"] = "Missing wp-content directory. Not a valid WordPress root?"
        return result
        
    # 2. Check for wp-config.php
    config_file = None
    
    if wp_config_path:
        # User provided path
        custom_conf = Path(wp_config_path)
        if custom_conf.exists() and custom_conf.is_file():
            config_file = custom_conf
        else:
            result["error"] = f"Provided wp-config.php not found at {wp_config_path}"
            return result
    else:
        # Auto-discovery
        # Check root
        if (path_obj / "wp-config.php").exists():
            config_file = path_obj / "wp-config.php"
        # Check parent (valid WP security practice)
        elif (path_obj.parent / "wp-config.php").exists():
            config_file = path_obj.parent / "wp-config.php"
            
    if not config_file:
        result["error"] = "wp-config.php not found. Please provide path explicitly."
        result["needs_config_path"] = True
        return result
        
    # 3. Parse config
    try:
        config = parse_wp_config(config_file)
        if not config.get("db_name"):
            result["error"] = "Could not parse DB credentials from wp-config.php"
            return result
            
        result["details"] = {
            "db_name": config.get("db_name"),
            "db_user": config.get("db_user"),
            "db_host": config.get("db_host"),
            "table_prefix": config.get("table_prefix"),
            "config_path": str(config_file)
        }
        
        # 4. Fetch Metadata
        metadata = get_site_metadata(config)
        result["details"]["site_url"] = metadata.get("url")
        result["details"]["site_name"] = metadata.get("name") or path_obj.name
        
        result["valid"] = True
        
    except Exception as e:
        result["error"] = f"Error processing configuration: {e}"
        
    return result

