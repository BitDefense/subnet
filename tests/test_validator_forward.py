import pytest
import bittensor as bt
import json
import os
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from template.validator.forward import forward
from template.protocol import Challenge

@pytest.fixture
def mock_validator():
    validator = MagicMock()
    validator.metagraph = MagicMock()
    validator.metagraph.n.item.return_value = 10
    validator.metagraph.axons = [MagicMock() for _ in range(10)]
    validator.config = MagicMock()
    validator.config.neuron.vpermit_tao_limit = 1000
    validator.dendrite = AsyncMock()
    validator.step = 0
    validator.update_scores = MagicMock()
    return validator

@pytest.mark.anyio
async def test_forward_logic_picks_k_miners(mock_validator):
    # Sample data that matches challenge_example.json structure
    sample_challenge = {
        "chain_id": 1,
        "block_number": 24642610,
        "tx": {
            "hash": "0x473e",
            "payload": {
                "type": "0x0", "chainId": "0x01", "nonce": "0x47", "gasPrice": "0x2206f00",
                "gas": "0x45089", "to": "0x81d4", "value": "0x0", "input": "0x57ec",
                "r": "0xc30a", "s": "0x325f", "v": "0x14985", "hash": "0x473e",
                "blockHash": "0x678e", "blockNumber": "0x191d5486", "transactionIndex": "0x4",
                "from": "0x3eeb"
            }
        },
        "invariants": [
            {"contract": "0x81d4", "type": "debt", "target": "80.0", "storage": "0x123e"}
        ]
    }
    
    # Mock get_random_uids and get_rewards
    with patch("template.validator.forward.get_random_uids") as mock_get_uids, \
         patch("template.validator.forward.get_rewards") as mock_get_rewards, \
         patch("builtins.open", mock_open(read_data=json.dumps(sample_challenge))):
        
        mock_get_uids.return_value = [1, 2, 3] # simulate picking 3 miners
        mock_get_rewards.return_value = [1.0, 1.0, 1.0]
        
        await forward(mock_validator)
        
        # Verify k was chosen from [3, 5, 7, 9]
        args, kwargs = mock_get_uids.call_args
        assert kwargs["k"] in [3, 5, 7, 9]
        
        # Verify dendrite was called with 10s timeout
        mock_validator.dendrite.assert_called_once()
        _, dendrite_kwargs = mock_validator.dendrite.call_args
        assert dendrite_kwargs["timeout"] == 10.0
        assert isinstance(dendrite_kwargs["synapse"], Challenge)
        # Verify block_number was correctly loaded
        assert dendrite_kwargs["synapse"].block_number == "24642610"
