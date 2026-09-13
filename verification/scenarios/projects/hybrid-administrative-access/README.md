# Hybrid administrative access

This fixed-time synthetic scenario assesses exactly one Linux administrative
bastion and one SaaS administration tenant in a single operation. Both enter
the factual `administrative-access=managed` scope and receive the same narrow
Objective: interactive administrative access is gated by centrally managed
identity controls, while unmanaged local or guest access paths are disabled.

The Linux realization proves that meaning through the company IAM domain, the
approved SSH operator group, and no unmanaged interactive local accounts. The
SaaS realization proves it through enforced SSO and disabled guest access. The
Linux member separately receives the direct `company.linux-server-operations@1`
technical package policy; it does not gain a synthetic Objective for that policy.

Fresh valid evidence makes every Linux check pass. The SaaS fixture makes SSO
pass but reports guest access as enabled, producing an attributable `fail`, not
an `unknown`. The one two-member operation therefore has complete accounting and
`all_passed=false`. Coverage is current policy expectation only; historical
explanation uses the exact plan/result pair and does not claim framework
conformity, inventory completeness, continuous effectiveness, or remediation.
