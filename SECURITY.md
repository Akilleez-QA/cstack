# Security

Report vulnerabilities privately by email: craig@nh3.biz (security contact). Do not open a public issue.

Include what you found, how to reproduce it, and the commit you tested. You will get a reply within 7 days.

Supported: the latest commit on `main`.

The TruffleHog suite in `ci/scan-secrets.sh` (also called by CI and `ci/run-local.sh`) scans the filesystem and branch history with `.trufflehog-exclude-paths.txt`. Its exact paths cover the two salted SHA-256 blocked-word stores and their original loose Git blobs, which PhraseAccessToken misidentifies as credentials. No detector or directory is excluded.
