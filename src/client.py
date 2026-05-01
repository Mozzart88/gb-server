import os
import httpx
from datetime import datetime
from .db import db

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("CURRENCY_API_BASE_URL", "https://api.currencybeacon.com/v1")


# api_key should be in headers not in parameters
async def fetch_rates_for_date(date: str):
    if not API_KEY:
        raise ValueError("API_KEY environment variable is not set")

    url = f"{BASE_URL}/historical"
    params = {"date": date}
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "rates" not in data:
                raise ValueError("Invalid response format: rates missing")

            db.save_rates(data["rates"], date)
            print(f"[{datetime.now().isoformat()}] Successfully fetched and saved rates for {date}")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error fetching rates for {date}: {e}")


# api_key should be in headers not in parameters
async def fetch_latest_rates():
    if not API_KEY:
        raise ValueError("API_KEY environment variable is not set")

    url = f"{BASE_URL}/latest"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "rates" not in data:
                raise ValueError("Invalid response format: rates missing")

            db.save_rates(data["rates"])
            print(f"[{datetime.now().isoformat()}] Successfully fetched and saved latest rates")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error fetching latest rates: {e}")
