# Alder Forge DEFSTAN/DCC Level 3 reference slice

This is a fictional, representative and non-authoritative project for **Alder Forge Defence Systems Ltd**. It exercises a small current-capability slice of the repository's Inventory → Coverage → Assessment workflow. It is not a DCC submission, certificate, assurance opinion, assessment of the correct Cyber Risk Profile, legal-entity population determination, contract-applicability determination, or a claim of DEFSTAN conformity or DCC Level 3 compliance.

An outcome means only: the exact Alder Forge project check passed, failed or was unknown for the supplied subject and frozen evidence at the stated time, and has the shown DEFSTAN mapping. Mappings are traceability context; they do not select policy or establish a regulatory conclusion. Real assessor sufficiency, scope, acceptance and continuous effectiveness remain external.

## Project ownership and sources

The project has three independent named policy inputs:

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

## Operator proof

Run from the repository root. Generated evidence, plans and results are untracked; the validation script writes all runtime output outside the project.

```sh
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml inventory validate
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage list assets
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage explain entity/alder-forge-defence-systems
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml policy validate
```

Coverage shows no assessable entity policy for the governance-only entries, the MFA
Objective, and the direct 2409 technical policy. It reads current inventory and
policy only; it does not read evidence or results. The focused project gate also runs
both `framework status` and `framework explain`, in human and JSON forms, over exact
retained history. It demonstrates:

- `1101` and `2410` as affirmative governance determinations;
- `0002`, `1202` and `2602` as not established governance accounting;
- `2201` following the pinned MFA Objective through the critical-SaaS group and
  frozen tenant to its exact Objective and passing technical outcome;
- `2409` following the pinned direct Linux policy to its exact failing technical
  outcome;
- governance attribution without an entity AssessmentResult; and
- explicit not-established governance support.

There are no waivers in this slice. In particular, no waiver is used for uncertain evidence, unknown scope or assessor judgment.

## Deferred work

This project does not add or simulate account ownership, remote-access posture, vulnerability management, logging posture, component integrity, backup/recovery, the remaining representative obligations, or the later multi-parent mission-development workstation. Those require the post-#155 architecture and capability promotion sequence.
