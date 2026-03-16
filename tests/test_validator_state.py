import pytest
from unittest.mock import MagicMock, patch
from neurons.validator import Validator

@pytest.fixture
def mock_bittensor_setup(monkeypatch):
    monkeypatch.setattr("bittensor.Subtensor", MagicMock())
    monkeypatch.setattr("bittensor.Wallet", MagicMock())
    monkeypatch.setattr("bittensor.Axon", MagicMock())
    monkeypatch.setattr("bittensor.logging", MagicMock())
    # Mock BaseValidatorNeuron init
    monkeypatch.setattr("template.base.validator.BaseValidatorNeuron.__init__", MagicMock(return_value=None))

def test_validator_initializes_miner_stats(mock_bittensor_setup):
    with patch("neurons.validator.Validator.load_state", MagicMock()):
        validator = Validator()
        assert hasattr(validator, "miner_stats")
        assert isinstance(validator.miner_stats, dict)
        
        # Test reset logic
        validator.miner_stats[0] = {"total_tasks": 1}
        validator.reset_miner_stats()
        assert len(validator.miner_stats) == 0
