# Miner Engine Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `InvariantsCheckEngine` interface, a mock engine, and integrate it into the miner's forward loop.

**Architecture:** Create an abstract base class `InvariantsCheckEngine` and a mock implementation `MockSafeOnlyInvariantsCheckEngine`. Update `Miner.forward` to use this engine to process `Challenge` synapses.

**Tech Stack:** Python, Pydantic, Bittensor.

---

## Chunk 1: Engine Interface & Mock Implementation

### Task 1: Create Engine Interface and Mock

**Files:**
- Create: `template/engine/__init__.py`
- Create: `template/engine/base.py`
- Create: `template/engine/mock.py`
- Create: `tests/engine/test_mock_engine.py`

- [ ] **Step 1: Write the failing test for the mock engine**

Create `tests/engine/test_mock_engine.py` with the following content:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/engine/test_mock_engine.py -v`
Expected: FAIL due to `ModuleNotFoundError` for `template.engine.mock`.

- [ ] **Step 3: Write minimal implementation**

Create `template/engine/__init__.py` (empty file).

Create `template/engine/base.py`:
```python
from abc import ABC, abstractmethod
from typing import List
from template.protocol import Challenge

class InvariantsCheckEngine(ABC):
    @abstractmethod
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Executes the invariant checks against the provided challenge.
        
        Args:
            challenge (Challenge): The incoming challenge synapse.
            
        Returns:
            List[int]: A list of integers (1 for safe, 0 for unsafe) corresponding 
                       to each invariant in the challenge.
        """
        pass
```

Create `template/engine/mock.py`:
```python
from typing import List
from template.protocol import Challenge
from template.engine.base import InvariantsCheckEngine

class MockSafeOnlyInvariantsCheckEngine(InvariantsCheckEngine):
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Mock implementation that always returns 1 (safe) for every invariant.
        """
        return [1] * len(challenge.invariants)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/engine/test_mock_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add template/engine tests/engine
git commit -m "feat: implement InvariantsCheckEngine and mock"
```

## Chunk 2: Miner Integration

### Task 2: Integrate Engine into Miner

**Files:**
- Modify: `neurons/miner.py`

- [ ] **Step 1: Write the failing test for the miner's forward pass**

Create `tests/test_miner.py`:
```python
import pytest
import bittensor as bt
from unittest.mock import MagicMock, patch
from neurons.miner import Miner
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant

@pytest.fixture
def mock_bittensor_setup(monkeypatch):
    """Mocks bittensor setup to prevent actual network/wallet calls during init."""
    monkeypatch.setattr(bt, "subtensor", MagicMock())
    monkeypatch.setattr(bt, "wallet", MagicMock())
    monkeypatch.setattr(bt, "axon", MagicMock())
    monkeypatch.setattr(bt.logging, "info", MagicMock())
    monkeypatch.setattr(bt.logging, "error", MagicMock())
    monkeypatch.setattr("template.base.miner.BaseMinerNeuron.__init__", MagicMock(return_value=None))
    
def test_miner_forward_pass(mock_bittensor_setup):
    # Setup miner
    miner = Miner()
    # Mocking the initialization that base miner would normally do
    miner.config = MagicMock()
    miner.axon = MagicMock()
    miner.wallet = MagicMock()
    
    # Setup challenge
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x0", gasPrice="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0",
        transactionIndex="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    challenge = Challenge(chain_id="1", tx=tx, invariants=[inv])
    
    # Test forward
    result_synapse = miner.forward(challenge)
    
    # Check that output was populated (by the mock engine, it should be [1])
    assert result_synapse.output == [1]

def test_miner_forward_engine_failure(mock_bittensor_setup, monkeypatch):
    # Setup miner
    miner = Miner()
    
    # Force the engine to raise an exception
    def mock_execute_raise(*args, **kwargs):
        raise Exception("Engine failure")
        
    monkeypatch.setattr(miner.engine, "execute_checks", mock_execute_raise)
    
    # Setup challenge
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x0", gasPrice="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0",
        transactionIndex="0x0", from_address="0x0"
    )
    tx = Transaction(hash="0x0", payload=payload)
    inv = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    challenge = Challenge(chain_id="1", tx=tx, invariants=[inv])
    
    # Test forward
    result_synapse = miner.forward(challenge)
    
    # Check that output gracefully returns empty list on failure
    assert result_synapse.output == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_miner.py -v`
Expected: FAIL because `Miner` doesn't have `self.engine` and its `forward` method is still expecting the old `Dummy` synapse.

- [ ] **Step 3: Write minimal implementation**

Modify `neurons/miner.py`. 

Add the `MockSafeOnlyInvariantsCheckEngine` import right below `from template.base.miner import BaseMinerNeuron`:
```python
from template.engine.mock import MockSafeOnlyInvariantsCheckEngine
```

Replace the `__init__` method of `Miner` to initialize the engine:
```python
    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)
        self.engine = MockSafeOnlyInvariantsCheckEngine()
```

Replace the `forward` method of `Miner`:
```python
    async def forward(
        self, synapse: template.protocol.Challenge
    ) -> template.protocol.Challenge:
        """
        Processes the incoming 'Challenge' synapse by performing invariant checks.

        Args:
            synapse (template.protocol.Challenge): The synapse object containing the transaction and invariants.

        Returns:
            template.protocol.Challenge: The synapse object with the 'output' field set.
        """
        try:
            synapse.output = self.engine.execute_checks(synapse)
        except Exception as e:
            bt.logging.error(f"Engine failed to execute checks: {e}")
            synapse.output = []
            
        return synapse
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_miner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add neurons/miner.py tests/test_miner.py
git commit -m "feat: integrate check engine into miner forward pass"
```