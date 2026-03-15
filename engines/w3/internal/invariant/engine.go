package invariant

import (
	"context"
	"fmt"

	"github.com/BitDefense/subnet/engines/w3/internal/models"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/tracing"
	"github.com/lmittmann/w3"
	"github.com/lmittmann/w3/w3vm"
)

type Engine struct {
	client *w3.Client
}

func NewEngine(client *w3.Client) *Engine {
	return &Engine{client: client}
}

func (e *Engine) ExecuteCheck(ctx context.Context, challenge models.Challenge) ([]int, error) {
	ethTx, err := challenge.Tx.EthereumTx()
	if err != nil {
		return nil, fmt.Errorf("create ethereum tx: %w", err)
	}

	vm, err := w3vm.New(
		w3vm.WithFork(e.client, challenge.BlockNumber),
	)
	if err != nil {
		return nil, fmt.Errorf("init vm: %w", err)
	}

	invariantsMap := challenge.InvariantSlotMap()
	result := make([]int, len(challenge.Invariants))

	// set all invariants as safe by default.
	for i := range result {
		result[i] = 1
	}

	storageChangeHook := func(addr common.Address, slot common.Hash, prev, new common.Hash) {
		contract, exists := invariantsMap[addr]
		if !exists {
			return
		}

		target, exists := contract[slot]
		if !exists {
			return
		}

		// TODO: check storage slot type to proper type conversion,
		// now we support only uint256 type.

		// if new value is greater than target value, then invariant is unsafe.
		if new.Big().Cmp(target.Target) > 0 {
			result[target.Index] = 0
		}
	}

	reciept, err := vm.ApplyTx(ethTx, &tracing.Hooks{
		OnStorageChange: storageChangeHook,
	})
	if err != nil {
		return nil, fmt.Errorf("apply tx: %w", err)
	}

	// it is mean that tx reverted, so all invariants are safe.
	if reciept.Err != nil {
	}

	return result, nil
}
