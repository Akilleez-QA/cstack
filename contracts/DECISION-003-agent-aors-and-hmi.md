# Agent areas of responsibility

The host registry assigns identifiers, scopes and effect limits. Requests cannot enlarge authority. External effects require explicit approval from the configured human approver.

Use `aors/fleet.json` as a minimal example and validate it with `adapters/aor_registry.py`. Agent sessions are exposed through `tools/cstack_mcp.py`.

The standalone CLI also resolves ask through ApprovalPort. Its terminal/file adapter
is a trusted local host channel, separate from the AOR Scheduled channel and
approvals.db. File answers bind exact request digests; requests cannot select an
answer source. Without an approver the CLI records a decline. See the
[CLI approval interface](../docs/icd/icd-foundations.md#local-cli-approval-interface).
