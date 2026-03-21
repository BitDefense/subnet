import httpx
from abc import ABC, abstractmethod
from typing import List
from bittensor.utils.btlogging import logging

# Bittensor Miner Template:
from template.protocol import Challenge


class InvariantsCheckEngine(ABC):
    @abstractmethod
    async def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Executes the invariant checks against the provided challenge.
        """
        pass


class SafeOnlyInvariantsCheckEngine(InvariantsCheckEngine):
    async def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Mock implementation that always returns 1 (safe) for every invariant.
        """
        return [1] * len(challenge.invariants)


class RemoteInvariantsCheckEngine(InvariantsCheckEngine):
    def __init__(self, remote_url: str):
        self.remote_url = remote_url

    async def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Executes the invariant checks by sending the challenge to a remote engine.
        """
        try:
            payload = challenge.dict()
            chain_id = int(payload["chain_id"])
            block_number = int(payload["block_number"])
            clean_invariants = []
            for inv in payload["invariants"]:
                clean_invariants.append(
                    {
                        "contract": inv["contract"],
                        "type": inv["type"],
                        "target": int(inv["target"]),
                        "storage": inv["storage"],
                        "slotType": inv.get("slot_type", "uint256"),
                    }
                )

            clean_payload = {
                "chain_id": chain_id,
                "block_number": block_number,
                "tx": payload["tx"],
                "invariants": clean_invariants,
            }

            # The Go engine API is under /api prefix and default port is 9000
            url = f"{self.remote_url}/api/check"

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=clean_payload, timeout=10.0)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logging.error(f"Failed to execute remote checks: {e}")
            raise e
