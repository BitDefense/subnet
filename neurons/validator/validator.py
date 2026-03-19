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
from typing import List
from traceback import print_exception

from bittensor import Subtensor, Wallet, Config, Dendrite, Metagraph
from bittensor.utils.btlogging import logging

# Bittensor Validator Template:
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant

from neurons.validator.reward import get_reward


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

        self.step = 0
        self.loop = asyncio.get_event_loop()
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
        # Adds subtensor specific arguments.
        Subtensor.add_args(parser)
        # Adds logging specific arguments.
        logging.add_args(parser)
        # Adds wallet specific arguments.
        Wallet.add_args(parser)
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

    def load_challenge_from_json(self, file_path: str) -> Challenge:
        """Loads a challenge from a JSON file. If file_path is a directory, picks a random JSON file."""
        if not os.path.isabs(file_path):
            # Handle path relative to neurons/
            dir_path = os.path.dirname(os.path.realpath(__file__))
            file_path = os.path.normpath(os.path.join(dir_path, "..", file_path))

        if os.path.isdir(file_path):
            files = [
                os.path.join(file_path, f)
                for f in os.listdir(file_path)
                if f.endswith(".json")
            ]
            if not files:
                raise FileNotFoundError(
                    f"No JSON files found in directory: {file_path}"
                )
            file_path = random.choice(files)

        with open(file_path, "r") as f:
            data = json.load(f)

        for inv in data.get("invariants", []):
            if "storage_slot_type" not in inv:
                inv["storage_slot_type"] = "uint256"

        p = data["tx"]["payload"]
        payload = TransactionPayload(
            type=p["type"],
            chain_id=p["chainId"],
            nonce=p["nonce"],
            gas_price=p["gasPrice"],
            max_fee_per_gas=p.get("maxFeePerGas"),
            max_priority_fee_per_gas=p.get("maxPriorityFeePerGas"),
            gas=p["gas"],
            to=p["to"],
            value=p["value"],
            input=p["input"],
            r=p["r"],
            s=p["s"],
            v=p["v"],
            hash=p["hash"],
            from_address=p.get("from") or p.get("fromAddress") or p.get("from_address"),
        )
        tx = Transaction(hash=data["tx"]["hash"], payload=payload)
        invariants = [Invariant(**inv) for inv in data["invariants"]]

        return Challenge(
            chain_id=str(data["chainId"]),
            block_number=str(data["blockNumber"]),
            tx=tx,
            invariants=invariants,
        )

    async def forward(self) -> None:
        """Validator forward pass."""
        k = random.choice([1])
        miner_uids = self.get_random_uids(k=k)
        logging.info(f"Querying {len(miner_uids)} miners (k={k})")

        try:
            challenge = self.load_challenge_from_json("challenge_example.json")
        except Exception as e:
            logging.error(f"Failed to load challenge: {e}")
            return

        synapses = await self.dendrite.forward(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=challenge,
            deserialize=False,
            timeout=12,
        )

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
                    if count / total_votes >= 0.66:
                        consensus_status = status
                        break
            ground_truth.append(consensus_status)

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
                stats["processed_tx_hashes"].add(challenge.tx.hash)
                if latency is not None:
                    stats["latencies"].append(latency)
                for i in range(num_invariants):
                    if len(resp) > i and ground_truth[i] is not None:
                        stats["total_tasks"] += 1
                        if resp[i] == ground_truth[i]:
                            stats["true_positives"] += 1

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

    def run(self) -> None:
        # The Main Validation Loop.
        logging.info("Starting validator loop.")
        logging.info(f"Validator starting at block: {self.block}")

        try:
            while True:
                logging.info(f"step({self.step}) block({self.block})")
                self.loop.run_until_complete(self.concurrent_forward())
                # self.forward()
                if self.should_exit:
                    break
                self.sync()
                time.sleep(1)
        except KeyboardInterrupt:
            if hasattr(self, "axon"):
                self.axon.stop()

            logging.success("Validator killed by keyboard interrupt.")

            exit()
        except Exception as err:
            logging.error(f"Error during validation: {str(err)}")
            logging.debug(str(print_exception(type(err), err, err.__traceback__)))

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
