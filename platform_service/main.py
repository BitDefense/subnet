import asyncio
import bittensor as bt
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from platform_service.database import InvariantRecord, SessionLocal, init_db
from platform_service.config import get_config
from platform_service.mempool import mempool_worker, get_monitored_contracts_from_db
from platform_service.dispatcher import Dispatcher
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

# Initialize database
init_db()

# Global state
config = get_config()
wallet = bt.wallet(config=config)
subtensor = bt.subtensor(config=config)
metagraph = subtensor.metagraph(netuid=config.netuid)
queue = asyncio.Queue()
dispatcher = Dispatcher(wallet=wallet, metagraph=metagraph)

async def dispatch_loop():
    """
    Main loop to pull transactions from the queue and dispatch them.
    """
    bt.logging.info("Starting dispatch loop")
    while True:
        try:
            tx = await queue.get()
            await dispatcher.dispatch(tx)
            queue.task_done()
        except Exception as e:
            bt.logging.error(f"Error in dispatch loop: {e}")
            await asyncio.sleep(1)

async def sync_metagraph():
    """
    Background task to sync the metagraph.
    """
    while True:
        try:
            metagraph.resync(subtensor=subtensor)
            bt.logging.info("Metagraph synced")
            await asyncio.sleep(300)
        except Exception as e:
            bt.logging.error(f"Error syncing metagraph: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks
    mempool_task = asyncio.create_task(mempool_worker(config.rpc_url, queue, get_monitored_contracts_from_db))
    dispatch_task = asyncio.create_task(dispatch_loop())
    metagraph_task = asyncio.create_task(sync_metagraph())
    
    yield
    
    # Cancel background tasks
    mempool_task.cancel()
    dispatch_task.cancel()
    metagraph_task.cancel()
    try:
        await asyncio.gather(mempool_task, dispatch_task, metagraph_task)
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class InvariantSchema(BaseModel):
    contract: str
    type: str
    target: str
    storage: str
    storage_slot_type: str

class InvariantResponse(InvariantSchema):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

@app.post("/invariants", response_model=InvariantResponse)
async def create_invariant(inv: InvariantSchema, db: Session = Depends(get_db)):
    db_inv = InvariantRecord(**inv.model_dump())
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)
    return db_inv

@app.get("/invariants", response_model=List[InvariantResponse])
async def get_invariants(db: Session = Depends(get_db)):
    invs = db.query(InvariantRecord).filter(InvariantRecord.is_active == True).all()
    return invs

@app.get("/")
async def root():
    return {"message": "BitDefense Platform API"}
