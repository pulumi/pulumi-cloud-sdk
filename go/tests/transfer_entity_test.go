// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Round-trip tests for the `TransferEntity` family. Ports
// NestedFamilyBranchTerminalRoundTrips from
// sdk/dotnet/Pulumi.Cloud.Sdk.Tests/PolymorphismTests.cs.
//
// This family differs from PermissionExpression in two ways worth covering
// separately: the discriminator key is `kind` rather than `__type`, and the
// hierarchy has a *branch-terminal* type — `TransferEntityEnvironmentRename`
// carries a `RenameAs` field declared as `TransferEntityEnvironment`, i.e. the
// branch it descends from.
//
// The Go-specific subtlety this test pins down: `Rename` embeds `Environment`
// and so ALSO satisfies the `TransferEntityEnvironment` interface. A Go type
// assertion is therefore not the equivalent of xUnit's exact-type
// `Assert.IsType<>` — `renameAs.(TransferEntityEnvironment)` succeeds for both.
// Narrowing has to be checked by discriminator, plus a negative assertion that
// the value is not itself a Rename.
package tests

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/pulumi/pulumi-cloud-sdk/go/apitype"
)

func TestNestedFamilyBranchTerminalRoundTrips(t *testing.T) {
	t.Parallel()

	rename := apitype.TransferEntityEnvironmentRenameBuilder{
		TransferEntityEnvironmentBuilder: apitype.TransferEntityEnvironmentBuilder{
			ProjectName:     "proj",
			EnvironmentName: "env",
		},
		RenameAs: apitype.TransferEntityEnvironmentBuilder{
			ProjectName:     "proj",
			EnvironmentName: "renamed",
		}.Build(),
	}.Build()

	encoded, err := json.Marshal(rename)
	if err != nil {
		t.Fatalf("marshalling rename: %v", err)
	}

	// This family discriminates on `kind`, not `__type`.
	for _, want := range []string{
		`"kind":"TransferEntityEnvironmentRename"`,
		`"kind":"TransferEntityEnvironment"`,
	} {
		if !strings.Contains(string(encoded), want) {
			t.Errorf("serialized rename is missing %s\ngot: %s", want, encoded)
		}
	}

	var decoded apitype.TransferEntity
	if err := apitype.UnmarshalJSONTransferEntity(encoded, &decoded); err != nil {
		t.Fatalf("unmarshalling rename: %v", err)
	}

	got, ok := decoded.(apitype.TransferEntityEnvironmentRename)
	if !ok {
		t.Fatalf("root: got %T, want TransferEntityEnvironmentRename", decoded)
	}

	inner := got.RenameAs()
	if inner == nil {
		t.Fatal("RenameAs is nil after round-trip")
	}

	// The assertion that matters: RenameAs must resolve to the *branch* type and
	// must not have recursed back into Rename. Because Rename satisfies the
	// Environment interface too, assert on the discriminator rather than on a
	// type assertion.
	discriminator, err := inner.GetDiscriminatorValue()
	if err != nil {
		t.Fatalf("RenameAs discriminator: %v", err)
	}
	if discriminator != "TransferEntityEnvironment" {
		t.Errorf("RenameAs discriminator: got %q, want %q", discriminator, "TransferEntityEnvironment")
	}
	if _, isRename := inner.(apitype.TransferEntityEnvironmentRename); isRename {
		t.Error("RenameAs resolved to a Rename; it must stay the branch type Environment")
	}

	if inner.ProjectName() != "proj" {
		t.Errorf("RenameAs.ProjectName: got %q, want %q", inner.ProjectName(), "proj")
	}
	if inner.EnvironmentName() != "renamed" {
		t.Errorf("RenameAs.EnvironmentName: got %q, want %q", inner.EnvironmentName(), "renamed")
	}
}

func TestTransferEntityUnknownDiscriminatorFails(t *testing.T) {
	t.Parallel()

	var decoded apitype.TransferEntity
	err := apitype.UnmarshalJSONTransferEntity([]byte(`{"kind":"NoSuchEntity"}`), &decoded)
	if err == nil {
		t.Fatal("expected an error for an unknown discriminator, got nil")
	}
	if !strings.Contains(err.Error(), "NoSuchEntity") {
		t.Errorf("error should name the offending discriminator, got: %v", err)
	}
}
