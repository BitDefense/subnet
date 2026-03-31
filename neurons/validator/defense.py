# The MIT License (MIT)
# Copyright © 2026 Aleksei Gubin

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import abc
import httpx
from bittensor.utils.btlogging import logging
from typing import Dict, Any, List
from web3 import Web3


class BaseDefenseAction(abc.ABC):
    """Base class for all defense actions."""

    def __init__(
        self,
        data: Dict[str, Any],
        eth_rpc_url: str = None,
        eth_private_key: str = None,
    ):
        self.data = data
        self.type = data.get("type")
        self.eth_rpc_url = eth_rpc_url
        self.eth_private_key = eth_private_key

    @abc.abstractmethod
    async def execute(self, invariant_context: Dict[str, Any] = None):
        """Execute the defense action."""
        pass


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
            message += "*Invariant Violation Detected!*\n"
            message += f"• Contract: `{invariant_context.get('contract')}`\n"
            message += f"• Condition: {invariant_context.get('variable')} {invariant_context.get('type')} {invariant_context.get('target')}\n"
            message += f"• Network: {invariant_context.get('network')}\n"
        else:
            message += "Unknown invariant violation detected."

        url = f"https://api.telegram.org/bot{api_key}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    logging.info("Telegram alert sent successfully")
                else:
                    logging.error(
                        f"Failed to send Telegram alert: {response.status_code} {response.text}"
                    )
            except Exception as e:
                logging.error(f"Error sending Telegram alert: {e}")


class PauseAgentAction(BaseDefenseAction):
    """Action to pause an agent/contract."""

    async def execute(self, invariant_context: Dict[str, Any] = None):
        logging.info(f"Executing Pause Agent: {self.data}")
        if not self.eth_rpc_url or not self.eth_private_key:
            logging.error("ETH RPC URL or Private Key missing for PauseAgentAction")
            return

        network = self.data.get("network", "ethereum")
        if network.lower() != "ethereum":
            logging.warning(
                f"PauseAgentAction currently only supports ethereum, but network is {network}"
            )
            # For now we proceed with ethereum rpc if it's the only one we have

        contract_address = (
            invariant_context.get("contract") if invariant_context else None
        )
        calldata = self.data.get("function_sig")

        if not contract_address or not calldata:
            logging.error("Contract address or calldata missing for PauseAgentAction")
            return

        try:
            w3 = Web3(Web3.HTTPProvider(self.eth_rpc_url))
            account = w3.eth.account.from_key(self.eth_private_key)
            gas_price = w3.eth.gas_price
            adjusted_gas_price = int(gas_price * 1.2)
            nonce = w3.eth.get_transaction_count(account.address)

            # Simple transaction build
            tx = {
                "to": contract_address,
                "data": calldata,
                "gas": 200000,  # Static gas limit for MVP, could be estimated
                "gasPrice": adjusted_gas_price,
                "nonce": nonce,
                "chainId": w3.eth.chain_id,
            }

            signed_tx = w3.eth.account.sign_transaction(tx, self.eth_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logging.info(f"Pause transaction sent: {tx_hash.hex()}")
        except Exception as e:
            logging.error(f"Error executing PauseAgentAction: {e}")


class DefenseManager:
    """Manages fetching and executing defense actions."""

    def __init__(
        self, platform_url: str, eth_rpc_url: str = None, eth_private_key: str = None
    ):
        self.platform_url = platform_url
        self.eth_rpc_url = eth_rpc_url
        self.eth_private_key = eth_private_key
        self.actions_cache = {}

    async def fetch_defense_action(self, action_id: int) -> Dict[str, Any]:
        """Fetch defense action details from platform API."""
        if action_id in self.actions_cache:
            return self.actions_cache[action_id]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.platform_url}/defense-actions/{action_id}",
                    timeout=10,
                )
                if response.status_code == 200:
                    action_data = response.json()
                    self.actions_cache[action_id] = action_data
                    return action_data
                else:
                    logging.error(
                        f"Failed to fetch defense action {action_id}: {response.status_code}"
                    )
                    return None
            except Exception as e:
                logging.error(f"Error fetching defense action {action_id}: {e}")
                return None

    def create_action(self, action_data: Dict[str, Any]) -> BaseDefenseAction:
        """Create the appropriate action object based on type."""
        action_type = action_data.get("type")
        if action_type == "TELEGRAM_ALERT":
            return TelegramAlertAction(
                action_data, self.eth_rpc_url, self.eth_private_key
            )
        elif action_type == "PAUSE_AGENT":
            return PauseAgentAction(action_data, self.eth_rpc_url, self.eth_private_key)
        else:
            logging.warning(f"Unknown defense action type: {action_type}")
            return None

    async def execute_actions(
        self, action_ids: List[int], invariant_context: Dict[str, Any] = None
    ):
        """Fetch and execute a list of defense actions."""
        for action_id in action_ids:
            action_data = await self.fetch_defense_action(action_id)
            if action_data:
                action = self.create_action(action_data)
                if action:
                    await action.execute(invariant_context)
