from bittensor import Wallet, Subtensor, Config
from bittensor.utils.btlogging import logging
import argparse


def get_config():
    parser = argparse.ArgumentParser()

    # Platform specific settings
    parser.add_argument(
        "--rpc_url",
        type=str,
        default="wss://sepolia.infura.io/ws/v3/your_key",
        help="Ethereum Sepolia WebSocket RPC URL",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default="default_key",
        help="API Key for Platform API security",
    )
    parser.add_argument(
        "--polling_interval",
        type=int,
        default=60,
        help="Interval for validator to poll invariants",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for the Platform API",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the Platform API",
    )

    parser.add_argument(
        "--database_url",
        type=str,
        default="sqlite:///./platform.db",
        help="Database URL (e.g., sqlite:///./platform.db or postgresql://user:pass@host/db)",
    )

    # Bittensor settings
    Wallet.add_args(parser)
    Subtensor.add_args(parser)
    logging.add_args(parser)

    parser.add_argument("--netuid", type=int, default=2, help="The chain subnet uid.")

    config = Config(parser)
    return config
