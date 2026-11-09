# Security

## Reporting

Report a vulnerability privately to craig@nh3.biz. Do not open a public issue. Include the affected file, the input that triggers it and the commit.

## Supported versions

| Version | Supported |
|---|---|
| Latest commit on `main` (0.1.0, untagged) | Yes |
| Anything older | No |

No release tags exist yet; this table will list tags once they do.

## Security posture

- The bridge reads JSON-RPC from stdin only. It opens no network connection, writes no files, starts no processes, reads no environment variables and accepts no command-line arguments.
- Parsing fails closed: 64 KiB frames, depth 32, 16384 nodes, 1024-character strings, 15-digit integers, no floats, no duplicate keys. Each tool also checks its own fields and refuses unknown ones.
- No runtime dependencies. GitHub Actions are updated weekly by Dependabot. CI runs gitleaks on the full history.
- Results are observations only and never control actions. See [Limitations and safety-relevant use](docs/guides/explanation/limitations.md).
