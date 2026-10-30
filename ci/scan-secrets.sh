#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
trufflehog filesystem . --no-update --json --fail --exclude-paths .trufflehog-exclude-paths.txt
trufflehog git "file://$PWD" --branch "$(git rev-parse HEAD)" --no-update --json --fail --exclude-paths .trufflehog-exclude-paths.txt
