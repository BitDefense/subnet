package invariant_test

import (
	"context"
	"encoding/json"
	"fmt"
	"testing"
	"time"

	"github.com/BitDefense/subnet/engines/w3/internal/invariant"
	"github.com/BitDefense/subnet/engines/w3/internal/models"
	"github.com/lmittmann/w3"
	"github.com/stretchr/testify/require"
)

var txPayloadJson = `{
    "chain_id": 1,
	"block_number": 24642610,
    "tx": {
        "hash": "0x057c9958ee0d890f6bcbc11d826537cf241091248f89bf0e8d5e9344c5c42040",
        "payload": {
            "type": "0x2",
            "chainId": "0x1",
            "nonce": "0x2",
            "gas": "0xb2a5",
            "maxFeePerGas": "0xb1c212e",
            "maxPriorityFeePerGas": "0x1",
            "to": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "value": "0x0",
            "accessList": [],
            "input": "0xa9059cbb000000000000000000000000bfef726eda93309fcc6d153b83648c827277828f0000000000000000000000000000000000000000000000000000000000000262",
            "r": "0xbb53fea0ed2a6a56054d5f7525c204467a10b12fa3f312d27b4e4ed78d0e6eb",
            "s": "0x71a0880775f54f860c519255478dfab8ca5f03fa8c50fc49f00634b42e7bd50",
            "yParity": "0x1",
            "v": "0x1",
            "hash": "0x057c9958ee0d890f6bcbc11d826537cf241091248f89bf0e8d5e9344c5c42040",
            "blockHash": "0x7f15a10b13565dcf386e28f909b68a655650865ebc246cc47555e4359e7f7eb0",
            "blockNumber": "0x1780433",
            "transactionIndex": "0xc9",
            "from": "0x38361883863dfe69024fbb56d9e58417ef7b36e7",
            "gasPrice": "0xa4077bd",
            "blockTimestamp": "0x69b2eb33"
        }
    },
    "invariants": [
        {
            "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "type": "debt-to-collateral ratio",
            "target": 8000,
            "storage": "0x057c9958ee0d890f6bcbc11d826537cf241091248f89bf0e8d5e9344c5c42040"
        },
        {
            "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "type": "unauthorized minting",
            "target": 10000000000,
            "storage": "0x057c9958ee0d890f6bcbc11d826537cf241091248f89bf0e8d5e9344c5c42040"
        }
    ]
}`

func TestEngine_ExecuteCheck(t *testing.T) {
	r := require.New(t)
	ctx := context.Background()

	client, err := w3.Dial("https://ethereum-rpc.publicnode.com")
	r.NoError(err)

	engine := invariant.NewEngine(client)

	challenge := models.Challenge{}
	err = json.Unmarshal([]byte(txPayloadJson), &challenge)
	r.NoError(err)

	start := time.Now()
	result, err := engine.ExecuteCheck(ctx, challenge)
	fmt.Println(time.Since(start))

	r.NoError(err)
	r.Equal([]int{1, 1}, result)
}
