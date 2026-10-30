# Shields control board: design (scaffold only, NOT deployed)

## What it is
An **HMI faceplate over the shields ledger** (`ledger.jsonl` locally, `shields:ledger` on the board). It shows, per machine:
- **desired** level (the last signed decision);
- **reported** level and outcome from the machine's last check-in;
- the age of that check-in (STALE after 3 minutes);
- the decision → attempt → receipt audit trail.
It never shows "applied" unless a machine's receipt says so. A missing receipt is shown as UNKNOWN. Big buttons (All clear / L1 / L2) are the only way to issue a decision. The faceplate does not run anything itself.

## Why it lives outside the tailnet
At L2 the tailnet is severed, so a tailnet-hosted board would be unreachable just when it's needed. The board runs on **Vercel (team Akilleez-QA)** at a custom domain chosen at deploy time (env only: `SHIELDS_BOARD_URL` on the poller, `SHIELDS_BOARD_HOST` in shields; no hostname is hard-coded). It has **no inbound path** to any machine. Machines **pull**.

## Data flow (pull model)
```
the owner (phone PWA, Clerk passkey/MFA) --POST /api/level--> board: decision record + desired state {machine, level, seq++, decision_id, issued_at, expires_at, rollback_min}
machine poller --GET /api/state/<machine> (every 60 s)--> {payload + served_at, sig = HMAC-SHA256(per-machine key, canonical JSON)}
poller verifies -> /usr/local/sbin/shields up|restore|confirm -> reads level back -> POST /api/checkin {receipt, HMAC-signed}
```
- **Outbound allowlist at every level**: the poller uid (`meta skuid "shields-poller"` → tcp/443) and the board's resolved IPs on 443 (see `poller/ALLOWLIST.md`, implemented in `shields/lib/shields-local.sh`).
- **Check-in replay guard**: each `/api/checkin` payload carries `cseq` (strictly increasing per machine) and a single-use 128-bit `nonce` inside the HMAC, plus `ts` (±5 min). The board accepts it only if `cseq` beats the last accepted value and the nonce is unseen (one atomic Redis EVAL), else 409.
- **Fail closed**: network error, bad signature, wrong machine, stale `served_at` (more than 5 min), `seq` going backwards (replay), expired decision, unreadable local level, or no key at all all mean **HOLD**: keep the last verified level and never lower. Tested locally 2026-10-24 (`dry-runs/poller-selftest.txt`).
- **Local wins over stale board**: a console or box-script change newer than the board decision isn't overridden downward until the board issues a newer decision.
- **Dead-man backup**: every raise arms the local auto-rollback timer (default 60 min). The poller cancels it (`shields confirm`) only after a *second* verified poll for the same decision. If the board is gone, the timer brings the machine back, so the owner can't be locked out by a dead board. The timer is the one deliberate exception to "never lower without a verified decision".

## Auth
- Clerk with **one allowed user** (`SHIELDS_ALLOWED_USER_ID`). Sign-up disabled. Passkey as first factor, TOTP as second factor, both enforced in the Clerk dashboard.
- `/api/level` also requires **fresh MFA** (`has({ reverification: "strict_mfa" })`, client `useReverification`).
- Machine routes (`/api/state/*`, `/api/checkin`) bypass Clerk and are authenticated by per-machine HMAC.
- **HMAC keys**: one per machine, generated ON that machine (`openssl rand -hex 32`), stored there as an encrypted systemd credential (rig) or a root-only file outside /workspace (box), and pasted by the owner into Vercel env `SHIELDS_HMAC_MAIN_RIG` / `SHIELDS_HMAC_BOX`. Never in repo files, the workspace, chat, or logs.
- Security headers: HSTS, frame-ancestors none, noindex, and a per-request nonce CSP from `middleware.ts` (`lib/csp.ts`): no `'unsafe-inline'`, `'strict-dynamic'`, Clerk host decoded from the publishable key or `SHIELDS_CLERK_FAPI_HOST`. The service worker never caches `/api/*`.

## Ledger mapping (POODO)
| Event | Record |
|---|---|
| Button press | `decision` {authorized_by: board:<clerk user>, level, scope, reason, rollback_min} |
| Poller acts | `receipt` {machine, outcome applied/failed/unknown/held, before/after fingerprint = sha256(`shields status`)[:16], checks} |
| Poller holds | `receipt` outcome `held` + reason |
The box-side scripts (`shields-up.sh`, `all-clear.sh`) write the same three record types to `/workspace/ops/shields/ledger.jsonl`. Merging the two ledgers is a later step: the poller could also append its receipts locally.

## Scaffold (this folder)
- `app/page.tsx`: faceplate; `app/layout.tsx`: Clerk + SW registration; `public/manifest.webmanifest`, `sw.js`, `icon.svg`
- `app/api/state/[machine]`: signed GET; `app/api/level`: POST decision (auth + MFA); `app/api/checkin`: signed receipts; `app/api/audit`: GET ledger + status
- `lib/sign.ts`: HMAC/canonical JSON; `lib/store.ts`: Upstash Redis REST (no SDK); `middleware.ts`: Clerk + nonce CSP; `lib/csp.ts`; `lib/checkin.ts`: check-in replay guard
- `poller/shields-poller.py` (stdlib), `shields-poller.service`, `sudoers.shields-poller`, `install-rig.sh` (not run), `ALLOWLIST.md`
- `.env.example`: variable names only

## What a deploy needs (not done; the owner's instruction)
1. Domain: pick a hostname, add it to the Vercel project (DNS A → 76.76.21.21), then set `SHIELDS_BOARD_URL` in `/etc/shields-poller.env` and `SHIELDS_BOARD_HOST` for shields.
2. Vercel project under Akilleez-QA from `products/hmi/control-board/`. Marketplace: Upstash Redis (sets UPSTASH_* env).
3. Clerk app: passkeys on, MFA required, sign-ups restricted. Create the owner's user and set `SHIELDS_ALLOWED_USER_ID`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`.
4. Per-machine HMAC keys (above) in env. `npm i && npm run build` locally first; it hasn't been built yet.
5. On host-a (later, with approval): `sudo ./install-rig.sh`, then `--once --dry-run`, then `systemctl enable --now shields-poller`. On the box: a setsid loop (no systemd).
6. Re-run `./shields-up.sh --level 1 --dry-run` so the nft output includes the board IPs and the poller uid rules.
