package invariant

import (
	"context"
	"fmt"
	"strings"
	"sync"

	"github.com/BitDefense/subnet/engines/w3/internal/models"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/tracing"
	"github.com/lmittmann/w3"
	"github.com/lmittmann/w3/w3vm"
	"github.com/rs/zerolog/log"
)

type Engine struct {
	client            *w3.Client
	mu                *sync.RWMutex
	staleTransactions map[common.Hash]bool
}

func NewEngine(client *w3.Client) *Engine {
	return &Engine{
		client:            client,
		mu:                &sync.RWMutex{},
		staleTransactions: make(map[common.Hash]bool),
	}
}

func (e *Engine) ExecuteCheck(ctx context.Context, challenge models.Challenge) ([]int, error) {
	invariantsMap := challenge.InvariantSlotMap()
	result := make([]int, len(challenge.Invariants))

	// set all invariants as safe by default.
	for i := range result {
		result[i] = 1
	}

	if e.isStaleTx(challenge.Tx.Hash) {
		return result, nil
	}

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

		switch target.Type {
		case "==":
			if new.Big().Cmp(target.Target) != 0 {
				result[target.Index] = 0
			}
		case ">=":
			if new.Big().Cmp(target.Target) < 0 {
				result[target.Index] = 0
			}
		case "<=":
			if new.Big().Cmp(target.Target) > 0 {
				result[target.Index] = 0
			}
		case ">":
			if new.Big().Cmp(target.Target) <= 0 {
				result[target.Index] = 0
			}
		case "<":
			if new.Big().Cmp(target.Target) >= 0 {
				result[target.Index] = 0
			}
		}
	}

	reciept, err := vm.ApplyTx(ethTx, &tracing.Hooks{
		OnStorageChange: storageChangeHook,
	})
	if err != nil {
		if strings.Contains(err.Error(), "nonce too high") ||
			strings.Contains(err.Error(), "max fee per gas less than block base fee") ||
			strings.Contains(err.Error(), "nonce too low") ||
			strings.Contains(err.Error(), "insufficient funds") ||
			strings.Contains(err.Error(), "execution reverted") {

			e.markStaleTx(challenge.Tx.Hash)

			return result, nil
		}

		return nil, fmt.Errorf("apply tx: %w", err)
	}

	// it is mean that tx reverted, so all invariants are safe.
	if reciept.Err != nil {
	}

	log.Info().Msgf("Tx processed: %v", challenge.Tx.Hash.String())

	return result, nil
}

func (e *Engine) isStaleTx(txHash common.Hash) bool {
	e.mu.RLock()
	defer e.mu.RUnlock()

	return e.staleTransactions[txHash]
}

func (e *Engine) markStaleTx(txHash common.Hash) {
	e.mu.Lock()
	e.staleTransactions[txHash] = true
	e.mu.Unlock()
}
