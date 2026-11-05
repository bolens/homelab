package main

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"github.com/yaronf/httpsign"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

type fakeIssuer struct {
	mu    sync.Mutex
	calls int
	fail  bool
}

func (f *fakeIssuer) Inspect(context.Context, request, policy) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	if f.fail {
		return errDenied
	}
	return nil
}
func (f *fakeIssuer) Authorize(context.Context, request, policy) (credential, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls++
	if f.fail {
		return credential{}, errDenied
	}
	return credential{Token: "synthetic-test-value", ExpiresAt: time.Now().Add(time.Hour)}, nil
}
func fixture(t *testing.T) (config, request, ed25519.PublicKey, ed25519.PrivateKey) {
	t.Helper()
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	if err = os.Chmod(dir, 0700); err != nil {
		t.Fatal(err)
	}
	leaseDir := t.TempDir()
	if err = os.Chmod(leaseDir, 0700); err != nil {
		t.Fatal(err)
	}
	budgetDir := t.TempDir()
	if err = os.Chmod(budgetDir, 0700); err != nil {
		t.Fatal(err)
	}
	cfg := config{BudgetDir: budgetDir, ForgeID: 2, ReplayDir: dir, LeaseDir: leaseDir, PublicOrigin: "https://ci.example.com"}
	for i, n := range []string{"owner/appicon", "owner/aur-response-toolkit", "owner/uddns", "owner/audio-utils"} {
		cfg.Repositories = append(cfg.Repositories, policy{FullName: n, RemoteID: string(rune('1' + i)), InstallationID: 1, MainPush: true, Tags: n != "owner/audio-utils", Permissions: publisherPermissions(strings.Split(n, "/")[1])})
	}
	var req request
	req.Repo.ID = 10
	req.Repo.ForgeID = 2
	req.Repo.RemoteID = "1"
	req.Repo.FullName = "owner/appicon"
	req.Repo.Owner = "owner"
	req.Repo.Name = "appicon"
	req.Repo.ForgeURL = "https://github.com/owner/appicon"
	req.Pipeline.ID = 30
	req.Pipeline.Number = 2
	req.Pipeline.Event = "push"
	req.Pipeline.Ref = "refs/heads/main"
	req.Pipeline.Branch = "main"
	req.Pipeline.Commit = strings.Repeat("a", 40)
	return cfg, req, pub, priv
}
func signed(t *testing.T, body []byte, key ed25519.PrivateKey, created int64) *http.Request {
	t.Helper()
	r := httptest.NewRequest(http.MethodPost, "http://broker/secrets", bytes.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	sum := sha256.Sum256(body)
	r.Header.Set("Content-Digest", "sha-256=:"+base64.StdEncoding.EncodeToString(sum[:])+":")
	cfg := httpsign.NewSignConfig()
	if created != 0 {
		cfg.SignCreated(false)
	}
	signer, err := httpsign.NewEd25519Signer(key, cfg, httpsign.Headers("@request-target", "content-digest"))
	if err != nil {
		t.Fatal(err)
	}
	si, s, err := httpsign.SignRequest(signatureName, *signer, r)
	if err != nil {
		t.Fatal(err)
	}
	if created != 0 {
		si += fmt.Sprintf(";created=%d", created)
		params := strings.TrimPrefix(si, signatureName+"=")
		canonical := "\"@request-target\": /secrets\n\"content-digest\": " + r.Header.Get("Content-Digest") + "\n\"@signature-params\": " + params
		s = signatureName + "=:" + base64.StdEncoding.EncodeToString(ed25519.Sign(key, []byte(canonical))) + ":"
	}
	r.Header.Set("Signature-Input", si)
	r.Header.Set("Signature", s)
	return r
}
func serve(h http.Handler, r *http.Request) int {
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w.Code
}
func TestSignedBoundary(t *testing.T) {
	cases := []struct {
		name   string
		change func(*request)
	}{
		{"forge", func(r *request) { r.Repo.ForgeID = 1 }},
		{"remote-repo", func(r *request) { r.Repo.RemoteID = "99" }},
		{"repository", func(r *request) { r.Repo.FullName = "other/appicon" }},
		{"forge-destination", func(r *request) { r.Repo.ForgeURL = "https://example.invalid/owner/appicon" }},
		{"repo-slug-mismatch", func(r *request) { r.Repo.Owner = "other" }},
		{"pull-request", func(r *request) { r.Pipeline.Event = "pull_request" }},
		{"manual", func(r *request) { r.Pipeline.Event = "manual" }},
		{"cron", func(r *request) { r.Pipeline.Cron = "publish" }},
		{"feature", func(r *request) { r.Pipeline.Ref = "refs/heads/feature" }},
		{"ref-branch-mismatch", func(r *request) { r.Pipeline.Branch = "feature" }},
		{"fork", func(r *request) { r.Pipeline.FromFork = true }},
		{"invalid-sha", func(r *request) { r.Pipeline.Commit = "not-a-sha" }},
		{"netrc-even-null", func(r *request) { r.Netrc = json.RawMessage(`null`) }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg, r, pub, priv := fixture(t)
			tc.change(&r)
			body, _ := json.Marshal(r)
			i := &fakeIssuer{}
			h, err := newBroker(cfg, pub, i)
			if err != nil {
				t.Fatal(err)
			}
			if got := serve(h, signed(t, body, priv, 0)); got != 403 {
				t.Fatalf("status %d", got)
			}
			if i.calls != 0 {
				t.Fatal("issuer called for denied request")
			}
		})
	}
}
func TestSignatureAndReplay(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := json.Marshal(r)
	original := signed(t, body, priv, 0)
	header := original.Header.Clone()
	if got := serve(h, original); got != 200 {
		t.Fatalf("valid status %d", got)
	}
	replay := httptest.NewRequest(http.MethodPost, "http://broker/secrets", bytes.NewReader(body))
	replay.Header = header
	if got := serve(h, replay); got != 401 {
		t.Fatalf("replay status %d", got)
	}
	// A fresh handler reading the same persistent directory still rejects the replay.
	h, err = newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	replay = httptest.NewRequest(http.MethodPost, "http://broker/secrets", bytes.NewReader(body))
	replay.Header = header
	if got := serve(h, replay); got != 401 {
		t.Fatalf("restart replay status %d", got)
	}
	for _, age := range []int64{time.Now().Add(-time.Minute).Unix(), time.Now().Add(time.Minute).Unix()} {
		if got := serve(h, signed(t, body, priv, age)); got != 401 {
			t.Fatalf("time-bound status %d", got)
		}
	}
	_, other, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	if got := serve(h, signed(t, body, other, 0)); got != 401 {
		t.Fatalf("forged status %d", got)
	}
	tampered := signed(t, body, priv, 0)
	tampered.Body = io.NopCloser(strings.NewReader(`{}`))
	if got := serve(h, tampered); got != 401 {
		t.Fatalf("tampered body status %d", got)
	}
	wrongPath := signed(t, body, priv, 0)
	wrongPath.URL.Path = "/secrets-other"
	if got := serve(h, wrongPath); got != 404 {
		t.Fatalf("destination status %d", got)
	}
	if i.calls != 1 {
		t.Fatalf("unexpected grants %d", i.calls)
	}
}
func TestFiltersAndUnavailableIssuer(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	cfg.GHCRUsername = "synthetic-user"
	cfg.GHCRTokenFile = filepath.Join(t.TempDir(), "token")
	if err := os.WriteFile(cfg.GHCRTokenFile, []byte("synthetic-registry-value"), 0600); err != nil {
		t.Fatal(err)
	}
	cfg.Repositories[3].GHCR = true
	cfg.Repositories[3].GHCREvents = []string{"push"}
	r.Repo.Name = "audio-utils"
	r.Repo.FullName = "owner/audio-utils"
	r.Repo.ForgeURL = "https://github.com/owner/audio-utils"
	r.Repo.RemoteID = "4"
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := json.Marshal(r)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, signed(t, body, priv, 0))
	if w.Code != 200 {
		t.Fatalf("status%d", w.Code)
	}
	var out struct {
		Secrets []secret `json:"secrets"`
	}
	if err = json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if len(out.Secrets) != 3 {
		t.Fatal("missing scoped secrets")
	}
	for _, s := range out.Secrets {
		if len(s.Events) != 1 || s.Events[0] != "push" {
			t.Fatal("wrong events")
		}
		if s.Name == "github_publish_lease" {
			if len(s.Images) != 0 {
				t.Fatal("commands token cannot have plugin filter")
			}
		} else if len(s.Images) != 1 || s.Images[0] != kanikoImage {
			t.Fatal("registry plugin filter")
		}
	}
	cfg, r, pub, priv = fixture(t)
	i = &fakeIssuer{fail: true}
	h, err = newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	body, _ = json.Marshal(r)
	w = httptest.NewRecorder()
	h.ServeHTTP(w, signed(t, body, priv, 0))
	if w.Code != 503 || strings.Contains(w.Body.String(), "synthetic") {
		t.Fatal("issuer failure did not fail closed")
	}
}
func TestRequestShapeLimits(t *testing.T) {
	cfg, _, pub, priv := fixture(t)
	h, err := newBroker(cfg, pub, &fakeIssuer{})
	if err != nil {
		t.Fatal(err)
	}
	for _, body := range [][]byte{[]byte(`{} {}`), []byte(`not json`), bytes.Repeat([]byte("x"), maxBody+1)} {
		if got := serve(h, signed(t, body, priv, 0)); got == 200 {
			t.Fatal("invalid request accepted")
		}
	}
	req := httptest.NewRequest(http.MethodPost, "http://broker/secrets", strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	if got := serve(h, req); got != 401 {
		t.Fatal("unsigned accepted")
	}
}

func TestExplicitCreationTime(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	h, err := newBroker(cfg, pub, &fakeIssuer{})
	if err != nil {
		t.Fatal(err)
	}
	body, _ := json.Marshal(r)
	if got := serve(h, signed(t, body, priv, time.Now().Unix())); got != 200 {
		t.Fatalf("explicit current signature status%d", got)
	}
}

func TestSignatureRepresentationCannotReopenReplay(t *testing.T) {
	cfg, r, pub, priv := fixture(t)
	i := &fakeIssuer{}
	h, err := newBroker(cfg, pub, i)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := json.Marshal(r)
	original := signed(t, body, priv, 0)
	header := original.Header.Clone()
	if got := serve(h, original); got != 200 {
		t.Fatal("valid request rejected")
	}
	for _, suffix := range []string{" ", ", extra=:AQ==:"} {
		replay := httptest.NewRequest(http.MethodPost, "http://broker/secrets", bytes.NewReader(body))
		replay.Header = header.Clone()
		replay.Header.Set("Signature", header.Get("Signature")+suffix)
		if got := serve(h, replay); got != 401 {
			t.Fatalf("signature representation replay status%d", got)
		}
	}
	if i.calls != 1 {
		t.Fatal("signature representation minted again")
	}
}

func TestPublicationPermissionBounds(t *testing.T) {
	cfg, _, pub, _ := fixture(t)
	cfg.Repositories[0].Permissions = map[string]string{"contents": "write", "pull_requests": "write", "actions": "write", "actions_variables": "read", "checks": "read", "statuses": "read"}
	cfg.Repositories[1].Permissions = map[string]string{"contents": "write", "pull_requests": "write", "actions": "read", "actions_variables": "read", "checks": "read", "statuses": "read"}
	cfg.Repositories[2].Permissions = map[string]string{"contents": "write", "actions": "write", "actions_variables": "read", "checks": "read", "statuses": "read"}
	cfg.Repositories[3].Permissions = map[string]string{"contents": "read", "actions_variables": "read"}
	if _, err := newBroker(cfg, pub, &fakeIssuer{}); err != nil {
		t.Fatal("approved per-repository maps rejected")
	}
	cases := []struct {
		repo       int
		key, value string
	}{{0, "variables", "read"}, {0, "administration", "write"}, {0, "checks", "write"}, {0, "statuses", "write"}, {0, "actions_variables", "write"}, {0, "issues", "write"}, {1, "actions", "write"}, {2, "pull_requests", "write"}, {3, "contents", "write"}, {3, "actions", "read"}}
	for _, tc := range cases {
		t.Run(fmt.Sprintf("%d-%s", tc.repo, tc.key), func(t *testing.T) {
			cfg, _, pub, _ := fixture(t)
			cfg.Repositories[tc.repo].Permissions[tc.key] = tc.value
			if _, err := newBroker(cfg, pub, &fakeIssuer{}); err == nil {
				t.Fatal("excess privilege accepted")
			}
		})
	}
	cfg, _, pub, _ = fixture(t)
	cfg.Repositories[0].GHCR = true
	cfg.Repositories[0].GHCREvents = []string{"push"}
	if _, err := newBroker(cfg, pub, &fakeIssuer{}); err == nil {
		t.Fatal("registry authority extended to Appicon")
	}
}
