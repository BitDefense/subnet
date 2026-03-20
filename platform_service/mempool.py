import asyncio
import json
from web3 import AsyncWeb3, Web3
from web3.providers.eth_tester import EthereumTesterProvider
import bittensor as bt
from typing import List, Callable, Coroutine
from platform_service.database import SessionLocal, InvariantRecord

async def mempool_worker(rpc_url: str, queue: asyncio.Queue, get_monitored_contracts: Callable[[], List[str]]):
    """
    Subscribes to pending transactions and filters them based on monitored contracts.
    """
    bt.logging.info(f"Connecting to mempool at {rpc_url}")
    
    try:
        # Use AsyncWeb3 for subscription
        w3 = AsyncWeb3(AsyncWeb3.WebSocketProvider(rpc_url))
        
        # In a real scenario, we'd use w3.eth.subscribe('pending_transactions')
        # But some nodes don't support it directly. We'll use a loop for now.
        
        async for tx_hash in w3.eth.subscribe("pending_transactions"):
            try:
                tx = await w3.eth.get_transaction(tx_hash)
                if tx and tx.get("to"):
                    monitored_contracts = get_monitored_contracts()
                    if tx["to"].lower() in monitored_contracts:
                        bt.logging.info(f"Matched monitored contract: {tx['to']}")
                        # Convert AttributeDict/HexBytes to serializable dict
                        tx_json = Web3.to_json(tx)
                        await queue.put(json.loads(tx_json))
            except Exception as e:
                bt.logging.error(f"Error processing transaction {tx_hash.hex()}: {e}")
                
    except Exception as e:
        bt.logging.error(f"Mempool connection error: {e}")
        # Reconnection strategy would go here
        await asyncio.sleep(5)
        await mempool_worker(rpc_url, queue, get_monitored_contracts)

def get_monitored_contracts_from_db() -> List[str]:
    """
    Utility to fetch monitored contracts from the database.
    """
    db = SessionLocal()
    try:
        invs = db.query(InvariantRecord).filter(InvariantRecord.is_active == True).all()
        return [inv.contract.lower() for inv in invs]
    finally:
        db.close()
