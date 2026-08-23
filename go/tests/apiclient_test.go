// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Error mapping for the hand-written client runtime (sdk/go/apiclient/errors.go
// and the error path of apiclient.go).
//
// This has no counterpart in the Java, .NET, Python or Node suites — none of them
// tests its error type at all. It is included because APIError is the surface
// every consumer touches on failure, and because the runtime has two distinct
// paths through it: a well-formed `{code,message}` JSON body, and anything else,
// which falls back to the HTTP status plus the raw body.
package tests

import (
	"context"
	"errors"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apiclient"
)

func errorClient(status int, body string) *apiclient.CloudClient {
	return &apiclient.CloudClient{
		BaseURL: "https://api.example.com",
		Executor: func(*http.Request) (*http.Response, error) {
			return &http.Response{
				StatusCode: status,
				Body:       io.NopCloser(strings.NewReader(body)),
				Header:     http.Header{"Content-Type": []string{"application/json"}},
			}, nil
		},
	}
}

func TestErrorResponseWithJSONBody(t *testing.T) {
	t.Parallel()

	client := errorClient(http.StatusNotFound, `{"code":404,"message":"organization not found"}`)

	_, err := client.ListOrganizationMembers(context.Background(), "acme", nil, nil)
	if err == nil {
		t.Fatal("expected an error for a 404 response, got nil")
	}

	var apiErr *apiclient.APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("error should unwrap to *APIError, got %T: %v", err, err)
	}
	if apiErr.HTTPStatusCode() != http.StatusNotFound {
		t.Errorf("status: got %d, want %d", apiErr.HTTPStatusCode(), http.StatusNotFound)
	}
	if apiErr.ResponseMessage() != "organization not found" {
		t.Errorf("message: got %q, want %q", apiErr.ResponseMessage(), "organization not found")
	}
	if !apiErr.IsNotFound() {
		t.Error("IsNotFound() should be true for a 404")
	}
	if apiErr.IsConflict() {
		t.Error("IsConflict() should be false for a 404")
	}
}

// A body that is not the {code,message} envelope must still produce a usable
// APIError carrying the HTTP status, rather than being swallowed or panicking.
func TestErrorResponseWithNonJSONBody(t *testing.T) {
	t.Parallel()

	client := errorClient(http.StatusBadGateway, "upstream exploded")

	_, err := client.ListOrganizationMembers(context.Background(), "acme", nil, nil)
	if err == nil {
		t.Fatal("expected an error for a 502 response, got nil")
	}

	var apiErr *apiclient.APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("error should unwrap to *APIError, got %T: %v", err, err)
	}
	if apiErr.HTTPStatusCode() != http.StatusBadGateway {
		t.Errorf("status: got %d, want %d", apiErr.HTTPStatusCode(), http.StatusBadGateway)
	}
	if !strings.Contains(apiErr.ResponseMessage(), "upstream exploded") {
		t.Errorf("message should carry the raw body, got %q", apiErr.ResponseMessage())
	}
}

func TestConflictIsRecognised(t *testing.T) {
	t.Parallel()

	client := errorClient(http.StatusConflict, `{"code":409,"message":"already exists"}`)

	_, err := client.ListOrganizationMembers(context.Background(), "acme", nil, nil)

	var apiErr *apiclient.APIError
	if !errors.As(err, &apiErr) {
		t.Fatalf("error should unwrap to *APIError, got %T: %v", err, err)
	}
	if !apiErr.IsConflict() {
		t.Error("IsConflict() should be true for a 409")
	}
	if apiErr.IsNotFound() {
		t.Error("IsNotFound() should be false for a 409")
	}
}

// A transport failure is not an APIError — it must surface as a wrapped error so
// callers can tell "the server said no" from "we never reached the server".
func TestTransportFailureIsWrappedNotAnAPIError(t *testing.T) {
	t.Parallel()

	sentinel := errors.New("dial tcp: connection refused")
	client := &apiclient.CloudClient{
		BaseURL: "https://api.example.com",
		Executor: func(*http.Request) (*http.Response, error) {
			return nil, sentinel
		},
	}

	_, err := client.ListOrganizationMembers(context.Background(), "acme", nil, nil)
	if err == nil {
		t.Fatal("expected an error when the executor fails, got nil")
	}
	if !errors.Is(err, sentinel) {
		t.Errorf("executor error should be wrapped, got %v", err)
	}

	var apiErr *apiclient.APIError
	if errors.As(err, &apiErr) {
		t.Error("a transport failure must not be reported as an APIError")
	}
}

func TestAPIErrorAccessors(t *testing.T) {
	t.Parallel()

	header := http.Header{"X-Request-Id": []string{"abc123"}}
	err := apiclient.NewAPIError(http.StatusNoContent, "nothing here", header)

	if !err.IsNoContent() {
		t.Error("IsNoContent() should be true for a 204")
	}
	if got := err.ResponseHeader().Get("X-Request-Id"); got != "abc123" {
		t.Errorf("ResponseHeader: got %q, want %q", got, "abc123")
	}
	if !strings.Contains(err.Error(), "nothing here") {
		t.Errorf("Error() should include the message, got %q", err.Error())
	}

	// The runtime guards against a nil receiver; a consumer logging a nil error
	// should not panic.
	var nilErr *apiclient.APIError
	if got := nilErr.Error(); got != "<nil>" {
		t.Errorf("nil-receiver Error(): got %q, want %q", got, "<nil>")
	}
}
