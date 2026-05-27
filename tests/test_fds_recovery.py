# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Alexey

import pytest
from unittest.mock import AsyncMock, MagicMock
from miband_tracker.fds import download_and_decrypt_sleep_details
from mi_fitness.exceptions import APIError

@pytest.mark.asyncio
async def test_download_and_decrypt_sleep_details_recovery_with_sid() -> None:
    client = MagicMock()
    client.auth.token.device_id = "old_did"
    
    # Mock first call failing with code -6
    # Mock second call (with sid) succeeding
    client._request = AsyncMock()
    client._request.side_effect = [
        APIError("device not exist", code=-6),
        {"result": {"suffix_sha1_1700000000": {"url": "http://example.com", "obj_key": "key"}}}
    ]
    
    # We need to mock httpx to avoid actual network calls
    with MagicMock() as mock_httpx:
        # This is tricky because fds.py uses httpx.AsyncClient() as context manager
        pass

    # Actually, let's just test that the retry logic is called with the right parameters
    # We'll stop before the actual HTTP download by making the first success return no URL or something
    
    relative_uid = 12345
    timestamp = 1700000000
    timezone = 60
    
    # Mock get_devices to return empty
    client.get_devices = AsyncMock(return_value=[])

    try:
        await download_and_decrypt_sleep_details(
            client,
            relative_uid,
            timestamp,
            timezone,
            log_fn=lambda x: None
        )
    except Exception:
        # It will fail later at HTTP download, but we want to check _request calls
        pass

    assert client._request.call_count == 2
    # First call with old_did
    assert client._request.call_args_list[0][1]["params"]["did"] == "old_did"
    # Second call with sid (12345)
    assert client._request.call_args_list[1][1]["params"]["did"] == "12345"

@pytest.mark.asyncio
async def test_download_and_decrypt_sleep_details_recovery_with_device_list() -> None:
    client = MagicMock()
    client.auth.token.device_id = "old_did"
    relative_uid = 12345
    sid = str(relative_uid)
    
    # Mock first call failing with code -6
    # Mock second call (with sid) failing with code -6
    # Mock third call (with real_did) succeeding
    client._request = AsyncMock()
    client._request.side_effect = [
        APIError("device not exist", code=-6), # attempt 1: old_did
        APIError("device not exist", code=-6), # attempt 2: sid
        {"result": {"some_key": {"url": "http://example.com"}}} # attempt 3: real_did
    ]
    
    # Mock get_devices to return a real device
    real_device = MagicMock()
    real_device.did = "real_did"
    real_device.name = "My Band"
    client.get_devices = AsyncMock(return_value=[real_device])

    try:
        await download_and_decrypt_sleep_details(
            client,
            relative_uid,
            1700000000,
            60,
            log_fn=lambda x: None
        )
    except Exception:
        pass

    # Total calls: 1 (original) + 1 (sid) + 1 (real_did) = 3
    assert client._request.call_count == 3
    assert client._request.call_args_list[0][1]["params"]["did"] == "old_did"
    assert client._request.call_args_list[1][1]["params"]["did"] == sid
    assert client._request.call_args_list[2][1]["params"]["did"] == "real_did"
