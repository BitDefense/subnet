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
import numpy as np
from typing import List, Dict, Any

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
    p = data["tx"]["payload"]
    payload = TransactionPayload(
        type=p["type"],
        chain_id=p["chainId"],
        nonce=p["nonce"],
        gas_price=p["gasPrice"],
        max_fee_per_gas=p.get("maxFeePerGas"),
        max_priority_fee_per_gas=p.get("maxPriorityFeePerGas"),
        gas=p["gas"],
        to=p["to"],
        value=p["value"],
        input=p["input"],
        r=p["r"],
        s=p["s"],
        v=p["v"],
        hash=p["hash"],
        from_address=p.get("from") or p.get("fromAddress") or p.get("from_address")
    )
    
    tx = Transaction(
        hash=data["tx"]["hash"],
        payload=payload
    )
    
    invariants = [Invariant(**inv) for inv in data["invariants"]]
    
    return Challenge(
        chain_id=str(data["chainId"]),
        block_number=str(data["blockNumber"]),
        tx=tx,
        invariants=invariants
    )


async def forward(self):
    """
    The forward function is called by the validator every time step.
    It picks 3, 5, 7, or 9 miners and queries them with a challenge.
    """
    # 1. Randomly choose k from [3, 5, 7, 9]
    k = random.choice([1, 2])
    
    # 2. Get k random miner UIDs
    miner_uids = get_random_uids(self, k=k)
    bt.logging.info(f"Querying {len(miner_uids)} miners (k={k})")

    # 3. Load challenge from JSON
    try:
        challenge = load_challenge_from_json("challenge_example.json")
    except Exception as e:
        bt.logging.error(f"Failed to load challenge from JSON: {e}")
        return

    bt.logging.debug(f"Sending Challenge: {challenge.tx.hash}")

    # 4. Query the network in parallel
    synapses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=challenge,
        # timeout=10.0,
        deserialize=False,
    )

    # 5. Process responses and update stats
    num_invariants = len(challenge.invariants)
    responses = [syn.deserialize() for syn in synapses]
    latencies = [syn.dendrite.process_time for syn in synapses]

    bt.logging.debug(f"Responses: {responses}")
    bt.logging.debug(f"Latencies: {latencies}")
    
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
                if count / total_votes >= 0.60:
                    consensus_status = status
                    break
        ground_truth.append(consensus_status)

    bt.logging.debug(f"Ground Truth: {ground_truth}")

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

        # Update throughput
        if resp: # Miner responded
            stats["processed_tx_hashes"].add(challenge.tx.hash)
            
            # Update latencies
            if latency is not None:
                stats["latencies"].append(latency)
            
            # Update accuracy based on consensus
            for i in range(num_invariants):
                if len(resp) > i:
                    stats["total_tasks"] += 1
                    if ground_truth[i] is not None and resp[i] == ground_truth[i]:
                        stats["true_positives"] += 1

    # 6. Score responses based on cumulative epoch stats
    rewards = get_rewards(self, miner_uids=miner_uids)

    bt.logging.info(f"Scored responses: {rewards}")
    
    # 7. Update scores
    self.update_scores(rewards, miner_uids)