#!/usr/bin/env bash
# The CI suites in one script: run locally now, and called by .github/workflows/ci.yml (PR #438, held until the
# Actions budget is fixed) so CI and local runs cannot drift. Prints a PASS/FAIL/SKIP summary; non-zero if any failed.
#
#   bash ci/run-local.sh --setup            # once: a venv with ci/requirements.txt in ~/.cache/cstack-ci/venv
#   bash ci/run-local.sh                    # every suite: python throttle node links gitleaks
#   bash ci/run-local.sh python links       # just these
#
# Suites run with HOME pointed at an empty temp dir and without the systemd user bus, as on a GitHub runner, so a test
# that leans on this host fails here too. What CI deliberately leaves out is in ci/host-only.txt, with reasons.
# PYTHON picks the interpreter (default: the venv if present, else python3). GITLEAKS picks the gitleaks binary.
# gitleaks scans the commits in CI_BASE..HEAD (default: merge-base with origin/main); without gitleaks on PATH the
# suite is SKIP locally and FAIL under CI=true.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
VENV=${CI_VENV:-${HOME}/.cache/cstack-ci/venv}
ALL=(python throttle node links gitleaks trufflehog)

if [ "${1:-}" = --setup ]; then
  python3 -m venv "$VENV" && "$VENV/bin/pip" install -q -r ci/requirements.txt && echo "venv ready: $VENV"; exit
fi
PY=${PYTHON:-}
[ -n "$PY" ] || { [ -x "$VENV/bin/python" ] && PY=$VENV/bin/python || PY=$(command -v python3); }
# subprocesses that call plain `python3` (pixel-diff, throttle tests) must get the same interpreter and its packages
PYBIN=$(cd "$(dirname "$PY")" && pwd); export PATH="$PYBIN:$PATH"

SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/cstack-ci.XXXXXX"); trap 'rm -rf "$SANDBOX"' EXIT
clean() {  # run "$@" as a GitHub runner would see it: empty HOME, no user systemd bus, no inherited XDG state
  env -u XDG_RUNTIME_DIR -u DBUS_SESSION_BUS_ADDRESS -u XDG_STATE_HOME -u XDG_CONFIG_HOME -u XDG_CACHE_HOME \
      -u WORKERS_DIR -u CSTACK_ROOT HOME="$SANDBOX/home" "$@"
}
mkdir -p "$SANDBOX/home"

host_only() { grep -v '^#' ci/host-only.txt | awk -v k="$1" '$1 == k {print $2}'; }

suite_python() {
  "$PY" -c 'import jsonschema, cryptography, PIL, numpy' 2>/dev/null \
    || { echo "missing Python test packages for $PY; run: bash ci/run-local.sh --setup (or pip install -r ci/requirements.txt)"; return 1; }
  clean "$PY" -B -m unittest discover -s tests -v 2>&1 | tee "$SANDBOX/unittest.log" | grep -E '(FAIL|ERROR)(:| \()|^Ran |^OK|^FAILED'
  local rc=${PIPESTATUS[0]}
  grep -oE "skipped ['\"].*['\"]$" "$SANDBOX/unittest.log" | sort | uniq -c | sed 's/^/  /'
  [ "$rc" -eq 0 ] || grep -A30 -E '^(FAIL|ERROR):' "$SANDBOX/unittest.log" | head -200
  return "$rc"
}

suite_throttle() { clean bash forge/endoforge/tools/throttle/test/run.sh; }

suite_node() {
  local f fails=0 n=0 excluded
  excluded=$(host_only node)
  local files=() ; while IFS= read -r f; do files+=("$f"); done < <(
    cd forge/endoforge && { git ls-files '*.test.mjs'; echo tools/job/test/run.mjs; echo tools/atomizer/test/run.mjs; } | sort -u)
  for f in "${files[@]}"; do
    if grep -qxF "forge/endoforge/$f" <<<"$excluded"; then echo "HOST-ONLY $f (ci/host-only.txt)"; continue; fi
    n=$((n+1))
    if (cd forge/endoforge && clean timeout 300 node "$f") >"$SANDBOX/node.log" 2>&1; then echo "PASS $f"
    else echo "FAIL $f"; sed 's/^/    /' "$SANDBOX/node.log" | grep -v -E '^    (PASS|ok|✔)' | tail -40; fails=$((fails+1)); fi
  done
  echo "node: $((n-fails))/$n files passed"; [ "$fails" -eq 0 ]
}

suite_trufflehog() { bash ci/scan-secrets.sh; }

suite_links() { "$PY" tools/check_links.py; }

suite_gitleaks() {
  local gl=${GITLEAKS:-$(command -v gitleaks)} base=${CI_BASE:-}
  if [ -z "$gl" ]; then
    echo "gitleaks not installed (set GITLEAKS=/path/to/gitleaks)"; [ "${CI:-}" = true ] && return 1; return 75
  fi
  [ -n "$base" ] || base=$(git merge-base HEAD origin/main) || { echo "no merge-base with origin/main; set CI_BASE"; return 1; }
  echo "gitleaks $("$gl" version) on $(git rev-list --count "$base..HEAD") commit(s) $base..HEAD"
  "$gl" git --config .gitleaks.toml --log-opts="$base..HEAD" --redact --no-banner .
}

# every host-only path must exist, or the list has rotted
missing=$(grep -v '^#' ci/host-only.txt | awk 'NF {print $2}' | while read -r p; do [ -e "$p" ] || echo "$p"; done)
[ -z "$missing" ] || { echo "ci/host-only.txt names paths that do not exist: $missing"; exit 1; }

want=("$@"); [ ${#want[@]} -gt 0 ] || want=("${ALL[@]}")
declare -A status secs; failed=0
for s in "${want[@]}"; do
  declare -F "suite_$s" >/dev/null || { echo "unknown suite: $s (have: ${ALL[*]})"; exit 64; }
  [ "${GITHUB_ACTIONS:-}" = true ] && echo "::group::$s" || echo "=== $s"
  start=$SECONDS; "suite_$s"; rc=$?; secs[$s]=$((SECONDS-start))
  case $rc in 0) status[$s]=PASS ;; 75) status[$s]=SKIP ;; *) status[$s]=FAIL; failed=1 ;; esac
  [ "${GITHUB_ACTIONS:-}" = true ] && echo "::endgroup::"
  [ "${status[$s]}" = FAIL ] && [ "${GITHUB_ACTIONS:-}" = true ] && echo "::error::suite $s failed"
done
echo; echo "ci/run-local.sh summary ($("$PY" -V 2>&1), node $(node -v 2>/dev/null || echo missing))"
for s in "${want[@]}"; do printf '  %-5s %-9s %4ss\n' "${status[$s]}" "$s" "${secs[$s]}"; done
[ "$failed" -eq 0 ] && echo "RESULT: PASS" || echo "RESULT: FAIL"
exit "$failed"
