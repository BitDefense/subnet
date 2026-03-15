# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
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
