# Derived-read browser falsification

This directory is one deliberately isolated external read-only browser consumer.
Open `index.html` and select JSON files emitted by the documented `compliance`
commands. The page has no build step, package dependency, Python import, network
client, storage, or service. It accepts only the explicit purpose-specific response
schemas listed in `app.js`; raw Inventory resources, assessment plans, assessment
results, Evidence documents, and policy sources are rejected.

The supported local boundary is therefore:

```text
explicit inputs -> compliance owner -> purpose-specific JSON response -> file picker -> browser
```

The browser may filter, sort, navigate, and format response rows. It does not join
raw artifacts, select Evidence, resolve policy, calculate qualification, recompute
outcomes/roll-ups, infer framework satisfaction, or choose a latest result. The CLI
text renderer and browser both consume the same JSON projection; neither browser
code nor a browser-specific semantic payload exists.

## Reproducible walkthrough

Use synthetic project inputs and a disposable response directory. Generated plans,
results, Evidence, and response captures remain untracked. From the repository
root, this exact command runs the semantic anchor assertions at assessment instant
`2026-09-01T00:00:00Z` and writes the browser responses outside the repository:

```sh
read_responses="$(mktemp -d "${TMPDIR:-/tmp}/compliance-read-browser.XXXXXX")"
(
  cd tooling
  uv run --frozen python \
    ../verification/scenarios/scripts/assert-semantic-anchors.py \
    --integration-root .. \
    --private-source ../verification/fixtures/iam-private-boundary/policy \
    --browser-output "$read_responses"
)
node tooling/examples/read-browser/test-app.cjs "$read_responses"/*.json
python3 -m http.server 8765 --directory tooling/examples/read-browser
```

Open `http://127.0.0.1:8765`, choose every JSON file in `$read_responses`, and
exercise response navigation, text filtering, and label sorting. The generated
captures and asserted observations are:

| Capture | Assertion/observation |
|---|---|
| `00`, `01` | Inventory exposes an intentional field set; current Coverage retains invalid, unassigned, inactive, non-assessable, and result-required classes. |
| `02`, `02a` | Direct technical policy has no synthetic Objective; exact Evidence enrichment is optional and history remains useful without Evidence bytes. |
| `03`, `03a`, `03b`, `03c` | PASS, FAIL, selection-related UNKNOWN, and ERROR remain distinct. |
| `04`, `04a` | `asset -> policy -> Objective -> Check -> required Evidence -> result`; criterion-inconclusive UNKNOWN has selected Evidence and is distinct from selection UNKNOWN. |
| `05` | Historical WAIVED remains immutable while current waiver qualification is expired. |
| `06`, `07` | The same PASS outcomes survive a query-instant change from `2026-09-01T00:00:00Z` to `2026-09-03T00:00:01Z`; only qualification changes. |
| `08` | Mapping rows are traceability facts and explicitly disclaim framework satisfaction. |
| `09` | The expected slot remains missing while caller-trusted refusal information is shown separately. |
| `10` | Overlapping group rows do not inflate the two-member frozen denominator; incomplete accounting remains visible. |
| `11` | Effective-policy changes and surrounding operation context stay in the policy-diff owner's response. |

The browser rejects a raw plan, result, Evidence document, Inventory resource, or
unknown response schema if one is included in the same file selection.

Framework interpretation has its own exact declaration input and is intentionally
not manufactured by the Assessment anchor. To add the maintained framework
exercise to the same disposable response directory, follow the exact Alder Forge
setup in `projects/alder-forge-dcc-level3/README.md`, then append `--format json`
and redirect its `assessment mappings`, `framework status`, and `framework explain`
commands into `$read_responses`. Loading them side-by-side demonstrates that the
mapping response does not become framework satisfaction; the framework response
is derived only by the framework owner from its exact declaration and validated
Assessment context.

External refusal query input is intentionally not a core artifact. It is a caller-
trusted JSON object exact-bound to the operation and assessment instant:

```json
{
  "operation_id": "sha256:<exact operation>",
  "assessment_instant": "2026-09-01T00:00:00Z",
  "refusals": [{
    "asset_id": "host/B",
    "authority": "synthetic-orchestrator",
    "reference": "attempt/example-1",
    "reason": "Shared result publication prerequisites were not established."
  }]
}
```

The response keeps the expected slot missing and presents this information in a
separate `external_orchestration` section. Absence alone never becomes refusal.

## Findings and remaining friction

- Ordinary JSON plus the file boundary is sufficient; a service, SDK, storage
  layer, and generic query protocol were not justified.
- A useful browser needs several purpose-specific responses rather than one
  universal report. Exact input paths and instants are intentionally verbose.
- Historical Assessment works without current Inventory, current policy, or
  retained Evidence bytes. Optional collector display requires an exact Evidence
  ID+digest match and exposes only selected collector ID/version fields.
- Framework satisfaction and mapping traceability remain separate views with
  different owners and claims. Policy comparison remains a policy-diff response.
- Response schemas remain experimental; this exercise creates no compatibility or
  hosted-service commitment.
