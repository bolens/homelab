package main

import (
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"
	"sync"
	"time"

	"github.com/dunglas/httpsfv"
	"github.com/yaronf/httpsign"
)

const signatureName = "woodpecker-ci-extensions"
const kanikoImage = "woodpeckerci/plugin-kaniko:2.3.4@sha256:497071c44ffd0c24d6e3e3e49993c33a6544eb30a5e3f887c031d2b643238432"
const maxBody = 2 << 20

var shaPattern = regexp.MustCompile(`^[0-9a-f]{40}$`)
var tagPattern = regexp.MustCompile(`^refs/tags/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*)?(\+[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*)?$`)
var repoPattern = regexp.MustCompile(`^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`)
var errDenied = errors.New("request denied")

type policy struct {
	FullName       string            `json:"full_name"`
	RemoteID       string            `json:"remote_id"`
	InstallationID int64             `json:"installation_id"`
	MainPush       bool              `json:"main_push"`
	Tags           bool              `json:"tags"`
	GHCR           bool              `json:"ghcr"`
	Permissions    map[string]string `json:"permissions"`
	GHCREvents     []string          `json:"ghcr_events"`
}
type config struct {
	ForgeID           int64    `json:"github_forge_id"`
	AppID             string   `json:"github_app_id"`
	PublicKeyFile     string   `json:"woodpecker_public_key_file"`
	PrivateKeyFile    string   `json:"github_app_key_file"`
	GHCRTokenFile     string   `json:"ghcr_token_file"`
	GHCRUsername      string   `json:"ghcr_username"`
	ReplayDir         string   `json:"replay_directory"`
	LeaseDir          string   `json:"lease_directory"`
	PublicOrigin      string   `json:"public_origin"`
	TrustedProxyCIDRs []string `json:"trusted_proxy_cidrs"`
	MaxRedemptions    int      `json:"max_redemptions"`
	Repositories      []policy `json:"repositories"`
}
type request struct {
	Repo struct {
		ID       int64  `json:"id"`
		ForgeID  int64  `json:"forge_id"`
		RemoteID string `json:"forge_remote_id"`
		FullName string `json:"full_name"`
		Owner    string `json:"owner"`
		Name     string `json:"name"`
		ForgeURL string `json:"forge_url"`
	} `json:"repo"`
	Pipeline struct {
		ID       int64  `json:"id"`
		Number   int64  `json:"number"`
		Event    string `json:"event"`
		Ref      string `json:"ref"`
		Branch   string `json:"branch"`
		Commit   string `json:"commit"`
		Cron     string `json:"cron"`
		FromFork bool   `json:"from_fork"`
	} `json:"pipeline"`
	Netrc json.RawMessage `json:"netrc,omitempty"`
}
type secret struct {
	Name   string   `json:"name"`
	Value  string   `json:"value"`
	Events []string `json:"events"`
	Images []string `json:"images,omitempty"`
}
type issuer interface {
	Inspect(context.Context, request, policy) error
	Authorize(context.Context, request, policy) (credential, error)
}
type broker struct {
	cfg        config
	policies   map[string]policy
	issuer     issuer
	replayMu   sync.Mutex
	rateLast   time.Time
	rateTokens float64
	active     chan struct{}
}

func newBroker(cfg config, key ed25519.PublicKey, issuer issuer) (http.Handler, error) {
	if cfg.MaxRedemptions == 0 {
		cfg.MaxRedemptions = 8
	}
	if cfg.MaxRedemptions < 1 || cfg.MaxRedemptions > 8 {
		return nil, errDenied
	}
	if cfg.ForgeID <= 0 || len(key) != ed25519.PublicKeySize || issuer == nil || !filepath.IsAbs(cfg.ReplayDir) || len(cfg.Repositories) != 4 || !filepath.IsAbs(cfg.LeaseDir) || filepath.Clean(cfg.LeaseDir) == filepath.Clean(cfg.ReplayDir) {
		return nil, errDenied
	}
	origin, err := url.Parse(cfg.PublicOrigin)
	if err != nil || origin.Scheme != "https" || origin.Host == "" || origin.User != nil || origin.Path != "" || origin.RawQuery != "" || origin.Fragment != "" {
		return nil, errDenied
	}
	for _, s := range cfg.TrustedProxyCIDRs {
		n, e := netip.ParsePrefix(s)
		if e != nil || !n.Addr().IsPrivate() || (n.Addr().Is4() && n.Bits() < 24) || (n.Addr().Is6() && n.Bits() < 120) {
			return nil, errDenied
		}
	}
	b := &broker{cfg: cfg, policies: map[string]policy{}, issuer: issuer, rateLast: time.Now(), rateTokens: 32, active: make(chan struct{}, 8)}
	for _, p := range cfg.Repositories {
		if !repoPattern.MatchString(p.FullName) || !regexp.MustCompile(`^[1-9][0-9]*$`).MatchString(p.RemoteID) || p.InstallationID <= 0 || (!p.MainPush && !p.Tags) {
			return nil, errDenied
		}
		name := strings.Split(p.FullName, "/")[1]
		if name != "appicon" && name != "aur-response-toolkit" && name != "uddns" && name != "audio-utils" {
			return nil, errDenied
		}
		if name == "audio-utils" && p.Tags {
			return nil, errDenied
		}
		if p.GHCR {
			if name != "audio-utils" && name != "uddns" {
				return nil, errDenied
			}
			expected := "tag"
			if name == "audio-utils" {
				expected = "push"
			}
			if len(p.GHCREvents) != 1 || p.GHCREvents[0] != expected {
				return nil, errDenied
			}
		}
		for _, old := range b.policies {
			if old.RemoteID == p.RemoteID {
				return nil, errDenied
			}
		}
		if len(p.Permissions) == 0 || p.Permissions["variables"] != "read" {
			return nil, errDenied
		}
		allowed := publisherPermissions(name)
		if p.Permissions["contents"] == "" {
			return nil, errDenied
		}
		for k, v := range p.Permissions {
			max, ok := allowed[k]
			if !ok || (v != "read" && v != "write") || (max == "read" && v != "read") {
				return nil, errDenied
			}
		}
		for _, ev := range p.GHCREvents {
			if ev != "push" && ev != "tag" {
				return nil, errDenied
			}
		}
		if _, ok := b.policies[p.FullName]; ok {
			return nil, errDenied
		}
		b.policies[p.FullName] = p
	}
	if st, err := os.Lstat(cfg.ReplayDir); err != nil || !st.IsDir() || st.Mode().Perm()&0077 != 0 {
		return nil, errDenied
	}
	if st, err := os.Lstat(cfg.LeaseDir); err != nil || !st.IsDir() || st.Mode().Perm()&0077 != 0 {
		return nil, errDenied
	}
	verifier, err := httpsign.NewEd25519Verifier(key, httpsign.NewVerifyConfig().SetAllowedAlgs([]string{"ed25519"}).SetNotOlderThan(30*time.Second).SetNotNewerThan(3*time.Second), httpsign.Headers("@request-target", "content-digest"))
	if err != nil {
		return nil, err
	}
	signed := httpsign.WrapHandler(http.HandlerFunc(b.secrets), *httpsign.NewHandlerConfig().SetFetchVerifier(func(*http.Request) (string, *httpsign.Verifier) { return signatureName, verifier }).SetLogger(nil).SetMaxBodySize(maxBody))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		if r.URL.Path == "/healthz" && r.Method == http.MethodGet {
			w.WriteHeader(http.StatusOK)
			return
		}
		if r.URL.Path == "/redeem" && r.Method == http.MethodPost && r.URL.RawQuery == "" {
			b.redeem(w, r)
			return
		}
		if r.Method != http.MethodPost || r.URL.Path != "/secrets" || r.URL.RawQuery != "" {
			http.NotFound(w, r)
			return
		}
		mt, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
		if err != nil || mt != "application/json" || len(r.Header.Values("Signature")) != 1 || len(r.Header.Values("Signature-Input")) != 1 || len(r.Header.Values("Content-Digest")) != 1 {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, maxBody)
		signed.ServeHTTP(w, r)
	}), nil
}
func (b *broker) consumeSignature(r *http.Request) error {
	// Persist authenticated fingerprints so restarting cannot reopen the replay window.
	dict, err := httpsfv.UnmarshalDictionary(r.Header.Values("Signature"))
	if err != nil || len(dict.Names()) != 1 || dict.Names()[0] != signatureName {
		return errDenied
	}
	member, ok := dict.Get(signatureName)
	if !ok {
		return errDenied
	}
	item, ok := member.(httpsfv.Item)
	if !ok {
		return errDenied
	}
	raw, ok := item.Value.([]byte)
	if !ok || len(raw) != ed25519.SignatureSize {
		return errDenied
	}
	input, err := httpsfv.UnmarshalDictionary(r.Header.Values("Signature-Input"))
	if err != nil || len(input.Names()) != 1 || input.Names()[0] != signatureName {
		return errDenied
	}
	sum := sha256.Sum256(raw)
	b.replayMu.Lock()
	defer b.replayMu.Unlock()
	entries, err := os.ReadDir(b.cfg.ReplayDir)
	if err != nil {
		return err
	}
	remaining := len(entries)
	for _, e := range entries {
		if e.Type().IsRegular() && len(e.Name()) == 69 && strings.HasSuffix(e.Name(), ".seen") && leasePattern.MatchString(e.Name()[:64]) {
			if st, err := e.Info(); err == nil && time.Since(st.ModTime()) > 2*time.Minute {
				if err = os.Remove(filepath.Join(b.cfg.ReplayDir, e.Name())); err != nil {
					return err
				}
				remaining--
			}
		}
	}
	if remaining >= 10000 {
		return errDenied
	}
	f, err := os.OpenFile(filepath.Join(b.cfg.ReplayDir, hex.EncodeToString(sum[:])+".seen"), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return syncDir(b.cfg.ReplayDir)
}
func (b *broker) secrets(w http.ResponseWriter, r *http.Request) {
	if b.consumeSignature(r) != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	var req request
	d := json.NewDecoder(r.Body)
	if d.Decode(&req) != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	p, err := b.policyFor(req)
	if err != nil {
		http.Error(w, "request denied", http.StatusForbidden)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
	defer cancel()
	err = b.issuer.Inspect(ctx, req, p)
	if err != nil {
		http.Error(w, "authorization unavailable", http.StatusServiceUnavailable)
		return
	}
	lease, err := b.createLease(req)
	if err != nil {
		http.Error(w, "authorization unavailable", http.StatusServiceUnavailable)
		return
	}
	out := []secret{{Name: "github_publish_lease", Value: lease, Events: []string{req.Pipeline.Event}}}
	if p.GHCR && slices.Contains(p.GHCREvents, req.Pipeline.Event) {
		value, err := readPrivateFile(b.cfg.GHCRTokenFile)
		if err != nil || b.cfg.GHCRUsername == "" {
			http.Error(w, "authorization unavailable", http.StatusServiceUnavailable)
			return
		}
		out = append(out, secret{Name: "ghcr_username", Value: b.cfg.GHCRUsername, Events: []string{req.Pipeline.Event}, Images: []string{kanikoImage}}, secret{Name: "ghcr_password", Value: string(value), Events: []string{req.Pipeline.Event}, Images: []string{kanikoImage}})
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(struct {
		Secrets []secret `json:"secrets"`
	}{out})
}
func readPrivateFile(path string) ([]byte, error) {
	st, err := os.Lstat(path)
	if err != nil || !st.Mode().IsRegular() || st.Mode().Perm()&0077 != 0 || st.Size() > 65536 {
		return nil, errDenied
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	b = []byte(strings.TrimSpace(string(b)))
	if len(b) == 0 {
		return nil, errDenied
	}
	return b, nil
}

func (b *broker) policyFor(req request) (policy, error) {
	p, ok := b.policies[req.Repo.FullName]
	if !ok || req.Repo.ForgeID != b.cfg.ForgeID || req.Repo.RemoteID != p.RemoteID || req.Repo.FullName != req.Repo.Owner+"/"+req.Repo.Name || req.Repo.ForgeURL != "https://github.com/"+p.FullName || req.Repo.ID <= 0 || req.Pipeline.ID <= 0 || req.Pipeline.Number <= 0 || !shaPattern.MatchString(req.Pipeline.Commit) || req.Pipeline.FromFork || req.Pipeline.Cron != "" || len(req.Netrc) != 0 {
		return policy{}, errDenied
	}
	switch req.Pipeline.Event {
	case "push":
		if !p.MainPush || req.Pipeline.Ref != "refs/heads/main" || req.Pipeline.Branch != "main" {
			return policy{}, errDenied
		}
	case "tag":
		if !p.Tags || !tagPattern.MatchString(req.Pipeline.Ref) {
			return policy{}, errDenied
		}
	default:
		return policy{}, errDenied
	}

	return p, nil
}

func publisherPermissions(name string) map[string]string {
	switch name {
	case "appicon":
		return map[string]string{"contents": "write", "pull_requests": "write", "actions": "write", "variables": "read", "checks": "read", "statuses": "read"}
	case "aur-response-toolkit":
		return map[string]string{"contents": "write", "pull_requests": "write", "actions": "read", "variables": "read", "checks": "read", "statuses": "read"}
	case "uddns":
		return map[string]string{"contents": "write", "actions": "write", "variables": "read", "checks": "read", "statuses": "read"}
	case "audio-utils":
		return map[string]string{"contents": "read", "variables": "read"}
	default:
		return nil
	}
}
