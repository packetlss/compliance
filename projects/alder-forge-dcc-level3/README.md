# Alder Forge DEFSTAN/DCC Level 3 reference slice

This is a fictional, representative and non-authoritative project for **Alder Forge Defence Systems Ltd**. It exercises a small current-capability slice of the repository's Inventory → Coverage → Assessment workflow. It is not a DCC submission, certificate, assurance opinion, assessment of the correct Cyber Risk Profile, legal-entity population determination, contract-applicability determination, or a claim of DEFSTAN conformity or DCC Level 3 compliance.

An outcome means only: the exact Alder Forge project check passed, failed or was unknown for the supplied subject and frozen evidence at the stated time, and has the shown DEFSTAN mapping. Mappings are traceability context; they do not select policy or establish a regulatory conclusion. Real assessor sufficiency, scope, acceptance and continuous effectiveness remain external.

## Project ownership and sources

The project has three independent named policy inputs:

```text
control-library/                              reusable existing Controls and evidence schemas
policy/programme/policies/                    Alder Forge interpretations, objectives and assertion policy
policy/corporate-platform/policies/           Alder Forge technical baseline, critical-access Objective and SaaS realization
```

The latter two are project-private semantic roots. Their order in `compliance.yaml` carries no precedence or authority. There is deliberately no empty secure-engineering source: that ownership boundary is deferred with the later programme work.

Inventory contains factual supplied scope only: one fictional legal entity, a Linux build/administration host, a critical SaaS administration tenant, and a managed macOS developer endpoint. Labels do not encode DEFSTAN IDs, desired settings, realization selection or evidence conclusions. The macOS endpoint is intentionally unassigned in this tranche: the current Homebrew-required fact does not establish an authorised-software block-by-default property, so the project does not manufacture a macOS 2409 realization.

## Provenance and reconciliation

This project pins its mapping reading as of **2026-09-13**:

- DEFSTAN control wording: [MOD Defence Standard 05-138, Issue 4](https://www.gov.uk/government/publications/cyber-security-for-defence-suppliers-def-stan-05-138-issue-4), published 2024-05-23 and page last updated 2025-12-03.
- Working Level 3 applicability set: the current [DCC Applicant Guide (Levels 0–3)](https://iasme.co.uk/defence-cyber-certification/help-resources/) linked by IASME on 2026-09-13. It is used only as the working applicability guide, not as a framework identity or assessment input.
- Cross-framework mapping provenance: MOD's [Issue 4 mapping spreadsheet](https://www.gov.uk/government/publications/mapping-document-cyber-security-for-defence-suppliers-def-stan-05-138-issue-4), published 2024-09-09.

The #153 exploration found a discrepancy that remains explicit here: the MOD spreadsheet mechanically produces a different profile count and treats `2300` differently, whereas the working Applicant Guide reconciles the stated 144-control Level 3 corpus by excluding `2300`, `2502`, `2504` and `3101`. This project uses that 144-control reconciliation only to select this representative workload. It does not normalize the discrepancy into policy, framework identity, inventory, plan semantics or assessment results.

## Seven mapped checks

| DEFSTAN control | Alder Forge representation | Existing contract |
| --- | --- | --- |
| `0002` | Entity Objective with one CE Plus scope assertion realization | `organization.assertion.required` + `organization.assertion/v1` |
| `1101` | Entity-scoped board-direction Objective and one complete assertion realization | same assertion contract |
| `1202` | Entity Objective with one bounded risk-assessment assertion realization | same assertion contract |
| `2201` | Technology-neutral MFA Objective with one critical-SaaS realization | `saas.tenant.setting-equals` + `saas.tenant.configuration/v1` |
| `2409` | Direct Linux authorised-package policy | `linux.packages.only-allowed` + `linux.packages/v1` |
| `2410` | Entity Objective with one bounded authorised-software-list review assertion realization, separate from package state | assertion contract |
| `2602` | Entity Objective with one bounded annual awareness assertion realization | assertion contract |

`1202`, `2410` and `2602` deliberately do not invent records, histories, population tables, completion tables or arbitrary assertion properties. Each assertion provides only the existing attributable beneficiary, source locator, scheme, outcome and validity interval. A `negative` awareness assertion can truthfully report the bounded supplied training check as failed; it does not prove complete personnel population coverage. The `inconclusive` risk snapshot becomes `unknown`, never `pass`.

The current organisation-assertion evidence contract represents one bounded entity assertion fact per supplied snapshot. A programme with several simultaneously applicable organisational Objectives therefore leaves nonmatching sibling Objectives unknown in that snapshot. This is a capability/authoring finding for post-#155 reassessment, not a programme roll-up or conformity mechanism. Each organisational fixture is an exact frozen run of the full applicable entity policy with one supplied assertion fact; it is not a run with only one applicable obligation and the separate snapshots do not constitute a combined programme result.

## Operator proof

Run from the repository root. Generated evidence, plans and results are untracked; the validation script writes all runtime output outside the project.

```sh
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml inventory validate
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage list assets
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage explain entity/alder-forge-defence-systems
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml policy validate
```

Coverage shows all five organisational paths and the MFA path as Objectives/Realizations; only 2409 remains direct technical policy. It reads current inventory and policy only; it does not read evidence or results. The focused project gate collects deterministic fixtures, performs frozen assessments and uses public `assessment explain` and `assessment mappings` views. It demonstrates:

- `0002`, `1101`, `2201` and `2410` passing in their respective exact snapshots;
- `1202` unknown from an attributable inconclusive assertion;
- `2602` and `2409` failing from a negative bounded assertion and an unexpected Linux package;
- entity, Linux and SaaS results retaining only their own applicable Objectives or direct checks; and
- historical explanation retaining the frozen reason, source-backed evidence, policy-source attribution and mapping context without treating an assertion as a direct package/MFA check.

There are no waivers in this slice. In particular, no waiver is used for uncertain evidence, unknown scope or assessor judgment.

## Deferred work

This project does not add or simulate account ownership, remote-access posture, vulnerability management, logging posture, component integrity, backup/recovery, the remaining representative obligations, or the later multi-parent mission-development workstation. Those require the post-#155 architecture and capability promotion sequence.
