# Actual composition and expected enforcement

Status: implemented foundation for #31; assessment v4 emission remains #32.

[ADR 0007](../../docs/adr/0007-unified-actual-and-expected-composition-provenance.md)
and [ADR 0009](../../docs/adr/0009-active-compliance-vocabulary.md) govern this
successor. `composition-lock/v1alpha1` is the sole forward complete expected
composition. It neither acquires inputs nor supplies missing actual provenance.

## Project configuration

```yaml
# yaml-language-server: $schema=../tools/schemas/project-config-v1alpha3.schema.json
schema: compliance.example/project-config/v1alpha3
policySources:
  - name: control-library
    path: /materialized/control-library/policies
  - name: environment-private
    path: /materialized/private-policy
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
# Optional; the only accepted selection is this exact adjacent filename.
expectedComposition:
  path: compliance.lock.yaml
```

Every source has an explicit unique name and materialized path. There is no
reserved source role, implicit dependency, source precedence, `paths.policies`,
or authored `paths.resourceSchema`. Inventory and assignment validation uses
executing tooling's packaged inventory schema. Project-registry selection is
unchanged. Project and policy paths remain location metadata.

An optional source-local `expectedContent` has exactly `digestAlgorithm` and
`digest`, using `compliance.example/policy-source-tree-digest/v1alpha1` and
`sha256:<64 lowercase hex digits>`. It guards only that source. Actual content
is always calculated independently. Direct and complete expectations must
agree exactly; neither overrides the other.

The selected lock must be a regular adjacent `compliance.lock.yaml`. Alternate
filenames, absolute paths, parent traversal, and symbolic-link redirection are
refused. No lock is implicitly selected by its presence. v1alpha3 refuses
policy-source and inventory-schema runtime overrides, including argparse
abbreviations, so CLI options cannot bypass configured expectations or schema
ownership. `--no-config` continues to explicitly select predecessor no-config
execution; it does not produce a successor artifact or successor provenance.

## Canonical identity

The normalized actual composition projection has exactly these fields:

```json
{
  "tooling": {
    "source": {
      "digestAlgorithm": "compliance.example/tooling-source-tree-digest/v1alpha1",
      "digest": "sha256:<actual source digest>"
    },
    "execution": {"kind": "source"}
  },
  "policySources": [
    {
      "name": "control-library",
      "content": {
        "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
        "digest": "sha256:<actual materialized content digest>"
      }
    }
  ]
}
```

Installed execution instead has exactly
`{"kind":"installed-wheel","wheelSha256":"sha256:<actual wheel digest>"}`.
Source execution has no wheel field. Source entries sort lexically by their
explicit ASCII source names; duplicates fail. Both existing raw source-tree
digest algorithms remain unchanged. Composition normalization precedes RFC
8785/JCS UTF-8 serialization and SHA-256, returning `sha256:<hex>` with algorithm
`compliance.example/composition-digest/v1alpha1`.

Repository, Git, filesystem location, source/file order, provider, URL,
distribution/version, release/archive coordinates, descriptive metadata and
expected enforcement are absent from that projection. Names are semantic;
renaming a source changes composition without changing its content digest.
Exact-identical resource definitions alone may coalesce; existing catalog
conflict detection still refuses divergent same-identity definitions.

## Complete expected composition

A lock is a strict object with `schema`, `expected`, and optional nonsemantic
`metadata`. Its schema is `compliance.example/composition-lock/v1alpha1`.
`expected.tooling` uses the exact tooling identity shape above.
`expected.policySources` is a name-keyed map; each value has exactly `content`
in the shape above. There are no acquisition or release fields. Both source
and installed-wheel tooling expectations are supported.

For `compliance.example/composition-lock-digest/v1alpha1`, normalize the expected
map into the same sorted source array used by actual composition, then hash
JCS bytes of exactly `{"schema": <lock schema>, "expected": <projection>}`.
YAML presentation, metadata, and lock location do not participate. Duplicate
YAML keys are invalid. Fixed byte and digest vectors are in
`tests/test_composition.py`.

Enforcement compares independently observed actual composition with the entire
normalized expected projection. Missing/additional names, renamed sources,
algorithms, content digests, tooling source identity, execution kind, or exact
wheel bytes cannot match by precedence or fallback. Invalid actual provenance
is a configuration error even with no expectations. These errors never become
assessment `unknown`.

## Actual tooling and local installation receipts

Source and editable runs identify the executing module's source root and
recompute the canonical tooling tree digest on each observation. No `.git`,
installed release metadata, or expected lock fills missing source content.

Installed wheels require a local receipt next to their distribution's
`METADATA` and `RECORD`. `scripts/install-locked-wheel.py` invokes the installed
hook in isolated Python mode after installing the exact supplied local wheel.
The hook compares the wheel's SHA-256 RECORD entries with installed bytes,
including `.data/purelib` relocation, and validates installed RECORD hashes and
sizes before writing `compliance-wheel-receipt.json` and retaining the exact
wheel as `compliance-provenance.whl` in that dist-info directory.

The local receipt schema `compliance.example/tooling-wheel-receipt/v1alpha1`
contains exactly `schema`, `distribution`, `version`, `wheelSha256`, and
`installedRecordSha256`. Distribution/version bind installation evidence; they
do not enter composition identity. The receipt and retained wheel are local
installation state, not repository source or another composition artifact.

On each installed observation, tooling verifies the receipt against the
installed distribution, retained wheel SHA-256, and installed RECORD SHA-256.
It then revalidates the wheel archive's complete file set through wheel RECORD,
compares the installed payload with those exact bytes, and validates every
hash-bearing installed RECORD entry. RECORD's self entry is necessarily unhashed.
All generated Python bytecode, including hashless/unrecorded caches, is checked
against compilation of the verified wheel-owned source at its declared optimization
level. Altered executable code, invalid/trailing cache data and sourceless bytecode
are refused; cache bytes and compilation filenames remain nonsemantic. Unrecorded runtime modules/schemas,
missing files, symlinked evidence, altered payload, missing/altered receipt,
wheel or RECORD are refused. Embedded canonical source metadata is accepted
only after verifying it as part of those wheel bytes.

This is local installation integrity evidence, not signing, publisher
attestation, or protection against replacement of the interpreter/trust root.
No network, Git, acquisition resolver, or expected lock participates. A plain
installation without this receipt cannot produce successor actual provenance.
Existing predecessor installation/artifact semantics remain unchanged.

## Diagnostics and transition to #32

```sh
compliance --config ./compliance.yaml composition show --format json
compliance --config ./compliance.yaml composition validate
```

These are console-level diagnostics, alongside the existing console-level
version/release diagnostics. They create no artifact. The JSON report separates
`actual`, `compositionDigestAlgorithm`, `compositionDigest`, `enforcement`,
`valid`, and `errors`. `show` may report an expected mismatch; `validate` exits
2 for a mismatch. Missing actual identity or invalid configuration fails both.
Configuration validation enforces selected expectations as well.

The accepted #31 transition refuses v1alpha3 plan rendering and assessment
execution before any plan/result is written, explaining that generation needs
assessment v4 owned by #32. Assessment views that internally render plans are
also refused. v1alpha3 never emits v1/v3 as a bridge. Existing v1alpha1/v1alpha2,
release-lock/v1alpha2 and assessment v1/v3 readers/workflows remain until #33.
`release show/validate` retain their existing predecessor contract; they do not
alias or interpret composition locks.

#32 will consume the fresh observation/enforcement boundary before planning
and again before evaluation, persist actual planning/evaluation composition,
refuse persisted-plan policy drift, and replace transitional refusal with v4.
#31 does not add a configuration-artifact successor or change domain evidence,
assurance, waivers, adapters, or project-registry semantics.
