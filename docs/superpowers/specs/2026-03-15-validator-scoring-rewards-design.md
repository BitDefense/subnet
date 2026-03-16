# Validator Scoring & Rewards Design - Epoch-Based Consensus

## Context
The BitDefense validator calculates a miner's performance score $S_i$ based on transaction throughput ($N_i$), consensus-based accuracy ($A_i$), and 99th percentile latency ($L_{99,i}$). This design defines how the validator tracks these metrics, calculates consensus, and implements the final scoring formula.

The parameters $\alpha=1.0, \beta=1.0, \gamma=1.0, T_{target}=5000ms$ are used for initial implementation.

## Architecture

We will implement the scoring logic in `template/validator/reward.py` and update the `Validator` class in `neurons/validator.py` to maintain metric state.

### Components

**1. Miner Metric State (`Validator.miner_stats`)**
*   The `Validator` will maintain a dictionary mapping miner UIDs to their epoch stats:
    *   `processed_tx_hashes`: Set[str] (Tracks $N_i$ - unique transaction hashes).
    *   `true_positives`: int (Tracks $A_i$ numerator - consensus agreement).
    *   `total_tasks`: int (Tracks $A_i$ denominator - total invariants checked).
    *   `latencies`: List[float] (Tracks $L_{99,i}$ - response times in ms).

**2. Consensus Logic**
*   **Majority Vote**: For each invariant in a challenge, the validator compares responses across the sampled miner subset (3-9 miners).
*   **66% Consensus**: If $\geq 66\%$ of the miners agree on a status (0 or 1), that status is the "Ground Truth" for that challenge step.
*   **Scoring Accuracy**: Miners in the majority increment their `true_positives`. All responding miners increment their `total_tasks`.

**3. Performance Scoring ($S_i$)**
*   The `get_rewards` function implements: $S_i = (N_i)^\alpha \cdot (A_i)^\beta \cdot \left( \frac{T_{target}}{L_{99,i}} \right)^\gamma$
*   **$L_{99}$ Calculation**: Uses `numpy.percentile(latencies, 99)` to calculate the tail latency.
*   **Reset Logic**: The validator will detect the end of an epoch (via `self.step % self.config.neuron.epoch_length == 0`) and clear the `miner_stats` dictionary.

## Data Flow
1.  **Validator** sends `Challenge` to $k$ miners.
2.  **Validator** receives responses and response times (latencies).
3.  **Consensus Loop**: For each invariant, the validator counts 0s and 1s.
4.  **Update Stats**:
    *   Add the challenge `tx.hash` to each miner's `processed_tx_hashes` set.
    *   Compare each miner's result to the consensus status for each invariant. Update `true_positives` and `total_tasks`.
    *   Append the response time to the miner's `latencies` list.
5.  **Calculate $S_i$**: Call the scoring formula using the current cumulative stats for the epoch.
6.  **Return Rewards**: Return the calculated $S_i$ for each miner to the `update_scores` moving average.

## Error Handling & Edge Cases
*   **No Consensus**: If no result reaches 66% agreement, no `true_positives` are awarded for that invariant, but `total_tasks` is still incremented for all.
*   **Empty Latency**: If a miner has no latencies (e.g., first query), use $T_{target}$ as the default $L_{99,i}$ to avoid division by zero (score multiplier becomes 1.0).
*   **Zero Accuracy**: If $A_i = 0$, the entire score $S_i$ becomes 0.
