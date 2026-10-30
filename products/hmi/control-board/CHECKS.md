# control-board: local checks (2026-10-24, America/New_York)
Target: `products/hmi/control-board/`. About 600 lines without package-lock.json (1237 generated lines), so it splits into 2 PRs:
- **PR-a (API + lib + config, about 220 lines):** package.json, package-lock.json (generated), tsconfig.json, next.config.mjs, middleware.ts, .env.example, .gitignore, lib/*, app/api/**, PWA-DESIGN.md
- **PR-b (UI + PWA + poller, about 380 lines):** app/layout.tsx, app/page.tsx, public/*, poller/*, CHECKS.md

| Check | Result |
|---|---|
| `npm install` | ok (42 packages) |
| `npx tsc --noEmit` | ok, rc=0 |
| `next build` with placeholder Clerk env (fake pk_test for example.clerk.accounts.dev, no real keys) | ok, rc=0: 4 dynamic API routes, static `/`, middleware 85 kB |
| `python3 -m py_compile poller/shields-poller.py` | ok |
| `bash -n` poller/install-rig.sh, poller/selftest.sh | ok |
| `bash poller/selftest.sh` (fake engine + mock board) | 7/7: apply, confirm, tamper→HOLD, wrong machine→HOLD, unreachable→HOLD, signed all-clear lowers, replay→HOLD |
| Deploy / poller install | NOT done (by instruction) |

## Follow-up: DECISION-004 ledger gate on the board API (2026-10-25, America/New_York)
`lib/ledger.ts` verifies `ledger.py bundle` proofs (ed25519 + hash chain + quorum cosigs against `LEDGER_ROSTER_JSON`, public keys only); single use via Redis `SET NX ledger:used:<hash>`. `LEDGER_ENFORCE` unset = log-only (default).
| Check | Result |
|---|---|
| `npx tsc --noEmit` | ok |
| `npm test` (`tsc -p tsconfig.test.json && node --test`) | 17 pass (8 new in tests/ledger.test.ts) |
| Cross-implementation: proofs and canonical JSON made by the Python prototype (`tests/fixtures/make-ledger-fixture.py`) | verify byte-for-byte, incl. unicode, astral, control chars, DEL |
| Denials | different action, under-quorum, duplicate cosigner, already claimed in chain, tampered body/prev/cosig ts, truncated chain, writer-node mismatch, missing roster |
| `/api/level` level 0, enforcing | 403 before any decision/state write when the proof is absent or invalid; 409 on reuse; 10 concurrent on one intent, exactly 1 wins |
| `/api/level` levels 1, 2 | never need the ledger |
| `/api/checkin` | never refused for ledger reasons; an applied level-0 receipt without a valid proof is stored with `ledger: alarm:...` and an `alarm` record when enforcing |
| `python3 -m unittest products/hmi/ledger/test_ledger.py` | 18 ok (new: `bundle`) |

## Follow-up (c): poller verifies the all-clear proof itself (2026-10-25, America/New_York)
The HMAC proves the board sent the state; it doesn't prove the witnessed quorum authorized an all-clear. `/api/level` now keeps a verified proof as `shields:proof:<decision id>`, `/api/state/<machine>` serves it beside the signed payload (`ledger`, outside the HMAC: it is self-authenticating), and the poller re-verifies it offline with `ledger.py verify_bundle` (Python twin of `verifyIntent`) against `/etc/shields-ledger-roster.json` (public keys only). Proof must be for `{op:"all-clear"}` with this machine in scope, intent at most 24h old, never used before on this machine. `SHIELDS_LEDGER_ENFORCE=1`: bad or missing proof => HOLD current level + `poller-ledger-hold` alarm + check-in `held` (`ledger:<reason>`). Default log-only: lowers, check-in carries `ledger_note`. Raising (and 2 -> 1) never needs a proof.
| Check | Result |
|---|---|
| `python3 poller/test_ledger_proof.py` | 6 ok: raise needs no proof; enforced no-proof holds + alarms; valid proof lowers once, replay held; wrong scope / under-quorum / tampered / stale / junk held; missing verifier fails safe; log-only lowers and reports |
| `cd products/hmi/ledger && python3 -m unittest test_ledger` | 23 ok (new: `verify_bundle` against the TS fixture) |
| `bash poller/selftest.sh` | 9/9 (new T8 raise while enforcing, T9 enforced all-clear without proof → HOLD + alarm) |
| `python3 poller/test_checkin.py` | 3 ok |
| `npx tsc --noEmit`, `npm test` | ok, 17 pass |

## Follow-up (d): all-clear needs the owner's phone co-sign (2026-10-25, America/New_York)
`/api/cosign` (Clerk, allowed user) issues a single-use nonce + challenge = sha256(canon({op:"all-clear-cosign", intent, scope, nonce, exp})); the board page signs it with the phone's passkey (`navigator.credentials.get`, user verification required) and sends it as `body.cosign` with the level-0 request. `lib/cosign.ts` verifies it with node crypto only (ES256 over authenticatorData || sha256(clientDataJSON), rpId hash, origin, UP+UV, binding to the attached proof's intent hash + scope, exp <= 10 min, nonce GETDEL). It is recorded as its own `cosign` ledger record (credential id, intent, sign count) and served beside the state; the poller re-checks it with `ledger.py verify_cosign` against roster `cosigners` (public keys). `COSIGN_ENFORCE=1` (board) / `SHIELDS_COSIGN_ENFORCE=1` (poller) make it mandatory; both default OFF (verify + record only). One-time "Register this phone" button prints the PUBLIC config for `COSIGN_PASSKEY_JSON` and the rig roster.
| Check | Result |
|---|---|
| `npm test` | 21 pass (4 new in tests/cosign.test.ts: Python-pinned challenge vectors, synthetic P-256 phone, 12 rejections, gate off/enforce/single-use) |
| `cd products/hmi/ledger && python3 -m unittest test_ledger` | 24 ok (new: `verify_cosign`, same vectors) |
| `python3 poller/test_ledger_proof.py` | 14 ok (new: enforced co-sign holds on absent / wrong intent / no UV / wrong scope, applies when valid; off by default only reports) |
| `npx tsc --noEmit` | ok |

## Issue #95: signed poller heartbeats (2026-10-25)

After each HTTP check-in attempt, the poller writes `{machine, level, outcome, cseq, ts}` as a signed `checkin` using the existing `Log.write()` lock. It writes on level/outcome changes, otherwise every `SHIELDS_LEDGER_CHECKIN_SEC` (default 300); the last signed entry preserves the limit across restarts. No HTTP nonce, HMAC or other receipt fields enter the ledger body. `LEDGER_ENFORCE` and `SHIELDS_LEDGER_ENFORCE` remain off by default.

Configure the poller with the existing `LEDGER_LOG`, `LEDGER_ORIGIN` (must equal `SHIELDS_MACHINE`), `LEDGER_ROSTER`, `LEDGER_KEY`, `LEDGER_WRITER`, and whitespace-separated `LEDGER_WITNESSES` including host-a. `LEDGER_PY` optionally selects the writer module, otherwise it uses `SHIELDS_LEDGER_PY`. The service user needs access to its node log/lock, signing key and `$LEDGER_ALARMS`; no installation or host configuration was changed here.

Repository inspection found no automatic push after `Log.write()`; the shell gate only reconciles during enforced all-clear. The poller now invokes the existing `ledger.py push()` function for each witness after every ledger check-in. (The CLI exposes this transport through `reconcile`, not a `push` subcommand.) A failed push leaves the signed tail queued for the next heartbeat/change. Missing configuration, write errors and push errors only log/alarm via `$LEDGER_ALARMS`; HTTP still runs first, and ledger failures never veto a shield action. Live box configuration was not inspected.

| Exact command (run from indicated directory) | Result in this restricted workspace |
|---|---|
| `python3 -B -m unittest discover -s poller -p 'test_*.py' -v` from `products/hmi/control-board` | 27 pass: 13 check-in tests + 14 proof/co-sign tests. Includes signed reader/witness verification, repeat/change/restart rates, push recovery, HTTP independence, write/alarm failure, and raising with a broken ledger. Keys and state are temporary; witness transport uses in-memory HTTP request/response bodies. |
| `python3 -B -m unittest -v test_ledger` from `products/hmi/ledger` | 24 run: 21 pass, 3 errors because the sandbox denies socket creation (`PermissionError: Operation not permitted`). Blocked: body cap HTTP, rollback HTTP, two-process witness exchange. Must rerun with loopback sockets available. |
| `env -i PATH=/usr/local/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 bash selftest.sh` from `products/hmi/control-board/poller` | Blocked before all 9 scenarios: mock HTTP board cannot start; exits 1 after its 15-second readiness deadline. Uses a clean environment and temporary HMAC key. |
| `git diff --check` from repository root | pass |
| `git diff -- products/hmi/control-board &#124; gitleaks stdin --config .gitleaks.toml --redact --no-banner` from repository root | pass, no leaks found; staging is unavailable because the shared Git directory is read-only |
