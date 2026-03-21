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
import argparse
import asyncio
import threading
import traceback
from abc import ABC, abstractmethod
from typing import List, Tuple

from bittensor import Subtensor, Wallet, Config, Axon
from bittensor.utils.btlogging import logging

# Bittensor Miner Template:
from template.protocol import Challenge


# --- ENGINES ---
class InvariantsCheckEngine(ABC):
    @abstractmethod
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Executes the invariant checks against the provided challenge.
        """
        pass


class SafeOnlyInvariantsCheckEngine(InvariantsCheckEngine):
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Mock implementation that always returns 1 (safe) for every invariant.
        """
        return [1] * len(challenge.invariants)


# --- MINER ---


class Miner(ABC):
    """
    Your miner neuron class. You should use this class to define your miner's behavior. In particular, you should replace the forward function with your own logic. You may also want to override the blacklist and priority functions according to your needs.
    """

    def __init__(self):
        self.subtensor = None
        self.wallet = None
        self.metagraph = None
        self.axon = None
        self.my_subnet_uid = None

        self.engine = SafeOnlyInvariantsCheckEngine()

        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()

        self.should_exit = False
        self.is_running = False
        self.thread = None
        self.lock = asyncio.Lock()

    def get_config(self):
        # Set up the configuration parser
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
        # Adds axon specific arguments.
        Axon.add_args(parser)
        # Parse the arguments.
        config = Config(parser)
        # Set up logging directory
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey,
                config.netuid,
                "miner",
            )
        )
        # Ensure the directory for logging exists.
        os.makedirs(config.full_path, exist_ok=True)
        return config

    def setup_logging(self):
        # Activate Bittensor's logging with the set configurations.
        logging(config=self.config, logging_dir=self.config.full_path)
        logging.info(
            f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:"
        )
        logging.info(self.config)

    def setup_bittensor_objects(self):
        # Initialize Bittensor miner objects
        logging.info("Setting up Bittensor objects.")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = Subtensor(config=self.config)
        logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(netuid=self.config.netuid)
        logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            logging.error(
                f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()
        else:
            # Each miner gets a unique identity (UID) in the network.
            self.my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            logging.info(f"Running miner on uid: {self.my_uid}")

    def blacklist_fn(self, synapse: Challenge) -> Tuple[bool, str]:
        # Ignore requests from unrecognized entities.
        if synapse.dendrite.hotkey not in self.metagraph.hotkeys:
            logging.trace(f"Blacklisting unrecognized hotkey {synapse.dendrite.hotkey}")
            return True, None
        logging.trace(f"Not blacklisting recognized hotkey {synapse.dendrite.hotkey}")
        return False, None

    async def forward(self, synapse: Challenge) -> Challenge:
        """
        Processes the incoming 'Challenge' synapse by performing invariant checks.
        """
        startedAt = time.time_ns()
        try:
            synapse.output = self.engine.execute_checks(synapse)
            logging.info(
                f"Challenge processed: {synapse.tx.get('hash')} in {(time.time_ns() - startedAt) / 1e6}ms"
            )
        except Exception as e:
            logging.error(f"Engine failed to execute checks: {e}")
            synapse.output = []

        return synapse

    def setup_axon(self):
        # Build and link miner functions to the axon.
        self.axon = Axon(wallet=self.wallet, config=self.config)

        # Attach functions to the axon.
        logging.info("Attaching forward function to axon.")
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist_fn,
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

    def run(self):
        """
        Initiates and manages the main loop for the miner on the Bittensor network.
        """
        self.setup_axon()

        logging.info("Starting main loop")
        step = 0
        while True:
            try:
                # Periodically update our knowledge of the network graph.
                if step % 60 == 0:
                    self.metagraph.sync()
                    log = (
                        f"Block: {self.metagraph.block.item()} | "
                        f"Incentive: {self.metagraph.I[self.my_subnet_uid]} | "
                    )
                    logging.info(log)
                step += 1
                time.sleep(1)
            # If someone intentionally stops the miner, it'll safely terminate operations.
            except KeyboardInterrupt:
                self.axon.stop()
                logging.success("Miner killed by keyboard interrupt.")
                exit()
            # In case of unforeseen errors, the miner will log the error and continue operations.
            except Exception:
                logging.error(traceback.format_exc())
                continue

    def run_in_background_thread(self):
        """
        Starts the miner's operations in a separate background thread.
        """
        if not self.is_running:
            logging.debug("Starting miner in background thread.")
            self.should_exit = False
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            self.is_running = True
            logging.debug("Started")

    def stop_run_thread(self):
        """
        Stops the miner's operations that are running in the background thread.
        """
        if self.is_running:
            logging.debug("Stopping miner in background thread.")
            self.should_exit = True
            if self.thread is not None:
                self.thread.join(5)
            self.is_running = False
            logging.debug("Stopped")

    def __enter__(self):
        """
        Starts the miner's operations in a background thread upon entering the context.
        """
        self.run_in_background_thread()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Stops the miner's background operations upon exiting the context.
        """
        self.stop_run_thread()


# This is the main function, which runs the miner.
if __name__ == "__main__":
    with Miner() as miner:
        while True:
            logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
