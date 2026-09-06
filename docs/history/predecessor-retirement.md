# ADR 0007 predecessor retirement (#33)

Base: `9d2e65889c20e41fc1c9e899a7009947bda3f0d5`. Dependencies #31, #32 and consumer
cutovers #34–#36 were complete before retirement. No external compatibility
consumer or explicit freeze was found.

## Inventory and disposition

| Predecessor support found | Disposition |
| --- | --- |
| Project-config v1alpha1/v1alpha2 schema files, config defaults, loading branches, authored schema paths | Deleted; sole config is v1alpha3 |
| Release-lock v1alpha2 schema, model, loader, digest, validation/formatting, `release show/validate` | Deleted; composition-lock v1alpha1 remains the expected-composition boundary |
| Assessment plan/results v1 and v3 schemas, construction, readers, v3 digest/provenance helpers | Deleted; v4 constructs and validates directly |
| `locked_artifacts.py` runtime monkeypatch dispatch, `artifact_provenance.py`, `assessment_v4.py` wrapping v1 construction, v4-to-v1 validation projection | Deleted; selected config is passed directly to native planning and evaluation |
| Old evidence loading/freshness/validation helpers used only by the predecessor evaluator | Deleted; current snapshot and selection implementation remains |
| Generic policy-source `release_lock_policy_source` projection and imports from the deleted lock module | Deleted; descriptor semantic identity and successor content composition remain |
| Three release-lock/locked-artifact compatibility test suites | Deleted |
| Remaining v1 tooling feature fixture, config and domain-test builders | Retired v1 construction and authored schema override; retained domain coverage constructs v1alpha3/v4 directly |
| Package inventory and standalone/locked/policy-release shell proofs | Removed predecessor positive assertions; test exact wheel receipts and successor locks/assessments |
| Current operator, provenance, config, release, architecture and maturity documentation | Updated to sole successor support |

Search covered tracked Python, schemas, package metadata, shell validation, tests,
fixtures, projects, verification and documentation. Maintained destination configs
are v1alpha3; no positive fixture or reader accepts the retired artifact families.
Unversioned internal domain helpers remain only where used by current contracts.
The single-source `--no-config --policies` input still supplies a named semantic
root and produces v4; it is not an old artifact reader. This tranche preserved the
then-current optional-evidence behavior; ADR 0010 and #84 subsequently removed
that behavior from the accepted successor model.

## Remaining references

- `docs/adr/0007-*` and `0009-*`: accepted migration sequence and temporary lock
  context at decision time; historical sequencing is not a reader obligation.
- `tooling/docs/adr/2026-08-29-locked-generated-artifact-provenance.md` and
  `2026-08-30-content-addressed-provenance-vnext.md`: original provenance decisions,
  including historical schema names, identity projections and reproduction rules.
- `tooling/docs/architecture.md` decision log: dated implementation/migration
  records preserve what was supported then. The new #33 entry records retirement.
- `docs/history/pre-consolidation.md`: source cutover preserved the then-current
  contracts; it is acquisition/migration provenance, not current runtime guidance.
- Current maturity/provenance/release documentation: explicit historical/removed
  sections explain refusal and reproduction using historical tooling.
- `test_predecessor_retirement.py` and the package's removed-resource inventory:
  negative assertions prove discriminator rejection and absence of retired schemas.
  They are enforcement of retirement, not positive compatibility fixtures.

Current digest algorithms, domain outcomes, actual planning/evaluation composition,
evaluator identity, complete evidence snapshots and factual successful selections
are preserved. Runtime requires neither Git nor access to historical repositories.
Historical Git, releases, wheels and generated artifacts are unchanged and require
their corresponding historical tooling for reproduction.
