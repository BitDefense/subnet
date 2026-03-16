import pytest
import numpy as np
from unittest.mock import MagicMock
from template.validator.reward import get_rewards, reward

def test_reward_calculation_basic():
    # Test basic reward calculation with 1 TX, 100% accuracy, and target latency
    uid_stats = {
        "processed_tx_hashes": {"hash1"},
        "true_positives": 1,
        "total_tasks": 1,
        "latencies": [5.0]  # 5 seconds = 5000ms (target)
    }
    # S = (1)^1 * (1)^1 * (5000 / 5000)^1 = 1.0
    res = reward(uid_stats)
    assert res == 1.0

def test_reward_calculation_throughput():
    # Test throughput scaling
    uid_stats = {
        "processed_tx_hashes": {"hash1", "hash2"},
        "true_positives": 2,
        "total_tasks": 2,
        "latencies": [5.0, 5.0]
    }
    # S = (2)^1 * (1)^1 * (5000 / 5000)^1 = 2.0
    res = reward(uid_stats)
    assert res == 2.0

def test_reward_calculation_accuracy():
    # Test accuracy scaling
    uid_stats = {
        "processed_tx_hashes": {"hash1"},
        "true_positives": 1,
        "total_tasks": 2,
        "latencies": [5.0]
    }
    # S = (1)^1 * (0.5)^1 * (5000 / 5000)^1 = 0.5
    res = reward(uid_stats)
    assert res == 0.5

def test_reward_calculation_latency():
    # Test latency scaling (faster than target)
    uid_stats = {
        "processed_tx_hashes": {"hash1"},
        "true_positives": 1,
        "total_tasks": 1,
        "latencies": [2.5]  # 2.5s = 2500ms
    }
    # S = (1)^1 * (1)^1 * (5000 / 2500)^1 = 2.0
    res = reward(uid_stats)
    assert res == 2.0

def test_get_rewards_integration():
    mock_self = MagicMock()
    mock_self.miner_stats = {
        1: {
            "processed_tx_hashes": {"h1"},
            "true_positives": 1,
            "total_tasks": 1,
            "latencies": [5.0]
        },
        2: {
            "processed_tx_hashes": {"h1", "h2"},
            "true_positives": 2,
            "total_tasks": 2,
            "latencies": [10.0] # 10s = 10000ms -> multiplier 0.5
        }
    }
    
    uids = [1, 2, 3] # UID 3 has no stats
    rewards = get_rewards(mock_self, uids)
    
    assert len(rewards) == 3
    assert rewards[0] == 1.0
    assert rewards[1] == 1.0 # 2 * 1 * 0.5 = 1.0
    assert rewards[2] == 0.0 # No stats -> 0 TX -> 0 score
