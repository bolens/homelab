package main

import (
	"bytes"
	"crypto/ed25519"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func compileLease(t *testing.T, h http.Handler, req request, priv ed25519.PrivateKey) string {
	t.Helper()
	body, _ := json.Marshal(req)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, signed(t, body, priv, 0))
	if w.Code != 200 {
		t.Fatalf("compile status%d", w.Code)
	}
	var out struct {
		Secrets []secret `json:"secrets"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	for _, s := range out.Secrets {
		if s.Name == "github_publish_lease" {
			if !leasePattern.MatchString(s.Value) {
				t.Fatal("weak lease")
			}
			return s.Value
		}
	}
	t.Fatal("missing lease")
	return ""
}
func redemption(lease string, req request, id int) *http.Request {
	data, _ := json.Marshal(map[string]string{"lease": lease, "repository": req.Repo.FullName, "commit": req.Pipeline.Commit, "purpose": "github", "request_id": fmt.Sprintf("%032x", id)})
	r := httptest.NewRequest(http.MethodPost, "https://ci.example.com/redeem", bytes.NewReader(data))
	r.Header.Set("Content-Type", "application/json")
	r.TLS = &tls.ConnectionState{}
	return r
}
func TestJustInTimeBoundedRedemption(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	lease := compileLease(t, h, r, priv)
	if i.calls != 1 {
		t.Fatal("compile must inspect, not return app token")
	}
	entries, err := os.ReadDir(cfg.LeaseDir)
	if err != nil || len(entries) != 1 {
		t.Fatal("lease state missing")
	}
	raw, err := os.ReadFile(filepath.Join(cfg.LeaseDir, entries[0].Name()))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(raw, []byte(lease)) || bytes.Contains(raw, []byte("synthetic-test-value")) {
		t.Fatal("raw capability/credential persisted")
	}
	var record leaseRecord
	if json.Unmarshal(raw, &record) != nil || record.Purpose != "github" || record.ExpiresAt.Sub(record.CreatedAt) > leaseTTL+time.Second {
		t.Fatal("lease lifetime/binding")
	}
	for n := 1; n <= 8; n++ {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, redemption(lease, r, n))
		if w.Code != 200 {
			t.Fatalf("redemption%d status%d", n, w.Code)
		}
		var c credential
		if json.Unmarshal(w.Body.Bytes(), &c) != nil || c.Token == "" || c.ExpiresAt.Before(time.Now()) {
			t.Fatal("credential response")
		}
		if w.Header().Get("Cache-Control") != "no-store" {
			t.Fatal("credential cache header")
		}
	}
	if got := serve(h, redemption(lease, r, 1)); got != 409 {
		t.Fatalf("replay status%d", got)
	}
	if got := serve(h, redemption(lease, r, 9)); got != 429 {
		t.Fatalf("limit status%d", got)
	}
	if i.calls != 9 {
		t.Fatalf("wrong grant count%d", i.calls)
	}
	// Redemption count and replay IDs survive broker restarts.
	h, err = newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	if got := serve(h, redemption(lease, r, 10)); got != 429 {
		t.Fatal("restart reopened limit")
	}
}
func TestRedemptionBindingAndTLS(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	lease := compileLease(t, h, r, priv)
	for _, field := range []string{"repository", "commit", "purpose", "lease"} {
		v := map[string]string{"lease": lease, "repository": r.Repo.FullName, "commit": r.Pipeline.Commit, "purpose": "github", "request_id": strings.Repeat("a", 32)}
		v[field] = "wrong"
		body, _ := json.Marshal(v)
		post := httptest.NewRequest(http.MethodPost, "https://ci.example.com/redeem", bytes.NewReader(body))
		post.Header.Set("Content-Type", "application/json")
		if got := serve(h, post); got != 403 {
			t.Fatalf("%s status%d", field, got)
		}
	}
	post := redemption(lease, r, 1)
	post.TLS = nil
	if got := serve(h, post); got != 403 {
		t.Fatal("plaintext accepted")
	}
	post = redemption(lease, r, 1)
	post.Host = "other.example.com"
	if got := serve(h, post); got != 403 {
		t.Fatal("wrong TLS destination accepted")
	}
	post = redemption(lease, r, 1)
	post.TLS = nil
	post.Header.Set("X-Forwarded-Proto", "https")
	post.Header.Set("X-Forwarded-Host", "ci.example.com")
	if got := serve(h, post); got != 403 {
		t.Fatal("untrusted forwarded TLS accepted")
	}
	if i.calls != 1 {
		t.Fatal("invalid redemption reached issuer")
	}
}
func TestExpiredLeaseAndPolicyChange(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	lease := compileLease(t, h, r, priv)
	// Removing authorization in current config must invalidate an already compiled lease.
	cfg.Repositories[0].MainPush = false
	cfg.Repositories[0].Tags = true
	h, err = newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	if got := serve(h, redemption(lease, r, 1)); got != 403 {
		t.Fatal("changed policy bypassed")
	}
	cfg.Repositories[0].MainPush = true
	h, err = newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	entries, _ := os.ReadDir(cfg.LeaseDir)
	path := filepath.Join(cfg.LeaseDir, entries[0].Name())
	raw, _ := os.ReadFile(path)
	var record leaseRecord
	_ = json.Unmarshal(raw, &record)
	record.CreatedAt = time.Now().Add(-13 * time.Hour)
	record.ExpiresAt = time.Now().Add(-time.Hour)
	data, _ := json.Marshal(record)
	if err = os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	if got := serve(h, redemption(lease, r, 1)); got != 403 {
		t.Fatal("expired lease accepted")
	}
}
func TestRevokedIssuerAndRequestLimit(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	lease := compileLease(t, h, r, priv)
	i.fail = true
	w := httptest.NewRecorder()
	h.ServeHTTP(w, redemption(lease, r, 1))
	if w.Code != 503 || strings.Contains(w.Body.String(), "synthetic") {
		t.Fatal("issuer revocation leaked/accepted")
	}
	if got := serve(h, redemption(lease, r, 1)); got != 409 {
		t.Fatal("failed attempt request replay accepted")
	}
	post := redemption(lease, r, 2)
	post.Body = http.NoBody
	if got := serve(h, post); got == 200 {
		t.Fatal("empty body accepted")
	}
}

func TestTrustedProxyAndQueuedLease(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	// Synthetic RFC1918 fixture; no live network or machine address is consulted.
	cfg.TrustedProxyCIDRs = []string{"172.31.255.0/24"}
	g, f := mockAPI(t, "", false)
	h, err := newBroker(cfg, pub, g)
	if err != nil {
		t.Fatal(err)
	}
	lease := compileLease(t, h, r, priv)
	entries, _ := os.ReadDir(cfg.LeaseDir)
	path := filepath.Join(cfg.LeaseDir, entries[0].Name())
	raw, _ := os.ReadFile(path)
	var record leaseRecord
	_ = json.Unmarshal(raw, &record)
	record.CreatedAt = time.Now().Add(-2 * time.Hour)
	record.ExpiresAt = record.CreatedAt.Add(leaseTTL)
	data, _ := json.Marshal(record)
	if err = os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	post := redemption(lease, r, 1)
	post.TLS = nil
	post.RemoteAddr = "172.31.255.3:1234"
	post.Header.Set("X-Forwarded-Proto", "https")
	post.Header.Set("X-Forwarded-Host", "ci.example.com")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, post)
	if w.Code != 200 {
		t.Fatalf("trusted proxy status%d", w.Code)
	}
	var cred credential
	if json.Unmarshal(w.Body.Bytes(), &cred) != nil || time.Until(cred.ExpiresAt) < 50*time.Minute {
		t.Fatal("queued lease did not mint fresh credential")
	}
	if f.mints.Load() != 2 || f.revokes.Load() != 1 {
		t.Fatal("compile inspection credential was reused instead of freshly minted")
	}
	for _, field := range []string{"X-Forwarded-Proto", "X-Forwarded-Host"} {
		post = redemption(lease, r, 2)
		post.TLS = nil
		post.RemoteAddr = "172.31.255.3:1234"
		post.Header.Set("X-Forwarded-Proto", "https")
		post.Header.Set("X-Forwarded-Host", "ci.example.com")
		post.Header.Set(field, "wrong")
		if got := serve(h, post); got != 403 {
			t.Fatal("invalid trusted-proxy claim accepted")
		}
	}
}
