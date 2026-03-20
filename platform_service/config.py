import bittensor as bt
import argparse
import os

def get_config():
    parser = argparse.ArgumentParser()
    
    # Platform specific settings
    parser.add_argument("--rpc_url", type=str, default="wss://sepolia.infura.io/ws/v3/your_key", help="Ethereum Sepolia WebSocket RPC URL")
    parser.add_argument("--api_key", type=str, default="default_key", help="API Key for Platform API security")
    parser.add_argument("--polling_interval", type=int, default=60, help="Interval for validator to poll invariants")

    # Bittensor settings
    bt.wallet.add_args(parser)
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    
    parser.add_argument("--netuid", type=int, default=21, help="The chain subnet uid.")

    config = bt.config(parser)
    return config
