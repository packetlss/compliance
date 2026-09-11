# IAM private-boundary fixture

This retained synthetic project demonstrates how a shared high-level
requirement is realized by an independently materialized environment-private
technical realization and rolled up to a requirement-baseline result. It is
not a claim about a real environment or regulatory framework.

```text
company.identity-access-objectives@1
└── company.iam.role-based-access@1
    ├── company.linux.central-role-access@1
    └── restricted.linux.central-role-access@1
        └── based_on company realization for provenance only
```

The project composes exactly three named policy sources. `control-library`
supplies evidence/parameter schemas and reusable controls; `verification-policy` supplies the
synthetic requirement, requirement baseline, and ordinary company
realization; and `environment-private` supplies this fixture's retained
restricted realization and fictitious parameters. The restricted resource has
no runnable copy in either central policy source and inherits no content from
the ordinary realization.

The realization carries no semantic information-classification field. Its
need-to-know boundary is demonstrated by independent physical materialization,
source ownership, and access/deployment controls rather than an assessment-plan
label.

Although the source snapshot is co-located, its checked-in `policy/` subtree is
not an execution input. The focused validation gate exports committed inputs
into a temporary non-Git assembly, verifies the relocated policy digest against
the committed source input, copies
the subtree into a separate `external-sources/environment-private/` root,
removes the fixture-side copy from the execution assembly, and composes only
the separate materialization. The committed, relocated, and materialized policy
trees must have equal content identity; the current tree's particular digest is
not an independent normative vector.

The inventory contains `host/restricted-linux-01`. Its trusted
`iam-profile=restricted-linux` label selects the complete restricted
realization. The assigned `company.identity-access-objectives@1` baseline
expands into four independently attributable checks using
`linux.access.setting_equals` and `linux.access.configuration/v1` evidence.

Trusted `iam-profile` labels must select exactly one realization:

```text
iam-profile=company-linux     -> company realization
iam-profile=restricted-linux  -> restricted realization
missing or overlapping match -> not implemented or invalid, never precedence
```

The synthetic observation deliberately reports
`ssh.allowed_groups=["local-operators"]` instead of the approved
`linux-production-operators` group. The preserved expected result is three
technical passes, one technical failure, a failing IAM requirement, and a
failing top requirement baseline. The generated assessment plan retains all
three source identities, the selected environment-private realization, and the
resolved control fields required by an external adapter.

The fixture uses `project-config/v1alpha3` with tooling-owned inventory and
assignment schemas and generates assessment plan/results v4. Validation checks
actual planning and evaluation tooling/source composition, exact evaluator bytes,
the complete subject evidence snapshot, and successful evidence selections bound
to the assessed plan's requirements and collection instant (ADR 0011 facts only).
It also retains one physical relocation/source-reorder relation and refuses
changed private content against the original plan. Focused tooling tests own
realization-selection order and the detailed evidence failure taxonomy.

Run from the destination root after committing the candidate revision:

```sh
bash scripts/validate-iam-private-boundary.sh
```

Generated evidence, plans, and results are temporary and
must not be committed. Real private inventories, realizations, evidence,
parameters, credentials, provider state, and operational data remain in their
separate authorized environments.

The additional `company-iam-policy-assessment` realization belongs to the canonical
two-host IAM scenario. It remains in this separately materialized private root and
introduces a named shared IAM dependency plus an attributable consumer relationship.
The original restricted Linux scenario and its four checks remain unchanged.
