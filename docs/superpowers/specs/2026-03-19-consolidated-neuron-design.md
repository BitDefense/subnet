# Design Spec: Consolidated Neuron Logic

**Date:** 2026-03-19
**Author:** Gemini CLI
**Status:** Draft

## 1. Overview
This design aims to simplify the BitDefense subnet codebase by consolidating the logic for Miners and Validators into single, self-contained files: `neurons/miner.py` and `neurons/validator.py`. Currently, logic is fragmented across `template/base/`, `template/validator/`, and `template/engine/`.

## 2. Goals
- **Simplicity:** All related logic for a neuron type in one place.
- **Standalone:** Neurons should be functional with minimal project-level dependencies (except `template.protocol`).
- **Clean Architecture:** Merge base class boilerplate directly into the primary `Miner` and `Validator` classes to remove redundant inheritance layers.

## 3. Architecture (Unified Class Structure)

### 3.1 Consolidated Miner (`neurons/miner.py`)
The `Miner` class will merge logic from `BaseNeuron`, `BaseMinerNeuron`, and the current `Miner` implementation.

**Components:**
- **`MockSafeOnlyInvariantsCheckEngine`**: Defined locally to handle invariant checks.
- **`Miner` Class Methods**:
    - `add_args`, `config`, `check_config`: Unified CLI argument parsing.
    - `__init__`: Sets up wallet, subtensor, metagraph, and Axon.
    - `forward`: Processes `Challenge` synapses using the local engine.
    - `blacklist` & `priority`: Request filtering and prioritization.
    - `run`: Main loop for serving the Axon and syncing with the chain.
    - `sync` & `resync_metagraph`: Network state management.

### 3.2 Consolidated Validator (`neurons/validator.py`)
The `Validator` class will merge logic from `BaseNeuron`, `BaseValidatorNeuron`, and the current `Validator` implementation.

**Components:**
- **`Validator` Class Methods**:
    - `add_args`, `config`, `check_config`: Unified CLI argument parsing.
    - `__init__`: Sets up wallet, subtensor, metagraph, and Dendrite.
    - `forward`: Main validation loop (logic from `template/validator/forward.py`).
    - `reward` & `get_rewards`: Scoring logic based on throughput, accuracy, and latency.
    - `update_scores`: Exponential moving average for miner rewards.
    - `set_weights`: Interaction with the chain to set miner incentives.
    - `run`: Main loop for concurrent forward passes and syncing.
    - `save_state` & `load_state`: Persistence for scores and hotkeys.

## 4. Data Flow

### Miner Flow
1. Receive `Challenge` via Axon.
2. Check `blacklist` (hotkey registration, stake).
3. Assign `priority` (stake-based).
4. Execute `forward`: Use `MockSafeOnlyInvariantsCheckEngine` to generate outputs.
5. Return results to Validator.

### Validator Flow
1. Pick random miners from metagraph.
2. Load/generate `Challenge` (from `challenge_example.json`).
3. Query miners via Dendrite.
4. Calculate consensus "Ground Truth" from responses.
5. Update miner stats (throughput, accuracy, latency).
6. Calculate `rewards` and update moving average `scores`.
7. Periodically `set_weights` on the Bittensor blockchain.

## 5. Error Handling
- **Engine Failures:** Catch exceptions in the miner's engine and return empty results.
- **Query Timeouts:** Handle dendrite timeouts gracefully in the validator.
- **Network Sync:** Automatic metagraph resynchronization every epoch.

## 6. Testing & Validation
- **Unit Tests:** Update `tests/test_miner.py` and `tests/test_validator_forward.py` to point to the new consolidated classes.
- **Mock Environment:** Use `bt.MockWallet` and `MockSubtensor` for local verification.
- **Consensus Logic:** Verify that the 66% consensus threshold correctly determines ground truth in the validator.
