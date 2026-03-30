# Design Spec - Implement Defense Actions

**Date:** 2026-03-30
**Topic:** Implementing `TelegramAlertAction` and `PauseAgentAction` in BitDefense Validator.
**Status:** Approved

## 1. Overview
The BitDefense validator needs to execute automated defense actions when an invariant violation is confirmed. This spec defines the implementation for sending Telegram alerts and calling a "pause" function on an Ethereum contract.

## 2. Architecture & Components

### 2.1 Configuration
Add two new CLI arguments to the validator:
- `--eth_rpc_url`: The Ethereum RPC URL (for now, only Ethereum is supported).
- `--eth_private_key`: The private key of the Ethereum wallet that will sign defense transactions.

### 2.2 `DefenseManager` (Updated)
The `DefenseManager` will now be initialized with:
- `platform_url`
- `eth_rpc_url`
- `eth_private_key`

It will pass these to the action objects it creates.

### 2.3 `BaseDefenseAction` (Updated)
The `execute` method will now accept an optional `invariant_context` dictionary.

```python
class BaseDefenseAction(abc.ABC):
    def __init__(self, data: Dict[str, Any], eth_rpc_url: str = None, eth_private_key: str = None):
        self.data = data
        self.eth_rpc_url = eth_rpc_url
        self.eth_private_key = eth_private_key

    @abc.abstractmethod
    async def execute(self, invariant_context: Dict[str, Any] = None):
        pass
```

## 3. Implementation Details

### 3.1 `TelegramAlertAction`
Constructs and sends a Telegram message using `httpx`.
- **Target:** `https://api.telegram.org/bot<tg_api_key>/sendMessage`
- **Data used:** `tg_api_key`, `tg_chat_id` from `self.data`.
- **Message Content:**
  - Contract address
  - Variable name
  - Comparison type (e.g., `>`, `<`, `==`)
  - Target/threshold value
  - Network

### 3.2 `PauseAgentAction`
Interacts with the Ethereum blockchain using the `web3` library.
- **Data used:** `role_id`, `function_sig`, `calldata`, `network` from `self.data`.
- **Process:**
  1. Connect to `eth_rpc_url`.
  2. Create an account from `eth_private_key`.
  3. Build a transaction to the `contract` address with the specified `calldata`.
  4. Sign the transaction.
  5. Send the raw transaction and wait for the receipt (or log the hash).
  - *Note: For the MVP, if `network` is not "ethereum", we log a warning as other networks are not yet supported.*

## 4. Error Handling
- **Telegram:** Log any `httpx` errors.
- **Pause Agent:** Log any `web3` errors, including connection issues or transaction failures.
- **Defense Manager:** Ensure that one failing action doesn't stop others from executing.

## 5. Testing Strategy
- **Unit Tests:** Mock `httpx` and `web3` to verify that the actions construct the correct payloads and calls.
- **Integration Tests:** (Optional for this task) Test with a local Ethereum node or testnet.
