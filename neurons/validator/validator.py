# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2026 Aleksei Gubin

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import os
import time
import json
import random
import asyncio
import argparse
import threading
import numpy as np
from typing import List, Tuple
import traceback

from bittensor import Subtensor, Wallet, Config, Dendrite, Metagraph, Axon
from bittensor.utils.btlogging import logging

# Bittensor Validator Template:
from template.protocol import (
    Challenge,
    Invariant,
    MempoolTransaction,
)

from neurons.validator.reward import get_reward
from neurons.validator.defense import DefenseManager
import httpx


class PendingTransaction:
    def __init__(self, chain_id: int, block_number: int, tx: dict):
        self.chain_id = chain_id
        self.block_number = block_number
        self.tx = tx


def check_uid_availability(metagraph: Metagraph, uid: int) -> bool:
    """Check if uid is available. The UID should be available if it is serving and has less than vpermit_tao_limit stake."""
    if not metagraph.axons[uid].is_serving:
        return False
    if metagraph.validator_permit[uid]:
        return False
    return True


class Validator:
    def __init__(self):
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()
        self.scores = [0] * len(self.metagraph.S)
        self.last_update = self.subtensor.blocks_since_last_update(
            self.config.netuid, self.my_uid
        )
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.weights_rate_limit = self.subtensor.weights_rate_limit(self.config.netuid)
        self.moving_avg_scores = [0] * len(self.metagraph.S)
        self.alpha = 0.1

        self.miner_stats = {}
        self.platform_invariants = []
        # Queue will be initialized in the thread where the loop runs
        self.platform_queue = None

        self.defense_manager = DefenseManager(
            self.config.platform.url,
            eth_rpc_url=self.config.eth_rpc_url,
            eth_private_key=self.config.eth_private_key,
        )

        self.step = 0
        self.loop = None
        self.should_exit = False
        self.is_running = False
        self.thread = None
        self.lock = asyncio.Lock()

    def get_config(self):
        # Set up the configuration parser.
        parser = argparse.ArgumentParser()
        # Adds override arguments for network and netuid.
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )
        parser.add_argument(
            "--platform.url",
            type=str,
            default="http://localhost:8000",
            help="Platform API URL",
        )
        parser.add_argument(
            "--polling_interval",
            type=int,
            default=5,
            help="Interval for validator to poll invariants",
        )
        parser.add_argument(
            "--eth_rpc_url",
            type=str,
            default="https://sepolia.infura.io/v3/your_key",
            help="Ethereum RPC URL for defense actions",
        )
        parser.add_argument(
            "--eth_private_key",
            type=str,
            help="Ethereum private key for defense actions",
        )
        # Adds subtensor specific arguments.
        Subtensor.add_args(parser)
        # Adds logging specific arguments.
        logging.add_args(parser)
        # Adds wallet specific arguments.
        Wallet.add_args(parser)
        Axon.add_args(parser)
        # Parse the config.
        config = Config(parser)
        # Set up logging directory.
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/validator".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
            )
        )
        # Ensure the logging directory exists.
        os.makedirs(config.full_path, exist_ok=True)
        return config

    def setup_logging(self):
        # Set up logging.
        logging(config=self.config, logging_dir=self.config.full_path)
        logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:"
        )
        logging.info(self.config)

    def setup_axon(self):
        # Build and link miner functions to the axon.
        self.axon = Axon(wallet=self.wallet, config=self.config)

        # Attach functions to the axon.
        logging.info("Attaching forward function to axon.")
        self.axon.attach(
            forward_fn=self.mempool_handler,
            blacklist_fn=self.mempool_blacklist,
        )

        # Serve the axon.
        logging.info(
            f"Serving axon on network: {self.config.subtensor.network} with netuid: {self.config.netuid}"
        )
        self.axon.serve(netuid=self.config.netuid, subtensor=self.subtensor)
        logging.info(f"Axon: {self.axon}")

        # Start the axon server.
        logging.info(f"Starting axon server on port: {self.config.axon.port}")
        self.axon.start()

    def setup_bittensor_objects(self):
        # Build Bittensor validator objects.
        logging.info("Setting up Bittensor objects.")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = Subtensor(config=self.config)
        logging.info(f"Subtensor: {self.subtensor}")

        # Initialize dendrite.
        self.dendrite = Dendrite(wallet=self.wallet)
        logging.info(f"Dendrite: {self.dendrite}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(netuid=self.config.netuid)
        logging.info(f"Metagraph: {self.metagraph}")

        # Initialize axon.
        self.setup_axon()

        self.check_registered()

        # Each validator gets a unique identity (UID) in the network.
        self.my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        logging.info(f"Running validator on uid: {self.my_uid}")

        # Set up initial scoring weights for validation.
        logging.info("Building validation weights.")
        self.scores = [0] * len(self.metagraph.S)
        weights_with_uids = [
            (int(self.metagraph.uids[i]), score) for i, score in enumerate(self.scores)
        ]
        logging.info(f"Weights (uid, weight): {weights_with_uids}")

    def check_registered(self) -> None:
        if not self.subtensor.is_hotkey_registered(
            netuid=self.config.netuid,
            hotkey_ss58=self.wallet.hotkey.ss58_address,
        ):
            logging.error(
                f"Your validator: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()

    @property
    def block(self) -> int:
        return self.subtensor.get_current_block()

    def get_random_uids(self, k: int, exclude: List[int] = None) -> np.ndarray:
        """Returns k available random uids from the metagraph."""
        candidate_uids = []
        avail_uids = []

        for uid in range(self.metagraph.n.item()):
            uid_is_available = check_uid_availability(self.metagraph, uid)
            uid_is_not_excluded = exclude is None or uid not in exclude

            if uid_is_available:
                avail_uids.append(uid)
                if uid_is_not_excluded:
                    candidate_uids.append(uid)

        k = min(k, len(avail_uids))
        available_uids = candidate_uids
        if len(candidate_uids) < k:
            available_uids += random.sample(
                [uid for uid in avail_uids if uid not in candidate_uids],
                k - len(candidate_uids),
            )
        uids = np.array(random.sample(available_uids, k))
        return uids

    async def mempool_blacklist(self, synapse: MempoolTransaction) -> Tuple[bool, str]:
        # Only allow requests from known platforms or with correct API key if we want.
        # For now, we'll check if the hotkey is in the metagraph (though platform might not be).
        # In a real subnet, the platform might have a dedicated hotkey registered.
        return False, None

    async def mempool_handler(self, synapse: MempoolTransaction) -> MempoolTransaction:
        for tx in synapse.txs:
            logging.debug(f"Received mempool transaction: {tx.get('hash')}")
            self.platform_queue.put_nowait(
                PendingTransaction(synapse.chain_id, synapse.block_number, tx)
            )
        synapse.received = True
        return synapse

    async def poll_invariants(self):
        """Polls the platform for active invariants."""
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.config.platform.url}/invariants",
                        timeout=10,
                    )
                    if response.status_code == 200:
                        self.platform_invariants = response.json()
                        logging.info(
                            f"Polled {len(self.platform_invariants)} invariants from platform."
                        )
                    else:
                        logging.error(
                            f"Failed to poll invariants: {response.status_code}"
                        )
            except Exception as e:
                logging.error(f"Error polling invariants: {e}")

            await asyncio.sleep(self.config.polling_interval)

    async def forward_loop(self):
        """Validator forward pass."""
        while True:
            try:
                pending_tx = await self.platform_queue.get()
                logging.debug(
                    f"Using mempool transaction for challenge: {pending_tx.tx.get('hash')}"
                )

                (
                    challenge,
                    synapses,
                    miner_uids,
                ) = await self.process_transaction(pending_tx)

                if not miner_uids:
                    logging.warning("No available miners found.")
                    continue

                if not challenge:
                    logging.warning("No challenge created.")
                    continue

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

                    # Trigger defense actions if violation is confirmed
                    if consensus_status == 0:
                        inv_data = self.platform_invariants[i]
                        action_ids = inv_data.get("defense_action_ids", [])
                        if action_ids:
                            logging.info(
                                f"Invariant violation confirmed for {inv_data.get('contract')}. Triggering {len(action_ids)} defense actions."
                            )
                            # We can run these in background to not block the forward loop
                            asyncio.create_task(
                                self.defense_manager.execute_actions(
                                    action_ids, invariant_context=inv_data
                                )
                            )

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

                self.platform_queue.task_done()
            except Exception as e:
                logging.error(f"Error in forward loop: {e}")

    async def process_transaction(self, pending_tx: PendingTransaction):
        k = random.choice([1])
        miner_uids = self.get_random_uids(k=k)

        if not miner_uids:
            return None, [], []

        # Try to get transaction from platform_queue
        challenge = None

        try:
            # Map platform transaction to Challenge synapse
            tx_data = pending_tx.tx

            # Filter invariants for this target contract
            relevant_invariants = []
            for inv in self.platform_invariants:
                # Only pass the keys that Invariant model expects
                relevant_invariants.append(Invariant(**inv))

            if not relevant_invariants:
                logging.warning("No relevant invariants for contracts")
                return

            challenge = Challenge(
                chain_id=str(pending_tx.chain_id),
                block_number=str(pending_tx.block_number),
                tx=tx_data,
                invariants=relevant_invariants,
            )
        except Exception as e:
            logging.error(f"Error building challenge from platform transaction: {e}")
            return

        logging.info(
            f"Querying {len(miner_uids)} miners with challenge {challenge.tx.get('hash')}"
        )

        synapses = await self.dendrite.forward(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=challenge,
            deserialize=False,
            timeout=12,
        )

        return challenge, synapses, miner_uids

    def sync(self) -> None:
        self.metagraph.sync()
        self.last_update = self.subtensor.blocks_since_last_update(
            self.config.netuid, self.my_uid
        )

        logging.debug(f"Blocks since last update: {self.last_update}")

        if self.should_set_weights():
            self.set_weights()

    def should_set_weights(self) -> bool:
        return self.last_update >= self.weights_rate_limit

    def set_weights(self):
        # Adjust the length of moving_avg_scores to match the number of miners
        if len(self.moving_avg_scores) < len(self.metagraph.S):
            self.moving_avg_scores.extend(
                [0] * (len(self.metagraph.S) - len(self.moving_avg_scores))
            )

        for i, uid in enumerate(self.metagraph.uids):
            miner_stat = self.miner_stats.get(uid, {})
            score = get_reward(miner_stat)
            self.moving_avg_scores[i] = (1 - self.alpha) * self.moving_avg_scores[
                i
            ] + self.alpha * score

        # Create list of (uid, score) tuples
        scores_with_uids = [
            (int(self.metagraph.uids[i]), score)
            for i, score in enumerate(self.moving_avg_scores)
        ]
        logging.info(f"Moving Average Scores (uid, score): {scores_with_uids}")

        # set weights once every tempo
        total = sum(self.moving_avg_scores)
        if total > 0:
            weights = [score / total for score in self.moving_avg_scores]
        else:
            # If no miners responded, set zero weights
            weights = [0.0] * len(self.moving_avg_scores)

        # Create list of (uid, weight) tuples
        weights_with_uids = [
            (int(self.metagraph.uids[i]), weight) for i, weight in enumerate(weights)
        ]
        logging.info(f"[blue]Setting weights (uid, weight): {weights_with_uids}[/blue]")

        # Update the incentive mechanism on the Bittensor blockchain.
        response = self.subtensor.set_weights(
            wallet=self.wallet,
            netuid=self.config.netuid,
            uids=self.metagraph.uids,
            weights=weights,
            wait_for_inclusion=True,
            period=self.tempo,  # Good for fast blocks - otherwise make sure to set proper period or remove this argument completely
        )
        if response.success:
            logging.success(f"Weights set successfully. Fee: {response.extrinsic_fee}")
        else:
            logging.error(
                f"Failed to set weights: {response.error} - {response.message}"
            )

    async def main_loop(self):
        """Main async loop for the validator."""
        self.platform_queue = asyncio.Queue()

        # Start background tasks
        self.loop.create_task(self.poll_invariants())
        self.loop.create_task(self.forward_loop())

        while not self.should_exit:
            # Run blocking sync logic in a separate thread
            await asyncio.to_thread(self.sync)
            await asyncio.sleep(1)
            self.step += 1

    def run(self) -> None:
        # The Main Validation Loop.
        logging.info("Starting validator loop.")

        # In the background thread, we need a fresh event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.main_loop())
        except KeyboardInterrupt:
            if hasattr(self, "axon"):
                self.axon.stop()
            logging.success("Validator killed by keyboard interrupt.")
            exit()
        except Exception as err:
            logging.error(f"Error during validation: {str(err)}")
            logging.debug(traceback.format_exc())
        finally:
            self.loop.close()

    async def concurrent_forward(self) -> None:
        coroutines = [self.forward() for _ in range(1)]
        await asyncio.gather(*coroutines)

    def run_in_background_thread(self) -> None:
        if not self.is_running:
            logging.debug("Starting validator in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True

    def stop_run_thread(self) -> None:
        if self.is_running:
            logging.debug("Stopping validator in background thread.")
            self.should_exit = True
            self.thread.join(5)
            self.is_running = False

    def __enter__(self) -> "Validator":
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop_run_thread()


# The main function parses the configuration and runs the validator.
if __name__ == "__main__":
    with Validator() as validator:
        while True:
            logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
