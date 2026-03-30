import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from neurons.validator.defense import TelegramAlertAction, PauseAgentAction

@pytest.mark.asyncio
async def test_telegram_alert_action_success():
    action_data = {
        "type": "TELEGRAM_ALERT",
        "tg_api_key": "test_bot_token",
        "tg_chat_id": "test_chat_id"
    }
    inv_context = {
        "contract": "0x123",
        "variable": "balance",
        "type": ">",
        "target": "100",
        "network": "ethereum"
    }
    action = TelegramAlertAction(action_data)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        await action.execute(inv_context)
        
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "test_bot_token" in args[0]
        assert kwargs["json"]["chat_id"] == "test_chat_id"
        assert "0x123" in kwargs["json"]["text"]

@pytest.mark.asyncio
async def test_pause_agent_action_success():
    action_data = {
        "type": "PAUSE_AGENT",
        "role_id": "0xAdmin",
        "function_sig": "pause()",
        "calldata": "0x842e5792",
        "network": "ethereum"
    }
    inv_context = {"contract": "0xContractAddress"}
    rpc_url = "http://localhost:8545"
    private_key = "0x" + "a" * 64
    
    action = PauseAgentAction(action_data, rpc_url, private_key)
    
    with patch("neurons.validator.defense.Web3") as mock_web3:
        # Mock HTTPProvider to avoid isinstance check failure if Web3 uses it
        mock_web3.HTTPProvider = MagicMock()
        
        mock_w3_instance = mock_web3.return_value
        mock_eth = mock_w3_instance.eth
        mock_eth.account.from_key.return_value.address = "0xMyAddress"
        mock_eth.get_transaction_count.return_value = 0
        mock_eth.gas_price = 20000000000
        mock_eth.chain_id = 1
        
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b"signed_tx"
        mock_eth.account.sign_transaction.return_value = mock_signed_tx
        
        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xTxHash"
        mock_eth.send_raw_transaction.return_value = mock_tx_hash
        
        await action.execute(inv_context)
        
        assert mock_eth.send_raw_transaction.called
        mock_eth.account.sign_transaction.assert_called_once()
        mock_eth.send_raw_transaction.assert_called_once_with(b"signed_tx")
