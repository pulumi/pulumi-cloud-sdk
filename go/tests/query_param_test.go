// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Query and path parameter rendering. Ports
// sdk/java/src/test/java/com/pulumi/cloud/sdk/QueryParamTest.java and the
// QueryParamEncoding / PathParamNullIgnored cases from
// sdk/dotnet/Pulumi.Cloud.Sdk.Tests/RuntimeTests.cs, which in turn mirror
// sdk/python/tests/test_query_params.py.
//
// Those suites reach into package-private parameter maps. Go's request builder
// (`createRequest`) is unexported and this is an external test package, so the
// assertions here go through the one exported seam instead: a CloudClient whose
// Executor captures the *http.Request the runtime produced. That is a closer test
// of observable behaviour anyway — it asserts the wire form, not an intermediate
// map.
package tests

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apiclient"
)

// captureExecutor records the request it is handed and replies with a canned
// response, so no network is involved.
func captureExecutor(t *testing.T, status int, body string) (*apiclient.CloudClient, func() *http.Request) {
	t.Helper()

	var captured *http.Request
	client := &apiclient.CloudClient{
		BaseURL: "https://api.example.com",
		Executor: func(req *http.Request) (*http.Response, error) {
			captured = req
			return &http.Response{
				StatusCode: status,
				Body:       io.NopCloser(strings.NewReader(body)),
				Header:     http.Header{"Content-Type": []string{"application/json"}},
			}, nil
		},
	}
	return client, func() *http.Request { return captured }
}

func TestQueryParamsAreRendered(t *testing.T) {
	t.Parallel()

	client, request := captureExecutor(t, http.StatusOK, `{"members":[]}`)

	token := "next-page"
	memberType := "backend"
	if _, err := client.ListOrganizationMembers(context.Background(), "acme", &token, &memberType); err != nil {
		t.Fatalf("ListOrganizationMembers: %v", err)
	}

	req := request()
	if req == nil {
		t.Fatal("executor was never invoked")
	}

	query := req.URL.Query()
	if got := query.Get("continuationToken"); got != token {
		t.Errorf("continuationToken: got %q, want %q", got, token)
	}
	if got := query.Get("type"); got != memberType {
		t.Errorf("type: got %q, want %q", got, memberType)
	}
}

// Java's `nullsAreDropped` and .NET's `PathParamNullIgnored`: an unset query
// parameter must not appear on the wire at all, rather than appearing empty.
func TestNilQueryParamsAreDropped(t *testing.T) {
	t.Parallel()

	client, request := captureExecutor(t, http.StatusOK, `{"members":[]}`)

	if _, err := client.ListOrganizationMembers(context.Background(), "acme", nil, nil); err != nil {
		t.Fatalf("ListOrganizationMembers: %v", err)
	}

	query := request().URL.Query()
	for _, key := range []string{"continuationToken", "type"} {
		if _, present := query[key]; present {
			t.Errorf("%s should be absent when nil, got %q", key, query.Get(key))
		}
	}
}

// Path parameters are percent-encoded, so a value containing a separator cannot
// forge an extra path segment.
func TestPathParamsAreEscaped(t *testing.T) {
	t.Parallel()

	client, request := captureExecutor(t, http.StatusOK, `{"members":[]}`)

	if _, err := client.ListOrganizationMembers(context.Background(), "acme/evil", nil, nil); err != nil {
		t.Fatalf("ListOrganizationMembers: %v", err)
	}

	req := request()
	if strings.Contains(req.URL.EscapedPath(), "acme/evil") {
		t.Errorf("path separator in an org name must be escaped, got %q", req.URL.EscapedPath())
	}
	if !strings.Contains(req.URL.EscapedPath(), "acme%2Fevil") {
		t.Errorf("expected a percent-encoded org name, got %q", req.URL.EscapedPath())
	}
}
