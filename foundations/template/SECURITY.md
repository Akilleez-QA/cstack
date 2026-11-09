# Security

## Reporting a vulnerability

Report a vulnerability privately to craig@nh3.biz. Do not open a public issue. Include the affected file, the input that triggers it and the commit.

## Supported versions

| Version | Supported |
|---|---|
| Latest commit on `main` | Yes |
| Tags | None exist yet (`git tag --list` is empty) |

A fix to the bridge here is not applied to existing Foundations automatically; the CHANGELOG says when a fix should be ported to copies.

## Security posture

- The bridge reads JSON-RPC from stdin and writes to stdout. It takes no command-line options or paths, opens no network connection, starts no process and reads or writes no files.
- Every input frame is bounded (65 536 bytes, depth 32, 4096 nodes, 1024-character strings, 15-digit integers; integers only) and every object is checked against an exact field set. Responses are bounded to 1 MiB.
- No runtime dependencies. CI scans the full Git history with gitleaks on every push and pull request.

Details: [software management plan §7](docs/plan/software-management-plan.md#7-security-privacy-and-secure-coding) and [ICD §6](docs/icd/icd-cstack.md#6-security-and-input-bounds).
