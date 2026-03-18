
import bittensor as bt
import numpy as np

def check_subnet_state():
    netuid = 2
    subtensor = bt.Subtensor(network="local")
    metagraph = subtensor.metagraph(netuid)
    
    print(f"Subnet {netuid} State:")
    print(f"Number of neurons: {metagraph.n}")
    
    # Check UIDs with non-zero incentive or emission
    for uid in range(metagraph.n):
        incentive = metagraph.I[uid]
        emission = metagraph.E[uid]
        
        if incentive > 0 or emission > 0:
            print(f"\nUID {uid}:")
            print(f"  Hotkey: {metagraph.hotkeys[uid]}")
            print(f"  Stake: {metagraph.S[uid]}")
            print(f"  Incentive: {incentive}")
            print(f"  Emissions: {emission}")
            print(f"  Validator Permit: {metagraph.validator_permit[uid]}")
            
    print("\nChecking for weights...")
    # In some bittensor versions, weights are in metagraph.weights
    if hasattr(metagraph, "weights"):
        for i, row in enumerate(metagraph.weights):
            for j, val in enumerate(row):
                if val > 0:
                    print(f"  UID {i} -> UID {j}: {val}")
    else:
        # Try metagraph.W
        try:
            weights = metagraph.W
            for i in range(len(weights)):
                for j in range(len(weights[i])):
                    if weights[i][j] > 0:
                        print(f"  UID {i} -> UID {j}: {weights[i][j]}")
        except:
            print("Could not find weights in metagraph.")

if __name__ == "__main__":
    check_subnet_state()
