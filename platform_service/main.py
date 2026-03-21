import asyncio
from bittensor import Wallet, Subtensor
from bittensor.utils.btlogging import logging
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from platform_service.database import InvariantRecord, SessionLocal, init_db
from platform_service.config import get_config
from platform_service.mempool import mempool_worker, get_monitored_contracts_from_db
from platform_service.dispatcher import Dispatcher
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from web3 import AsyncWeb3, WebSocketProvider

# Initialize database
init_db()

# Global state
config = get_config()
wallet = Wallet(config=config)
subtensor = Subtensor(config=config)
metagraph = subtensor.metagraph(netuid=config.netuid)
queue = asyncio.Queue()
dispatcher = Dispatcher(wallet=wallet, metagraph=metagraph)

# Thread-safe (async-safe) block storage
current_block: Optional[int] = None
block_lock = asyncio.Lock()

chain_id: int


async def block_worker(rpc_url: str):
    """
    Subscribes to new blocks and updates current_block.
    """
    global current_block
    logging.info(f"Connecting to block subscriber at {rpc_url}")

    while True:
        try:
            async with AsyncWeb3(WebSocketProvider(rpc_url)) as w3:
                # Subscribe to new heads
                await w3.eth.subscribe("newHeads")
                logging.info("Subscribed to newHeads")

                async for response in w3.socket.process_subscriptions():
                    try:
                        new_block = int(response["result"]["number"])
                        async with block_lock:
                            current_block = new_block
                        logging.info(f"New block arrived: {current_block}")
                    except Exception as e:
                        logging.error(f"Error processing block update: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Block subscriber connection error: {e}")
            await asyncio.sleep(5)
            logging.info("Retrying block subscriber connection...")


async def dispatch_loop():
    """
    Main loop to pull transactions from the queue and dispatch them.
    """
    logging.info("Starting dispatch loop")
    while True:
        try:
            tx = await queue.get()
            # Read block number safely
            async with block_lock:
                block_to_send = current_block

            await dispatcher.dispatch(
                chain_id=chain_id, block_number=block_to_send, tx_dict=tx
            )
            queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error in dispatch loop: {e}")
            await asyncio.sleep(1)


async def sync_metagraph(metagraph, subtensor):
    """
    Background task to sync the metagraph.
    """
    while True:
        try:
            # Syncing metagraph is a blocking call, perform in thread
            await asyncio.to_thread(metagraph.sync, subtensor=subtensor)
            logging.info("Metagraph synced")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error syncing metagraph: {e}")
            await asyncio.sleep(60)


async def get_initial_block(rpc_url: str):
    """
    Fetches the initial block number from the RPC provider.
    """
    global current_block
    try:
        async with AsyncWeb3(WebSocketProvider(rpc_url)) as w3:
            block = await w3.eth.block_number
            async with block_lock:
                current_block = block
            logging.info(f"Initial block retrieved: {current_block}")
    except Exception as e:
        logging.error(f"Failed to retrieve initial block: {e}")


async def get_chain_id(rpc_url: str):
    """
    Fetches the initial chain ID from the RPC provider.
    """
    global chain_id
    try:
        async with AsyncWeb3(WebSocketProvider(rpc_url)) as w3:
            chain_id = await w3.eth.chain_id
            logging.info(f"Chain ID retrieved: {chain_id}")
    except Exception as e:
        logging.error(f"Failed to retrieve chain ID: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks
    logging.info("Initializing Platform background tasks...")
    metagraph.sync(subtensor=subtensor)
    await get_chain_id(config.rpc_url)
    await get_initial_block(config.rpc_url)

    mempool_task = asyncio.create_task(
        mempool_worker(config.rpc_url, queue, get_monitored_contracts_from_db)
    )
    block_task = asyncio.create_task(block_worker(config.rpc_url))
    dispatch_task = asyncio.create_task(dispatch_loop())
    metagraph_task = asyncio.create_task(sync_metagraph(metagraph, subtensor))

    yield

    # Shutdown sequence
    logging.info("Shutting down Platform service...")
    mempool_task.cancel()
    block_task.cancel()
    dispatch_task.cancel()
    metagraph_task.cancel()

    # Wait for tasks to clean up with a timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                mempool_task,
                block_task,
                dispatch_task,
                metagraph_task,
                return_exceptions=True,
            ),
            timeout=5.0,
        )
    except asyncio.TimeoutError:
        logging.warning(
            "Shutdown timed out, some tasks may have been killed forcefully."
        )
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
    finally:
        from platform_service.database import engine

        engine.dispose()
        logging.info("Platform service shutdown complete.")


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
    slot_type: str


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
    invs = db.query(InvariantRecord).filter(InvariantRecord.is_active).all()
    return invs


@app.get("/")
async def root():
    return {"message": "BitDefense Platform API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("platform_service.main:app", host=config.host, port=config.port)
