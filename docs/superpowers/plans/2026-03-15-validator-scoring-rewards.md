# Validator Scoring & Rewards Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the consensus-based scoring logic to evaluate miners based on their throughput, accuracy, and latency, calculating $S_i$ at the end of the epoch.

**Architecture:** 
- Add `miner_stats` tracking and epoch reset logic to `Validator` class.
- Update `forward` in `template/validator/forward.py` to determine consensus and update `miner_stats` (throughput, true positives, total tasks, latency).
- Update `get_rewards` in `template/validator/reward.py` to calculate $S_i$ based on the formula using the maintained stats.

**Tech Stack:** Python, Numpy, Bittensor.

---

## Chunk 1: Validator State Initialization

### Task 1: Initialize Miner Stats in Validator

**Files:**
- Modify: `neurons/validator.py`
- Create: `tests/test_validator_state.py`

- [ ] **Step 1: Write the failing test for miner_stats initialization**

Create `tests/test_validator_state.py`:
```python
import pytest
from unittest.mock import MagicMock
from neurons.validator import Validator

@pytest.fixture
def mock_bittensor_setup(monkeypatch):
    monkeypatch.setattr("bittensor.subtensor", MagicMock())
    monkeypatch.setattr("bittensor.wallet", MagicMock())
    monkeypatch.setattr("bittensor.axon", MagicMock())
    monkeypatch.setattr("bittensor.logging", MagicMock())
    monkeypatch.setattr("template.base.validator.BaseValidatorNeuron.__init__", MagicMock(return_value=None))

def test_validator_initializes_miner_stats(mock_bittensor_setup):
    validator = Validator()
    assert hasattr(validator, "miner_stats")
    assert isinstance(validator.miner_stats, dict)
    
    # Test reset logic
    validator.miner_stats[0] = {"total_tasks": 1}
    validator.reset_miner_stats()
    assert len(validator.miner_stats) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validator_state.py -v`
Expected: FAIL if methods/properties are missing.

- [ ] **Step 3: Write minimal implementation**

Modify `neurons/validator.py`:

Locate the `__init__` method and add the initialization. Add `reset_miner_stats` method.
```python
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

        self.miner_stats = {}

    def reset_miner_stats(self):
        """Resets the miner statistics for the next epoch."""
        bt.logging.info("Resetting miner stats for the new epoch.")
        self.miner_stats = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_validator_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add neurons/validator.py tests/test_validator_state.py
git commit -m "feat: initialize miner_stats in validator"
```

## Chunk 2: Consensus Logic in Forward Pass

### Task 2: Implement Consensus and Stats Updating

**Files:**
- Modify: `template/validator/forward.py`
- Create: `tests/test_validator_forward.py`

- [ ] **Step 1: Write the failing test for consensus logic**

Create `tests/test_validator_forward.py`:
```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant

@pytest.mark.asyncio
async def test_forward_consensus_and_stats():
    # Setup mock validator
    validator = MagicMock()
    validator.miner_stats = {}
    validator.dendrite = AsyncMock()
    
    # Setup mock responses
    inv1 = Invariant(contract="0x1", type="mint", target="100", storage="0x0", storage_slot_type="uint256")
    payload = TransactionPayload(
        type="0x0", chainId="0x01", nonce="0x0", gasPrice="0x0",
        gas="0x0", to="0x0", value="0x0", input="0x0", r="0x0", s="0x0", v="0x0",
        hash="0x0", blockHash="0x0", blockNumber="0x0",
        transactionIndex="0x0", from_address="0x0"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validator_forward.py -v`
Expected: FAIL because `forward.py` lacks consensus logic or fails to update stats.

- [ ] **Step 3: Implement consensus logic in forward**

Modify `template/validator/forward.py`:
In the `forward` function, after getting `synapses = await self.dendrite(...)`, add:
```python
    # 5. Process responses and update stats
    num_invariants = len(challenge.invariants)
    responses = [syn.deserialize() for syn in synapses]
    latencies = [syn.dendrite.process_time for syn in synapses]

    # Calculate Consensus for each invariant
    ground_truth = []
    for i in range(num_invariants):
        votes = {0: 0, 1: 0}
        for resp in responses:
            if resp and len(resp) > i:
                vote = resp[i]
                if vote in votes:
                    votes[vote] += 1
        
        # Determine 66% consensus
        total_votes = sum(votes.values())
        consensus_status = None
        if total_votes > 0:
            for status, count in votes.items():
                if count / total_votes >= 0.66:
                    consensus_status = status
                    break
        ground_truth.append(consensus_status)

    # Update Miner Stats
    for idx, uid in enumerate(miner_uids):
        if uid not in self.miner_stats:
            self.miner_stats[uid] = {
                "processed_tx_hashes": set(),
                "true_positives": 0,
                "total_tasks": 0,
                "latencies": []
            }
        
        stats = self.miner_stats[uid]
        resp = responses[idx]
        latency = latencies[idx]

        if resp:
            stats["processed_tx_hashes"].add(challenge.tx.hash)
            if latency is not None:
                stats["latencies"].append(latency)
            
            for i in range(num_invariants):
                if len(resp) > i:
                    stats["total_tasks"] += 1
                    if ground_truth[i] is not None and resp[i] == ground_truth[i]:
                        stats["true_positives"] += 1

    # 6. Score responses based on cumulative epoch stats
    rewards = get_rewards(self, miner_uids=miner_uids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_validator_forward.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add template/validator/forward.py tests/test_validator_forward.py
git commit -m "feat: implement consensus and stat tracking in forward"
```

## Chunk 3: Reward Calculation Logic

### Task 3: Implement Scoring Formula

**Files:**
- Modify: `template/validator/reward.py`
- Create: `tests/test_reward_logic.py`

- [ ] **Step 1: Write the failing test for reward logic**

Create `tests/test_reward_logic.py`:
```python
import pytest
import numpy as np
from unittest.mock import MagicMock
from template.validator.reward import get_rewards, reward

def test_reward_formula():
    stats = {
        "processed_tx_hashes": {"0x1", "0x2"}, # N_i = 2
        "true_positives": 4, 
        "total_tasks": 5, # A_i = 0.8
        "latencies": [1.0, 2.0, 3.0] # 99th percentile around 3.0s = 3000ms
    }
    # T_TARGET = 5000.0, so L_99 multiplier = (5000/3000) = 1.666
    # Score = 2^1 * 0.8^1 * 1.666^1 = 2.666
    score = reward(stats)
    assert score > 0
    assert isinstance(score, float)

def test_get_rewards_returns_array():
    validator = MagicMock()
    validator.miner_stats = {
        0: {"processed_tx_hashes": {"0x1"}, "true_positives": 1, "total_tasks": 1, "latencies": [1.0]},
        1: {"processed_tx_hashes": set(), "true_positives": 0, "total_tasks": 0, "latencies": []}
    }
    rewards = get_rewards(validator, [0, 1])
    assert len(rewards) == 2
    assert isinstance(rewards, np.ndarray)
    assert rewards[0] > rewards[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reward_logic.py -v`
Expected: FAIL because `reward.py` has dummy implementation.

- [ ] **Step 3: Implement `get_rewards` logic**

Modify `template/validator/reward.py`:
```python
import numpy as np
from typing import List

ALPHA = 1.0
BETA = 1.0
GAMMA = 1.0
T_TARGET = 5000.0

def reward(uid_stats: dict) -> float:
    """
    Reward calculation based on the cumulative stats of a miner.
    S_i = (N_i)^alpha * (A_i)^beta * (T_target / L_99,i)^gamma
    """
    processed_tx_hashes = uid_stats.get("processed_tx_hashes", set())
    true_positives = uid_stats.get("true_positives", 0)
    total_tasks = uid_stats.get("total_tasks", 0)
    latencies = uid_stats.get("latencies", [])

    n_i = len(processed_tx_hashes)
    a_i = true_positives / total_tasks if total_tasks > 0 else 0.0

    if not latencies:
        l_99 = T_TARGET
    else:
        l_99 = np.percentile(latencies, 99) * 1000.0

    if l_99 <= 0:
        l_99 = 1.0

    score = (n_i**ALPHA) * (a_i**BETA) * ((T_TARGET / l_99) ** GAMMA)
    return float(score)

def get_rewards(self, miner_uids: List[int]) -> np.ndarray:
    """Returns an array of rewards for the given miner UIDs."""
    rewards = []
    for uid in miner_uids:
        uid_stats = self.miner_stats.get(uid, {})
        rewards.append(reward(uid_stats))
    return np.array(rewards)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reward_logic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add template/validator/reward.py tests/test_reward_logic.py
git commit -m "feat: implement scoring formula in reward.py"
```
