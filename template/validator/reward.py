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

import numpy as np
from typing import List
import bittensor as bt

# Initial Scoring Parameters
ALPHA = 1.0  # Throughput exponent
BETA = 1.0   # Accuracy exponent
GAMMA = 1.0  # Latency exponent
T_TARGET_MS = 5000.0  # Target latency in ms


def reward(uid_stats: dict) -> float:
    """
    Reward calculation based on the cumulative stats of a miner.
    S_i = (N_i)^alpha * (A_i)^beta * (T_target / L_99,i)^gamma
    """
    processed_tx_hashes = uid_stats.get("processed_tx_hashes", set())
    true_positives = uid_stats.get("true_positives", 0)
    total_tasks = uid_stats.get("total_tasks", 0)
    latencies = uid_stats.get("latencies", [])

    # 1. Throughput (N_i)
    n_i = len(processed_tx_hashes)

    # 2. Accuracy (A_i)
    a_i = true_positives / total_tasks if total_tasks > 0 else 0.0

    # 3. L99 Latency (L_99,i)
    if not latencies:
        l_99 = T_TARGET_MS  # Default multiplier to 1.0 if no latencies recorded
    else:
        # latencies are in seconds, formula expects ms (or consistent units)
        # Assuming latencies in stats are in seconds (standard dendrite output)
        l_99 = np.percentile(latencies, 99) * 1000.0

    # Avoid division by zero for latency
    if l_99 <= 0:
        l_99 = 1.0

    # Scoring Formula
    score = (n_i**ALPHA) * (a_i**BETA) * ((T_TARGET_MS / l_99) ** GAMMA)

    return float(score)


def get_rewards(
    self,
    miner_uids: List[int],
) -> np.ndarray:
    """
    Returns an array of rewards for the given miner UIDs based on their epoch statistics.

    Args:
    - miner_uids (List[int]): A list of miner UIDs.

    Returns:
    - np.ndarray: An array of rewards for the given miner UIDs.
    """
    rewards = []
    for uid in miner_uids:
        uid_stats = self.miner_stats.get(uid, {})
        rewards.append(reward(uid_stats))

    return np.array(rewards)
