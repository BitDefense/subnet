# Consolidated Neuron Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate miner and validator logic from fragmented template files into single, self-contained `neurons/miner.py` and `neurons/validator.py` files.

**Architecture:** Merge `BaseNeuron`, `BaseMinerNeuron`/`BaseValidatorNeuron`, and business logic (engine, forward, reward) into unified `Miner` and `Validator` classes. Keep `template.protocol` as a shared dependency.

**Tech Stack:** Python, Bittensor SDK, NumPy, Pydantic, asyncio.

---

### Task 1: Consolidated Miner Implementation

**Files:**
- Modify: `neurons/miner.py`
- Test: `tests/test_miner.py`

- [ ] **Step 1: Write a baseline test for the new Miner structure**

```python
import pytest
from neurons.miner import Miner
import bittensor as bt

def test_miner_initialization():
    config = bt.Config()
    config.mock = True
    config.netuid = 1
    config.wallet = bt.Config()
    config.wallet.name = "mock_wallet"
    config.wallet.hotkey = "mock_hotkey"
    miner = Miner(config=config)
    assert miner.neuron_type == "MinerNeuron"
    assert hasattr(miner, 'engine')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_miner.py -v`
Expected: FAIL

- [ ] **Step 3: Flatten `InvariantsCheckEngine` and `MockSafeOnlyInvariantsCheckEngine` into `neurons/miner.py`**
Define the base class and mock implementation at the top of the file.

- [ ] **Step 4: Flatten essential utilities from `template/utils/` and `template/base/`**
Move `ttl_get_block`, `ttl_cache`, `add_args`, `config`, and `check_config` into `neurons/miner.py`.

- [ ] **Step 5: Merge `BaseNeuron` and `BaseMinerNeuron` logic into the `Miner` class**
Include `__init__`, `run`, `sync`, `resync_metagraph`, `check_registered`, `should_sync_metagraph`, and `should_set_weights`. **Note:** Handle `spec_version` by defining it locally or importing from `template`.

- [ ] **Step 6: Implement Miner-specific logic (`forward`, `blacklist`, `priority`)**
Ensure `forward` uses the local `MockSafeOnlyInvariantsCheckEngine`.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_miner.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add neurons/miner.py tests/test_miner.py
git commit -m "feat: consolidate miner logic into neurons/miner.py"
```

---

### Task 2: Consolidated Validator Implementation

**Files:**
- Modify: `neurons/validator.py`
- Test: `tests/test_validator_forward.py`

- [ ] **Step 1: Write a baseline test for the new Validator structure**

```python
import pytest
from neurons.validator import Validator
import bittensor as bt

def test_validator_initialization():
    config = bt.Config()
    config.mock = True
    config.netuid = 1
    validator = Validator(config=config)
    assert validator.neuron_type == "ValidatorNeuron"
    assert hasattr(validator, 'scores')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validator_forward.py -v`
Expected: FAIL

- [ ] **Step 3: Flatten essential utilities and weight helpers**
Move `get_random_uids`, `process_weights_for_netuid`, `convert_weights_and_uids_for_emit`, `add_args`, `config`, and `check_config` into `neurons/validator.py`.

- [ ] **Step 4: Merge `BaseNeuron` and `BaseValidatorNeuron` logic into the `Validator` class**
Include `__init__`, `run`, `sync`, `resync_metagraph`, `check_registered`, `set_weights`, and `update_scores`. **Critical:** Initialize `self.miner_stats = {}` in `__init__`.

- [ ] **Step 5: Implement persistence methods (`save_state`, `load_state`)**
Ensure `self.scores`, `self.hotkeys`, and `self.miner_stats` are all saved to and loaded from `state.npz`.

- [ ] **Step 6: Implement Validator-specific methods (`forward`, `reward`, `get_rewards`)**
**Critical:** Align with spec (66% consensus, k=3,5,7,9). Update `load_challenge_from_json` to handle paths relative to `neurons/`.

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_validator_forward.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add neurons/validator.py tests/test_validator_forward.py
git commit -m "feat: consolidate validator logic into neurons/validator.py"
```

---

### Task 3: Cleanup and Verification

**Files:**
- Modify: `template/__init__.py`
- Delete: `template/base/`, `template/validator/`, `template/engine/`, `template/utils/`

- [ ] **Step 1: Remove redundant directories/files**

Run: `rm -rf template/base/ template/validator/ template/engine/ template/utils/`

- [ ] **Step 2: Update `template/__init__.py` to remove dead references**
Ensure it only exports `__version__`, `spec_version`, and any remaining shared modules like `protocol`.

- [ ] **Step 3: Run full test suite to ensure no regressions**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Final Commit**

```bash
git add .
git commit -m "cleanup: remove redundant template files after consolidation"
```
