import asyncio
import json
from bittensor import Wallet, Subtensor
from bittensor.utils.btlogging import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from platform_service.database import (
    InvariantRecord,
    Dashboard,
    Contract,
    DefenseAction,
    SessionLocal,
    init_db,
)
from platform_service.config import get_config
from platform_service.mempool import mempool_worker, get_monitored_contracts_from_db
from platform_service.dispatcher import Dispatcher
from pydantic import BaseModel, ConfigDict, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from web3 import AsyncWeb3, Web3, WebSocketProvider

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
                        full_block = await w3.eth.get_block(
                            new_block, full_transactions=True
                        )
                        txs = []
                        for tx in full_block.transactions:
                            tx_json = Web3.to_json(tx)
                            txs.append(json.loads(tx_json))
                        await dispatcher.dispatch(chain_id, new_block, txs)
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
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error syncing metagraph: {e}")
            await asyncio.sleep(10)


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
    # metagraph.sync(subtensor=subtensor)
    await get_chain_id(config.rpc_url)
    await get_initial_block(config.rpc_url)

    # mempool_task = asyncio.create_task(
    #     mempool_worker(config.rpc_url, queue, get_monitored_contracts_from_db)
    # )
    block_task = asyncio.create_task(block_worker(config.rpc_url))
    dispatch_task = asyncio.create_task(dispatch_loop())
    metagraph_task = asyncio.create_task(sync_metagraph(metagraph, subtensor))

    yield

    # Shutdown sequence
    logging.info("Shutting down Platform service...")
    # mempool_task.cancel()
    block_task.cancel()
    dispatch_task.cancel()
    metagraph_task.cancel()

    # Wait for tasks to clean up with a timeout
    try:
        await asyncio.wait_for(
            asyncio.gather(
                # mempool_task,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    variable: str
    storage: str
    slot_type: str
    network: str = "ethereum"
    defense_action_ids: List[int] = []


class InvariantResponse(InvariantSchema):
    id: int
    created_at: datetime
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_ids(cls, data: Any) -> Any:
        if hasattr(data, "defense_actions"):
            setattr(data, "defense_action_ids", [a.id for a in data.defense_actions])
        return data


class ContractCreate(BaseModel):
    address: str
    network: str
    variables: Dict = {}
    invariant_ids: List[int] = []


class ContractResponse(ContractCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def populate_ids(cls, data: Any) -> Any:
        if hasattr(data, "invariants"):
            setattr(data, "invariant_ids", [i.id for i in data.invariants])
        return data


class DefenseActionCreate(BaseModel):
    type: str
    network: str
    tg_api_key: Optional[str] = None
    tg_chat_id: Optional[str] = None
    role_id: Optional[str] = None
    function_sig: Optional[str] = None
    calldata: Optional[str] = None


class DefenseActionResponse(DefenseActionCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class DashboardCreate(BaseModel):
    name: str
    contract_ids: List[int] = []
    invariant_ids: List[int] = []
    defense_action_ids: List[int] = []


class DashboardResponse(DashboardCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class DashboardFlatResponse(BaseModel):
    id: int
    name: str
    contracts: List[ContractResponse]
    invariants: List[InvariantResponse]
    defense_actions: List[DefenseActionResponse]

    model_config = ConfigDict(from_attributes=True)


@app.get("/")
async def root():
    return {"message": "BitDefense Platform API"}


# --- Invariants CRUD ---
@app.post("/invariants", response_model=InvariantResponse)
async def create_invariant(inv: InvariantSchema, db: Session = Depends(get_db)):
    data = inv.model_dump(exclude={"defense_action_ids"})
    db_inv = InvariantRecord(**data)
    if inv.defense_action_ids:
        actions = (
            db.query(DefenseAction)
            .filter(DefenseAction.id.in_(inv.defense_action_ids))
            .all()
        )
        db_inv.defense_actions = actions
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)
    return db_inv


@app.get("/invariants", response_model=List[InvariantResponse])
async def get_invariants(db: Session = Depends(get_db)):
    return db.query(InvariantRecord).all()


@app.get("/invariants/{id}", response_model=InvariantResponse)
async def get_invariant(id: int, db: Session = Depends(get_db)):
    inv = db.query(InvariantRecord).filter(InvariantRecord.id == id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invariant not found")
    return inv


@app.put("/invariants/{id}", response_model=InvariantResponse)
async def update_invariant(
    id: int, inv: InvariantSchema, db: Session = Depends(get_db)
):
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == id).first()
    if not db_inv:
        raise HTTPException(status_code=404, detail="Invariant not found")

    for key, value in inv.model_dump(exclude={"defense_action_ids"}).items():
        setattr(db_inv, key, value)

    if inv.defense_action_ids is not None:
        actions = (
            db.query(DefenseAction)
            .filter(DefenseAction.id.in_(inv.defense_action_ids))
            .all()
        )
        db_inv.defense_actions = actions

    db.commit()
    db.refresh(db_inv)
    return db_inv


@app.delete("/invariants/{id}")
async def delete_invariant(id: int, db: Session = Depends(get_db)):
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == id).first()
    if not db_inv:
        raise HTTPException(status_code=404, detail="Invariant not found")
    db.delete(db_inv)
    db.commit()
    return {"message": "Invariant deleted"}


# --- Contracts CRUD ---
@app.post("/contracts", response_model=ContractResponse)
async def create_contract(contract: ContractCreate, db: Session = Depends(get_db)):
    data = contract.model_dump(exclude={"invariant_ids"})
    db_contract = Contract(**data)
    if contract.invariant_ids:
        invs = (
            db.query(InvariantRecord)
            .filter(InvariantRecord.id.in_(contract.invariant_ids))
            .all()
        )
        db_contract.invariants = invs
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract


@app.get("/contracts", response_model=List[ContractResponse])
async def get_contracts(db: Session = Depends(get_db)):
    return db.query(Contract).all()


@app.get("/contracts/{id}", response_model=ContractResponse)
async def get_contract(id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(Contract.id == id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@app.put("/contracts/{id}", response_model=ContractResponse)
async def update_contract(
    id: int, contract: ContractCreate, db: Session = Depends(get_db)
):
    db_contract = db.query(Contract).filter(Contract.id == id).first()
    if not db_contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    for key, value in contract.model_dump(exclude={"invariant_ids"}).items():
        setattr(db_contract, key, value)

    if contract.invariant_ids is not None:
        invs = (
            db.query(InvariantRecord)
            .filter(InvariantRecord.id.in_(contract.invariant_ids))
            .all()
        )
        db_contract.invariants = invs

    db.commit()
    db.refresh(db_contract)
    return db_contract


@app.delete("/contracts/{id}")
async def delete_contract(id: int, db: Session = Depends(get_db)):
    db_contract = db.query(Contract).filter(Contract.id == id).first()
    if not db_contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    db.delete(db_contract)
    db.commit()
    return {"message": "Contract deleted"}


# --- Defense Actions CRUD ---
@app.post("/defense-actions", response_model=DefenseActionResponse)
async def create_defense_action(
    action: DefenseActionCreate, db: Session = Depends(get_db)
):
    db_action = DefenseAction(**action.model_dump())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action


@app.get("/defense-actions", response_model=List[DefenseActionResponse])
async def get_defense_actions(db: Session = Depends(get_db)):
    return db.query(DefenseAction).all()


@app.get("/defense-actions/{id}", response_model=DefenseActionResponse)
async def get_defense_action(id: int, db: Session = Depends(get_db)):
    action = db.query(DefenseAction).filter(DefenseAction.id == id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Defense Action not found")
    return action


@app.put("/defense-actions/{id}", response_model=DefenseActionResponse)
async def update_defense_action(
    id: int, action: DefenseActionCreate, db: Session = Depends(get_db)
):
    db_action = db.query(DefenseAction).filter(DefenseAction.id == id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="Defense Action not found")

    for key, value in action.model_dump().items():
        setattr(db_action, key, value)

    db.commit()
    db.refresh(db_action)
    return db_action


@app.delete("/defense-actions/{id}")
async def delete_defense_action(id: int, db: Session = Depends(get_db)):
    db_action = db.query(DefenseAction).filter(DefenseAction.id == id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="Defense Action not found")
    db.delete(db_action)
    db.commit()
    return {"message": "Defense Action deleted"}


# --- Dashboards CRUD ---
@app.post("/dashboards", response_model=DashboardResponse)
async def create_dashboard(dash: DashboardCreate, db: Session = Depends(get_db)):
    data = dash.model_dump(
        exclude={"contract_ids", "invariant_ids", "defense_action_ids"}
    )
    db_dash = Dashboard(**data)

    if dash.contract_ids:
        db_dash.contracts = (
            db.query(Contract).filter(Contract.id.in_(dash.contract_ids)).all()
        )
    if dash.invariant_ids:
        db_dash.invariants = (
            db.query(InvariantRecord)
            .filter(InvariantRecord.id.in_(dash.invariant_ids))
            .all()
        )
    if dash.defense_action_ids:
        db_dash.defense_actions = (
            db.query(DefenseAction)
            .filter(DefenseAction.id.in_(dash.defense_action_ids))
            .all()
        )

    db.add(db_dash)
    db.commit()
    db.refresh(db_dash)
    return db_dash


@app.get("/dashboards", response_model=List[DashboardResponse])
async def get_dashboards(db: Session = Depends(get_db)):
    return db.query(Dashboard).all()


# Specialized GET for Dashboard (Task 5)
@app.get("/dashboards/{id}", response_model=DashboardFlatResponse)
async def get_dashboard(id: int, db: Session = Depends(get_db)):
    db_dash = db.query(Dashboard).filter(Dashboard.id == id).first()
    if not db_dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Gather flat hierarchy
    all_contracts = list(db_dash.contracts)
    all_invariants = set(db_dash.invariants)
    all_actions = set(db_dash.defense_actions)

    for c in all_contracts:
        for inv in c.invariants:
            all_invariants.add(inv)

    for inv in all_invariants:
        for action in inv.defense_actions:
            all_actions.add(action)

    return {
        "id": db_dash.id,
        "name": db_dash.name,
        "contracts": all_contracts,
        "invariants": list(all_invariants),
        "defense_actions": list(all_actions),
    }


@app.put("/dashboards/{id}", response_model=DashboardResponse)
async def update_dashboard(
    id: int, dash: DashboardCreate, db: Session = Depends(get_db)
):
    db_dash = db.query(Dashboard).filter(Dashboard.id == id).first()
    if not db_dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    db_dash.name = dash.name

    if dash.contract_ids is not None:
        db_dash.contracts = (
            db.query(Contract).filter(Contract.id.in_(dash.contract_ids)).all()
        )
    if dash.invariant_ids is not None:
        db_dash.invariants = (
            db.query(InvariantRecord)
            .filter(InvariantRecord.id.in_(dash.invariant_ids))
            .all()
        )
    if dash.defense_action_ids is not None:
        db_dash.defense_actions = (
            db.query(DefenseAction)
            .filter(DefenseAction.id.in_(dash.defense_action_ids))
            .all()
        )

    db.commit()
    db.refresh(db_dash)
    return db_dash


@app.delete("/dashboards/{id}")
async def delete_dashboard(id: int, db: Session = Depends(get_db)):
    db_dash = db.query(Dashboard).filter(Dashboard.id == id).first()
    if not db_dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    db.delete(db_dash)
    db.commit()
    return {"message": "Dashboard deleted"}


# --- Relationship Management (Task 4) ---
@app.post("/dashboards/{id}/contracts/{contract_id}")
async def link_dashboard_contract(
    id: int, contract_id: int, db: Session = Depends(get_db)
):
    db_dash = db.query(Dashboard).filter(Dashboard.id == id).first()
    db_contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not db_dash or not db_contract:
        raise HTTPException(status_code=404, detail="Dashboard or Contract not found")
    if db_contract not in db_dash.contracts:
        db_dash.contracts.append(db_contract)
        db.commit()
    return {"message": "Linked dashboard to contract"}


@app.delete("/dashboards/{id}/contracts/{contract_id}")
async def unlink_dashboard_contract(
    id: int, contract_id: int, db: Session = Depends(get_db)
):
    db_dash = db.query(Dashboard).filter(Dashboard.id == id).first()
    db_contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not db_dash or not db_contract:
        raise HTTPException(status_code=404, detail="Dashboard or Contract not found")
    if db_contract in db_dash.contracts:
        db_dash.contracts.remove(db_contract)
        db.commit()
    return {"message": "Unlinked dashboard from contract"}


@app.post("/contracts/{id}/invariants/{inv_id}")
async def link_contract_invariant(id: int, inv_id: int, db: Session = Depends(get_db)):
    db_contract = db.query(Contract).filter(Contract.id == id).first()
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == inv_id).first()
    if not db_contract or not db_inv:
        raise HTTPException(status_code=404, detail="Contract or Invariant not found")
    if db_inv not in db_contract.invariants:
        db_contract.invariants.append(db_inv)
        db.commit()
    return {"message": "Linked contract to invariant"}


@app.delete("/contracts/{id}/invariants/{inv_id}")
async def unlink_contract_invariant(
    id: int, inv_id: int, db: Session = Depends(get_db)
):
    db_contract = db.query(Contract).filter(Contract.id == id).first()
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == inv_id).first()
    if not db_contract or not db_inv:
        raise HTTPException(status_code=404, detail="Contract or Invariant not found")
    if db_inv in db_contract.invariants:
        db_contract.invariants.remove(db_inv)
        db.commit()
    return {"message": "Unlinked contract from invariant"}


@app.post("/invariants/{id}/defense-actions/{action_id}")
async def link_invariant_action(id: int, action_id: int, db: Session = Depends(get_db)):
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == id).first()
    db_action = db.query(DefenseAction).filter(DefenseAction.id == action_id).first()
    if not db_inv or not db_action:
        raise HTTPException(
            status_code=404, detail="Invariant or Defense Action not found"
        )
    if db_action not in db_inv.defense_actions:
        db_inv.defense_actions.append(db_action)
        db.commit()
    return {"message": "Linked invariant to defense action"}


@app.delete("/invariants/{id}/defense-actions/{action_id}")
async def unlink_invariant_action(
    id: int, action_id: int, db: Session = Depends(get_db)
):
    db_inv = db.query(InvariantRecord).filter(InvariantRecord.id == id).first()
    db_action = db.query(DefenseAction).filter(DefenseAction.id == action_id).first()
    if not db_inv or not db_action:
        raise HTTPException(
            status_code=404, detail="Invariant or Defense Action not found"
        )
    if db_action in db_inv.defense_actions:
        db_inv.defense_actions.remove(db_action)
        db.commit()
    return {"message": "Unlinked invariant from defense action"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("platform_service.main:app", host=config.host, port=config.port)
