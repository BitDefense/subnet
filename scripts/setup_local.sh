#!/bin/bash

export NETWORK_URL=ws://127.0.0.1:9945
export WALLET_PATH=~/.bittensor/wallets
export WALLET_SETTINGS="--wallet-path $WALLET_PATH --no-use-password --n-words 12 --overwrite"

# Create and set up wallets
# This section can be skipped if wallets are already set up
if [ ! -f ".wallets_setup" ]; then
    btcli wallet new_coldkey --wallet-name owner --hotkey default $WALLET_SETTINGS
    btcli wallet new_hotkey --wallet-name owner --hotkey default $WALLET_SETTINGS
    btcli wallet new_coldkey --wallet-name validator --hotkey default $WALLET_SETTINGS
    btcli wallet new_hotkey --wallet-name validator --hotkey default $WALLET_SETTINGS
    btcli wallet new_coldkey --wallet-name miner --hotkey default $WALLET_SETTINGS
    btcli wallet new_hotkey --wallet-name miner --hotkey default $WALLET_SETTINGS
    touch ".wallets_setup"
fi

export BT_OWNER_TOKEN_WALLET=$(grep -E -o '"ss58Address"\s*:\s*"[^"]*"' $WALLET_PATH/owner/coldkeypub.txt | cut -d'"' -f4)
export BT_MINER_TOKEN_WALLET=$(grep -E -o '"ss58Address"\s*:\s*"[^"]*"' $WALLET_PATH/miner/coldkeypub.txt | cut -d'"' -f4)
export BT_VALIDATOR_TOKEN_WALLET=$(grep -E -o '"ss58Address"\s*:\s*"[^"]*"' $WALLET_PATH/validator/coldkeypub.txt | cut -d'"' -f4)

echo "Owner Coldkey:" $BT_OWNER_TOKEN_WALLET
echo "Validator Coldkey:" $BT_VALIDATOR_TOKEN_WALLET
echo "Miner Coldkey:" $BT_MINER_TOKEN_WALLET

echo "Top up Owner"
btcli wallet transfer --network $NETWORK_URL --wallet-name alice --dest $BT_OWNER_TOKEN_WALLET --amount 10000 --no_prompt

echo "Top up Miner"
btcli wallet transfer --network $NETWORK_URL --wallet-name alice --dest $BT_MINER_TOKEN_WALLET --amount 10 --no_prompt

echo "Top up Validator"
btcli wallet transfer --network $NETWORK_URL --wallet-name alice --dest $BT_VALIDATOR_TOKEN_WALLET --amount 1000 --no_prompt

# Register a subnet (this needs to be run each time we start a new local chain)
btcli subnet create \
    --subnet-name bitdefense \
    --wallet-name owner \
    --hotkey default \
    --network $NETWORK_URL \
    --no-mev-protection \
    --no_prompt \
    --repo https://github.com/BitDefense/subnet \
    --contact a.v.gubin0911@gmail.com \
    --url "-" \
    --discord "-" \
    --description "-" \
    --logo-url "-" \
    --additional-info "-"

btcli subnet start \
    --netuid 2 \
    --wallet-name owner \
    --network $NETWORK_URL \
    --yes

btcli subnets register \
    --netuid 2 \
    --wallet-name miner \
    --hotkey default \
    --network $NETWORK_URL \
    --yes

btcli subnets register \
    --netuid 2 \
    --wallet-name validator \
    --hotkey default \
    --network $NETWORK_URL \
    --yes

# Add stake to the validator
btcli stake add \
    --netuid 2 \
    --wallet-name validator \
    --hotkey default \
    --network $NETWORK_URL \
    --amount 500 \
    --no-mev-protection \
    --unsafe \
    --yes

# Ensure both the miner and validator keys are successfully registered.
btcli subnet list --network $NETWORK_URL
btcli wallet overview --wallet-name validator --network $NETWORK_URL
btcli wallet overview --wallet-name miner --network $NETWORK_URL