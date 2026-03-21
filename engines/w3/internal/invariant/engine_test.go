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
    "chain_id": 11155111,
    "block_number": 10492861,
    "tx": {
        "from": "0x0000440f05cE7110CBAD473f71d29350106d7488",
        "gas": 700000,
        "gasPrice": 3500148,
        "maxFeePerGas": 3500148,
        "maxPriorityFeePerGas": 2000000,
        "hash": "0xfa33e31835a7079a6b54d5e1c9aa106649693311cd7dac2c65306ea954565403",
        "input": "0x04e45aaf000000000000000000000000fff9976782d46cc05630d1f6ebab18b2324d6b14000000000000000000000000bd18476394435d3decacabf50df360ccc479cd7900000000000000000000000000000000000000000000000000000000000000640000000000000000000000000000440f05ce7110cbad473f71d29350106d74880000000000000000000000000000000000000000000000000cfbeb3e33db000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        "nonce": 42776,
        "to": "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E",
        "value": 0,
        "type": 2,
        "accessList": [],
        "chainId": 11155111,
        "v": 1,
        "r": "0xb56846c8b3d63c0c2eb79a5f709ca1502b0a82153e3e9be790655a246a245fb8",
        "s": "0x06d6b2c4da13bb8cb4994b6e991e0dc815470eed968129cfaaa055e88feda511"
    },
    "invariants": [
        {
            "contract": "0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
            "type": "unauthorized minting",
            "target": 10000000000,
            "storage": "0x325f5c7d0dbc1b2b9548e916a6eec23104865d21322b600caedb790388daaa4e",
            "slotType": "uint256"
        },
        {
            "contract": "0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
            "type": "unauthorized minting",
            "target": 10000000000,
            "storage": "0x325f5c7d0dbc1b2b9548e916a6eec23104865d21322b600caedb790388daaa4e",
            "slotType": "uint256"
        }
    ]
}`

func TestEngine_ExecuteCheck(t *testing.T) {
	r := require.New(t)
	ctx := context.Background()

	client, err := w3.Dial("https://ethereum-sepolia-rpc.publicnode.com")
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
