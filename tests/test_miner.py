import pytest
import bittensor as bt
from unittest.mock import MagicMock, patch
from neurons.miner import Miner
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant

@pytest.fixture
def mock_bittensor_setup(monkeypatch):
    """Mocks bittensor setup to prevent actual network/wallet calls during init."""
    monkeypatch.setattr(bt, "Subtensor", MagicMock())
    monkeypatch.setattr(bt, "Wallet", MagicMock())
    monkeypatch.setattr(bt, "Axon", MagicMock())
    monkeypatch.setattr(bt.logging, "info", MagicMock())
    monkeypatch.setattr(bt.logging, "error", MagicMock())
    monkeypatch.setattr("template.base.miner.BaseMinerNeuron.__init__", MagicMock(return_value=None))
    
@pytest.mark.anyio
async def test_miner_forward_pass(mock_bittensor_setup):
    # Setup miner
    miner = Miner()
    # Mocking the initialization that base miner would normally do
    miner.config = MagicMock()
    miner.axon = MagicMock()
    miner.wallet = MagicMock()
    
    # Setup challenge
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x0", gas_price="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    challenge = Challenge(chain_id="1", block_number="123124", tx=tx, invariants=[inv])
    
    # Test forward
    result_synapse = await miner.forward(challenge)
    
    # Check that output was populated (by the mock engine, it should be [1])
    assert result_synapse.output == [1]

@pytest.mark.anyio
async def test_miner_forward_engine_failure(mock_bittensor_setup, monkeypatch):
    # Setup miner
    miner = Miner()
    
    # Force the engine to raise an exception
    def mock_execute_raise(*args, **kwargs):
        raise Exception("Engine failure")
        
    monkeypatch.setattr(miner.engine, "execute_checks", mock_execute_raise)
    
    # Setup challenge
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x0", gas_price="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    challenge = Challenge(chain_id="1", block_number="123124", tx=tx, invariants=[inv])
    
    # Test forward
    result_synapse = await miner.forward(challenge)
    
    # Check that output gracefully returns empty list on failure
    assert result_synapse.output == []
