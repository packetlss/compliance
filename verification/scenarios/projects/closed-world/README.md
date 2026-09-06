# Closed-world company assessment

This synthetic scenario implements the bounded acceptance cases in
[#78](https://github.com/packetlss/compliance/issues/78). Nothing represents a real
organization, asset, credential, assessor or certification.

Host A/B have a named IAM requirement. Their realization resides only in the
separately materialized environment-private source. Both observations preserve the
same original service assertion; each host also needs its own observed relationship.
Entity A's supplied label selects a company target with three required objectives,
each requiring a qualifying CE+-style attributable assertion. Entity B lacks that
assignment. System S has its own separately assigned objective and deliberately
lacks a realization, retaining `not_implemented` and a failing requirement. A retired
host remains an explicit inactive accounting row.

The public CLI proof in `scripts/assert-operation.py` exercises exact A/B/entity
success, missing and wrong-operation children, document copies, frozen membership
tampering, historical mapping/report reconstruction after mutable inputs are removed,
positive/negative/inconclusive/missing/stale/invalid assertions, beneficiary mismatch,
criterion error, unsafe routing refusal, missing relationship evidence, unassigned and
inactive rows, empty selection and missing-realization behavior.

Run through the canonical scenario gate from a clean committed candidate. Focused
working-tree execution copies all sources and this project into a temporary non-Git
assembly before invoking `compliance`. The checked-in private source is never the
execution source. Generated evidence, plans and results remain temporary.

Results establish only exact supplied company-policy conclusions at the recorded
instant. Governance owns inventory exhaustiveness, external applicability, assertion
truth and demonstration sufficiency. Passing mapped objectives never establishes
framework conformity, certification, legal compliance or continuous effectiveness.
