package models

import (
	"fmt"
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/types"
)

type Challenge struct {
	ChainID     *big.Int     `json:"chainId"`
	BlockNumber *big.Int     `json:"blockNumber"`
	Tx          *Transaction `json:"tx"`
	Invariants  []Invariant  `json:"invariants"`
}

func (c Challenge) InvariantSlotMap() map[common.Address]map[common.Hash]*InvariantIndex {
	out := make(map[common.Address]map[common.Hash]*InvariantIndex)
	for idx, inv := range c.Invariants {
		if _, ok := out[inv.Contract]; !ok {
			out[inv.Contract] = make(map[common.Hash]*InvariantIndex)
		}
		out[inv.Contract][inv.Storage] = &InvariantIndex{
			Index:  idx,
			Target: inv.Target,
		}
	}
	return out
}

type Transaction struct {
	Hash    string                     `json:"hash"`
	Payload EthereumTransactionPayload `json:"payload"`
}

type EthereumTransactionPayload struct {
	Type                 *hexutil.Big   `json:"type"`
	ChainID              *hexutil.Big   `json:"chainId"`
	Nonce                *hexutil.Big   `json:"nonce"`
	GasPrice             *hexutil.Big   `json:"gasPrice"`
	Gas                  *hexutil.Big   `json:"gas"`
	MaxFeePerGas         *hexutil.Big   `json:"maxFeePerGas"`
	MaxPriorityFeePerGas *hexutil.Big   `json:"maxPriorityFeePerGas"`
	To                   common.Address `json:"to"`
	Value                *hexutil.Big   `json:"value"`
	Input                hexutil.Bytes  `json:"input"`
	R                    *hexutil.Big   `json:"r"`
	S                    *hexutil.Big   `json:"s"`
	V                    *hexutil.Big   `json:"v"`
	From                 common.Address `json:"from"`
}

func (t *Transaction) EthereumTx() (*types.Transaction, error) {
	switch t.Payload.Type.ToInt().Int64() {
	case types.LegacyTxType:

		payload := types.NewTx(&types.LegacyTx{
			Nonce:    t.Payload.Nonce.ToInt().Uint64(),
			GasPrice: t.Payload.GasPrice.ToInt(),
			Gas:      t.Payload.Gas.ToInt().Uint64(),
			To:       &t.Payload.To,
			Value:    t.Payload.Value.ToInt(),
			Data:     t.Payload.Input,
		})

		signer := types.LatestSignerForChainID(t.Payload.ChainID.ToInt())
		sig := append(t.Payload.R.ToInt().Bytes(), t.Payload.S.ToInt().Bytes()...)
		sig = append(sig, t.Payload.V.ToInt().Bytes()...)

		return payload.WithSignature(signer, sig)
	case types.DynamicFeeTxType:
		payload := types.NewTx(&types.DynamicFeeTx{
			ChainID:   t.Payload.ChainID.ToInt(),
			Nonce:     t.Payload.Nonce.ToInt().Uint64(),
			GasTipCap: t.Payload.MaxPriorityFeePerGas.ToInt(),
			GasFeeCap: t.Payload.MaxFeePerGas.ToInt(),
			Gas:       t.Payload.Gas.ToInt().Uint64(),
			To:        &t.Payload.To,
			Value:     t.Payload.Value.ToInt(),
			Data:      t.Payload.Input,
		})

		signer := types.LatestSignerForChainID(t.Payload.ChainID.ToInt())
		sig := append(t.Payload.R.ToInt().Bytes(), t.Payload.S.ToInt().Bytes()...)
		sig = append(sig, t.Payload.V.ToInt().Bytes()...)

		return payload.WithSignature(signer, sig)
	default:
		return nil, fmt.Errorf("unsupproted tx type")
	}
}

type Invariant struct {
	Contract        common.Address `json:"contract"`
	Type            string         `json:"type"`
	Target          *big.Int       `json:"target"`
	Storage         common.Hash    `json:"storage"`
	StorageSlotType string         `json:"slotType"`
}

type InvariantIndex struct {
	Index  int
	Target *big.Int
}
