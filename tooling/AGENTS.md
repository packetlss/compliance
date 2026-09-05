# Tooling instructions

This root owns the unified `compliance` CLI, planner, evaluator, generic collectors, project configuration and inventory schemas, tests, packaging, and executable architecture contracts. `tooling/docs/architecture.md` is the detailed contract for tooling changes.

## Boundaries

- Collectors emit evidence and never contain desired policy.
- OPA evaluation remains off the governed subject.
- Policy and project data remain explicit inputs; do not copy production policy or project state into tooling.
- Named policy sources have independent content identity, no order precedence, identical-only coalescing, and fail-closed divergence.
- The provenance-bearing assessment plan is the external-adapter handoff. Do not add in-core backend rendering, credentials/state, apply authority, or an executable adapter/plugin runtime.
- Preserve stable IDs, resolved parameters, fingerprints, disposition, derivations, deviations, lineage, subject/plan identity, and named source digests.
- The Python distribution remains `compliance-tooling`; the repository root must not become a Python project.

ADR 0007 successor contracts remain bounded work. Do not redesign detailed requirement/realization assurance semantics while implementing them.

## Validation

For a working-tree inner loop, run:

```sh
cd tooling
uv run --frozen python -m unittest discover -s tests -v
```

After committing the candidate revision and ensuring the outer checkout is clean, run from the repository root:

```sh
bash tooling/scripts/validate-tooling.sh
```

Run installed/package/release gates when their contracts are affected. The canonical composed feature suite belongs to `verification/scenarios/`; do not duplicate it here. Keep generated artifacts out of Git and update the applicable tooling document and decision log when a domain contract changes.
