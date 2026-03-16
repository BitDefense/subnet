import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant

@pytest.mark.anyio
async def test_forward_consensus_and_stats():
    # Setup mock validator
    validator = MagicMock()
    validator.miner_stats = {}
    validator.dendrite = AsyncMock()
    
    # Setup mock responses
    inv1 = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x47", gasPrice="0x2206f00",
        gas="0x45089", to="0x81d4", value="0x0", input="0x57ec",
        r="0xc30a", s="0x325f", v="0x14985", hash="0x0",
        blockHash="0x0", blockNumber="0x0", transactionIndex="0x0",
        from_address="0x3eeb"
    )
    tx = Transaction(hash="0xabc123", payload=payload)
    challenge = Challenge(chain_id="1", block_number="10", tx=tx, invariants=[inv1])
    
    # Mock synapses
    syn0 = MagicMock()
    syn0.deserialize.return_value = [1]
    syn0.dendrite.process_time = 1.0
    
    syn1 = MagicMock()
    syn1.deserialize.return_value = [1]
    syn1.dendrite.process_time = 2.0
    
    syn2 = MagicMock()
    syn2.deserialize.return_value = [0]
    syn2.dendrite.process_time = 3.0
    
    validator.dendrite.return_value = [syn0, syn1, syn2]
    
    with patch("template.validator.forward.get_random_uids", return_value=[0, 1, 2]), \
         patch("template.validator.forward.load_challenge_from_json", return_value=challenge), \
         patch("template.validator.forward.get_rewards", return_value=[1.0, 1.0, 0.0]):
        
        from template.validator.forward import forward
        await forward(validator)
        
    assert validator.miner_stats[0]["true_positives"] == 1
    assert validator.miner_stats[0]["total_tasks"] == 1
    assert "0xabc123" in validator.miner_stats[0]["processed_tx_hashes"]
    assert validator.miner_stats[0]["latencies"] == [1.0]
    
    assert validator.miner_stats[2]["true_positives"] == 0
    assert validator.miner_stats[2]["total_tasks"] == 1
