# Challenge Synapse Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Pydantic-based `Challenge` synapse for the BitDefense protocol.

**Architecture:** Define `TransactionPayload`, `Transaction`, `Invariant`, and `Challenge` models in `template/protocol.py`. Add testing for serialization and deserialization in `tests/test_protocol.py`.

**Tech Stack:** Python, Pydantic, Bittensor.

---

## Chunk 1: Protocol Implementation

### Task 1: Implement Challenge Models and Synapse

**Files:**
- Modify: `template/protocol.py`
- Create: `tests/test_protocol.py`

- [ ] **Step 1: Write the failing test for Challenge synapse initialization and deserialization**

Create `tests/test_protocol.py` with the following content:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_protocol.py -v`
Expected: FAIL due to missing imports (`TransactionPayload`, etc. not defined).

- [ ] **Step 3: Write minimal implementation**

Modify `template/protocol.py`. Replace the `Dummy` class with the new protocol classes:

```python
import typing
import bittensor as bt
from pydantic import BaseModel, Field

class TransactionPayload(BaseModel):
    model_config = {"populate_by_name": True}
    
    type: str
    chainId: str
    nonce: str
    gasPrice: str
    gas: str
    to: str
    value: str
    input: str
    r: str
    s: str
    v: str
    hash: str
    blockHash: str
    blockNumber: str
    transactionIndex: str
    from_address: str = Field(alias="from")

class Transaction(BaseModel):
    hash: str
    payload: TransactionPayload

class Invariant(BaseModel):
    contract: str
    type: str
    target: str
    storage: str

class Challenge(bt.Synapse):
    """
    The BitDefense Challenge protocol representation.
    """
    chain_id: str
    tx: Transaction
    invariants: typing.List[Invariant]

    output: typing.Optional[typing.List[int]] = None

    def deserialize(self) -> typing.List[int]:
        """
        Deserialize the challenge output. 
        Returns an empty list if output is None.
        """
        if self.output is None:
            return []
        return self.output
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_protocol.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add template/protocol.py tests/test_protocol.py
git commit -m "feat: implement Challenge synapse protocol"
```