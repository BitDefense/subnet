import bittensor as bt
from template.protocol import MempoolTransaction
import asyncio
from typing import List, Optional

class Dispatcher:
    def __init__(self, wallet: bt.wallet, metagraph: bt.metagraph):
        self.wallet = wallet
        self.metagraph = metagraph
        self.dendrite = bt.dendrite(wallet=wallet)
        self.current_index = 0

    async def dispatch(self, tx_dict: dict) -> bool:
        """
        Dispatches a transaction to the next available validator in a round-robin fashion.
        """
        # Get active validators (nodes with positive trust)
        validators = [
            self.metagraph.axons[uid] 
            for uid in range(len(self.metagraph.axons))
            if self.metagraph.validator_trust[uid] > 0
        ]
        
        if not validators:
            bt.logging.warning("No active validators found in metagraph.")
            return False
        
        # Select target using round-robin
        num_validators = len(validators)
        for _ in range(num_validators):
            target_axon = validators[self.current_index % num_validators]
            self.current_index += 1
            
            bt.logging.info(f"Dispatching transaction to validator: {target_axon.hotkey}")
            
            synapse = MempoolTransaction(tx=tx_dict)
            try:
                responses = await self.dendrite(
                    [target_axon],
                    synapse,
                    deserialize=False,
                    timeout=12,
                )
                
                response = responses[0]
                if response.dendrite.status_code == 200:
                    bt.logging.success(f"Successfully dispatched to {target_axon.hotkey}")
                    return True
                else:
                    bt.logging.error(f"Failed to dispatch to {target_axon.hotkey}: {response.dendrite.status_message}")
            except Exception as e:
                bt.logging.error(f"Error during dispatch to {target_axon.hotkey}: {e}")
            
            # If dispatch failed, loop continues to the next validator
        
        bt.logging.error("Failed to dispatch to any validator.")
        return False
