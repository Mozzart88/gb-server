import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from src.scheduler import get_last_window_start, check_and_trigger

@pytest.mark.parametrize("now_hour, now_minute, expected_hour", [
    (11, 0, 10),  # After 10am, before 6pm -> 10am
    (19, 0, 18),  # After 6pm -> 6pm
    (9, 0, 18),   # Before 10am -> 6pm yesterday
])
def test_get_last_window_start(now_hour, now_minute, expected_hour):
    now = datetime(2025, 1, 20, now_hour, now_minute, tzinfo=timezone.utc)
    window_start = get_last_window_start(now)
    assert window_start.hour == expected_hour
    if now_hour < 10:
        assert window_start.day == 19
    else:
        assert window_start.day == 20

@pytest.mark.asyncio
@patch("src.scheduler.db")
@patch("src.scheduler.fetch_latest_rates", new_callable=AsyncMock)
async def test_check_and_trigger_fetches_if_missing(mock_fetch, mock_db):
    # Setup: No data in DB since window_start
    mock_cursor = MagicMock()
    mock_db.conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    
    await check_and_trigger()
    
    mock_fetch.assert_called_once()

@pytest.mark.asyncio
@patch("src.scheduler.db")
@patch("src.scheduler.fetch_latest_rates", new_callable=AsyncMock)
async def test_check_and_trigger_skips_if_present(mock_fetch, mock_db):
    # Setup: Data ALREADY exists in DB since window_start
    mock_cursor = MagicMock()
    mock_db.conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)
    
    await check_and_trigger()
    
    mock_fetch.assert_not_called()
