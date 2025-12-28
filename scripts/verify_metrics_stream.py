#!/usr/bin/env python3
"""
Test script to verify node metrics streaming.
"""
import sys
import json
import time
import requests
import sseclient  # pip install sseclient-py

# Check if sseclient is installed, if not suggest installation
try:
    import sseclient
except ImportError:
    print("Please install sseclient-py: pip install sseclient-py")
    # Minimal SSE implementation if library not available
    class SimpleSSEClient:
        def __init__(self, url):
            self.resp = requests.get(url, stream=True)
            self.resp.raise_for_status()
            
        def events(self):
            for line in self.resp.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    yield type('Event', (), {'data': line[6:]})
    sseclient = type('module', (), {'SSEClient': SimpleSSEClient})

API_URL = "https://wp.zimpricecheck.com:8081/api/v1"
USERNAME = "admin@example.com"
PASSWORD = "admin123"

def get_token():
    print(f"Logging in as {USERNAME}...")
    resp = requests.post(f"{API_URL}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
        
    return resp.json()["access_token"]

def stream_metrics(token):
    url = f"{API_URL}/metrics/node/stream?token={token}&interval=2"
    print(f"\nConnecting to SSE stream: {url}")
    print("waiting for events (Ctrl+C to stop)...\n")
    
    try:
        messages = sseclient.SSEClient(url)
        for msg in messages.events():
            try:
                data = json.loads(msg.data)
                
                # Handle connection message
                if data.get("event") == "connected":
                    print(f"✅ CONNECTED: {data.get('message')}")
                    continue
                
                # Handle error message
                if data.get("event") == "error":
                    print(f"❌ ERROR: {data.get('message')}")
                    continue
                
                # Handle metrics data
                timestamp = data.get("timestamp", "").split("T")[1].split(".")[0]
                cpu = data.get("cpu", {}).get("usage_percent", 0)
                mem = data.get("memory", {}).get("percent_used", 0)
                disk = data.get("disks", [{}])[0].get("percent_used", 0)
                
                print(f"[{timestamp}] CPU: {cpu:>4}% | MEM: {mem:>4}% | DISK: {disk:>4}%")
                
            except json.JSONDecodeError:
                print(f"Received raw data: {msg.data}")
                
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nStream error: {e}")

def poll_nodes_stats(token):
    """Background polling for remote node stats via /nodes/ endpoint."""
    print("Starting background polling for remote node stats...")
    headers = {"Authorization": f"Bearer {token}"}
    
    while True:
        try:
            resp = requests.get(f"{API_URL}/nodes/", headers=headers, timeout=5)
            if resp.status_code == 200:
                nodes = resp.json()
                for node in nodes:
                    stats = node.get("stats", [])
                    if stats:
                        latest = stats[0]
                        print(f"[Polling] Node {node['hostname']} (ID {node['id']}): CPU {latest['cpu_usage']}% | Disk {latest['disk_usage']}% | Active Backups {latest['active_backups']}")
            time.sleep(5)
        except Exception as e:
            print(f"[Polling Error] {e}")
            time.sleep(5)

if __name__ == "__main__":
    try:
        token = get_token()
        
        # Start polling in background thread
        import threading
        t = threading.Thread(target=poll_nodes_stats, args=(token,), daemon=True)
        t.start()
        
        stream_metrics(token)
    except KeyboardInterrupt:
        pass
