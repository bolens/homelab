package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type apiFixture struct {
	bad      string
	tag      bool
	key      *rsa.PrivateKey
	refReads atomic.Int32
	mints    atomic.Int32
	revokes  atomic.Int32
	t        *testing.T
}

var testKeyOnce sync.Once
var testRSA *rsa.PrivateKey

func mockAPI(t *testing.T, bad string, tag bool) (*githubIssuer, *apiFixture) {
	t.Helper()
	testKeyOnce.Do(func() {
		var err error
		testRSA, err = rsa.GenerateKey(rand.Reader, 2048)
		if err != nil {
			panic(err)
		}
	})
	f := &apiFixture{bad: bad, tag: tag, key: testRSA, t: t}
	s := httptest.NewServer(http.HandlerFunc(f.serve))
	t.Cleanup(s.Close)
	return &githubIssuer{baseURL: s.URL, appID: "123", key: testRSA, client: &http.Client{Timeout: time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errDenied }}}, f
}
func (f *apiFixture) serve(w http.ResponseWriter, r *http.Request) {
	send := func(v any) {
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(v); err != nil {
			f.t.Error(err)
		}
	}
	if r.URL.Path == "/app/installations/1/access_tokens" {
		f.mints.Add(1)
		parts := strings.Split(strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "), ".")
		if len(parts) != 3 {
			http.Error(w, "jwt", 401)
			return
		}
		sig, e := base64.RawURLEncoding.DecodeString(parts[2])
		sum := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
		if e != nil || rsa.VerifyPKCS1v15(&f.key.PublicKey, crypto.SHA256, sum[:], sig) != nil {
			http.Error(w, "jwt", 401)
			return
		}
		raw, _ := base64.RawURLEncoding.DecodeString(parts[1])
		var claims map[string]any
		_ = json.Unmarshal(raw, &claims)
		if claims["iss"] != "123" || int64(claims["exp"].(float64)) > time.Now().Add(6*time.Minute).Unix() {
			http.Error(w, "jwt", 401)
			return
		}
		var in struct {
			IDs         []int64           `json:"repository_ids"`
			Permissions map[string]string `json:"permissions"`
		}
		if json.NewDecoder(r.Body).Decode(&in) != nil || len(in.IDs) != 1 || in.IDs[0] != 1 {
			http.Error(w, "scope", 400)
			return
		}
		if _, legacy := in.Permissions["variables"]; legacy {
			http.Error(w, "unsupported permission", 422)
			return
		}
		permissions := in.Permissions
		if f.bad == "broad-permissions" {
			permissions["administration"] = "write"
		}
		repositories := []map[string]int64{{"id": 1}}
		if f.bad == "broad-repositories" {
			repositories = append(repositories, map[string]int64{"id": 99})
		}
		expires := time.Now().Add(time.Hour)
		if f.bad == "expired-token" {
			expires = time.Now().Add(-time.Minute)
		}
		if f.bad == "long-token" {
			expires = time.Now().Add(2 * time.Hour)
		}
		response := map[string]any{"token": "synthetic-installation-value", "expires_at": expires, "repositories": repositories, "permissions": permissions}
		if strings.HasPrefix(f.bad, "missing-repositories") {
			delete(response, "repositories")
		}
		if f.bad == "null-repositories" {
			response["repositories"] = nil
		}
		send(response)
		return
	}
	if r.Header.Get("Authorization") != "Bearer synthetic-installation-value" {
		http.Error(w, "authentication", 401)
		return
	}
	if r.URL.Path == "/installation/token" && r.Method == http.MethodDelete {
		f.revokes.Add(1)
		w.WriteHeader(204)
		return
	}
	if r.URL.Path == "/installation/repositories" {
		if r.Method != http.MethodGet || r.URL.RawQuery != "per_page=2" || !strings.HasPrefix(f.bad, "missing-repositories") {
			f.t.Error("unexpected scope probe")
			http.Error(w, "scope", 400)
			return
		}
		id, name, total := 1, "owner/appicon", 1
		switch f.bad {
		case "missing-repositories-wrong-id":
			id = 99
		case "missing-repositories-wrong-name":
			name = "owner/other"
		case "missing-repositories-broad":
			total = 2
		case "missing-repositories-empty":
			send(map[string]any{"total_count": 1, "repositories": []any{}})
			return
		case "missing-repositories-extra":
			send(map[string]any{"total_count": 1, "repositories": []map[string]any{{"id": 1, "full_name": name}, {"id": 99, "full_name": "owner/other"}}})
			return
		case "missing-repositories-unavailable":
			http.Error(w, "private scope failure", 503)
			return
		}
		send(map[string]any{"total_count": total, "repositories": []map[string]any{{"id": id, "full_name": name}}})
		return
	}
	if f.bad == "unavailable" {
		http.Error(w, "private diagnostic must never escape", 503)
		return
	}
	if f.bad == "redirect" {
		http.Redirect(w, r, "https://example.invalid/private", http.StatusFound)
		return
	}
	base := "/repos/owner/appicon"
	if r.URL.Path == base {
		switch f.bad {
		case "repo-not-found":
			http.Error(w, "unavailable repository", 404)
			return
		case "missing-flag-and-outage":
			http.Error(w, "unavailable metadata", 503)
			return
		case "missing-flag-malformed-repo":
			send(map[string]any{})
			return
		case "oversized-metadata":
			_, _ = w.Write([]byte(strings.Repeat("x", maxBody+1)))
			return
		case "malformed-metadata":
			_, _ = w.Write([]byte(`{"id":"wrong type"}`))
			return
		}
	}
	switch r.URL.Path {
	case base:
		id := 1
		if f.bad == "remote-id" {
			id = 99
		}
		name := "owner/appicon"
		if f.bad == "full-name" {
			name = "other/appicon"
		}
		branch := "main"
		if f.bad == "default-branch" {
			branch = "other"
		}
		send(map[string]any{"id": id, "full_name": name, "default_branch": branch, "archived": f.bad == "archived", "disabled": f.bad == "disabled"})
	case base + "/actions/variables/WOODPECKER_PUBLISHING":
		if strings.HasPrefix(f.bad, "missing-flag") {
			http.Error(w, "missing", 404)
			return
		}
		if f.bad == "flag-forbidden" {
			http.Error(w, "forbidden", 403)
			return
		}
		value := "true"
		if f.bad == "disabled-publishing" {
			value = "false"
		}
		send(map[string]string{"name": "WOODPECKER_PUBLISHING", "value": value})
	case base + "/branches/main":
		commit := strings.Repeat("a", 40)
		if f.bad == "source-sha" {
			commit = strings.Repeat("d", 40)
		}
		send(map[string]any{"name": "main", "protected": f.bad != "unprotected", "commit": map[string]string{"sha": commit}})
	case base + "/git/ref/tags/v1.2.3":
		n := f.refReads.Add(1)
		kind := "tag"
		sha := strings.Repeat("c", 40)
		if f.bad == "lightweight-tag" {
			kind = "commit"
			sha = strings.Repeat("b", 40)
		}
		if f.bad == "retargeted-tag" && n > 1 {
			sha = strings.Repeat("d", 40)
		}
		send(map[string]any{"ref": "refs/tags/v1.2.3", "object": map[string]string{"sha": sha, "type": kind}})
	case base + "/git/tags/" + strings.Repeat("c", 40):
		commit := strings.Repeat("b", 40)
		if f.bad == "tag-source" {
			commit = strings.Repeat("d", 40)
		}
		send(map[string]any{"tag": "v1.2.3", "sha": strings.Repeat("c", 40), "object": map[string]string{"sha": commit, "type": "commit"}, "verification": map[string]bool{"verified": f.bad != "unsigned-tag"}})
	case base + "/compare/" + strings.Repeat("b", 40) + "..." + strings.Repeat("a", 40):
		sha := strings.Repeat("b", 40)
		if f.bad == "unreachable-tag" {
			sha = strings.Repeat("d", 40)
		}
		send(map[string]any{"merge_base_commit": map[string]string{"sha": sha}})
	default:
		http.Error(w, fmt.Sprintf("unexpected fixture route %s", r.URL.Path), 404)
	}
}

func TestGitHubPolicyDenialHTTPBoundary(t *testing.T) {
	for _, tc := range []struct {
		bad    string
		status int
	}{
		{"disabled-publishing", 204}, {"missing-flag", 204}, {"unprotected", 204},
		{"remote-id", 204}, {"full-name", 204}, {"default-branch", 204},
		{"archived", 204}, {"disabled", 204}, {"source-sha", 204},
		{"repo-not-found", 503}, {"flag-forbidden", 503}, {"unavailable", 503},
		{"missing-flag-and-outage", 503}, {"missing-flag-malformed-repo", 503},
		{"oversized-metadata", 503}, {"malformed-metadata", 503},
		{"broad-permissions", 503}, {"broad-repositories", 503},
	} {
		t.Run(tc.bad, func(t *testing.T) {
			issuer, f := mockAPI(t, tc.bad, false)
			cfg, req, pub, priv := fixture(t)
			handler, err := newBroker(cfg, pub, issuer)
			if err != nil {
				t.Fatal(err)
			}
			body, _ := json.Marshal(req)
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, signed(t, body, priv, 0))
			if w.Code != tc.status || (tc.status == 204 && w.Body.Len() != 0) {
				t.Fatalf("status %d, expected %d", w.Code, tc.status)
			}
			if f.revokes.Load() != 1 {
				t.Fatal("unused inspection token was not revoked")
			}
			for _, dir := range []string{cfg.LeaseDir, cfg.BudgetDir} {
				entries, err := os.ReadDir(dir)
				if err != nil || len(entries) != 0 {
					t.Fatal("denied/unavailable metadata created publication state")
				}
			}
		})
	}
}
func TestGitHubImmutableMetadata(t *testing.T) {
	for _, bad := range []string{"", "missing-repositories", "missing-repositories-wrong-id", "missing-repositories-wrong-name", "missing-repositories-broad", "missing-repositories-empty", "missing-repositories-extra", "missing-repositories-unavailable", "null-repositories", "remote-id", "full-name", "default-branch", "archived", "disabled", "disabled-publishing", "unprotected", "source-sha", "broad-permissions", "broad-repositories", "expired-token", "long-token", "unavailable", "redirect"} {
		t.Run(bad, func(t *testing.T) {
			g, f := mockAPI(t, bad, false)
			cfg, r, _, _ := fixture(t)
			p := cfg.Repositories[0]
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			cred, err := g.Authorize(ctx, r, p)
			if bad == "" || bad == "missing-repositories" {
				if err != nil || cred.Token == "" {
					t.Fatalf("valid metadata rejected:%v", err)
				}
				if f.revokes.Load() != 0 {
					t.Fatal("returned token revoked")
				}
			} else {
				if err == nil || cred.Token != "" {
					t.Fatal("invalid metadata granted")
				}
				if f.revokes.Load() != 1 {
					t.Fatal("unused token not revoked")
				}
			}
		})
	}
}
func TestGitHubSignedTagBinding(t *testing.T) {
	for _, bad := range []string{"", "lightweight-tag", "unsigned-tag", "tag-source", "unreachable-tag", "retargeted-tag"} {
		t.Run(bad, func(t *testing.T) {
			g, _ := mockAPI(t, bad, true)
			cfg, r, _, _ := fixture(t)
			r.Pipeline.Event = "tag"
			r.Pipeline.Ref = "refs/tags/v1.2.3"
			r.Pipeline.Commit = strings.Repeat("b", 40)
			cred, err := g.Authorize(context.Background(), r, cfg.Repositories[0])
			if bad == "" {
				if err != nil || cred.Token == "" {
					t.Fatalf("valid signed tag:%v", err)
				}
			} else if err == nil || cred.Token != "" {
				t.Fatal("invalid signed tag granted")
			}
		})
	}
}
func TestInspectionTokenRevoked(t *testing.T) {
	g, f := mockAPI(t, "", false)
	cfg, r, _, _ := fixture(t)
	if err := g.Inspect(context.Background(), r, cfg.Repositories[0]); err != nil {
		t.Fatal(err)
	}
	if f.mints.Load() != 1 || f.revokes.Load() != 1 {
		t.Fatal("inspection token lifetime")
	}
}
