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

// Guards EscSchemaSchema's legacy wire shorthand: JSON Schema's bare true/false
// instead of an object, meaning {always: true} / {never: true}. Mirrors
// cmd/console2/src/proxy/esc-schema-schema-wire-bool-fixup.spec.ts.
func TestEscSchemaSchemaMarshalUnmarshal_BareBooleanRoundTrip(t *testing.T) {
	t.Parallel()

	for _, tt := range []struct {
		name string
		json string
	}{
		{"true", "true"},
		{"false", "false"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			var s apitype.EscSchemaSchema
			if err := json.Unmarshal([]byte(tt.json), &s); err != nil {
				t.Fatalf("unmarshal: %v", err)
			}

			wantAlways := tt.json == "true"
			if s.Always != wantAlways {
				t.Fatalf("unmarshal(%s): Always = %v, want %v", tt.json, s.Always, wantAlways)
			}
			if s.Never != !wantAlways {
				t.Fatalf("unmarshal(%s): Never = %v, want %v", tt.json, s.Never, !wantAlways)
			}

			out, err := json.Marshal(&s)
			if err != nil {
				t.Fatalf("marshal: %v", err)
			}
			if string(out) != tt.json {
				t.Fatalf("marshal round-trip = %s, want %s", out, tt.json)
			}
		})
	}
}

func TestEscSchemaSchemaUnmarshal_BareBooleanAtMapPosition(t *testing.T) {
	t.Parallel()

	var s apitype.EscSchemaSchema
	if err := json.Unmarshal([]byte(`{"properties":{"foo":true,"bar":false}}`), &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	foo := s.Properties["foo"]
	if foo == nil || !foo.Always {
		t.Fatalf("properties.foo = %+v, want an Always schema", foo)
	}
	bar := s.Properties["bar"]
	if bar == nil || !bar.Never {
		t.Fatalf("properties.bar = %+v, want a Never schema", bar)
	}
}

func TestEscSchemaSchemaUnmarshal_BareBooleanTwoLevelsDeep(t *testing.T) {
	t.Parallel()

	var s apitype.EscSchemaSchema
	if err := json.Unmarshal([]byte(`{"properties":{"foo":{"anyOf":[true,{"type":"string"}]}}}`), &s); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	foo := s.Properties["foo"]
	if foo == nil || len(foo.AnyOf) != 2 {
		t.Fatalf("properties.foo = %+v, want an object schema with 2 anyOf entries", foo)
	}
	if !foo.AnyOf[0].Always {
		t.Fatalf("properties.foo.anyOf[0].Always = false, want true")
	}
	if foo.AnyOf[1].Type != "string" {
		t.Fatalf("properties.foo.anyOf[1].Type = %q, want %q", foo.AnyOf[1].Type, "string")
	}
}
