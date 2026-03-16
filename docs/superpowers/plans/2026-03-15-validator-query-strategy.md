# Validator Query Strategy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the validator query strategy: load a mock challenge from JSON, randomly select 3, 5, 7, or 9 miners, and query them in parallel with a 10s timeout.

**Architecture:** 
- Add a challenge loader utility to `template/validator/forward.py` (or a separate file if it grows).
- Modify `forward()` in `template/validator/forward.py` to pick a random $k \in \{3, 5, 7, 9\}$.
- Use `self.dendrite` for parallel querying with a 10.0s timeout.
- Inject `storage_slot_type: "uint256"` into invariants if missing.

**Tech Stack:** Python, Pydantic, Bittensor, JSON.

---

## Chunk 1: Implementation & Integration

### Task 1: Implement Challenge Loader and Random Query Logic

**Files:**
- Modify: `template/validator/forward.py`
- Create: `tests/test_validator_forward.py`

- [x] **Step 1: Write the failing test for forward logic**

Create `tests/test_validator_forward.py`:
```python
import pytest
import bittensor as bt
import json
import os
from unittest.mock import MagicMock, patch, mock_open
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
    validator.dendrite = MagicMock()
    validator.step = 0
    validator.update_scores = MagicMock()
    return validator

@pytest.mark.asyncio
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_validator_forward.py -v`
Expected: FAIL due to `ImportError` (load_challenge_from_json missing) or logic mismatch.

- [x] **Step 3: Implement challenge loader and update forward loop**

Modify `template/validator/forward.py`:

```python
import time
import json
import random
import os
import bittensor as bt
from typing import List

from template.protocol import Challenge, Transaction, TransactionPayload, Invariant
from template.validator.reward import get_rewards
from template.utils.uids import get_random_uids

def load_challenge_from_json(file_path: str = "challenge_example.json") -> Challenge:
    """
    Loads a challenge from a JSON file and injects default storage_slot_type if missing.
    """
    # Use absolute path relative to project root if relative path provided
    if not os.path.isabs(file_path):
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        file_path = os.path.join(root_dir, file_path)
        
    with open(file_path, "r") as f:
        data = json.load(f)
    
    # Inject storage_slot_type: "uint256" if missing in invariants
    for inv in data.get("invariants", []):
        if "storage_slot_type" not in inv:
            inv["storage_slot_type"] = "uint256"
            
    # Map to Pydantic models
    payload_data = data["tx"]["payload"]
    payload = TransactionPayload(**payload_data)
    
    tx = Transaction(
        hash=data["tx"]["hash"],
        payload=payload
    )
    
    invariants = [Invariant(**inv) for inv in data["invariants"]]
    
    return Challenge(
        chain_id=str(data["chain_id"]),
        block_number=str(data["block_number"]),
        tx=tx,
        invariants=invariants
    )

async def forward(self):
    """
    The forward function is called by the validator every time step.
    It picks 3, 5, 7, or 9 miners and queries them with a challenge.
    """
    # 1. Randomly choose k from [3, 5, 7, 9]
    k = random.choice([3, 5, 7, 9])
    
    # 2. Get k random miner UIDs
    miner_uids = get_random_uids(self, k=k)
    bt.logging.info(f"Querying {len(miner_uids)} miners (k={k})")

    # 3. Load challenge from JSON
    try:
        challenge = load_challenge_from_json("challenge_example.json")
    except Exception as e:
        bt.logging.error(f"Failed to load challenge from JSON: {e}")
        return

    # 4. Query the network in parallel
    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=challenge,
        timeout=10.0,
        deserialize=True,
    )

    bt.logging.info(f"Received responses: {responses}")

    # 5. Score responses
    # responses is a list of results (List[int] or [] if failed)
    rewards = get_rewards(self, query=self.step, responses=responses)

    bt.logging.info(f"Scored responses: {rewards}")
    
    # 6. Update scores
    self.update_scores(rewards, miner_uids)
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_validator_forward.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add template/validator/forward.py tests/test_validator_forward.py
git commit -m "feat: implement validator query strategy with random miner selection"
```
