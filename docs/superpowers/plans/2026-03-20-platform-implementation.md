# Platform Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Platform service that ingests Ethereum Sepolia mempool transactions and dispatches them to Validators via a Round-Robin strategy, while managing a registry of contract invariants.

**Architecture:** A FastAPI-based service with an asynchronous mempool worker (Web3.py) and an internal task queue for buffered dispatching to Validators using Bittensor's `MempoolTransaction` synapse.

**Tech Stack:** Python, FastAPI, Web3.py, SQLAlchemy, SQLite, Bittensor SDK.

---

### Task 1: Protocol Update

**Files:**
- Modify: `template/protocol.py`

- [ ] **Step 1: Add the `MempoolTransaction` synapse class**

```python
class MempoolTransaction(bt.Synapse):
    """
    Synapse representing a raw Ethereum transaction sent from Platform to Validator.
    """
    tx: typing.Dict[str, typing.Any]
    received: bool = False

    def deserialize(self) -> bool:
        return self.received
```

- [ ] **Step 2: Commit**

```bash
git add template/protocol.py
git commit -m "feat: add MempoolTransaction synapse to protocol"
```

---

### Task 3: Platform API & Database (FastAPI)

**Files:**
- Create: `platform/main.py`
- Create: `platform/database.py`
- Test: `tests/platform/test_api.py`

- [ ] **Step 1: Implement SQLite/SQLAlchemy setup in `platform/database.py`**

```python
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class InvariantRecord(Base):
    __tablename__ = "invariants"
    id = Column(Integer, primary_key=True)
    contract = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    storage = Column(String, nullable=False)
    storage_slot_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

engine = create_engine("sqlite:///./platform.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Implement FastAPI with Invariant endpoints in `platform/main.py`**

```python
from fastapi import FastAPI, Depends, HTTPException
from platform.database import InvariantRecord, SessionLocal
from pydantic import BaseModel

app = FastAPI()

class InvariantSchema(BaseModel):
    contract: str
    type: str
    target: str
    storage: str
    storage_slot_type: str

@app.post("/invariants")
async def create_invariant(inv: InvariantSchema):
    db = SessionLocal()
    db_inv = InvariantRecord(**inv.dict())
    db.add(db_inv)
    db.commit()
    db.close()
    return {"status": "created"}

@app.get("/invariants")
async def get_invariants():
    db = SessionLocal()
    invs = db.query(InvariantRecord).filter(InvariantRecord.is_active == True).all()
    db.close()
    return invs
```

- [ ] **Step 3: Commit**

```bash
git add platform/main.py platform/database.py
git commit -m "feat: implement Platform API and invariant endpoints"
```

---

### Task 4: Mempool Worker & Dispatcher

**Files:**
- Create: `platform/mempool.py`
- Create: `platform/dispatcher.py`

- [ ] **Step 1: Implement Round-Robin Dispatcher in `platform/dispatcher.py`**

```python
import bittensor as bt
from template.protocol import MempoolTransaction

class Dispatcher:
    def __init__(self, wallet, metagraph):
        self.wallet = wallet
        self.metagraph = metagraph
        self.dendrite = bt.dendrite(wallet=wallet)
        self.current_index = 0

    async def dispatch(self, tx_dict):
        validators = [axon for axon in self.metagraph.axons if axon.is_serving]
        if not validators: return
        
        target = validators[self.current_index % len(validators)]
        synapse = MempoolTransaction(tx=tx_dict)
        await self.dendrite(target, synapse)
        self.current_index += 1
```

- [ ] **Step 2: Implement Mempool worker in `platform/mempool.py`**

```python
import asyncio
from web3 import Web3

async def mempool_worker(rpc_url, queue):
    w3 = Web3(Web3.WebsocketProvider(rpc_url))
    async for tx_hash in w3.eth.subscribe('pending_transactions'):
        tx = w3.eth.get_transaction(tx_hash)
        await queue.put(dict(tx))
```

- [ ] **Step 3: Commit**

```bash
git add platform/mempool.py platform/dispatcher.py
git commit -m "feat: implement mempool worker and round-robin dispatcher"
```

---

### Task 5: Validator Integration

**Files:**
- Modify: `neurons/validator.py`

- [ ] **Step 1: Add `MempoolTransaction` axon handler**

```python
def mempool_handler(synapse: MempoolTransaction) -> MempoolTransaction:
    bt.logging.info(f"Received mempool transaction: {synapse.tx['hash']}")
    synapse.received = True
    # Logic to trigger challenge with local invariants
    return synapse
```

- [ ] **Step 2: Implement background polling task for invariants**

- [ ] **Step 3: Commit**

```bash
git add neurons/validator.py
git commit -m "feat: integrate validator with platform service"
```
