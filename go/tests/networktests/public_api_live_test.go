// Copyright 2026, Pulumi Corporation.  All rights reserved.

// A live, unauthenticated call against the public Pulumi Cloud API. Ports
// sdk/java/src/test/java/com/pulumi/cloud/sdk/PublicApiLiveTest.java and
// sdk/dotnet/Pulumi.Cloud.Sdk.Tests/PublicApiLiveTest.cs, and mirrors
// sdk/python/tests/test_public_api_live.py and
// sdk/nodejs/tests/public_api_live.test.js.
//
// This is a smoke test of the whole stack — real DNS, TLS, routing, and JSON
// decoding of a real response — which no amount of stubbed-Executor testing
// covers.
//
// It lives in its own package, and its own Bazel target, so that it can carry
// `requires-network` without dragging the offline suite in sdk/go/tests onto a
// network-enabled worker.
//
// Like its four counterparts it *skips* rather than fails when the request never
// reaches the server: a developer offline, or an RBE worker without egress,
// should not see a red test. A real HTTP status is a genuine failure and is
// reported as one.
package networktests

import (
	"context"
	"errors"
	"net/http"
	"os"
	"regexp"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apiclient"
)

var semver = regexp.MustCompile(`^\d+\.\d+\.\d+`)

func TestVersionReturnsSemver(t *testing.T) {
	t.Parallel()

	host := os.Getenv("PULUMI_API_HOST")
	if host == "" {
		host = "https://api.pulumi.com"
	}

	client := &apiclient.CloudClient{
		BaseURL:  host,
		Executor: http.DefaultClient.Do,
	}

	response, err := client.Version(context.Background())
	if err != nil {
		// An APIError means we reached the service and it answered — that is a
		// real failure. Anything else is a transport problem; skip.
		var apiErr *apiclient.APIError
		if errors.As(err, &apiErr) {
			t.Fatalf("Version returned HTTP %d: %s", apiErr.HTTPStatusCode(), apiErr.ResponseMessage())
		}
		t.Skipf("skipping: could not reach %s: %v", host, err)
	}

	if response == nil {
		t.Fatal("Version returned a nil response and no error")
	}
	if !semver.MatchString(response.LatestVersion) {
		t.Errorf("LatestVersion: got %q, want a semver string", response.LatestVersion)
	}
}
