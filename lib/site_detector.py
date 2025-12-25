#!/usr/bin/env python3
"""
WordPress Site Detector

Auto-detects WordPress installations on the server.
"""

import os
import re
import json
from glob import glob

# Common WordPress installation patterns
WP_SEARCH_PATHS = [
    "/var/www/*/wp-config.php",
    "/var/www/*/htdocs/wp-config.php",
    "/var/www/*/public_html/wp-config.php",
    "/var/www/*/html/wp-config.php",
    "/home/*/public_html/wp-config.php",
]

WP_CONTENT_PATTERNS = [
    "htdocs/wp-content",
    "public_html/wp-content",
    "html/wp-content",
    "wp-content",
]


def find_wp_content(base_dir):
    """Find wp-content directory relative to base."""
    for pattern in WP_CONTENT_PATTERNS:
        path = os.path.join(base_dir, pattern)
        if os.path.isdir(path):
            # Validate it's real WordPress content
            if os.path.isdir(os.path.join(path, "themes")) or os.path.isdir(os.path.join(path, "plugins")):
                return path
    return None


def extract_site_name(wp_config_path):
    """Extract a sensible site name from path."""
    # /var/www/example.com/htdocs/wp-config.php -> example.com
    # /var/www/example.com/wp-config.php -> example.com
    parts = wp_config_path.split("/")
    
    # Find the directory after /var/www/ or similar
    for i, part in enumerate(parts):
        if part in ("www", "html", "public_html", "home"):
            if i + 1 < len(parts):
                name = parts[i + 1]
                # Clean up domain-like names
                name = name.replace(".com", "").replace(".co.zw", "").replace(".org", "")
                name = re.sub(r'[^a-zA-Z0-9-]', '-', name)
                return name.lower()
    
    # Fallback: use parent directory name
    parent = os.path.dirname(os.path.dirname(wp_config_path))
    return os.path.basename(parent).lower().replace(".", "-")


def detect_wordpress_sites():
    """Scan for WordPress installations."""
    found_sites = []
    seen_configs = set()
    
    for pattern in WP_SEARCH_PATHS:
        for wp_config in glob(pattern):
            # Avoid duplicates
            if wp_config in seen_configs:
                continue
            seen_configs.add(wp_config)
            
            # Validate it's a real wp-config
            if not os.path.isfile(wp_config):
                continue
            
            try:
                with open(wp_config, 'r') as f:
                    content = f.read(1000)
                    if 'DB_NAME' not in content:
                        continue  # Not a real wp-config
            except:
                continue
            
            # Find wp-content
            base_dir = os.path.dirname(wp_config)
            wp_content = find_wp_content(base_dir)
            
            # Also check parent directory
            if not wp_content:
                parent_dir = os.path.dirname(base_dir)
                wp_content = find_wp_content(parent_dir)
            
            if not wp_content:
                continue  # Can't find wp-content, skip
            
            site_name = extract_site_name(wp_config)
            
            found_sites.append({
                "name": site_name,
                "wp_config_path": wp_config,
                "wp_content_path": wp_content,
                "db_host": "",
                "db_name": "",
                "db_user": "",
                "db_password": ""
            })
    
    return found_sites


def prompt_select_sites(sites):
    """Interactive prompt to select which sites to back up."""
    if not sites:
        print("\n[!] No WordPress sites detected.")
        return []
    
    print(f"\n[*] Found {len(sites)} WordPress site(s):\n")
    
    selected = []
    for i, site in enumerate(sites):
        print(f"  {i+1}. {site['name']}")
        print(f"      Config: {site['wp_config_path']}")
        print(f"      Content: {site['wp_content_path']}")
        
        choice = input(f"      Back up this site? [Y/n]: ").strip().lower()
        if choice != 'n':
            selected.append(site)
        print()
    
    return selected


def is_remote_environment():
    """Detect if running on a server (has /var/www with sites)."""
    if os.path.isdir("/var/www"):
        # Check if there are actual sites
        sites = glob("/var/www/*/")
        return len(sites) > 0
    return False


if __name__ == "__main__":
    print("Scanning for WordPress sites...")
    sites = detect_wordpress_sites()
    
    if sites:
        print(f"\nFound {len(sites)} site(s):")
        for s in sites:
            print(f"  - {s['name']}: {s['wp_config_path']}")
    else:
        print("No WordPress sites found.")
