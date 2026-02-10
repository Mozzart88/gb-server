import asyncio
from datetime import datetime, timedelta
from .db import db
from .client import fetch_rates_for_date

async def fill_missing_rates():
    # Get the latest date we have in the DB
    latest_rates = db.get_latest_rates()
    if not latest_rates:
        start_date_str = "2025-01-01" # Default start if empty
    else:
        start_date_str = latest_rates[0]['date']
    
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.now()
    current_date = start_date

    print(f"[Filler] Starting from {start_date_str}")

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        if not db.has_data_for_date(date_str):
            print(f"[Filler] Fetching missing rates for {date_str}")
            await fetch_rates_for_date(date_str)
            # Throttle API calls
            await asyncio.sleep(5)
        
        current_date += timedelta(days=1)

if __name__ == "__main__":
    asyncio.run(fill_missing_rates())
