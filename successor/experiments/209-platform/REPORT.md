# #209 experiment evidence and recommendation

Status: disposable Phase B candidate; no platform/operating contract is promoted.
Target is `successor`; starting base is
`fa49127ec30675a47486dd9f5d1e1485e4032fd4` (human-merged Phase A #215).
The PR records the exact candidate head, CI URLs and independent review rather than
putting a self-referential commit ID inside that commit. Native macOS and exact-head
CI evidence must be read from that PR; local Linux results alone do not establish it.

## Evidence/limitation matrix

All test names refer to `experiment_test.go`; the CLI uses the same application
owners as these tests. Fresh JSON inputs are in `fixtures/input/`. No legacy fixture,
module, CLI, schema or whole-output oracle is consumed.

| Story | Executable owner and observed local behavior | Limit / interpretation |
| --- | --- | --- |
| 1 | `TestStories1And2PersonaTrust`: standard/container pass with fresh matching observations; forwarding 0 -> 1 reason/approval retained; ASLR/audit/runtime plus independent backup assessed. | No claim of unmodified benchmark conformity; retained selected policy IDs/revisions, source attribution and changes describe the adopted variant. |
| 2 | Same test: contradictory standard/container assignment refuses; observed runtime does not select persona; uncovered Z remains visible. `TestConservativeObjectiveAndParameterOnly` exercises a diamond group DAG without duplicating checks. | Governed inputs are trusted, not authenticated; no claim of external fleet completeness. |
| 3 | `TestStory3WaiverAndExclusionHistory`: E visibly excluded; audit WAIVED with underlying FAIL at T1; fresh T2 FAIL after expiry; retained T1 unchanged. Missing, invalid and execution-error evidence cannot be waived. | Approval references are governance attribution, not authentication; waiver window is half-open. |
| 4 | `TestStories4And5ObjectivesParameters`: all central/group/audit children evaluated, grouping retained, failing child prevents Objective success; zero/nonimplementation gaps, N/A, multiple realization refusal, missing/unexpected child rejection. Conservative/all-N/A/gap tests also run. | Sufficiency of the three Checks for Objective prose is authored review, never mechanically proved. |
| 5 | Same test: 3600-second freshness fans out; explicit complete software replacement; missing value, wrong type, absent target, stale parent revision/expected value and stale final interface refuse before evaluation. | Narrow typed subset; arrays retain order, no set-union engine, defaults, general expressions or content pins. |
| 6 | `TestStory6EvidenceAndRefusal`: real Rego PASS/FAIL; missing/stale/invalid/ambiguous UNKNOWN; reordered complete duplicates unchanged; execution/malformed ERROR, inconclusive UNKNOWN; conflicting observation ID and cancelled shared prerequisite refuse. | Candidate observation IDs and qualification diagnostics retained; selected complete facts inline. Rejected candidate payloads are not retained. |
| 7 | `TestStories7And8Records`: three recorded slots retain missing member; foreign operation/plan, wrong subject, conflicting duplicates and truncated children fail admission. | IDs are ordinary random references. A coherent coordinated rewrite cannot be detected. |
| 8 | Same test: retained read/explain, missing selected evidence and waiver basis rejected; synced exclusive publication, byte-identical retry, overwrite refusal and interrupted publication. `package_probe.py` deletes all current inputs before repeated explanation. | No derivation replay or current qualification. Single-document publication is intentionally simple; missing-member views never manufacture success. |
| 9 | `package_probe.py`: copied-subtree native build, external independently named sources/private realization, packaged assessment/history outside checkout; network and checkout unavailable. Linux locally observed; native macOS executes in CI. | Synthetic access separation only. macOS is native evidence only when its real job succeeds; cross-compilation is not evidence. |

Additional boundary probes: `TestAdmissionMutationAndIsolation`,
`TestAdmissionModuleSchemaMutationsAndFileBounds`, `TestTypedJSON`,
`TestUnicodeValueBoundary`, `TestSourceOrderAndConflicts`, and
`TestEvaluatorBoundaryAndCancellation`. They test cooperative writer exclusion,
in-flight inventory/evidence/module/schema change diagnostics, after-admission
isolation, symlink/size refusal, exact typed equality, duplicate-member refusal,
forbidden HTTP/DNS/time/random/UUID builtins, pre-cancellation and deadline
interruption of a synthetic cross product. These are asserted failures, not
placeholder successes.

## Proposed operating answers (experimental)

1. **Admission:** a shared lock spanning the complete operation acquisition works
   for a controlled local writer population; memory copies remain independent after
   release. Both a writer already holding the exclusive lock and a writer trying
   during admission are excluded. In-flight lock-ignoring writes observed by the
   diagnostic reread refuse, but transient/ABA changes or a coherently rewritten
   set may escape detection. This is an environmental precondition, not a security
   claim. Prefer externally frozen/read-only snapshots where all writers cannot
   follow one lock discipline. Atomic envelope publication is another viable
   alternative; it shifts consistency responsibility to the producer. Do not
   promote the cooperative protocol as universal input safety.
2. **Evidence:** inline selected observation IDs, collector/subject/time/facts and
   per-candidate qualification reasons suffice for this slice's exact evaluation
   use and retained diagnostic attribution. Collector IDs alone do not. Missing
   selected facts reject the retained record. Explicitly supplied frozen evidence
   records could reduce duplication and enable independent access control, but
   their loss would make dependent explanation unavailable; they need a separately
   promoted join/admission contract. The prototype intentionally has no external
   evidence lookup. Inline full facts expose more information to record readers;
   rejected payloads are omitted, so inspecting their exact invalid bytes is not
   supported. Recommend a reviewed minimum diagnostic projection and privacy
   analysis before production, retaining exact facts actually consumed.
3. **Records/publication:** random operation/plan/result IDs with exact explicit
   membership and references are sufficient ordinary references under faithful
   retention. Admit exact duplicates, reject conflicting IDs/slots/child sets and
   foreign references. Atomically publish the complete supplied document via synced
   temp file plus exclusive hard link; exact-byte retries succeed and different
   content never overwrites the same name. Before-link interruption leaves no public
   document. After-link interruption can leave a complete document; a safe retry
   admits those exact bytes. Filesystem crash durability, disk failure after link,
   and cross-filesystem publication remain environmental constraints, not tested
   power-loss guarantees. Previously published documents remain independently usable.
   Missing members are retained in the denominator; there is no atomic fleet-wide
   transaction or database. Recommend this simple local protocol only if the
   accepted operating environment supports its filesystem primitives.
4. **Authoring/value:** strict small JSON plus typed revision/expected-value guards
   is sufficient for the demonstrated inputs without JCS. Recommend specifying
   numeric domain, string/array semantics and timestamp syntax before broadening
   authoring formats. This prototype rejects fractional/exponent numbers and YAML,
   including YAML aliases/tags/duplicates, rather than inheriting their semantics.
   It rejects Unicode replacement ambiguities. Whole-array replacement intentionally
   differs from automatic union. Revision labels/expected values protect against
   demonstrated stale edits, not coordinated same-revision content changes.

## Evaluator and platform assessment

OPA sees only admitted module text, resolved desired values and qualified observation
facts. Go owns applicability, Objective selection, freshness/schema qualification,
ambiguity, waiver interpretation, statuses and publication. `Explain` validates and
joins retained records only, with no resolver/evaluator/current-input or clock call.
There is no remote OPA SDK/management, bundle store, plugin or second policy language.
A positive builtin allowlist prevents newly added OPA builtins from silently granting
network/time/random capabilities. Safe generic error diagnostics avoid exposing
arbitrary evaluator internals. Compiled queries are operation/check-local; there is
no global cache or later module/schema file loading.

The 100 ms deadline interrupts the measured expensive query, and source/count/size
limits bound ordinary admitted inputs. The Go OPA parser/compiler and evaluator
share the application process and heap. A context deadline is not a hard memory
limit or reliable recovery from OOM/native/runtime faults. No adversarial-policy
sandbox claim is supported. Production allowing hostile policy or requiring hard
per-criterion memory isolation would need a process boundary or another explicitly
reviewed containment design. The CLI can refuse a cancelled shared prerequisite;
attributable criterion failure remains ERROR and cannot become PASS or WAIVED.

**Recommendation:** Go with narrow embedded OPA is a viable candidate for this
trusted local snapshot workload, subject to promotion of the four operating
contracts and the explicit containment limit. Native packaged evidence and review
are necessary before accepting that recommendation. Dependency cost is substantial
for a small app; do not infer that a single executable means a small trusted codebase.
A clean Python application plus external evaluator would add interpreter/OPA
packaging and IPC, while providing a killable evaluator process and easier hard
resource limits. **An executable Python comparator is not materially needed for
this bounded trusted-policy experiment:** no unresolved observed behavior here
requires a language comparison. If hard evaluator containment becomes a product
requirement, compare process designs explicitly; do not assume Python itself is
the isolation mechanism. No comparative performance claim is made.

**Code disposition:** discard the prototype as a production implementation. The
fresh acceptance vectors, failure taxonomy, narrow evaluator-boundary probes and
packaging-isolation harness are candidates for separate review/promotion after
architecture decisions. Do not promote exported Go structs, CLI grammar, lock/file
layout, JSON subset or record shape implicitly. The prototype retains more plan
material (including criterion module/schema text) than explanation alone needs;
production should review a smaller retained projection. Test success is not API
freeze, migration authorization, catalog coverage or cutover evidence.

## Versions, reproduction and measurements

Pinned Go **1.27.1**, OPA **v1.21.0**, with the exact indirect dependency versions and
checksums in `go.mod`/`go.sum`. Selected against current official
[Go downloads](https://go.dev/dl/), [OPA release v1.21.0](https://github.com/open-policy-agent/opa/releases/tag/v1.21.0)
and [OPA embedding guidance](https://www.openpolicyagent.org/docs/integration).
`go mod verify`, `go vet`, `go test -race -count=1` run through `check.sh core`.
The resolved module graph reports 124 entries including the experiment; the binary
package closure reports 394 packages including the Go standard library. Transitive
OPA test/tool dependencies in the module graph are not all linked into the binary.
`go version -m` in each package job reports the actual linked dependency versions.
CGO is disabled for the package build; build flags are `-trimpath -ldflags='-s -w'`.
The host packaging harness uses Python 3 standard library (local version 3.13.5),
with no Python runtime dependency in the binary.

Local Linux environment: x86_64, kernel 6.12.107+deb13-cloud-amd64, glibc 2.41;
Go-produced static executable under a new network namespace/chroot. Run
`bash check.sh package` for current byte sizes and five-sample wall-time medians.
Measured numbers for the committed candidate are recorded below before review;
CI logs supply independent Linux/native macOS measurements. Wall times include
process/isolation-wrapper startup, use a warm filesystem and are not evaluator-only
latency or statistically robust platform comparisons. No peak-memory claim is made.

Local validation: focused/race tests and vet; real packaged Linux assessment/history;
repository standard-library/foundation checks and `git diff --check`. Exact-head CI,
native macOS, fresh-context independent review and any required current-successor
integration evidence are recorded in the PR. Before merge, the administrator must
require all three real experiment contexts from their observed GitHub Actions source,
preserving `successor-foundation`. No ruleset is changed by this experiment.

Local measured run (2026-09-26): executable **23,380,128 bytes**; gzip package
**7,279,579 bytes**; representative retained document **39,676 bytes**. Five-sample
medians: startup/usage **4.77 ms**, assessment **8.00 ms**, explanation **6.54 ms**.
The cancellation test interrupted its expensive cross product at approximately
100 ms (the configured cooperative deadline). Gzip container timestamps can change
archive bytes/size between runs; no reproducible-binary or content-identity claim
is made. Exact timings and platform details print on each run.


Independent first-review findings were implementation-local: nondeterministic loss
of coalesced change attribution, inconsistent duplicate waiver handling, observation
ID conflicts escaping across outcomes, and mismatched retained Objective references.
`TestReviewDeterministicTailoringAndWaiverIdentity` and
`TestReviewRetainedObservationAndObjectiveReferences` reproduce these cases and now
assert deterministic complete attribution, same-ID coalescence/conflict refusal,
record-wide observation identity and exact realization/Objective relationships.
The PR records re-review on the final head; the first review is not final-head evidence.
