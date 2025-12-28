import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add root to path
sys.path.insert(0, os.getcwd())

from master.core.scheduler import calculate_next_run
from master.db import models

def test_calculate_next_run():
    print("Testing calculate_next_run...")
    
    harare = ZoneInfo("Africa/Harare")
    now_harare = datetime.now(harare)
    
    # Mock Site
    site = models.Site(
        schedule_frequency="daily",
        schedule_time="23:00", # 11 PM
        schedule_days=None
    )
    
    next_run_utc = calculate_next_run(site)
    
    if not next_run_utc:
        print("FAIL: Next run is None")
        sys.exit(1)
        
    print(f"Current Harare Time: {now_harare}")
    print(f"Next Run (UTC): {next_run_utc}")
    
    # Convert back to Harare for verification
    next_run_harare = next_run_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(harare)
    print(f"Next Run (Harare): {next_run_harare}")
    
    # Check if time matches 23:00
    if next_run_harare.hour != 23 or next_run_harare.minute != 0:
        print(f"FAIL: Expected 23:00, got {next_run_harare.strftime('%H:%M')}")
        sys.exit(1)
        
    # Check if it's in the future
    if next_run_harare <= now_harare:
        print("FAIL: Next run is in the past!")
        sys.exit(1)
        
    print("PASS: Daily schedule calculation correct")

if __name__ == "__main__":
    test_calculate_next_run()
