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

## Seven declared obligations

| DEFSTAN control | Alder Forge representation | Existing contract |
| --- | --- | --- |
| `0002` | External CE Plus judgment/dependency | external judgment; intentionally not established |
| `1101` | Reviewed board security-direction adoption | declaration-side governance determination |
| `1202` | Reviewed risk-assessment adoption plus bounded Objective assertion | mixed governance + assessed Objective |
| `2201` | Critical-SaaS MFA Objective | evidence-assessed Objective |
| `2409` | Direct Linux authorised-package policy | direct technical policy basis |
| `2410` | Reviewed authorised-software review plus bounded Objective assertion | mixed governance + assessed Objective |
| `2602` | Reviewed awareness adoption plus bounded Objective assertion | mixed governance + assessed Objective |

`1202`, `2410` and `2602` deliberately do not invent records, histories, population tables, completion tables or arbitrary assertion properties. Each assertion provides only the existing attributable beneficiary, source locator, scheme, outcome and validity interval. A `negative` awareness assertion can truthfully report the bounded supplied training check as failed; it does not prove complete personnel population coverage. The `inconclusive` risk snapshot becomes `unknown`, never `pass`.

The declaration at `framework-obligations/defstan-dcc-level3.yaml` is closed,
versioned project-governance state, outside `policy/` and generated output. It has its
own digest and does not change policy-source, composition, member-plan, operation,
plan, or result identity. `framework status` joins it only to explicitly supplied
exact retained plans/results and an operation scope witness; it never treats mappings,
current Coverage, or a latest result as framework satisfaction.

## Operator proof

Run from the repository root. Generated evidence, plans and results are untracked; the validation script writes all runtime output outside the project.

```sh
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml inventory validate
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage list assets
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml coverage explain entity/alder-forge-defence-systems
scripts/dev cli --config projects/alder-forge-dcc-level3/compliance.yaml policy validate
```

Coverage shows the retained three assessed organisational paths and the MFA path as
Objectives/Realizations; only 2409 remains direct technical policy. It reads current
inventory and policy only; it does not read evidence or results. The focused project
gate also runs `framework status` over exact retained history. It demonstrates:

- `1101` as a reviewed governance determination and `0002` as unresolved external judgment;
- `1202` unknown from an attributable inconclusive assertion;
- `2602` and `2409` failing from a negative bounded assertion and an unexpected Linux package;
- entity, Linux and SaaS results retaining only their own applicable Objectives or direct checks; and
- historical explanation retaining the frozen reason, source-backed evidence, policy-source attribution and mapping context without treating an assertion as a direct package/MFA check.

There are no waivers in this slice. In particular, no waiver is used for uncertain evidence, unknown scope or assessor judgment.

## Deferred work

This project does not add or simulate account ownership, remote-access posture, vulnerability management, logging posture, component integrity, backup/recovery, the remaining representative obligations, or the later multi-parent mission-development workstation. Those require the post-#155 architecture and capability promotion sequence.
