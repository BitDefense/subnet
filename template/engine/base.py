from abc import ABC, abstractmethod
from typing import List
from template.protocol import Challenge

class InvariantsCheckEngine(ABC):
    @abstractmethod
    def execute_checks(self, challenge: Challenge) -> List[int]:
        """
        Executes the invariant checks against the provided challenge.
        
        Args:
            challenge (Challenge): The incoming challenge synapse.
            
        Returns:
            List[int]: A list of integers (1 for safe, 0 for unsafe) corresponding 
                       to each invariant in the challenge.
        """
        pass
