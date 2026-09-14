// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Tests for CloudClient's response-header parsing (invokeWithResponseAndHeaders /
// invokeWithHeaders and the generated *_.go methods that call them for operations
// declaring typed response headers, e.g. EnvironmentsApi's
// UpdateEnvironment_esc_environments / HeadEnvironment_esc_environments). Mirrors
// sdk/java/src/test/java/com/pulumi/cloud/sdk/ResponseHeadersTest.java,
// sdk/dotnet/Pulumi.Cloud.Sdk.Tests/ResponseHeadersTests.cs,
// sdk/python/tests/test_response_headers.py, and
// sdk/nodejs/tests/response_headers.test.js — this is the one language that had
// no such test at all despite already having the mockable Executor seam (see
// apiclient_test.go / query_param_test.go).
package tests

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apiclient"
)

// headers builds an http.Header via Set, so each key is stored in its
// canonical form (e.g. "ETag" -> "Etag", "Pulumi-ESC-Revision" ->
// "Pulumi-Esc-Revision") the same way net/http canonicalizes a header parsed
// off the wire — a map literal with the raw names would not match what
// Header.Get looks up.
func headers(pairs ...string) http.Header {
	h := http.Header{}
	for i := 0; i+1 < len(pairs); i += 2 {
		h.Set(pairs[i], pairs[i+1])
	}
	return h
}

func headersClient(status int, body string, respHeaders http.Header) *apiclient.CloudClient {
	return &apiclient.CloudClient{
		BaseURL: "https://api.example.com",
		Executor: func(*http.Request) (*http.Response, error) {
			return &http.Response{
				StatusCode: status,
				Body:       io.NopCloser(strings.NewReader(body)),
				Header:     respHeaders,
			}, nil
		},
	}
}

func TestBodyOperationParsesResponseAndHeaders(t *testing.T) {
	t.Parallel()

	client := headersClient(http.StatusOK, `{"diagnostics":[]}`, headers("ETag", "abc123", "Pulumi-ESC-Revision", "7"))

	result, err := client.UpdateEnvironment_esc_environments(context.Background(), "acme", "proj", "env", "values: {}")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result.Response.Diagnostics) != 0 {
		t.Errorf("Diagnostics: got %v, want empty", result.Response.Diagnostics)
	}
	if result.Headers.ETag != "abc123" {
		t.Errorf("ETag: got %q, want %q", result.Headers.ETag, "abc123")
	}
	if result.Headers.PulumiESCRevision != 7 {
		t.Errorf("PulumiESCRevision: got %d, want %d", result.Headers.PulumiESCRevision, 7)
	}
}

func TestNoBodyOperationResolvesToJustTheHeaders(t *testing.T) {
	t.Parallel()

	client := headersClient(http.StatusOK, "", headers("ETag", "head-etag", "Pulumi-ESC-Revision", "3"))

	result, err := client.HeadEnvironment_esc_environments(context.Background(), "acme", "proj", "env")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.ETag != "head-etag" {
		t.Errorf("ETag: got %q, want %q", result.ETag, "head-etag")
	}
	if result.PulumiESCRevision != 3 {
		t.Errorf("PulumiESCRevision: got %d, want %d", result.PulumiESCRevision, 3)
	}
}

func TestMissingHeadersDefaultToTheZeroValue(t *testing.T) {
	t.Parallel()

	client := headersClient(http.StatusOK, "", headers())

	result, err := client.HeadEnvironment_esc_environments(context.Background(), "acme", "proj", "env")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.ETag != "" {
		t.Errorf("ETag: got %q, want empty", result.ETag)
	}
	if result.PulumiESCRevision != 0 {
		t.Errorf("PulumiESCRevision: got %d, want 0", result.PulumiESCRevision)
	}
}

// A malformed-but-present header must degrade to the type's zero value rather
// than failing an otherwise-successful call — see emitParsedResponseHeaderField
// in cmd/pulumi-codegen/cmd/go.go.
func TestMalformedHeaderDefaultsToTheZeroValueRatherThanErroring(t *testing.T) {
	t.Parallel()

	client := headersClient(http.StatusOK, "", headers("ETag", "some-etag", "Pulumi-ESC-Revision", "not-a-number"))

	result, err := client.HeadEnvironment_esc_environments(context.Background(), "acme", "proj", "env")
	if err != nil {
		t.Fatalf("a malformed advisory header must not fail the call, got error: %v", err)
	}
	if result.ETag != "some-etag" {
		t.Errorf("ETag: got %q, want %q", result.ETag, "some-etag")
	}
	if result.PulumiESCRevision != 0 {
		t.Errorf("PulumiESCRevision: got %d, want 0", result.PulumiESCRevision)
	}
}
