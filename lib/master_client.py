import requests
import json
import time
import sys
import os

def request_join(master_url, hostname, ip_address):
    """
    Submit a join request to the Master Server.
    Returns: request_id (str) or None.
    """
    try:
        node_data = {
            "hostname": hostname,
            "ip_address": ip_address,
            "system_info": f"Python {sys.version.split()[0]}"
        }
        
        res = requests.post(
            f"{master_url}/api/v1/nodes/join-request",
            json=node_data,
            timeout=10
        )
        res.raise_for_status()
        data = res.json()
        print(f"[+] Join request submitted. ID: {data['request_id']}")
        print(f"    Message: {data['message']}")
        return data["request_id"]
        
    except Exception as e:
        print(f"[!] Request failed: {e}")
        return None

def poll_for_approval(master_url, request_id, timeout_minutes=5):
    """
    Poll the Master Server until approved or timeout.
    Returns: api_key (str) or None.
    """
    print(f"[*] Waiting for Admin approval (Timeout: {timeout_minutes}m)...")
    start_time = time.time()
    
    while (time.time() - start_time) < (timeout_minutes * 60):
        try:
            res = requests.get(
                f"{master_url}/api/v1/nodes/status/{request_id}",
                timeout=10
            )
            if res.status_code == 200:
                data = res.json()
                status = data.get("status")
                
                if status == "active":
                    api_key = data.get("api_key")
                    if api_key:
                        print("\n[+] Approval Granted!")
                        return api_key
                elif status == "blocked":
                    print("\n[!] Request was BLOCKED by Admin.")
                    return None
                
            # Wait before retry
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)
            
        except Exception as e:
            print(f"\n[!] Polling error: {e}")
            time.sleep(10)
            
    print("\n[!] Timed out waiting for approval.")
    return None
