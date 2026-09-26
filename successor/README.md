# Temporary successor source area

This directory contains only bootstrap instructions. No application or production
platform has been selected or implemented here.

[ADR 0025](../docs/adr/0025-trusted-snapshot-successor.md) and the existing
[successor architecture](../docs/SUCCESSOR_ARCHITECTURE.md) own the accepted target.
Follow [AGENTS.md](AGENTS.md), the [development lane and activation checklist](../docs/DEVELOPMENT_WORKFLOW.md#successor-lane-activation)
and the [repository/cutover contract](../docs/REPOSITORIES.md#successor-repository-strategy).

PR #210 merged the #208 routing
bootstrap. Before starting successor work, check the recorded activation checkpoint
in #208, linked from
roadmap #85. Bootstrap merge
and branch creation alone do not unblock #209.
`scripts/dev foundation` runs actual infrastructure tests with Python 3, Git, Bash
and jq. A pass does not establish application semantics, acceptance stories or
Linux/native macOS packaged execution; those responsibilities are pending #209.
