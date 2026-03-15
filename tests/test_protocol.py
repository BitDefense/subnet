import pytest
from template.protocol import TransactionPayload, Transaction, Invariant, Challenge

def test_challenge_synapse_deserialization():
    # Setup
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x47", gasPrice="0x2206f00",
        gas="0x45089", to="0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
        value="0x0", input="0x57ec", r="0x1", s="0x2", v="0x1b",
        hash="0xabc", blockHash="0xdef", blockNumber="0x123",
        transactionIndex="0x4", from_address="0x3eeb"
    )
    tx = Transaction(hash="0xabc", payload=payload)
    inv = Invariant(contract="0x81d", type="mint", target="100", storage="0x0")
    
    challenge = Challenge(chain_id="1", tx=tx, invariants=[inv])
    
    # Test initial deserialize (output is None)
    assert challenge.deserialize() == []
    
    # Test deserialize with output
    challenge.output = [1]
    assert challenge.deserialize() == [1]

def test_transaction_payload_from_alias():
    # Test that 'from_address' maps to 'from' when dumping
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x47", gasPrice="0x2206f00",
        gas="0x45089", to="0x81d", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0", transactionIndex="0x0",
        from_address="0x3eeb"
    )
    dumped = payload.model_dump(by_alias=True)
    assert "from" in dumped
    assert dumped["from"] == "0x3eeb"
