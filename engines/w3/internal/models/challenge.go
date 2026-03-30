package models

import (
	"fmt"
	"math/big"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/common/hexutil"
	"github.com/ethereum/go-ethereum/core/types"
)

type Challenge struct {
	ChainID     *big.Int                    `json:"chain_id"`
	BlockNumber *big.Int                    `json:"block_number"`
	Tx          *EthereumTransactionPayload `json:"tx"`
	Invariants  []Invariant                 `json:"invariants"`
}

func (c Challenge) InvariantSlotMap() map[common.Address]map[common.Hash]*InvariantIndex {
	out := make(map[common.Address]map[common.Hash]*InvariantIndex)
	for idx, inv := range c.Invariants {
		if _, ok := out[inv.Contract]; !ok {
			out[inv.Contract] = make(map[common.Hash]*InvariantIndex)
		}
		out[inv.Contract][inv.Storage] = &InvariantIndex{
			Index:  idx,
			Type:   inv.Type,
			Target: inv.Target,
		}
	}
	return out
}

type EthereumTransactionPayload struct {
	Type                 *big.Int       `json:"type"`
	ChainID              *big.Int       `json:"chainId"`
	Nonce                *big.Int       `json:"nonce"`
	GasPrice             *big.Int       `json:"gasPrice"`
	Gas                  *big.Int       `json:"gas"`
	MaxFeePerGas         *big.Int       `json:"maxFeePerGas"`
	MaxPriorityFeePerGas *big.Int       `json:"maxPriorityFeePerGas"`
	To                   common.Address `json:"to"`
	Value                *big.Int       `json:"value"`
	Input                hexutil.Bytes  `json:"input"`
	R                    common.Hash    `json:"r"`
	S                    common.Hash    `json:"s"`
	V                    int64          `json:"v"`
	From                 common.Address `json:"from"`
	Hash                 common.Hash    `json:"hash"`
}

func (t *EthereumTransactionPayload) EthereumTx() (*types.Transaction, error) {
	switch t.Type.Int64() {
	case types.LegacyTxType:
		payload := types.NewTx(&types.LegacyTx{
			Nonce:    t.Nonce.Uint64(),
			GasPrice: t.GasPrice,
			Gas:      t.Gas.Uint64(),
			To:       &t.To,
			Value:    t.Value,
			Data:     t.Input,
		})

		signer := types.LatestSignerForChainID(t.ChainID)
		sig := append(t.R.Bytes(), t.S.Bytes()...)

		v := byte(0x0)
		if t.V == 1 {
			v = byte(0x1)
		}
		sig = append(sig, []byte{v}...)

		if len(sig) != 65 {
			return nil, fmt.Errorf("invalid signature length: %d", len(sig))
		}

		return payload.WithSignature(signer, sig)
	case types.DynamicFeeTxType:
		payload := types.NewTx(&types.DynamicFeeTx{
			ChainID:   t.ChainID,
			Nonce:     t.Nonce.Uint64(),
			GasTipCap: t.MaxPriorityFeePerGas,
			GasFeeCap: t.MaxFeePerGas,
			Gas:       t.Gas.Uint64(),
			To:        &t.To,
			Value:     t.Value,
			Data:      t.Input,
		})

		signer := types.LatestSignerForChainID(t.ChainID)
		sig := append(t.R.Bytes(), t.S.Bytes()...)

		v := byte(0x0)
		if t.V == 1 {
			v = byte(0x1)
		}
		sig = append(sig, []byte{v}...)

		if len(sig) != 65 {
			return nil, fmt.Errorf("invalid signature length: %d", len(sig))
		}

		return payload.WithSignature(signer, sig)
	default:
		return nil, fmt.Errorf("unsupproted tx type")
	}
}

type Invariant struct {
	Contract common.Address `json:"contract"`
	Type     string         `json:"type"`
	Target   *big.Int       `json:"target"`
	Storage  common.Hash    `json:"storage"`
	SlotType string         `json:"slotType"`
}

type InvariantIndex struct {
	Index  int
	Type   string
	Target *big.Int
}
