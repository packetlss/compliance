# Compliance verification policy

This co-located producer contains source-only internal test content for developing
and integrating the compliance toolset. It remains semantically separate from the
reusable policy library and from downstream adopter policy.

The producer is a partial named policy source. The destination revision selects
one atomic reviewed development composition, while the actual source content is
identified semantically by its canonical policy-tree digest. The source remains
independently named `verification-policy`, rooted at
`policy-sources/verification-policy/policies/`, and independently digested.
Repository location, source order, and Git metadata do not define its semantic
identity or precedence.

Projects assemble this source with the reusable `control-library` source, which
supplies controls, Rego helpers, and schemas. Source order has no precedence,
and reusable resources must not be copied here.

Every maintained `Baseline`, `BaselineOverlay`, and `RequirementBaseline` owns a
required authored title. These titles name the exact assignable policy roots,
participate in their normal content identities, and never select or order policy.
Control title/purpose continues to come exclusively from `control-library`.

## Retained policy source

The source contains sixteen synthetic resources with an assessment or assurance
purpose. The mock-fleet family retains:

- two illustrative CSA CCM v4.1 technical profiles;
- the AWS and SaaS company overlays that pin and tailor those profiles; and
- the standalone S3 account public-access assessment baseline.

The workstation family retains:

- the managed-workstation package baseline;
- the illustrative macOS hardening benchmark;
- the company adoption overlay with its documented tailoring and exclusion;
  and
- the developer overlay that adds the intentional `shellcheck` drift check.

The Linux hardening and IAM family retains:

- the illustrative Linux server benchmark, company hardening overlay,
  container-runtime overlay, and independent operations baseline; and
- the company role-access requirement, objective baseline, and complete
  ordinary Linux realization.

This family serves server-personas, the stable Linux rollout scenario, and the
IAM boundary project. The container overlay and ordinary Linux hardening
baseline retain the general fail-closed technical-control conflict used when
both divergent definitions of the IPv4-forwarding instance are assigned. IAM
adds its environment-private partial source without copying or exposing the
restricted realization here.

Issue #16 removed three resources after inspecting their content and consumers:

- `company.linux-configuration-demo@1`, whose duplicated package and sysctl
  instances existed only to compose configuration intents for the retired
  configuration-demo project;
- `company.linux-configuration-conflict-demo@1`, whose distinct control
  instances conflicted only after keyed sysctl-intent composition; and
- `company.aws-configuration-conflict-demo@1`, whose distinct S3 control
  instance existed only to conflict during desired-state composition.

The technical implementations referenced by those resources remain covered by
retained Linux, workstation, AWS, and server-persona assessment baselines. No
requirement, requirement baseline, realization, framework mapping, ordinary
baseline/overlay, or general policy/source conflict was removed.

Development projects, stable scenarios, policy-diff examples, and tooling tests
consume these slices. The ordinary projects assemble:

```text
control-library       -> reusable package/sysctl controls and schemas
verification-policy -> synthetic assessment and assurance resources
```

The IAM project adds `environment-private` as a third source. All sixteen
retained verification resources are preserved here.

The earlier source-boundary migration changed the canonical `policies/` content
digest because those three resources were removed:

- before: `sha256:b479cb24083fd6f44e49465c2bb9f4aa026f2dda5e1620b01837693a2dc4ec14`
- after that migration: `sha256:4e4bec94fa7b73056989074ae51c03671bd254fa63c89d4e7d324d13a4313da4`

ADR 0017 implementation then added required titles and regenerated dependent
pins, producing `sha256:d9048c194393a2a1242aaf12a7e1d8e3d77c69cae81c1a763d9a9db55707426a`
for `control-library` and
`sha256:580358f5de42040dc723dd6f7801be0287661bd3d1d8982c12c1f452485b4f37`
for this verification-policy tree.

Stage 6A's typed AWS security-contact and SaaS guest-access schema additions
advance the `control-library` content digest to
`sha256:12075201052d1cf5291d055f13a8c85178c5d0fc1e72e80a5d92c85b8f5a1979`.
The verification-policy tree digest is unchanged.

The path-and-byte digest construction is unchanged.

## Validation

Commit proposed changes before running the canonical gate, which checks the
destination repository for tracked and unignored changes before and after
validation. Install the exact Python, uv, and OPA versions in
root [`toolchain/versions.env`](../../toolchain/versions.env), then run from the destination
root:

```sh
./policy-sources/verification-policy/scripts/validate-verification-policy.sh
```

The gate consumes the co-located `tooling/`, `policy-sources/control-library/`,
and `policy-sources/verification-policy/` roots from the same committed destination
revision. It exports those committed objects into a temporary non-Git directory,
synchronizes only tooling's frozen environment, and removes all temporary output.
It never consumes local working-file edits, acquires a sibling repository, or
discovers an implicit policy tree. The resource validator receives the
`control-library` and `verification-policy` roots explicitly, without project
configuration, inventory, or assignments.

Coverage retained by the verification-policy component gate:

- all sixteen owned policy resources and their reusable schema, control,
  parameter, requirement, realization, inheritance, and Rego entrypoint
  references;
- rejection of copied reusable controls, schemas, and Rego, including local
  negative fixtures constructed from this repository's resources;
- baseline/overlay lineage and retained technical-control conflict behavior;
- deterministic realization selection plus evidence-derived pass, fail, and
  unknown objective roll-up;
- deterministic policy-tree identity, location and source-order invariance,
  identical-only cross-source coalescing, and fail-closed divergent resources;
- rejection of invalid schemas, control parameters, missing references, and
  digest mismatch; and
- owning-repository cleanliness and temporary-output cleanup.

Project-by-project behavior, deliberate conflict outcomes, and the complete
CLI/domain feature suite belong to the canonical
`verification/scenarios/` gate in this repository. The full tooling unit suite
belongs to tooling. Component validation does not invoke these suites. Candidate
changes are verified from the exact destination revision; there is no separate
scenario pin or persistent integration manifest to advance.

Destination CI runs the gate in `component-validation` after repository, tooling,
and control-library checks. Its single ordinary read-only checkout does not persist
credentials. No App token, PAT, sibling clone, or explicit historical repository
checkout is used.

## Source-only lifecycle

Verification policy has no current independent version, release cadence,
archive producer, tag validator, or hosted publisher. Consumers select an exact
development composition and record the actual `policies/` content digest.
Historical Git tags, GitHub Releases, manifests, archives, and checksums remain
immutable in `packetlss-labs/compliance-verification-policy`, but they are not
current runtime or validation dependencies and are not republished here.
