# Implement Defense Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `TelegramAlertAction` and `PauseAgentAction` in the BitDefense validator to respond to confirmed invariant violations.

**Architecture:** Update `DefenseManager` to handle Ethereum RPC and private keys, and implement specific logic for Telegram alerts and blockchain "pause" transactions. Actions will receive the full invariant context for richer alerting and precise execution.

**Tech Stack:** Python, `httpx`, `web3`, `bittensor`.

---

### Task 1: Update Validator Configuration

**Files:**
- Modify: `neurons/validator/validator.py`

- [ ] **Step 1: Add Ethereum configuration arguments**

```python
        parser.add_argument(
            "--eth_rpc_url",
            type=str,
            default="https://sepolia.infura.io/v3/your_key",
            help="Ethereum RPC URL for defense actions",
        )
        parser.add_argument(
            "--eth_private_key",
            type=str,
            help="Ethereum private key for defense actions",
        )
```

- [ ] **Step 2: Commit configuration changes**

```bash
git add neurons/validator/validator.py
git commit -m "feat: add ethereum config for defense actions"
```

### Task 2: Update `DefenseManager` and `BaseDefenseAction`

**Files:**
- Modify: `neurons/validator/defense.py`

- [ ] **Step 1: Update `BaseDefenseAction` constructor and `execute` signature**

```python
class BaseDefenseAction(abc.ABC):
    """Base class for all defense actions."""

    def __init__(self, data: Dict[str, Any], eth_rpc_url: str = None, eth_private_key: str = None):
        self.data = data
        self.type = data.get("type")
        self.eth_rpc_url = eth_rpc_url
        self.eth_private_key = eth_private_key

    @abc.abstractmethod
    async def execute(self, invariant_context: Dict[str, Any] = None):
        """Execute the defense action."""
        pass
```

- [ ] **Step 2: Update `DefenseManager` constructor and methods**

```python
class DefenseManager:
    """Manages fetching and executing defense actions."""

    def __init__(self, platform_url: str, eth_rpc_url: str = None, eth_private_key: str = None):
        self.platform_url = platform_url
        self.eth_rpc_url = eth_rpc_url
        self.eth_private_key = eth_private_key
        self.actions_cache = {}

    # ... inside create_action ...
    def create_action(self, action_data: Dict[str, Any]) -> BaseDefenseAction:
        action_type = action_data.get("type")
        if action_type == "TELEGRAM_ALERT":
            return TelegramAlertAction(action_data, self.eth_rpc_url, self.eth_private_key)
        elif action_type == "PAUSE_AGENT":
            return PauseAgentAction(action_data, self.eth_rpc_url, self.eth_private_key)
        # ...

    # ... update execute_actions signature ...
    async def execute_actions(self, action_ids: List[int], invariant_context: Dict[str, Any] = None):
        for action_id in action_ids:
            action_data = await self.fetch_defense_action(action_id)
            if action_data:
                action = self.create_action(action_data)
                if action:
                    await action.execute(invariant_context)
```

- [ ] **Step 3: Commit structural changes**

```bash
git add neurons/validator/defense.py
git commit -m "refactor: update DefenseManager and BaseDefenseAction signatures"
```

### Task 3: Implement `TelegramAlertAction`

**Files:**
- Modify: `neurons/validator/defense.py`
- Create: `tests/validator/test_defense_actions.py`

- [ ] **Step 1: Write failing test for `TelegramAlertAction`**

```python
import pytest
from unittest.mock import AsyncMock, patch
from neurons.validator.defense import TelegramAlertAction

@pytest.mark.asyncio
async def test_telegram_alert_action_success():
    action_data = {
        "type": "TELEGRAM_ALERT",
        "tg_api_key": "test_bot_token",
        "tg_chat_id": "test_chat_id"
    }
    inv_context = {
        "contract": "0x123",
        "variable": "balance",
        "type": ">",
        "target": "100",
        "network": "ethereum"
    }
    action = TelegramAlertAction(action_data)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        await action.execute(inv_context)
        
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert "test_bot_token" in args[0]
        assert kwargs["json"]["chat_id"] == "test_chat_id"
        assert "0x123" in kwargs["json"]["text"]
```

- [ ] **Step 2: Implement `TelegramAlertAction.execute`**

```python
class TelegramAlertAction(BaseDefenseAction):
    """Action to send a Telegram alert."""

    async def execute(self, invariant_context: Dict[str, Any] = None):
        logging.info(f"Executing Telegram Alert: {self.data}")
        api_key = self.data.get("tg_api_key")
        chat_id = self.data.get("tg_chat_id")
        
        if not api_key or not chat_id:
            logging.error("Telegram API key or Chat ID missing")
            return

        message = "🚨 *BitDefense Alert* 🚨\n\n"
        if invariant_context:
            message += f"*Invariant Violation Detected!*\n"
            message += f"• Contract: `{invariant_context.get('contract')}`\n"
            message += f"• Variable: `{invariant_context.get('variable')}`\n"
            message += f"• Condition: {invariant_context.get('type')} {invariant_context.get('target')}\n"
            message += f"• Network: {invariant_context.get('network')}\n"
        else:
            message += "Unknown invariant violation detected."

        url = f"https://api.telegram.org/bot{api_key}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    logging.info("Telegram alert sent successfully")
                else:
                    logging.error(f"Failed to send Telegram alert: {response.status_code} {response.text}")
            except Exception as e:
                logging.error(f"Error sending Telegram alert: {e}")
```

- [ ] **Step 3: Run test and verify it passes**

Run: `pytest tests/validator/test_defense_actions.py -v`

- [ ] **Step 4: Commit `TelegramAlertAction` implementation**

```bash
git add neurons/validator/defense.py tests/validator/test_defense_actions.py
git commit -m "feat: implement TelegramAlertAction"
```

### Task 4: Implement `PauseAgentAction`

**Files:**
- Modify: `neurons/validator/defense.py`
- Modify: `tests/validator/test_defense_actions.py`

- [ ] **Step 1: Write failing test for `PauseAgentAction`**

```python
from neurons.validator.defense import PauseAgentAction

@pytest.mark.asyncio
async def test_pause_agent_action_success():
    action_data = {
        "type": "PAUSE_AGENT",
        "role_id": "0xAdmin",
        "function_sig": "pause()",
        "calldata": "0x842e5792",
        "network": "ethereum"
    }
    inv_context = {"contract": "0xContractAddress"}
    rpc_url = "http://localhost:8545"
    private_key = "0x" + "a" * 64
    
    action = PauseAgentAction(action_data, rpc_url, private_key)
    
    with patch("web3.Web3") as mock_web3:
        mock_eth = mock_web3.return_value.eth
        mock_eth.account.from_key.return_value.address = "0xMyAddress"
        mock_eth.get_transaction_count.return_value = 0
        mock_eth.gas_price = 20000000000
        mock_eth.account.sign_transaction.return_value.raw_transaction = b"signed_tx"
        mock_eth.send_raw_transaction.return_value.hex.return_value = "0xTxHash"
        
        await action.execute(inv_context)
        
        assert mock_eth.send_raw_transaction.called
```

- [ ] **Step 2: Implement `PauseAgentAction.execute`**

```python
from web3 import Web3

class PauseAgentAction(BaseDefenseAction):
    """Action to pause an agent/contract."""

    async def execute(self, invariant_context: Dict[str, Any] = None):
        logging.info(f"Executing Pause Agent: {self.data}")
        if not self.eth_rpc_url or not self.eth_private_key:
            logging.error("ETH RPC URL or Private Key missing for PauseAgentAction")
            return

        network = self.data.get("network", "ethereum")
        if network.lower() != "ethereum":
            logging.warning(f"PauseAgentAction currently only supports ethereum, but network is {network}")
            # For now we proceed with ethereum rpc if it's the only one we have
            
        contract_address = invariant_context.get("contract") if invariant_context else None
        calldata = self.data.get("calldata")
        
        if not contract_address or not calldata:
            logging.error("Contract address or calldata missing for PauseAgentAction")
            return

        try:
            w3 = Web3(Web3.HTTPProvider(self.eth_rpc_url))
            account = w3.eth.account.from_key(self.eth_private_key)
            
            # Simple transaction build
            tx = {
                'to': contract_address,
                'data': calldata,
                'gas': 200000, # Static gas limit for MVP, could be estimated
                'gasPrice': w3.eth.gas_price,
                'nonce': w3.eth.get_transaction_count(account.address),
                'chainId': w3.eth.chain_id
            }
            
            signed_tx = w3.eth.account.sign_transaction(tx, self.eth_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logging.info(f"Pause transaction sent: {tx_hash.hex()}")
        except Exception as e:
            logging.error(f"Error executing PauseAgentAction: {e}")
```

- [ ] **Step 3: Run tests and verify they pass**

Run: `pytest tests/validator/test_defense_actions.py -v`

- [ ] **Step 4: Commit `PauseAgentAction` implementation**

```bash
git add neurons/validator/defense.py tests/validator/test_defense_actions.py
git commit -m "feat: implement PauseAgentAction"
```

### Task 5: Final Integration in `validator.py`

**Files:**
- Modify: `neurons/validator/validator.py`

- [ ] **Step 1: Update `DefenseManager` initialization**

```python
        # Around line 74
        self.defense_manager = DefenseManager(
            self.config.platform.url,
            eth_rpc_url=self.config.eth_rpc_url,
            eth_private_key=self.config.eth_private_key
        )
```

- [ ] **Step 2: Update `execute_actions` call to pass invariant context**

```python
                            # Around line 323
                            asyncio.create_task(
                                self.defense_manager.execute_actions(action_ids, invariant_context=inv_data)
                            )
```

- [ ] **Step 3: Commit integration changes**

```bash
git add neurons/validator/validator.py
git commit -m "feat: integrate defense actions with validator config and context"
```
