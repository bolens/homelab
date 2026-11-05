package main

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"syscall"
	"time"
)

func main() {
	if len(os.Args) == 2 && os.Args[1] == "healthcheck" {
		client := http.Client{Timeout: 2 * time.Second}
		resp, err := client.Get("http://127.0.0.1:8080/healthz")
		if err != nil {
			os.Exit(1)
		}
		resp.Body.Close()
		if resp.StatusCode != 200 {
			os.Exit(1)
		}
		return
	}

	if err := run(); err != nil {
		log.Print("publisher broker startup/serve failed")
		os.Exit(1)
	}
}
func run() error {
	path := os.Getenv("BROKER_CONFIG_FILE")
	if path == "" {
		path = "/etc/publisher-broker/config.json"
	}
	data, err := readPrivateFile(path)
	if err != nil {
		return err
	}
	var cfg config
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err = dec.Decode(&cfg); err != nil {
		return err
	}
	var extra any
	if dec.Decode(&extra) != io.EOF {
		return errDenied
	}
	raw, err := os.ReadFile(cfg.PublicKeyFile)
	if err != nil {
		return err
	}
	block, rest := pem.Decode(raw)
	if block == nil || len(rest) != 0 {
		return errDenied
	}
	public, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return err
	}
	key, ok := public.(ed25519.PublicKey)
	if !ok {
		return errDenied
	}
	raw, err = readPrivateFile(cfg.PrivateKeyFile)
	if err != nil {
		return err
	}
	private, err := appKey(raw)
	if err != nil {
		return err
	}
	if !regexp.MustCompile(`^[1-9][0-9]*$`).MatchString(cfg.AppID) {
		return errDenied
	}
	client := &http.Client{Timeout: 3 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errDenied }}
	handler, err := newBroker(cfg, key, &githubIssuer{baseURL: "https://api.github.com", appID: cfg.AppID, key: private, client: client})
	if err != nil {
		return err
	}
	srv := &http.Server{Addr: ":8080", Handler: handler, ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 4 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 16 << 10, ErrorLog: log.New(io.Discard, "", 0)}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdown)
	}()
	err = srv.ListenAndServe()
	if err == http.ErrServerClosed {
		return nil
	}
	return err
}
