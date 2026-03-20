# Platform Service Design Specification

**Status:** Finalized (Draft)
**Date:** 2026-03-20
**Topic:** Standalone Platform service for mempool ingestion and invariant management.

## 1. Overview
The Platform Service is a standalone component of the BitDefense subnet. It bridges real-time Ethereum Sepolia mempool data with the Bittensor network and provides a registry for security invariants.

### Goals
- Ingest pending transactions from Ethereum Sepolia.
- Provide a public API for registering and retrieving security invariants.
- Dispatch relevant transactions to Validators in a fair, round-robin fashion.

## 2. Architecture

### 2.1 Components
- **FastAPI Web Server**: Handles invariant registration and polling.
- **Mempool Worker**: Connects to an Ethereum RPC (WS) to stream pending transactions.
- **Internal Task Queue**: An `asyncio.Queue` used to buffer transactions between ingestion and dispatch.
- **Dispatcher**: Maintains a metagraph view and manages the round-robin delivery of transactions to Validators with failover.
- **SQLite Database**: Stores invariants persistently via SQLAlchemy.

### 2.2 Data Flow
1. **User/Frontend** calls `POST /invariants` to add a contract and its monitoring rules.
2. **Validator** periodically calls `GET /invariants` to sync its local cache.
3. **Mempool Worker** detects a new pending transaction and pushes it to the **Internal Task Queue**.
4. **Dispatcher** pulls from the queue, checks for contract matches, and selects the next Validator (Round Robin).
5. If a dispatch fails, the **Dispatcher** immediately retries with the next Validator in the sequence.

## 3. Protocol & Synapses

### 3.1 Transaction Synapse
```python
class Transaction(bt.Synapse):
    """
    Synapse representing a raw Ethereum transaction sent from Platform to Validator.
    """
    tx: Dict[str, Any]  # The literal, flat Eth tx dictionary from the mempool
    received: bool = False
```

### 3.2 Invariant Model & Schema
```python
class Invariant(BaseModel):
    id: Optional[int] = None
    contract: str  # Index for fast lookups
    type: str
    target: str
    storage: str
    storage_slot_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
```

**Database Constraints**: Unique constraint on `(contract, type, target)`.

## 4. API Specification & Security

### 4.1 Invariant Management
- `POST /invariants`: Create a new invariant.
- `GET /invariants`: Retrieve all active invariants.

### 4.2 Security Strategy
- **Initial Phase**: Simple API Key required in headers (`X-API-KEY`).
- **Roadmap**: Transition to Bittensor hotkey signature verification (ECDSA) to ensure only authorized actors can register rules.

## 5. Resiliency & Performance

### 5.1 Connection Management
- **Exponential Backoff**: Automatic reconnection for WebSocket drops.
- **Heartbeats**: Periodic `ping/pong` to detect silent disconnects.

### 5.2 Burst Handling
- The **Internal Task Queue** acts as a buffer to handle high-volume spikes without dropping transactions.
- Dispatch rate limiting to avoid overwhelming Validator axons.

### 5.3 Dispatch Failover
- If a `Transaction` synapse request fails (timeout or error), the Dispatcher:
    1. Logs the failure for the specific Validator.
    2. Immediately attempts to dispatch to the *next* available Validator in the Round-Robin sequence.

## 6. Validator Integration
Validators must be updated to:
1. Expose an axon handler for the `Transaction` synapse.
2. Implement a background task to poll the Platform's `GET /invariants` endpoint every 60 seconds.
3. Maintain an in-memory cache of invariants for efficient matching.

