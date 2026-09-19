# Alder Forge DEFSTAN/DCC Level 3 reference slice

This is a fictional, representative and non-authoritative project for **Alder Forge Defence Systems Ltd**. It exercises a small current-capability slice of the repository's Inventory → Coverage → Assessment workflow. It is not a DCC submission, certificate, assurance opinion, assessment of the correct Cyber Risk Profile, legal-entity population determination, contract-applicability determination, or a claim of DEFSTAN conformity or DCC Level 3 compliance.

An outcome means only: the exact Alder Forge project check passed, failed or was unknown for the supplied subject and frozen evidence at the stated time, and has the shown DEFSTAN mapping. Mappings are traceability context; they do not select policy or establish a regulatory conclusion. Real assessor sufficiency, scope, acceptance and continuous effectiveness remain external.

## Project ownership and sources

The project has two independent named policy inputs:

```text
control-library/                              reusable existing Controls and evidence schemas
policy/corporate-platform/policies/           Alder Forge technical baseline, critical-access Objective and SaaS realization
```

The corporate-platform source is a project-private semantic root. Its order in
`compliance.yaml` carries no precedence or authority. Governance-only framework
accounting is deliberately outside policy sources.

Inventory contains factual supplied scope only: one fictional legal entity, a Linux build/administration host, a critical SaaS administration tenant, and a managed macOS developer endpoint. Labels do not encode DEFSTAN IDs, desired settings, realization selection or evidence conclusions. The macOS endpoint is intentionally unassigned in this tranche: the current Homebrew-required fact does not establish an authorised-software block-by-default property, so the project does not manufacture a macOS 2409 realization.

## Provenance and reconciliation

This project pins its mapping reading as of **2026-09-13**:

- DEFSTAN control wording: [MOD Defence Standard 05-138, Issue 4](https://www.gov.uk/government/publications/cyber-security-for-defence-suppliers-def-stan-05-138-issue-4), published 2024-05-23 and page last updated 2025-12-03.
- Working Level 3 applicability set: the current [DCC Applicant Guide (Levels 0–3)](https://iasme.co.uk/defence-cyber-certification/help-resources/) linked by IASME on 2026-09-13. It is used only as the working applicability guide, not as a framework identity or assessment input.
- Cross-framework mapping provenance: MOD's [Issue 4 mapping spreadsheet](https://www.gov.uk/government/publications/mapping-document-cyber-security-for-defence-suppliers-def-stan-05-138-issue-4), published 2024-09-09.

The #153 exploration found a discrepancy that remains explicit here: the MOD spreadsheet mechanically produces a different profile count and treats `2300` differently, whereas the working Applicant Guide reconciles the stated 144-control Level 3 corpus by excluding `2300`, `2502`, `2504` and `3101`. This project uses that 144-control reconciliation only to select this representative workload. It does not normalize the discrepancy into policy, framework identity, inventory, plan semantics or assessment results.

## Seven declared obligations

| DEFSTAN control | Alder Forge representation | Existing contract |
| --- | --- | --- |
| `0002` | CE Plus dependency accounting | governance-declared; not established |
| `1101` | Reviewed board security-direction adoption | declaration-side governance determination |
| `1202` | Periodic risk-assessment accounting | governance-declared; not established |
| `2201` | Critical-SaaS MFA Objective | evidence-assessed Objective |
| `2409` | Direct Linux authorised-package policy | direct technical policy basis |
| `2410` | Reviewed authorised-software review adoption | governance-declared; affirmative |
| `2602` | External training-basis adoption accounting | governance-declared; not established |

`0002`, `1202`, `2410` and `2602` are declaration-side governance accounting and
never produce an AssessmentResult. In particular, this project does not recreate
risk completeness, software-review workflow, training completion or personnel
population semantics in Compliance. `2602` is not established because this proving
slice does not record Governance's review and adoption of an external training basis.

The declaration at `framework-obligations/defstan-dcc-level3.yaml` is closed,
versioned project-governance state, outside `policy/` and generated output. It has its
own digest and does not change policy-source, composition, member-plan, operation,
plan, or result identity. `framework status` and `framework explain` join it only to
explicitly supplied exact retained plans/results and an operation scope witness; they
never treat mappings, current Coverage, or a latest result as framework satisfaction.
Status is the compact seven-row ledger. Explain follows each row into its exact
governance determination or assessed support.

## Operator walkthrough

Run this deterministic walkthrough from the repository root. It places every
runtime artifact in a new temporary directory; it does not write generated state
below the project. The first `scripts/dev cli` call prepares the repository-managed
`.dev/venv`, whose Python runs the existing mock collector.

```sh
alder_run="$(mktemp -d "${TMPDIR:-/tmp}/compliance-alder-forge.XXXXXX")"
alder_config=projects/alder-forge-dcc-level3/compliance.yaml
alder_at=2026-09-01T00:00:00Z

scripts/dev cli --config "$alder_config" inventory validate
scripts/dev cli --config "$alder_config" coverage list assets
scripts/dev cli --config "$alder_config" \
  coverage explain entity/alder-forge-defence-systems
scripts/dev cli --config "$alder_config" \
  coverage explain host/alder-build-01
scripts/dev cli --config "$alder_config" \
  coverage explain saas/alder-admin-tenant

.dev/venv/bin/python tooling/collectors/mock-api/collect.py \
  projects/alder-forge-dcc-level3/fixtures/technical \
  "$alder_run/evidence" --collected-at "$alder_at"

scripts/dev cli --config "$alder_config" assessment run \
  --group alder-forge-legal-entity \
  --group corporate-linux-build-systems \
  --group critical-saas-administration \
  --evidence "$alder_run/evidence" \
  --plan-output "$alder_run/plans" \
  --output "$alder_run/results" \
  --at "$alder_at"

alder_anchor="$alder_run/plans/entity__alder-forge-defence-systems.json"
scripts/dev cli --no-config assessment status \
  --plan "$alder_anchor" --assessed-plans "$alder_run/plans" \
  --results "$alder_run/results" --at "$alder_at" --as-of "$alder_at"
scripts/dev cli --no-config assessment mappings \
  --plan "$alder_anchor" --assessed-plans "$alder_run/plans" \
  --results "$alder_run/results" --at "$alder_at" --as-of "$alder_at"

scripts/dev cli --no-config framework status \
  alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --declarations projects/alder-forge-dcc-level3/framework-obligations \
  --plan "$alder_anchor" --assessed-plans "$alder_run/plans" \
  --results "$alder_run/results" --at "$alder_at" --as-of "$alder_at"
scripts/dev cli --no-config framework explain \
  alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --declarations projects/alder-forge-dcc-level3/framework-obligations \
  --plan "$alder_anchor" --assessed-plans "$alder_run/plans" \
  --results "$alder_run/results" --at "$alder_at" --as-of "$alder_at"
```

Current Coverage shows no assessable entity policy for the governance-only
entries, one direct Linux check, and one SaaS Objective/check. It reads current
inventory and policy only; it does not read evidence or results. The single frozen
operation then shows the entity as `NOT REQUIRED`, the Linux member as `FAIL`, and
the SaaS member as `PASS`. Mappings connect DEFSTAN `2201` to the exact Objective
PASS and `2409` to the exact direct technical FAIL.

`framework status` is intentionally the concise seven-row ledger;
`framework explain` is the drill-down into the exact declared governance or
retained technical support. Together they demonstrate:

- `1101` and `2410` as affirmative governance determinations;
- `0002`, `1202` and `2602` as not established governance accounting;
- `2201` following the pinned MFA Objective through the critical-SaaS group and
  frozen tenant to its exact Objective and passing technical outcome;
- `2409` following the pinned direct Linux policy to its exact failing technical
  outcome;
- governance attribution without an entity AssessmentResult; and
- explicit not-established governance support.

There are no waivers in this slice. In particular, no waiver is used for uncertain evidence, unknown scope or assessor judgment.

The focused Alder validator remains the primary executable owner of these
semantics. This walkthrough is the operator path through that existing behavior,
not a second assertion suite.

## Deferred work

This project does not add or simulate account ownership, remote-access posture, vulnerability management, logging posture, component integrity, backup/recovery, the remaining representative obligations, or the later multi-parent mission-development workstation. Those require the post-#155 architecture and capability promotion sequence.
