import pytest
import bittensor as bt
from unittest.mock import MagicMock, patch
from neurons.validator import Validator

def test_validator_initialization():
    # Mock the configuration
    mock_config = MagicMock(spec=bt.Config)
    mock_config.neuron = MagicMock()
    mock_config.neuron.device = "cpu"
    mock_config.neuron.full_path = "/tmp/validator_test"
    mock_config.neuron.epoch_length = 100
    mock_config.neuron.disable_set_weights = False
    mock_config.neuron.num_concurrent_forwards = 1
    mock_config.logging = MagicMock()
    mock_config.mock = True
    mock_config.netuid = 1
    
    with patch("neurons.validator.Validator.config", return_value=mock_config), \
         patch("neurons.validator.Validator.check_config"), \
         patch("bittensor.logging.set_config"), \
         patch("bittensor.Wallet") as mock_wallet_class, \
         patch("bittensor.MockWallet", create=True) as mock_mock_wallet_class, \
         patch("bittensor.Subtensor"), \
         patch("bittensor.Metagraph") as mock_metagraph_class:
        
        # Setup mock wallet
        mock_wallet = mock_mock_wallet_class.return_value if hasattr(bt, 'MockWallet') else mock_wallet_class.return_value
        mock_wallet.hotkey.ss58_address = "hotkey1"
        mock_wallet.coldkey.ss58_address = "coldkey1"
        
        # Setup mock metagraph
        mock_metagraph = mock_metagraph_class.return_value
        mock_metagraph.hotkeys = ["hotkey1", "hotkey2"]
        mock_metagraph.n = 2
        
        # Instantiate validator
        # We need to mock load_state since it might fail if state.npz doesn't exist
        with patch("neurons.validator.Validator.load_state"):
            validator = Validator(config=mock_config)
            
        # Check initial state
        assert hasattr(validator, 'miner_stats')
        assert validator.miner_stats == {}
        assert hasattr(validator, 'scores')
        assert len(validator.scores) == 2
        assert hasattr(validator, 'hotkeys')
        assert len(validator.hotkeys) == 2

@pytest.mark.anyio
async def test_validator_forward_exists():
    # This test just checks if forward exists and is async
    mock_config = MagicMock(spec=bt.Config)
    mock_config.neuron = MagicMock()
    mock_config.neuron.full_path = "/tmp/validator_test"
    mock_config.mock = True
    
    with patch("neurons.validator.Validator.config", return_value=mock_config), \
         patch("neurons.validator.Validator.check_config"), \
         patch("bittensor.logging.set_config"), \
         patch("neurons.validator.Validator.load_state"), \
         patch("bittensor.Wallet") as mock_wallet_class, \
         patch("bittensor.MockWallet", create=True) as mock_mock_wallet_class, \
         patch("bittensor.Subtensor"), \
         patch("bittensor.Metagraph"):
        
        # Setup mock wallet
        mock_wallet = mock_mock_wallet_class.return_value if hasattr(bt, 'MockWallet') else mock_wallet_class.return_value
        mock_wallet.hotkey.ss58_address = "mock_hotkey"
        mock_wallet.coldkey.ss58_address = "mock_coldkey"
        
        validator = Validator(config=mock_config)
        assert hasattr(validator, 'forward')
        assert callable(validator.forward)

@pytest.mark.anyio
async def test_validator_forward_logic():
    # Mock the configuration
    mock_config = MagicMock(spec=bt.Config)
    mock_config.neuron = MagicMock()
    mock_config.neuron.full_path = "/tmp/validator_test"
    mock_config.neuron.timeout = 10
    mock_config.neuron.vpermit_tao_limit = 4096
    mock_config.neuron.moving_average_alpha = 0.1
    mock_config.neuron.challenge_file = "challenge_example.json"
    mock_config.neuron.axon_off = True
    mock_config.logging = MagicMock()
    mock_config.mock = True
    mock_config.netuid = 1
    
    with patch("neurons.validator.Validator.config", return_value=mock_config), \
         patch("neurons.validator.Validator.check_config"), \
         patch("bittensor.logging.set_config"), \
         patch("neurons.validator.Validator.load_state"), \
         patch("bittensor.Wallet") as mock_wallet_class, \
         patch("bittensor.MockWallet", create=True) as mock_mock_wallet_class, \
         patch("bittensor.Subtensor") as mock_subtensor_class, \
         patch("bittensor.Metagraph") as mock_metagraph_class, \
         patch("bittensor.Dendrite") as mock_dendrite_class:
        
        # Setup mock wallet
        mock_wallet = mock_mock_wallet_class.return_value if hasattr(bt, 'MockWallet') else mock_wallet_class.return_value
        mock_wallet.hotkey.ss58_address = "mock_hotkey"
        mock_wallet.coldkey.ss58_address = "mock_coldkey"
        
        # Setup mock metagraph
        mock_metagraph = mock_metagraph_class.return_value
        mock_metagraph.hotkeys = ["hotkey0", "hotkey1", "hotkey2"]
        mock_metagraph.n = MagicMock()
        mock_metagraph.n.item.return_value = 3
        mock_metagraph.uids = [0, 1, 2]
        
        # Mock axons
        mock_axons = [MagicMock(), MagicMock(), MagicMock()]
        for i, axon in enumerate(mock_axons):
            axon.is_serving = True
        mock_metagraph.axons = mock_axons
        mock_metagraph.validator_permit = [False, False, False]
        mock_metagraph.S = [0, 0, 0]
        
        # Instantiate validator
        validator = Validator(config=mock_config)
        validator.metagraph = mock_metagraph
        validator.scores = [0.0, 0.0, 0.0]
        
        # Mock challenge
        mock_challenge = MagicMock()
        mock_challenge.invariants = [MagicMock(), MagicMock()]
        mock_challenge.tx.hash = "0x123"
        
        with patch.object(validator, 'load_challenge_from_json', return_value=mock_challenge), \
             patch.object(validator, 'get_random_uids', return_value=[0, 1, 2]):
            
            # Mock dendrite call
            mock_synapses = [MagicMock(), MagicMock(), MagicMock()]
            # Miner 0: Correct votes [0, 1]
            mock_synapses[0].deserialize.return_value = [0, 1]
            mock_synapses[0].dendrite.process_time = 0.5
            # Miner 1: Correct votes [0, 1]
            mock_synapses[1].deserialize.return_value = [0, 1]
            mock_synapses[1].dendrite.process_time = 0.5
            # Miner 2: Incorrect votes [1, 0]
            mock_synapses[2].deserialize.return_value = [1, 0]
            mock_synapses[2].dendrite.process_time = 0.5
            
            validator.dendrite = MagicMock(return_value=mock_synapses)
            
            # Run forward
            await validator.forward()
            
            # Consensus should be [0, 1] (Miner 0 and 1 voted same)
            # Miner 0: 2 true positives
            # Miner 1: 2 true positives
            # Miner 2: 0 true positives
            
            assert 0 in validator.miner_stats
            assert 1 in validator.miner_stats
            assert 2 in validator.miner_stats
            
            assert validator.miner_stats[0]["true_positives"] == 2
            assert validator.miner_stats[1]["true_positives"] == 2
            assert validator.miner_stats[2]["true_positives"] == 0
            
            # Check scores updated
            assert any(s > 0 for s in validator.scores)
            assert validator.scores[0] == validator.scores[1]
            assert validator.scores[0] > validator.scores[2]

@pytest.mark.anyio
async def test_validator_no_consensus():
    # Mock the configuration
    mock_config = MagicMock(spec=bt.Config)
    mock_config.neuron = MagicMock()
    mock_config.neuron.full_path = "/tmp/validator_test"
    mock_config.neuron.timeout = 10
    mock_config.neuron.vpermit_tao_limit = 4096
    mock_config.neuron.moving_average_alpha = 0.1
    mock_config.neuron.challenge_file = "challenge_example.json"
    mock_config.neuron.axon_off = True
    mock_config.logging = MagicMock()
    mock_config.mock = True
    mock_config.netuid = 1
    
    with patch("neurons.validator.Validator.config", return_value=mock_config), \
         patch("neurons.validator.Validator.check_config"), \
         patch("bittensor.logging.set_config"), \
         patch("neurons.validator.Validator.load_state"), \
         patch("bittensor.Wallet") as mock_wallet_class, \
         patch("bittensor.MockWallet", create=True) as mock_mock_wallet_class, \
         patch("bittensor.Subtensor"), \
         patch("bittensor.Metagraph") as mock_metagraph_class:
        
        # Setup mock wallet
        mock_wallet = mock_mock_wallet_class.return_value if hasattr(bt, 'MockWallet') else mock_wallet_class.return_value
        mock_wallet.hotkey.ss58_address = "mock_hotkey"
        mock_wallet.coldkey.ss58_address = "mock_coldkey"
        
        mock_metagraph = mock_metagraph_class.return_value
        mock_metagraph.hotkeys = ["hotkey0", "hotkey1", "hotkey2"]
        mock_metagraph.n = MagicMock()
        mock_metagraph.n.item.return_value = 3
        mock_metagraph.uids = [0, 1, 2]
        mock_metagraph.axons = [MagicMock() for _ in range(3)]
        for axon in mock_metagraph.axons: axon.is_serving = True
        mock_metagraph.validator_permit = [False] * 3
        mock_metagraph.S = [0] * 3
        
        validator = Validator(config=mock_config)
        validator.metagraph = mock_metagraph
        
        # Mock challenge with 1 invariant
        mock_challenge = MagicMock()
        mock_challenge.invariants = [MagicMock()]
        mock_challenge.tx.hash = "0xabc"
        
        with patch.object(validator, 'load_challenge_from_json', return_value=mock_challenge), \
             patch.object(validator, 'get_random_uids', return_value=[0, 1, 2]):
            
            # 3 miners, all different votes -> no consensus (66% required)
            mock_synapses = [MagicMock() for _ in range(3)]
            mock_synapses[0].deserialize.return_value = [0]
            mock_synapses[1].deserialize.return_value = [1]
            mock_synapses[2].deserialize.return_value = [2]
            for syn in mock_synapses: syn.dendrite.process_time = 0.5
            
            validator.dendrite = MagicMock(return_value=mock_synapses)
            
            await validator.forward()
            
            # Since no consensus was reached, total_tasks should NOT be incremented
            for uid in [0, 1, 2]:
                assert validator.miner_stats[uid]["total_tasks"] == 0
                assert validator.miner_stats[uid]["true_positives"] == 0

@pytest.mark.anyio
async def test_validator_reward_latency():
    # Mock the configuration
    mock_config = MagicMock(spec=bt.Config)
    mock_config.neuron = MagicMock()
    mock_config.neuron.full_path = "/tmp/validator_test"
    mock_config.neuron.timeout = 10
    mock_config.neuron.vpermit_tao_limit = 4096
    mock_config.neuron.moving_average_alpha = 1.0 # Set alpha to 1.0 to see reward directly in scores
    mock_config.neuron.challenge_file = "challenge_example.json"
    mock_config.neuron.axon_off = True
    mock_config.logging = MagicMock()
    mock_config.mock = True
    mock_config.netuid = 1
    
    with patch("neurons.validator.Validator.config", return_value=mock_config), \
         patch("neurons.validator.Validator.check_config"), \
         patch("bittensor.logging.set_config"), \
         patch("neurons.validator.Validator.load_state"), \
         patch("bittensor.Wallet") as mock_wallet_class, \
         patch("bittensor.MockWallet", create=True) as mock_mock_wallet_class, \
         patch("bittensor.Subtensor"), \
         patch("bittensor.Metagraph") as mock_metagraph_class:
        
        # Setup mock wallet
        mock_wallet = mock_mock_wallet_class.return_value if hasattr(bt, 'MockWallet') else mock_wallet_class.return_value
        mock_wallet.hotkey.ss58_address = "mock_hotkey"
        mock_wallet.coldkey.ss58_address = "mock_coldkey"
        
        mock_metagraph = mock_metagraph_class.return_value
        mock_metagraph.hotkeys = ["hotkey0", "hotkey1"]
        mock_metagraph.n = MagicMock()
        mock_metagraph.n.item.return_value = 2
        mock_metagraph.uids = [0, 1]
        mock_metagraph.axons = [MagicMock(), MagicMock()]
        for axon in mock_metagraph.axons: axon.is_serving = True
        mock_metagraph.validator_permit = [False, False]
        mock_metagraph.S = [0, 0]
        
        validator = Validator(config=mock_config)
        validator.metagraph = mock_metagraph
        validator.scores = np.zeros(2)
        
        # Mock challenge
        mock_challenge = MagicMock()
        mock_challenge.invariants = [MagicMock()]
        mock_challenge.tx.hash = "0xdef"
        
        with patch.object(validator, 'load_challenge_from_json', return_value=mock_challenge), \
             patch.object(validator, 'get_random_uids', return_value=[0, 1]):
            
            # Both correct, but miner 0 is faster
            mock_synapses = [MagicMock(), MagicMock()]
            mock_synapses[0].deserialize.return_value = [0]
            mock_synapses[0].dendrite.process_time = 0.1 # 100ms
            mock_synapses[1].deserialize.return_value = [0]
            mock_synapses[1].dendrite.process_time = 1.0 # 1000ms
            
            validator.dendrite = MagicMock(return_value=mock_synapses)
            
            await validator.forward()
            
            # Miner 0 should have higher score than Miner 1 due to lower latency
            assert validator.scores[0] > validator.scores[1]
