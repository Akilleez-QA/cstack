#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
if [ "${1:-}" = --setup ]; then
  "$PY" -m pip install -r ci/requirements.txt
  exit
fi
suite_python() {
  "$PY" -B -m unittest discover -s tests
  "$PY" -B -O -m unittest discover -s tests
  for domain in foundations/*; do
    [ -d "$domain/tests" ] || continue
    (cd "$domain" && "$PY" -B -m unittest discover -s tests && "$PY" -B -O -m unittest discover -s tests)
  done
}
suite_links() { "$PY" -B tools/check_links.py; }
suite_readme() { "$PY" -B tools/check_readme.py; }
suite_refrigeration() { PYTHON="$PY" bash tools/e2e_refrigeration.sh; }
suite_gitleaks() { gitleaks dir . --no-banner; }
suite_trufflehog() { bash ci/scan-secrets.sh; }
want=("$@")
[ ${#want[@]} -gt 0 ] || want=(python links refrigeration gitleaks trufflehog)
for suite in "${want[@]}"; do
  declare -F "suite_$suite" >/dev/null || { echo "unknown suite: $suite"; exit 64; }
  "suite_$suite"
done
