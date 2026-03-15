from typing import List
from template.protocol import Challenge
from template.engine.base import InvariantsCheckEngine

class MockSafeOnlyInvariantsCheckEngine(InvariantsCheckEngine):
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Mock implementation that always returns 1 (safe) for every invariant.
        """
        return [1] * len(challenge.invariants)
