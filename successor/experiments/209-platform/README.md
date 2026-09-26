# Disposable trusted-snapshot platform experiment (#209)

This is an experiment, not the successor application or a production API. Authority
is [#209](https://github.com/packetlss/compliance/issues/209),
[ADR 0025](../../../docs/adr/0025-trusted-snapshot-successor.md) and the
[target stories](../../../docs/SUCCESSOR_ARCHITECTURE.md#behavioral-acceptance-stories).
[NOTES.md](NOTES.md) records assumptions written before implementation;
[REPORT.md](REPORT.md) records evidence, tradeoffs and disposition.

Use **Go 1.27.1** and **OPA v1.21.0**. `go.mod`/`go.sum` pin the dependency graph.
No legacy Python/OPA installation is used. Build acquisition can use the network;
the resulting native executable needs no external evaluator, Git or network.
Python 3 is only the standard-library packaging test harness, not the application.

```sh
cd successor/experiments/209-platform
bash check.sh core       # module verification, vet, race-enabled focused/E2E tests
bash check.sh package    # native build, isolated assessment/history, measurements
```

The packaging command requires Linux `unshare`/`chroot` (user namespaces, or runner
passwordless sudo for namespace setup) or native macOS `sandbox-exec`. It fails if
isolation is unavailable. Linux's chroot contains only the binary and fresh synthetic
input files; macOS denies repository reads and networking. It builds from an isolated
copy of this subtree, not a legacy build root. CI uses native Linux and macOS jobs.
Every measurement prints OS/architecture, byte sizes and five-sample medians.

For a small manual walkthrough outside the checkout:

```sh
go build -mod=readonly -trimpath -o /tmp/experiment209 ./cmd/probe
work=$(mktemp -d)
cp -R fixtures/input "$work/inputs"
touch "$work/inputs/.admission.lock"
cd "$work"
/tmp/experiment209 assess inputs 2026-09-26T12:00:00Z result.json
rm -r inputs
/tmp/experiment209 explain result.json
```

`assess` succeeds when it publishes a valid attributable record, including FAIL,
UNKNOWN, ERROR or WAIVED. It exits nonzero on refusal and publishes no result.
`explain` validates the supplied retained document and prints original intent,
observations, outcomes, gaps and membership. It has no clock or input-directory
argument. These commands are experiment grammar, not a proposed CLI freeze.
Do not run the manual command against an actively changing directory: the admission
preconditions below apply even though this walkthrough uses private temporary data.

The fixture has two independent policy source files plus a separately supplied
synthetic private realization file. `S` selects standard policy; `C` selects the
container variant and company Objective. At T1, C's audit failure is WAIVED and its
allowed-group Check FAILs; independent checks still run. No real private data exists
in these fixtures. Test variants create the remaining positive/negative stories.

Input preparation owns `.admission.lock` as a persistent regular inode and obtains
an exclusive advisory lock **before any change** to inventory, sources (including
modules/schema interfaces), evidence or directory membership. It releases the lock
only after publishing a complete coherent acquisition. Readers acquire a shared lock
before opening any constituent. Never unlink/replace the lock or input root during
admission. Use a local filesystem supporting `flock`; parent directories must be
controlled. Lock-ignoring writers are outside the guarantee. See the mutation probes
and alternatives in the report; a double read is diagnostic, not snapshot proof.

The JSON subset rejects unknown/duplicate fields, null, fractions/exponents, `-0`,
out-of-range integers, malformed UTF-8 and lone escaped surrogates. Member spelling
is case-sensitive. Integers are in [-9007199254740991, 9007199254740991]. Boolean and
integer values differ; arrays are ordered; string equality does no Unicode
normalization. ParameterPolicy owns explicit declarations; consumers must match them. Supported
types are integer, boolean, string and string array. Observation interfaces are authored closed field/type maps, not a JSON Schema
implementation. Timestamps are UTC RFC3339 whole seconds ending in `Z`. YAML is
unsupported. Root and parent revision/expected-state checks do not pin exact content.

Experimental limits: 1 MiB per input/retained document, JSON depth 32, at most 128
members per JSON collection, 16 sources/subjects, 64 resolved Checks per subject,
16 KiB per Rego module, 100 ms cooperative criterion deadline and 30-day maximum
freshness. This is a bounded trusted-policy probe, not an adversarial memory sandbox.
The small limits intentionally reject workloads outside the experiment.

Retained records and binaries are execution material; keep them outside this tree.
No release, service, bundle manager, plugin, legacy adapter or production catalog is
part of this experiment.
