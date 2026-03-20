# BitDefense Platform Service

The Platform Service is a standalone component of the BitDefense subnet. It bridges real-time Ethereum Sepolia mempool data with the Bittensor network and provides a registry for security invariants.

## Features
- **Mempool Ingestion**: Streams pending transactions from Ethereum Sepolia via WebSockets.
- **Round-Robin Dispatch**: Fairly distributes matched transactions across subnet validators.
- **Invariant Management**: Public API for registering and polling security invariants.
- **Persistent Storage**: Uses SQLite for local rule management.

## Prerequisites
- **Ethereum RPC**: An Infura, Alchemy, or other RPC node with WebSocket support for Sepolia.
- **Bittensor Wallet**: A registered coldkey/hotkey for subnet participation.
- **Python 3.10+**: Managed via `uv`.

## Installation

### Using `uv` (Recommended)
```bash
# Clone the repository
git clone <repo_url>
cd bitdefense/subnet

# Sync dependencies
uv sync
```

## Running the Service

### Local Mode
```bash
uv run uvicorn platform_service.main:app --host 0.0.0.0 --port 8000 --reload
```

### Mock Mode (No wallet required)
```bash
uv run uvicorn platform_service.main:app --host 0.0.0.0 --port 8000 -- --mock
```

### With Bittensor Arguments
```bash
uv run uvicorn platform_service.main:app --host 0.0.0.0 --port 8000 -- \
    --rpc_url wss://sepolia.infura.io/ws/v3/your_api_key \
    --wallet.name your_wallet \
    --wallet.hotkey your_hotkey \
    --netuid 21 \
    --subtensor.network testnet
```

## API Documentation
Once running, you can access the interactive API docs at:
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints
- `POST /invariants`: Register a new contract for monitoring.
- `GET /invariants`: List all active invariants.

## Docker Support
Build the container:
```bash
docker build -t bitdefense-platform -f Dockerfile.platform .
```

Run the container:
```bash
docker run -p 8000:8000 bitdefense-platform
```

## Configuration
Arguments can be passed via the CLI:
- `--rpc_url`: WebSocket RPC URL for Ethereum.
- `--api_key`: Simple API key for registration security.
- `--polling_interval`: Frequency for validators to fetch new invariants.
