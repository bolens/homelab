package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"mime"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"time"
)

const leaseTTL = 12 * time.Hour

var leasePattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var requestIDPattern = regexp.MustCompile(`^[0-9a-f]{32}$`)

type credential struct {
	Token     string    `json:"token"`
	ExpiresAt time.Time `json:"expires_at"`
}
type leaseRecord struct {
	Request    request   `json:"request"`
	CreatedAt  time.Time `json:"created_at"`
	ExpiresAt  time.Time `json:"expires_at"`
	RequestIDs []string  `json:"request_ids"`
	Purpose    string    `json:"purpose"`
}

func (b *broker) createLease(req request) (string, error) {
	b.replayMu.Lock()
	defer b.replayMu.Unlock()
	entries, err := os.ReadDir(b.cfg.LeaseDir)
	if err != nil {
		return "", err
	}
	remaining := len(entries)
	// Only our bounded, expired lease records are eligible for automatic cleanup.
	for _, e := range entries {
		if e.Type().IsRegular() && len(e.Name()) == 69 && e.Name()[64:] == ".json" && leasePattern.MatchString(e.Name()[:64]) {
			if st, err := e.Info(); err == nil && time.Since(st.ModTime()) > leaseTTL+time.Hour {
				if err = os.Remove(filepath.Join(b.cfg.LeaseDir, e.Name())); err != nil {
					return "", err
				}
				remaining--
			}
		}
	}
	if remaining >= 10000 {
		return "", errDenied
	}
	random := make([]byte, 32)
	if _, err = rand.Read(random); err != nil {
		return "", err
	}
	lease := hex.EncodeToString(random)
	digest := sha256.Sum256([]byte(lease))
	record := leaseRecord{Request: req, CreatedAt: time.Now().UTC(), ExpiresAt: time.Now().UTC().Add(leaseTTL), Purpose: "github"}
	data, err := json.Marshal(record)
	if err != nil {
		return "", err
	}
	path := filepath.Join(b.cfg.LeaseDir, hex.EncodeToString(digest[:])+".json")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return "", err
	}
	_, err = f.Write(data)
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return "", err
	}
	if closeErr != nil {
		return "", closeErr
	}
	if err = syncDir(b.cfg.LeaseDir); err != nil {
		return "", err
	}
	return lease, nil
}
func syncDir(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return f.Sync()
}
func (b *broker) tlsRequest(r *http.Request) bool {
	origin, _ := url.Parse(b.cfg.PublicOrigin)
	if r.TLS != nil {
		return r.Host == origin.Host
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return false
	}
	addr, err := netip.ParseAddr(host)
	if err != nil {
		return false
	}
	trusted := false
	for _, s := range b.cfg.TrustedProxyCIDRs {
		p, err := netip.ParsePrefix(s)
		if err == nil && p.Contains(addr) {
			trusted = true
		}
	}
	return trusted && r.Header.Get("X-Forwarded-Proto") == "https" && r.Header.Get("X-Forwarded-Host") == origin.Host
}
func (b *broker) redeem(w http.ResponseWriter, r *http.Request) {
	if !b.tlsRequest(r) {
		http.Error(w, "request denied", http.StatusForbidden)
		return
	}
	mt, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || mt != "application/json" {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 512)
	var input struct {
		Lease      string `json:"lease"`
		RequestID  string `json:"request_id"`
		Repository string `json:"repository"`
		Commit     string `json:"commit"`
		Purpose    string `json:"purpose"`
	}
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if d.Decode(&input) != nil || !leasePattern.MatchString(input.Lease) || !requestIDPattern.MatchString(input.RequestID) {
		http.Error(w, "request denied", http.StatusForbidden)
		return
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	if !b.allowRedeem() {
		http.Error(w, "rate limit", http.StatusTooManyRequests)
		return
	}
	select {
	case b.active <- struct{}{}:
		defer func() { <-b.active }()
	default:
		http.Error(w, "busy", http.StatusTooManyRequests)
		return
	}
	digest := sha256.Sum256([]byte(input.Lease))
	path := filepath.Join(b.cfg.LeaseDir, hex.EncodeToString(digest[:])+".json")
	// Atomic reservation survives failed/ambiguous network attempts and serializes concurrent replays.
	b.replayMu.Lock()
	raw, err := readPrivateFile(path)
	var record leaseRecord
	if err != nil || json.Unmarshal(raw, &record) != nil || record.Purpose != "github" || time.Now().After(record.ExpiresAt) || time.Now().Before(record.CreatedAt.Add(-3*time.Second)) || record.ExpiresAt.Sub(record.CreatedAt) > leaseTTL+time.Second {
		b.replayMu.Unlock()
		http.Error(w, "request denied", http.StatusForbidden)
		return
	}
	for _, id := range record.RequestIDs {
		if id == input.RequestID {
			b.replayMu.Unlock()
			http.Error(w, "request replayed", http.StatusConflict)
			return
		}
	}
	if len(record.RequestIDs) >= b.cfg.MaxRedemptions {
		b.replayMu.Unlock()
		http.Error(w, "redemption limit", http.StatusTooManyRequests)
		return
	}
	p, policyErr := b.policyFor(record.Request)
	if policyErr != nil || input.Repository != record.Request.Repo.FullName || input.Commit != record.Request.Pipeline.Commit || input.Purpose != "github" {
		b.replayMu.Unlock()
		http.Error(w, "request denied", http.StatusForbidden)
		return
	}
	record.RequestIDs = append(record.RequestIDs, input.RequestID)
	data, err := json.Marshal(record)
	if err == nil {
		err = replacePrivateFile(path, data)
	}
	b.replayMu.Unlock()
	if err != nil {
		http.Error(w, "authorization unavailable", http.StatusServiceUnavailable)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
	defer cancel()
	cred, err := b.issuer.Authorize(ctx, record.Request, p)
	if err != nil || cred.Token == "" {
		http.Error(w, "authorization unavailable", http.StatusServiceUnavailable)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(cred)
}
func replacePrivateFile(path string, data []byte) error {
	f, err := os.CreateTemp(filepath.Dir(path), ".lease-update-")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(0600); err == nil {
		_, err = f.Write(data)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err = os.Rename(f.Name(), path); err != nil {
		return err
	}
	return syncDir(filepath.Dir(path))
}

func (b *broker) allowRedeem() bool {
	b.replayMu.Lock()
	defer b.replayMu.Unlock()
	now := time.Now()
	b.rateTokens += now.Sub(b.rateLast).Seconds() * 2
	if b.rateTokens > 32 {
		b.rateTokens = 32
	}
	b.rateLast = now
	if b.rateTokens < 1 {
		return false
	}
	b.rateTokens--
	return true
}
