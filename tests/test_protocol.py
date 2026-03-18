import pytest
from template.protocol import TransactionPayload, Transaction, Invariant, Challenge

def test_challenge_synapse_deserialization():
    # Setup
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x47", gas_price="0x2206f00",
        gas="0x45089", to="0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
        value="0x0", input="0x57ec", r="0x1", s="0x2", v="0x1b",
        hash="0xabc", from_address="0x3eeb"
    )
    tx = Transaction(hash="0xabc", payload=payload)
    inv = Invariant(contract="0x81d", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    
    challenge = Challenge(chain_id="1", block_number="123", tx=tx, invariants=[inv])
    
    # Test initial deserialize (output is None)
    assert challenge.deserialize() == []
    
    # Test deserialize with output
    challenge.output = [1]
    assert challenge.deserialize() == [1]

def test_transaction_payload_from_alias():
    # Test that 'from_address' maps to 'from' when dumping
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x47", gas_price="0x2206f00",
        gas="0x45089", to="0x81d", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", from_address="0x3eeb"
    )
    dumped = payload.model_dump(by_alias=True)
    assert "from" in dumped
    assert dumped["from"] == "0x3eeb"
    assert "chainId" in dumped
    assert "gasPrice" in dumped

def test_challenge_synapse_from_headers():
    # Test that we can reconstruct from dummy headers without validation errors
    payload = TransactionPayload(
        type="0x0", chain_id="0x01", nonce="0x47", gas_price="0x2206f00",
        gas="0x45089", to="0x81d", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", from_address="0x3eeb"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv = Invariant(contract="0x81d", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    
    challenge = Challenge(chain_id="1", block_number="123", tx=tx, invariants=[inv])
    headers = challenge.to_headers()
    
    # Simulate lowercasing of headers by Bittensor/HTTP
    lowercased_headers = {k.lower(): v for k, v in headers.items()}
    
    # This should not raise a ValidationError
    reconstructed = Challenge.from_headers(lowercased_headers)
    assert reconstructed.chain_id == ""  # Dummy value from headers (mapped from chainid)
    assert reconstructed.tx.hash == ""   # Dummy injected value
