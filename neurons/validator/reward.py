import numpy as np
from typing import List


# Constants
U16_MAX = 65535
ALPHA_REWARD = 1.0  # Throughput exponent
BETA_REWARD = 1.0  # Accuracy exponent
GAMMA_REWARD = 1.0  # Latency exponent
T_TARGET_MS = 5000.0  # Target latency in ms


def get_reward(uid_stats: dict) -> float:
    """Reward calculation based on cumulative stats."""
    processed_tx_hashes = uid_stats.get("processed_tx_hashes", set())
    true_positives = uid_stats.get("true_positives", 0)
    total_tasks = uid_stats.get("total_tasks", 0)
    latencies = uid_stats.get("latencies", [])

    n_i = len(processed_tx_hashes)
    a_i = true_positives / total_tasks if total_tasks > 0 else 0.0

    if not latencies:
        l_99 = T_TARGET_MS
    else:
        l_99 = np.percentile(latencies, 99) * 1000.0

    if l_99 <= 0:
        l_99 = 1.0

    score = (
        (n_i**ALPHA_REWARD)
        * (a_i**BETA_REWARD)
        * ((T_TARGET_MS / l_99) ** GAMMA_REWARD)
    )

    return float(score)


def get_rewards(self, miner_uids: List[int]) -> np.ndarray:
    """Returns an array of rewards for given miner UIDs."""
    rewards = []
    for uid in miner_uids:
        uid_stats = self.miner_stats.get(uid, {})
        rewards.append(self.reward(uid_stats))
    return np.array(rewards)
