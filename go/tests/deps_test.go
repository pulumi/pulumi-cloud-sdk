// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Guards that sdk/go/go.mod's direct requires match sanctionedDirectDeps.
// Catches drift between the go.mod templater (sdk/go/go.mod.sh's DIRECT_DEPS)
// and this list — either changed intentionally, both should change together.
// Import additions in the copied runtime files (pkg/apiclient, pkg/apitype)
// are caught separately by //sdk/go:go_sdk_build_test, since the go_library
// deps there are hand-maintained and a new import without a matching dep
// fails to compile.
package tests

import (
	"bufio"
	"os"
	"slices"
	"strings"
	"testing"

	"github.com/bazelbuild/rules_go/go/runfiles"
)

// The published SDK's direct dependency surface. Adding an entry here is the
// reviewer signal that the SDK's third-party graph intentionally grew.
var sanctionedDirectDeps = []string{
	"github.com/blang/semver",
	"github.com/go-jose/go-jose/v4",
	"gopkg.in/yaml.v3",
}

// directRequires extracts the module paths listed as direct (non-indirect) in
// a go.mod file's require(...) block. It's a minimal scanner tailored to this
// repo's own generated sdk/go/go.mod (see sdk/go/go.mod.sh), not a
// general-purpose go.mod parser — using golang.org/x/mod/modfile here would
// force that module to stay a direct dependency of the *root* go.mod even
// though nothing in the root module imports it, since this test's package now
// lives inside the sdk/go nested module and go.mod's own `require` graph no
// longer sees it.
func directRequires(t *testing.T, path string) []string {
	t.Helper()

	f, err := os.Open(path)
	if err != nil {
		t.Fatalf("open %s: %v", path, err)
	}
	defer f.Close()

	var direct []string
	inRequire := false
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		switch {
		case line == "require (":
			inRequire = true
		case inRequire && line == ")":
			inRequire = false
		case inRequire && !strings.HasSuffix(line, "// indirect"):
			if fields := strings.Fields(line); len(fields) > 0 {
				direct = append(direct, fields[0])
			}
		}
	}
	if err := scanner.Err(); err != nil {
		t.Fatalf("scan %s: %v", path, err)
	}
	return direct
}

func TestGoModDirectDepsMatchSanctionedList(t *testing.T) {
	t.Parallel()

	goModPath, err := runfiles.Rlocation("_main/sdk/sdk_go_module_gen.mod")
	if err != nil {
		t.Fatalf("locate generated go.mod runfile: %v", err)
	}

	direct := directRequires(t, goModPath)
	slices.Sort(direct)

	want := slices.Clone(sanctionedDirectDeps)
	slices.Sort(want)

	if !slices.Equal(direct, want) {
		t.Errorf("sdk/go/go.mod direct requires drifted from the sanctioned list.\n"+
			"got:  %v\n"+
			"want: %v\n"+
			"If the addition is intentional, add it to sanctionedDirectDeps in deps_test.go.",
			direct, want)
	}
}
