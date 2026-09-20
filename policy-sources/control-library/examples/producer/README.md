# Package observation producer example

These reviewed authored examples belong to the policy owner of `linux.packages/v1`.
They are synthetic source material; generated observations and schema exports remain
untracked. The canonical schema stays in the policy artifact under `policies/` and
is discoverable through the [experimental producer CLI](../../../../tooling/docs/producer-interface.md).
No schema or release ownership moves into tooling.

`collect_packages.py` constructs an ordinary typed Evidence document from
`package-observation.json`. Its only dependencies are Python's standard library.
The caller supplies identity, subject and collection instant:

```sh
python -I -S collect_packages.py \
  --id evidence:external-example:001 --subject host/producer-example \
  --collected-at 2000-01-01T00:00:00Z \
  --observation package-observation.json > /tmp/package-evidence.json
```

`linux-packages.json` is the reviewed expected document. The observation contains
`auditd` and `curl`, with nested extensions that construction must preserve.
Envelope, subject and collector extensions are ordinary authored content too.
They do not become supported criterion inputs or authenticated provenance merely
because the schema permits them. The old timestamp deliberately demonstrates that
document validity makes no freshness claim.

`conformance.json` contains 11 small cases applied to that document: two valid
cases and nine invalid cases. Each `changes` entry replaces or removes exactly the
listed path in a fresh copy. These are test vectors, not a patch API or a new
producer format. The independent policy resource tests verify their schema outcomes,
ordinary construction, exact document equality and existing complete-document digest
behavior. The installed scenario exercise checks the same vectors through the CLI.

Collectors know no Control IDs, desired package sets or policy thresholds. A separate
scenario proves the same observation works with the existing required-package and
only-allowed-package criteria. Subject governance and inventory validation remain
separate; an observed package inventory does not choose policy or correct governed
subject facts.
