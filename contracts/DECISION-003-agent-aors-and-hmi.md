# Agent areas of responsibility

The host registry assigns identifiers, scopes and effect limits. Requests cannot enlarge authority. External effects require explicit approval from the configured human approver.

Use `aors/fleet.json` as a minimal example and validate it with `adapters/aor_registry.py`. Agent sessions are exposed through `tools/cstack_mcp.py`.
