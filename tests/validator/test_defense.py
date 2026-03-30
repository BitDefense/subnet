# The MIT License (MIT)
# Copyright © 2026 Aleksei Gubin

import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch
from neurons.validator.defense import DefenseManager, TelegramAlertAction, PauseAgentAction


@pytest.mark.asyncio
async def test_defense_manager_fetch_and_create():
    platform_url = "http://localhost:8000"
    eth_rpc_url = "http://localhost:8545"
    manager = DefenseManager(platform_url, eth_rpc_url=eth_rpc_url)

    action_id = 1
    mock_action_data = {
        "id": action_id,
        "type": "TELEGRAM_ALERT",
        "network": "ethereum",
        "tg_chat_id": "123456",
    }

    from unittest.mock import MagicMock
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_action_data
        
        mock_client.get.return_value = mock_response

        # Test fetching
        fetched_data = await manager.fetch_defense_action(action_id)
        assert fetched_data == mock_action_data
        assert action_id in manager.actions_cache

        # Test creation
        action = manager.create_action(fetched_data)
        assert isinstance(action, TelegramAlertAction)
        assert action.type == "TELEGRAM_ALERT"


@pytest.mark.asyncio
async def test_defense_manager_pause_action():
    manager = DefenseManager("http://localhost:8000", eth_rpc_url="http://localhost:8545")
    mock_action_data = {
        "id": 2,
        "type": "PAUSE_AGENT",
        "network": "ethereum",
        "role_id": "0x123",
    }

    action = manager.create_action(mock_action_data)
    assert isinstance(action, PauseAgentAction)
    assert action.type == "PAUSE_AGENT"


@pytest.mark.asyncio
async def test_execute_actions():
    manager = DefenseManager("http://localhost:8000")
    action_ids = [1, 2]

    mock_actions = {
        1: {"id": 1, "type": "TELEGRAM_ALERT"},
        2: {"id": 2, "type": "PAUSE_AGENT"},
    }

    async def mock_fetch(action_id):
        return mock_actions.get(action_id)

    manager.fetch_defense_action = AsyncMock(side_effect=mock_fetch)

    # Patch execute methods
    with patch.object(TelegramAlertAction, "execute", new_callable=AsyncMock) as mock_tg_exec, \
         patch.object(PauseAgentAction, "execute", new_callable=AsyncMock) as mock_pause_exec:

        await manager.execute_actions(action_ids)

        assert mock_tg_exec.called
        assert mock_pause_exec.called
