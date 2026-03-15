package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/BitDefense/subnet/engines/w3/config"
	"github.com/BitDefense/subnet/engines/w3/internal/api"
	"github.com/BitDefense/subnet/engines/w3/internal/invariant"
	"github.com/labstack/echo/v4"
	"github.com/lmittmann/w3"
	"github.com/rs/zerolog/log"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(),
		syscall.SIGINT,
		syscall.SIGTERM,
	)
	defer cancel()

	if err := run(ctx); err != nil {
		log.Fatal().Err(err).Msg("run application")
	}
}

func run(ctx context.Context) error {
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}

	client, err := w3.Dial(cfg.RPC)
	if err != nil {
		return fmt.Errorf("dial rpc: %w", err)
	}

	defer client.Close()

	engine := invariant.NewEngine(client)

	echoServer := echo.New()
	echoServer.HideBanner = true
	echoServer.Server.WriteTimeout = 10 * time.Second
	echoServer.Server.ReadTimeout = 10 * time.Second
	defer echoServer.Close()

	apiGroup := echoServer.Group("/api")
	apiHandler := api.NewHandler(engine)
	apiHandler.Register(apiGroup)

	wg := &sync.WaitGroup{}
	wg.Go(func() {
		addr := fmt.Sprintf("%s:%s", cfg.Host, cfg.Port)
		if err := echoServer.Start(addr); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error().Err(err).Msg("start http server")
		}
	})

	<-ctx.Done()
	log.Info().Msg("interrupted signal received, shutting down")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := echoServer.Shutdown(shutdownCtx); err != nil {
		log.Warn().Err(err).Msg("server shutdown failed")
	}

	log.Info().Msg("waiting for all goroutines to finish")

	wg.Wait()

	log.Info().Msg("gracefully shutdown")

	return nil
}
