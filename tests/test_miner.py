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
    monkeypatch.setattr(bt.logging, "set_config", MagicMock())
    monkeypatch.setattr(bt.logging, "warning", MagicMock())
    
@pytest.mark.anyio
async def test_miner_forward_pass(mock_bittensor_setup):
    # Setup miner
    with patch("neurons.miner.Miner.check_registered", return_value=None):
        miner = Miner()
    
    # Mocking necessary components
    miner.metagraph = MagicMock()
    miner.metagraph.hotkeys = ["mock_hotkey"]
    miner.wallet.hotkey.ss58_address = "mock_hotkey"
    miner.uid = 0
    
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
    with patch("neurons.miner.Miner.check_registered", return_value=None):
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

@pytest.mark.anyio
async def test_miner_blacklist_unrecognized_hotkey(mock_bittensor_setup):
    # Setup miner
    with patch("neurons.miner.Miner.check_registered", return_value=None):
        miner = Miner()
    
    # Mock metagraph index to raise ValueError
    miner.metagraph = MagicMock()
    miner.metagraph.hotkeys.index.side_effect = ValueError("Not found")
    
    # Setup challenge with a mock hotkey
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x0", gas_price="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    synapse = Challenge(chain_id="1", block_number="123124", tx=tx, invariants=[])
    synapse.dendrite = {"hotkey": "unknown_hotkey"}
    
    # Test blacklist
    blacklisted, message = await miner.blacklist(synapse)
    
    # Check results
    assert blacklisted is True
    assert message == "Unrecognized hotkey"

def test_miner_standalone_attributes():
    # This test will eventually verify that the Miner class has all necessary methods
    # after flattening. For now, it might fail or pass depending on mocking.
    # We use a mock config to avoid real network calls if it's not yet flattened.
    with patch("bittensor.Wallet"), patch("bittensor.Subtensor"), patch("bittensor.Metagraph"):
        miner = Miner()
        assert hasattr(miner, 'run')
        assert hasattr(miner, 'sync')
        assert hasattr(miner, 'resync_metagraph')
        assert hasattr(miner, 'check_registered')
        assert hasattr(miner, 'should_sync_metagraph')
        assert hasattr(miner, 'should_set_weights')
