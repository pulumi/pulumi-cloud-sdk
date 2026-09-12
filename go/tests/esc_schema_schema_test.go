// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Regression coverage for apitype.EscSchemaSchema's hand-written JSON-schema
// evaluation logic (sdk/go/apitype/esc_schema_schema_impl.go), which has no
// generated counterpart and so no other test suite exercises it.
package tests

import (
	"encoding/json"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apitype"
)

// A $defs entry that references itself, reached through a rotateOnly property,
// used to recurse forever inside setRotateOnly: its re-entry guard only ever
// checked the original (never-mutated) node, while the rotateOnly flag was only
// ever set on copies. Compile crashed the whole process with an unrecoverable
// stack overflow.
func TestEscSchemaSchemaCompile_SelfReferentialRotateOnlyRef(t *testing.T) {
	t.Parallel()

	var s apitype.EscSchemaSchema
	if err := json.Unmarshal([]byte(`{
		"$defs": {"a": {"$ref": "#/$defs/a"}},
		"properties": {"foo": {"$ref": "#/$defs/a"}},
		"rotateOnly": ["foo"]
	}`), &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if err := s.Compile(); err != nil {
		t.Fatalf("compile: %v", err)
	}

	foo := s.Properties["foo"]
	if foo == nil || !foo.IsRotateOnly() {
		t.Fatalf("expected properties.foo to be rotate-only after compiling a self-referential $ref, got %+v", foo)
	}
}

// A JSON `null` entry inside anyOf/oneOf decodes to a nil slice element, since
// encoding/json does not invoke UnmarshalJSON for a null value. Item and
// Property used to dereference that nil element directly, panicking.
func TestEscSchemaSchemaItem_NilAnyOfEntry(t *testing.T) {
	t.Parallel()

	var s apitype.EscSchemaSchema
	if err := json.Unmarshal([]byte(`{"anyOf":[null,{"type":"string"}]}`), &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if err := s.Compile(); err != nil {
		t.Fatalf("compile: %v", err)
	}

	_ = s.Item(0)
}

func TestEscSchemaSchemaProperty_NilOneOfEntry(t *testing.T) {
	t.Parallel()

	var s apitype.EscSchemaSchema
	if err := json.Unmarshal([]byte(`{"oneOf":[null,{"type":"object","properties":{"foo":{"type":"string"}}}]}`), &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if err := s.Compile(); err != nil {
		t.Fatalf("compile: %v", err)
	}

	got := s.Property("foo")
	if got == nil {
		t.Fatal(`Property("foo") returned nil`)
	}
	if got.Type != "string" {
		t.Fatalf("Property(%q).Type = %q, want %q", "foo", got.Type, "string")
	}
}
