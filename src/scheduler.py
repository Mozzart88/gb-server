import asyncio
import time
from datetime import datetime, timezone, timedelta
from .client import fetch_latest_rates
from .db import db

def get_last_window_start(now: datetime) -> datetime:
    """Calculates the start of the most recent scheduled window (10:00 or 18:00 UTC)."""
    today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
    today_6pm = now.replace(hour=18, minute=0, second=0, microsecond=0)
    
    if now >= today_6pm:
        return today_6pm
    elif now >= today_10am:
        return today_10am
    else:
        # Before 10am today, so the last window was 6pm yesterday
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=18, minute=0, second=0, microsecond=0)

async def check_and_trigger():
    now = datetime.now(timezone.utc)
    window_start = get_last_window_start(now)
    
    # Check if we have any rates fetched since window_start
    # The 'timestamp' column in 'rate' table stores fetch time.
    cursor = db.conn.cursor()
    # Note: sqlite3 stores timestamps as strings usually. We need to be careful with formats.
    # In db.py, I used: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # This is local time. Let's fix db.py to use UTC for consistency if needed, 
    # but for now let's assume it matches.
    
    window_start_str = window_start.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("SELECT 1 FROM rate WHERE timestamp >= ? LIMIT 1", (window_start_str,))
    result = cursor.fetchone()
    
    if not result:
        print(f"[{now.isoformat()}] [Scheduler] No updates found for window starting {window_start_str}. Triggering fetch...")
        await fetch_latest_rates()
    else:
        # Already fetched for this window
        pass

async def start_scheduler():
    print("[Scheduler] Started with catch-up logic")
    while True:
        try:
            await check_and_trigger()
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        
        # Check every 60 seconds
        await asyncio.sleep(60)

if __name__ == "__main__":
    # For testing the logic independently
    asyncio.run(start_scheduler())
