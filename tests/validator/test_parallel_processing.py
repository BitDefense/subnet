import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from neurons.validator.validator import Validator, PendingTransaction

class MockConfig:
    def __init__(self):
        self.netuid = 1
        self.eth_rpc_url = "http://localhost:8545"
        self.eth_private_key = "0x" + "1" * 64
        self.polling_interval = 5
        self.platform = MagicMock()
        self.platform.url = "http://localhost:8000"
        self.logging = MagicMock()
        self.logging.logging_dir = "/tmp"
        self.wallet = MagicMock()
        self.wallet.name = "test"
        self.wallet.hotkey = "test"
        self.axon = MagicMock()
        self.axon.port = 8091

@pytest.mark.asyncio
async def test_parallel_workers():
    # Mock subtensor and other bittensor objects to avoid actual network calls
    with patch('neurons.validator.validator.Subtensor'), \
         patch('neurons.validator.validator.Wallet'), \
         patch('neurons.validator.validator.Metagraph'), \
         patch('neurons.validator.validator.Dendrite'), \
         patch('neurons.validator.validator.Axon'), \
         patch('neurons.validator.validator.logging'), \
         patch.object(Validator, 'get_config', return_value=MockConfig()), \
         patch.object(Validator, 'setup_bittensor_objects'):
        
        validator = Validator()
        validator.platform_queue = asyncio.Queue()
        validator.platform_invariants = [{"id": 1, "contract": "0x123", "defense_action_ids": []}]
        validator.metagraph = MagicMock()
        validator.metagraph.axons = {}
        validator.dendrite = AsyncMock()
        
        # Mock process_transaction to simulate work
        async def mock_process_transaction(pending_tx):
            # Simulate some processing time to ensure multiple workers can run
            await asyncio.sleep(0.01)
            challenge = MagicMock()
            challenge.tx = pending_tx.tx
            challenge.invariants = [MagicMock()]
            
            # 1 miner, 1 invariant, response [1] (no violation)
            miner_uids = [10]
            synapse = MagicMock()
            synapse.deserialize.return_value = [1]
            synapse.dendrite.process_time = 0.1
            
            return challenge, [synapse], miner_uids

        validator.process_transaction = AsyncMock(side_effect=mock_process_transaction)
        
        # Start workers
        workers = []
        for i in range(10):
            workers.append(asyncio.create_task(validator.forward_worker(i)))
            
        # Add tasks to queue
        num_tasks = 50
        for i in range(num_tasks):
            tx = {"hash": f"0x{i}", "from": "0xabc", "to": "0xdef"}
            validator.platform_queue.put_nowait(PendingTransaction(1, 100, tx))
            
        # Wait for all tasks to be processed with a timeout
        try:
            await asyncio.wait_for(validator.platform_queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Tasks did not complete in time")
        
        # Verify miner_stats
        assert 10 in validator.miner_stats
        assert validator.miner_stats[10]["total_tasks"] == num_tasks
        assert len(validator.miner_stats[10]["processed_tx_hashes"]) == num_tasks
        
        # Cleanup
        for worker in workers:
            worker.cancel()

@pytest.mark.asyncio
async def test_atomic_updates_with_lock():
    # This test verifies that the lock is used during miner_stats updates
    with patch('neurons.validator.validator.Subtensor'), \
         patch('neurons.validator.validator.Wallet'), \
         patch('neurons.validator.validator.Metagraph'), \
         patch('neurons.validator.validator.Dendrite'), \
         patch('neurons.validator.validator.Axon'), \
         patch('neurons.validator.validator.logging'), \
         patch.object(Validator, 'get_config', return_value=MockConfig()), \
         patch.object(Validator, 'setup_bittensor_objects'):
        
        validator = Validator()
        validator.platform_queue = asyncio.Queue()
        validator.platform_invariants = [{"id": 1, "contract": "0x123", "defense_action_ids": []}]
        
        # We want to check if self.lock.acquire/release was called
        # Use a real Lock but wrap its __aenter__ and __aexit__
        original_lock = validator.lock
        validator.lock = AsyncMock(wraps=original_lock)
        
        async def mock_process_transaction(pending_tx):
            challenge = MagicMock()
            challenge.tx = pending_tx.tx
            challenge.invariants = [MagicMock()]
            miner_uids = [10]
            synapse = MagicMock()
            synapse.deserialize.return_value = [1]
            synapse.dendrite.process_time = 0.1
            return challenge, [synapse], miner_uids

        validator.process_transaction = AsyncMock(side_effect=mock_process_transaction)
        
        worker_task = asyncio.create_task(validator.forward_worker(0))
        
        tx = {"hash": "0x1", "from": "0xabc", "to": "0xdef"}
        validator.platform_queue.put_nowait(PendingTransaction(1, 100, tx))
        
        await asyncio.wait_for(validator.platform_queue.join(), timeout=2.0)
        
        # Check if lock was used
        assert validator.lock.__aenter__.called
        assert validator.lock.__aexit__.called
        
        worker_task.cancel()
