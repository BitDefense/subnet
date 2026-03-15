# BitDefense Protocol Design - Challenge Synapse

## Context
The BitDefense subnet analyzes Ethereum transactions in real-time, checking them against specified invariants (e.g., debt-to-collateral ratio, unauthorized minting).

The validator sends a transaction payload and a list of invariants. The miner analyzes the transaction and responds with an array indicating pass (1) or fail (0) for each invariant check.

## Architecture

We will implement the protocol definition in `template/protocol.py`. We will use Pydantic `BaseModel`s for strictly typed, serializable structures that closely mirror the data in `challenge_example.json`.

### Components

**1. Data Models**
*   `TransactionPayload(BaseModel)`: Explicitly defines the fields of an Ethereum transaction payload (type, chainId, nonce, gasPrice, gas, to, value, input, r, s, v, hash, blockHash, blockNumber, transactionIndex, from). All fields will be typed as strings (representing Hex values).
*   `Transaction(BaseModel)`: Wraps the transaction `hash` and the `payload`.
*   `Invariant(BaseModel)`: Defines the structure for a single invariant check (`contract`, `type`, `target`, `storage`).

**2. Synapse**
*   `Challenge(bt.Synapse)`: The core communication protocol.
    *   **Inputs (Validator -> Miner):**
        *   `chain_id`: str (e.g., "1" for mainnet)
        *   `tx`: `Transaction`
        *   `invariants`: `List[Invariant]`
    *   **Outputs (Miner -> Validator):**
        *   `output`: `Optional[List[int]]` = None. The miner sets this field.

**3. Deserialization**
The `Challenge.deserialize()` method will simply return the `output` field (the `List[int]`), making it easy for the validator to grab the results.

## Data Flow
1.  **Validator** constructs `TransactionPayload`, `Transaction`, and a list of `Invariant` objects.
2.  **Validator** instantiates a `Challenge` synapse with `chain_id`, `tx`, and `invariants`.
3.  **Validator** queries the **Miner**'s dendrite with the `Challenge` synapse.
4.  **Miner** receives the `Challenge` synapse.
5.  **Miner** inspects `tx.payload` and `invariants`.
6.  **Miner** evaluates the rules and populates `Challenge.output` with a list of integers (e.g., `[1, 0, 1]`).
7.  **Miner** returns the modified `Challenge` synapse.
8.  **Validator** receives the response and calls `Challenge.deserialize()` to get the `List[int]` result.

## Trade-offs
*   **Why custom Pydantic models instead of raw Web3 types?** Network serialization. Bittensor transmits data as JSON via Pydantic. Web3 library types (like `HexBytes` or specific custom objects) often cause serialization failures across the wire. Explicit string-based Pydantic models guarantee successful transmission and provide clear typing for IDEs.