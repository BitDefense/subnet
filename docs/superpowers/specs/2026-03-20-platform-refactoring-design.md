# Platform Refactoring: Imports & Wallet Handling

**Status:** Draft
**Date:** 2026-03-20
**Topic:** Standardizing Bittensor imports and clarifying wallet requirements for the Platform service.

## 1. Overview
This refactoring aligns the Platform service with the project's preferred Bittensor import style and ensures that the `Dendrite` communication is correctly authenticated using a `Wallet`.

## 2. Refactoring Goals
- Standardize Bittensor imports across `platform_service/` and `neurons/`.
- Ensure `Dendrite` always has access to a `Wallet` for signing synapse requests.
- Maintain `MockWallet` support for local testing without keyfiles.

## 3. Implementation Details

### 3.1 Import Style
All files will move away from `import bittensor as bt` in favor of direct imports:
```python
from bittensor import Wallet, Metagraph, Dendrite, Config, Subtensor, axon, dendrite
from bittensor import MockWallet, MockSubtensor
from bittensor.utils.btlogging import logging
```

### 3.2 Wallet Handling
- **Platform**: The Platform service will initialize its own `Wallet` using configuration arguments (`--wallet.name`, `--wallet.hotkey`).
- **Dendrite**: The `Dispatcher` will be initialized with this `Wallet` to enable signed communication with Validators.
- **Mocking**: In `--mock` mode, `MockWallet` and `MockSubtensor` will be used to bypass local keyfile and chain requirements.

### 3.3 Files to Modify
- `platform_service/main.py`: Refactor global state initialization and lifespan logic.
- `platform_service/config.py`: Update `get_config` to use direct Bittensor imports.
- `platform_service/dispatcher.py`: Update type hints and `Dendrite` initialization.
- `platform_service/mempool.py`: Update logging calls.
- `neurons/validator/validator.py`: Update imports and `axon` initialization for consistency.
- `neurons/miner/miner.py`: Update imports and class initialization for consistency.
- `template/protocol.py`: Update imports for consistency.

## 4. Verification Plan
- **Unit Tests**: Run existing `tests/platform_service/test_api.py` to ensure no regressions in the FastAPI layer.
- **Mock Run**: Start the platform with `--mock` to verify the refactored initialization logic.
- **Syntax Check**: Verify all modified files for correct Bittensor imports.
