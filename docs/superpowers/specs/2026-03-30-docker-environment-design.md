# Design Spec: BitDefense Subnet Docker Environment

This document defines the architecture and configuration for a complete BitDefense subnet deployment using Docker Compose.

## 1. Overview
The goal is to provide a reproducible, containerized environment for the BitDefense subnet, consisting of:
- 1 Platform Service with PostgreSQL database.
- 3 Validator nodes.
- 10 Miner nodes, each paired with its own W3 Invariant Engine.

## 2. Architecture
### Network Layout
- All containers will reside on a single bridge network named `bitdefense-net`.
- Services will communicate using container names as hostnames (e.g., `miner_1` connects to `w3_engine_1:9000`).

### Components
| Component | Technology | Count | Role |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | Postgres 15 | 1 | Persistent storage for the Platform Service. |
| **Platform Service** | Python (FastAPI) | 1 | Orchestrates challenge distribution and invariant monitoring. |
| **Validator** | Python (Bittensor) | 3 | Queries miners, evaluates performance, and sets weights. |
| **Miner** | Python (Bittensor) | 10 | Performs security analysis and interfaces with W3 Engine. |
| **W3 Engine** | Go | 10 | Low-level EVM invariant analysis sidecar for miners. |

## 3. Dockerfile Specifications

### `Dockerfile.platform`
- Base: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`.
- Strategy: Multi-stage build to minimize final image size.
- Entrypoint: `uv run python -m platform_service.main`.

### `Dockerfile.validator`
- Base: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`.
- Strategy: Multi-stage build.
- Entrypoint: `python neurons/validator/validator.py`.

### `Dockerfile.miner`
- Base: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`.
- Strategy: Multi-stage build.
- Entrypoint: `python neurons/miner/miner.py`.

### `Dockerfile.w3_engine`
- Base: `golang:1.22-bookworm` (Builder) / `debian:bookworm-slim` (Runner).
- Strategy: Multi-stage Go build for a minimal binary.
- Entrypoint: Compiled `w3-engine` binary.

## 4. Configuration Strategy (Docker Compose)

### YAML Anchors
To avoid a massive `docker-compose.yml`, we will use anchors for:
- `x-python-base`: Shared environment variables and volumes for Python nodes.
- `x-miner-template`: Shared CLI arguments for miners.
- `x-engine-template`: Shared configuration for W3 engines.

### Parameterization
All sensitive and node-specific arguments will be exposed via:
1.  **Environment Variables**: For RPC URLs, private keys, and wallet names.
2.  **CLI Overrides**: In the `command` section of each service in `docker-compose.yml`.

### Persistence
- `postgres_data`: Volume for the database.
- `bittensor_wallets`: Shared volume for `.bittensor/wallets` to persist identity across container restarts.

## 5. Success Criteria
- `docker compose up` starts all 25+ services successfully.
- Platform service can connect to Postgres.
- Miners can connect to their respective W3 engines.
- Validators can reach the Ethereum RPC.
- All CLI arguments provided in the request are configurable.
