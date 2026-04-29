import asyncio
import os
from src.db import db

HANDSHAKE_TIMEOUT = int(os.getenv("HANDSHAKE_TIMEOUT", "3600"))


async def start_handshake_cleanup():
    while True:
        await asyncio.sleep(HANDSHAKE_TIMEOUT)
        try:
            deleted = db.delete_expired_handshakes(HANDSHAKE_TIMEOUT)
            if deleted:
                print(f"[Cleanup] Deleted {deleted} expired handshake(s)")
        except Exception as e:
            print(f"[Cleanup] Error during handshake cleanup: {e}")
