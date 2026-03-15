# Miner Implementation & Invariants Engine Design

## Context
The BitDefense miner is responsible for receiving `Challenge` synapses (containing an Ethereum transaction and a list of invariants) and determining if the transaction breaches any of those invariants. 

To keep the architecture flexible, the complex logic of forking Ethereum state and executing transactions will be abstracted behind an interface. This allows us to start with a mock implementation and plug in real blockchain simulation tools (like Anvil or Hardhat) later.

## Architecture

We will implement an `InvariantsCheckEngine` interface and integrate it into the core miner loop.

### Components

**1. Engine Interface (`template/engine/base.py`)**
*   `InvariantsCheckEngine`: An Abstract Base Class (ABC).
    *   Defines the contract for all future engine implementations.
    *   Method: `execute_checks(self, challenge: Challenge) -> List[int]`

**2. Mock Implementation (`template/engine/mock.py`)**
*   `MockSafeOnlyInvariantsCheckEngine`: Inherits from `InvariantsCheckEngine`.
    *   Purpose: A placeholder engine for initial testing and validation of the network communication.
    *   Implementation: Overrides `execute_checks`. It reads the `challenge.invariants` list and returns a list of `1`s (representing "safe") that is the exact same length as the input list.

**3. Miner Integration (`neurons/miner.py`)**
*   The main `Miner` class (which inherits from `BaseMinerNeuron`) needs to be updated.
*   **Initialization**: The miner will instantiate `MockSafeOnlyInvariantsCheckEngine` during its `__init__` or setup phase.
*   **Forward Pass**: The `forward` method is the entry point for incoming requests. 
    *   It will accept the `Challenge` synapse.
    *   It will call `self.engine.execute_checks(synapse)` to get the result array.
    *   It will assign the array to `synapse.output`.
    *   It will return the updated `synapse`.

## Data Flow
1.  **Validator** sends a `Challenge` synapse over the network.
2.  **Miner**'s axon receives the `Challenge` and routes it to `Miner.forward()`.
3.  `Miner.forward()` passes the synapse to `self.engine.execute_checks(synapse)`.
4.  `MockSafeOnlyInvariantsCheckEngine` counts the invariants and returns an array like `[1, 1]`.
5.  `Miner.forward()` assigns `[1, 1]` to `synapse.output` and returns the synapse.
6.  The Bittensor network serializes and sends the response back to the validator.

## Error Handling & Edge Cases
*   **Empty Invariants**: If `challenge.invariants` is empty, the engine should return an empty list `[]`.
*   **Engine Failure**: The miner's `forward` function should wrap the engine execution in a basic `try/except` block. If the engine crashes unexpectedly, it should log the error and potentially return `None` or an empty list to avoid crashing the entire miner process.