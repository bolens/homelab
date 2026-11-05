package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

type githubIssuer struct {
	baseURL string
	appID   string
	key     *rsa.PrivateKey
	client  *http.Client
}

func appKey(data []byte) (*rsa.PrivateKey, error) {
	block, rest := pem.Decode(data)
	if block == nil || len(bytes.TrimSpace(rest)) != 0 {
		return nil, errDenied
	}
	if k, err := x509.ParsePKCS1PrivateKey(block.Bytes); err == nil {
		if k.N.BitLen() < 2048 {
			return nil, errDenied
		}
		return k, k.Validate()
	}
	k, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		return nil, err
	}
	r, ok := k.(*rsa.PrivateKey)
	if !ok || r.N.BitLen() < 2048 {
		return nil, errDenied
	}
	return r, r.Validate()
}
func (g *githubIssuer) jwt() (string, error) {
	enc := base64.RawURLEncoding.EncodeToString
	payload, err := json.Marshal(map[string]any{"iss": g.appID, "iat": time.Now().Add(-time.Minute).Unix(), "exp": time.Now().Add(5 * time.Minute).Unix()})
	if err != nil {
		return "", err
	}
	data := enc([]byte(`{"alg":"RS256","typ":"JWT"}`)) + "." + enc(payload)
	sum := sha256.Sum256([]byte(data))
	sig, err := rsa.SignPKCS1v15(rand.Reader, g.key, crypto.SHA256, sum[:])
	if err != nil {
		return "", err
	}
	return data + "." + enc(sig), nil
}
func (g *githubIssuer) call(ctx context.Context, method, path, token string, body, out any) error {
	var data io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return err
		}
		data = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, g.baseURL+path, data)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
	req.Header.Set("User-Agent", "woodpecker-publisher-broker")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := g.client.Do(req)
	if err != nil {
		return errors.New("github unavailable")
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("github returned status %d", resp.StatusCode)
	}
	if out == nil {
		_, err = io.Copy(io.Discard, io.LimitReader(resp.Body, maxBody))
		return err
	}
	limited := io.LimitReader(resp.Body, maxBody+1)
	dataBytes, err := io.ReadAll(limited)
	if err != nil || len(dataBytes) > maxBody {
		return errDenied
	}
	return json.Unmarshal(dataBytes, out)
}

type githubRef struct {
	Ref    string `json:"ref"`
	Object struct {
		SHA  string `json:"sha"`
		Type string `json:"type"`
	} `json:"object"`
}

func (g *githubIssuer) Authorize(ctx context.Context, req request, p policy) (credential, error) {
	return g.authorize(ctx, req, p, false)
}
func (g *githubIssuer) Inspect(ctx context.Context, req request, p policy) error {
	_, err := g.authorize(ctx, req, p, true)
	return err
}
func (g *githubIssuer) authorize(ctx context.Context, req request, p policy, inspect bool) (credential, error) {
	remoteID, err := strconv.ParseInt(p.RemoteID, 10, 64)
	if err != nil || remoteID <= 0 {
		return credential{}, errDenied
	}
	jwt, err := g.jwt()
	if err != nil {
		return credential{}, err
	}
	permissions := p.Permissions
	if inspect {
		permissions = map[string]string{"contents": "read", "actions_variables": "read"}
	}

	var minted struct {
		Token        string    `json:"token"`
		Expires      time.Time `json:"expires_at"`
		Repositories []struct {
			ID int64 `json:"id"`
		} `json:"repositories"`
		Permissions map[string]string `json:"permissions"`
	}
	err = g.call(ctx, http.MethodPost, fmt.Sprintf("/app/installations/%d/access_tokens", p.InstallationID), jwt, map[string]any{"repository_ids": []int64{remoteID}, "permissions": permissions}, &minted)
	if err != nil {
		return credential{}, err
	}
	accepted := false
	defer func() {
		if !accepted && minted.Token != "" {
			revokeCtx, cancel := context.WithTimeout(context.Background(), time.Second)
			defer cancel()
			_ = g.call(revokeCtx, http.MethodDelete, "/installation/token", minted.Token, nil, nil)
		}
	}()
	if minted.Token == "" || len(minted.Repositories) != 1 || minted.Repositories[0].ID != remoteID || minted.Expires.Before(time.Now().Add(time.Minute)) || minted.Expires.After(time.Now().Add(65*time.Minute)) {
		return credential{}, errDenied
	}
	for k, v := range permissions {
		if minted.Permissions[k] != v {
			return credential{}, errDenied
		}
	}
	for k, v := range minted.Permissions {
		if k != "metadata" && permissions[k] != v {
			return credential{}, errDenied
		}
		if k == "metadata" && v != "read" {
			return credential{}, errDenied
		}
	}
	prefix := "/repos/" + p.FullName
	var repo struct {
		ID            int64  `json:"id"`
		FullName      string `json:"full_name"`
		DefaultBranch string `json:"default_branch"`
		Archived      bool   `json:"archived"`
		Disabled      bool   `json:"disabled"`
	}
	var flag struct {
		Name  string `json:"name"`
		Value string `json:"value"`
	}
	var branch struct {
		Name      string `json:"name"`
		Protected bool   `json:"protected"`
		Commit    struct {
			SHA string `json:"sha"`
		} `json:"commit"`
	}
	// Independent immutable metadata reads share one bounded authorization deadline.
	var wg sync.WaitGroup
	errs := make(chan error, 3)
	for _, task := range []struct {
		path string
		out  any
	}{{prefix, &repo}, {prefix + "/actions/variables/WOODPECKER_PUBLISHING", &flag}, {prefix + "/branches/main", &branch}} {
		wg.Add(1)
		go func(path string, out any) {
			defer wg.Done()
			errs <- g.call(ctx, http.MethodGet, path, minted.Token, nil, out)
		}(task.path, task.out)
	}
	wg.Wait()
	close(errs)
	for e := range errs {
		if e != nil {
			return credential{}, e
		}
	}
	if repo.ID != remoteID || repo.FullName != p.FullName || repo.DefaultBranch != "main" || repo.Archived || repo.Disabled || flag.Name != "WOODPECKER_PUBLISHING" || flag.Value != "true" || branch.Name != "main" || !branch.Protected || !shaPattern.MatchString(branch.Commit.SHA) {
		return credential{}, errDenied
	}
	if req.Pipeline.Event == "push" {
		if branch.Commit.SHA != req.Pipeline.Commit {
			return credential{}, errDenied
		}
	} else {
		tag := strings.TrimPrefix(req.Pipeline.Ref, "refs/tags/")
		path := prefix + "/git/ref/tags/" + url.PathEscape(tag)
		var ref githubRef
		if err = g.call(ctx, http.MethodGet, path, minted.Token, nil, &ref); err != nil {
			return credential{}, err
		}
		if ref.Ref != req.Pipeline.Ref || !shaPattern.MatchString(ref.Object.SHA) {
			return credential{}, errDenied
		}
		commit := ref.Object.SHA
		switch ref.Object.Type {
		case "commit":
			return credential{}, errDenied
		case "tag":
			var annotated struct {
				Tag    string `json:"tag"`
				SHA    string `json:"sha"`
				Object struct {
					SHA  string `json:"sha"`
					Type string `json:"type"`
				} `json:"object"`
				Verification struct {
					Verified bool `json:"verified"`
				} `json:"verification"`
			}
			if err = g.call(ctx, http.MethodGet, prefix+"/git/tags/"+ref.Object.SHA, minted.Token, nil, &annotated); err != nil {
				return credential{}, err
			}
			if annotated.Tag != tag || annotated.SHA != ref.Object.SHA || annotated.Object.Type != "commit" || !annotated.Verification.Verified {
				return credential{}, errDenied
			}
			commit = annotated.Object.SHA
		default:
			return credential{}, errDenied
		}
		if commit != req.Pipeline.Commit {
			return credential{}, errDenied
		}
		var comparison struct {
			MergeBase struct {
				SHA string `json:"sha"`
			} `json:"merge_base_commit"`
		}
		if err = g.call(ctx, http.MethodGet, prefix+"/compare/"+commit+"..."+branch.Commit.SHA, minted.Token, nil, &comparison); err != nil {
			return credential{}, err
		}
		if comparison.MergeBase.SHA != commit {
			return credential{}, errDenied
		}
		var final githubRef
		if err = g.call(ctx, http.MethodGet, path, minted.Token, nil, &final); err != nil {
			return credential{}, err
		}
		if final != ref {
			return credential{}, errDenied
		}
	}
	accepted = !inspect
	return credential{Token: minted.Token, ExpiresAt: minted.Expires}, nil
}
