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
import copy
import numpy as np
import bittensor as bt
from typing import List, Union, Tuple, Any, Dict
from traceback import print_exception

# Bittensor Validator Template:
from template.protocol import Challenge, Transaction, TransactionPayload, Invariant
from template import __spec_version__ as spec_version

# Constants
U16_MAX = 65535
ALPHA_REWARD = 1.0  # Throughput exponent
BETA_REWARD = 1.0   # Accuracy exponent
GAMMA_REWARD = 1.0  # Latency exponent
T_TARGET_MS = 5000.0  # Target latency in ms

# --- Utility Functions ---

def check_uid_availability(
    metagraph: "bt.metagraph.Metagraph", uid: int, vpermit_tao_limit: int
) -> bool:
    """Check if uid is available. The UID should be available if it is serving and has less than vpermit_tao_limit stake."""
    if not metagraph.axons[uid].is_serving:
        return False
    if metagraph.validator_permit[uid]:
        if metagraph.S[uid] > vpermit_tao_limit:
            return False
    return True

def normalize_max_weight(x: np.ndarray, limit: float = 0.1) -> np.ndarray:
    """Normalizes the numpy array x so that sum(x) = 1 and the max value is not greater than the limit."""
    epsilon = 1e-7
    weights = x.copy()
    values = np.sort(weights)

    if x.sum() == 0 or len(x) * limit <= 1:
        return np.ones_like(x) / x.size
    else:
        estimation = values / values.sum()
        if estimation.max() <= limit:
            return weights / weights.sum()

        cumsum = np.cumsum(estimation, 0)
        estimation_sum = np.array(
            [(len(values) - i - 1) * estimation[i] for i in range(len(values))]
        )
        n_values = (
            estimation / (estimation_sum + cumsum + epsilon) < limit
        ).sum()

        cutoff_scale = (limit * cumsum[n_values - 1] - epsilon) / (
            1 - (limit * (len(estimation) - n_values))
        )
        cutoff = cutoff_scale * values.sum()
        weights[weights > cutoff] = cutoff
        y = weights / weights.sum()
        return y

def convert_weights_and_uids_for_emit(
    uids: np.ndarray, weights: np.ndarray
) -> Tuple[List[int], List[int]]:
    """Converts weights into integer u32 representation that sum to MAX_INT_WEIGHT."""
    uids = np.asarray(uids)
    weights = np.asarray(weights)

    if np.min(weights) < 0:
        raise ValueError(f"Passed weight is negative: {weights}")
    if np.min(uids) < 0:
        raise ValueError(f"Passed uid is negative: {uids}")
    if len(uids) != len(weights):
        raise ValueError(f"Passed weights and uids must have the same length: {len(uids)} and {len(weights)}")
    
    if np.sum(weights) == 0:
        return [], []
    else:
        max_weight = float(np.max(weights))
        weights = [float(value) / max_weight for value in weights]

    weight_vals = []
    weight_uids = []
    for i, (weight_i, uid_i) in enumerate(list(zip(weights, uids))):
        uint16_val = round(float(weight_i) * int(U16_MAX))
        if uint16_val != 0:
            weight_vals.append(uint16_val)
            weight_uids.append(uid_i)
    return weight_uids, weight_vals

def process_weights_for_netuid(
    uids,
    weights: np.ndarray,
    netuid: int,
    subtensor: "bt.subtensor",
    metagraph: "bt.metagraph" = None,
    exclude_quantile: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Process weights for subtensor limitations."""
    if metagraph is None:
        metagraph = subtensor.metagraph(netuid)

    if not isinstance(weights, np.ndarray) or weights.dtype != np.float32:
        weights = weights.astype(np.float32)

    quantile = exclude_quantile / U16_MAX
    min_allowed_weights = subtensor.min_allowed_weights(netuid=netuid)
    max_weight_limit = subtensor.max_weight_limit(netuid=netuid)

    non_zero_weight_idx = np.argwhere(weights > 0).squeeze()
    non_zero_weight_idx = np.atleast_1d(non_zero_weight_idx)
    non_zero_weight_uids = uids[non_zero_weight_idx]
    non_zero_weights = weights[non_zero_weight_idx]

    if non_zero_weights.size == 0 or metagraph.n < min_allowed_weights:
        final_weights = np.ones(metagraph.n) / metagraph.n
        return np.arange(len(final_weights)), final_weights

    elif non_zero_weights.size < min_allowed_weights:
        weights_base = np.ones(metagraph.n) * 1e-5
        weights_base[non_zero_weight_idx] += non_zero_weights
        normalized_weights = normalize_max_weight(x=weights_base, limit=max_weight_limit)
        return np.arange(len(normalized_weights)), normalized_weights

    max_exclude = max(0, len(non_zero_weights) - min_allowed_weights) / len(non_zero_weights)
    exclude_quantile = min([quantile, max_exclude])
    lowest_quantile = np.quantile(non_zero_weights, exclude_quantile)

    non_zero_weight_uids = non_zero_weight_uids[lowest_quantile <= non_zero_weights]
    non_zero_weights = non_zero_weights[lowest_quantile <= non_zero_weights]

    normalized_weights = normalize_max_weight(x=non_zero_weights, limit=max_weight_limit)
    return non_zero_weight_uids, normalized_weights

# --- Validator Class ---

# --- MOCK BITTENSOR ---

class MockSubtensor(bt.MockSubtensor):
    def __init__(self, netuid, n=16, wallet=None, network="mock"):
        super().__init__(network=network)

        # Create subnet if it doesn't exist
        if not self.subnet_exists(netuid):
            self.create_subnet(netuid)

        # Register ourself (the validator) as a neuron at uid=0
        if wallet is not None:
            self.force_register_neuron(
                netuid=netuid,
                hotkey_ss58=wallet.hotkey.ss58_address,
                coldkey_ss58=wallet.coldkey.ss58_address,
                balance=100000,
                stake=100000,
            )

        # Register n mock neurons who will be miners
        for i in range(1, n + 1):
            self.force_register_neuron(
                netuid=netuid,
                hotkey_ss58=f"miner-hotkey-{i}",
                coldkey_ss58="mock-coldkey",
                balance=100000,
                stake=100000,
            )


class MockMetagraph(bt.Metagraph):
    def __init__(self, netuid=1, network="mock", subtensor=None):
        super().__init__(netuid=netuid, network=network, sync=False)

        if subtensor is not None:
            self.subtensor = subtensor
        self.sync(subtensor=subtensor)

        for axon in self.axons:
            axon.ip = "127.0.0.0"
            axon.port = 8091

        bt.logging.info(f"Metagraph: {self}")
        bt.logging.info(f"Axons: {self.axons}")


class MockDendrite(bt.Dendrite):
    """
    Replaces a real bittensor network request with a mock request that just returns some static response for all axons that are passed and adds some random delay.
    """

    def __init__(self, wallet):
        super().__init__(wallet)

    async def forward(
        self,
        axons: List[bt.Axon],
        synapse: bt.Synapse = bt.Synapse(),
        timeout: float = 12,
        deserialize: bool = True,
        run_async: bool = True,
        streaming: bool = False,
    ):
        if streaming:
            raise NotImplementedError("Streaming not implemented yet.")

        async def query_all_axons(streaming: bool):
            """Queries all axons for responses."""

            async def single_axon_response(i, axon):
                """Queries a single axon for a response."""

                start_time = time.time()
                s = synapse.copy()
                # Attach some more required data so it looks real
                s = self.preprocess_synapse_for_request(axon, s, timeout)
                # We just want to mock the response, so we'll just fill in some data
                process_time = random.random()
                if process_time < timeout:
                    s.dendrite.process_time = str(time.time() - start_time)
                    # Update the status code and status message of the dendrite to match the axon
                    # TODO (developer): replace with your own expected synapse data
                    s.dendrite.status_code = 200
                    s.dendrite.status_message = "OK"
                    synapse.dendrite.process_time = str(process_time)
                else:
                    s.dendrite.status_code = 408
                    s.dendrite.status_message = "Timeout"
                    synapse.dendrite.process_time = str(timeout)

                # Return the updated synapse object after deserializing if requested
                if deserialize:
                    return s.deserialize()
                else:
                    return s

            return await asyncio.gather(
                *(
                    single_axon_response(i, target_axon)
                    for i, target_axon in enumerate(axons)
                )
            )

        return await query_all_axons(streaming)

    def __str__(self) -> str:
        """
        Returns a string representation of the Dendrite object.

        Returns:
            str: The string representation of the Dendrite object in the format "dendrite(<user_wallet_address>)".
        """
        return "MockDendrite({})".format(self.keypair.ss58_address)


class Validator:
    @classmethod
    def check_config(cls, config: "bt.Config") -> None:
        bt.logging.check_config(config)
        full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
                config.neuron.name,
            )
        )
        config.neuron.full_path = os.path.expanduser(full_path)
        if not os.path.exists(config.neuron.full_path):
            os.makedirs(config.neuron.full_path, exist_ok=True)

    @classmethod
    def add_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--netuid", type=int, help="Subnet netuid", default=1)
        parser.add_argument("--neuron.device", type=str, help="Device to run on.", default="cpu")
        parser.add_argument("--neuron.epoch_length", type=int, help="Epoch length.", default=100)
        parser.add_argument("--mock", action="store_true", help="Mock neuron.", default=False)
        
        parser.add_argument("--neuron.name", type=str, help="Neuron name.", default="validator")
        parser.add_argument("--neuron.timeout", type=float, help="Forward timeout.", default=10)
        parser.add_argument("--neuron.num_concurrent_forwards", type=int, help="Concurrent forwards.", default=1)
        parser.add_argument("--neuron.sample_size", type=int, help="Miners to query.", default=50)
        parser.add_argument("--neuron.disable_set_weights", action="store_true", help="Disable set weights.", default=False)
        parser.add_argument("--neuron.moving_average_alpha", type=float, help="Moving average alpha.", default=0.1)
        parser.add_argument("--neuron.axon_off", action="store_true", help="Axon off.", default=False)
        parser.add_argument("--neuron.vpermit_tao_limit", type=int, help="Vpermit tao limit.", default=4096)
        parser.add_argument("--neuron.challenge_file", type=str, help="Path to the challenge JSON file.", default="challenge_example.json")

    @classmethod
    def config(cls) -> "bt.Config":
        parser = argparse.ArgumentParser()
        bt.Wallet.add_args(parser)
        bt.Subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.Axon.add_args(parser)
        cls.add_args(parser)
        return bt.Config(parser)

    def __init__(self, config=None) -> None:
        self.config = copy.deepcopy(config or self.config())
        self.check_config(self.config)
        bt.logging.set_config(config=self.config.logging)

        bt.logging.info("Setting up bittensor objects.")
        if self.config.mock:
            self.wallet = bt.MockWallet(config=self.config)
            # Ensure netuid is an int if it's a mock/MagicMock from tests
            netuid = self.config.netuid
            if hasattr(netuid, "item"):
                netuid = netuid.item()
            elif not isinstance(netuid, int):
                try:
                    netuid = int(netuid)
                except (TypeError, ValueError):
                    netuid = 1
            self.subtensor = MockSubtensor(netuid, wallet=self.wallet)
            self.metagraph = MockMetagraph(netuid, subtensor=self.subtensor)
        else:
            self.wallet = bt.Wallet(config=self.config)
            self.subtensor = bt.Subtensor(config=self.config)
            self.metagraph = self.subtensor.metagraph(self.config.netuid)

        bt.logging.info(f"Wallet: {self.wallet}")
        bt.logging.info(f"Subtensor: {self.subtensor}")
        bt.logging.info(f"Metagraph: {self.metagraph}")

        self.check_registered()

        self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)
        self.dendrite = bt.Dendrite(wallet=self.wallet)
        self.scores = np.zeros(self.metagraph.n, dtype=np.float32)
        self.miner_stats = {}
        
        self.load_state()
        
        if not self.config.neuron.axon_off:
            self.serve_axon()
            
        self.step = 0
        self.last_set_weights_block = 0
        self.loop = asyncio.get_event_loop()
        self.should_exit = False
        self.is_running = False
        self.thread = None
        self.lock = asyncio.Lock()

    def check_registered(self) -> None:
        if not self.subtensor.is_hotkey_registered(
            netuid=self.config.netuid,
            hotkey_ss58=self.wallet.hotkey.ss58_address,
        ):
            bt.logging.error(f"Wallet: {self.wallet} is not registered on netuid {self.config.netuid}.")
            exit()

    @property
    def block(self) -> int:
        return self.subtensor.get_current_block()

    def serve_axon(self) -> None:
        bt.logging.info("serving ip to chain...")
        try:
            self.axon = bt.axon(wallet=self.wallet, config=self.config)
            self.subtensor.serve_axon(netuid=self.config.netuid, axon=self.axon)
        except Exception as e:
            bt.logging.error(f"Failed to serve Axon: {e}")

    def get_random_uids(self, k: int, exclude: List[int] = None) -> np.ndarray:
        """Returns k available random uids from the metagraph."""
        candidate_uids = []
        avail_uids = []

        for uid in range(self.metagraph.n.item()):
            uid_is_available = check_uid_availability(
                self.metagraph, uid, self.config.neuron.vpermit_tao_limit
            )
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

    def load_challenge_from_json(self, file_path: str = None) -> Challenge:
        """Loads a challenge from a JSON file. If file_path is a directory, picks a random JSON file."""
        if file_path is None:
            file_path = self.config.neuron.challenge_file

        if not os.path.isabs(file_path):
            # Handle path relative to neurons/
            dir_path = os.path.dirname(os.path.realpath(__file__))
            file_path = os.path.normpath(os.path.join(dir_path, "..", file_path))
        
        if os.path.isdir(file_path):
            files = [os.path.join(file_path, f) for f in os.listdir(file_path) if f.endswith(".json")]
            if not files:
                raise FileNotFoundError(f"No JSON files found in directory: {file_path}")
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
            from_address=p.get("from") or p.get("fromAddress") or p.get("from_address")
        )
        tx = Transaction(hash=data["tx"]["hash"], payload=payload)
        invariants = [Invariant(**inv) for inv in data["invariants"]]
        
        return Challenge(
            chain_id=str(data["chainId"]),
            block_number=str(data["blockNumber"]),
            tx=tx,
            invariants=invariants
        )

    def reward(self, uid_stats: dict) -> float:
        """Reward calculation based on cumulative stats."""
        processed_tx_hashes = uid_stats.get("processed_tx_hashes", set())
        true_positives = uid_stats.get("true_positives", 0)
        total_tasks = uid_stats.get("total_tasks", 0)
        latencies = uid_stats.get("latencies", [])

        n_i = len(processed_tx_hashes)
        a_i = true_positives / total_tasks if total_tasks > 0 else 0.0

        if not latencies:
            l_99 = T_TARGET_MS
        else:
            l_99 = np.percentile(latencies, 99) * 1000.0

        if l_99 <= 0:
            l_99 = 1.0

        score = (n_i**ALPHA_REWARD) * (a_i**BETA_REWARD) * ((T_TARGET_MS / l_99) ** GAMMA_REWARD)
        return float(score)

    def get_rewards(self, miner_uids: List[int]) -> np.ndarray:
        """Returns an array of rewards for given miner UIDs."""
        rewards = []
        for uid in miner_uids:
            uid_stats = self.miner_stats.get(uid, {})
            rewards.append(self.reward(uid_stats))
        return np.array(rewards)

    async def forward(self) -> None:
        """Validator forward pass."""
        k = random.choice([3, 5, 7, 9])
        miner_uids = self.get_random_uids(k=k)
        bt.logging.info(f"Querying {len(miner_uids)} miners (k={k})")

        try:
            challenge = self.load_challenge_from_json()
        except Exception as e:
            bt.logging.error(f"Failed to load challenge: {e}")
            return

        synapses = await self.dendrite(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=challenge,
            deserialize=False,
            timeout=self.config.neuron.timeout,
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
                    "latencies": []
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

        rewards = self.get_rewards(miner_uids=miner_uids)
        self.update_scores(rewards, miner_uids)

    async def concurrent_forward(self) -> None:
        coroutines = [self.forward() for _ in range(self.config.neuron.num_concurrent_forwards)]
        await asyncio.gather(*coroutines)

    def update_scores(self, rewards: np.ndarray, uids: List[int]) -> None:
        """Performs exponential moving average on the scores."""
        if np.isnan(rewards).any():
            rewards = np.nan_to_num(rewards, nan=0)
        rewards = np.asarray(rewards)
        uids_array = np.array(uids)

        if rewards.size == 0 or uids_array.size == 0:
            return

        scattered_rewards: np.ndarray = np.zeros_like(self.scores)
        scattered_rewards[uids_array] = rewards
        alpha: float = self.config.neuron.moving_average_alpha
        self.scores: np.ndarray = alpha * scattered_rewards + (1 - alpha) * self.scores

    def sync(self) -> None:
        self.check_registered()
        if (self.block - self.metagraph.last_update[self.uid]) > self.config.neuron.epoch_length:
            self.resync_metagraph()
        if self.step > 0 and not self.config.neuron.disable_set_weights and self.block > self.last_set_weights_block and (self.block - self.metagraph.last_update[self.uid]) > self.config.neuron.epoch_length:
            self.set_weights()
        self.save_state()

    def resync_metagraph(self) -> None:
        bt.logging.info("resync_metagraph()")
        previous_metagraph = copy.deepcopy(self.metagraph)
        self.metagraph.sync(subtensor=self.subtensor)

        if previous_metagraph.axons == self.metagraph.axons:
            return

        bt.logging.info("Metagraph updated, re-syncing hotkeys and moving averages")
        overlap = min(len(self.hotkeys), len(self.metagraph.hotkeys))
        for uid in range(overlap):
            if self.hotkeys[uid] != self.metagraph.hotkeys[uid]:
                self.scores[uid] = 0

        if len(self.scores) != int(self.metagraph.n):
            new_scores = np.zeros((self.metagraph.n), dtype=self.scores.dtype)
            copy_len = min(len(self.scores), int(self.metagraph.n))
            new_scores[:copy_len] = self.scores[:copy_len]
            self.scores = new_scores

        self.hotkeys = copy.deepcopy(self.metagraph.hotkeys)

    def set_weights(self) -> None:
        if np.isnan(self.scores).any():
            bt.logging.warning("Scores contain NaN values.")

        norm = np.linalg.norm(self.scores, ord=1, axis=0, keepdims=True)
        if np.any(norm == 0) or np.isnan(norm).any():
            norm = np.ones_like(norm)
        raw_weights = self.scores / norm

        processed_weight_uids, processed_weights = process_weights_for_netuid(
            uids=self.metagraph.uids,
            weights=raw_weights,
            netuid=self.config.netuid,
            subtensor=self.subtensor,
            metagraph=self.metagraph,
        )
        uint_uids, uint_weights = convert_weights_and_uids_for_emit(
            uids=processed_weight_uids, weights=processed_weights
        )
        result, msg = self.subtensor.set_weights(
            wallet=self.wallet,
            netuid=self.config.netuid,
            uids=uint_uids,
            weights=uint_weights,
            wait_for_finalization=False,
            wait_for_inclusion=False,
            version_key=spec_version,
        )
        if result:
            bt.logging.info("set_weights on chain successfully!")
            self.last_set_weights_block = self.block
        else:
            bt.logging.error(f"set_weights failed: {msg}")

    def save_state(self) -> None:
        bt.logging.info("Saving validator state.")
        # We need to handle set in miner_stats for JSON/NPZ
        miner_stats_copy = copy.deepcopy(self.miner_stats)
        for uid in miner_stats_copy:
            if "processed_tx_hashes" in miner_stats_copy[uid]:
                miner_stats_copy[uid]["processed_tx_hashes"] = list(miner_stats_copy[uid]["processed_tx_hashes"])
        
        np.savez(
            self.config.neuron.full_path + "/state.npz",
            step=self.step,
            scores=self.scores,
            hotkeys=self.hotkeys,
            miner_stats=np.array([miner_stats_copy], dtype=object)
        )

    def load_state(self) -> None:
        bt.logging.info("Loading validator state.")
        state_path = self.config.neuron.full_path + "/state.npz"
        if os.path.exists(state_path):
            try:
                state = np.load(state_path, allow_pickle=True)
                self.step = int(state["step"])
                self.scores = state["scores"]
                self.hotkeys = list(state["hotkeys"])
                if "miner_stats" in state:
                    self.miner_stats = state["miner_stats"][0]
                    for uid in self.miner_stats:
                        if "processed_tx_hashes" in self.miner_stats[uid]:
                            self.miner_stats[uid]["processed_tx_hashes"] = set(self.miner_stats[uid]["processed_tx_hashes"])
            except Exception as e:
                bt.logging.error(f"Failed to load state: {e}")

    def run(self) -> None:
        self.sync()
        bt.logging.info(f"Validator starting at block: {self.block}")
        try:
            while True:
                bt.logging.info(f"step({self.step}) block({self.block})")
                self.loop.run_until_complete(self.concurrent_forward())
                if self.should_exit:
                    break
                self.sync()
                self.step += 1
                time.sleep(1)
        except KeyboardInterrupt:
            if hasattr(self, "axon"):
                self.axon.stop()
            bt.logging.success("Validator killed by keyboard interrupt.")
            exit()
        except Exception as err:
            bt.logging.error(f"Error during validation: {str(err)}")
            bt.logging.debug(str(print_exception(type(err), err, err.__traceback__)))

    def run_in_background_thread(self) -> None:
        if not self.is_running:
            bt.logging.debug("Starting validator in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True

    def stop_run_thread(self) -> None:
        if self.is_running:
            bt.logging.debug("Stopping validator in background thread.")
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
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
