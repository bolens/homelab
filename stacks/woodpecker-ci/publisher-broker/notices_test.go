package main

import (
	"context"
	"encoding/json"
	"io"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

func TestCompiledDependencyNotices(t *testing.T) {
	notices, err := os.ReadFile("THIRD_PARTY_NOTICES.md")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, "go", "list", "-deps", "-json", ".").Output()
	if err != nil {
		t.Fatal("cannot enumerate compiled dependencies")
	}
	d := json.NewDecoder(strings.NewReader(string(out)))
	seen := map[string]bool{}
	for {
		var pkg struct {
			Module *struct{ Path, Version string }
		}
		err = d.Decode(&pkg)
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if pkg.Module == nil || pkg.Module.Version == "" {
			continue
		}
		key := pkg.Module.Path + "@" + pkg.Module.Version
		seen[key] = true
		if !strings.Contains(string(notices), "## "+key+"\n") {
			t.Errorf("missing compiled dependency notice: %s", key)
		}
	}
	for _, line := range strings.Split(string(notices), "\n") {
		if strings.HasPrefix(line, "## ") && strings.Contains(line, "@v") {
			if !seen[strings.TrimPrefix(line, "## ")] {
				t.Errorf("obsolete dependency notice: %s", line)
			}
		}
	}
}
