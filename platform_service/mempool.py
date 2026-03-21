import asyncio
import json
from web3 import AsyncWeb3, Web3, WebSocketProvider
from bittensor.utils.btlogging import logging
from typing import List, Callable
from platform_service.database import SessionLocal, InvariantRecord


async def mempool_worker(
    rpc_url: str, queue: asyncio.Queue, get_monitored_contracts: Callable[[], List[str]]
):
    """
    Subscribes to pending transactions and filters them based on monitored contracts.
    """
    logging.info(f"Connecting to mempool at {rpc_url}")

    while True:
        try:
            async with AsyncWeb3(WebSocketProvider(rpc_url)) as w3:
                # Subscribe to pending transactions
                await w3.eth.subscribe("drpc_pendingTransactions")
                logging.info("Subscribed to newPendingTransactions")

                async for response in w3.socket.process_subscriptions():
                    try:
                        raw_tx = response["result"]
                        logging.debug(
                            f"Receive pending transaction: {Web3.to_hex(raw_tx['hash'])}"
                        )
                        tx_json = Web3.to_json(raw_tx)
                        await queue.put(json.loads(tx_json))
                    except Exception as e:
                        logging.error(f"Error processing transaction: {e}")

        except Exception as e:
            logging.error(f"Mempool connection error: {e}")
            await asyncio.sleep(5)
            logging.info("Retrying mempool connection...")


def get_monitored_contracts_from_db() -> List[str]:
    """
    Utility to fetch monitored contracts from the database.
    """
    db = SessionLocal()
    try:
        invs = db.query(InvariantRecord).filter(InvariantRecord.is_active).all()
        return [inv.contract.lower() for inv in invs]
    finally:
        db.close()
