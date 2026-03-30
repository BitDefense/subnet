# Design Spec: Parallel Transaction Processing in Validator

## Overview
Currently, the Validator processes transactions from the `platform_queue` sequentially in a single `forward_loop`. This leads to slow processing times when the transaction volume is high. This design proposes a parallel processing strategy using a Worker Pool of 10 concurrent tasks.

## Goals
- Increase transaction throughput by processing up to 10 transactions in parallel.
- Maintain a stable concurrency limit (buffer of 10).
- Ensure atomic updates to shared state (`miner_stats`) to prevent race conditions.
- Minimize latency for real-time invariant monitoring.

## Architecture

### 1. Worker Pool Pattern
The current `forward_loop` will be refactored into a `forward_worker`.
- **Worker Count:** 10 (configurable).
- **Distribution:** All workers listen to the same `self.platform_queue` (asyncio.Queue). The queue's internal mechanics will handle the distribution of work to the first available worker.

### 2. Atomic Updates
Since 10 workers will be updating `self.miner_stats` concurrently, we will use `self.lock` (an `asyncio.Lock` already initialized in the Validator) to synchronize access to this dictionary.

```python
async with self.lock:
    # Update miner_stats for all relevant UIDs
    for idx, uid in enumerate(miner_uids):
        # ... update logic ...
```

### 3. Workflow Changes
- **Initialization:** In `main_loop`, instead of starting one `forward_loop` task, we will start 10 `forward_worker` tasks.
- **Processing:** Each worker pulls a `PendingTransaction` from the queue, executes `process_transaction`, calculates consensus, triggers defense actions, and updates stats.
- **Defense Actions:** Defense actions are already triggered via `asyncio.create_task`, so they will remain non-blocking for the workers.

## Components

### Validator class refactoring
- **`forward_worker()`**: The new worker logic (extracted from `forward_loop`).
- **`main_loop()`**: Updated to spawn 10 worker tasks.
- **`miner_stats` synchronization**: Wrap the stats update block in `async with self.lock`.

## Error Handling
- Each worker will contain a `try/except` block to ensure that an error in one transaction does not terminate the worker.
- Failed transactions will be logged, and the worker will proceed to the next item in the queue.

## Testing Strategy
- **Unit Test:** Mock `platform_queue` with multiple transactions and verify that `miner_stats` is updated correctly across multiple workers.
- **Race Condition Test:** Simulate high-frequency updates to the same miner UID from multiple workers to ensure the lock prevents data corruption.
- **Throughput Test:** Compare processing time for 100 transactions between the sequential and parallel implementations.

## Success Criteria
- Validator can handle a burst of transactions without blocking the mempool ingestion.
- `miner_stats` remains accurate and consistent after high-volume parallel processing.
- No deadlocks occur between the workers and other background tasks (like `poll_invariants`).
