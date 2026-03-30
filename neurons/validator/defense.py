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


class BaseDefenseAction(abc.ABC):
    """Base class for all defense actions."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.type = data.get("type")

    @abc.abstractmethod
    async def execute(self):
        """Execute the defense action."""
        pass


class TelegramAlertAction(BaseDefenseAction):
    """Action to send a Telegram alert."""

    async def execute(self):
        logging.info(f"Executing Telegram Alert: {self.data}")
        # Implementation will be in the next task
        pass


class PauseAgentAction(BaseDefenseAction):
    """Action to pause an agent/contract."""

    async def execute(self):
        logging.info(f"Executing Pause Agent: {self.data}")
        # Implementation will be in the next task
        pass


class DefenseManager:
    """Manages fetching and executing defense actions."""

    def __init__(self, platform_url: str, api_key: str):
        self.platform_url = platform_url
        self.api_key = api_key
        self.actions_cache = {}

    async def fetch_defense_action(self, action_id: int) -> Dict[str, Any]:
        """Fetch defense action details from platform API."""
        if action_id in self.actions_cache:
            return self.actions_cache[action_id]

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.platform_url}/defense-actions/{action_id}",
                    headers={"X-API-KEY": self.api_key},
                    timeout=10,
                )
                if response.status_code == 200:
                    action_data = response.json()
                    self.actions_cache[action_id] = action_data
                    return action_data
                else:
                    logging.error(f"Failed to fetch defense action {action_id}: {response.status_code}")
                    return None
            except Exception as e:
                logging.error(f"Error fetching defense action {action_id}: {e}")
                return None

    def create_action(self, action_data: Dict[str, Any]) -> BaseDefenseAction:
        """Create the appropriate action object based on type."""
        action_type = action_data.get("type")
        if action_type == "Telegram Alert":
            return TelegramAlertAction(action_data)
        elif action_type == "Pause Agent":
            return PauseAgentAction(action_data)
        else:
            logging.warning(f"Unknown defense action type: {action_type}")
            return None

    async def execute_actions(self, action_ids: List[int]):
        """Fetch and execute a list of defense actions."""
        for action_id in action_ids:
            action_data = await self.fetch_defense_action(action_id)
            if action_data:
                action = self.create_action(action_data)
                if action:
                    await action.execute()
