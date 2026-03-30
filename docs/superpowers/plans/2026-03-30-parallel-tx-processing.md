# Parallel Transaction Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Validator's transaction processing to use a pool of 10 parallel workers with atomic state updates.

**Architecture:** Refactor `forward_loop` into a `forward_worker` and spawn 10 worker tasks in `main_loop`. Use `asyncio.Lock` to synchronize updates to `miner_stats`.

**Tech Stack:** Python, asyncio, Bittensor SDK.

---

### Task 1: Refactor `forward_loop` to `forward_worker` and implement synchronization

**Files:**
- Modify: `neurons/validator/validator.py`
- Test: `tests/validator/test_parallel_processing.py`

- [ ] **Step 1: Define `forward_worker` method and add lock synchronization**
Refactor the logic from `forward_loop` into `forward_worker` and wrap the `miner_stats` update in `async with self.lock:`.

```python
    async def forward_worker(self, worker_id: int):
        """Worker task that processes transactions from the queue."""
        logging.info(f"Worker {worker_id} started.")
        while True:
            try:
                pending_tx = await self.platform_queue.get()
                logging.debug(
                    f"Worker {worker_id} processing transaction: {pending_tx.tx.get('hash')}"
                )

                (
                    challenge,
                    synapses,
                    miner_uids,
                ) = await self.process_transaction(pending_tx)

                if not miner_uids or not challenge:
                    self.platform_queue.task_done()
                    continue

                # ... (consensus calculation logic stays the same) ...
                # [Existing consensus logic here]
                num_invariants = len(challenge.invariants)
                responses = [syn.deserialize() for syn in synapses]
                latencies = [syn.dendrite.process_time for syn in synapses]
                
                ground_truth = []
                for i in range(num_invariants):
                    votes = {0: 0, 1: 0}
                    for resp in responses:
                        if resp and len(resp) > i:
                            vote = resp[i]
                            if vote in votes:
                                votes[vote] += 1
                    total_votes = sum(votes.values())
                    consensus_status = None
                    if total_votes > 0:
                        for status, count in votes.items():
                            if count / total_votes >= 0.60:
                                consensus_status = status
                                break
                    ground_truth.append(consensus_status)

                    if consensus_status == 0:
                        inv_data = self.platform_invariants[i]
                        action_ids = inv_data.get("defense_action_ids", [])
                        if action_ids:
                            asyncio.create_task(
                                self.defense_manager.execute_actions(
                                    action_ids, invariant_context=inv_data
                                )
                            )

                # ATOMIC UPDATE START
                async with self.lock:
                    for idx, uid in enumerate(miner_uids):
                        if uid not in self.miner_stats:
                            self.miner_stats[uid] = {
                                "processed_tx_hashes": set(),
                                "true_positives": 0,
                                "total_tasks": 0,
                                "latencies": [],
                            }
                        stats = self.miner_stats[uid]
                        resp = responses[idx]
                        latency = latencies[idx]
                        if resp:
                            stats["processed_tx_hashes"].add(challenge.tx.get("hash"))
                            if latency is not None:
                                stats["latencies"].append(latency)
                            for i in range(num_invariants):
                                if resp and ground_truth[i] is not None:
                                    stats["total_tasks"] += 1
                                    if resp[i] == ground_truth[i]:
                                        stats["true_positives"] += 1
                # ATOMIC UPDATE END

                self.platform_queue.task_done()
            except Exception as e:
                logging.error(f"Error in worker {worker_id}: {e}")
```

- [ ] **Step 2: Update `main_loop` to spawn 10 workers**
Replace the single `forward_loop` call with a loop creating 10 `forward_worker` tasks.

```python
    async def main_loop(self):
        """Main async loop for the validator."""
        self.platform_queue = asyncio.Queue()

        # Start background tasks
        self.loop.create_task(self.poll_invariants())
        
        # Spawn 10 parallel workers
        for i in range(10):
            self.loop.create_task(self.forward_worker(worker_id=i))

        while not self.should_exit:
            await asyncio.to_thread(self.sync)
            await asyncio.sleep(1)
            self.step += 1
```

- [ ] **Step 3: Remove the old `forward_loop` method**

- [ ] **Step 4: Create a test to verify parallel execution and lock**
Create `tests/validator/test_parallel_processing.py` to simulate high-load transaction processing.

```python
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from neurons.validator.validator import Validator, PendingTransaction

@pytest.mark.asyncio
async def test_parallel_worker_processing():
    with patch('neurons.validator.validator.Validator.setup_bittensor_objects'):
        validator = Validator()
        validator.platform_queue = asyncio.Queue()
        validator.platform_invariants = []
        validator.miner_stats = {}
        
        # Mock process_transaction to return dummy data
        async def mock_process(tx):
            return MagicMock(tx={'hash': '0x1'}, invariants=[]), [], []
        
        validator.process_transaction = mock_process
        
        # Add 20 transactions to the queue
        for i in range(20):
            await validator.platform_queue.put(PendingTransaction(1, 1, {'hash': f'0x{i}'}))
            
        # Start workers
        workers = [asyncio.create_task(validator.forward_worker(i)) for i in range(10)]
        
        # Wait for queue to be empty
        await asyncio.wait_for(validator.platform_queue.join(), timeout=5)
        
        # Cleanup workers
        for w in workers:
            w.cancel()
            
        assert validator.platform_queue.empty()
```

- [ ] **Step 5: Run tests**
Run: `pytest tests/validator/test_parallel_processing.py`
Expected: PASS

- [ ] **Step 6: Commit**
```bash
git add neurons/validator/validator.py tests/validator/test_parallel_processing.py
git commit -m "refactor: implement parallel transaction processing with 10 workers and atomic updates"
```
