//go:build repositoryfixtures

package main

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestPreparationIsExplicitPreservingAndOffline(t *testing.T) {
	root := t.TempDir()
	stack := filepath.Join(root, "stacks", "woodpecker-ci")
	if err := os.MkdirAll(filepath.Join(stack, "publisher-broker"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "scripts"), 0700); err != nil {
		t.Fatal(err)
	}
	for _, pair := range [][2]string{{"../prepare-stack.sh", filepath.Join(stack, "prepare-stack.sh")}, {"../stack.env.example", filepath.Join(stack, "stack.env.example")}, {"../caddy_snippet.conf.example", filepath.Join(stack, "caddy_snippet.conf.example")}, {"config.json.example", filepath.Join(stack, "publisher-broker", "config.json.example")}, {"../../../scripts/prepare-stack-lib.sh", filepath.Join(root, "scripts", "prepare-stack-lib.sh")}} {
		b, err := os.ReadFile(pair[0])
		if err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(pair[1], b, 0600); err != nil {
			t.Fatal(err)
		}
	}
	bin := filepath.Join(root, "bin")
	if err := os.Mkdir(bin, 0700); err != nil {
		t.Fatal(err)
	}
	logPath := filepath.Join(root, "docker.log")
	if err := os.WriteFile(filepath.Join(bin, "docker"), []byte("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$DOCKER_TEST_LOG\"\nexit 1\n"), 0700); err != nil {
		t.Fatal(err)
	}
	run := func(opt bool) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, "bash", filepath.Join(stack, "prepare-stack.sh"))
		cmd.Env = []string{"PATH=" + bin + ":/usr/bin:/bin", "HOME=" + root, "DOCKER_TEST_LOG=" + logPath}
		if opt {
			cmd.Env = append(cmd.Env, "WOODPECKER_PREPARE_PUBLISHER_BROKER=1")
		}
		return cmd.Run()
	}
	if err := run(false); err != nil {
		t.Fatal("default preparation failed")
	}
	runtime := filepath.Join(stack, "publisher-broker", "runtime")
	if _, err := os.Stat(runtime); !os.IsNotExist(err) {
		t.Fatal("default preparation activated broker")
	}
	if err := run(true); err != nil {
		t.Fatal("opt-in preparation failed")
	}
	config := filepath.Join(runtime, "private", "config.json")
	if err := os.WriteFile(config, []byte("preserve-operator-fixture"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := run(true); err != nil {
		t.Fatal("repeat preparation failed")
	}
	b, _ := os.ReadFile(config)
	if string(b) != "preserve-operator-fixture" {
		t.Fatal("existing operator file overwritten")
	}
	for _, suffix := range []string{"private", "state", "state/replay", "state/leases"} {
		s, e := os.Stat(filepath.Join(runtime, suffix))
		if e != nil || s.Mode().Perm() != 0700 {
			t.Fatal("unsafe state directory permissions")
		}
	}
	log, _ := os.ReadFile(logPath)
	for _, line := range strings.Fields(string(log)) {
		if line != "info" {
			t.Fatal("preparation attempted Docker mutation")
		}
	}
	if err := os.RemoveAll(filepath.Join(runtime, "state")); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(root, "outside")
	if err := os.Mkdir(outside, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Join(runtime, "state")); err != nil {
		t.Fatal(err)
	}
	if err := run(true); err == nil {
		t.Fatal("symlink state directory accepted")
	}
	entries, _ := os.ReadDir(outside)
	if len(entries) != 0 {
		t.Fatal("preparation followed unsafe directory")
	}
}
