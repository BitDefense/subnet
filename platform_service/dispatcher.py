from bittensor import Wallet, Metagraph, Dendrite
from template.protocol import MempoolTransaction
from bittensor.utils.btlogging import logging


class Dispatcher:
    def __init__(self, wallet: Wallet, metagraph: Metagraph):
        self.wallet = wallet
        self.metagraph = metagraph
        self.dendrite = Dendrite(wallet=wallet)
        self.current_index = 0

    async def dispatch(
        self,
        chain_id: int,
        block_number: int,
        tx_dict: dict,
    ) -> bool:
        """
        Dispatches a transaction to the next available validator in a round-robin fashion.
        """
        # Get active validators (nodes with positive trust)

        validators = [
            self.metagraph.axons[uid]
            for uid in range(len(self.metagraph.axons))
            if self.metagraph.validator_trust[uid] > 0
        ]

        logging.debug(
            f"Try to dispatch chain {chain_id} block {block_number} tx {tx_dict['hash']} to validators"
        )

        if not validators:
            logging.warning("No active validators found in metagraph.")
            return False

        # Select target using round-robin
        num_validators = len(validators)
        for _ in range(num_validators):
            target_axon = validators[self.current_index % num_validators]
            self.current_index += 1

            logging.info(f"Dispatching transaction to validator: {target_axon.hotkey})")

            synapse = MempoolTransaction(
                chain_id=chain_id,
                block_number=block_number,
                tx=tx_dict,
            )
            try:
                responses = await self.dendrite(
                    [target_axon],
                    synapse,
                    deserialize=False,
                    timeout=12,
                )

                response = responses[0]
                if response.dendrite.status_code == 200:
                    logging.success(f"Successfully dispatched to {target_axon.hotkey}")
                    return True
                else:
                    logging.error(
                        f"Failed to dispatch to {target_axon.hotkey}: {response.dendrite.status_message}"
                    )
            except Exception as e:
                logging.error(f"Error during dispatch to {target_axon.hotkey}: {e}")

            # If dispatch failed, loop continues to the next validator

        logging.error("Failed to dispatch to any validator.")
        return False
