from bittensor import Wallet, Metagraph, Dendrite
from template.protocol import MempoolTransaction
from bittensor.utils.btlogging import logging


def check_uid_availability(metagraph: Metagraph, uid: int) -> bool:
    if not metagraph.axons[uid].is_serving:
        return False
    if metagraph.validator_permit[uid]:
        return True
    if metagraph.tao_stake[uid] > 0:
        return True
    return False


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
        txs: list[dict],
    ) -> bool:
        """
        Dispatches a transaction to the next available validator in a round-robin fashion.
        """
        # Get active validators (nodes with positive trust)

        validators = [
            self.metagraph.axons[uid]
            for uid in range(len(self.metagraph.axons))
            if check_uid_availability(self.metagraph, uid)
        ]

        logging.debug(
            f"Try to dispatch chain {chain_id} block {block_number} tx {len(txs)} to validators"
        )

        if not validators:
            logging.warning("No active validators found in metagraph.")
            return False

        # Select target using round-robin
        num_validators = len(validators)
        for _ in range(num_validators):
            target_axon = validators[self.current_index % num_validators]
            self.current_index += 1

            logging.debug(
                f"Dispatching transaction to validator: {target_axon.hotkey})"
            )

            synapse = MempoolTransaction(
                chain_id=chain_id,
                block_number=block_number,
                txs=txs,
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
                    logging.debug(f"Successfully dispatched to {target_axon.hotkey}")
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
