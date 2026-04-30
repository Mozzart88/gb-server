from src.filler import fill_missing_rates
from src.scheduler import start_scheduler
from src.cleanup import start_handshake_cleanup
from src.server import app
import asyncio
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


async def main():
    print("[App] Initializing Python rewrite...")

    # Run filler in background (non-blocking)
    asyncio.create_task(fill_missing_rates())

    # Start the scheduler in background
    asyncio.create_task(start_scheduler())

    # Start the handshake cleanup in background
    asyncio.create_task(start_handshake_cleanup())

    # Start the FastAPI server (blocking)
    # Server should send CORS headers
    config = uvicorn.Config(
        app, host="0.0.0.0", port=int(os.getenv("PORT", 3000)), log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[App] Shutting down...")
