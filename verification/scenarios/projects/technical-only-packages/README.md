# Technical-only package assessment

This fixed-time synthetic scenario selects `host/technical-A` through the
`managed-linux` group and assigns one technical baseline. The baseline requires
the native Linux `auditd` package and `linux.packages/v1` evidence no older than
24 hours. Planning, assessment, frozen-operation accounting, and historical
qualification use the public CLI. The happy path deliberately contains no
Requirement, RequirementBaseline assessment, ControlRealization, external
mapping, or synthesized `not_implemented` object.

Canonical mutations distinguish valid negative evidence (`FAIL`), missing
evidence (`UNKNOWN` plus `absent`), stale evidence (`UNKNOWN` plus its exact latest
candidate), schema-invalid evidence (`UNKNOWN` plus minimized attributable
diagnostics), ambiguous greatest-instant documents, canonical-identical copies,
and each closed criterion execution/decision `ERROR` class. A pinned overlay tailors `[auditd]` to
`[auditd, aide]`; its plan differs relationally from the base plan. Assigning
the divergent base and child together is non-assessable. No digest is golden.

The conclusion is only about the exact supplied synthetic host, assignment,
policy, evidence, evaluator, and recorded instant. It says nothing about other
assets, package provenance, continuous state, or external conformity.
