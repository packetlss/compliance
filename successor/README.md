# Temporary successor source area

This directory contains only bootstrap instructions. No application or production
platform has been selected or implemented here.

[ADR 0025](../docs/adr/0025-trusted-snapshot-successor.md) and the existing
[successor architecture](../docs/SUCCESSOR_ARCHITECTURE.md) own the accepted target.
Follow [AGENTS.md](AGENTS.md), the [development lane and activation checklist](../docs/DEVELOPMENT_WORKFLOW.md#successor-lane-activation)
and the [repository/cutover contract](../docs/REPOSITORIES.md#successor-repository-strategy).

#208 prepares routing on main. Lane activation is pending a human bootstrap merge
and recorded administrative checkpoint. #209 is blocked until both are complete.
`scripts/dev foundation` runs actual infrastructure tests with Python 3, Git, Bash
and jq. A pass does not establish application semantics, acceptance stories or
Linux/native macOS packaged execution; those responsibilities are pending #209.
