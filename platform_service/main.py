import asyncio
import bittensor as bt
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from platform_service.database import InvariantRecord, SessionLocal, init_db
from platform_service.config import get_config
from platform_service.mempool import mempool_worker, get_monitored_contracts_from_db
from platform_service.dispatcher import Dispatcher
from pydantic import BaseModel
from typing import List
from datetime import datetime
from contextlib import asynccontextmanager

# Initialize database
init_db()

# Global state placeholders
app_config = None
app_wallet = None
app_subtensor = None
app_metagraph = None
app_queue = asyncio.Queue()
app_dispatcher = None

async def dispatch_loop():
    """
    Main loop to pull transactions from the queue and dispatch them.
    """
    bt.logging.info("Starting dispatch loop")
    while True:
        try:
            tx = await app_queue.get()
            if app_dispatcher:
                await app_dispatcher.dispatch(tx)
            app_queue.task_done()
        except Exception as e:
            bt.logging.error(f"Error in dispatch loop: {e}")
            await asyncio.sleep(1)

async def sync_metagraph():
    """
    Background task to sync the metagraph.
    """
    while True:
        try:
            if app_metagraph and app_subtensor:
                app_metagraph.resync(subtensor=app_subtensor)
                bt.logging.info("Metagraph synced")
            await asyncio.sleep(300)
        except Exception as e:
            bt.logging.error(f"Error syncing metagraph: {e}")
            await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_config, app_wallet, app_subtensor, app_metagraph, app_dispatcher

    # Initialize Bittensor configuration
    app_config = get_config()
    bt.logging(config=app_config)

    if app_config.mock:
        bt.logging.info("Running in MOCK mode")
        app_wallet = bt.MockWallet()
        app_subtensor = bt.MockSubtensor()
        app_metagraph = app_subtensor.metagraph(netuid=app_config.netuid)
    else:
        try:
            app_wallet = bt.wallet(config=app_config)
            # Check if wallet exists locally
            if not app_wallet.hotkey_file.exists_on_device():
                bt.logging.error(f"Hotkey not found at {app_wallet.hotkey_file.path}. Run with --mock or specify a valid wallet.")
                # We don't raise here to allow the API to at least start
            else:
                app_subtensor = bt.subtensor(config=app_config)
                app_metagraph = app_subtensor.metagraph(netuid=app_config.netuid)
        except Exception as e:
            bt.logging.error(f"Failed to initialize Bittensor objects: {e}")
            bt.logging.error("Continuing in limited mode. Dispatching will be disabled.")

    if app_wallet and app_metagraph:
        app_dispatcher = Dispatcher(wallet=app_wallet, metagraph=app_metagraph)

    # Start background tasks
    bt.logging.info("Initializing Platform background tasks...")
    mempool_task = asyncio.create_task(mempool_worker(app_config.rpc_url, app_queue, get_monitored_contracts_from_db))
    dispatch_task = asyncio.create_task(dispatch_loop())
    metagraph_task = asyncio.create_task(sync_metagraph())

    yield

    # Shutdown sequence
    bt.logging.info("Shutting down Platform service...")
    mempool_task.cancel()
    dispatch_task.cancel()
    metagraph_task.cancel()

    # Wait for tasks to clean up with a timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                mempool_task, dispatch_task, metagraph_task, return_exceptions=True
            ),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        bt.logging.warning(
            "Shutdown timed out, some tasks may have been killed forcefully."
        )
    except Exception as e:
        bt.logging.error(f"Error during shutdown: {e}")
    finally:
        from platform_service.database import engine
        engine.dispose()
        bt.logging.info("Platform service shutdown complete.")


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
