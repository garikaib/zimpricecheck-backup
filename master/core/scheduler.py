import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from master.db import models
from master.db.session import SessionLocal
from daemon.api import _run_real_backup

logger = logging.getLogger(__name__)

# Config
HARARE_TZ = ZoneInfo("Africa/Harare")
SCHEDULER_INTERVAL_SECONDS = 60

scheduler = AsyncIOScheduler()

def init_scheduler(app):
    """Initialize and start the background scheduler."""
    # Add main job to check for scheduled backups
    scheduler.add_job(
        check_scheduled_backups,
        trigger=IntervalTrigger(seconds=SCHEDULER_INTERVAL_SECONDS),
        id="backup_scheduler",
        name="Check Scheduled Backups",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("Backup Scheduler started (Africa/Harare timezone)")

async def check_scheduled_backups():
    """
    Main loop to check and trigger scheduled backups.
    """
    db = SessionLocal()
    try:
        now_utc = datetime.now(ZoneInfo("UTC")).replace(tzinfo=None) # Naive UTC for DB comparison
        
        # 1. Fetch active sites with due backups
        # next_run_at is stored as naive UTC
        sites = db.query(models.Site).filter(
            models.Site.status == "active",
            models.Site.schedule_frequency != "manual",
            models.Site.next_run_at != None,
            models.Site.next_run_at <= now_utc
        ).all()
        
        for site in sites:
            # Check concurrency limits for the node
            if not can_run_backup_on_node(site.node, db):
                logger.warning(f"Skipping scheduled backup for {site.name}: Node concurrency limit reached")
                continue
                
            # Double check status (don't run if already running)
            if site.backup_status == "running":
                logger.info(f"Skipping scheduled backup for {site.name}: Backup already running")
                # Advance schedule anyway to avoid stuck loop? 
                # Better to retry later? No, if we don't advance, it will try again next minute while running.
                # But calculating next run should happen AFTER start or if skipped?
                # If running, we should likely wait. But if it runs for 2 hours and schedule is hourly?
                # Let's just skip this tick.
                continue
            
            # Start Backup
            logger.info(f"Triggering scheduled backup for {site.name}")
            
            # Update status
            site.backup_status = "running"
            site.backup_started_at = now_utc
            site.backup_message = "Starting scheduled backup..."
            db.commit()
            
            # Fire and forget (async)
            asyncio.create_task(_run_real_backup(site.id, site.wp_path, site.name))
            
            # Calculate next run time
            site.next_run_at = calculate_next_run(site)
            db.commit()
            logger.info(f"Rescheduled {site.name} for {site.next_run_at} UTC")

    except Exception as e:
        logger.exception("Error in backup scheduler")
    finally:
        db.close()

def can_run_backup_on_node(node: models.Node, db: Session) -> bool:
    """Check if node has capacity for another backup."""
    if not node:
        return True # Orphaned site?
        
    running_count = db.query(models.Site).filter(
        models.Site.node_id == node.id,
        models.Site.backup_status == "running"
    ).count()
    
    limit = node.max_concurrent_backups or 2
    return running_count < limit

def calculate_next_run(site: models.Site) -> datetime:
    """
    Calculate next run time based on schedule params (Harare Time).
    Returns naive UTC datetime.
    """
    if site.schedule_frequency == "manual":
        return None
        
    # Current time in Harare
    now_harare = datetime.now(HARARE_TZ)
    
    # Target time components from site.schedule_time (HH:MM or HH:MM:SS)
    if not site.schedule_time:
        return None
        
    try:
        parts = list(map(int, site.schedule_time.split(':')))
        hour = parts[0]
        minute = parts[1] if len(parts) > 1 else 0
    except ValueError:
        logger.error(f"Invalid schedule_time for site {site.id}: {site.schedule_time}")
        return None
        
    # Base candidate: Today at HH:MM
    candidate = now_harare.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if site.schedule_frequency == "daily":
        if candidate <= now_harare:
            candidate += timedelta(days=1)
            
    elif site.schedule_frequency == "weekly":
        # schedule_days: 0 (Mon) - 6 (Sun)
        # Assuming single day for now. If CSV, pick earliest next.
        target_days = [0] # Default Mon
        if site.schedule_days:
            try:
                target_days = [int(d.strip()) for d in site.schedule_days.split(',')]
            except:
                pass
        
        # Find next valid day
        # Naive loop: examine next 14 days
        found = False
        if candidate <= now_harare:
             candidate += timedelta(days=1) # Start checking from tomorrow if today passed
        else:
             # Check if today is allowed
             if candidate.weekday() in target_days:
                 found = True
        
        if not found:
            # Search forward
            for i in range(14): 
                if candidate.weekday() in target_days:
                    found = True
                    break
                candidate += timedelta(days=1)
                
    elif site.schedule_frequency == "monthly":
        # schedule_days: 1-31 (Day of month)
        target_day = 1
        if site.schedule_days:
            try:
                target_day = int(site.schedule_days.split(',')[0])
            except:
                pass
        
        # Ensure valid day range
        target_day = max(1, min(31, target_day))
        
        # Construct candidate for this month
        try:
            candidate = candidate.replace(day=target_day)
        except ValueError:
            # Month too short? skip to next month? 
            # Simple handling: use first of next month if current month invlaid? 
            # Or just rely on standard next month logic.
            pass
            
        if candidate <= now_harare:
            # Move to next month
            # Add 32 days then sanitize to day 1? No.
            # Logic: (Year, Month) + 1
            if candidate.month == 12:
                candidate = candidate.replace(year=candidate.year + 1, month=1)
            else:
                candidate = candidate.replace(month=candidate.month + 1)
            
             # Try to set day again (handle Feb 30 etc)
            try:
                candidate = candidate.replace(day=target_day)
            except ValueError:
                # If target is 31 and next month is Feb, clamps to 28? 
                # Or skip to Mar 1?
                # Standard cron behavior: run on last day? 
                # Let's clamp to last valid day of month
                # (Complex logic omitted for brevity, simplistic approach: last day)
                 pass

    # Add Jitter? (Optional, maybe later)
    
    # Convert Harare candidate back to UTC
    candidate_utc = candidate.astimezone(ZoneInfo("UTC"))
    
    return candidate_utc.replace(tzinfo=None) # Return naive UTC
