# Validator Query Strategy Design - Random Multi-Miner Challenge

## Context
The BitDefense validator ensures network security by challenging multiple miners simultaneously with an Ethereum transaction and a set of invariants. The validator then collects and compares their responses to determine rewards.

This design covers the strategy for selecting miners and querying them with a mock challenge.

## Architecture

We will implement the query strategy in `template/validator/forward.py`.

### Components

**1. Challenge Loader**
*   A utility function will be added to load `challenge_example.json`.
*   **Data Injection**: Since the `Invariant` Pydantic model now requires `storage_slot_type`, the loader will inject `"uint256"` as a default value for any invariant missing this field in the JSON.
*   The loader will return a fully instantiated `Challenge` synapse.

**2. Miner Selection Logic**
*   **Dynamic Sample Size**: For each forward pass, the validator will randomly choose a value $k \in \{3, 5, 7, 9\}$.
*   **Random UIDs**: Use the existing `get_random_uids(self, k=k)` utility to select $k$ active miner UIDs from the metagraph.

**3. Parallel Network Query**
*   **Dendrite Call**: The validator will use `self.dendrite` to query all selected miners in parallel.
*   **Synapse**: The `Challenge` synapse loaded from the JSON.
*   **Timeout**: A strict 10.0-second timeout will be applied to the query.
*   **Deserialization**: `deserialize=True` will be used to automatically extract the `List[int]` results from the miners.

## Data Flow
1.  **Start Forward Pass**: `forward(self)` is triggered by the validator loop.
2.  **Load Mock Challenge**: Load `challenge_example.json`, inject missing `storage_slot_type`, and create the `Challenge` object.
3.  **Pick K**: Randomly select $k \in [3, 5, 7, 9]$.
4.  **Pick Miners**: Get $k$ random miner UIDs.
5.  **Query Network**: Call `self.dendrite(axons, challenge, timeout=10.0, deserialize=True)`.
6.  **Receive Responses**: The call waits (up to 10s) and returns a list of responses (each being a deserialized `List[int]` or `[]` for failures, resulting in a `List[List[int]]`).
7.  **Log & Score**: Log the miner UIDs and their responses, then pass them to the reward mechanism.

## Error Handling & Edge Cases
*   **Insufficient Miners**: If the metagraph has fewer than 9 miners, `get_random_uids` should gracefully handle picking the maximum available up to $k$.
*   **JSON Load Failure**: If the JSON file is missing or malformed, the validator should log a critical error and skip the forward pass to avoid crashing.
*   **Timeouts/Empty Responses**: Miners that timeout or fail will return an empty list `[]` (as defined in our `Challenge.deserialize()` logic). The reward mechanism (next task) will handle these as failures (0 reward).
