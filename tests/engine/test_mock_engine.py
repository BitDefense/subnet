import pytest
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant
from template.engine.mock import MockSafeOnlyInvariantsCheckEngine

def test_mock_engine_returns_ones():
    # Setup
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x0", gasPrice="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0",
        transactionIndex="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv1 = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    inv2 = Invariant(contract="0x2", type="burn", target="50", storage="0x1", storage_slot_type="bool")
    
    challenge = Challenge(chain_id="1", tx=tx, invariants=[inv1, inv2])
    
    # Test
    engine = MockSafeOnlyInvariantsCheckEngine()
    result = engine.execute_checks(challenge)
    
    assert result == [1, 1]

def test_mock_engine_empty_invariants():
    # Setup
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x0", gasPrice="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0",
        transactionIndex="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    challenge = Challenge(chain_id="1", tx=tx, invariants=[])
    
    # Test
    engine = MockSafeOnlyInvariantsCheckEngine()
    result = engine.execute_checks(challenge)
    
    assert result == []
