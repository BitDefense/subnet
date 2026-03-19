import bittensor as bt
print(f"Bittensor version: {bt.__version__}")
try:
    w = bt.wallet()
    print(f"Wallet mock exists: {hasattr(w, 'mock')}")
except:
    pass
print(f"bt.MockWallet exists: {hasattr(bt, 'MockWallet')}")
print(f"bt.mock exists: {hasattr(bt, 'mock')}")
if hasattr(bt, 'mock'):
    print(f"bt.mock attributes: {dir(bt.mock)}")
