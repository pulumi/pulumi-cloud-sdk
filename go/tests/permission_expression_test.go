// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Round-trip tests for the `PermissionExpression` polymorphic hierarchy. Ports
// sdk/java/src/test/java/com/pulumi/cloud/sdk/PermissionExpressionRoundTripTest.java,
// which in turn mirrors sdk/python/tests/test_permission_expression_roundtrip.py
// and sdk/nodejs/tests/permission_expression.test.js. The tree built here matches
// those `buildTree()` helpers node-for-node.
//
// `PermissionExpression` is the most complex generated shape: a recursive,
// discriminated composite whose fields are typed against *abstract* intermediates
// (PermissionBooleanExpression) while the concrete node type travels in the
// `__type` discriminator.
//
// Go models this differently from Java/C#: an exported sealed interface per node,
// an unexported impl, an exported `…Builder{}.Build()` constructor, and a
// free-function dispatcher (`UnmarshalJSONPermissionExpression`) rather than an
// UnmarshalJSON on the interface. Tests therefore construct via builders and
// assert via interface type assertions — the impls are unexported and
// unreachable.
package tests

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apitype"
)

func str(v string) apitype.PermissionLiteralExpressionString {
	return apitype.PermissionLiteralExpressionStringBuilder{Value: v}.Build()
}

func num(v float64) apitype.PermissionLiteralExpressionNumber {
	return apitype.PermissionLiteralExpressionNumberBuilder{Value: v}.Build()
}

func boolean(v bool) apitype.PermissionLiteralExpressionBool {
	return apitype.PermissionLiteralExpressionBoolBuilder{Value: v}.Build()
}

func eq(left, right apitype.PermissionExpression) apitype.PermissionExpressionEqual {
	return apitype.PermissionExpressionEqualBuilder{Left: left, Right: right}.Build()
}

// A deep, heterogeneous PermissionExpression tree:
//
//	And( Equal("prod", "prod"), Or( Equal(42.5, 42.5), Equal(true, false) ) )
func buildTree() apitype.PermissionExpressionAnd {
	or := apitype.PermissionExpressionOrBuilder{
		PermissionBooleanExpressionBinaryBuilder: apitype.PermissionBooleanExpressionBinaryBuilder{
			Left:  eq(num(42.5), num(42.5)),
			Right: eq(boolean(true), boolean(false)),
		},
	}.Build()

	return apitype.PermissionExpressionAndBuilder{
		PermissionBooleanExpressionBinaryBuilder: apitype.PermissionBooleanExpressionBinaryBuilder{
			Left:  eq(str("prod"), str("prod")),
			Right: or,
		},
	}.Build()
}

func TestRoundTripPreservesConcreteTypesAndValues(t *testing.T) {
	t.Parallel()

	encoded, err := json.Marshal(buildTree())
	if err != nil {
		t.Fatalf("marshalling tree: %v", err)
	}

	// The discriminator must be on the wire for every concrete node, otherwise
	// the dispatcher below has nothing to switch on.
	for _, want := range []string{
		`"__type":"PermissionExpressionAnd"`,
		`"__type":"PermissionExpressionOr"`,
		`"__type":"PermissionExpressionEqual"`,
		`"__type":"PermissionLiteralExpressionString"`,
		`"__type":"PermissionLiteralExpressionNumber"`,
		`"__type":"PermissionLiteralExpressionBool"`,
	} {
		if !strings.Contains(string(encoded), want) {
			t.Errorf("serialized tree is missing %s\ngot: %s", want, encoded)
		}
	}

	// Re-parse as the *abstract* root and walk back down, asserting the concrete
	// type at every level.
	var decoded apitype.PermissionExpression
	if err := apitype.UnmarshalJSONPermissionExpression(encoded, &decoded); err != nil {
		t.Fatalf("unmarshalling tree: %v", err)
	}

	and, ok := decoded.(apitype.PermissionExpressionAnd)
	if !ok {
		t.Fatalf("root: got %T, want PermissionExpressionAnd", decoded)
	}

	andLeft, ok := and.Left().(apitype.PermissionExpressionEqual)
	if !ok {
		t.Fatalf("and.Left: got %T, want PermissionExpressionEqual", and.Left())
	}
	assertString(t, "and.Left.Left", andLeft.Left(), "prod")
	assertString(t, "and.Left.Right", andLeft.Right(), "prod")

	or, ok := and.Right().(apitype.PermissionExpressionOr)
	if !ok {
		t.Fatalf("and.Right: got %T, want PermissionExpressionOr", and.Right())
	}

	orLeft, ok := or.Left().(apitype.PermissionExpressionEqual)
	if !ok {
		t.Fatalf("or.Left: got %T, want PermissionExpressionEqual", or.Left())
	}
	assertNumber(t, "or.Left.Left", orLeft.Left(), 42.5)
	assertNumber(t, "or.Left.Right", orLeft.Right(), 42.5)

	orRight, ok := or.Right().(apitype.PermissionExpressionEqual)
	if !ok {
		t.Fatalf("or.Right: got %T, want PermissionExpressionEqual", or.Right())
	}
	assertBool(t, "or.Right.Left", orRight.Left(), true)
	assertBool(t, "or.Right.Right", orRight.Right(), false)
}

// Java's `unknownDiscriminatorFails`, which expects Jackson's
// InvalidTypeIdException. The Go dispatcher's default branch reports
// "type '%s' not recognized".
func TestUnknownDiscriminatorFails(t *testing.T) {
	t.Parallel()

	var decoded apitype.PermissionExpression
	err := apitype.UnmarshalJSONPermissionExpression([]byte(`{"__type":"NoSuchExpression"}`), &decoded)
	if err == nil {
		t.Fatal("expected an error for an unknown discriminator, got nil")
	}
	if !strings.Contains(err.Error(), "NoSuchExpression") {
		t.Errorf("error should name the offending discriminator, got: %v", err)
	}
}

// The abstract root cannot be marshalled — it has no discriminator to emit. This
// has no Java or C# counterpart; it is specific to Go's builder-per-interface
// modelling, where the abstract builder is constructible.
func TestAbstractExpressionCannotBeMarshalled(t *testing.T) {
	t.Parallel()

	// Parenthesised: a composite literal in an if-statement initialiser is
	// ambiguous with the block that follows it.
	abstract := (apitype.PermissionExpressionBuilder{}).Build()
	if _, err := abstract.MarshalJSON(); err == nil {
		t.Fatal("expected marshalling the abstract PermissionExpression to fail, got nil")
	}
}

func assertString(t *testing.T, field string, got apitype.PermissionExpression, want string) {
	t.Helper()
	lit, ok := got.(apitype.PermissionLiteralExpressionString)
	if !ok {
		t.Fatalf("%s: got %T, want PermissionLiteralExpressionString", field, got)
	}
	if lit.Value() != want {
		t.Errorf("%s: got %q, want %q", field, lit.Value(), want)
	}
}

func assertNumber(t *testing.T, field string, got apitype.PermissionExpression, want float64) {
	t.Helper()
	lit, ok := got.(apitype.PermissionLiteralExpressionNumber)
	if !ok {
		t.Fatalf("%s: got %T, want PermissionLiteralExpressionNumber", field, got)
	}
	if lit.Value() != want {
		t.Errorf("%s: got %v, want %v", field, lit.Value(), want)
	}
}

func assertBool(t *testing.T, field string, got apitype.PermissionExpression, want bool) {
	t.Helper()
	lit, ok := got.(apitype.PermissionLiteralExpressionBool)
	if !ok {
		t.Fatalf("%s: got %T, want PermissionLiteralExpressionBool", field, got)
	}
	if lit.Value() != want {
		t.Errorf("%s: got %v, want %v", field, lit.Value(), want)
	}
}
