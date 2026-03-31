# BitDefense Subnet Docker Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a complete, configurable Docker Compose environment with 1 Platform Service, 3 Validators, and 10 Miner-Engine pairs.

**Architecture:** Use multi-stage Dockerfiles for Python and Go components. Orchestrate via Docker Compose using YAML anchors to minimize repetition while allowing full parameterization of CLI arguments and environment variables.

**Tech Stack:** Docker, Docker Compose, Python (uv), Go, PostgreSQL.

---

### Task 1: Create .env.example Template

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write the .env.example file**

```env
# Shared Configuration
NETUID=2
SUBTENSOR_NETWORK=local
ETH_RPC_URL=https://lb.drpc.live/ethereum/Auqt09rhqkw_pIYVQr9B-jk8RgZzA1YR8bOqehXRfUMv
ETH_PRIVATE_KEY=your_private_key_here

# Platform Service
POSTGRES_PASSWORD=postgres
PLATFORM_HOST=0.0.0.0
PLATFORM_PORT=8000
PLATFORM_WALLET_NAME=default
PLATFORM_WALLET_HOTKEY=default

# Validator Configuration
VALIDATOR_WALLET_NAME=validator
VALIDATOR_HOTKEY=default
VALIDATOR_AXON_PORT=8901

# Miner Configuration
MINER_WALLET_PREFIX=miner_
MINER_HOTKEY=default
MINER_START_PORT=8902
ENGINE_TYPE=remote
ENGINE_PORT=9000
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add .env.example template for docker environment"
```

---

### Task 2: Implement Dockerfile.platform

**Files:**
- Create: `Dockerfile.platform`

- [ ] **Step 1: Write the Dockerfile.platform content**

```dockerfile
# Use a multi-stage build with uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies separately to leverage Docker cache
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application
ADD . /app

# Final stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Expose port 8000
EXPOSE 8000

# Start the Platform service
ENTRYPOINT ["uv", "run", "python", "-m", "platform_service.main"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.platform
git commit -m "feat: add Dockerfile.platform for platform service"
```

---

### Task 3: Implement Dockerfile.validator

**Files:**
- Create: `Dockerfile.validator`

- [ ] **Step 1: Write the Dockerfile.validator content**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ADD . /app

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "neurons/validator/validator.py"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.validator
git commit -m "feat: add Dockerfile.validator for validator nodes"
```

---

### Task 4: Implement Dockerfile.miner

**Files:**
- Create: `Dockerfile.miner`

- [ ] **Step 1: Write the Dockerfile.miner content**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ADD . /app

FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

ENTRYPOINT ["python", "neurons/miner/miner.py"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.miner
git commit -m "feat: add Dockerfile.miner for miner nodes"
```

---

### Task 5: Implement Dockerfile.w3_engine

**Files:**
- Create: `Dockerfile.w3_engine`

- [ ] **Step 1: Write the Dockerfile.w3_engine content**

```dockerfile
# Build stage
FROM golang:1.22-bookworm AS builder

WORKDIR /app

# Copy go mod files
COPY engines/w3/go.mod engines/w3/go.sum ./
RUN go mod download

# Copy source code
COPY engines/w3/ ./

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o w3-engine cmd/main.go

# Final stage
FROM debian:bookworm-slim

WORKDIR /app

# Copy the binary from the builder
COPY --from=builder /app/w3-engine .

# Expose the engine port
EXPOSE 9000

# Start the engine
ENTRYPOINT ["./w3-engine"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile.w3_engine
git commit -m "feat: add Dockerfile.w3_engine for Go-based sidecars"
```

---

### Task 6: Implement docker-compose.yml (Base & Infrastructure)

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Write the base infrastructure and YAML anchors**

```yaml
version: '3.8'

x-python-base: &python-base
  env_file: .env
  volumes:
    - bittensor_wallets:/root/.bittensor/wallets
  networks:
    - bitdefense-net

x-miner-template: &miner-template
  <<: *python-base
  build:
    context: .
    dockerfile: Dockerfile.miner

x-engine-template: &engine-template
  build:
    context: .
    dockerfile: Dockerfile.w3_engine
  networks:
    - bitdefense-net

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: platform
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - bitdefense-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  platform:
    build:
      context: .
      dockerfile: Dockerfile.platform
    <<: *python-base
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    command: >
      --host ${PLATFORM_HOST:-0.0.0.0}
      --port ${PLATFORM_PORT:-8000}
      --rpc_url ${ETH_RPC_URL}
      --wallet.name ${PLATFORM_WALLET_NAME:-default}
      --wallet.hotkey ${PLATFORM_WALLET_HOTKEY:-default}
      --netuid ${NETUID:-2}
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --logging.info

networks:
  bitdefense-net:
    driver: bridge

volumes:
  postgres_data:
  bittensor_wallets:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose base infrastructure and anchors"
```

---

### Task 7: Add Validators to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add the 3 validator services**

```yaml
# Add to services: block in docker-compose.yml
  validator_1:
    build:
      context: .
      dockerfile: Dockerfile.validator
    <<: *python-base
    command: >
      --wallet.name ${VALIDATOR_WALLET_NAME:-validator}
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 8901
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --eth_rpc_url ${ETH_RPC_URL}
      --eth_private_key ${ETH_PRIVATE_KEY}

  validator_2:
    build:
      context: .
      dockerfile: Dockerfile.validator
    <<: *python-base
    command: >
      --wallet.name ${VALIDATOR_WALLET_NAME:-validator}
      --wallet.hotkey hotkey_2
      --netuid ${NETUID:-2}
      --axon.port 8902
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --eth_rpc_url ${ETH_RPC_URL}
      --eth_private_key ${ETH_PRIVATE_KEY}

  validator_3:
    build:
      context: .
      dockerfile: Dockerfile.validator
    <<: *python-base
    command: >
      --wallet.name ${VALIDATOR_WALLET_NAME:-validator}
      --wallet.hotkey hotkey_3
      --netuid ${NETUID:-2}
      --axon.port 8903
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --eth_rpc_url ${ETH_RPC_URL}
      --eth_private_key ${ETH_PRIVATE_KEY}
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add 3 validator nodes to docker-compose"
```

---

### Task 8: Add Miners and Engines to docker-compose.yml (1-5)

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add miner/engine pairs 1 to 5**

```yaml
# Add to services: block in docker-compose.yml
  w3_engine_1:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_1:
    <<: *miner-template
    command: >
      --wallet.name miner_1
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9001
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_1:9000

  w3_engine_2:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_2:
    <<: *miner-template
    command: >
      --wallet.name miner_2
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9002
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_2:9000

  w3_engine_3:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_3:
    <<: *miner-template
    command: >
      --wallet.name miner_3
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9003
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_3:9000

  w3_engine_4:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_4:
    <<: *miner-template
    command: >
      --wallet.name miner_4
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9004
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_4:9000

  w3_engine_5:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_5:
    <<: *miner-template
    command: >
      --wallet.name miner_5
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9005
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_5:9000
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add miner-engine pairs 1-5 to docker-compose"
```

---

### Task 9: Add Miners and Engines to docker-compose.yml (6-10)

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add miner/engine pairs 6 to 10**

```yaml
# Add to services: block in docker-compose.yml
  w3_engine_6:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_6:
    <<: *miner-template
    command: >
      --wallet.name miner_6
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9006
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_6:9000

  w3_engine_7:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_7:
    <<: *miner-template
    command: >
      --wallet.name miner_7
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9007
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_7:9000

  w3_engine_8:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_8:
    <<: *miner-template
    command: >
      --wallet.name miner_8
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9008
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_8:9000

  w3_engine_9:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_9:
    <<: *miner-template
    command: >
      --wallet.name miner_9
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9009
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_9:9000

  w3_engine_10:
    <<: *engine-template
    environment:
      - RPC=${ETH_RPC_URL}
  miner_10:
    <<: *miner-template
    command: >
      --wallet.name miner_10
      --wallet.hotkey default
      --netuid ${NETUID:-2}
      --axon.port 9010
      --logging.info
      --subtensor.network ${SUBTENSOR_NETWORK:-local}
      --engine.type remote
      --engine.remote_url http://w3_engine_10:9000
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add miner-engine pairs 6-10 to docker-compose"
```
