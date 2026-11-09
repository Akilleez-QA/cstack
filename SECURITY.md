# Security

Report vulnerabilities privately by email: craig@nh3.biz (security contact). Do not open a public issue.

Include what you found, how to reproduce it, and the commit you tested. You will get a reply within 7 days.

## Supported versions

| Version | Supported |
|---|---|
| `main` (latest commit) | Yes |
| Older commits | No |

There are no release tags yet (`git tag` is empty), so no tagged version is supported separately.

## Security posture

Cstack runs on the operator's machine with no network listener of its own. Requests, tool replies, MCP frames and fleet mail are untrusted and size-bounded; authority comes only from host configuration; state files are private and never opened through symlinks; storage failures stop work instead of skipping evidence. Workcells and bridge processes are not an OS sandbox for hostile code. Details: [software management plan §7](docs/plan/software-management-plan.md#7-security-privacy-and-secure-coding) and [limitations](docs/guides/explanation/limitations.md#misuse-and-security-considerations).

## Secret scanning


The TruffleHog suite in `ci/scan-secrets.sh` (also called by CI and `ci/run-local.sh`) scans the filesystem and branch history with `.trufflehog-exclude-paths.txt`. Its exact paths cover the two salted SHA-256 blocked-word stores and their original loose Git blobs, which PhraseAccessToken misidentifies as credentials. No detector or directory is excluded.
